"""AI Transcript Search - search across AI assistant conversation history.

Supports Claude Code, Codex CLI, Gemini CLI, and MCP Memory conversations.

Core API:
    context() - RLM-style search and slice for AI conversation context

Sources (adapter protocol):
    sources.claude - Claude Code transcripts
    sources.codex - Codex CLI transcripts
    sources.gemini - Gemini CLI transcripts
    sources.mcp_memory - MCP Memory conversations

Backward-compatible functions:
    search_all() - Search all sources (returns dict by source)
    sync_all() - Sync all sources
    stats_all() - Get stats for all sources
"""

from mcp_handley_lab.search.core import context

# Legacy module-level aliases for backward compatibility
# (code that imports `from mcp_handley_lab.search import claude` etc.)
from mcp_handley_lab.search.sources import SOURCES, claude, codex, gemini, mcp_memory

mcp = mcp_memory  # Alias for `from mcp_handley_lab.search import mcp`

__all__ = [
    "context",
    "SOURCES",
    "claude",
    "codex",
    "gemini",
    "mcp_memory",
    "mcp",
    "search_all",
    "sync_all",
    "stats_all",
]


def search_all(query: str, limit: int = 5) -> dict[str, list[dict]]:
    """Search across all transcript sources.

    Note: This is a backward-compatible wrapper. Prefer context(action='search', source='all').
    """
    from mcp_handley_lab.search import db

    conn = db.ensure_db()
    results = {}
    for source_name in SOURCES:
        if query:
            results[source_name] = db.fts_search(
                conn, query, source=source_name, limit=limit
            )
        else:
            results[source_name] = db.search_recent(
                conn, source=source_name, limit=limit
            )
    return results


def sync_all(full: bool = False) -> dict[str, dict]:
    """Sync all transcript sources.

    Note: This is a backward-compatible wrapper. Prefer context(action='sync', source='all').
    """
    from mcp_handley_lab.search.sync import sync_all_sources

    return sync_all_sources(SOURCES, full=full)


def stats_all() -> dict[str, dict]:
    """Get statistics for all transcript sources.

    Note: This is a backward-compatible wrapper. Prefer context(action='stats', source='all').
    """
    from mcp_handley_lab.search import db

    conn = db.ensure_db()
    return {name: db.get_stats(conn, name) for name in SOURCES}
