"""Google Calendar tool for MCP framework.

Usage:
    from mcp_handley_lab.google_calendar import read, create, update, delete, list_calendars

    # List calendars
    calendars = list_calendars()

    # Read events
    events = read(start_date="2024-01-01", end_date="2024-01-07")

    # Create event
    result = create("Meeting", "tomorrow 2pm", "tomorrow 3pm", calendar_id="primary")

    # Update event
    update(event_id="abc123", summary="New Title")

    # Delete event
    delete(event_id="abc123")
"""

from mcp_handley_lab.google_calendar.shared import (
    create,
    delete,
    list_calendars,
    read,
    update,
)

__all__ = ["read", "create", "update", "delete", "list_calendars"]
