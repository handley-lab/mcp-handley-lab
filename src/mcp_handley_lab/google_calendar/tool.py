"""Google Calendar tool for calendar management via MCP."""
import pickle
import zoneinfo
from datetime import datetime, timedelta, timezone
from typing import Any

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.shared.models import ServerInfo

# Application-level default timezone as final fallback
DEFAULT_TIMEZONE = "Europe/London"


class Attendee(BaseModel):
    """Calendar event attendee."""

    email: str
    responseStatus: str = "needsAction"


class EventDateTime(BaseModel):
    """Event date/time information."""

    dateTime: str = ""
    date: str = ""
    timeZone: str = ""


class CalendarEvent(BaseModel):
    """Calendar event details."""

    id: str
    summary: str
    description: str = ""
    location: str = ""
    start: EventDateTime
    end: EventDateTime
    attendees: list[Attendee] = Field(default_factory=list)
    calendar_name: str = ""
    created: str = ""
    updated: str = ""


class CreatedEventResult(BaseModel):
    """Result of creating a calendar event."""

    status: str
    event_id: str
    title: str
    time: str
    calendar: str
    attendees: list[str]


class CalendarInfo(BaseModel):
    """Calendar information."""

    id: str
    summary: str
    accessRole: str
    colorId: str


class FreeTimeSlot(BaseModel):
    """Available time slot."""

    start: str
    end: str
    duration_minutes: int


mcp = FastMCP("Google Calendar Tool")


# Google Calendar API scopes
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_calendar_service():
    """Get authenticated Google Calendar service."""
    creds = None
    token_file = settings.google_token_path
    credentials_file = settings.google_credentials_path

    if token_file.exists():
        with open(token_file, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_file), SCOPES
            )
            creds = flow.run_local_server(port=0)

        token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)

    return build("calendar", "v3", credentials=creds)


def _resolve_calendar_id(calendar_id: str, service) -> str:
    """Resolve calendar name to calendar ID."""
    if calendar_id in ["primary", "all"] or "@" in calendar_id:
        return calendar_id

    calendar_list = service.calendarList().list().execute()

    for calendar in calendar_list.get("items", []):
        if calendar.get("summary", "").lower() == calendar_id.lower():
            return calendar["id"]

    return calendar_id


def _get_effective_timezone(
    service, calendar_id: str = "primary", user_specified_timezone: str = ""
) -> str:
    """
    Determines the effective timezone using a robust fallback chain.

    Fallback Order:
    1. User-specified timezone (if valid)
    2. Target calendar's configured timezone
    3. Local system's timezone
    4. Application-level default (DEFAULT_TIMEZONE)
    """
    # 1. User-specified timezone always wins if valid
    if user_specified_timezone:
        try:
            zoneinfo.ZoneInfo(user_specified_timezone)  # Validate it's a real timezone
            return user_specified_timezone
        except zoneinfo.ZoneInfoNotFoundError:
            print(
                f"⚠️  Warning: Invalid timezone '{user_specified_timezone}' provided. Falling back..."
            )

    # 2. Get the calendar's default timezone from the API
    try:
        calendar_list_entry = (
            service.calendarList().get(calendarId=calendar_id).execute()
        )
        calendar_timezone = calendar_list_entry.get("timeZone")
        if calendar_timezone:
            return calendar_timezone
    except Exception:
        # Fails silently if permissions are missing or calendar not in list
        pass

    # 3. Get the local system's timezone
    try:
        import time

        system_timezone = time.tzname[time.daylight]
        # Convert system timezone name to IANA format if needed
        # This is basic - more robust implementations would use tzlocal
        if system_timezone in ["GMT", "BST"]:
            return "Europe/London"
        elif system_timezone in ["EST", "EDT"]:
            return "America/New_York"
        elif system_timezone in ["PST", "PDT"]:
            return "America/Los_Angeles"
        # Add more mappings as needed
    except Exception:
        pass

    # 4. Fallback to the hardcoded application default
    return DEFAULT_TIMEZONE


