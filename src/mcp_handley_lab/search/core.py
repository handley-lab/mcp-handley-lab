"""Core context search and slice functionality (RLM-style).

Uses the unified database for all operations.
Composite session handles: "{source}:{session_key}" for opaque API IDs.
"""

import re

from mcp_handley_lab.search import db
from mcp_handley_lab.search.models import (
    Entry,
    SearchHit,
    SearchResults,
    SessionInfo,
    SessionList,
    SliceEntry,
    SliceResult,
)
from mcp_handley_lab.search.sources import SOURCES
from mcp_handley_lab.search.sync import sync_all_sources, sync_single_source


def _make_session_id(source: str, session_key: str) -> str:
    """Create composite session handle."""
    return f"{source}:{session_key}"


def _parse_session_id(session_id: str) -> tuple[str, str]:
    """Parse composite session handle into (source, session_key).

    Uses first colon as separator (source names don't contain colons).
    """
    idx = session_id.find(":")
    if idx < 0:
        raise ValueError(
            f"Invalid session_id format: {session_id!r}. "
            "Expected '{{source}}:{{session_key}}'"
        )
    return session_id[:idx], session_id[idx + 1 :]


def _resolve_handle(default_source: str, session_id: str) -> tuple[str, str]:
    """Resolve session_id to (source, session_key).

    If session_id is a composite handle "{source}:{session_key}", uses
    the embedded source. Otherwise uses default_source with raw value.
    """
    if ":" in session_id:
        return _parse_session_id(session_id)
    return default_source, session_id


def context(
    action: str,
    source: str = "claude",
    query: str = "",
    project: str = "",
    type: str = "",
    limit: int = 20,
    since: str = "",
    session_id: str = "",
    start: int = 0,
    end: int | None = None,
    max_chars: int = 0,
    full: bool = False,
    verbose: bool = False,
    # Deprecated alias for session_id
    file_path: str = "",
) -> dict:
    """Unified context function for search and slice.

    Args:
        action: One of "search", "slice", "sessions", "sync", "stats"
        source: Transcript source - "claude", "codex", "gemini", "mcp", or "all"
        query: FTS5 search query (for search action)
        project: Filter by project path (partial match)
        type: Filter by entry type (user, assistant, system, prompt, tool)
        limit: Maximum number of results
        since: Filter entries after this ISO timestamp
        session_id: Session identifier for slice/search scoping.
            Accepts composite handle "{source}:{session_key}" from search results.
        start: Start index for slice (0-indexed)
        end: End index for slice (exclusive, None=end)
        max_chars: For slice: max chars per entry (0=no limit)
        full: For sync action, re-sync all files
        verbose: For slice action, return full Entry objects instead of compact strings
        file_path: Deprecated alias for session_id

    source='all' behavior:
    - search: merges hits from all sources ranked by BM25 score
    - sync/stats: returns dict[source, result]
    - slice/sessions: raises ValueError (need specific source)

    Returns:
        dict in all cases.
    """
    # Support deprecated file_path alias
    sid = session_id or file_path

    if action == "sync":
        return _handle_sync(source, full)
    if action == "stats":
        return _handle_stats(source)

    # All non-sync/stats actions need the DB
    conn = db.ensure_db()

    if source == "all":
        if action == "search":
            if sid:
                raise ValueError(
                    "session_id filter not supported with source='all' "
                    "(composite session_id already encodes source)"
                )
            return _search(conn, None, query, limit, project, type, since, "")
        raise ValueError(f"source='all' not supported for action='{action}'")

    if source not in SOURCES:
        raise ValueError(f"Unknown source: {source}")

    if action == "search":
        # Resolve source and session_key from composite handle
        resolved_source, resolved_key = (
            _resolve_handle(source, sid) if sid else (source, "")
        )
        return _search(
            conn,
            resolved_source,
            query,
            limit,
            project,
            type,
            since,
            resolved_key,
        )
    elif action == "slice":
        return _slice(conn, source, sid, start, end, max_chars, verbose)
    elif action == "sessions":
        return _get_sessions(conn, source, limit)
    else:
        raise ValueError(f"Unknown action: {action}")


def _handle_sync(source: str, full: bool) -> dict:
    """Handle sync action."""
    if source == "all":
        return sync_all_sources(SOURCES, full=full)
    if source not in SOURCES:
        raise ValueError(f"Unknown source: {source}")
    return sync_single_source(source, SOURCES[source], full=full)


def _handle_stats(source: str) -> dict:
    """Handle stats action."""
    conn = db.ensure_db()
    if source == "all":
        return {name: db.get_stats(conn, name) for name in SOURCES}
    if source not in SOURCES:
        raise ValueError(f"Unknown source: {source}")
    return db.get_stats(conn, source)


