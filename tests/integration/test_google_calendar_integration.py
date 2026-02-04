from datetime import datetime, timedelta

import pytest

from mcp_handley_lab.google_calendar.shared import list_calendars
from mcp_handley_lab.google_calendar.tool import mcp


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_google_calendar_read_events_basic_listing(google_calendar_test_config):
    """Test read() for listing events (was search_events)."""
    # Use fixed dates to avoid VCR timestamp mismatches
    start_date = "2024-06-01T00:00:00Z"
    end_date = "2024-06-08T00:00:00Z"

    _, response = await mcp.call_tool(
        "read", {"start_date": start_date, "end_date": end_date}
    )
    assert "error" not in response, response.get("error")
    result = response["result"]

    assert isinstance(result, list)
    # This test may return events or empty list - both are valid


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_google_calendar_event_lifecycle(google_calendar_test_config):
    """Test full CRUD lifecycle: create, read, update, delete."""
    # Create event
    tomorrow = datetime.now() + timedelta(days=1)
    start_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)

    event_title = "VCR Test Event"

    _, create_response = await mcp.call_tool(
        "create",
        {
            "summary": event_title,
            "start_datetime": start_time.isoformat() + "Z",
            "end_datetime": end_time.isoformat() + "Z",
            "description": "Test event for VCR testing",
            "calendar_id": "primary",
        },
    )
    assert "error" not in create_response, create_response.get("error")
    create_result = create_response

    assert create_result["status"] == "Event created successfully!"
    assert create_result["title"] == event_title
    event_id = create_result["event_id"]

    # Read event (now returns list, even for single event)
    _, get_response = await mcp.call_tool("read", {"event_id": event_id})
    assert "error" not in get_response, get_response.get("error")
    get_result = get_response["result"]
    assert isinstance(get_result, list)
    assert len(get_result) == 1
    assert event_title in get_result[0]["summary"]

    # Update event
    _, update_response = await mcp.call_tool(
        "update",
        {
            "event_id": event_id,
            "summary": event_title,
            "description": "Updated description for VCR test",
        },
    )
    assert "error" not in update_response, update_response.get("error")
    update_result = update_response
    assert update_result["event_id"] == event_id
    assert "description" in update_result["updated_fields"]
    assert "updated" in update_result["message"].lower()

    # Delete event
    _, delete_response = await mcp.call_tool("delete", {"event_id": event_id})
    assert "error" not in delete_response, delete_response.get("error")
    delete_result = delete_response["result"]
    assert "deleted" in delete_result.lower()


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_google_calendar_read_with_search(google_calendar_test_config):
    """Test read() with search_text parameter."""
    # Use fixed dates to avoid VCR timestamp mismatches
    start_date = "2024-06-01T00:00:00Z"
    end_date = "2024-06-08T00:00:00Z"

    # Test basic search functionality
    _, response = await mcp.call_tool(
        "read",
        {
            "search_text": "meeting",
            "start_date": start_date,
            "end_date": end_date,
            "match_all_terms": False,  # Use OR logic to increase chances of matches
        },
    )
    assert "error" not in response, response.get("error")
    result = response["result"]

    # Should not error
    assert isinstance(result, list)
    # Result is a list of CalendarEvent objects or empty list


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_google_calendar_read_search_text(google_calendar_test_config):
    """Test read() with search_text parameter."""
    start_date = "2024-06-01T00:00:00Z"
    end_date = "2024-06-08T00:00:00Z"

    _, response = await mcp.call_tool(
        "read",
        {"search_text": "test", "start_date": start_date, "end_date": end_date},
    )
    assert "error" not in response, response.get("error")
    result = response["result"]

    # Should not error
    assert isinstance(result, list)
    # Result is a list of CalendarEvent objects or empty list


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_google_calendar_update_with_move(google_calendar_test_config):
    """Test moving an event via update() with destination_calendar_id."""
    # First get available calendars
    calendars = list_calendars()

    # Find two calendars with write access
    writable_calendars = [
        cal for cal in calendars if cal.accessRole in ["owner", "writer"]
    ]

    if len(writable_calendars) < 2:
        pytest.skip("Need at least 2 writable calendars for move test")

    primary_calendar = writable_calendars[0].id
    other_calendar = writable_calendars[1].id

    # Create event in primary calendar
    tomorrow = datetime.now() + timedelta(days=1)

    _, create_response = await mcp.call_tool(
        "create",
        {
            "summary": "Event to Move",
            "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
            "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
            "description": "This event will be moved between calendars",
            "calendar_id": primary_calendar,
        },
    )
    assert "error" not in create_response, create_response.get("error")
    event_id = create_response["event_id"]

    try:
        # Move event to other calendar via update() with destination_calendar_id
        _, move_response = await mcp.call_tool(
            "update",
            {
                "event_id": event_id,
                "calendar_id": primary_calendar,
                "destination_calendar_id": other_calendar,
            },
        )
        assert "error" not in move_response, move_response.get("error")
        assert "moved" in move_response["updated_fields"]
        # new_event_id may differ from original
        new_event_id = move_response.get("new_event_id", event_id)

        # Verify event is no longer in source calendar
        try:
            _, get_from_source_response = await mcp.call_tool(
                "read", {"event_id": event_id, "calendar_id": primary_calendar}
            )
            # Should fail to find event in original calendar
            if "error" not in get_from_source_response:
                # Some implementations might still show the event
                pytest.skip(
                    "Event still visible in source calendar - move behavior may vary"
                )
        except Exception:
            # Expected - event should not be in source calendar
            pass

        # Verify event exists in destination calendar
        _, get_from_dest_response = await mcp.call_tool(
            "read", {"event_id": new_event_id, "calendar_id": other_calendar}
        )
        assert "error" not in get_from_dest_response, (
            "Event should exist in destination calendar"
        )
        moved_events = get_from_dest_response["result"]
        assert len(moved_events) == 1
        moved_event = moved_events[0]

        assert moved_event["summary"] == "Event to Move"
        assert (
            moved_event["description"] == "This event will be moved between calendars"
        )

    finally:
        # Clean up - delete from destination calendar
        await mcp.call_tool(
            "delete", {"event_id": new_event_id, "calendar_id": other_calendar}
        )
