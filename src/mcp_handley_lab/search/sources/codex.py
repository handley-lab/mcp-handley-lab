"""Codex CLI transcript source adapter.

Discovers JSONL session files under ~/.codex/sessions/.
"""

import json
from pathlib import Path

from mcp_handley_lab.search.models import RawEntry, SyncItem


def _get_codex_dir() -> Path:
    return Path.home() / ".codex"


def discover_items() -> list[SyncItem]:
    """Find all Codex transcript JSONL files."""
    sessions_dir = _get_codex_dir() / "sessions"
    if not sessions_dir.exists():
        return []
    items = []
    for f in sessions_dir.glob("**/*.jsonl"):
        stat = f.stat()
        items.append(
            SyncItem(
                session_key=f.stem,  # Short: just "session1"
                display_name=f.stem,
                project=None,  # Extracted during load_entries from session_meta
                fingerprint=f"{stat.st_mtime}:{stat.st_size}",
                file_path=str(f),
                mtime=stat.st_mtime,
                size=stat.st_size,
            )
        )
    return items


def load_entries(item: SyncItem) -> list[RawEntry]:
    """Load and parse entries from a Codex session file."""
    file_path = Path(item.file_path)
    entries = []
    project_path = None
    idx = 0

    with open(file_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                # Extract project from session_meta
                if entry.get("type") == "session_meta":
                    project_path = entry.get("payload", {}).get("cwd")
                    # Update item.project for session creation
                    item.project = project_path

                entry_type = _classify_type(entry)
                content_text = _extract_text(entry)

                if not content_text.strip():
                    continue

                entries.append(
                    RawEntry(
                        idx=idx,
                        role=entry_type,
                        timestamp=entry.get("timestamp"),
                        content=content_text,
                        model=entry.get("payload", {}).get("model"),
                        raw_json=line.strip(),
                    )
                )
                idx += 1
            except json.JSONDecodeError:
                continue
    return entries


def _classify_type(entry: dict) -> str:
    """Classify entry into user/assistant/system/tool type."""
    etype = entry.get("type")
    payload = entry.get("payload", {})
    ptype = payload.get("type")

    if etype == "session_meta":
        return "system"
    elif etype == "event_msg":
        msg_type = payload.get("type")
        if msg_type == "user_message":
            return "user"
        elif msg_type == "agent_reasoning":
            return "assistant"
        return "system"
    elif etype == "response_item":
        role = payload.get("role")
        if role == "user":
            return "user"
        if ptype in ("message", "reasoning"):
            return "assistant"
        if ptype in ("function_call", "function_call_output"):
            return "tool"
        return "assistant"
    return "system"


def _extract_text(entry: dict) -> str:
    """Extract searchable text from Codex entry."""
    texts = []
    payload = entry.get("payload", {})
    ptype = payload.get("type")
    etype = entry.get("type")

    if etype == "event_msg":
        msg_type = payload.get("type")
        if msg_type == "agent_reasoning":
            texts.append(payload.get("text", ""))
        elif msg_type == "user_message":
            texts.append(payload.get("message", ""))
    elif etype == "response_item":
        if ptype == "message":
            for block in payload.get("content", []):
                if isinstance(block, dict) and block.get("type") == "input_text":
                    texts.append(block.get("text", ""))
        elif ptype == "reasoning":
            for summary in payload.get("summary", []):
                if isinstance(summary, dict) and summary.get("type") == "summary_text":
                    texts.append(summary.get("text", ""))
        elif ptype == "function_call":
            texts.append(f"tool:{payload.get('name', '')}")
            args = payload.get("arguments", "")
            if isinstance(args, str):
                texts.append(args)
        elif ptype == "function_call_output":
            texts.append(payload.get("output", ""))
    elif etype == "session_meta":
        cwd = payload.get("cwd", "")
        if cwd:
            texts.append(f"cwd:{cwd}")

    return "\n".join(filter(None, texts))
