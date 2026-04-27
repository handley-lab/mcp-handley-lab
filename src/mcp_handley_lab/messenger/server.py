"""Multi-platform Claude messenger server.

Receives messages via WhatsApp webhooks and Telegram long-polling, routes
them to persistent Claude loops (one per conversation), and relays responses
back. Each conversation gets a ChatActor with an asyncio queue.

Uses loop daemon for Claude sessions — policy-based tool approval
(--permission-mode acceptEdits) instead of interactive buttons.
"""

import asyncio
import contextlib
import hashlib
import hmac
import json
import mimetypes
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
from uuid import uuid4

from mcp_handley_lab.loop.client import kill, run, spawn, terminate
from mcp_handley_lab.loop.client import read_raw as read_cells_raw
from mcp_handley_lab.loop.client import session_id as get_session_id
from mcp_handley_lab.loop.client import status as loop_status

# ---------------------------------------------------------------------------
# Environment (set via systemd EnvironmentFile or shell exports)
# ---------------------------------------------------------------------------

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_tg_allowed_raw = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
TELEGRAM_ALLOWED_CHAT_IDS: set[int] | None = (
    {int(x.strip()) for x in _tg_allowed_raw.split(",") if x.strip()}
    if _tg_allowed_raw
    else None
)

CLAUDE_PERMISSION_MODE = os.environ.get("CLAUDE_PERMISSION_MODE", "acceptEdits")
CLAUDE_DISALLOWED_TOOLS = os.environ.get("CLAUDE_DISALLOWED_TOOLS", "EnterPlanMode")
_APPEND_SYSTEM_PROMPT = (
    "Keep responses concise for mobile. "
    "When a user sends an image, sticker, video, or document, "
    "ALWAYS use the Read tool to view the file before responding. "
    "Never guess or assume the contents of media files. "
    "To send a file to the user, output send:<filename> on its own line "
    "(e.g. send:media/chart.png). Files must be under the current working directory. "
    "When sending emails, ALWAYS use draft=True to create a draft first. "
    "Present the full draft (From, To, Subject, Body) to the user and wait for "
    "explicit approval before calling send with mode='send_draft'. "
    "Never call send_draft without first showing the draft and receiving approval."
)

MESSENGER_DIR = Path.home() / "messenger"
GRAPH_API = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


_TG_ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"
_TG_ESCAPE_RE = re.compile(r"([" + re.escape(_TG_ESCAPE_CHARS) + r"])")
# URL chars that need escaping in MarkdownV2
_TG_URL_ESCAPE_RE = re.compile(r"([\\)`(])")
# Link regex that handles balanced parentheses in URLs (e.g. Wikipedia)
_TG_LINK_RE = re.compile(r"\[([^\]]+)\]\(((?:[^()]*|\([^()]*\))*)\)")


def _md_to_tg(text: str) -> str:
    """Convert markdown text to Telegram MarkdownV2 format.

    Preserves fenced code blocks and inline code as-is (Telegram handles them),
    escapes special chars in everything else.
    """
    parts = re.split(r"(```[\s\S]*?```|`[^`]+`)", text)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            result.append(part)
        else:
            result.append(_escape_tg_text(part))
    return "".join(result)


def _escape_tg_text(text: str) -> str:
    """Escape MarkdownV2 special chars in plain text, preserving links."""

    def _replace_link(m: re.Match) -> str:
        link_text = _TG_ESCAPE_RE.sub(r"\\\1", m.group(1))
        url = _TG_URL_ESCAPE_RE.sub(r"\\\1", m.group(2))
        return f"[{link_text}]({url})"

    # Replace links first, then escape remaining text
    result: list[str] = []
    last_end = 0
    for m in _TG_LINK_RE.finditer(text):
        result.append(_TG_ESCAPE_RE.sub(r"\\\1", text[last_end : m.start()]))
        result.append(_replace_link(m))
        last_end = m.end()
    result.append(_TG_ESCAPE_RE.sub(r"\\\1", text[last_end:]))
    return "".join(result)


def _extract_send_files(text: str, cwd: Path) -> tuple[list[Path], str]:
    """Extract send:<path> markers and return (files, cleaned_text)."""
    cwd_resolved = cwd.resolve()
    files: list[Path] = []
    seen: set[Path] = set()
    clean_lines: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^send:(.+)$", line.strip())
        if m:
            raw = m.group(1).strip()
            # Try relative to cwd first, then absolute/home-relative
            matched = False
            for candidate in (cwd / raw, Path(raw).expanduser()):
                p = candidate.resolve()
                if p.is_relative_to(cwd_resolved) and p.is_file() and p not in seen:
                    files.append(p)
                    seen.add(p)
                    matched = True
                    break
            if matched:
                continue
        clean_lines.append(line)
    return files, "\n".join(clean_lines)


_MESSAGE_LOG_MAX = 200


