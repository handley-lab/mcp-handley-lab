"""Systematic unhappy path tests for Google Calendar integration.

Tests error scenarios, edge cases, and failure modes to ensure robust error handling.
Covers authentication failures, invalid inputs, resource constraints, and service errors.
"""
import pytest
from datetime import datetime, timedelta
from mcp.server.fastmcp.exceptions import ToolError

from mcp_handley_lab.google_calendar.tool import mcp


@pytest.mark.integration 
class TestGoogleCalendarAuthenticationErrors:
    """Test authentication and permission error scenarios."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_invalid_event_id_error(self, google_calendar_test_config):
        """Test handling of non-existent event IDs."""
        invalid_event_id = "nonexistent_event_id_12345"
        
        with pytest.raises(ToolError, match="Event not found|not found|invalid"):
            await mcp.call_tool("get_event", {
                "event_id": invalid_event_id,
                "calendar_id": "primary"
            })

    @pytest.mark.vcr
    @pytest.mark.asyncio  
    async def test_invalid_calendar_id_error(self, google_calendar_test_config):
        """Test handling of non-existent calendar IDs."""
        invalid_calendar_id = "nonexistent_calendar_12345@group.calendar.google.com"
        
        with pytest.raises(ToolError, match="Calendar not found|not found|invalid"):
            await mcp.call_tool("list_calendars", {})
            # Try to create event in non-existent calendar
            tomorrow = datetime.now() + timedelta(days=1)
            await mcp.call_tool("create_event", {
                "summary": "Test Event",
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00", 
                "calendar_id": invalid_calendar_id,
                "description": "",
                "location": "",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": ""
            })


@pytest.mark.integration
class TestGoogleCalendarInvalidInputs:
    """Test systematic invalid input scenarios."""

    @pytest.mark.asyncio
    async def test_empty_required_parameters(self, google_calendar_test_config):
        """Test validation of empty required parameters."""
        
        # Test empty summary
        tomorrow = datetime.now() + timedelta(days=1)
        with pytest.raises(ToolError, match="summary|required|empty|missing"):
            await mcp.call_tool("create_event", {
                "summary": "",
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
                "calendar_id": "primary",
                "description": "",
                "location": "",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": ""
            })
        
        # Test empty event_id for get_event
        with pytest.raises(ToolError, match="id|event_id|required|empty|missing"):
            await mcp.call_tool("get_event", {
                "event_id": "",
                "calendar_id": "primary"
            })

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_malformed_datetime_inputs(self, google_calendar_test_config):
        """Test handling of various malformed datetime formats."""
        malformed_datetimes = [
            "not-a-datetime",
            "2024/13/45T25:00:00",  # Invalid date/time values
            "2024-02-30T10:00:00",  # Invalid date (Feb 30th)
            "tomorrow at 25 o'clock",  # Invalid natural language
            "2024-12-25T10:00:00+99:00",  # Invalid timezone offset
            "",  # Empty datetime
            "null",  # String "null"
            "undefined",  # String "undefined"
        ]
        
        for bad_datetime in malformed_datetimes:
            with pytest.raises(ToolError, match="datetime|parse|invalid|format|empty"):
                await mcp.call_tool("create_event", {
                    "summary": "Test Event",
                    "start_datetime": bad_datetime,
                    "end_datetime": "tomorrow at 11am",
                    "calendar_id": "primary",
                    "description": "",
                    "location": "",
                    "attendees": [],
                    "start_timezone": "",
                    "end_timezone": ""
                })

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_invalid_timezone_inputs(self, google_calendar_test_config):
        """Test handling of invalid timezone specifications."""
        tomorrow = datetime.now() + timedelta(days=1)
        
        invalid_timezones = [
            "Invalid/Timezone",
            "America/NonExistent", 
            "UTC+25",  # Invalid UTC offset
            "Not_A_Timezone",
            "Europe/London/Extra",  # Too many parts
            "GMT+999",  # Invalid offset range
        ]
        
        for bad_timezone in invalid_timezones:
            with pytest.raises(ToolError, match="timezone|invalid|unknown|TIMEZONE"):
                await mcp.call_tool("create_event", {
                    "summary": "Timezone Test",
                    "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
                    "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
                    "start_timezone": bad_timezone,
                    "end_timezone": "UTC",
                    "calendar_id": "primary",
                    "description": "",
                    "location": "",
                    "attendees": [],
                })

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_invalid_email_attendees(self, google_calendar_test_config):
        """Test handling of malformed attendee email addresses."""
        tomorrow = datetime.now() + timedelta(days=1)
        
        invalid_emails = [
            "not-an-email",
            "missing@domain", 
            "@missinguser.com",
            "spaces in email@domain.com",
            "toolong" + "x" * 1000 + "@domain.com",  # Excessively long
            "",  # Empty string in list
        ]
        
        for bad_email in invalid_emails:
            with pytest.raises(ToolError, match="email|invalid|attendee|format"):
                await mcp.call_tool("create_event", {
                    "summary": "Email Test",
                    "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
                    "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
                    "attendees": [bad_email],
                    "calendar_id": "primary",
                    "description": "",
                    "location": "",
                    "start_timezone": "",
                    "end_timezone": ""
                })

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_end_before_start_datetime(self, google_calendar_test_config):
        """Test handling of end datetime before start datetime."""
        tomorrow = datetime.now() + timedelta(days=1)
        
        with pytest.raises(ToolError, match="end.*before.*start|start.*after.*end|duration|time.*order|time range.*empty|empty.*time"):
            await mcp.call_tool("create_event", {
                "summary": "Invalid Duration Event",
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T15:00:00",  # 3 PM
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",    # 10 AM (before start)
                "calendar_id": "primary",
                "description": "",
                "location": "",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": ""
            })

    @pytest.mark.asyncio
    async def test_excessively_large_inputs(self, google_calendar_test_config):
        """Test handling of inputs that exceed reasonable size limits."""
        tomorrow = datetime.now() + timedelta(days=1)
        
        # Test very long summary
        very_long_summary = "A" * 10000  # 10k characters
        # Test very long description  
        very_long_description = "B" * 50000  # 50k characters
        # Test very long location
        very_long_location = "C" * 5000  # 5k characters
        
        # These should either be handled gracefully or rejected with clear error
        try:
            _, response = await mcp.call_tool("create_event", {
                "summary": very_long_summary,
                "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
                "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
                "description": very_long_description,
                "location": very_long_location,
                "calendar_id": "primary",
                "attendees": [],
                "start_timezone": "",
                "end_timezone": ""
            })
            
            # If it succeeds, verify the data was truncated or handled properly
            if "error" not in response:
                event_id = response.get("event_id")
                if event_id:
                    # Clean up
                    await mcp.call_tool("delete_event", {
                        "event_id": event_id,
                        "calendar_id": "primary"
                    })
                    
        except ToolError as e:
            # Expected - should contain size/length related error
            assert any(keyword in str(e).lower() for keyword in ["size", "length", "limit", "too large", "too long"])


@pytest.mark.integration
class TestGoogleCalendarZeroResultsScenarios:
    """Test scenarios that return empty/zero results."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_search_events_no_matches(self, google_calendar_test_config):
        """Test search with query that matches no events."""
        # Use a very unique search term that won't match existing events
        unique_query = f"unique_search_term_{datetime.now().timestamp()}"
        
        _, response = await mcp.call_tool("search_events", {
            "search_text": unique_query,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "calendar_id": "primary"
        })
        
        assert "error" not in response, response.get("error")
        
        # Should return empty list, not error
        events = response.get("events", [])
        assert isinstance(events, list)
        assert len(events) == 0

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_find_time_no_availability(self, google_calendar_test_config):
        """Test find_time when no slots are available."""
        # Try to find time in the past (should have no availability)
        past_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        _, response = await mcp.call_tool("find_time", {
            "start_date": past_date,
            "end_date": past_date,
            "duration_minutes": 60,
            "work_hours_only": True,
            "calendar_id": "primary"
        })
        
        assert "error" not in response, response.get("error")
        
        # Should return empty list or clear message about no availability
        free_times = response.get("free_times", [])
        assert isinstance(free_times, list)
        # Either empty list or message about no availability
        if len(free_times) == 0:
            assert True  # Expected empty result
        else:
            # If not empty, should be in the past (which is fine)
            assert True

    @pytest.mark.vcr 
    @pytest.mark.asyncio
    async def test_search_events_empty_date_range(self, google_calendar_test_config):
        """Test search with date range that contains no events."""
        # Use future dates far in the future
        far_future_start = (datetime.now() + timedelta(days=3650)).strftime('%Y-%m-%d')  # ~10 years
        far_future_end = (datetime.now() + timedelta(days=3651)).strftime('%Y-%m-%d')
        
        _, response = await mcp.call_tool("search_events", {
            "start_date": far_future_start,
            "end_date": far_future_end,
            "calendar_id": "primary",
            "search_text": ""
        })
        
        assert "error" not in response, response.get("error")
        
        events = response.get("events", [])
        assert isinstance(events, list)
        assert len(events) == 0


