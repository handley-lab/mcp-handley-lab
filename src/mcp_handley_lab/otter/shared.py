"""Core Otter.ai functions using undocumented API.

All functions are usable without MCP server.
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_serializer

from mcp_handley_lab.common.config import settings

API_BASE = "https://otter.ai/forward/api/v1"


# --- Response Models ---


class MeetingSummary(BaseModel):
    """Summary of an Otter.ai meeting."""

    otid: str = Field(..., description="Unique meeting identifier.")
    title: str = Field(default="", description="Meeting title.")
    created_at: int = Field(
        default=0, description="Unix timestamp (seconds) when created."
    )
    live_status: str = Field(
        default="", description="Meeting status (e.g., 'live', 'ended')."
    )


class TranscriptSegment(BaseModel):
    """A single transcript segment."""

    speaker_name: str = Field(default="Unknown", description="Speaker name.")
    start_offset_ms: int = Field(
        default=0, description="Offset from meeting start in ms."
    )
    text: str = Field(default="", description="Transcript text.")


class TranscriptResult(BaseModel):
    """Full transcript for a meeting."""

    title: str = Field(default="", description="Meeting title.")
    otid: str = Field(..., description="Unique meeting identifier.")
    live_status: str = Field(default="", description="Meeting status.")
    created_at: int = Field(default=0, description="Unix timestamp (seconds).")
    url: str = Field(default="", description="Otter.ai URL for this meeting.")
    speakers: list[str] = Field(default_factory=list, description="Speaker names.")
    segments: list[TranscriptSegment] = Field(
        default_factory=list, description="Transcript segments."
    )
    formatted_text: str = Field(default="", description="Formatted transcript text.")


class RefreshResult(BaseModel):
    """Result of a session refresh."""

    refreshed_at: str = Field(..., description="ISO timestamp of refresh.")
    cookie_count: int = Field(..., description="Number of cookies saved.")
    session_path: str = Field(..., description="Path to session file.")


class OtterResult(BaseModel):
    """Envelope result — only relevant fields are populated."""

    model_config = ConfigDict(extra="forbid")

    meetings: list[MeetingSummary] | None = None
    transcript: TranscriptResult | None = None
    refresh: RefreshResult | None = None

    @model_serializer
    def serialize(self) -> dict:
        """Exclude None fields from serialization."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


# --- Session Management ---

_session_cache: httpx.Client | None = None


def _get_session(force_reload: bool = False) -> httpx.Client:
    """Load session from disk lazily, cached for process lifetime."""
    global _session_cache
    if _session_cache is not None and not force_reload:
        return _session_cache

    session_path = settings.otter_session_path
    data = json.loads(session_path.read_text())
    cookies = httpx.Cookies()
    for c in data.get("cookies", []):
        domain = c.get("domain") or ".otter.ai"
        cookies.set(c["name"], c["value"], domain=domain, path=c.get("path", "/"))

    client = httpx.Client(
        cookies=cookies, follow_redirects=True, timeout=settings.otter_timeout
    )
    _session_cache = client
    return _session_cache


def _clear_session_cache():
    """Clear cached session, closing the client."""
    global _session_cache
    if _session_cache is not None:
        _session_cache.close()
        _session_cache = None


# --- API helpers ---


_SESSION_EXPIRED = (
    "Otter session expired. Call otter(action='refresh') or run otter-refresh-session."
)


def _parse_json(resp: httpx.Response) -> dict:
    """Parse JSON from response, raising RuntimeError on HTML login redirects."""
    content_type = resp.headers.get("content-type", "").lower()
    if "text/html" in content_type:
        raise RuntimeError("HTML login redirect")
    return resp.json()


