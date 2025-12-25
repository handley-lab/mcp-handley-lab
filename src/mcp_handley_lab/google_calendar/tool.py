"""Google Calendar tool for calendar management via MCP."""

import logging
import pickle
import zoneinfo
from datetime import datetime, timedelta, timezone
from typing import Any

import dateparser
import pendulum
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.common.config import settings

logger = logging.getLogger(__name__)

# Application-level default timezone as final fallback
DEFAULT_TIMEZONE = "Europe/London"


class Attendee(BaseModel):
    """Calendar event attendee."""

    email: str = Field(..., description="The email address of the attendee.")
    responseStatus: str = Field(
        default="needsAction",
        description="The attendee's response status (e.g., 'accepted', 'declined', 'needsAction').",
    )


class EventDateTime(BaseModel):
    """Event date/time information."""

    dateTime: str = Field(
        default="",
        description="The timestamp for timed events in RFC3339 format (e.g., '2023-12-25T10:00:00Z').",
    )
    date: str = Field(
        default="",
        description="The date for all-day events in YYYY-MM-DD format (e.g., '2023-12-25').",
    )
    timeZone: str = Field(
        default="",
        description="The timezone identifier (e.g., 'America/New_York', 'Europe/London').",
    )


class CalendarEvent(BaseModel):
    """Calendar event details."""

    id: str = Field(..., description="The unique identifier for the event.")
    summary: str = Field(..., description="The title or summary of the event.")
    description: str = Field(
        default="", description="A detailed description or notes for the event."
    )
    location: str = Field(
        default="", description="The physical location or meeting link for the event."
    )
    start: EventDateTime = Field(
        ..., description="The start time of the event, including timezone."
    )
    end: EventDateTime = Field(
        ..., description="The end time of the event, including timezone."
    )
    attendees: list[Attendee] = Field(
        default_factory=list, description="A list of people attending the event."
    )
    calendar_name: str = Field(
        default="", description="The name of the calendar this event belongs to."
    )
    created: str = Field(
        default="", description="The creation time of the event as an ISO 8601 string."
    )
    updated: str = Field(
        default="",
        description="The last modification time of the event as an ISO 8601 string.",
    )


class CreatedEventResult(BaseModel):
    """Result of creating a calendar event."""

    status: str = Field(
        ...,
        description="The status of the event creation (e.g., 'confirmed', 'tentative').",
    )
    event_id: str = Field(
        ..., description="The unique identifier assigned to the newly created event."
    )
    title: str = Field(..., description="The title of the created event.")
    time: str = Field(
        ..., description="A human-readable summary of when the event occurs."
    )
    calendar: str = Field(
        ..., description="The name or ID of the calendar where the event was created."
    )
    attendees: list[str] = Field(
        ..., description="A list of attendee email addresses for the event."
    )


class UpdateEventResult(BaseModel):
    """Result of a successful event update or move operation."""

    event_id: str = Field(
        ..., description="The unique identifier of the updated event."
    )
    new_event_id: str = Field(
        default="",
        description="For move operations: the new event ID (may differ from original). Empty for updates.",
    )
    html_link: str = Field(
        ..., description="A direct link to the event in the Google Calendar UI."
    )
    updated_fields: list[str] = Field(
        ...,
        description="A list of the fields that were modified in this update operation.",
    )
    message: str = Field(..., description="A human-readable confirmation message.")


class CalendarInfo(BaseModel):
    """Calendar information."""

    id: str = Field(..., description="The unique identifier of the calendar.")
    summary: str = Field(..., description="The title or name of the calendar.")
    accessRole: str = Field(
        ...,
        description="The user's access level to the calendar (e.g., 'owner', 'reader', 'writer').",
    )
    colorId: str = Field(
        ..., description="The color identifier used to display the calendar."
    )


mcp = FastMCP("Google Calendar Tool")

# Google Calendar API scopes
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_calendar_service():
    """Get authenticated Google Calendar service."""
    creds = None
    token_file = settings.google_token_path
    credentials_file = settings.google_credentials_path

    try:
        with open(token_file, "rb") as f:
            creds = pickle.load(f)
    except FileNotFoundError:
        pass

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


