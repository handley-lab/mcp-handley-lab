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
    file_path: str = Field(
        default="",
        description="Session identifier for slice (from SearchHit.file_path)",
    ),
    start: int = Field(
        default=0,
        description="Start index for slice (0-indexed)",
    ),
    end: int = Field(
        default=-1,
        description="End index for slice (exclusive, -1 = to end of session)",
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

    Search returns hits with location metadata (index, session_length) for slicing.
    Slice retrieves entries at specific positions within a session.

    Example workflow:
        1. Search to find relevant entries
        2. Use file_path and index from hits to slice surrounding context
    """
    # Convert -1 to None for end parameter
    end_val = None if end == -1 else end

    result = _context(
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
        full=full,
        verbose=verbose,
    )

    # Convert Pydantic models to dicts for JSON serialization
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if isinstance(result, list):
        return [e.model_dump() if hasattr(e, "model_dump") else e for e in result]
    return result


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
        description="Filter by entry type: user, assistant, system, tool",
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