def _extract_usage(cells: list[dict]) -> dict | None:
    """Extract usage info from the last cell's result event.

    modelUsage is keyed by model name, e.g.:
      {"claude-opus-4-7": {"inputTokens": ..., "contextWindow": ..., "costUSD": ...}}
    We sum across models and take max contextWindow.
    """
    if not cells:
        return None
    last_cell = cells[-1]
    for event in reversed(last_cell.get("events", [])):
        if event.get("type") == "result":
            model_usage = event.get("modelUsage") or {}
            if not model_usage:
                continue
            input_tokens = output_tokens = context_window = 0
            for model_data in model_usage.values():
                if isinstance(model_data, dict):
                    input_tokens += model_data.get("inputTokens", 0)
                    output_tokens += model_data.get("outputTokens", 0)
                    context_window = max(
                        context_window, model_data.get("contextWindow", 0)
                    )
            return {
                "context_window": context_window,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
    return None


def _context_footer(usage: dict) -> str:
    """Format a context usage footer line from usage dict."""
    ctx = usage["context_window"]
    if not ctx:
        return ""
    used = usage["input_tokens"] + usage["output_tokens"]
    pct = used / ctx * 100
    return f"{pct:.0f}% context"


COMMANDS = frozenset({"/reset", "/cancel", "/model", "/help", "/status"})


def _parse_command(text: str) -> tuple[str, str] | None:
    """Parse a command from text. Returns (cmd, args) or None if not a command."""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    parts = stripped.split(None, 1)
    cmd_token = parts[0]
    args = parts[1] if len(parts) > 1 else ""
    # Strip @botname suffix from command token only (Telegram)
    if "@" in cmd_token:
        cmd_token = cmd_token.split("@", 1)[0]
    cmd = cmd_token.lower()
    if cmd not in COMMANDS:
        return None
    return cmd, args


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class Platform(Protocol):
    """Messaging platform abstraction."""

    def send_text(
        self, conversation_id: str, text: str, reply_to: str | None = None
    ) -> str | None: ...
    def send_media(
        self,
        conversation_id: str,
        path: Path,
        caption: str = "",
        reply_to: str | None = None,
    ) -> str | None: ...
    def send_typing(self, conversation_id: str) -> None: ...


@dataclass
class IncomingEvent:
    conversation_id: str
    kind: str  # "text", "command"
    text: str
    platform: Platform
    message_id: str | None = None
    reply_to_id: str | None = None
    media_type: str | None = None  # "image", "video", "audio", "document", etc.
    media_id: str | None = None  # WA media_id or TG file_id
    media_mime: str | None = None


@dataclass
class WAMessage:
    """Parsed WhatsApp incoming message."""

    sender: str
    text: str | None = None
    media_type: str | None = None
    media_id: str | None = None
    caption: str | None = None
    mime_type: str | None = None
    message_id: str | None = None
    reply_to_id: str | None = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_MEDIA_BYTES = 50 * 1024 * 1024  # 50 MB (Telegram bot limit)
_WA_MAX_MEDIA_BYTES = 16 * 1024 * 1024  # 16 MB (WhatsApp Cloud API limit)

# ---------------------------------------------------------------------------
# WhatsApp platform
# ---------------------------------------------------------------------------

_WA_TEXT_MAX = 4096


_WA_MEDIA_TYPES = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".mp4": "video",
    ".3gp": "video",
    ".mp3": "audio",
    ".ogg": "audio",
    ".amr": "audio",
    ".aac": "audio",
}


class WhatsAppPlatform:
    def send_text(
        self, conversation_id: str, text: str, reply_to: str | None = None
    ) -> str | None:
        text = _truncate(text, _WA_TEXT_MAX)
        payload: dict = {"type": "text", "text": {"body": text}}
        if reply_to:
            payload["context"] = {"message_id": reply_to}
        return _send_whatsapp(conversation_id, payload)

    def send_media(
        self,
        conversation_id: str,
        path: Path,
        caption: str = "",
        reply_to: str | None = None,
    ) -> str | None:
        media_type = _WA_MEDIA_TYPES.get(path.suffix.lower(), "document")
        media_id = _upload_wa_media(path)
        if not media_id:
            return None
        media_payload: dict = {"id": media_id}
        if caption:
            media_payload["caption"] = _truncate(caption, _WA_TEXT_MAX)
        payload: dict = {"type": media_type, media_type: media_payload}
        if reply_to:
            payload["context"] = {"message_id": reply_to}
        return _send_whatsapp(conversation_id, payload)

    def send_typing(self, conversation_id: str) -> None:
        pass  # WhatsApp Cloud API has no typing indicator


