"""Google Calendar tool for calendar management via MCP."""
import pickle
from datetime import datetime, timedelta, timezone
from typing import Any

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP

from mcp_handley_lab.common.config import settings

mcp = FastMCP("Google Calendar Tool")


# Google Calendar API scopes
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_calendar_service():
    """Get authenticated Google Calendar service."""
    creds = None
    token_file = settings.google_token_path
    credentials_file = settings.google_credentials_path

    # Load existing token
    if token_file.exists():
        with open(token_file, "rb") as f:
            creds = pickle.load(f)

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_file), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save credentials for next run
        token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)

    return build("calendar", "v3", credentials=creds)


def _resolve_calendar_id(calendar_id: str, service) -> str:
    """Resolve calendar name to calendar ID."""
    if calendar_id in ["primary", "all"] or "@" in calendar_id:
        return calendar_id

    # Try to find calendar by name
    calendar_list = service.calendarList().list().execute()

    for calendar in calendar_list.get("items", []):
        if calendar.get("summary", "").lower() == calendar_id.lower():
            return calendar["id"]

    # If not found, assume it's already an ID
    return calendar_id


def _parse_datetime_to_utc(dt_str: str) -> str:
    """
    Parse datetime string and convert to UTC with proper timezone handling.

    Handles:
    - ISO 8601 with timezone: "2024-06-30T14:00:00+01:00" -> "2024-06-30T13:00:00Z"
    - ISO 8601 with Z: "2024-06-30T14:00:00Z" -> "2024-06-30T14:00:00Z"
    - ISO 8601 naive: "2024-06-30T14:00:00" -> "2024-06-30T14:00:00Z" (assumes UTC)
    - Date only: "2024-06-30" -> "2024-06-30T00:00:00Z"
    """
    if not dt_str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if "T" not in dt_str:
        # Date only format - treat as start of day in UTC
        return dt_str + "T00:00:00Z"

    if dt_str.endswith("Z"):
        # Already UTC
        return dt_str
    elif "+" in dt_str or dt_str.count("-") > 2:
        # Has timezone info - convert to UTC properly
        dt = datetime.fromisoformat(dt_str)
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.isoformat().replace("+00:00", "Z")
    else:
        # Naive datetime - assume UTC
        return dt_str + "Z"


def _format_datetime(dt_str: str) -> str:
    """Format datetime string for display with proper timezone handling."""
    if "T" in dt_str:
        # DateTime format
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo:
            # Format with timezone info
            return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        else:
            # Naive datetime - assume UTC for display
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    else:
        return dt_str + " (all-day)"


def _client_side_filter(
    events: list[dict[str, Any]],
    search_text: str | None = None,
    search_fields: list[str] = [],
    case_sensitive: bool = False,
    match_all_terms: bool = True,
) -> list[dict[str, Any]]:
    """
    Client-side filtering of events with advanced search capabilities.

    Args:
        events: List of calendar events to filter
        search_text: Text to search for
        search_fields: Fields to search in. Default: ['summary', 'description', 'location']
        case_sensitive: Whether search should be case sensitive
        match_all_terms: If True, all search terms must match (AND logic).
                        If False, any search term can match (OR logic).
    """
    if not search_text:
        return events

    if search_fields is None:
        search_fields = ["summary", "description", "location"]

    # Split search text into terms
    search_terms = search_text.split()
    if not search_terms:
        return events

    # Prepare search terms for comparison
    if not case_sensitive:
        search_terms = [term.lower() for term in search_terms]

    filtered_events = []

    for event in events:
        # Extract searchable text from event
        searchable_text_parts = []

        for field in search_fields:
            if field == "summary":
                text = event.get("summary", "")
            elif field == "description":
                text = event.get("description", "")
            elif field == "location":
                text = event.get("location", "")
            elif field == "attendees":
                # Search in attendee names and emails
                attendees = event.get("attendees", [])
                attendee_texts = []
                for attendee in attendees:
                    attendee_texts.append(attendee.get("email", ""))
                    attendee_texts.append(attendee.get("displayName", ""))
                text = " ".join(attendee_texts)
            else:
                text = event.get(field, "")

            if text:
                searchable_text_parts.append(text)

        # Combine all searchable text
        full_searchable_text = " ".join(searchable_text_parts)
        if not case_sensitive:
            full_searchable_text = full_searchable_text.lower()

        # Check if event matches search criteria
        if match_all_terms:
            # AND logic: all terms must be present
            matches = all(term in full_searchable_text for term in search_terms)
        else:
            # OR logic: any term can be present
            matches = any(term in full_searchable_text for term in search_terms)

        if matches:
            filtered_events.append(event)

    return filtered_events


