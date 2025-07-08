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

    assert "calendar" in result.lower()
    assert "accessible" in result.lower() or "primary" in result.lower()


@pytest.mark.vcr
def test_google_calendar_search_events_basic_listing(google_calendar_test_config):
    # Use fixed dates to avoid VCR timestamp mismatches
    start_date = "2024-06-01T00:00:00Z"
    end_date = "2024-06-08T00:00:00Z"

    result = search_events(start_date=start_date, end_date=end_date)

    assert "events" in result.lower() or "no events" in result.lower()


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

    assert "created" in create_result.lower()

    # Extract event ID from structured JSON response
    import json

    try:
        result_data = json.loads(create_result)
        event_id = result_data.get("event_id")
        assert result_data.get("status") == "Event created successfully!"
        assert result_data.get("title") == event_title
    except (json.JSONDecodeError, AssertionError):
        pytest.fail(f"Invalid create_event response format: {create_result}")

    if event_id:
        # Get event
        get_result = get_event(event_id=event_id)
        assert event_title in get_result

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

    assert "available" in result.lower() or "slot" in result.lower()


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

    # Should not error and should contain search-related text
    assert (
        "search" in result.lower()
        or "found" in result.lower()
        or "no events" in result.lower()
    )
    assert "meeting" in result.lower() or "no events" in result.lower()


@pytest.mark.vcr
def test_google_calendar_list_events_with_search(google_calendar_test_config):
    # Test the search_text parameter in search_events
    start_date = "2024-06-01T00:00:00Z"
    end_date = "2024-06-08T00:00:00Z"

    # Test search via search_events
    result = search_events(search_text="test", start_date=start_date, end_date=end_date)

    # Should not error and should contain expected response
    assert "events" in result.lower() or "no events" in result.lower()


@pytest.mark.vcr
def test_google_calendar_server_info(google_calendar_test_config):
    result = server_info()

    assert "google calendar" in result.lower()
    assert "status" in result.lower()
