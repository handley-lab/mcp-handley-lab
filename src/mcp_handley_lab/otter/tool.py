"""Otter.ai MCP tool for accessing live meeting transcripts.

Uses undocumented Otter.ai API with session cookies.
Session must be refreshed via 'refresh' action or otter-refresh-session.
"""

from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.otter.shared import OtterResult

mcp = FastMCP("Otter Tool")


@mcp.tool(
    description="""Access Otter.ai meeting transcripts.
Requires session cookies (use 'refresh' action to update, or run otter-refresh-session externally).

Actions:
- live: List currently live meetings (title, otid, status).
  No required params.
- transcript: Get full transcript for a meeting (live or recent).
  Required: otid. Optional: max_segments (0=all, default 0).
- recent: List recent meetings.
  Optional: limit (default 10).
- search: Filter recent meetings by title (client-side).
  Required: query. Optional: limit (default 10).
- refresh: Refresh session cookies using Playwright headless.
  No params. Auto-copies Chrome profile on first run. Requires: playwright installed.
"""
)
def otter(
    action: Literal["live", "transcript", "recent", "search", "refresh"] = Field(
        ...,
        description="Operation to perform.",
    ),
    otid: str = Field(default="", description="Meeting ID (for 'transcript')."),
    query: str = Field(
        default="", description="Search text for meeting titles (for 'search')."
    ),
    limit: int = Field(default=10, description="Max results (for 'recent'/'search')."),
    max_segments: int = Field(
        default=0,
        description="Return last N segments (most recent), 0=all (for 'transcript').",
    ),
) -> OtterResult:
    """Dispatch to the appropriate Otter.ai operation."""
    from mcp_handley_lab.otter.shared import (
        find_live_meetings,
        get_transcript,
        list_recent_meetings,
        refresh_session,
        search_meetings,
    )

    if action == "live":
        return OtterResult(meetings=find_live_meetings())
    elif action == "transcript":
        if not otid:
            raise ValueError("'otid' is required for transcript action")
        return OtterResult(transcript=get_transcript(otid, max_segments))
    elif action == "recent":
        return OtterResult(meetings=list_recent_meetings(limit))
    elif action == "search":
        if not query:
            raise ValueError("'query' is required for search action")
        return OtterResult(meetings=search_meetings(query, limit))
    elif action == "refresh":
        return OtterResult(refresh=refresh_session())
    raise ValueError(f"Unknown action: {action}")
