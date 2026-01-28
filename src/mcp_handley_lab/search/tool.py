"""MCP tool for transcript search with RLM-style slicing."""

from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.search.core import context as _context

mcp = FastMCP("Transcript Search")


@mcp.tool(description="Search and slice AI conversation context (RLM-style)")
def context(
    action: Literal["search", "slice", "sessions", "sync", "stats"] = Field(
        description="Action: 'search' to query, 'slice' to get entries by position, "
        "'sessions' to list sessions, 'sync' to update index, 'stats' for usage statistics"
    ),
    source: Literal["claude", "codex", "gemini", "mcp", "all"] = Field(
        default="claude",
        description="Transcript source. Use 'all' to search across all sources.",
    ),
    query: str = Field(
        default="",
        description='FTS5 query. Syntax: word, prefix*, "exact phrase", '
        "A AND B, A OR B, NEAR(a b, N), NOT term. "
        "Invalid syntax auto-falls back to phrase search.",
    ),
    project: str = Field(
        default="",
        description="Filter by project path (partial match)",
    ),
    type: str = Field(
        default="",
        description="Filter by entry type: user, assistant, system, tool, prompt",
    ),
    limit: int = Field(
        default=20,
        description="Maximum number of results to return",
    ),
    since: str = Field(
        default="",
        description="Filter entries after this ISO timestamp (e.g., '2024-01-01')",
    ),
    file_path: str = Field(
        default="",
        description="Session identifier for slice/search scoping. "
        "Accepts composite handle '{source}:{session_key}' from search results, "
        "or raw session_key. Use session_id from search hits for slicing.",
    ),
    start: int = Field(
        default=0,
        description="Start index for slice (0-indexed)",
    ),
    end: int = Field(
        default=-1,
        description="End index for slice (exclusive, -1 = to end of session)",
    ),
    max_chars: int = Field(
        default=0,
        description="For slice: max chars per entry (0=no limit). Truncates at word boundary.",
    ),
    full: bool = Field(
        default=False,
        description="For sync action: re-sync all files, not just changed ones",
    ),
    verbose: bool = Field(
        default=False,
        description="For slice action: return full Entry objects instead of compact strings",
    ),
) -> dict:
    """Search and slice AI conversation context.

    Search returns structured hits with session_id, entry_index, role, snippet, and BM25 score.
    Use session_id from hits to slice for full context.

    Workflow: search -> get session_id/entry_index -> slice with context window
    """
    # Convert -1 to None for end parameter
    end_val = None if end == -1 else end

    return _context(
        action=action,
        source=source,
        query=query,
        project=project,
        type=type,
        limit=limit,
        since=since,
        file_path=file_path,
        start=start,
        end=end_val,
        max_chars=max_chars,
        full=full,
        verbose=verbose,
    )


@mcp.tool(description="[DEPRECATED] Use 'context' tool instead")
def transcript_search(
    action: Literal["search", "sync", "stats"] = Field(
        description="Action: 'search' to query, 'sync' to update index, 'stats' for usage statistics"
    ),
    source: Literal["claude", "codex", "gemini", "mcp"] = Field(
        default="claude",
        description="Transcript source: claude (Claude Code), codex (Codex CLI), gemini (Gemini CLI), mcp (MCP Memory)",
    ),
    query: str = Field(
        default="",
        description="FTS5 search query (supports AND, OR, NEAR, prefix*). Required for search action.",
    ),
    project: str = Field(
        default="",
        description="Filter by project path (partial match)",
    ),
    type: str = Field(
        default="",
        description="Filter by entry type: user, assistant, system, tool, prompt",
    ),
    limit: int = Field(
        default=20,
        description="Maximum number of results to return",
    ),
    since: str = Field(
        default="",
        description="Filter entries after this ISO timestamp (e.g., '2024-01-01')",
    ),
    full: bool = Field(
        default=False,
        description="For sync action: re-sync all files, not just changed ones",
    ),
) -> dict:
    """[DEPRECATED] Search and analyze AI assistant transcript history.

    Use the 'context' tool instead for enhanced RLM-style search with slicing support.
    """
    return context(
        action=action,
        source=source,
        query=query,
        project=project,
        type=type,
        limit=limit,
        since=since,
        full=full,
    )