def _get_calendar_timezone(service: Any, calendar_id: str) -> str:
    """Gets the timezone of a specific calendar, falling back to the default."""
    calendar = service.calendars().get(calendarId=calendar_id).execute()
    return calendar.get("timeZone", DEFAULT_TIMEZONE)


def _parse_user_datetime(dt_str: str, default_tz: str = None) -> pendulum.DateTime:
    """
    Parses a datetime string using advanced natural language processing.

    Args:
        dt_str: The input datetime string (can be natural language)
        default_tz: Default timezone for naive datetimes (fallback context)

    Returns:
        A timezone-aware pendulum.DateTime object
    """
    if not dt_str.strip():
        raise ValueError("Datetime string cannot be empty")

    # Try dateparser first (best for natural language)
    settings = {
        "PREFER_DATES_FROM": "future",  # Good for event creation
        "RETURN_AS_TIMEZONE_AWARE": True,
    }

    if default_tz:
        settings["TIMEZONE"] = default_tz

    parsed_dt = dateparser.parse(dt_str, settings=settings)

    if parsed_dt:
        # Convert to pendulum for better timezone handling
        try:
            return pendulum.instance(parsed_dt)
        except Exception:
            # Handle StaticTzInfo conversion issues
            return pendulum.parse(parsed_dt.isoformat())

    # Fallback to pendulum for structured formats
    try:
        parsed_dt = pendulum.parse(dt_str)
        # If no timezone and we have a default, apply it
        if parsed_dt.timezone is None and default_tz:
            parsed_dt = parsed_dt.in_timezone(default_tz)
        return parsed_dt
    except Exception:
        pass

    raise ValueError(f"Could not parse datetime string: '{dt_str}'")


def _prepare_event_datetime(dt_str: str, target_tz: str = None) -> dict[str, str]:
    """
    Parses a datetime string and prepares the correct Google Calendar API format.
    Supports natural language, flexible formats, and mixed timezones.

    Args:
        dt_str: The input datetime string (supports natural language)
        target_tz: Target timezone (if None, preserves input timezone)

    Returns:
        A dictionary like {'dateTime': 'YYYY-MM-DDTHH:MM:SS', 'timeZone': '...'} for
        timed events, or {'date': 'YYYY-MM-DD'} for all-day events.
    """
    if not dt_str.strip():
        raise ValueError("Datetime string cannot be empty")

    # Check for date-only patterns (all-day events)
    # Only treat as date-only if it's clearly a date format without time
    looks_like_date_only = (
        len(dt_str.strip().split()) == 1  # Single token
        and "-" in dt_str  # Has date separators
        and dt_str.count("-") == 2  # YYYY-MM-DD format
        and not any(char.isalpha() for char in dt_str)  # No letters
        and "T" not in dt_str
        and ":" not in dt_str  # No time components
    )

    if looks_like_date_only:
        try:
            # Use dateparser for flexible date parsing
            parsed_dt = dateparser.parse(
                dt_str, settings={"PREFER_DATES_FROM": "future"}
            )
            if parsed_dt:
                return {"date": parsed_dt.strftime("%Y-%m-%d")}
        except Exception:
            pass

        # Fallback to pendulum for date parsing
        try:
            parsed_dt = pendulum.parse(dt_str)
            return {"date": parsed_dt.format("YYYY-MM-DD")}
        except Exception as e:
            raise ValueError(f"Could not parse date string: {dt_str}") from e

    # Handle timed events with advanced parsing
    try:
        parsed_dt = _parse_user_datetime(dt_str, target_tz)
    except Exception as e:
        raise ValueError(f"Could not parse datetime string: {dt_str}") from e

    # Convert to target timezone if specified, otherwise preserve input timezone
    if target_tz and target_tz != str(parsed_dt.timezone):
        final_dt = parsed_dt.in_timezone(target_tz)
    else:
        final_dt = parsed_dt

    # Return the format Google Calendar prefers
    # Handle timezone string conversion properly
    timezone_str = str(final_dt.timezone)
    if timezone_str.startswith("FixedTimezone("):
        # For fixed offsets, convert to standard format
        timezone_str = final_dt.timezone.name

    return {
        "dateTime": final_dt.isoformat(),
        "timeZone": timezone_str,
    }