def _search(
    conn,
    source_filter: str | None,
    query: str,
    limit: int,
    project: str,
    role: str,
    since: str,
    session_key: str,
) -> dict:
    """Search with structured output.

    Returns dict with ranked hits including BM25 scores.
    session_entry_count is included in DB results to avoid N+1 queries.
    """
    since_unix = db.parse_timestamp(since) if since else None

    if query:
        raw_hits = db.fts_search(
            conn,
            query,
            source=source_filter,
            limit=limit,
            project=project or None,
            role=role or None,
            since_unix=since_unix,
            session_key=session_key or None,
        )
    else:
        raw_hits = db.search_recent(
            conn,
            source=source_filter,
            limit=limit,
            project=project or None,
            role=role or None,
            since_unix=since_unix,
            session_key=session_key or None,
        )

    # Build structured hits — session_entry_count comes from the JOIN
    hits: list[SearchHit] = []
    for row in raw_hits:
        src = row["source"]
        sk = row["session_key"]

        hits.append(
            SearchHit(
                session_id=_make_session_id(src, sk),
                entry_index=row.get("idx", 0) or 0,
                session_length=row.get("session_entry_count", 0) or 0,
                role=row.get("role", "unknown"),
                timestamp=row.get("timestamp_text"),
                snippet=_make_snippet(row.get("content_text") or "", query),
                source=src,
                score=row.get("score"),
            )
        )

    result = SearchResults(hits=hits, total=len(hits), query=query)
    return result.model_dump()


def _slice(
    conn,
    source: str,
    session_id: str,
    start: int,
    end: int | None,
    max_chars: int,
    verbose: bool,
) -> dict:
    """Get entries by position with structured output.

    session_id accepts composite handle or raw session_key.
    """
    if not session_id:
        raise ValueError("session_id is required for slice action")

    # Resolve composite handle
    resolved_source, session_key = _resolve_handle(source, session_id)

    rows = db.slice_entries(conn, resolved_source, session_key, start, end)
    session_len = db.get_session_length(conn, resolved_source, session_key)
    composite_id = _make_session_id(resolved_source, session_key)

    if verbose:
        entries = [Entry.from_db_row(row, resolved_source) for row in rows]
        return {
            "session_id": composite_id,
            "source": resolved_source,
            "project": rows[0].get("project") if rows else None,
            "entry_count": session_len,
            "entries": [e.model_dump() for e in entries],
        }

    slice_entries = []
    for row in rows:
        content = row.get("content_text", "") or ""
        if max_chars > 0 and len(content) > max_chars:
            truncated = content[:max_chars]
            last_space = truncated.rfind(" ")
            if last_space > max_chars * 0.8:
                truncated = truncated[:last_space]
            content = truncated + "..."
        slice_entries.append(
            SliceEntry(
                entry_index=row.get("idx", 0) or 0,
                role=row.get("role", "unknown"),
                content=content,
                timestamp=row.get("timestamp_text"),
                model=row.get("model"),
                cost_usd=row.get("cost_usd"),
            )
        )

    result = SliceResult(
        session_id=composite_id,
        source=resolved_source,
        project=rows[0].get("project") if rows else None,
        entry_count=session_len,
        entries=slice_entries,
    )
    return result.model_dump()


def _get_sessions(conn, source: str, limit: int = 20) -> dict:
    """List sessions for a source, ordered by most recent activity."""
    rows = db.get_sessions(conn, source, limit)
    result = SessionList(
        source=source,
        sessions=[
            SessionInfo(
                session_id=_make_session_id(row["source"], row["session_key"]),
                display_name=row["display_name"],
                source=row["source"],
                project=row.get("project"),
                start_time=_unix_to_iso(row.get("first_ts")),
                end_time=_unix_to_iso(row.get("last_ts")),
                entry_count=row["entry_count"],
            )
            for row in rows
        ],
    )
    return result.model_dump()


def _unix_to_iso(ts: float | None) -> str | None:
    """Convert unix timestamp to ISO string for API output."""
    if ts is None:
        return None
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _make_snippet(text: str, query: str, max_len: int = 200) -> str:
    """Create a snippet centered on the first query term match."""
    if len(text) <= max_len:
        return text

    terms = re.sub(r"\b(AND|OR|NOT|NEAR)\b", " ", query, flags=re.IGNORECASE)
    terms = re.sub(r"[\"()*,]", " ", terms)
    words = [w.strip() for w in terms.split() if w.strip()]

    match_pos = -1
    text_lower = text.lower()
    for word in words:
        pos = text_lower.find(word.lower())
        if pos >= 0:
            match_pos = pos
            break

    if match_pos < 0:
        truncated = text[:max_len]
        last_space = truncated.rfind(" ")
        if last_space > max_len * 0.8:
            truncated = truncated[:last_space]
        return truncated + "..."

    half = max_len // 2
    start = max(0, match_pos - half)
    end = min(len(text), start + max_len)
    if end - start < max_len:
        start = max(0, end - max_len)

    snippet = text[start:end]

    if start > 0:
        first_space = snippet.find(" ")
        if 0 < first_space < len(snippet) * 0.2:
            snippet = snippet[first_space + 1 :]
        snippet = "..." + snippet
    if end < len(text):
        last_space = snippet.rfind(" ")
        if last_space > len(snippet) * 0.8:
            snippet = snippet[:last_space]
        snippet = snippet + "..."

    return snippet