def _convert_utc_to_local_time(utc_time_str: str, target_timezone: str) -> str:
    """Convert UTC time string to local time in specified timezone."""
    if not utc_time_str or not utc_time_str.endswith("Z"):
        return utc_time_str  # Not UTC, return as-is

    try:
        # Parse UTC time
        utc_dt = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))

        # Convert to target timezone
        if target_timezone:
            local_tz = zoneinfo.ZoneInfo(target_timezone)
            local_dt = utc_dt.astimezone(local_tz)
            return local_dt.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            # No timezone specified, return as local time without Z
            return utc_time_str.rstrip("Z")
    except Exception:
        # If conversion fails, return original
        return utc_time_str


def _has_timezone_inconsistency(event_data: dict) -> bool:
    """Check if an event has conflicting UTC time and timezone label."""
    start = event_data.get("start", {})

    # Check if this is a timed event (not all-day)
    if "dateTime" not in start:
        return False

    start_dt = start.get("dateTime", "")
    timezone = start.get("timeZone", "")

    # The inconsistency exists if dateTime ends in 'Z' (UTC) AND
    # a specific, non-UTC timezone is also defined
    has_utc_suffix = start_dt.endswith("Z")
    has_specific_timezone = timezone and timezone.lower() != "utc"

    return has_utc_suffix and has_specific_timezone


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
        return dt_str + "T00:00:00Z"

    if dt_str.endswith("Z"):
        return dt_str
    elif "+" in dt_str or dt_str.count("-") > 2:
        dt = datetime.fromisoformat(dt_str)
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.isoformat().replace("+00:00", "Z")
    else:
        return dt_str + "Z"


def _format_datetime(dt_str: str) -> str:
    """Format datetime string for display with proper timezone handling."""
    if "T" in dt_str:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo:
            return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        else:
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    else:
        return dt_str + " (all-day)"


