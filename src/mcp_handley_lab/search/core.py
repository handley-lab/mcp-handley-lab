"""Core context search and slice functionality (RLM-style)."""

import re

from mcp_handley_lab.search import claude, codex, common, gemini, mcp_memory
from mcp_handley_lab.search.models import (
    Entry,
    SearchResults,
    SessionInfo,
    SessionList,
)

SOURCES = {
    "claude": claude,
    "codex": codex,
    "gemini": gemini,
    "mcp": mcp_memory,
}


def context(
    action: str,
    source: str = "claude",
    query: str = "",
    project: str = "",
    type: str = "",
    limit: int = 20,
    since: str = "",
    file_path: str = "",
    start: int = 0,
    end: int | None = None,
    max_chars: int = 0,
    full: bool = False,
    verbose: bool = False,
) -> SearchResults | list[str] | list[Entry] | SessionList | dict:
    """Unified context function for search and slice.

    Args:
        action: One of "search", "slice", "sessions", "sync", "stats"
        source: Transcript source - "claude", "codex", "gemini", "mcp", or "all"
        query: FTS5 search query (for search action)
        project: Filter by project path (partial match)
        type: Filter by entry type (user, assistant, system, prompt, tool)
        limit: Maximum number of results
        since: Filter entries after this ISO timestamp
        file_path: Session identifier (files[file_idx] from search results).
            For slice: get entries by position. For search: scope to this session.
        start: Start index for slice (0-indexed)
        end: End index for slice (exclusive, None=end)
        max_chars: For slice: max chars per entry (0=no limit)
        full: For sync action, re-sync all files
        verbose: For slice action, return full Entry objects instead of compact strings

    source='all' behavior:
    - search: merges hits from all sources, returns SearchResults
    - sync/stats: returns dict[source, result] (backward compatible)
    - slice/sessions: raises ValueError (need specific source)

    Returns:
        SearchResults for search, list[str] for slice (or list[Entry] if verbose),
        SessionList for sessions, dict for sync/stats operations
    """
    if source == "all":
        if action == "search":
            if file_path:
                raise ValueError(
                    "file_path filter not supported with source='all' "
                    "(file paths are source-specific)"
                )
            return _search_all_merged(query, limit, project, type, since)
        elif action == "sync":
            return _sync_all(full)
        elif action == "stats":
            return _stats_all()
        else:
            raise ValueError(f"source='all' not supported for action='{action}'")

    if source not in SOURCES:
        raise ValueError(f"Unknown source: {source}")

    module = SOURCES[source]
    if action == "search":
        return _search_with_metadata(
            module,
            source,
            query=query,
            project=project,
            type=type,
            limit=limit,
            since=since,
            file_path=file_path,
        )
    elif action == "slice":
        return _slice_entries(module, source, file_path, start, end, max_chars, verbose)
    elif action == "sessions":
        return _get_sessions(module, source)
    elif action == "sync":
        return module.sync(full=full)
    elif action == "stats":
        return module.stats()
    else:
        raise ValueError(f"Unknown action: {action}")


def _make_snippet(text: str, query: str, max_len: int = 200) -> str:
    """Create a snippet centered on the first query term match.

    Returns text unchanged if under max_len. Strips FTS5 operators to extract
    search terms, centers a window around the first match, and truncates at
    word boundaries with "..." markers.
    """
    if len(text) <= max_len:
        return text

    # Strip FTS5 operators to extract plain search terms
    terms = re.sub(r"\b(AND|OR|NOT|NEAR)\b", " ", query, flags=re.IGNORECASE)
    terms = re.sub(r"[\"()*,]", " ", terms)
    words = [w.strip() for w in terms.split() if w.strip()]

    # Find first term match position
    match_pos = -1
    text_lower = text.lower()
    for word in words:
        pos = text_lower.find(word.lower())
        if pos >= 0:
            match_pos = pos
            break

    if match_pos < 0:
        # No match found — use leading text
        truncated = text[:max_len]
        last_space = truncated.rfind(" ")
        if last_space > max_len * 0.8:
            truncated = truncated[:last_space]
        return truncated + "..."

    # Center window around match
    half = max_len // 2
    start = max(0, match_pos - half)
    end = min(len(text), start + max_len)
    if end - start < max_len:
        start = max(0, end - max_len)

    snippet = text[start:end]

    # Truncate at word boundaries
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


