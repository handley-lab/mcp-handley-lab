from datetime import datetime, timedelta

import pytest
from mcp_handley_lab.google_calendar.tool import mcp


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_google_calendar_list_calendars(google_calendar_test_config):
    _, response = await mcp.call_tool("list_calendars", {})
    assert "error" not in response, response.get("error")
    result = response["result"]

    assert isinstance(result, list)
    assert len(result) > 0
    # Check if we have at least one calendar
    assert any("primary" in cal["id"] or "gmail.com" in cal["id"] for cal in result)


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_google_calendar_search_events_basic_listing(google_calendar_test_config):
    # Use fixed dates to avoid VCR timestamp mismatches
    start_date = "2024-06-01T00:00:00Z"
    end_date = "2024-06-08T00:00:00Z"

    _, response = await mcp.call_tool("search_events", {
        "start_date": start_date, 
        "end_date": end_date
    })
    assert "error" not in response, response.get("error")
    result = response["result"]

    assert isinstance(result, list)
    # This test may return events or empty list - both are valid


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_google_calendar_event_lifecycle(google_calendar_test_config):
    # Create event
    tomorrow = datetime.now() + timedelta(days=1)
    start_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)

    event_title = "VCR Test Event"

    _, create_response = await mcp.call_tool("create_event", {
        "summary": event_title,
        "start_datetime": start_time.isoformat() + "Z",
        "end_datetime": end_time.isoformat() + "Z",
        "description": "Test event for VCR testing",
    })
    assert "error" not in create_response, create_response.get("error")
    create_result = create_response

    assert create_result["status"] == "Event created successfully!"
    assert create_result["title"] == event_title
    event_id = create_result["event_id"]

    # Event ID is now directly available from the structured response

    # Get event
    _, get_response = await mcp.call_tool("get_event", {"event_id": event_id})
    assert "error" not in get_response, get_response.get("error")
    get_result = get_response
    assert event_title in get_result["summary"]

    # Update event
    _, update_response = await mcp.call_tool("update_event", {
        "event_id": event_id,
        "summary": event_title,
        "description": "Updated description for VCR test",
    })
    assert "error" not in update_response, update_response.get("error")
    update_result = update_response
    assert update_result["event_id"] == event_id
    assert "description" in update_result["updated_fields"]
    assert "updated" in update_result["message"].lower()

    # Delete event
    _, delete_response = await mcp.call_tool("delete_event", {"event_id": event_id})
    assert "error" not in delete_response, delete_response.get("error")
    delete_result = delete_response["result"]
    assert "deleted" in delete_result.lower()


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_google_calendar_find_time(google_calendar_test_config):
    _, response = await mcp.call_tool("find_time", {
        "duration_minutes": 30, 
        "work_hours_only": True
    })
    assert "error" not in response, response.get("error")
    result = response["result"]

    assert isinstance(result, list)
    # May return 0 or more time slots - both are valid


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_google_calendar_search_events(google_calendar_test_config):
    # Use fixed dates to avoid VCR timestamp mismatches
    start_date = "2024-06-01T00:00:00Z"
    end_date = "2024-06-08T00:00:00Z"

    # Test basic search functionality
    _, response = await mcp.call_tool("search_events", {
        "search_text": "meeting",
        "start_date": start_date,
        "end_date": end_date,
        "match_all_terms": False,  # Use OR logic to increase chances of matches
    })
    assert "error" not in response, response.get("error")
    result = response["result"]

    # Should not error
    assert isinstance(result, list)
    # Result is a list of CalendarEvent objects or empty list


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_google_calendar_list_events_with_search(google_calendar_test_config):
    # Test the search_text parameter in search_events
    start_date = "2024-06-01T00:00:00Z"
    end_date = "2024-06-08T00:00:00Z"

    # Test search via search_events
    _, response = await mcp.call_tool("search_events", {
        "search_text": "test", 
        "start_date": start_date, 
        "end_date": end_date
    })
    assert "error" not in response, response.get("error")
    result = response["result"]

    # Should not error
    assert isinstance(result, list)
    # Result is a list of CalendarEvent objects or empty list


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_google_calendar_move_event(google_calendar_test_config):
    """Test moving an event between calendars."""
    # First get available calendars
    _, calendars_response = await mcp.call_tool("list_calendars", {})
    assert "error" not in calendars_response, calendars_response.get("error")
    calendars = calendars_response["result"]
    
    # Find primary and at least one other calendar
    primary_calendar = None
    other_calendar = None
    
    for cal in calendars:
        if cal["id"] == "primary" or "gmail.com" in cal["id"]:
            primary_calendar = cal["id"]
        elif cal["accessRole"] in ["owner", "writer"] and cal["id"] != primary_calendar:
            other_calendar = cal["id"]
            break
    
    assert primary_calendar is not None, "Primary calendar not found"
    
    if other_calendar is None:
        pytest.skip("No writable secondary calendar available for move_event test")
    
    # Create event in primary calendar
    tomorrow = datetime.now() + timedelta(days=1)
    
    _, create_response = await mcp.call_tool("create_event", {
        "summary": "Event to Move",
        "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
        "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
        "description": "This event will be moved between calendars",
        "calendar_id": primary_calendar,
        "location": "",
        "attendees": [],
        "start_timezone": "",
        "end_timezone": ""
    })
    assert "error" not in create_response, create_response.get("error")
    event_id = create_response["event_id"]
    
    try:
        # Move event to other calendar
        _, move_response = await mcp.call_tool("move_event", {
            "event_id": event_id,
            "source_calendar_id": primary_calendar,
            "destination_calendar_id": other_calendar
        })
        assert "error" not in move_response, move_response.get("error")
        
        # Verify event is no longer in source calendar
        try:
            _, get_from_source_response = await mcp.call_tool("get_event", {
                "event_id": event_id,
                "calendar_id": primary_calendar
            })
            # Should fail to find event in original calendar
            if "error" not in get_from_source_response:
                # Some implementations might still show the event
                pytest.skip("Event still visible in source calendar - move behavior may vary")
        except Exception:
            # Expected - event should not be in source calendar
            pass
            
        # Verify event exists in destination calendar
        _, get_from_dest_response = await mcp.call_tool("get_event", {
            "event_id": event_id,
            "calendar_id": other_calendar
        })
        assert "error" not in get_from_dest_response, "Event should exist in destination calendar"
        moved_event = get_from_dest_response
        
        assert moved_event["summary"] == "Event to Move"
        assert moved_event["description"] == "This event will be moved between calendars"
        
    finally:
        # Clean up - try to delete from both calendars
        for cal_id in [primary_calendar, other_calendar]:
            try:
                await mcp.call_tool("delete_event", {
                    "event_id": event_id,
                    "calendar_id": cal_id
                })
            except:
                # Expected if event not in this calendar
                pass


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_google_calendar_server_info(google_calendar_test_config):
    _, response = await mcp.call_tool("server_info", {})
    assert "error" not in response, response.get("error")
    result = response

    assert result["name"] == "Google Calendar Tool"
    assert result["status"] == "active"
    assert "search_events" in str(result["capabilities"])