def _client_side_filter(
    events: list[dict[str, Any]],
    search_text: str = "",
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

    if not search_fields:
        search_fields = ["summary", "description", "location"]

    search_terms = search_text.split()
    if not search_terms:
        return events

    if not case_sensitive:
        search_terms = [term.lower() for term in search_terms]

    filtered_events = []

    for event in events:
        searchable_text_parts = []

        for field in search_fields:
            if field == "summary":
                text = event.get("summary", "")
            elif field == "description":
                text = event.get("description", "")
            elif field == "location":
                text = event.get("location", "")
            elif field == "attendees":
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

        full_searchable_text = " ".join(searchable_text_parts)
        if not case_sensitive:
            full_searchable_text = full_searchable_text.lower()

        if match_all_terms:
            matches = all(term in full_searchable_text for term in search_terms)
        else:
            matches = any(term in full_searchable_text for term in search_terms)

        if matches:
            filtered_events.append(event)

    return filtered_events


@mcp.tool(
    description="Retrieves detailed information about a specific calendar event by its ID. Returns comprehensive event details including attendees, location, and timestamps. Automatically detects timezone inconsistencies."
)
def get_event(event_id: str, calendar_id: str = "primary") -> CalendarEvent:
    """Get detailed information about a specific event."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    event = service.events().get(calendarId=resolved_id, eventId=event_id).execute()

    # Check for timezone inconsistency and warn user
    if _has_timezone_inconsistency(event):
        print(
            f"⚠️  Timezone inconsistency detected in event '{event.get('summary', 'Unknown')}'"
        )
        print(
            "   Event has UTC time but local timezone label, which can cause confusion."
        )
        print(
            f"   To normalize: update_event(event_id='{event_id}', calendar_id='{calendar_id}', normalize_timezone=True)"
        )

    # Convert start/end to EventDateTime objects with automatic UTC conversion
    start_raw = event["start"]
    end_raw = event["end"]

    start_dt = EventDateTime(
        dateTime=_convert_utc_to_local_time(
            start_raw.get("dateTime", ""), start_raw.get("timeZone", "")
        ),
        date=start_raw.get("date", ""),
        timeZone=start_raw.get("timeZone", ""),
    )
    end_dt = EventDateTime(
        dateTime=_convert_utc_to_local_time(
            end_raw.get("dateTime", ""), end_raw.get("timeZone", "")
        ),
        date=end_raw.get("date", ""),
        timeZone=end_raw.get("timeZone", ""),
    )

    # Convert attendees
    attendees = []
    if event.get("attendees"):
        attendees = [
            Attendee(
                email=att.get("email", "Unknown"),
                responseStatus=att.get("responseStatus", "needsAction"),
            )
            for att in event["attendees"]
        ]

    return CalendarEvent(
        id=event["id"],
        summary=event.get("summary", "No Title"),
        description=event.get("description", ""),
        location=event.get("location", ""),
        start=start_dt,
        end=end_dt,
        attendees=attendees,
        created=event.get("created", ""),
        updated=event.get("updated", ""),
    )


@mcp.tool(
    description="Creates a new event in a Google Calendar. Requires a `summary` (title), `start_datetime`, and `end_datetime`. Datetimes must be in ISO 8601 format (e.g., '2024-10-26T10:00:00Z' for timed events, or '2024-10-26' for all-day events). Optionally include `attendees`, a `description`, `location`, and a `calendar_id`."
)
def create_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: str = "",
    location: str = "",
    calendar_id: str = "primary",
    timezone: str = "",
    attendees: list[str] = [],
) -> CreatedEventResult:
    """Create a new calendar event."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    # Use the centralized timezone helper
    effective_timezone = _get_effective_timezone(
        service, calendar_id=resolved_id, user_specified_timezone=timezone
    )

    event_body = {
        "summary": summary,
        "description": description or "",
        "location": location or "",
        "start": {},
        "end": {},
    }

    if "T" in start_datetime:
        event_body["start"]["dateTime"] = start_datetime
        event_body["start"]["timeZone"] = effective_timezone
        event_body["end"]["dateTime"] = end_datetime
        event_body["end"]["timeZone"] = effective_timezone
    else:
        event_body["start"]["date"] = start_datetime
        event_body["end"]["date"] = end_datetime

    if attendees:
        event_body["attendees"] = [{"email": email} for email in attendees]

    created_event = (
        service.events().insert(calendarId=resolved_id, body=event_body).execute()
    )

    start = created_event["start"].get("dateTime", created_event["start"].get("date"))

    return CreatedEventResult(
        status="Event created successfully!",
        event_id=created_event["id"],
        title=created_event["summary"],
        time=_format_datetime(start),
        calendar=calendar_id,
        attendees=attendees or [],
    )


@mcp.tool(
    description="Updates an existing calendar event by event ID. Only provided parameters will be updated - omit parameters to leave them unchanged. Pass empty strings to clear fields. Set normalize_timezone=True to fix UTC/timezone inconsistencies on recurring events."
)
def update_event(
    event_id: str,
    calendar_id: str = "primary",
    summary: str = "",
    start_datetime: str = "",
    end_datetime: str = "",
    description: str = "",
    location: str = "",
    normalize_timezone: bool = False,
) -> str:
    """Update an existing calendar event. Can normalize timezone inconsistencies."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    # Get current event for timezone normalization check
    if normalize_timezone:
        try:
            current_event = (
                service.events().get(calendarId=resolved_id, eventId=event_id).execute()
            )
        except Exception as e:
            return f"Error retrieving event for timezone check: {str(e)}"

    # Use the centralized timezone helper for any datetime updates
    effective_timezone = _get_effective_timezone(service, calendar_id=resolved_id)

    update_body = {}
    if summary:
        update_body["summary"] = summary
    if description:
        update_body["description"] = description
    if location:
        update_body["location"] = location

    if start_datetime:
        if "T" in start_datetime:
            update_body["start"] = {
                "dateTime": start_datetime,
                "timeZone": effective_timezone,
            }
        else:
            update_body["start"] = {"date": start_datetime}

    if end_datetime:
        if "T" in end_datetime:
            update_body["end"] = {
                "dateTime": end_datetime,
                "timeZone": effective_timezone,
            }
        else:
            update_body["end"] = {"date": end_datetime}

    # Handle timezone normalization if requested
    if normalize_timezone and _has_timezone_inconsistency(current_event):
        start = current_event.get("start", {})
        end = current_event.get("end", {})

        # Use the timezone from the event itself if available, otherwise fall back
        norm_tz = start.get("timeZone") or effective_timezone

        # Convert UTC times to local timezone format
        if "dateTime" in start:
            # Parse UTC time and convert to local timezone
            utc_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
            local_tz = zoneinfo.ZoneInfo(norm_tz)
            local_dt = utc_dt.astimezone(local_tz)
            local_time_str = local_dt.strftime("%Y-%m-%dT%H:%M:%S")

            update_body["start"] = {
                "dateTime": local_time_str,
                "timeZone": norm_tz,
            }
        if "dateTime" in end:
            # Parse UTC time and convert to local timezone
            utc_dt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
            local_tz = zoneinfo.ZoneInfo(norm_tz)
            local_dt = utc_dt.astimezone(local_tz)
            local_time_str = local_dt.strftime("%Y-%m-%dT%H:%M:%S")

            update_body["end"] = {
                "dateTime": local_time_str,
                "timeZone": norm_tz,
            }

    if not update_body:
        return "No updates specified. Nothing to do."

    updated_event = (
        service.events()
        .patch(calendarId=resolved_id, eventId=event_id, body=update_body)
        .execute()
    )

    result_msg = f"Event (ID: {updated_event['id']}) updated successfully. Fields changed: {', '.join(update_body.keys())}"
    if normalize_timezone and "start" in update_body:
        result_msg += " (timezone inconsistency normalized)"
    return result_msg


@mcp.tool(
    description="Deletes a calendar event permanently by event ID. WARNING: This action is irreversible. Returns confirmation of deletion."
)
def delete_event(event_id: str, calendar_id: str = "primary") -> str:
    """Delete a calendar event. Trusts the provided event_id."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    service.events().delete(calendarId=resolved_id, eventId=event_id).execute()
    return f"Event (ID: {event_id}) has been permanently deleted."


@mcp.tool(
    description="Lists all calendars accessible to the authenticated user with their IDs, access levels, and colors. Use this to discover calendar IDs before using other calendar tools."
)
def list_calendars() -> list[CalendarInfo]:
    """List all accessible calendars."""
    service = _get_calendar_service()

    calendar_list = service.calendarList().list().execute()
    calendars = calendar_list.get("items", [])

    return [
        CalendarInfo(
            id=cal["id"],
            summary=cal.get("summary", "Unknown"),
            accessRole=cal.get("accessRole", "unknown"),
            colorId=cal.get("colorId", "default"),
        )
        for cal in calendars
    ]


@mcp.tool(
    description="Finds available free time slots within a calendar for scheduling meetings. Defaults to next 7 days if no date range specified. Returns up to 20 slots, checking every 30 minutes. Set `work_hours_only=False` to include evenings/weekends."
)
def find_time(
    calendar_id: str = "primary",
    start_date: str = "",
    end_date: str = "",
    duration_minutes: int = 60,
    work_hours_only: bool = True,
) -> list[FreeTimeSlot]:
    """Find free time slots in a calendar."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    start_dt = datetime.now() if not start_date else datetime.fromisoformat(start_date)

    if not end_date:
        end_dt = start_dt + timedelta(days=7)
    else:
        end_dt = datetime.fromisoformat(end_date)

    freebusy_request = {
        "timeMin": _parse_datetime_to_utc(start_dt.isoformat()),
        "timeMax": _parse_datetime_to_utc(end_dt.isoformat()),
        "items": [{"id": resolved_id}],
    }

    freebusy_result = service.freebusy().query(body=freebusy_request).execute()
    busy_times = freebusy_result["calendars"][resolved_id].get("busy", [])

    slots = []
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

        is_free = True
        for busy in busy_times:
            busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
            busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))

            if busy_start.tzinfo:
                busy_start = busy_start.astimezone(timezone.utc).replace(tzinfo=None)
            if busy_end.tzinfo:
                busy_end = busy_end.astimezone(timezone.utc).replace(tzinfo=None)

            if current < busy_end and slot_end > busy_start:
                is_free = False
                break

        if is_free:
            slots.append((current, slot_end))

        current += timedelta(minutes=30)

    if not slots:
        return []

    # Convert to FreeTimeSlot objects
    free_slots = []
    for start_time, end_time in slots[:20]:  # Limit to first 20 slots
        free_slots.append(
            FreeTimeSlot(
                start=start_time.strftime("%Y-%m-%d %H:%M"),
                end=end_time.strftime("%Y-%m-%d %H:%M"),
                duration_minutes=duration_minutes,
            )
        )

    return free_slots


@mcp.tool(
    description="Searches for events across one or all calendars within a specified date range. Provide a `search_text` to find events with matching text in the title, description, or location. If no search text is given, it lists all events. Supports advanced client-side filtering by `search_fields` and `case_sensitive` options."
)
def search_events(
    search_text: str = "",
    calendar_id: str = "all",
    start_date: str = "",
    end_date: str = "",
    max_results: int = 100,
    search_fields: list[str] = [],
    case_sensitive: bool = False,
    match_all_terms: bool = True,
) -> list[CalendarEvent]:
    """Advanced hybrid search for calendar events."""
    service = _get_calendar_service()

    if not start_date:
        start_date = _parse_datetime_to_utc("")
    else:
        start_date = _parse_datetime_to_utc(start_date)

    if not end_date:
        days = 7 if not search_text else 365
        end_dt = datetime.now(timezone.utc) + timedelta(days=days)
        end_date = end_dt.isoformat().replace("+00:00", "Z")
    else:
        if "T" not in end_date:
            end_date = end_date + "T23:59:59Z"
        else:
            end_date = _parse_datetime_to_utc(end_date)

    events_list = []

    if calendar_id == "all":
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
        return []

    filtered_events.sort(
        key=lambda x: x.get("start", {}).get(
            "dateTime", x.get("start", {}).get("date", "")
        )
    )

    # Convert filtered events to CalendarEvent objects
    calendar_events = []
    for event in filtered_events:
        # Convert start/end to EventDateTime objects with automatic UTC conversion
        start_raw = event["start"]
        end_raw = event["end"]

        start_dt = EventDateTime(
            dateTime=_convert_utc_to_local_time(
                start_raw.get("dateTime", ""), start_raw.get("timeZone", "")
            ),
            date=start_raw.get("date", ""),
            timeZone=start_raw.get("timeZone", ""),
        )
        end_dt = EventDateTime(
            dateTime=_convert_utc_to_local_time(
                end_raw.get("dateTime", ""), end_raw.get("timeZone", "")
            ),
            date=end_raw.get("date", ""),
            timeZone=end_raw.get("timeZone", ""),
        )

        # Convert attendees
        attendees = []
        if event.get("attendees"):
            attendees = [
                Attendee(
                    email=att.get("email", "Unknown"),
                    responseStatus=att.get("responseStatus", "needsAction"),
                )
                for att in event["attendees"]
            ]

        calendar_event = CalendarEvent(
            id=event["id"],
            summary=event.get("summary", "No Title"),
            description=event.get("description", ""),
            location=event.get("location", ""),
            start=start_dt,
            end=end_dt,
            attendees=attendees,
            calendar_name=event.get("calendar_name", ""),
            created=event.get("created", ""),
            updated=event.get("updated", ""),
        )
        calendar_events.append(calendar_event)

    return calendar_events


@mcp.tool(
    description="Checks the status of the Google Calendar server and API connectivity. Returns version info and available functions."
)
def server_info() -> ServerInfo:
    """Get server status and Google Calendar API connection info."""
    service = _get_calendar_service()

    calendar_list = service.calendarList().list(maxResults=1).execute()

    return ServerInfo(
        name="Google Calendar Tool",
        version="1.9.4",
        status="active",
        capabilities=[
            "search_events",
            "get_event",
            "create_event",
            "update_event",
            "delete_event",
            "list_calendars",
            "find_time",
            "server_info",
        ],
        dependencies={
            "google_calendar_api": "active",
            "calendars_accessible": str(len(calendar_list.get("items", []))),
        },
    )