def _upload_wa_media(path: Path) -> str | None:
    """Upload a file to WhatsApp and return the media_id."""
    file_size = path.stat().st_size
    if file_size > _WA_MAX_MEDIA_BYTES:
        mb = file_size / (1024 * 1024)
        print(
            f"WA upload rejected: {path.name} is {mb:.1f} MB (limit 16 MB)",
            flush=True,
        )
        return None
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    boundary = uuid4().hex
    body = bytearray()
    # messaging_product field
    body += f"--{boundary}\r\n".encode()
    body += (
        b'Content-Disposition: form-data; name="messaging_product"\r\n\r\nwhatsapp\r\n'
    )
    # type field
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="type"\r\n\r\n{mime}\r\n'.encode()
    # file field
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode()
    body += f"Content-Type: {mime}\r\n\r\n".encode()
    body += path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()

    upload_url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/media"
    req = Request(
        upload_url,
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get("id")
    except HTTPError as e:
        print(
            f"WA media upload error {e.code}: {e.read().decode(errors='replace')}",
            flush=True,
        )
        return None


def _send_whatsapp(to: str, payload: dict) -> str | None:
    payload["messaging_product"] = "whatsapp"
    payload["to"] = to
    req = Request(
        GRAPH_API,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            print(f"WA sent to {to}: {resp.status}", flush=True)
            msgs = data.get("messages", [])
            return msgs[0]["id"] if msgs else None
    except HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"WhatsApp API error {e.code}: {body}", flush=True)
        return None


# ---------------------------------------------------------------------------
# Media download helpers (SSRF-safe, size-limited, streaming)
# ---------------------------------------------------------------------------

_CHUNK_SIZE = 65536

_WA_CDN_DOMAINS = {
    "lookaside.fbsbx.com",
    "scontent.whatsapp.net",
    "mmg.whatsapp.net",
    "fbcdn.net",
}

_EXT_NORMALIZE = {".jpe": ".jpg", ".jpeg": ".jpg"}


_MAX_REDIRECTS = 5


def _validate_url(url: str) -> None:
    """Reject non-HTTPS and private/reserved IPs (SSRF defense)."""
    import ipaddress
    import socket

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Only HTTPS URLs allowed, got {parsed.scheme}")
    host = parsed.hostname or ""

    # Check against WA CDN allowlist
    normalized = host.lower().rstrip(".")
    for domain in _WA_CDN_DOMAINS:
        if normalized == domain or normalized.endswith("." + domain):
            return

    # Resolve all IPs and check for private ranges
    for info in socket.getaddrinfo(host, None):
        addr = ipaddress.ip_address(info[4][0])
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        ):
            raise ValueError(f"URL resolves to non-public IP: {addr}")


class _SafeRedirectHandler(HTTPRedirectHandler):
    """Validates each redirect hop against SSRF checks."""

    def __init__(self):
        self._redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self._redirect_count += 1
        if self._redirect_count > _MAX_REDIRECTS:
            raise ValueError(f"Too many redirects (>{_MAX_REDIRECTS})")
        # Reject scheme downgrade (https → http)
        if urlparse(newurl).scheme != "https":
            raise ValueError(f"Redirect scheme downgrade rejected: {newurl}")
        _validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _safe_urlopen(req: Request, timeout: int = 30):
    """urlopen with redirect validation for SSRF defense."""
    handler = _SafeRedirectHandler()
    opener = build_opener(handler)
    return opener.open(req, timeout=timeout)


