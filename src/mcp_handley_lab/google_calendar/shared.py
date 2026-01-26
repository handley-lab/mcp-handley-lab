"""Core Google Calendar functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

from datetime import datetime, timedelta
from typing import Any

from mcp_handley_lab.google_calendar.tool import (
    CalendarEvent,
    CalendarInfo,
    CreatedEventResult,
    UpdateEventResult,
    _build_event_model,
    _client_side_filter,
    _get_calendar_service,
    _get_calendar_timezone,
    _get_normalization_patch,
    _has_timezone_inconsistency,
    _is_all_day_event,
    _parse_datetime_to_utc,
    _prepare_event_datetime,
    _resolve_calendar_id,
    _would_be_timed_event,
    logger,
)


def read(
    event_id: str | None = None,
    calendar_id: str = "primary",
    search_text: str = "",
    start_date: str = "",
    end_date: str = "",
    max_results: int = 100,
    search_fields: list[str] | None = None,
    case_sensitive: bool = False,
    match_all_terms: bool = True,
) -> list[CalendarEvent]:
    """Read calendar events - either get by ID or search.

    Args:
        event_id: If provided, get single event by ID (returns singleton list).
            Cannot use with calendar_id='all'.
        calendar_id: ID or name of the calendar. Use 'all' to search all calendars.
        search_text: Text to search for. If empty, lists all events in date range.
        start_date: Start date (YYYY-MM-DD) for search. Defaults to today.
        end_date: End date (YYYY-MM-DD) for search. Defaults to 7 days from start.
        max_results: Maximum events to return per calendar.
        search_fields: Client-side filter fields (e.g., 'summary', 'description').
            None=API search only, []=search all fields.
        case_sensitive: If True, search is case-sensitive.
        match_all_terms: If True (AND), all words must match. If False (OR), any can match.

    Returns:
        List of CalendarEvent objects.
    """
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
        start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end_dt = start_dt + timedelta(days=days)
        end_date = end_dt.isoformat().replace("+00:00", "Z")
    else:
        if "T" not in end_date:
            end_date = end_date + "T23:59:59Z"
        else:
            end_date = _parse_datetime_to_utc(end_date)

    events_list: list[dict[str, Any]] = []

    if calendar_id == "all":
        calendar_list_response = service.calendarList().list().execute()

        for calendar in calendar_list_response.get("items", []):
            cal_id = calendar["id"]

            params: dict[str, Any] = {
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

    # Client-side filtering
    if search_fields is not None or case_sensitive or not match_all_terms:
        filtered_events = _client_side_filter(
            events_list,
            search_text=search_text,
            search_fields=search_fields if search_fields else None,
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


def create(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: str = "",
    location: str = "",
    calendar_id: str = "primary",
    start_timezone: str = "",
    end_timezone: str = "",
    attendees: list[str] | None = None,
) -> CreatedEventResult:
    """Create a new calendar event with intelligent datetime parsing.

    Args:
        summary: The title or summary for the new event.
        start_datetime: The start time. Supports natural language (e.g., 'tomorrow at 2pm').
        end_datetime: The end time. Supports natural language (e.g., 'in 3 hours').
        description: A detailed description or notes for the event.
        location: The physical location or meeting link for the event.
        calendar_id: The ID or name of the calendar to add the event to.
        start_timezone: Explicit IANA timezone for the start time (e.g., 'America/Los_Angeles').
        end_timezone: Explicit IANA timezone for the end time.
        attendees: A list of attendee email addresses to invite.

    Returns:
        CreatedEventResult with event details.

    Examples:
        - Natural language: create("Meeting", "tomorrow at 2pm", "tomorrow at 3pm")
        - Mixed timezones: create("Flight", "10:00am", "6:30pm",
            start_timezone="America/Los_Angeles", end_timezone="America/New_York")
    """
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    # Get calendar's default timezone as fallback context
    calendar_tz = _get_calendar_timezone(service, resolved_id)

    # Prepare start datetime with smart timezone handling
    if start_timezone:
        start_body = _prepare_event_datetime(start_datetime, start_timezone)
    else:
        start_body = _prepare_event_datetime(start_datetime, calendar_tz)

    # Prepare end datetime with smart timezone handling
    if end_timezone:
        end_body = _prepare_event_datetime(end_datetime, end_timezone)
    else:
        end_body = _prepare_event_datetime(end_datetime, calendar_tz)

    event_body: dict[str, Any] = {
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


def update(
    event_id: str,
    calendar_id: str = "primary",
    destination_calendar_id: str | None = None,
    summary: str | None = None,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    description: str | None = None,
    location: str | None = None,
    start_timezone: str = "",
    end_timezone: str = "",
    normalize_timezone: bool = False,
) -> UpdateEventResult:
    """Update or move a calendar event.

    Args:
        event_id: The unique identifier of the event to update or move.
        calendar_id: The calendar where the event is located. Defaults to primary.
        destination_calendar_id: If provided, move event to this calendar instead of updating.
            Cannot combine with update fields.
        summary: New title. None=no change, ''=clear field.
        start_datetime: New start time. Supports natural language. None=no change.
        end_datetime: New end time. Supports natural language. None=no change.
        description: New description. None=no change, ''=clear field.
        location: New location. None=no change, ''=clear field.
        start_timezone: New IANA timezone for start. If empty, preserves existing.
        end_timezone: New IANA timezone for end. If empty, preserves existing.
        normalize_timezone: Fix timezone inconsistencies (UTC time with non-UTC label).

    Returns:
        UpdateEventResult with update details.
    """
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    # Handle move operation
    if destination_calendar_id:
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
    update_body: dict[str, Any] = {}
    updated_fields: list[str] = []

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


def delete(event_id: str, calendar_id: str = "primary") -> str:
    """Delete a calendar event permanently.

    Args:
        event_id: The unique identifier of the event to delete.
        calendar_id: The calendar where the event is located. Defaults to primary.

    Returns:
        Confirmation message.

    WARNING: This operation is irreversible.
    """
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    service.events().delete(calendarId=resolved_id, eventId=event_id).execute()
    return f"Event (ID: {event_id}) has been permanently deleted."


def list_calendars() -> list[CalendarInfo]:
    """List all accessible calendars.

    Returns:
        List of CalendarInfo with IDs, names, and access levels.
    """
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
