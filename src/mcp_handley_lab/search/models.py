"""Data models for transcript search.

Adapter protocol types (SyncItem, RawEntry) and Pydantic models for API responses.
"""

import json
from dataclasses import dataclass

from pydantic import BaseModel

# --- Adapter protocol types ---


@dataclass
class SyncItem:
    """A syncable unit discovered by a source adapter."""

    session_key: str  # Unique key for sessions + sync_state (full path or repo:branch)
    display_name: str  # Human-readable name
    project: str | None  # Project identifier
    fingerprint: str  # Change detection: "{mtime}:{size}" or git SHA
    # Source-specific fields for sync_state:
    mtime: float | None = None  # Filesystem sources
    size: int | None = None  # Filesystem sources
    tip_sha: str | None = None  # Git sources


@dataclass
class RawEntry:
    """A parsed transcript entry from a source."""

    idx: int
    role: str  # user, assistant, system, tool, prompt
    timestamp: str | None  # Original ISO string (normalized to unix at ingest)
    content: str
    model: str | None = None
    cost_usd: float | None = None
    raw_json: str | None = None


# --- Pydantic models for API responses ---


class SearchHit(BaseModel):
    """A single search result with structured metadata."""

    session_id: str  # Composite handle: "{source}:{session_key}"
    entry_index: int  # Position in session
    session_length: int
    role: str  # user, assistant, system, tool, prompt
    timestamp: str | None = None
    snippet: str
    source: str
    score: float | None = None  # BM25 score (lower = better)


class SearchResults(BaseModel):
    """Structured search response with ranked hits."""

    hits: list[SearchHit]
    total: int
    query: str


class SliceEntry(BaseModel):
    """A single entry in a slice result."""

    entry_index: int
    role: str
    content: str
    timestamp: str | None = None
    model: str | None = None
    cost_usd: float | None = None


class SliceResult(BaseModel):
    """Slice response with session context."""

    session_id: str  # Composite handle: "{source}:{session_key}"
    source: str
    project: str | None = None
    entry_count: int
    entries: list[SliceEntry]


class Entry(BaseModel):
    """Full transcript entry (verbose mode)."""

    id: int
    source: str
    session_id: str  # Composite handle: "{source}:{session_key}"
    index: int  # Position in session
    type: str
    timestamp: str | None = None
    content: str  # Mapped from content_text
    model: str | None = None
    cost_usd: float | None = None
    raw: dict | None = None  # Parsed from raw_json, optional for performance

    @classmethod
    def from_db_row(cls, row: dict, source: str, parse_raw: bool = False) -> "Entry":
        """Convert DB row to Entry model."""
        idx_val = row.get("idx")
        session_key = row.get("session_key", "")
        return cls(
            id=row["id"],
            source=source,
            session_id=f"{source}:{session_key}",
            index=idx_val if idx_val is not None else 0,
            type=row.get("role", "unknown"),
            timestamp=row.get("timestamp_text"),
            content=row.get("content_text", "") or "",
            model=row.get("model"),
            cost_usd=row.get("cost_usd"),
            raw=(
                json.loads(row["raw_json"])
                if parse_raw and row.get("raw_json")
                else None
            ),
        )


class SessionInfo(BaseModel):
    """Session metadata."""

    session_id: str  # Composite handle: "{source}:{session_key}"
    display_name: str
    source: str
    project: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    entry_count: int


class SessionList(BaseModel):
    """List of sessions."""

    source: str
    sessions: list[SessionInfo]


class SyncStats(BaseModel):
    """Statistics from a sync operation."""

    files: int = 0
    entries: int = 0
    skipped: int = 0
    deleted: int = 0


class Stats(BaseModel):
    """Usage statistics for a source."""

    entries: int
    sessions: int
    projects: int
    total_cost: float = 0.0
    by_type: dict[str, int]