def _normalize_datetime_for_output(dt_info: dict) -> dict:
    """Convert timezone-inconsistent datetime to unambiguous format for LLMs.

    Converts formats like:
    {"dateTime": "14:30:00Z", "timeZone": "Europe/London"}
    to:
    {"dateTime": "15:30:00+01:00", "timeZone": "Europe/London"}

    This eliminates LLM confusion between GMT/BST interpretation.
    """
    if not dt_info.get("dateTime") or not dt_info.get("timeZone"):
        return dt_info

    dt_str = dt_info["dateTime"]
    tz_str = dt_info["timeZone"]

    # Only process if we have a Z suffix with a specific timezone
    if not dt_str.endswith("Z") or tz_str.lower() == "utc":
        return dt_info

    # Parse UTC datetime
    utc_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

    # Convert to target timezone
    target_tz = zoneinfo.ZoneInfo(tz_str)
    local_dt = utc_dt.astimezone(target_tz)

    # Return with explicit offset format
    return {"dateTime": local_dt.isoformat(), "timeZone": tz_str}


def _build_event_model(event_data: dict) -> CalendarEvent:
    """Convert raw Google Calendar API event dict to CalendarEvent model."""
    start_raw = event_data.get("start", {})
    end_raw = event_data.get("end", {})

    # Normalize datetime formats for unambiguous LLM interpretation
    start_normalized = _normalize_datetime_for_output(start_raw)
    end_normalized = _normalize_datetime_for_output(end_raw)

    start_dt = EventDateTime(**start_normalized)
    end_dt = EventDateTime(**end_normalized)

    attendees = [
        Attendee(
            email=att.get("email", "Unknown"),
            responseStatus=att.get("responseStatus", "needsAction"),
        )
        for att in event_data.get("attendees", [])
    ]

    return CalendarEvent(
        id=event_data["id"],
        summary=event_data.get("summary", "No Title"),
        description=event_data.get("description", ""),
        location=event_data.get("location", ""),
        start=start_dt,
        end=end_dt,
        attendees=attendees,
        calendar_name=event_data.get("calendar_name", ""),
        created=event_data.get("created", ""),
        updated=event_data.get("updated", ""),
    )


def _get_normalization_patch(event_data: dict) -> dict:
    """If event has timezone inconsistency, return patch to fix it."""
    if not _has_timezone_inconsistency(event_data):
        return {}

    start = event_data["start"]
    end = event_data["end"]
    target_tz = zoneinfo.ZoneInfo(start["timeZone"])

    patch = {}

    # Normalize start time
    utc_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
    local_dt = utc_dt.astimezone(target_tz)
    patch["start"] = {
        "dateTime": local_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "timeZone": start["timeZone"],
    }

    # Normalize end time
    utc_dt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
    local_dt = utc_dt.astimezone(target_tz)
    patch["end"] = {
        "dateTime": local_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "timeZone": end["timeZone"],
    }

    return patch


def _is_all_day_event(event_data: dict) -> bool:
    """Check if an event is an all-day event (uses date instead of dateTime)."""
    start = event_data.get("start", {})
    return "date" in start and "dateTime" not in start


def _would_be_timed_event(dt_str: str | None) -> bool:
    """Check if a datetime string would result in a timed event (not all-day).

    Uses the actual _prepare_event_datetime() logic to determine whether the input
    would create a timed event (has 'dateTime') vs all-day event (has 'date').

    Raises:
        ValueError: If the datetime string cannot be parsed (surfaced from _prepare_event_datetime)
    """
    if not dt_str or not dt_str.strip():
        return False

    # Use the actual formatter to determine result type
    # Let parsing errors propagate so they're surfaced properly
    result = _prepare_event_datetime(dt_str.strip())
    # If result has 'dateTime', it's a timed event; if 'date', it's all-day
    return "dateTime" in result


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
    has_specific_timezone = bool(timezone and timezone.lower() != "utc")

    return has_utc_suffix and has_specific_timezone