def _download_media(
    url: str,
    dest_dir: Path,
    media_type: str,
    mime_type: str | None,
    max_bytes: int = _MAX_MEDIA_BYTES,
    headers: dict | None = None,
) -> Path:
    """Download media to dest_dir with safe naming. Returns the saved path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = mimetypes.guess_extension(mime_type or "") or ".bin"
    ext = _EXT_NORMALIZE.get(ext, ext)
    filename = f"{media_type}_{int(time.time())}_{uuid4().hex[:8]}{ext}"
    dest = dest_dir / filename
    tmp = dest.with_suffix(".tmp")

    req = Request(url, headers=headers or {})
    with _safe_urlopen(req, timeout=30) as resp:
        downloaded = 0
        with open(tmp, "wb") as f:
            while True:
                chunk = resp.read(_CHUNK_SIZE)
                if not chunk:
                    break
                downloaded += len(chunk)
                if downloaded > max_bytes:
                    tmp.unlink(missing_ok=True)
                    raise ValueError(f"File exceeds {max_bytes} byte limit")
                f.write(chunk)
    tmp.rename(dest)
    return dest


def _download_wa_media(media_id: str, dest_dir: Path) -> tuple[Path, str]:
    """Download WhatsApp media by ID. Returns (path, mime_type)."""
    # Step 1: get media URL
    url = f"https://graph.facebook.com/v21.0/{media_id}"
    req = Request(url, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    media_url = data["url"]
    mime_type = data.get("mime_type", "application/octet-stream")
    file_size = data.get("file_size", 0)
    if file_size > _MAX_MEDIA_BYTES:
        raise ValueError(f"WhatsApp media too large: {file_size} bytes")
    _validate_url(media_url)

    # Step 2: download
    path = _download_media(
        media_url,
        dest_dir,
        "media",
        mime_type,
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
    )
    return path, mime_type


def _download_tg_media(file_id: str, dest_dir: Path, media_type: str) -> Path:
    """Download Telegram media by file_id. Returns the saved path."""
    # Step 1: getFile
    payload = json.dumps({"file_id": file_id}).encode()
    req = Request(
        f"{TELEGRAM_API}/getFile",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    file_info = data["result"]
    file_path = file_info["file_path"]
    file_size = file_info.get("file_size", 0)
    if file_size > _MAX_MEDIA_BYTES:
        raise ValueError(f"Telegram media too large: {file_size} bytes")

    # Step 2: download
    download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
    mime_type = mimetypes.guess_type(file_path)[0]
    return _download_media(download_url, dest_dir, media_type, mime_type)


# ---------------------------------------------------------------------------
# Telegram platform
# ---------------------------------------------------------------------------

_TG_TEXT_MAX = 4096


_TG_CAPTION_MAX = 1024

_TG_PHOTO_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


class TelegramPlatform:
    @staticmethod
    def _parse_conversation_id(conversation_id: str) -> tuple[str, str | None]:
        parts = conversation_id.split(":", 2)
        chat_id = parts[1] if len(parts) > 1 else conversation_id
        topic_id = parts[2] if len(parts) > 2 else None
        return chat_id, topic_id

    def _call(self, method: str, payload: dict) -> dict:
        url = f"{TELEGRAM_API}/{method}"
        req = Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except HTTPError as e:
            body = e.read().decode(errors="replace")
            print(f"Telegram API error {e.code} ({method}): {body}", flush=True)
            raise

    def _call_multipart(
        self, method: str, fields: dict, file_field: str, file_path: Path
    ) -> dict:
        """Send a multipart/form-data request with a file upload."""
        boundary = uuid4().hex
        body = bytearray()
        for k, v in fields.items():
            body += f"--{boundary}\r\n".encode()
            body += (
                f'Content-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
            )
        mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'.encode()
        body += f"Content-Type: {mime}\r\n\r\n".encode()
        body += file_path.read_bytes()
        body += f"\r\n--{boundary}--\r\n".encode()

        url = f"{TELEGRAM_API}/{method}"
        req = Request(
            url,
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except HTTPError as e:
            print(
                f"Telegram API error {e.code} ({method}): {e.read().decode(errors='replace')}",
                flush=True,
            )
            raise

    def send_text(
        self, conversation_id: str, text: str, reply_to: str | None = None
    ) -> str | None:
        chat_id, topic_id = self._parse_conversation_id(conversation_id)
        formatted = _md_to_tg(text)
        formatted = _truncate(formatted, _TG_TEXT_MAX)
        payload: dict = {
            "chat_id": chat_id,
            "text": formatted,
            "parse_mode": "MarkdownV2",
        }
        if topic_id:
            payload["message_thread_id"] = int(topic_id)
        if reply_to:
            payload["reply_parameters"] = {"message_id": int(reply_to)}
        try:
            result = self._call("sendMessage", payload)
        except HTTPError:
            # Fallback: retry as plain text without formatting
            payload["text"] = _truncate(text, _TG_TEXT_MAX)
            payload.pop("parse_mode", None)
            result = self._call("sendMessage", payload)
        msg_id = result.get("result", {}).get("message_id")
        return str(msg_id) if msg_id else None

    def send_media(
        self,
        conversation_id: str,
        path: Path,
        caption: str = "",
        reply_to: str | None = None,
    ) -> str | None:
        chat_id, topic_id = self._parse_conversation_id(conversation_id)
        ext = path.suffix.lower()
        if ext in _TG_PHOTO_EXTS:
            method, file_field = "sendPhoto", "photo"
        elif ext == ".gif":
            method, file_field = "sendAnimation", "animation"
        else:
            method, file_field = "sendDocument", "document"

        fields: dict = {"chat_id": chat_id}
        if topic_id:
            fields["message_thread_id"] = topic_id
        if reply_to:
            fields["reply_parameters"] = json.dumps({"message_id": int(reply_to)})
        if caption:
            formatted_caption = _md_to_tg(caption)
            fields["caption"] = _truncate(formatted_caption, _TG_CAPTION_MAX)
            fields["parse_mode"] = "MarkdownV2"

        try:
            result = self._call_multipart(method, fields, file_field, path)
        except HTTPError:
            # Fallback: send as text reference
            self.send_text(
                conversation_id, f"[File: {path.name} ({path.stat().st_size} bytes)]"
            )
            return None
        msg_id = result.get("result", {}).get("message_id")
        return str(msg_id) if msg_id else None

    def send_typing(self, conversation_id: str) -> None:
        chat_id, topic_id = self._parse_conversation_id(conversation_id)
        payload: dict = {"chat_id": chat_id, "action": "typing"}
        if topic_id:
            payload["message_thread_id"] = int(topic_id)
        with contextlib.suppress(HTTPError):
            self._call("sendChatAction", payload)


# ---------------------------------------------------------------------------
# Directory mapping
# ---------------------------------------------------------------------------


def _cwd_for_conversation(conversation_id: str) -> Path:
    parts = conversation_id.split(":", 2)
    if len(parts) == 3:
        return MESSENGER_DIR / parts[0] / parts[1] / parts[2]
    if len(parts) == 2:
        return MESSENGER_DIR / parts[0] / parts[1]
    return MESSENGER_DIR / conversation_id


def _migrate_old_dirs():
    MESSENGER_DIR.mkdir(parents=True, exist_ok=True)
    renames = {"wa": "whatsapp", "tg": "telegram"}

    old_wa = Path.home() / "whatsapp"
    if old_wa.is_dir():
        new_wa = MESSENGER_DIR / "whatsapp"
        new_wa.mkdir(parents=True, exist_ok=True)
        for child in old_wa.iterdir():
            if child.is_dir() and not (new_wa / child.name).exists():
                child.rename(new_wa / child.name)
                print(f"Migrated {child} → {new_wa / child.name}", flush=True)

    old_bridge = Path.home() / "bridge"
    if old_bridge.is_dir():
        for child in old_bridge.iterdir():
            dest_name = renames.get(child.name, child.name)
            dest = MESSENGER_DIR / dest_name
            if not dest.exists():
                child.rename(dest)
                print(f"Migrated {child} → {dest}", flush=True)


# ---------------------------------------------------------------------------
# ChatActor — one per conversation, owns a persistent loop
# ---------------------------------------------------------------------------


class ChatActor:
    def __init__(self, conversation_id: str, platform: Platform):
        self.conversation_id = conversation_id
        self.platform = platform
        self.queue: asyncio.Queue[IncomingEvent | None] = asyncio.Queue(maxsize=50)
        self.cwd = _cwd_for_conversation(conversation_id)
        self.loop_id: str | None = None
        self.session_id: str = ""
        self._model: str = ""
        self._stopped = False
        self._last_transcription: str | None = None
        self._state_file = self.cwd / "loop_state.json"
        self._msg_log_file = self.cwd / "message_log.json"
        self._message_log: dict[str, dict] = {}
        self._task: asyncio.Task | None = None

    async def start(self):
        self.cwd.mkdir(parents=True, exist_ok=True)
        self._load_state()
        self._load_message_log()
        if self._stopped:
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        """Stop the actor gracefully."""
        self._stopped = True
        with contextlib.suppress(asyncio.QueueFull):
            self.queue.put_nowait(None)  # Sentinel to unblock queue.get()
        if self._task:
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _run(self):
        while not self._stopped:
            event = await self.queue.get()
            if event is None:
                break  # Sentinel from stop()
            try:
                await self._handle(event)
            except Exception as e:
                print(f"Chat {self.conversation_id} error: {e}", flush=True)
                try:
                    self._send_text(f"Error: {e}")
                except Exception:
                    print(f"Failed to send error to {self.conversation_id}", flush=True)

    def _log_message(self, msg_id: str | None, role: str, text: str) -> None:
        if not msg_id:
            return
        self._message_log[msg_id] = {"role": role, "text": text[:200]}
        # Cap at max entries
        if len(self._message_log) > _MESSAGE_LOG_MAX:
            keys = list(self._message_log)
            for k in keys[: len(keys) - _MESSAGE_LOG_MAX]:
                del self._message_log[k]
        self._save_message_log()

    def _send_text(self, text: str, reply_to: str | None = None) -> None:
        print(f"Reply to {self.conversation_id}: {text[:200]}", flush=True)
        msg_id = self.platform.send_text(self.conversation_id, text, reply_to=reply_to)
        self._log_message(msg_id, "assistant", text)

    def _send_response(self, text: str, reply_to: str | None = None) -> None:
        """Send response, extracting any send:<file> markers for media."""
        files, clean_text = _extract_send_files(text, self.cwd)
        if clean_text.strip():
            self._send_text(clean_text, reply_to=reply_to)
        for f in files:
            msg_id = self.platform.send_media(self.conversation_id, f)
            if msg_id:
                self._log_message(msg_id, "assistant", f"[file: {f.name}]")
            else:
                try:
                    mb = f.stat().st_size / (1024 * 1024)
                    detail = f" ({mb:.1f} MB)"
                except OSError:
                    detail = ""
                self._send_text(
                    f"Failed to send {f.name}{detail} — upload rejected by platform."
                )

    def _prepare_text(self, event: IncomingEvent) -> str:
        """Build query text from event, downloading media if present."""
        text = event.text
        if event.media_id and event.media_type:
            media_dir = self.cwd / "media"
            try:
                if event.conversation_id.startswith("whatsapp:"):
                    path, _ = _download_wa_media(event.media_id, media_dir)
                else:
                    path = _download_tg_media(
                        event.media_id, media_dir, event.media_type
                    )
                if event.media_type == "audio":
                    from mcp_handley_lab.llm.registry import get_adapter

                    transcribe = get_adapter("groq", "audio_transcription")
                    result = transcribe(str(path))
                    self._last_transcription = result["text"]
                    media_ref = f"[Voice message transcription: {result['text']}]"
                else:
                    rel = path.relative_to(self.cwd)
                    media_ref = (
                        f"[User sent {event.media_type}: {rel} — "
                        f"use the Read tool on {rel} to view it]"
                    )
                text = f"{media_ref}\n{text}" if text else media_ref
            except Exception as e:
                print(f"Media download failed: {e}", flush=True)
                text = (
                    f"[Media download failed: {e}]\n{text}"
                    if text
                    else f"[Media download failed: {e}]"
                )

        # Inject reply-to context
        if event.reply_to_id and event.reply_to_id in self._message_log:
            ref = self._message_log[event.reply_to_id]
            text = f"[Replying to {ref['role']}'s message: {ref['text'][:200]}]\n{text}"

        return text

    async def _handle(self, event: IncomingEvent) -> None:
        # Log inbound message
        self._log_message(event.message_id, "user", event.text)

        # Send typing indicator
        self.platform.send_typing(self.conversation_id)

        # Dispatch commands
        if event.kind == "command":
            parsed = _parse_command(event.text)
            if parsed:
                cmd, args = parsed
                if cmd == "/reset":
                    await self._handle_reset()
                    return
                await self._handle_command(cmd, args)
                return

        text = await asyncio.to_thread(self._prepare_text, event)
        for attempt in (1, 2):
            try:
                output = await asyncio.to_thread(self._query, text)
                transcription = self._last_transcription
                if transcription:
                    output = f"> {transcription.strip()}\n\n{output}"
                    self._last_transcription = None
                # Append context usage footer
                footer = await self._get_context_footer()
                if footer:
                    output = f"{output}\n\n_{footer}_"
                self._send_response(output, reply_to=event.message_id)
                return
            except RuntimeError as e:
                if attempt == 1 and "not found" in str(e):
                    self._clear_state()
                    continue
                raise

    async def _handle_command(self, cmd: str, args: str) -> None:
        if cmd == "/help":
            self._send_help()
        elif cmd == "/cancel":
            self._send_text("Cancelled.")
        elif cmd == "/model":
            await self._handle_model(args)
        elif cmd == "/status":
            await self._handle_status()

    async def _kill_loop(self):
        """Kill the active loop. Suppresses errors to avoid wedging the actor."""
        if not self.loop_id:
            return
        try:
            await asyncio.to_thread(kill, self.loop_id)
        except Exception as e:
            print(f"kill({self.loop_id}) failed: {e}", flush=True)

    async def _handle_reset(self):
        """Handle /reset. New conversation, preserve model preference."""
        await self._kill_loop()
        self.loop_id = None
        self.session_id = ""
        self._save_state()
        self._send_text("Session reset. Send a new message to start fresh.")

    def _send_help(self):
        self._send_text(
            "Commands:\n"
            "/cancel - Cancel current operation\n"
            "/reset - New conversation\n"
            "/model [name] - Show or set model\n"
            "/status - Show session status\n"
            "/help - Show this help"
        )

    async def _handle_model(self, model_name: str):
        if not model_name:
            self._send_text(f"Current model: {self._model or 'default'}")
            return
        self._model = model_name
        self._save_state()
        if self.loop_id:
            if not self.session_id:
                sid = get_session_id(self.loop_id)
                if sid:
                    self.session_id = sid
            await self._kill_loop()
            self.loop_id = None
            self._save_state()
            self._send_text(f"Model set to {model_name}. Session restarted.")
        else:
            self._send_text(f"Model set to {model_name}.")

    async def _handle_status(self):
        if not self.loop_id:
            self._send_text("No active session.")
            return
        try:
            st = await asyncio.to_thread(loop_status, self.loop_id)
            running = "running" if st.get("running") else "idle"
            elapsed = f" ({st['elapsed_seconds']:.0f}s)" if st.get("running") else ""
            lines = [f"Session: {self.loop_id}", f"Status: {running}{elapsed}"]
            if self.session_id:
                lines.append(f"Session ID: {self.session_id}")
            if self._model:
                lines.append(f"Model: {self._model}")
            self._send_text("\n".join(lines))
        except RuntimeError as e:
            if "not_found" in str(e) or "not found" in str(e):
                self.loop_id = None
                self._save_state()
                self._send_text("Session expired. Send a new message to start fresh.")
            else:
                self._send_text(f"Status error: {e}")

    async def _get_context_footer(self) -> str:
        """Get context usage footer from last cell's events."""
        if not self.loop_id:
            return ""
        try:
            cells = await asyncio.to_thread(read_cells_raw, self.loop_id)
            usage = _extract_usage(cells)
            if usage:
                return _context_footer(usage)
        except Exception:
            pass
        return ""

    def _query(self, text: str) -> str:
        """Ensure loop exists and run text. Called via to_thread."""
        if not self.loop_id:
            args = f"--permission-mode {CLAUDE_PERMISSION_MODE}"
            if CLAUDE_DISALLOWED_TOOLS:
                args += f" --disallowed-tools {CLAUDE_DISALLOWED_TOOLS}"
            if self._model:
                args += f" --model {self._model}"
            self.loop_id = spawn(
                "claude",
                label=f"msg-{self.conversation_id[:20]}",
                cwd=str(self.cwd),
                prompt=_APPEND_SYSTEM_PROMPT,
                args=args,
                session_id=self.session_id,
            )
            self._save_state()
        output = run(self.loop_id, text, sync_timeout=-1)
        # Capture session_id for resume after kill/restart
        if not self.session_id and self.loop_id:
            sid = get_session_id(self.loop_id)
            if sid:
                self.session_id = sid
                self._save_state()
        return output

    def _load_state(self):
        with contextlib.suppress(FileNotFoundError, json.JSONDecodeError):
            data = json.loads(self._state_file.read_text())
            self.loop_id = data.get("loop_id")
            self.session_id = data.get("session_id", "")
            self._model = data.get("model", "")

    def _save_state(self):
        data = {"loop_id": self.loop_id, "session_id": self.session_id}
        if self._model:
            data["model"] = self._model
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(data))

    def _clear_state(self):
        self.loop_id = None
        # Preserve session_id for resume on next spawn
        self._save_state()

    def _load_message_log(self):
        with contextlib.suppress(FileNotFoundError, json.JSONDecodeError):
            self._message_log = json.loads(self._msg_log_file.read_text())

    def _save_message_log(self):
        self._msg_log_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._msg_log_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._message_log))
        tmp.rename(self._msg_log_file)


