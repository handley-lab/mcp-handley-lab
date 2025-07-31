"""Integration tests for Google Calendar timezone normalization functionality."""

from datetime import datetime, timedelta

import pytest
from mcp_handley_lab.google_calendar.tool import mcp


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_normalize_timezone_integration(google_calendar_test_config):
    """Test end-to-end timezone normalization workflow."""
    # Create event with UTC time and timezone label (simulating recurring event issue)
    tomorrow = datetime.now() + timedelta(days=1)

    # Create an event that would have timezone inconsistency
    import json

    result = await mcp.call_tool(
        "create_event",
        {
            "summary": "Timezone Test Event",
            "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00Z",  # UTC time
            "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00Z",
            "start_timezone": "Europe/London",  # But with timezone label
            "end_timezone": "Europe/London",
            "description": "Testing timezone normalization",
        },
    )
    create_response = json.loads(result[0].text)
    assert "error" not in create_response, create_response.get("error")

    event_id = create_response["event_id"]

    try:
        # Get the event to verify it was created
        import json

        result = await mcp.call_tool("get_event", {"event_id": event_id})
        get_response = json.loads(result[0].text)
        assert "error" not in get_response, get_response.get("error")

        event = get_response
        assert event["summary"] == "Timezone Test Event"

        # Update event with normalize_timezone=True
        import json

        result = await mcp.call_tool(
            "update_event",
            {
                "event_id": event_id,
                "description": "Updated with timezone normalization",
                "normalize_timezone": True,
            },
        )
        update_response = json.loads(result[0].text)
        assert "error" not in update_response, update_response.get("error")

        update_result = update_response
        assert "updated" in update_result["message"].lower()

        # Verify the event was updated
        import json

        result = await mcp.call_tool("get_event", {"event_id": event_id})
        updated_response = json.loads(result[0].text)
        assert "error" not in updated_response, updated_response.get("error")

        updated_event = updated_response
        assert updated_event["description"] == "Updated with timezone normalization"

    finally:
        # Clean up
        result = await mcp.call_tool("delete_event", {"event_id": event_id})
        delete_response = result[0].text
        assert (
            "deleted" in delete_response.lower()
        ), f"Deletion failed: {delete_response}"


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_normalize_timezone_no_inconsistency(google_calendar_test_config):
    """Test normalize_timezone=True on event without inconsistency does nothing."""
    tomorrow = datetime.now() + timedelta(days=1)

    # Create event with proper local time (no inconsistency)
    import json

    result = await mcp.call_tool(
        "create_event",
        {
            "summary": "Normal Timezone Event",
            "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T14:00:00",  # Local time
            "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T15:00:00",
            "start_timezone": "Europe/London",
            "end_timezone": "Europe/London",
            "description": "No timezone issues",
        },
    )
    create_response = json.loads(result[0].text)
    assert "error" not in create_response, create_response.get("error")

    event_id = create_response["event_id"]

    try:
        # Update with normalize_timezone=True (should be no-op)
        import json

        result = await mcp.call_tool(
            "update_event",
            {
                "event_id": event_id,
                "description": "Updated but no normalization needed",
                "normalize_timezone": True,
            },
        )
        update_response = json.loads(result[0].text)
        assert "error" not in update_response, update_response.get("error")

        update_result = update_response
        # Should still update successfully
        assert "updated" in update_result["message"].lower()

        # Verify the event was updated
        import json

        result = await mcp.call_tool("get_event", {"event_id": event_id})
        updated_response = json.loads(result[0].text)
        assert "error" not in updated_response, updated_response.get("error")

        updated_event = updated_response
        assert updated_event["description"] == "Updated but no normalization needed"

    finally:
        # Clean up
        import json

        result = await mcp.call_tool("delete_event", {"event_id": event_id})
        delete_response = result[0].text
        assert (
            "deleted" in delete_response.lower()
        ), f"Deletion failed: {delete_response}"


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_create_event_without_timezone_uses_api_defaults(
    google_calendar_test_config,
):
    """Test that create_event without timezone uses application default."""
    tomorrow = datetime.now() + timedelta(days=1)

    # Create event without specifying timezone - should use application default
    import json

    result = await mcp.call_tool(
        "create_event",
        {
            "summary": "Default Timezone Event",
            "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T16:00:00",
            "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T17:00:00",
            # No timezone parameter - should use DEFAULT_TIMEZONE
            "description": "Testing default timezone fallback",
            "start_timezone": "",  # Empty string for default
            "end_timezone": "",  # Empty string for default
        },
    )
    create_response = json.loads(result[0].text)
    assert "error" not in create_response, create_response.get("error")

    event_id = create_response["event_id"]

    try:
        # Event should be created successfully with default timezone
        import json

        result = await mcp.call_tool("get_event", {"event_id": event_id})
        get_response = json.loads(result[0].text)
        assert "error" not in get_response, get_response.get("error")

        event = get_response
        assert event["summary"] == "Default Timezone Event"
        assert event["description"] == "Testing default timezone fallback"

    finally:
        # Clean up
        import json

        result = await mcp.call_tool("delete_event", {"event_id": event_id})
        delete_response = result[0].text
        assert (
            "deleted" in delete_response.lower()
        ), f"Deletion failed: {delete_response}"


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_update_event_datetime_without_timezone(google_calendar_test_config):
    """Test updating event datetime without timezone (should work cleanly)."""
    tomorrow = datetime.now() + timedelta(days=1)

    # Create initial event
    import json

    result = await mcp.call_tool(
        "create_event",
        {
            "summary": "Update Time Test",
            "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T09:00:00",
            "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
            "description": "Original time",
            "start_timezone": "",  # Empty string for default
            "end_timezone": "",  # Empty string for default
        },
    )
    create_response = json.loads(result[0].text)
    assert "error" not in create_response, create_response.get("error")

    event_id = create_response["event_id"]

    try:
        # Update just the time without timezone info
        import json

        result = await mcp.call_tool(
            "update_event",
            {
                "event_id": event_id,
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T12:00:00",
                "description": "Updated time",
                "start_timezone": "",  # Empty string for default
                "end_timezone": "",  # Empty string for default
            },
        )
        update_response = json.loads(result[0].text)
        assert "error" not in update_response, update_response.get("error")

        update_result = update_response
        assert "updated" in update_result["message"].lower()

        # Verify times were updated
        import json

        result = await mcp.call_tool("get_event", {"event_id": event_id})
        updated_response = json.loads(result[0].text)
        assert "error" not in updated_response, updated_response.get("error")

        updated_event = updated_response
        assert updated_event["description"] == "Updated time"
        # Times should be updated (exact format may vary based on API response)
        start_time_str = str(
            updated_event["start"].get(
                "dateTime", updated_event["start"].get("date", "")
            )
        )
        assert "11:00" in start_time_str

    finally:
        # Clean up
        import json

        result = await mcp.call_tool("delete_event", {"event_id": event_id})
        delete_response = result[0].text
        assert (
            "deleted" in delete_response.lower()
        ), f"Deletion failed: {delete_response}"


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_all_day_event_unaffected_by_timezone_normalization(
    google_calendar_test_config,
):
    """Test that all-day events are unaffected by timezone operations."""
    tomorrow = datetime.now() + timedelta(days=1)

    # Create all-day event
    import json

    result = await mcp.call_tool(
        "create_event",
        {
            "summary": "All Day Event",
            "start_datetime": tomorrow.strftime("%Y-%m-%d"),  # Date only, no time
            "end_datetime": (tomorrow + timedelta(days=1)).strftime("%Y-%m-%d"),
            "description": "All day event test",
            "start_timezone": "",  # Empty string for default
            "end_timezone": "",  # Empty string for default
        },
    )
    create_response = json.loads(result[0].text)
    assert "error" not in create_response, create_response.get("error")

    event_id = create_response["event_id"]

    try:
        # Attempt timezone normalization on all-day event (should be no-op)
        import json

        result = await mcp.call_tool(
            "update_event",
            {
                "event_id": event_id,
                "description": "All day with normalization attempt",
                "normalize_timezone": True,
            },
        )
        update_response = json.loads(result[0].text)
        assert "error" not in update_response, update_response.get("error")

        update_result = update_response
        assert "updated" in update_result["message"].lower()

        # Verify event was updated but remains all-day
        import json

        result = await mcp.call_tool("get_event", {"event_id": event_id})
        updated_response = json.loads(result[0].text)
        assert "error" not in updated_response, updated_response.get("error")

        updated_event = updated_response
        assert updated_event["description"] == "All day with normalization attempt"
        # Should still be all-day (has date, no dateTime)
        assert updated_event["start"]["date"] and not updated_event["start"].get(
            "dateTime"
        )

    finally:
        # Clean up
        import json

        result = await mcp.call_tool("delete_event", {"event_id": event_id})
        delete_response = result[0].text
        assert (
            "deleted" in delete_response.lower()
        ), f"Deletion failed: {delete_response}"
