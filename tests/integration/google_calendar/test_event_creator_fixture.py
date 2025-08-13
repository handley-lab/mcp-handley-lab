"""Test the event_creator fixture functionality."""
from datetime import datetime, timedelta

import pytest
from mcp_handley_lab.google_calendar.tool import mcp


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_event_creator_fixture_basic(event_creator):
    """Test that the event_creator fixture creates and cleans up events properly."""
    tomorrow = datetime.now() + timedelta(days=1)

    # Create event using the fixture
    event_id = await event_creator(
        {
            "summary": "Fixture Test Event",
            "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
            "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
            "description": "Testing the event creator fixture",
        }
    )

    # Verify event was created and can be retrieved
    _, get_response = await mcp.call_tool("get_event", {"event_id": event_id})
    assert "error" not in get_response, get_response.get("error")
    event = get_response

    assert event["summary"] == "Fixture Test Event"
    assert event["description"] == "Testing the event creator fixture"

    # The fixture will automatically delete the event after this test


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_event_creator_fixture_multiple_events(event_creator):
    """Test creating multiple events with the fixture."""
    tomorrow = datetime.now() + timedelta(days=1)

    # Create first event
    event_id1 = await event_creator(
        {
            "summary": "First Test Event",
            "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T09:00:00",
            "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
        }
    )

    # Create second event
    event_id2 = await event_creator(
        {
            "summary": "Second Test Event",
            "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
            "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T12:00:00",
        }
    )

    # Verify both events exist
    _, get_response1 = await mcp.call_tool("get_event", {"event_id": event_id1})
    assert "error" not in get_response1
    assert get_response1["summary"] == "First Test Event"

    _, get_response2 = await mcp.call_tool("get_event", {"event_id": event_id2})
    assert "error" not in get_response2
    assert get_response2["summary"] == "Second Test Event"

    # Both events will be automatically cleaned up


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_event_creator_with_natural_language(event_creator):
    """Test event creator with natural language datetime inputs."""
    # Create event with natural language times
    event_id = await event_creator(
        {
            "summary": "Natural Language Event",
            "start_datetime": "tomorrow at 2pm",
            "end_datetime": "tomorrow at 3pm",
            "description": "Created with natural language",
        }
    )

    # Verify it was created properly
    _, get_response = await mcp.call_tool("get_event", {"event_id": event_id})
    assert "error" not in get_response
    event = get_response

    assert event["summary"] == "Natural Language Event"
    assert event["description"] == "Created with natural language"
    # Should have timezone info for natural language events
    assert event["start"]["timeZone"]
    assert event["end"]["timeZone"]