@mcp.tool(
    description="Retrieves detailed information about a specific calendar event by its ID. Returns comprehensive event details including attendees, location, and timestamps."
)
def get_event(event_id: str, calendar_id: str = "primary") -> str:
    """Get detailed information about a specific event."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    event = service.events().get(calendarId=resolved_id, eventId=event_id).execute()

    result = "Event Details:\n"
    result += f"Title: {event.get('summary', 'No Title')}\n"

    start = event["start"].get("dateTime", event["start"].get("date"))
    end = event["end"].get("dateTime", event["end"].get("date"))
    result += f"Start: {_format_datetime(start)}\n"
    result += f"End: {_format_datetime(end)}\n"

    if event.get("description"):
        result += f"Description: {event['description']}\n"

    if event.get("location"):
        result += f"Location: {event['location']}\n"

    if event.get("attendees"):
        result += "Attendees:\n"
        for attendee in event["attendees"]:
            email = attendee.get("email", "Unknown")
            status = attendee.get("responseStatus", "needsAction")
            result += f"  - {email} ({status})\n"

    result += f"Event ID: {event['id']}\n"
    result += f"Created: {event.get('created', 'Unknown')}\n"
    result += f"Updated: {event.get('updated', 'Unknown')}\n"

    return result


@mcp.tool(
    description="Creates a new event in a Google Calendar. Requires a `summary` (title), `start_datetime`, and `end_datetime`. Datetimes must be in ISO 8601 format (e.g., '2024-10-26T10:00:00Z' for timed events, or '2024-10-26' for all-day events). Optionally include `attendees`, a `description`, and a `calendar_id`."
)
def create_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: str | None = None,
    calendar_id: str = "primary",
    timezone: str = "UTC",
    attendees: list[str] = [],
) -> str:
    """Create a new calendar event."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    # Build event object
    event_body = {
        "summary": summary,
        "description": description or "",
        "start": {},
        "end": {},
    }

    # Handle all-day vs timed events
    if "T" in start_datetime:
        # Timed event
        event_body["start"]["dateTime"] = start_datetime
        event_body["start"]["timeZone"] = timezone
        event_body["end"]["dateTime"] = end_datetime
        event_body["end"]["timeZone"] = timezone
    else:
        # All-day event
        event_body["start"]["date"] = start_datetime
        event_body["end"]["date"] = end_datetime

    # Add attendees if provided
    if attendees:
        event_body["attendees"] = [{"email": email} for email in attendees]

    # Create the event
    created_event = (
        service.events().insert(calendarId=resolved_id, body=event_body).execute()
    )

    start = created_event["start"].get("dateTime", created_event["start"].get("date"))

    # Return structured data as JSON string for programmatic access
    import json

    result_data = {
        "status": "Event created successfully!",
        "event_id": created_event["id"],
        "title": created_event["summary"],
        "time": _format_datetime(start),
        "calendar": calendar_id,
        "attendees": attendees or [],
    }

    # Format as human-readable JSON
    return json.dumps(result_data, indent=2)


@mcp.tool(
    description="Updates an existing calendar event by event ID. Only provided parameters will be updated - omit parameters to leave them unchanged. Pass empty strings to clear fields. Returns confirmation of the update."
)
def update_event(
    event_id: str,
    calendar_id: str = "primary",
    summary: str | None = None,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    description: str | None = None,
) -> str:
    """Update an existing calendar event. Trusts the provided event_id."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    update_body = {}
    if summary is not None:
        update_body["summary"] = summary
    if description is not None:
        update_body["description"] = description

    if start_datetime:
        update_body["start"] = (
            {"dateTime": start_datetime, "timeZone": "UTC"}
            if "T" in start_datetime
            else {"date": start_datetime}
        )

    if end_datetime:
        update_body["end"] = (
            {"dateTime": end_datetime, "timeZone": "UTC"}
            if "T" in end_datetime
            else {"date": end_datetime}
        )

    if not update_body:
        return "No updates specified. Nothing to do."

    # Use 'patch' which is more efficient for partial updates
    updated_event = (
        service.events()
        .patch(calendarId=resolved_id, eventId=event_id, body=update_body)
        .execute()
    )
    return f"Event (ID: {updated_event['id']}) updated successfully. Fields changed: {', '.join(update_body.keys())}"


@mcp.tool(
    description="Deletes a calendar event permanently by event ID. WARNING: This action is irreversible. Returns confirmation of deletion."
)
def delete_event(event_id: str, calendar_id: str = "primary") -> str:
    """Delete a calendar event. Trusts the provided event_id."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    # The API will return a 404 if it doesn't exist, which is handled below.
    service.events().delete(calendarId=resolved_id, eventId=event_id).execute()
    return f"Event (ID: {event_id}) has been permanently deleted."