def _parse_datetime_to_utc(dt_str: str, default_tz: str = DEFAULT_TIMEZONE) -> str:
    """
    Parse datetime string and convert to UTC with proper timezone handling.

    Uses pendulum for DST-safe localization of naive datetimes.

    Handles:
    - ISO 8601 with timezone: "2024-06-30T14:00:00+01:00" -> "2024-06-30T13:00:00Z"
    - ISO 8601 with Z: "2024-06-30T14:00:00Z" -> "2024-06-30T14:00:00Z"
    - ISO 8601 naive: "2024-06-30T14:00:00" -> interpreted in default_tz, then converted to UTC
    - Date only: "2024-06-30" -> start of day in default_tz, converted to UTC

    For ambiguous DST times (e.g., "2024-10-27T01:30:00" in Europe/London which occurs twice),
    pendulum uses the later occurrence (post-transition). For non-existent times (spring forward),
    pendulum adjusts to the nearest valid time.

    Args:
        dt_str: The datetime string to parse
        default_tz: IANA timezone for interpreting naive datetimes (default: Europe/London)
    """
    if not dt_str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Date only: interpret as start of day in default timezone using pendulum for DST safety
    if "T" not in dt_str:
        try:
            # Use pendulum for DST-safe localization
            local_dt = pendulum.parse(dt_str, tz=default_tz)
            utc_dt = local_dt.in_tz("UTC")
            return utc_dt.format("YYYY-MM-DDTHH:mm:ss") + "Z"
        except Exception:
            # Fallback if pendulum parsing fails
            return dt_str + "T00:00:00Z"

    # Handle UTC suffix explicitly
    if dt_str.endswith("Z"):
        return dt_str

    # Parse the datetime and check if it has tzinfo
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is not None:
            # Has explicit timezone - convert to UTC
            utc_dt = dt.astimezone(timezone.utc)
            return utc_dt.isoformat().replace("+00:00", "Z")
        else:
            # Naive datetime - use pendulum for DST-safe localization
            local_dt = pendulum.instance(dt, tz=default_tz)
            utc_dt = local_dt.in_tz("UTC")
            return utc_dt.format("YYYY-MM-DDTHH:mm:ss") + "Z"
    except Exception:
        # Fallback if parsing fails - assume UTC
        logger.warning(
            "Failed to parse datetime '%s' in timezone '%s', assuming UTC",
            dt_str,
            default_tz,
        )
        return dt_str + "Z"


