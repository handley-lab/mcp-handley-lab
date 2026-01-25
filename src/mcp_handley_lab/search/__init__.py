"""AI Transcript Search - search across AI assistant conversation history.

Supports Claude Code, Codex CLI, Gemini CLI, and MCP Memory conversations.

Core API:
    context() - RLM-style search and slice for AI conversation context

Modules:
    claude - Claude Code transcripts
    codex - Codex CLI transcripts
    gemini - Gemini CLI transcripts
    mcp_memory - MCP Memory conversations

Backward-compatible functions:
    search_all() - Search all sources (returns dict by source)
    sync_all() - Sync all sources
    stats_all() - Get stats for all sources
"""

from mcp_handley_lab.search import claude, codex, gemini, mcp_memory
from mcp_handley_lab.search.core import context

# Alias for plan compatibility: `from mcp_handley_lab.search import mcp`
mcp = mcp_memory

__all__ = [
    "context",
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

    Args:
        query: FTS search query
        limit: Max results per source

    Returns:
        Dict mapping source name to list of results
    """
    return {
        "claude": claude.search(query=query, limit=limit),
        "codex": codex.search(query=query, limit=limit),
        "gemini": gemini.search(query=query, limit=limit),
        "mcp": mcp_memory.search(query=query, limit=limit),
    }


def sync_all(full: bool = False) -> dict[str, dict]:
    """Sync all transcript sources.

    Args:
        full: If True, re-sync all files (not just changed ones)

    Returns:
        Dict mapping source name to sync stats
    """
    return {
        "claude": claude.sync(full=full),
        "codex": codex.sync(full=full),
        "gemini": gemini.sync(full=full),
        "mcp": mcp_memory.sync(full=full),
    }


def stats_all() -> dict[str, dict]:
    """Get statistics for all transcript sources.

    Returns:
        Dict mapping source name to stats
    """
    return {
        "claude": claude.stats(),
        "codex": codex.stats(),
        "gemini": gemini.stats(),
        "mcp": mcp_memory.stats(),
    }