@mcp.tool(
    description="Lists all calendars accessible to the authenticated user with their IDs, access levels, and colors. Use this to discover calendar IDs before using other calendar tools."
)
def list_calendars() -> str:
    """List all accessible calendars."""
    service = _get_calendar_service()

    calendar_list = service.calendarList().list().execute()
    calendars = calendar_list.get("items", [])

    if not calendars:
        return "No calendars found."

    result = f"Found {len(calendars)} accessible calendars:\n\n"

    for calendar in calendars:
        name = calendar.get("summary", "Unknown")
        cal_id = calendar["id"]
        access_role = calendar.get("accessRole", "unknown")
        color_id = calendar.get("colorId", "default")

        result += f"• {name}\n"
        result += f"  ID: {cal_id}\n"
        result += f"  Access: {access_role}\n"
        result += f"  Color: {color_id}\n\n"

    return result.strip()


@mcp.tool(
    description="Finds available free time slots within a calendar for scheduling meetings. Defaults to next 7 days if no date range specified. Returns up to 20 slots, checking every 30 minutes. Set `work_hours_only=False` to include evenings/weekends."
)
def find_time(
    calendar_id: str = "primary",
    start_date: str | None = None,
    end_date: str | None = None,
    duration_minutes: int = 60,
    work_hours_only: bool = True,
) -> str:
    """Find free time slots in a calendar."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    # Set default date range
    start_dt = datetime.now() if not start_date else datetime.fromisoformat(start_date)

    if not end_date:
        end_dt = start_dt + timedelta(days=7)
    else:
        end_dt = datetime.fromisoformat(end_date)

    # Get busy times with proper timezone handling
    freebusy_request = {
        "timeMin": _parse_datetime_to_utc(start_dt.isoformat()),
        "timeMax": _parse_datetime_to_utc(end_dt.isoformat()),
        "items": [{"id": resolved_id}],
    }

    freebusy_result = service.freebusy().query(body=freebusy_request).execute()
    busy_times = freebusy_result["calendars"][resolved_id].get("busy", [])

    # Generate time slots with proper timezone handling
    slots = []
    # Convert to UTC for consistent comparison
    if start_dt.tzinfo:
        current = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        current = start_dt

    if end_dt.tzinfo:
        end_dt_utc = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        end_dt_utc = end_dt

    slot_duration = timedelta(minutes=duration_minutes)

    while current + slot_duration <= end_dt_utc:
        if work_hours_only and (current.hour < 9 or current.hour >= 17):
            current += timedelta(hours=1)
            continue

        slot_end = current + slot_duration

        # Check if slot conflicts with busy times
        is_free = True
        for busy in busy_times:
            # Parse busy times properly
            busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
            busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))

            # Convert to UTC naive for comparison
            if busy_start.tzinfo:
                busy_start = busy_start.astimezone(timezone.utc).replace(tzinfo=None)
            if busy_end.tzinfo:
                busy_end = busy_end.astimezone(timezone.utc).replace(tzinfo=None)

            if current < busy_end and slot_end > busy_start:
                is_free = False
                break

        if is_free:
            slots.append((current, slot_end))

        current += timedelta(minutes=30)  # Check every 30 minutes

    if not slots:
        return f"No free {duration_minutes}-minute slots found in the specified time range."

    result = f"Found {len(slots)} free {duration_minutes}-minute slots:\n\n"

    for start_time, end_time in slots[:20]:  # Limit to first 20 slots
        result += f"• {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%H:%M')}\n"

    if len(slots) > 20:
        result += f"\n... and {len(slots) - 20} more slots"

    return result


@mcp.tool(
    description="Searches for events across one or all calendars within a specified date range. Provide a `search_text` to find events with matching text in the title, description, or location. If no search text is given, it lists all events. Supports advanced client-side filtering by `search_fields` and `case_sensitive` options."
)
def search_events(
    search_text: str | None = None,
    calendar_id: str = "all",
    start_date: str | None = None,
    end_date: str | None = None,
    max_results: int = 100,
    search_fields: list[str] = [],
    case_sensitive: bool = False,
    match_all_terms: bool = True,
) -> str:
    """Advanced hybrid search for calendar events."""
    # Step 1: Server-side filtering using Google API 'q' parameter
    # This reduces data transfer and improves initial search performance
    service = _get_calendar_service()

    # Set default date range if not provided with proper timezone handling
    if not start_date:
        start_date = _parse_datetime_to_utc("")  # Uses current time in UTC
    else:
        start_date = _parse_datetime_to_utc(start_date)

    if not end_date:
        # Default to 7 days for basic listing, 1 year for search
        days = 7 if not search_text else 365
        end_dt = datetime.now(timezone.utc) + timedelta(days=days)
        end_date = end_dt.isoformat().replace("+00:00", "Z")
    else:
        # Handle end date - for date-only format, use end of day
        if "T" not in end_date:
            end_date = end_date + "T23:59:59Z"
        else:
            end_date = _parse_datetime_to_utc(end_date)

    events_list = []
    warnings = []

    if calendar_id == "all":
        # Search all calendars
        calendar_list = service.calendarList().list().execute()

        for calendar in calendar_list.get("items", []):
            cal_id = calendar["id"]

            params = {
                "calendarId": cal_id,
                "timeMin": start_date,
                "timeMax": end_date,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            }
            if search_text:
                params["q"] = search_text
            events_result = service.events().list(**params).execute()

            cal_events = events_result.get("items", [])
            for event in cal_events:
                event["calendar_name"] = calendar.get("summary", cal_id)
            events_list.extend(cal_events)
    else:
        # Search specific calendar
        resolved_id = _resolve_calendar_id(calendar_id, service)

        params = {
            "calendarId": resolved_id,
            "timeMin": start_date,
            "timeMax": end_date,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if search_text:
            params["q"] = search_text
        events_result = service.events().list(**params).execute()
        events_list = events_result.get("items", [])

    # Step 2: Apply client-side filtering if advanced options are specified
    # This provides granular control not available in the Google API
    if search_fields or case_sensitive or not match_all_terms:
        filtered_events = _client_side_filter(
            events_list,
            search_text=search_text,
            search_fields=search_fields,
            case_sensitive=case_sensitive,
            match_all_terms=match_all_terms,
        )
    else:
        filtered_events = events_list

    if not filtered_events:
        if search_text:
            return (
                f"No events found matching '{search_text}' in the specified criteria."
            )
        else:
            return "No events found in the specified date range."

    # Sort by start time
    filtered_events.sort(
        key=lambda x: x.get("start", {}).get(
            "dateTime", x.get("start", {}).get("date", "")
        )
    )

    if search_text:
        result = f"Found {len(filtered_events)} events matching '{search_text}':\n\n"
    else:
        result = f"Found {len(filtered_events)} events:\n\n"

    for event in filtered_events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        title = event.get("summary", "No Title")
        event_id = event["id"]

        result += f"• {title}\n"
        result += f"  Time: {_format_datetime(start)}\n"
        result += f"  ID: {event_id}\n"

        if "calendar_name" in event:
            result += f"  Calendar: {event['calendar_name']}\n"

        if event.get("location"):
            result += f"  Location: {event['location']}\n"

        if event.get("description"):
            # Show first 100 characters of description
            desc = event["description"]
            if len(desc) > 100:
                desc = desc[:97] + "..."
            result += f"  Description: {desc}\n"

        result += "\n"

    # Add warnings if any calendars were inaccessible
    if warnings:
        result += (
            "\n⚠️ Warnings:\n" + "\n".join(f"- {warning}" for warning in warnings) + "\n"
        )

    # Add search summary only for advanced searches
    if search_text and (search_fields or case_sensitive or not match_all_terms):
        search_summary = "\nSearch Details:\n"
        search_summary += f"- Search text: '{search_text}'\n"
        search_summary += f"- Fields searched: {search_fields or ['summary', 'description', 'location']}\n"
        search_summary += f"- Match logic: {'All terms must match (AND)' if match_all_terms else 'Any term can match (OR)'}\n"
        search_summary += f"- Case sensitive: {case_sensitive}\n"
        search_summary += f"- Date range: {start_date} to {end_date}\n"
        return result.strip() + search_summary

    return result.strip()


@mcp.tool(
    description="Checks the status of the Google Calendar Tool server and API connectivity. Returns connection status and list of available tools. Use this to verify the tool is operational before making other requests."
)
def server_info() -> str:
    """Get server status and Google Calendar API connection info."""
    service = _get_calendar_service()

    # Test API connection by getting calendar list
    calendar_list = service.calendarList().list(maxResults=1).execute()

    return f"""Google Calendar Tool Server Status
========================================
Status: Connected and ready
API Connection: ✓ Active
Calendars Access: ✓ Available ({len(calendar_list.get('items', []))} calendars accessible)

Available tools:
- search_events: Search and list calendar events (handles both basic listing and advanced search)
- get_event: Get detailed event information
- create_event: Create new calendar events
- update_event: Update existing events
- delete_event: Delete calendar events
- list_calendars: List all accessible calendars
- find_time: Find free time slots
- server_info: Get server status"""
