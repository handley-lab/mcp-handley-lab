"""Core Otter.ai functions using undocumented API.

All functions are usable without MCP server.
"""

import json
import os
import tempfile
from datetime import datetime

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

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", description="Meeting title.")
    otid: str = Field(..., description="Unique meeting identifier.")
    live_status: str = Field(default="", description="Meeting status.")
    created_at: int = Field(default=0, description="Unix timestamp (seconds).")
    url: str = Field(default="", description="Otter.ai URL for this meeting.")
    speakers: list[str] = Field(default_factory=list, description="Speaker names.")
    segments: list[TranscriptSegment] = Field(
        default_factory=list, description="Transcript segments."
    )
    formatted_text: str | None = Field(
        default=None, description="Formatted transcript text."
    )

    @model_serializer
    def serialize(self) -> dict:
        """Exclude None fields from serialization."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


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


_NOT_LOGGED_IN = (
    "No Otter.ai session found in any browser (tried Chrome, Chromium, Brave, Firefox). "
    "Please log in at https://otter.ai in your browser, then retry."
)


def _parse_json(resp: httpx.Response) -> dict:
    """Parse JSON from response, raising RuntimeError on HTML login redirects."""
    content_type = resp.headers.get("content-type", "").lower()
    if "text/html" in content_type:
        raise RuntimeError("HTML login redirect")
    return resp.json()


def _auto_refresh() -> bool:
    """Try to refresh session from browser cookies. Returns True if successful."""
    try:
        refresh_session()
        return True
    except RuntimeError:
        return False


def _api_get(path: str, params: dict | None = None) -> dict:
    """GET an Otter API endpoint with session cookies.

    On auth failure: reloads session file, then auto-refreshes from browser cookies.
    """
    client = _get_session()
    resp = client.get(f"{API_BASE}/{path}", params=params)

    if resp.status_code in (400, 401, 403):
        # Try reloading from disk first (another process may have refreshed)
        _clear_session_cache()
        client = _get_session(force_reload=True)
        resp = client.get(f"{API_BASE}/{path}", params=params)

        if resp.status_code in (400, 401, 403):
            # Auto-refresh from browser cookies
            if not _auto_refresh():
                raise RuntimeError(_NOT_LOGGED_IN)
            client = _get_session(force_reload=True)
            resp = client.get(f"{API_BASE}/{path}", params=params)
            if resp.status_code in (400, 401, 403):
                raise RuntimeError(_NOT_LOGGED_IN)

    resp.raise_for_status()

    try:
        return _parse_json(resp)
    except (RuntimeError, json.JSONDecodeError):
        _clear_session_cache()
        if not _auto_refresh():
            raise RuntimeError(_NOT_LOGGED_IN) from None
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


def _build_segments(
    transcripts: list, speakers: dict[int, str]
) -> list[TranscriptSegment]:
    """Build structured segments from raw transcript data (assumes pre-sorted)."""
    segments = []
    for t in transcripts:
        text = t.get("transcript", "")
        if not text.strip():
            continue
        speaker_id = t.get("speaker_id")
        speaker = (
            speakers.get(speaker_id, f"Speaker {speaker_id}")
            if speaker_id is not None
            else "Unknown"
        )
        segments.append(
            TranscriptSegment(
                speaker_name=speaker,
                start_offset_ms=t.get("start_offset", 0),
                text=text,
            )
        )
    return segments


def _format_segments(segments: list[TranscriptSegment]) -> str:
    """Render segments as human-readable markdown text."""
    lines = []
    for seg in segments:
        total_secs = seg.start_offset_ms // 1000
        mins = total_secs // 60
        secs = total_secs % 60
        lines.append(f"[{mins:02d}:{secs:02d}] **{seg.speaker_name}**: {seg.text}")
    return "\n\n".join(lines)


def _format_transcript(
    transcripts: list, speakers: dict[int, str]
) -> tuple[str, list[TranscriptSegment]]:
    """Format transcript segments into readable text and structured segments."""
    indexed = list(enumerate(transcripts))
    indexed.sort(key=lambda x: (x[1].get("start_offset", 0), x[0]))
    transcripts = [t for _, t in indexed]
    segments = _build_segments(transcripts, speakers)
    return _format_segments(segments), segments


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


def get_transcript(
    otid: str,
    max_segments: int = 0,
    since_offset_ms: int = 0,
    include_formatted_text: bool = True,
) -> TranscriptResult:
    """Get full transcript for a meeting."""
    data = _api_get("speech", {"otid": otid})
    speech = data.get("speech", data)

    speakers = _get_speakers(otid)
    transcripts = speech.get("transcripts", [])

    # Sort with stable tiebreaker for consistent filtering and truncation
    indexed = list(enumerate(transcripts))
    indexed.sort(key=lambda x: (x[1].get("start_offset", 0), x[0]))
    transcripts = [t for _, t in indexed]

    if since_offset_ms > 0:
        transcripts = [
            t for t in transcripts if t.get("start_offset", 0) > since_offset_ms
        ]

    if max_segments > 0:
        transcripts = transcripts[-max_segments:]

    segments = _build_segments(transcripts, speakers)

    return TranscriptResult(
        title=speech.get("title", ""),
        otid=otid,
        live_status=speech.get("live_status", ""),
        created_at=speech.get("created_at", 0),
        url=f"https://otter.ai/u/{otid}",
        speakers=sorted({seg.speaker_name for seg in segments}),
        segments=segments,
        formatted_text=_format_segments(segments) if include_formatted_text else None,
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


def _extract_browser_cookies() -> dict:
    """Try extracting otter.ai cookies from installed browsers.

    Tries Chrome, Chromium, Brave, then Firefox. Returns the first cookie jar
    that contains a sessionid, or raises RuntimeError.
    """
    from pycookiecheat import BrowserType, chrome_cookies, firefox_cookies

    for browser in (BrowserType.CHROME, BrowserType.CHROMIUM, BrowserType.BRAVE):
        try:
            cookies = chrome_cookies("https://otter.ai", browser=browser)
            if "sessionid" in cookies:
                return cookies
        except Exception:
            continue

    try:
        cookies = firefox_cookies("https://otter.ai")
        if "sessionid" in cookies:
            return cookies
    except Exception:
        pass

    import webbrowser

    webbrowser.open("https://otter.ai/signin")
    raise RuntimeError(_NOT_LOGGED_IN)


def refresh_session() -> RefreshResult:
    """Refresh Otter.ai session by extracting cookies from the user's browser.

    Tries Chrome, Chromium, Brave, and Firefox via pycookiecheat.
    If no browser has a valid session, opens otter.ai sign-in page and raises an error.
    """
    raw_cookies = _extract_browser_cookies()

    cookies = [
        {"name": name, "value": value, "domain": ".otter.ai", "path": "/"}
        for name, value in raw_cookies.items()
    ]

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
