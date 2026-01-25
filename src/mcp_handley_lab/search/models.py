"""Pydantic models for RLM-style context search and slicing."""

import json

from pydantic import BaseModel


class SearchResults(BaseModel):
    """Compact search response with file lookup table.

    hits are formatted as "file_idx[entry_idx/session_len] type: snippet..."
    Use files[file_idx] to get the full file_path for slicing.
    """

    files: list[str]  # Unique file paths, indexed by position
    hits: list[str]  # Compact: "0[55/64] tool: Exit code..."
    query: str
    total: int


class Entry(BaseModel):
    """Full transcript entry."""

    id: int
    source: str
    file_path: str
    session_id: str
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
        # Handle NULL idx explicitly (can occur if DB migrated but not synced yet)
        idx_val = row.get("idx")
        return cls(
            id=row["id"],
            source=source,
            file_path=row["file_path"],
            session_id=row["session_id"],
            index=idx_val if idx_val is not None else 0,
            type=row["type"],
            timestamp=row.get("timestamp"),
            content=row.get("content_text", ""),
            model=row.get("model"),
            cost_usd=row.get("cost_usd"),
            raw=(
                json.loads(row["raw_json"])
                if parse_raw and row.get("raw_json")
                else None
            ),
        )


class SessionInfo(BaseModel):
    """Session metadata. Identified by file_path (unique)."""

    file_path: str  # Unique session identifier (primary key for slicing)
    session_id: str  # Display name (may not be unique across files)
    source: str
    project: str | None = None  # project_path
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
