"""Otter.ai tool for accessing live meeting transcripts.

Usage:
    from mcp_handley_lab.otter import find_live_meetings, get_transcript
"""

from mcp_handley_lab.otter.shared import (
    find_live_meetings,
    get_transcript,
    list_recent_meetings,
    refresh_session,
    search_meetings,
)

__all__ = [
    "find_live_meetings",
    "get_transcript",
    "list_recent_meetings",
    "refresh_session",
    "search_meetings",
]