def _api_get(path: str, params: dict | None = None) -> dict:
    """GET an Otter API endpoint with session cookies. Retries once on auth failure."""
    client = _get_session()
    resp = client.get(f"{API_BASE}/{path}", params=params)

    if resp.status_code in (400, 401, 403):
        _clear_session_cache()
        client = _get_session(force_reload=True)
        resp = client.get(f"{API_BASE}/{path}", params=params)
        if resp.status_code in (400, 401, 403):
            raise RuntimeError(_SESSION_EXPIRED)

    resp.raise_for_status()

    try:
        return _parse_json(resp)
    except (RuntimeError, json.JSONDecodeError):
        _clear_session_cache()
        client = _get_session(force_reload=True)
        resp = client.get(f"{API_BASE}/{path}", params=params)
        resp.raise_for_status()
        return _parse_json(resp)


# --- Parsing helpers ---


def _parse_meeting(raw: dict) -> MeetingSummary | None:
    """Parse a raw meeting dict into MeetingSummary. Returns None on failure."""
    try:
        return MeetingSummary(
            otid=raw["otid"],
            title=raw.get("title", ""),
            created_at=raw.get("created_at", 0),
            live_status=raw.get("live_status", ""),
        )
    except (KeyError, TypeError):
        return None


def _get_speakers(otid: str) -> dict[int, str]:
    """Get speaker ID to name mapping for a meeting."""
    data = _api_get("speakers", {"otid": otid})
    mapping = {}
    for speaker in data.get("speakers", []):
        if "id" in speaker:
            mapping[speaker["id"]] = speaker.get("speaker_name", "Unknown")
    return mapping


def _format_transcript(
    transcripts: list, speakers: dict[int, str]
) -> tuple[str, list[TranscriptSegment]]:
    """Format transcript segments into readable text and structured segments."""
    indexed = list(enumerate(transcripts))
    indexed.sort(key=lambda x: (x[1].get("start_offset", 0), x[0]))

    lines = []
    segments = []
    for _, t in indexed:
        text = t.get("transcript", "")
        if not text.strip():
            continue
        start = t.get("start_offset", 0)
        total_secs = start // 1000
        mins = total_secs // 60
        secs = total_secs % 60
        speaker_id = t.get("speaker_id")
        speaker = (
            speakers.get(speaker_id, f"Speaker {speaker_id}")
            if speaker_id is not None
            else "Unknown"
        )
        lines.append(f"[{mins:02d}:{secs:02d}] **{speaker}**: {text}")
        segments.append(
            TranscriptSegment(
                speaker_name=speaker,
                start_offset_ms=start,
                text=text,
            )
        )

    return "\n\n".join(lines), segments


# --- Public operations ---


def find_live_meetings() -> list[MeetingSummary]:
    """Find all currently live meetings."""
    data = _api_get("speeches", {"page_size": 10})
    results = []
    for raw in data.get("speeches", []):
        if raw.get("live_status") == "live":
            meeting = _parse_meeting(raw)
            if meeting:
                results.append(meeting)
    return results


def get_transcript(otid: str, max_segments: int = 0) -> TranscriptResult:
    """Get full transcript for a meeting."""
    data = _api_get("speech", {"otid": otid})
    speech = data.get("speech", data)

    speakers = _get_speakers(otid)
    transcripts = speech.get("transcripts", [])

    if max_segments > 0:
        # Sort with stable tiebreaker (matching _format_transcript), keep last N
        indexed = list(enumerate(transcripts))
        indexed.sort(key=lambda x: (x[1].get("start_offset", 0), x[0]))
        transcripts = [t for _, t in indexed[-max_segments:]]

    formatted_text, segments = _format_transcript(transcripts, speakers)

    return TranscriptResult(
        title=speech.get("title", ""),
        otid=otid,
        live_status=speech.get("live_status", ""),
        created_at=speech.get("created_at", 0),
        url=f"https://otter.ai/u/{otid}",
        speakers=sorted({seg.speaker_name for seg in segments}),
        segments=segments,
        formatted_text=formatted_text,
    )


def list_recent_meetings(limit: int = 10) -> list[MeetingSummary]:
    """List recent meetings."""
    data = _api_get("speeches", {"page_size": limit})
    results = []
    for raw in data.get("speeches", []):
        meeting = _parse_meeting(raw)
        if meeting:
            results.append(meeting)
    return results


