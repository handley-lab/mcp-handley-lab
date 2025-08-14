"""Integration tests for real-world Google Calendar scenarios."""

from datetime import datetime, timedelta

import pytest

from mcp_handley_lab.google_calendar.tool import mcp


class TestRealWorldEventCreation:
    """Test real-world event creation scenarios with various datetime formats."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_us_website_event_creation(self, google_calendar_test_config):
        """Test creating event from US website datetime (with timezone offset)."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Simulate user copying "2:00 PM PST" from US website
        _, response = await mcp.call_tool(
            "create_event",
            {
                "summary": "US Conference Session",
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T14:00:00-08:00",  # PST
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T15:00:00-08:00",
                "description": "Copied from US conference website",
                "location": "San Francisco, CA",
                "calendar_id": "primary",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": "",
            },
        )
        assert "error" not in response, response.get("error")
        create_result = response

        event_id = create_result["event_id"]

        try:
            # Verify event was created correctly
            assert create_result["status"] == "Event created successfully!"
            assert create_result["title"] == "US Conference Session"

            # Get the event to verify timezone handling
            _, event_response = await mcp.call_tool(
                "get_event", {"event_id": event_id, "calendar_id": "primary"}
            )
            assert "error" not in event_response, event_response.get("error")
            event = event_response

            assert event["summary"] == "US Conference Session"
            assert event["description"] == "Copied from US conference website"
            assert event["location"] == "San Francisco, CA"

            # Time should be converted to calendar's timezone
            assert event["start"]["timeZone"]  # Should have timezone info
            assert event["end"]["timeZone"]

        finally:
            await mcp.call_tool(
                "delete_event", {"event_id": event_id, "calendar_id": "primary"}
            )

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_international_utc_event_creation(self, google_calendar_test_config):
        """Test creating event from international website with UTC time."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Simulate user copying UTC time from international webinar
        _, response = await mcp.call_tool(
            "create_event",
            {
                "summary": "Global Webinar",
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T14:00:00Z",  # UTC
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T15:00:00Z",
                "description": "International webinar in UTC",
                "location": "Online",
                "calendar_id": "primary",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": "",
            },
        )
        assert "error" not in response, response.get("error")
        create_result = response

        event_id = create_result["event_id"]

        try:
            # Verify event was created correctly
            assert create_result["status"] == "Event created successfully!"
            assert create_result["title"] == "Global Webinar"

            # Get the event to verify timezone handling
            _, event_response = await mcp.call_tool(
                "get_event", {"event_id": event_id, "calendar_id": "primary"}
            )
            assert "error" not in event_response, event_response.get("error")
            event = event_response
            assert event["summary"] == "Global Webinar"
            assert event["description"] == "International webinar in UTC"

            # Should be properly converted from UTC to local time
            assert event["start"]["timeZone"]  # Should have timezone info
            assert event["end"]["timeZone"]

        finally:
            await mcp.call_tool(
                "delete_event", {"event_id": event_id, "calendar_id": "primary"}
            )

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_local_naive_time_event_creation(self, google_calendar_test_config):
        """Test creating event with naive datetime (no timezone info)."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Simulate user typing local time for meeting
        _, response = await mcp.call_tool(
            "create_event",
            {
                "summary": "Local Team Meeting",
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T09:00:00",  # Naive time
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
                "description": "Regular team standup",
                "location": "Conference Room A",
                "calendar_id": "primary",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": "",
            },
        )
        assert "error" not in response, response.get("error")
        create_result = response

        event_id = create_result["event_id"]

        try:
            # Verify event was created correctly
            assert create_result["status"] == "Event created successfully!"
            assert create_result["title"] == "Local Team Meeting"

            # Get the event to verify timezone handling
            _, event_response = await mcp.call_tool(
                "get_event", {"event_id": event_id, "calendar_id": "primary"}
            )
            assert "error" not in event_response, event_response.get("error")
            event = event_response
            assert event["summary"] == "Local Team Meeting"
            assert event["description"] == "Regular team standup"

            # Should be treated as local time in calendar's timezone
            assert event["start"]["timeZone"]  # Should have timezone info
            assert event["end"]["timeZone"]

        finally:
            await mcp.call_tool(
                "delete_event", {"event_id": event_id, "calendar_id": "primary"}
            )

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_european_timezone_event_creation(self, google_calendar_test_config):
        """Test creating event from European website with CET/CEST timezone."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Simulate user copying from European conference site
        _, response = await mcp.call_tool(
            "create_event",
            {
                "summary": "European Workshop",
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T15:00:00+01:00",  # CET
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T16:30:00+01:00",
                "description": "Workshop in Central European Time",
                "location": "Berlin, Germany",
                "calendar_id": "primary",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": "",
            },
        )
        assert "error" not in response, response.get("error")
        create_result = response

        event_id = create_result["event_id"]

        try:
            # Verify event was created correctly
            assert create_result["status"] == "Event created successfully!"
            assert create_result["title"] == "European Workshop"

            # Get the event to verify timezone handling
            _, event_response = await mcp.call_tool(
                "get_event", {"event_id": event_id, "calendar_id": "primary"}
            )
            assert "error" not in event_response, event_response.get("error")
            event = event_response
            assert event["summary"] == "European Workshop"
            assert event["description"] == "Workshop in Central European Time"

            # Should be converted from CET to calendar's timezone
            assert event["start"]["timeZone"]  # Should have timezone info
            assert event["end"]["timeZone"]

        finally:
            await mcp.call_tool(
                "delete_event", {"event_id": event_id, "calendar_id": "primary"}
            )

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_all_day_event_creation(self, google_calendar_test_config):
        """Test creating all-day event with date-only input."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Simulate user creating holiday/all-day event
        _, response = await mcp.call_tool(
            "create_event",
            {
                "summary": "Company Holiday",
                "start_datetime": tomorrow.strftime("%Y-%m-%d"),  # Date only
                "end_datetime": (tomorrow + timedelta(days=1)).strftime("%Y-%m-%d"),
                "description": "National holiday - office closed",
                "location": "",
                "calendar_id": "primary",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": "",
            },
        )
        assert "error" not in response, response.get("error")
        create_result = response

        event_id = create_result["event_id"]

        try:
            # Verify event was created correctly
            assert create_result["status"] == "Event created successfully!"
            assert create_result["title"] == "Company Holiday"

            # Get the event to verify all-day handling
            _, event_response = await mcp.call_tool(
                "get_event", {"event_id": event_id, "calendar_id": "primary"}
            )
            assert "error" not in event_response, event_response.get("error")
            event = event_response
            assert event["summary"] == "Company Holiday"
            assert event["description"] == "National holiday - office closed"

            # Should be all-day event (has date, no dateTime, timezone can be empty)
            assert event["start"]["date"]  # Should have date
            assert not event["start"].get("dateTime")  # Should not have dateTime

        finally:
            await mcp.call_tool(
                "delete_event", {"event_id": event_id, "calendar_id": "primary"}
            )


