"""Demonstration of how event_creator fixture simplifies Google Calendar tests."""
import pytest
from datetime import datetime, timedelta
from mcp_handley_lab.google_calendar.tool import mcp


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_update_event_simplified_with_fixture(event_creator):
    """Demonstrate how the fixture simplifies event update tests."""
    tomorrow = datetime.now() + timedelta(days=1)
    
    # OLD WAY (without fixture):
    # - 15+ lines of create_event boilerplate
    # - Manual try/finally cleanup 
    # - Risk of leaving events if test fails
    
    # NEW WAY (with fixture):
    # Create event with just the essential test data
    event_id = await event_creator({
        "summary": "Partial Update Test", 
        "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
        "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
        "description": "Original meeting time"
    })
    
    # Focus on the actual test logic
    _, update_response = await mcp.call_tool("update_event", {
        "event_id": event_id,
        "description": "Updated description only",
        "calendar_id": "primary",
        "summary": "",
        "location": "",
        "start_datetime": "",
        "end_datetime": "", 
        "start_timezone": "",
        "end_timezone": "",
        "normalize_timezone": False
    })
    assert "error" not in update_response, update_response.get("error")
    update_result = update_response
    
    # Validate using the new structured format
    assert update_result["event_id"] == event_id
    assert "description" in update_result["updated_fields"]
    assert "updated" in update_result["message"].lower()
    
    # Verify the update was applied
    _, event_response = await mcp.call_tool("get_event", {
        "event_id": event_id,
        "calendar_id": "primary"
    })
    assert "error" not in event_response, event_response.get("error")
    updated_event = event_response
    
    assert updated_event["description"] == "Updated description only"
    assert updated_event["start"]["timeZone"]
    assert updated_event["end"]["timeZone"]
    
    # No cleanup needed - fixture handles it automatically!


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_multiple_events_with_fixture(event_creator):
    """Test creating multiple events with the fixture - demonstrates automatic cleanup."""
    tomorrow = datetime.now() + timedelta(days=1)
    
    # Create three events quickly with the fixture
    event_id1 = await event_creator({
        "summary": "Meeting 1",
        "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T09:00:00",
        "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00"
    })
    
    event_id2 = await event_creator({
        "summary": "Meeting 2", 
        "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
        "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T12:00:00"
    })
    
    event_id3 = await event_creator({
        "summary": "Meeting 3",
        "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T13:00:00", 
        "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T14:00:00"
    })
    
    # Verify all events were created
    for event_id, expected_summary in [(event_id1, "Meeting 1"), (event_id2, "Meeting 2"), (event_id3, "Meeting 3")]:
        _, response = await mcp.call_tool("get_event", {"event_id": event_id})
        assert "error" not in response
        assert response["summary"] == expected_summary
    
    # All three events will be automatically cleaned up by the fixture!