def _search_with_metadata(
    module,
    source: str,
    query: str,
    project: str,
    type: str,
    limit: int,
    since: str,
    file_path: str = "",
) -> SearchResults:
    """Search with compact output format.

    Returns files lookup table and compact hit strings like:
    "0[55/64] tool: Exit code: 0..."
    """
    conn = common.get_connection(module.DB_NAME)
    module._init_schema(conn)

    raw_hits = module.search(
        query=query,
        project=project,
        type=type,
        limit=limit,
        since=since,
        file_path=file_path,
    )

    # Build file lookup table and compact hits
    files: list[str] = []
    file_to_idx: dict[str, int] = {}
    hits: list[str] = []

    for row in raw_hits:
        fp = row["file_path"]

        # Add to files lookup if new
        if fp not in file_to_idx:
            file_to_idx[fp] = len(files)
            files.append(fp)

        fidx = file_to_idx[fp]
        entry_idx = row.get("idx") if row.get("idx") is not None else 0
        session_len = common.get_session_length(conn, fp)
        entry_type = row.get("type", "unknown")
        snippet = _make_snippet(row.get("content_text") or "", query)

        # Format: "file_idx[entry_idx/session_len] type: snippet"
        hits.append(f"{fidx}[{entry_idx}/{session_len}] {entry_type}: {snippet}")

    return SearchResults(
        files=files,
        hits=hits,
        query=query,
        total=len(hits),
    )


def _search_all_merged(
    query: str, limit: int, project: str, type: str, since: str
) -> SearchResults:
    """Search all sources, merge file lists and reindex hits.

    Note:
    - Fetches up to `limit` from each source
    - File indices are global across all sources
    """
    merged_files: list[str] = []
    merged_hits: list[str] = []

    for source_name, module in SOURCES.items():
        result = _search_with_metadata(
            module,
            source_name,
            query=query,
            project=project,
            type=type,
            limit=limit,
            since=since,
        )

        # Reindex hits to use global file indices
        file_offset = len(merged_files)
        for hit in result.hits:
            # Parse "old_idx[...]" and replace with "new_idx[...]"
            bracket_pos = hit.find("[")
            if bracket_pos > 0:
                old_idx = int(hit[:bracket_pos])
                new_idx = old_idx + file_offset
                merged_hits.append(f"{new_idx}{hit[bracket_pos:]}")
            else:
                merged_hits.append(hit)

        merged_files.extend(result.files)

    return SearchResults(
        files=merged_files,
        hits=merged_hits[:limit],
        query=query,
        total=len(merged_hits),
    )


def _slice_entries(
    module,
    source: str,
    file_path: str,
    start: int,
    end: int | None,
    max_chars: int,
    verbose: bool,
) -> list[str] | list[Entry]:
    """Get entries by position.

    Args:
        max_chars: Max chars per entry in compact mode (0=no limit).
        verbose: If True, return full Entry objects. If False, return compact
                 "type: content" strings.

    Position in list corresponds to index (start + position).
    """
    if not file_path:
        raise ValueError("file_path is required for slice action")

    conn = common.get_connection(module.DB_NAME)
    module._init_schema(conn)
    rows = common.slice_entries(conn, file_path, start, end)

    if verbose:
        return [Entry.from_db_row(row, source) for row in rows]

    result = []
    for row in rows:
        entry_type = row.get("type", "unknown")
        content = row.get("content_text", "") or ""
        if max_chars > 0 and len(content) > max_chars:
            truncated = content[:max_chars]
            last_space = truncated.rfind(" ")
            if last_space > max_chars * 0.8:
                truncated = truncated[:last_space]
            content = truncated + "..."
        if content:
            result.append(f"{entry_type}: {content}")
        else:
            result.append(f"{entry_type}:")
    return result


def _get_sessions(module, source: str) -> SessionList:
    """List all sessions for a source."""
    conn = common.get_connection(module.DB_NAME)
    module._init_schema(conn)
    rows = common.get_sessions(conn)
    return SessionList(
        source=source,
        sessions=[
            SessionInfo(
                file_path=row["file_path"],
                session_id=row["session_id"],
                source=source,
                project=row.get("project_path"),
                start_time=row.get("start_time"),
                end_time=row.get("end_time"),
                entry_count=row["entry_count"],
            )
            for row in rows
        ],
    )


def _sync_all(full: bool = False) -> dict[str, dict]:
    """Sync all transcript sources."""
    return {
        "claude": claude.sync(full=full),
        "codex": codex.sync(full=full),
        "gemini": gemini.sync(full=full),
        "mcp": mcp_memory.sync(full=full),
    }


def _stats_all() -> dict[str, dict]:
    """Get statistics for all transcript sources."""
    return {
        "claude": claude.stats(),
        "codex": codex.stats(),
        "gemini": gemini.stats(),
        "mcp": mcp_memory.stats(),
    }