class TestRealWorldEventUpdates:
    """Test real-world event update scenarios with timezone handling."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_update_event_with_timezone_conversion(
        self, google_calendar_test_config
    ):
        """Test updating event time with automatic timezone conversion."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Create initial event
        _, response = await mcp.call_tool(
            "create_event",
            {
                "summary": "Meeting to Reschedule",
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
                "description": "Initial meeting time",
                "location": "",
                "calendar_id": "primary",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": "",
            },
        )
        assert "error" not in response, response.get("error")
        create_result = response

        event_id = create_result["event_id"]

        try:
            # Update with time from different timezone (e.g., copied from website)
            _, update_response = await mcp.call_tool(
                "update_event",
                {
                    "event_id": event_id,
                    "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T14:00:00-07:00",  # PDT
                    "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T15:00:00-07:00",
                    "description": "Updated with time from West Coast website",
                    "calendar_id": "primary",
                    "summary": "",
                    "location": "",
                    "start_timezone": "",
                    "end_timezone": "",
                    "normalize_timezone": False,
                },
            )
            assert "error" not in update_response, update_response.get("error")
            update_result = update_response

            # update_result is the string returned by update_event
            if isinstance(update_result, dict):
                # If the result is wrapped in a dict, extract the message
                message = update_result.get("message", str(update_result))
            else:
                message = str(update_result)
            assert "updated" in message.lower()

            # Verify the update was applied with correct timezone conversion
            _, event_response = await mcp.call_tool(
                "get_event", {"event_id": event_id, "calendar_id": "primary"}
            )
            assert "error" not in event_response, event_response.get("error")
            updated_event = event_response
            assert (
                updated_event["description"]
                == "Updated with time from West Coast website"
            )

            # Should be converted from PDT to calendar's timezone
            assert updated_event["start"]["timeZone"]  # Should have timezone info
            assert updated_event["end"]["timeZone"]

        finally:
            await mcp.call_tool(
                "delete_event", {"event_id": event_id, "calendar_id": "primary"}
            )

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_update_event_with_naive_time(self, google_calendar_test_config):
        """Test updating event with naive datetime (no timezone info)."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Create initial event
        _, response = await mcp.call_tool(
            "create_event",
            {
                "summary": "Local Meeting Update",
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T09:00:00",
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
                "description": "Original time",
                "location": "",
                "calendar_id": "primary",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": "",
            },
        )
        assert "error" not in response, response.get("error")
        create_result = response

        event_id = create_result["event_id"]

        try:
            # Update with naive time (user types new local time)
            _, update_response = await mcp.call_tool(
                "update_event",
                {
                    "event_id": event_id,
                    "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",  # Naive time
                    "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T12:00:00",
                    "description": "Updated to new local time",
                    "calendar_id": "primary",
                    "summary": "",
                    "location": "",
                    "start_timezone": "",
                    "end_timezone": "",
                    "normalize_timezone": False,
                },
            )
            assert "error" not in update_response, update_response.get("error")
            update_result = update_response

            # update_result is the string returned by update_event
            if isinstance(update_result, dict):
                # If the result is wrapped in a dict, extract the message
                message = update_result.get("message", str(update_result))
            else:
                message = str(update_result)
            assert "updated" in message.lower()

            # Verify the update was applied correctly
            _, event_response = await mcp.call_tool(
                "get_event", {"event_id": event_id, "calendar_id": "primary"}
            )
            assert "error" not in event_response, event_response.get("error")
            updated_event = event_response
            assert updated_event["description"] == "Updated to new local time"

            # Should be treated as local time in existing event's timezone
            assert updated_event["start"]["timeZone"]  # Should have timezone info
            assert updated_event["end"]["timeZone"]

        finally:
            await mcp.call_tool(
                "delete_event", {"event_id": event_id, "calendar_id": "primary"}
            )

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_update_event_description_only(self, google_calendar_test_config):
        """Test updating event description without changing times."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Create initial timed event
        _, response = await mcp.call_tool(
            "create_event",
            {
                "summary": "Simple Update Test",
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T09:00:00",
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T17:00:00",
                "description": "Original description",
                "location": "",
                "calendar_id": "primary",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": "",
            },
        )
        assert "error" not in response, response.get("error")
        create_result = response

        event_id = create_result["event_id"]

        try:
            # Update description only
            _, update_response = await mcp.call_tool(
                "update_event",
                {
                    "event_id": event_id,
                    "description": "Updated description without time changes",
                    "calendar_id": "primary",
                    "summary": "",
                    "location": "",
                    "start_datetime": "",
                    "end_datetime": "",
                    "start_timezone": "",
                    "end_timezone": "",
                    "normalize_timezone": False,
                },
            )
            assert "error" not in update_response, update_response.get("error")
            update_result = update_response

            # update_result is the string returned by update_event
            if isinstance(update_result, dict):
                # If the result is wrapped in a dict, extract the message
                message = update_result.get("message", str(update_result))
            else:
                message = str(update_result)
            assert "updated" in message.lower()

            # Verify the update was applied correctly
            _, event_response = await mcp.call_tool(
                "get_event", {"event_id": event_id, "calendar_id": "primary"}
            )
            assert "error" not in event_response, event_response.get("error")
            updated_event = event_response
            assert (
                updated_event["description"]
                == "Updated description without time changes"
            )

            # Should still be timed event with timezone
            assert updated_event["start"]["timeZone"]  # Should have timezone

        finally:
            await mcp.call_tool(
                "delete_event", {"event_id": event_id, "calendar_id": "primary"}
            )