def _client_side_filter(
    events: list[dict[str, Any]],
    search_text: str = "",
    search_fields: list[str] | None = None,
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


# =============================================================================
# MCP Resource: Calendars
# =============================================================================


@mcp.resource("calendar://list")
def calendar_list() -> list[CalendarInfo]:
    """All accessible calendars with IDs, names, and access levels."""
    service = _get_calendar_service()
    calendar_list_response = service.calendarList().list().execute()
    return [
        CalendarInfo(
            id=cal["id"],
            summary=cal.get("summary", "Unknown"),
            accessRole=cal.get("accessRole", "unknown"),
            colorId=cal.get("colorId", "default"),
        )
        for cal in calendar_list_response.get("items", [])
    ]


# =============================================================================
# MCP Tools: CRUD Operations
# =============================================================================


@mcp.tool(
    description="Read calendar events. Get single event by ID (returns singleton list), or search/list events in date range. Use calendar://list resource to discover available calendar IDs."
)
def read(
    event_id: str | None = Field(
        None,
        description="If provided, get single event by ID (returns singleton list). Cannot use with calendar_id='all'.",
    ),
    calendar_id: str = Field(
        "primary",
        description="ID or name of the calendar. Use 'all' to search all calendars (only for search, not get-by-id).",
    ),
    search_text: str = Field(
        "",
        description="Text to search for. If empty, lists all events in the date range.",
    ),
    start_date: str = Field(
        "",
        description="Start date (YYYY-MM-DD) for search. Defaults to today.",
    ),
    end_date: str = Field(
        "",
        description="End date (YYYY-MM-DD) for search. Defaults to 7 days from start.",
    ),
    max_results: int = Field(100, description="Maximum events to return per calendar."),
    search_fields: list[str] | None = Field(
        None,
        description="Client-side filter fields (e.g., 'summary', 'description'). None=API search only, []=search all fields.",
    ),
    case_sensitive: bool = Field(
        False,
        description="If True, search is case-sensitive.",
    ),
    match_all_terms: bool = Field(
        True,
        description="If True (AND), all words must match. If False (OR), any can match.",
    ),
) -> list[CalendarEvent]:
    """Read calendar events - either get by ID or search."""
    service = _get_calendar_service()

    # Get single event by ID
    if event_id:
        if calendar_id == "all":
            raise ValueError("Cannot use calendar_id='all' when fetching by event_id")
        resolved_id = _resolve_calendar_id(calendar_id, service)
        event = service.events().get(calendarId=resolved_id, eventId=event_id).execute()

        if _has_timezone_inconsistency(event):
            logger.warning(
                "Timezone inconsistency detected in event '%s'. "
                "To fix: update(event_id='%s', calendar_id='%s', normalize_timezone=True)",
                event.get("summary", "Unknown"),
                event_id,
                calendar_id,
            )

        return [_build_event_model(event)]

    # Search/list events
    if not start_date:
        start_date = _parse_datetime_to_utc("")
    else:
        start_date = _parse_datetime_to_utc(start_date)

    if not end_date:
        days = 7 if not search_text else 365
        # Compute end_date from start_date, not from now
        start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end_dt = start_dt + timedelta(days=days)
        end_date = end_dt.isoformat().replace("+00:00", "Z")
    else:
        if "T" not in end_date:
            end_date = end_date + "T23:59:59Z"
        else:
            end_date = _parse_datetime_to_utc(end_date)

    events_list = []

    if calendar_id == "all":
        calendar_list_response = service.calendarList().list().execute()

        for calendar in calendar_list_response.get("items", []):
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

    # Client-side filtering: None=skip, []=default fields, ['field1',...]=specific fields
    if search_fields is not None or case_sensitive or not match_all_terms:
        filtered_events = _client_side_filter(
            events_list,
            search_text=search_text,
            search_fields=search_fields
            if search_fields
            else None,  # [] -> use defaults
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

    return [_build_event_model(event) for event in filtered_events]


@mcp.tool(
    description="Create a new calendar event. Supports natural language datetimes (e.g., 'tomorrow at 2pm') and mixed timezones."
)
def create(
    summary: str = Field(..., description="The title or summary for the new event."),
    start_datetime: str = Field(
        ...,
        description="The start time of the event. Supports natural language (e.g., 'tomorrow at 2pm').",
    ),
    end_datetime: str = Field(
        ...,
        description="The end time of the event. Supports natural language (e.g., 'in 3 hours').",
    ),
    description: str = Field(
        "", description="A detailed description or notes for the event."
    ),
    location: str = Field(
        "", description="The physical location or meeting link for the event."
    ),
    calendar_id: str = Field(
        ...,
        description="The ID or name of the calendar to add the event to. Use calendar://list resource to discover options. Required parameter - no default.",
    ),
    start_timezone: str = Field(
        "",
        description="Explicit IANA timezone for the start time (e.g., 'America/Los_Angeles'). Overrides calendar's default.",
    ),
    end_timezone: str = Field(
        "",
        description="Explicit IANA timezone for the end time. Essential for events spanning timezones, like flights.",
    ),
    attendees: list[str] = Field(
        default_factory=list,
        description="A list of attendee email addresses to invite to the event.",
    ),
) -> CreatedEventResult:
    """Create a new calendar event with intelligent datetime parsing and flexible timezone handling.

    Examples:
    - Natural language: start_datetime="tomorrow at 2pm", end_datetime="tomorrow at 3pm"
    - Mixed timezones: start_datetime="10:00am", start_timezone="America/Los_Angeles",
                      end_datetime="6:30pm", end_timezone="America/New_York"
    - ISO format: start_datetime="2024-07-15T14:00:00-08:00" (preserves timezone)
    - Relative time: start_datetime="in 2 hours", end_datetime="in 3 hours"
    """
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    # Get calendar's default timezone as fallback context
    calendar_tz = _get_calendar_timezone(service, resolved_id)

    # Prepare start datetime with smart timezone handling
    if start_timezone:
        # Use explicit timezone for start time
        start_body = _prepare_event_datetime(start_datetime, start_timezone)
    else:
        # Use calendar timezone as context for naive datetimes
        start_body = _prepare_event_datetime(start_datetime, calendar_tz)

    # Prepare end datetime with smart timezone handling
    if end_timezone:
        # Use explicit timezone for end time
        end_body = _prepare_event_datetime(end_datetime, end_timezone)
    else:
        # Use calendar timezone as context for naive datetimes
        end_body = _prepare_event_datetime(end_datetime, calendar_tz)

    event_body = {
        "summary": summary,
        "description": description or "",
        "location": location or "",
        "start": start_body,
        "end": end_body,
    }

    if attendees:
        event_body["attendees"] = [{"email": email} for email in attendees]

    created_event = (
        service.events().insert(calendarId=resolved_id, body=event_body).execute()
    )

    start = created_event.get("start", {})
    time_str = start.get("dateTime", start.get("date", "N/A"))
    tz_str = start.get("timeZone")
    display_time = f"{time_str} ({tz_str})" if tz_str else time_str

    return CreatedEventResult(
        status="Event created successfully!",
        event_id=created_event["id"],
        title=created_event["summary"],
        time=display_time,
        calendar=calendar_id,
        attendees=[att.get("email") for att in created_event.get("attendees", [])],
    )


@mcp.tool(
    description="Update or move a calendar event. If destination_calendar_id provided, moves event (may change event ID). Otherwise updates event properties."
)
def update(
    event_id: str = Field(
        ..., description="The unique identifier of the event to update or move."
    ),
    calendar_id: str = Field(
        "primary",
        description="The calendar where the event is located. Defaults to primary.",
    ),
    destination_calendar_id: str | None = Field(
        None,
        description="If provided, move event to this calendar instead of updating. Cannot combine with update fields.",
    ),
    summary: str | None = Field(
        None, description="New title. None=no change, ''=clear field."
    ),
    start_datetime: str | None = Field(
        None,
        description="New start time. Supports natural language. None=no change.",
    ),
    end_datetime: str | None = Field(
        None,
        description="New end time. Supports natural language. None=no change.",
    ),
    description: str | None = Field(
        None, description="New description. None=no change, ''=clear field."
    ),
    location: str | None = Field(
        None, description="New location. None=no change, ''=clear field."
    ),
    start_timezone: str = Field(
        "",
        description="New IANA timezone for start. If empty, preserves existing.",
    ),
    end_timezone: str = Field(
        "",
        description="New IANA timezone for end. If empty, preserves existing.",
    ),
    normalize_timezone: bool = Field(
        False,
        description="Fix timezone inconsistencies (UTC time with non-UTC label).",
    ),
) -> UpdateEventResult:
    """Update or move an event. Move and update are mutually exclusive."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    # Handle move operation
    if destination_calendar_id:
        # Validate mutual exclusivity - include ALL update-related fields
        # Check str|None fields for not-None, check str fields for non-empty
        has_update_fields = any(
            f is not None
            for f in [summary, start_datetime, end_datetime, description, location]
        ) or any(f.strip() for f in [start_timezone, end_timezone])
        if has_update_fields:
            raise ValueError(
                "Cannot combine move (destination_calendar_id) with update fields. "
                "Move first, then update in a separate call."
            )
        if normalize_timezone:
            raise ValueError(
                "Cannot combine move (destination_calendar_id) with normalize_timezone. "
                "Move first, then normalize in a separate call."
            )

        dest_resolved_id = _resolve_calendar_id(destination_calendar_id, service)
        moved_event = (
            service.events()
            .move(
                calendarId=resolved_id,
                eventId=event_id,
                destination=dest_resolved_id,
            )
            .execute()
        )

        return UpdateEventResult(
            event_id=event_id,
            new_event_id=moved_event["id"],
            html_link=moved_event.get("htmlLink", ""),
            updated_fields=["moved"],
            message=f"Event moved from '{calendar_id}' to '{destination_calendar_id}'. New ID: {moved_event['id']}",
        )

    # Handle update operation
    update_body = {}
    updated_fields = []

    current_event = None
    if normalize_timezone or start_datetime or end_datetime:
        current_event = (
            service.events().get(calendarId=resolved_id, eventId=event_id).execute()
        )

    if normalize_timezone and current_event:
        normalization_patch = _get_normalization_patch(current_event)
        update_body.update(normalization_patch)
        if normalization_patch:
            updated_fields.append("timezone_normalization")

    if summary is not None:
        update_body["summary"] = summary
        updated_fields.append("summary")
    if description is not None:
        update_body["description"] = description
        updated_fields.append("description")
    if location is not None:
        update_body["location"] = location
        updated_fields.append("location")

    if start_datetime or end_datetime:
        calendar_tz = _get_calendar_timezone(service, resolved_id)
        existing_start_tz = (
            current_event.get("start", {}).get("timeZone") or calendar_tz
        )
        existing_end_tz = current_event.get("end", {}).get("timeZone") or calendar_tz

        # Prevent silent conversion of all-day events to timed events
        is_all_day = _is_all_day_event(current_event)
        if is_all_day:
            would_convert_start = start_datetime and _would_be_timed_event(
                start_datetime
            )
            would_convert_end = end_datetime and _would_be_timed_event(end_datetime)
            if would_convert_start or would_convert_end:
                raise ValueError(
                    "Cannot convert all-day event to timed event. "
                    "Use date-only format (YYYY-MM-DD) to update all-day events, "
                    "or delete and recreate as a timed event."
                )

        if start_datetime:
            target_tz = start_timezone or existing_start_tz
            update_body["start"] = _prepare_event_datetime(start_datetime, target_tz)
            updated_fields.append("start_datetime")

        if end_datetime:
            target_tz = end_timezone or existing_end_tz
            update_body["end"] = _prepare_event_datetime(end_datetime, target_tz)
            updated_fields.append("end_datetime")

    if not update_body:
        return UpdateEventResult(
            event_id=event_id,
            html_link="",
            updated_fields=[],
            message="No updates specified. Nothing to do.",
        )

    updated_event = (
        service.events()
        .patch(calendarId=resolved_id, eventId=event_id, body=update_body)
        .execute()
    )

    result_msg = f"Event (ID: {updated_event['id']}) updated successfully."
    if updated_fields:
        result_msg += f" Modified fields: {', '.join(updated_fields)}"
    if normalize_timezone and ("start" in update_body or "end" in update_body):
        result_msg += " (timezone inconsistency normalized)"

    return UpdateEventResult(
        event_id=updated_event["id"],
        html_link=updated_event.get("htmlLink", ""),
        updated_fields=updated_fields,
        message=result_msg,
    )


@mcp.tool(description="Delete a calendar event permanently. WARNING: Irreversible.")
def delete(
    event_id: str = Field(
        ..., description="The unique identifier of the event to delete."
    ),
    calendar_id: str = Field(
        "primary",
        description="The calendar where the event is located. Defaults to primary.",
    ),
) -> str:
    """Delete a calendar event permanently."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    service.events().delete(calendarId=resolved_id, eventId=event_id).execute()
    return f"Event (ID: {event_id}) has been permanently deleted."