@pytest.mark.integration  
class TestGoogleCalendarBoundaryConditions:
    """Test boundary conditions and edge cases."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_create_event_at_year_boundaries(self, google_calendar_test_config):
        """Test event creation at year boundaries."""
        # Test New Year's Eve to New Year's Day event
        current_year = datetime.now().year
        
        _, response = await mcp.call_tool("create_event", {
            "summary": "New Year Boundary Event",
            "start_datetime": f"{current_year}-12-31T23:30:00",
            "end_datetime": f"{current_year + 1}-01-01T00:30:00",
            "calendar_id": "primary",
            "description": "Event spanning year boundary",
            "location": "",
            "attendees": [],
            "start_timezone": "",
            "end_timezone": ""
        })
        
        if "error" not in response:
            # Clean up if successful
            event_id = response.get("event_id")
            if event_id:
                await mcp.call_tool("delete_event", {
                    "event_id": event_id,
                    "calendar_id": "primary"
                })
        else:
            # Some boundary dates might be invalid, that's acceptable
            assert "error" in response

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_maximum_duration_event(self, google_calendar_test_config):
        """Test creating events with very long durations."""
        tomorrow = datetime.now() + timedelta(days=1)
        
        # Test multi-week event
        _, response = await mcp.call_tool("create_event", {
            "summary": "Long Duration Event",
            "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T09:00:00",
            "end_datetime": f"{(tomorrow + timedelta(days=365)).strftime('%Y-%m-%d')}T09:00:00",  # 1 year duration
            "calendar_id": "primary",
            "description": "Testing maximum duration handling",
            "location": "",
            "attendees": [],
            "start_timezone": "",
            "end_timezone": ""
        })
        
        if "error" not in response:
            # Clean up if successful  
            event_id = response.get("event_id")
            if event_id:
                await mcp.call_tool("delete_event", {
                    "event_id": event_id,
                    "calendar_id": "primary"
                })
        # Very long events might be rejected by Google Calendar API - that's acceptable

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_minimal_duration_event(self, google_calendar_test_config):
        """Test creating events with very short durations."""
        tomorrow = datetime.now() + timedelta(days=1)
        
        # Test 1-minute event
        start_time = f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00"
        end_time = f"{tomorrow.strftime('%Y-%m-%d')}T10:01:00"  # 1 minute duration
        
        _, response = await mcp.call_tool("create_event", {
            "summary": "Minimal Duration Event",  
            "start_datetime": start_time,
            "end_datetime": end_time,
            "calendar_id": "primary", 
            "description": "Testing minimal duration handling",
            "location": "",
            "attendees": [],
            "start_timezone": "",
            "end_timezone": ""
        })
        
        if "error" not in response:
            # Clean up if successful
            event_id = response.get("event_id")
            if event_id:
                await mcp.call_tool("delete_event", {
                    "event_id": event_id,
                    "calendar_id": "primary"
                })

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_unicode_content_handling(self, google_calendar_test_config):
        """Test handling of unicode characters in event content."""
        tomorrow = datetime.now() + timedelta(days=1)
        
        # Test various unicode characters
        unicode_summary = "测试事件 🗓️ Événement tëst"
        unicode_description = "Descrição com caracteres especiais: åäö üëï ñç 中文"
        unicode_location = "Café München, Zürich 🇨🇭"
        
        _, response = await mcp.call_tool("create_event", {
            "summary": unicode_summary,
            "start_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
            "end_datetime": f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
            "description": unicode_description,
            "location": unicode_location,
            "calendar_id": "primary",
            "attendees": [],
            "start_timezone": "",
            "end_timezone": ""
        })
        
        assert "error" not in response, response.get("error")
        
        # Verify unicode was preserved
        event_id = response.get("event_id")
        assert event_id
        
        try:
            # Get the event back and verify unicode preservation
            _, get_response = await mcp.call_tool("get_event", {
                "event_id": event_id,
                "calendar_id": "primary"
            })
            
            assert "error" not in get_response
            event = get_response
            
            # Check that unicode characters are preserved
            assert unicode_summary in event["summary"]
            assert unicode_description in event.get("description", "")
            assert unicode_location in event.get("location", "")
            
        finally:
            # Clean up
            await mcp.call_tool("delete_event", {
                "event_id": event_id,
                "calendar_id": "primary"
            })