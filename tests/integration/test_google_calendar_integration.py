from datetime import datetime, timedelta

import pytest
from mcp_handley_lab.google_calendar.tool import (
    create_event,
    delete_event,
    find_time,
    get_event,
    list_calendars,
    search_events,
    server_info,
    update_event,
)


@pytest.mark.vcr
def test_google_calendar_list_calendars(google_calendar_test_config):
    result = list_calendars()

    assert isinstance(result, list)
    assert len(result) > 0
    # Check if we have at least one calendar
    assert any("primary" in cal.id or "gmail.com" in cal.id for cal in result)


@pytest.mark.vcr
def test_google_calendar_search_events_basic_listing(google_calendar_test_config):
    # Use fixed dates to avoid VCR timestamp mismatches
    start_date = "2024-06-01T00:00:00Z"
    end_date = "2024-06-08T00:00:00Z"

    result = search_events(start_date=start_date, end_date=end_date)

    assert isinstance(result, list)
    # This test may return events or empty list - both are valid


@pytest.mark.vcr
def test_google_calendar_event_lifecycle(google_calendar_test_config):
    # Create event
    tomorrow = datetime.now() + timedelta(days=1)
    start_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)

    event_title = "VCR Test Event"

    create_result = create_event(
        summary=event_title,
        start_datetime=start_time.isoformat() + "Z",
        end_datetime=end_time.isoformat() + "Z",
        description="Test event for VCR testing",
    )

    assert create_result.status == "Event created successfully!"
    assert create_result.title == event_title
    event_id = create_result.event_id

    # Event ID is now directly available from the structured response

    # Get event
    get_result = get_event(event_id=event_id)
    assert event_title in get_result.summary

    # Update event
    update_result = update_event(
        event_id=event_id,
        summary=event_title,
        description="Updated description for VCR test",
    )
    assert "updated" in update_result.lower()

    # Delete event
    delete_result = delete_event(event_id=event_id)
    assert "deleted" in delete_result.lower()


@pytest.mark.vcr
def test_google_calendar_find_time(google_calendar_test_config):
    result = find_time(duration_minutes=30, work_hours_only=True)

    assert isinstance(result, list)
    # May return 0 or more time slots - both are valid


@pytest.mark.vcr
def test_google_calendar_search_events(google_calendar_test_config):
    # Import the search function
    from mcp_handley_lab.google_calendar.tool import search_events

    # Use fixed dates to avoid VCR timestamp mismatches
    start_date = "2024-06-01T00:00:00Z"
    end_date = "2024-06-08T00:00:00Z"

    # Test basic search functionality
    result = search_events(
        search_text="meeting",
        start_date=start_date,
        end_date=end_date,
        match_all_terms=False,  # Use OR logic to increase chances of matches
    )

    # Should not error
    assert isinstance(result, list)
    # Result is a list of CalendarEvent objects or empty list


@pytest.mark.vcr
def test_google_calendar_list_events_with_search(google_calendar_test_config):
    # Test the search_text parameter in search_events
    start_date = "2024-06-01T00:00:00Z"
    end_date = "2024-06-08T00:00:00Z"

    # Test search via search_events
    result = search_events(search_text="test", start_date=start_date, end_date=end_date)

    # Should not error
    assert isinstance(result, list)
    # Result is a list of CalendarEvent objects or empty list


@pytest.mark.vcr
def test_google_calendar_server_info(google_calendar_test_config):
    result = server_info()

    assert result.name == "Google Calendar Tool"
    assert result.status == "active"
    assert "search_events" in str(result.capabilities)