# ---------------------------------------------------------------------------
# Event loop dispatch
# ---------------------------------------------------------------------------

_loop: asyncio.AbstractEventLoop | None = None
_actors: dict[str, ChatActor] = {}


def _get_or_create_actor(conversation_id: str, platform: Platform) -> ChatActor:
    actor = _actors.get(conversation_id)
    if actor and actor._stopped:
        del _actors[conversation_id]
        actor = None
    if actor is None:
        actor = ChatActor(conversation_id, platform)
        _actors[conversation_id] = actor
        _loop.create_task(actor.start())
    return actor


async def _dispatch(event: IncomingEvent):
    actor = _get_or_create_actor(event.conversation_id, event.platform)
    # /reset and /cancel must interrupt a stuck _query() — terminate the loop
    # before enqueueing so the blocked _run() unblocks.
    if event.kind == "command":
        parsed = _parse_command(event.text)
        if parsed and parsed[0] in ("/reset", "/cancel") and actor.loop_id:
            await asyncio.to_thread(terminate, actor.loop_id)
    try:
        actor.queue.put_nowait(event)
    except asyncio.QueueFull:
        event.platform.send_text(
            event.conversation_id, "Too many pending messages. Please wait."
        )


def _post_to_loop(event: IncomingEvent):
    if _loop is None:
        print(
            f"Event loop not ready, dropping {event.kind} from {event.conversation_id}",
            flush=True,
        )
        return
    fut = asyncio.run_coroutine_threadsafe(_dispatch(event), _loop)
    fut.add_done_callback(
        lambda f: (
            print(f"Dispatch error: {f.exception()}", flush=True)
            if f.exception()
            else None
        )
    )