class TestComplexScenarios:
    """Test complex real-world scenarios involving multiple timezone operations."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_multi_timezone_event_workflow(self, google_calendar_test_config):
        """Test complete workflow with multiple timezone conversions."""
        tomorrow = datetime.now() + timedelta(days=1)

        # 1. Create event with US timezone (from website)
        _, response = await mcp.call_tool(
            "create_event",
            {
                "summary": "Global Team Sync",
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00-08:00",  # PST
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00-08:00",
                "description": "Originally scheduled for PST",
                "location": "Online",
                "calendar_id": "primary",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": "",
            },
        )
        assert "error" not in response, response.get("error")
        create_result = response

        event_id = create_result["event_id"]

        try:
            # 2. Update with European timezone (from another website)
            _, update_response = await mcp.call_tool(
                "update_event",
                {
                    "event_id": event_id,
                    "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T16:00:00+01:00",  # CET
                    "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T17:00:00+01:00",
                    "description": "Rescheduled to better time for European team",
                    "calendar_id": "primary",
                    "summary": "",
                    "location": "",
                    "start_timezone": "",
                    "end_timezone": "",
                    "normalize_timezone": False,
                },
            )
            assert "error" not in update_response, update_response.get("error")
            update_result = update_response

            # update_result is the string returned by update_event
            if isinstance(update_result, dict):
                # If the result is wrapped in a dict, extract the message
                message = update_result.get("message", str(update_result))
            else:
                message = str(update_result)
            assert "updated" in message.lower()

            # 3. Final update with UTC time (from international platform)
            _, final_update_response = await mcp.call_tool(
                "update_event",
                {
                    "event_id": event_id,
                    "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T14:00:00Z",  # UTC
                    "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T15:00:00Z",
                    "description": "Final time in UTC for global accessibility",
                    "calendar_id": "primary",
                    "summary": "",
                    "location": "",
                    "start_timezone": "",
                    "end_timezone": "",
                    "normalize_timezone": False,
                },
            )
            assert "error" not in final_update_response, final_update_response.get(
                "error"
            )
            final_update = final_update_response

            # final_update is the string returned by update_event
            if isinstance(final_update, dict):
                # If the result is wrapped in a dict, extract the message
                message = final_update.get("message", str(final_update))
            else:
                message = str(final_update)
            assert "updated" in message.lower()

            # 4. Verify final event has correct timezone handling
            _, event_response = await mcp.call_tool(
                "get_event", {"event_id": event_id, "calendar_id": "primary"}
            )
            assert "error" not in event_response, event_response.get("error")
            final_event = event_response
            assert final_event["summary"] == "Global Team Sync"
            assert (
                final_event["description"]
                == "Final time in UTC for global accessibility"
            )

            # Should be converted from UTC to calendar's timezone
            assert final_event["start"]["timeZone"]  # Should have timezone info
            assert final_event["end"]["timeZone"]

        finally:
            await mcp.call_tool(
                "delete_event", {"event_id": event_id, "calendar_id": "primary"}
            )

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_cross_calendar_timezone_consistency(
        self, google_calendar_test_config
    ):
        """Test that events maintain timezone consistency across operations."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Create event with complex timezone scenario
        _, response = await mcp.call_tool(
            "create_event",
            {
                "summary": "Cross-Timezone Consistency Test",
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T15:30:00+02:00",  # CEST
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T16:45:00+02:00",
                "description": "Testing timezone consistency",
                "location": "Virtual",
                "calendar_id": "primary",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": "",
            },
        )
        assert "error" not in response, response.get("error")
        create_result = response

        event_id = create_result["event_id"]

        try:
            # Get event immediately after creation
            _, event_response = await mcp.call_tool(
                "get_event", {"event_id": event_id, "calendar_id": "primary"}
            )
            assert "error" not in event_response, event_response.get("error")
            created_event = event_response
            original_start_time = created_event["start"]["dateTime"]
            original_timezone = created_event["start"]["timeZone"]

            # Update only description (no time change)
            _, update_response = await mcp.call_tool(
                "update_event",
                {
                    "event_id": event_id,
                    "description": "Updated description without time change",
                    "calendar_id": "primary",
                    "summary": "",
                    "location": "",
                    "start_datetime": "",
                    "end_datetime": "",
                    "start_timezone": "",
                    "end_timezone": "",
                    "normalize_timezone": False,
                },
            )
            assert "error" not in update_response, update_response.get("error")
            update_result = update_response

            # update_result is the string returned by update_event
            if isinstance(update_result, dict):
                # If the result is wrapped in a dict, extract the message
                message = update_result.get("message", str(update_result))
            else:
                message = str(update_result)
            assert "updated" in message.lower()

            # Verify time remained unchanged
            _, updated_event_response = await mcp.call_tool(
                "get_event", {"event_id": event_id, "calendar_id": "primary"}
            )
            assert "error" not in updated_event_response, updated_event_response.get(
                "error"
            )
            updated_event = updated_event_response
            assert updated_event["start"]["dateTime"] == original_start_time
            assert updated_event["start"]["timeZone"] == original_timezone
            assert (
                updated_event["description"]
                == "Updated description without time change"
            )

        finally:
            await mcp.call_tool(
                "delete_event", {"event_id": event_id, "calendar_id": "primary"}
            )

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_seasonal_time_change_handling(self, google_calendar_test_config):
        """Test handling of seasonal time changes (DST transitions)."""
        # Use dates that cross DST boundaries
        winter_date = "2024-01-15"
        summer_date = "2024-07-15"

        # Create winter event with EST timezone
        _, winter_response = await mcp.call_tool(
            "create_event",
            {
                "summary": "Winter Event",
                "start_datetime": f"{winter_date}T14:00:00-05:00",  # EST
                "end_datetime": f"{winter_date}T15:00:00-05:00",
                "description": "Event during standard time",
                "location": "",
                "calendar_id": "primary",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": "",
            },
        )
        assert "error" not in winter_response, winter_response.get("error")
        winter_result = winter_response

        winter_event_id = winter_result["event_id"]

        # Create summer event with EDT timezone
        _, summer_response = await mcp.call_tool(
            "create_event",
            {
                "summary": "Summer Event",
                "start_datetime": f"{summer_date}T14:00:00-04:00",  # EDT
                "end_datetime": f"{summer_date}T15:00:00-04:00",
                "description": "Event during daylight time",
                "location": "",
                "calendar_id": "primary",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": "",
            },
        )
        assert "error" not in summer_response, summer_response.get("error")
        summer_result = summer_response

        summer_event_id = summer_result["event_id"]

        try:
            # Verify both events were created successfully
            _, winter_event_response = await mcp.call_tool(
                "get_event", {"event_id": winter_event_id, "calendar_id": "primary"}
            )
            assert "error" not in winter_event_response, winter_event_response.get(
                "error"
            )
            winter_event = winter_event_response

            _, summer_event_response = await mcp.call_tool(
                "get_event", {"event_id": summer_event_id, "calendar_id": "primary"}
            )
            assert "error" not in summer_event_response, summer_event_response.get(
                "error"
            )
            summer_event = summer_event_response

            assert winter_event["summary"] == "Winter Event"
            assert summer_event["summary"] == "Summer Event"

            # Both should have proper timezone handling
            assert winter_event["start"]["timeZone"]
            assert summer_event["start"]["timeZone"]

        finally:
            await mcp.call_tool(
                "delete_event", {"event_id": winter_event_id, "calendar_id": "primary"}
            )
            await mcp.call_tool(
                "delete_event", {"event_id": summer_event_id, "calendar_id": "primary"}
            )
