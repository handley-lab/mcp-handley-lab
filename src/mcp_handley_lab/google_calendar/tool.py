"""Google Calendar tool for calendar management via MCP."""

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
from mcp_handley_lab.shared.models import ServerInfo

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
    """Result of a successful event update operation."""

    event_id: str = Field(
        ..., description="The unique identifier of the updated event."
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


class FreeTimeSlot(BaseModel):
    """Available time slot."""

    start: str = Field(
        ..., description="The start time of the free slot in ISO 8601 format."
    )
    end: str = Field(
        ..., description="The end time of the free slot in ISO 8601 format."
    )
    duration_minutes: int = Field(
        ..., description="The duration of the free time slot in minutes."
    )


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


def _get_calendar_timezone(service: Any, calendar_id: str) -> str:
    """Gets the timezone of a specific calendar, falling back to the default."""
    try:
        calendar = service.calendars().get(calendarId=calendar_id).execute()
        return calendar.get("timeZone", DEFAULT_TIMEZONE)
    except Exception:
        # Fallback if the calendar isn't found or another error occurs
        return DEFAULT_TIMEZONE


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

    try:
        # Parse UTC datetime
        utc_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

        # Convert to target timezone
        target_tz = zoneinfo.ZoneInfo(tz_str)
        local_dt = utc_dt.astimezone(target_tz)

        # Return with explicit offset format
        return {"dateTime": local_dt.isoformat(), "timeZone": tz_str}
    except Exception:
        # If conversion fails, return original
        return dt_info


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


@mcp.tool(
    description="Retrieves detailed information about a specific calendar event by its ID. Returns comprehensive event details including attendees, location, and timestamps. Automatically detects timezone inconsistencies."
)
def get_event(
    event_id: str = Field(
        ..., description="The unique identifier of the event to retrieve."
    ),
    calendar_id: str = Field(
        "primary",
        description="The ID or name of the calendar containing the event. Use 'list_calendars' to see available options. Defaults to the user's primary calendar.",
    ),
) -> CalendarEvent:
    """Get detailed information about a specific event."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)
    event = service.events().get(calendarId=resolved_id, eventId=event_id).execute()

    if _has_timezone_inconsistency(event):
        print(
            f"⚠️  Timezone inconsistency detected in event '{event.get('summary', 'Unknown')}'. "
            f"To fix: update_event(event_id='{event_id}', calendar_id='{calendar_id}', normalize_timezone=True)"
        )

    return _build_event_model(event)


@mcp.tool(
    description="Creates a new event. Supports natural language datetimes (e.g., 'tomorrow at 2pm') and mixed timezones."
)
def create_event(
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
        description="The ID or name of the calendar to add the event to. Use 'list_calendars' to see available options. Required parameter - no default.",
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
    description="Updates an event. Supports natural language rescheduling and can fix timezone inconsistencies."
)
def update_event(
    event_id: str = Field(
        ..., description="The unique identifier of the event to update."
    ),
    calendar_id: str = Field(
        "primary",
        description="The calendar where the event is located. Use 'list_calendars' to see available options. Defaults to the primary calendar.",
    ),
    summary: str = Field(
        "", description="New title for the event. If empty, the summary is not changed."
    ),
    start_datetime: str = Field(
        "",
        description="New start time for the event. Supports natural language. If empty, not changed.",
    ),
    end_datetime: str = Field(
        "",
        description="New end time for the event. Supports natural language. If empty, not changed.",
    ),
    description: str = Field(
        "", description="New description for the event. If empty, not changed."
    ),
    location: str = Field(
        "", description="New location for the event. If empty, not changed."
    ),
    start_timezone: str = Field(
        "",
        description="New IANA timezone for the start time. If empty, preserves existing timezone.",
    ),
    end_timezone: str = Field(
        "",
        description="New IANA timezone for the end time. If empty, preserves existing timezone.",
    ),
    normalize_timezone: bool = Field(
        False,
        description="Set to True to fix timezone inconsistencies (e.g., UTC time with a non-UTC timezone label) on the event.",
    ),
) -> UpdateEventResult:
    """Update an existing event, with automatic timezone handling for new times.

    Examples:
    - Natural language: start_datetime="tomorrow at 3pm", end_datetime="tomorrow at 4pm"
    - Reschedule with timezone: start_datetime="10am", start_timezone="Europe/London"
    - Relative time: start_datetime="in 1 hour" (keeps existing end time)
    - Mixed timezones: start_timezone="America/Los_Angeles", end_timezone="America/New_York"
    """
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)
    update_body = {}
    updated_fields = []

    current_event = None
    if normalize_timezone or start_datetime.strip() or end_datetime.strip():
        current_event = (
            service.events().get(calendarId=resolved_id, eventId=event_id).execute()
        )

    if normalize_timezone and current_event:
        normalization_patch = _get_normalization_patch(current_event)
        update_body.update(normalization_patch)
        if normalization_patch:
            updated_fields.append("timezone_normalization")

    # Build update from provided arguments
    if summary.strip():
        update_body["summary"] = summary
        updated_fields.append("summary")
    if description is not None:  # Allow clearing the description
        update_body["description"] = description
        updated_fields.append("description")
    if location is not None:  # Allow clearing the location
        update_body["location"] = location
        updated_fields.append("location")

    # If start or end times are being updated, use intelligent preparation logic
    if start_datetime.strip() or end_datetime.strip():
        # Get fallback timezone context
        calendar_tz = _get_calendar_timezone(service, resolved_id)
        existing_start_tz = (
            current_event.get("start", {}).get("timeZone") or calendar_tz
        )
        existing_end_tz = current_event.get("end", {}).get("timeZone") or calendar_tz

        if start_datetime.strip():
            # Use explicit timezone or preserve existing event's start timezone
            target_tz = start_timezone or existing_start_tz
            update_body["start"] = _prepare_event_datetime(start_datetime, target_tz)
            updated_fields.append("start_datetime")

        if end_datetime.strip():
            # Use explicit timezone or preserve existing event's end timezone
            target_tz = end_timezone or existing_end_tz
            update_body["end"] = _prepare_event_datetime(end_datetime, target_tz)
            updated_fields.append("end_datetime")

    if not update_body:
        # Return a minimal result for no updates case
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


@mcp.tool(
    description="Deletes a calendar event permanently by event ID. WARNING: This action is irreversible. Returns confirmation of deletion."
)
def delete_event(
    event_id: str = Field(
        ..., description="The unique identifier of the event to be permanently deleted."
    ),
    calendar_id: str = Field(
        "primary",
        description="The calendar where the event is located. Use 'list_calendars' to see available options. Defaults to the primary calendar.",
    ),
) -> str:
    """Delete a calendar event. Trusts the provided event_id."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    service.events().delete(calendarId=resolved_id, eventId=event_id).execute()
    return f"Event (ID: {event_id}) has been permanently deleted."


@mcp.tool(
    description="Moves a calendar event from one calendar to another. This is the proper way to transfer events between calendars, preserving event metadata and attendee information."
)
def move_event(
    event_id: str = Field(
        ..., description="The unique identifier of the event to move."
    ),
    source_calendar_id: str = Field(
        "primary",
        description="The ID or name of the calendar the event is currently in. Use 'list_calendars' to see available options. Defaults to primary.",
    ),
    destination_calendar_id: str = Field(
        "primary",
        description="The ID or name of the calendar to move the event to. Use 'list_calendars' to see available options. Defaults to primary.",
    ),
) -> str:
    """Move an event from one calendar to another using the Google Calendar API move endpoint."""
    service = _get_calendar_service()
    source_resolved_id = _resolve_calendar_id(source_calendar_id, service)
    dest_resolved_id = _resolve_calendar_id(destination_calendar_id, service)

    # Use the Google Calendar API's move endpoint
    moved_event = (
        service.events()
        .move(
            calendarId=source_resolved_id,
            eventId=event_id,
            destination=dest_resolved_id,
        )
        .execute()
    )

    return f"Event (ID: {moved_event['id']}) moved successfully from '{source_calendar_id}' to '{destination_calendar_id}'."


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
    calendar_id: str = Field(
        "primary",
        description="The ID or name of the calendar to search for free time. Use 'list_calendars' to see available options. Defaults to primary.",
    ),
    start_date: str = Field(
        "", description="The start date (YYYY-MM-DD) for the search. Defaults to now."
    ),
    end_date: str = Field(
        "",
        description="The end date (YYYY-MM-DD) for the search. Defaults to 7 days from the start date.",
    ),
    duration_minutes: int = Field(
        60, description="The desired duration of the free time slot in minutes."
    ),
    work_hours_only: bool = Field(
        True, description="If True, only searches for slots between 9 AM and 5 PM."
    ),
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
    description="Searches for events in a date range. Filter by text, specific fields ('search_fields'), and case sensitivity."
)
def search_events(
    search_text: str = Field(
        "",
        description="Text to search for. If empty, lists all events in the date range. Can be a simple string or use Google Calendar's advanced search operators.",
    ),
    calendar_id: str = Field(
        "all",
        description="ID or name of the calendar to search. Use 'all' to search every accessible calendar, or use 'list_calendars' to see available options.",
    ),
    start_date: str = Field(
        "",
        description="The start date (YYYY-MM-DD) for the search range. Defaults to today.",
    ),
    end_date: str = Field(
        "",
        description="The end date (YYYY-MM-DD) for the search range. Defaults to 7 days from start (or 365 if search_text is provided).",
    ),
    max_results: int = Field(
        100, description="The maximum number of events to return per calendar."
    ),
    search_fields: list[str] = Field(
        default_factory=list,
        description="Client-side filter: specific fields to search within (e.g., 'summary', 'description', 'attendees'). If empty, defaults to API search.",
    ),
    case_sensitive: bool = Field(
        False,
        description="Client-side filter: If True, the search_text match will be case-sensitive.",
    ),
    match_all_terms: bool = Field(
        True,
        description="Client-side filter: If True (AND logic), all words in search_text must match. If False (OR logic), any can match.",
    ),
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
    return [_build_event_model(event) for event in filtered_events]


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
            "move_event",
            "list_calendars",
            "find_time",
            "server_info",
        ],
        dependencies={
            "google_calendar_api": "active",
            "calendars_accessible": str(len(calendar_list.get("items", []))),
        },
    )