# ---------------------------------------------------------------------------
# WhatsApp webhook → IncomingEvent
# ---------------------------------------------------------------------------

_wa_platform: WhatsAppPlatform | None = None


def _classify_wa_event(wa_msg: WAMessage) -> IncomingEvent:
    conversation_id = f"whatsapp:{wa_msg.sender}"
    text = wa_msg.text or wa_msg.caption or ""
    kind = "command" if _parse_command(text) is not None else "text"
    return IncomingEvent(
        conversation_id,
        kind=kind,
        text=text,
        platform=_wa_platform,
        message_id=wa_msg.message_id,
        reply_to_id=wa_msg.reply_to_id,
        media_type=wa_msg.media_type,
        media_id=wa_msg.media_id,
        media_mime=wa_msg.mime_type,
    )


def verify_signature(payload: bytes, signature_header: str) -> bool:
    if not APP_SECRET or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header[7:])


_WA_MEDIA_MSG_TYPES = {"image", "video", "audio", "document", "sticker"}


def extract_messages(data: dict) -> list[WAMessage]:
    """Extract WAMessage objects from webhook payload."""
    messages = []
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                sender = msg.get("from")
                if not sender:
                    continue
                msg_id = msg.get("id")
                reply_to = msg.get("context", {}).get("id")
                msg_type = msg.get("type")

                if msg_type == "text":
                    messages.append(
                        WAMessage(
                            sender=sender,
                            text=msg.get("text", {}).get("body", ""),
                            message_id=msg_id,
                            reply_to_id=reply_to,
                        )
                    )
                elif msg_type in _WA_MEDIA_MSG_TYPES:
                    media_data = msg.get(msg_type, {})
                    messages.append(
                        WAMessage(
                            sender=sender,
                            media_type=msg_type,
                            media_id=media_data.get("id"),
                            caption=media_data.get("caption") or msg.get("caption"),
                            mime_type=media_data.get("mime_type"),
                            message_id=msg_id,
                            reply_to_id=reply_to,
                        )
                    )
                else:
                    messages.append(
                        WAMessage(
                            sender=sender,
                            text=f"[Unsupported WhatsApp message type: {msg_type}]",
                            message_id=msg_id,
                            reply_to_id=reply_to,
                        )
                    )
    return messages


