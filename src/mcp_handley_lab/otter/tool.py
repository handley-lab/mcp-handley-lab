"""Otter.ai MCP tool for accessing live meeting transcripts.

Uses undocumented Otter.ai API with session cookies.
Cookies auto-extracted from browser (Chrome/Chromium/Brave/Firefox) via pycookiecheat.
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
  Required: otid. Optional: max_segments (0=all, default 0), since_offset_ms (0=all, for incremental reads),
  include_formatted_text (default true; set false to omit formatted_text and reduce response size for live monitoring).
- recent: List recent meetings.
  Optional: limit (default 10).
- search: Filter recent meetings by title (client-side).
  Required: query. Optional: limit (default 10).
- refresh: Refresh session cookies from browser cookie store.
  Tries Chrome, Chromium, Brave, Firefox. If not logged in, opens otter.ai sign-in page.
  Note: API calls auto-refresh on auth failure, so explicit refresh is rarely needed.
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
    since_offset_ms: int = Field(
        default=0,
        description="Only return segments after this offset in ms. Track max start_offset_ms from previous call for incremental reading (for 'transcript').",
    ),
    include_formatted_text: bool = Field(
        default=True,
        description="Include formatted_text in transcript response. Set false to reduce response size for live monitoring (for 'transcript').",
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
        return OtterResult(
            transcript=get_transcript(
                otid,
                max_segments,
                since_offset_ms,
                include_formatted_text=include_formatted_text,
            )
        )
    elif action == "recent":
        return OtterResult(meetings=list_recent_meetings(limit))
    elif action == "search":
        if not query:
            raise ValueError("'query' is required for search action")
        return OtterResult(meetings=search_meetings(query, limit))
    elif action == "refresh":
        return OtterResult(refresh=refresh_session())
    raise ValueError(f"Unknown action: {action}")