def search_meetings(query: str, limit: int = 10) -> list[MeetingSummary]:
    """Client-side title filter over most recent meetings."""
    data = _api_get("speeches", {"page_size": 10})
    query_lower = query.lower()
    results = []
    for raw in data.get("speeches", []):
        if query_lower in raw.get("title", "").lower():
            meeting = _parse_meeting(raw)
            if meeting:
                results.append(meeting)
                if len(results) >= limit:
                    break
    return results


_REFRESH_SCRIPT = """
import json, sys
from playwright.sync_api import sync_playwright

chrome_profile = sys.argv[1]
output_file = sys.argv[2]

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=chrome_profile, headless=True, channel="chrome",
    )
    try:
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://otter.ai/home", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        all_cookies = browser.cookies("https://otter.ai")
        cookies = [
            {"name": c["name"], "value": c["value"],
             "domain": c.get("domain", "otter.ai"), "path": c.get("path", "/")}
            for c in all_cookies if "otter.ai" in c.get("domain", "")
        ]
    finally:
        browser.close()
with open(output_file, "w") as f:
    json.dump(cookies, f)
"""


_MANAGED_MARKER = ".mcp_otter_managed"

# Directories to exclude when copying Chrome profile (~300MB vs ~4GB)
_PROFILE_SKIP = {
    "Cache",
    "Code Cache",
    "GPUCache",
    "CacheStorage",
    "DawnCache",
    "Service Worker",
    "WebStorage",
    "File System",
    "IndexedDB",
    "SingletonLock",
    "SingletonCookie",
    "SingletonSocket",
}


def _ensure_chrome_profile():
    """Ensure the Otter Chrome profile exists, copying from the system Chrome profile."""
    import shutil

    chrome_profile = settings.otter_chrome_profile_path
    if chrome_profile.exists() and (chrome_profile / "Default").exists():
        return

    source = Path.home() / ".config" / "google-chrome"
    if not (source / "Default").exists():
        raise RuntimeError(
            f"Chrome profile not found at {source}. "
            "Start Chrome at least once, then retry."
        )

    # Remove stale/incomplete copies (only if we created them)
    if chrome_profile.exists():
        if not (chrome_profile / _MANAGED_MARKER).exists():
            raise RuntimeError(
                f"{chrome_profile} exists but is not managed by mcp-otter. "
                "Delete it manually if safe, then retry."
            )
        shutil.rmtree(chrome_profile)

    shutil.copytree(
        str(source),
        str(chrome_profile),
        ignore=shutil.ignore_patterns(*_PROFILE_SKIP),
    )
    (chrome_profile / _MANAGED_MARKER).touch()


def refresh_session() -> RefreshResult:
    """Refresh Otter.ai session using Playwright headless with a Chrome profile copy.

    Runs in a subprocess to avoid asyncio loop conflicts with FastMCP.
    """
    import subprocess

    _ensure_chrome_profile()
    chrome_profile = settings.otter_chrome_profile_path

    session_path = settings.otter_session_path
    session_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_cookies = tempfile.mkstemp(suffix=".json")
    os.close(fd)

    try:
        result = subprocess.run(
            [sys.executable, "-c", _REFRESH_SCRIPT, str(chrome_profile), tmp_cookies],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Refresh failed: {result.stderr.strip()}")

        with open(tmp_cookies) as f:
            cookies = json.load(f)
    finally:
        if os.path.exists(tmp_cookies):
            os.unlink(tmp_cookies)

    if not any(c["name"] == "sessionid" for c in cookies):
        raise RuntimeError("Not logged in to Otter.ai. Log in via Chrome, then retry.")

    session_data = {
        "cookies": cookies,
        "refreshed_at": datetime.now().isoformat(),
    }

    session_path = settings.otter_session_path
    session_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(session_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(session_data, f, indent=2)
        os.chmod(tmp_path, 0o600)
        os.rename(tmp_path, str(session_path))
    except Exception:
        os.unlink(tmp_path)
        raise

    _clear_session_cache()

    return RefreshResult(
        refreshed_at=session_data["refreshed_at"],
        cookie_count=len(cookies),
        session_path=str(session_path),
    )