# ---------------------------------------------------------------------------
# Telegram long-polling → IncomingEvent
# ---------------------------------------------------------------------------

_tg_platform: TelegramPlatform | None = None
_tg_offset_file = MESSENGER_DIR / "tg_offset.txt"


def _load_tg_offset() -> int:
    try:
        return int(_tg_offset_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _save_tg_offset(offset: int):
    _tg_offset_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tg_offset_file.with_suffix(".tmp")
    tmp.write_text(str(offset))
    tmp.rename(_tg_offset_file)


def _tg_conversation_id(chat_id: int, thread_id: int | None) -> str:
    if thread_id:
        return f"telegram:{chat_id}:{thread_id}"
    return f"telegram:{chat_id}"


def _telegram_poll():
    """Long-polling loop for Telegram updates. Runs on a daemon thread."""
    offset = _load_tg_offset()
    backoff = 1

    while True:
        try:
            payload = json.dumps(
                {
                    "offset": offset + 1,
                    "timeout": 30,
                    "allowed_updates": ["message"],
                }
            ).encode()
            req = Request(
                f"{TELEGRAM_API}/getUpdates",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read())

            backoff = 1

            for update in data.get("result", []):
                update_id = update["update_id"]
                if update_id > offset:
                    offset = update_id
                    _save_tg_offset(offset)

                if "message" in update:
                    _handle_tg_message(update["message"])

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Telegram poll error: {e}", flush=True)
            time.sleep(min(backoff, 30))
            backoff = min(backoff * 2, 30)


_TG_MEDIA_KEYS = {
    "photo": "image",
    "document": "document",
    "audio": "audio",
    "video": "video",
    "voice": "audio",
    "sticker": "sticker",
    "animation": "image",
}


def _handle_tg_message(msg: dict):
    chat_id = msg["chat"]["id"]
    if (
        TELEGRAM_ALLOWED_CHAT_IDS is not None
        and chat_id not in TELEGRAM_ALLOWED_CHAT_IDS
    ):
        print(f"[TG blocked] chat_id={chat_id}", flush=True)
        return

    text = msg.get("text") or msg.get("caption") or ""
    thread_id = msg.get("message_thread_id")
    conversation_id = _tg_conversation_id(chat_id, thread_id)

    # Extract message_id and reply_to_id
    message_id = str(msg.get("message_id", "")) or None
    reply_to_msg = msg.get("reply_to_message")
    reply_to_id = (
        str(reply_to_msg["message_id"])
        if reply_to_msg and "message_id" in reply_to_msg
        else None
    )

    # Detect media
    media_type = None
    media_id = None
    for key, mtype in _TG_MEDIA_KEYS.items():
        if key in msg:
            media_type = mtype
            media_obj = msg[key]
            if key == "photo":
                media_id = media_obj[-1]["file_id"]  # Largest size
            elif isinstance(media_obj, dict):
                media_id = media_obj.get("file_id")
            break

    if not text and not media_id:
        return

    kind = "command" if _parse_command(text) is not None else "text"

    event = IncomingEvent(
        conversation_id,
        kind=kind,
        text=text,
        platform=_tg_platform,
        message_id=message_id,
        reply_to_id=reply_to_id,
        media_type=media_type,
        media_id=media_id,
    )

    print(f"[TG {event.kind}] {chat_id}: {text[:100]}", flush=True)
    _post_to_loop(event)


# ---------------------------------------------------------------------------
# HTTP handler (WhatsApp webhooks)
# ---------------------------------------------------------------------------


class WebhookHandler(BaseHTTPRequestHandler):
    PRIVACY_HTML = b"""<!DOCTYPE html>
<html><head><title>Privacy Policy - handley-lab</title></head>
<body><h1>Privacy Policy</h1>
<p>This WhatsApp integration is a personal project by Handley Lab.
Conversation data and media files are stored locally on the server
for session continuity. Data is not shared with third parties.</p>
<p>Contact: handleylab@gmail.com</p>
</body></html>"""

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/privacy":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(self.PRIVACY_HTML)
            return
        if parsed.path != "/webhook":
            self.send_error(404)
            return

        params = parse_qs(parsed.query)
        mode = params.get("hub.mode", [None])[0]
        token = params.get("hub.verify_token", [None])[0]
        challenge = params.get("hub.challenge", [None])[0]

        if mode == "subscribe" and token == VERIFY_TOKEN:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(challenge.encode() if challenge else b"")
            print("Webhook verified", flush=True)
        else:
            self.send_error(403)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/webhook":
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(content_length)

        signature = self.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(payload, signature):
            print("Invalid signature", flush=True)
            self.send_error(403)
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return

        for wa_msg in extract_messages(data):
            event = _classify_wa_event(wa_msg)
            kind_label = wa_msg.media_type or event.kind
            print(f"[WA {kind_label}] {wa_msg.sender}: {event.text[:100]}", flush=True)
            _post_to_loop(event)

    def log_message(self, format, *args):
        print(f"{self.client_address[0]} - {format % args}", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    global _loop, _wa_platform, _tg_platform
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

    MESSENGER_DIR.mkdir(parents=True, exist_ok=True)
    _migrate_old_dirs()

    _wa_platform = WhatsAppPlatform()

    _loop = asyncio.new_event_loop()

    def _run_loop():
        asyncio.set_event_loop(_loop)
        _loop.run_forever()

    threading.Thread(target=_run_loop, daemon=True).start()

    if TELEGRAM_BOT_TOKEN:
        _tg_platform = TelegramPlatform()
        threading.Thread(target=_telegram_poll, daemon=True).start()
        print("Telegram polling started", flush=True)

    server = ThreadingHTTPServer(("127.0.0.1", port), WebhookHandler)
    print(f"Listening on 127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down", flush=True)
        server.server_close()


if __name__ == "__main__":
    main()
