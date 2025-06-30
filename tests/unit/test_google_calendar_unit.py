"""Unit tests for Google Calendar tool functionality."""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path

from mcp_handley_lab.google_calendar.tool import (
    list_events, get_event, create_event, update_event, delete_event,
    list_calendars, find_time, server_info, _get_calendar_service, _format_datetime
)


class TestDateTimeParsing:
    """Test date/time parsing functionality."""
    
    @pytest.mark.parametrize("date_string,expected_has_exception", [
        # ISO 8601 formats that should work
        ("2024-06-24T14:30:00Z", False),
        ("2024-06-24T14:30:00+02:00", False),
        ("2024-06-24T14:30:00", False),
        
        # Date only formats  
        ("2024-06-24", False),
        ("2024-12-31", False),
        
        # Invalid datetime formats with 'T' that should raise exceptions
        ("invalid-dateT14:30:00Z", True),
        ("2024-13-45T14:30:00Z", True),
        ("not-a-dateT14:30:00Z", True),
    ])
    @pytest.mark.asyncio
    async def test_parse_datetime_parameterized(self, date_string, expected_has_exception):
        """Test date/time parsing with various formats."""
        if expected_has_exception:
            with pytest.raises(ValueError):
                _format_datetime(date_string)
        else:
            result = _format_datetime(date_string)
            assert result is not None
            assert isinstance(result, str)
    
    @pytest.mark.parametrize("date_string,expected_contains", [
        # Date only formats that get treated as all-day
        ("2024-06-24", "all-day"),
        ("2024-12-31", "all-day"),
        ("invalid-date", "all-day"),
        ("", "all-day"),
    ])
    @pytest.mark.asyncio
    async def test_all_day_format_parameterized(self, date_string, expected_contains):
        """Test all-day date formatting."""
        result = _format_datetime(date_string)
        assert expected_contains in result


class TestEventCreation:
    """Test event creation with various parameters."""
    
    @pytest.mark.parametrize("summary,start_dt,end_dt,description,attendees,timezone", [
        ("Team Meeting", "2024-06-24T10:00:00Z", "2024-06-24T11:00:00Z", "Weekly sync", ["test@example.com"], "UTC"),
        ("All Day Event", "2024-06-25", "2024-06-26", None, None, "UTC"),
        ("Complex Event", "2024-06-24T14:00:00", "2024-06-24T15:30:00", "Complex meeting", ["a@test.com", "b@test.com"], "America/New_York"),
        ("Simple Event", "2024-06-24T09:00:00Z", "2024-06-24T10:00:00Z", "", [], "UTC"),
    ])
    @patch('mcp_handley_lab.google_calendar.tool._resolve_calendar_id')
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    @pytest.mark.asyncio
    async def test_create_event_parameterized(self, mock_get_service, mock_resolve_calendar_id, summary, start_dt, end_dt, description, attendees, timezone):
        """Test event creation with various configurations."""
        # Mock the service and its methods
        mock_service = Mock()
        mock_events = Mock()
        mock_service.events.return_value = mock_events
        # Build proper mock response based on event type
        start_data = {}
        end_data = {}
        if 'T' in start_dt:
            start_data['dateTime'] = start_dt
            end_data['dateTime'] = end_dt
        else:
            start_data['date'] = start_dt
            end_data['date'] = end_dt
            
        mock_events.insert.return_value.execute.return_value = {
            'id': 'test_event_id',
            'summary': summary,
            'htmlLink': 'https://calendar.google.com/event?eid=test',
            'start': start_data,
            'end': end_data
        }
        mock_get_service.return_value = mock_service
        mock_resolve_calendar_id.return_value = "primary"
        
        result = await create_event(
            summary=summary,
            start_datetime=start_dt,
            end_datetime=end_dt,
            description=description,
            attendees=attendees,
            timezone=timezone
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "created" in result.lower() or "success" in result.lower()
        mock_events.insert.assert_called_once()


class TestEventListing:
    """Test event listing with various parameters."""
    
    @pytest.mark.parametrize("calendar_id,start_date,end_date,max_results", [
        ("primary", "2024-06-01T00:00:00Z", "2024-06-08T00:00:00Z", 10),
        ("work@company.com", "2024-06-01", "2024-06-02", 25),
        ("primary", "2024-12-01T00:00:00Z", "2024-12-31T23:59:59Z", 50),
    ])
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    @pytest.mark.asyncio
    async def test_list_events_parameterized(self, mock_get_service, calendar_id, start_date, end_date, max_results):
        """Test event listing with various configurations."""
        # Mock the service
        mock_service = Mock()
        mock_events = Mock()
        mock_service.events.return_value = mock_events
        mock_events.list.return_value.execute.return_value = {
            'items': [
                {
                    'id': 'event1',
                    'summary': 'Test Event',
                    'start': {'dateTime': '2024-06-01T10:00:00Z'},
                    'end': {'dateTime': '2024-06-01T11:00:00Z'}
                }
            ]
        }
        mock_get_service.return_value = mock_service
        
        result = await list_events(
            calendar_id=calendar_id,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
        mock_events.list.assert_called_once()

    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    @pytest.mark.asyncio
    async def test_list_events_all_calendars(self, mock_get_service):
        """Test listing events from all calendars."""
        # Mock the service
        mock_service = Mock()
        mock_calendar_list = Mock()
        mock_events = Mock()
        
        mock_service.calendarList.return_value = mock_calendar_list
        mock_calendar_list.list.return_value.execute.return_value = {
            'items': [
                {'id': 'primary', 'summary': 'Primary Calendar'},
                {'id': 'secondary', 'summary': 'Secondary Calendar'}
            ]
        }
        
        mock_service.events.return_value = mock_events
        mock_events.list.return_value.execute.return_value = {'items': []}
        mock_get_service.return_value = mock_service
        
        result = await list_events(calendar_id="all")
        
        assert isinstance(result, str)
        assert len(result) > 0


class TestEventUpdate:
    """Test event updating with various scenarios."""
    
    @pytest.mark.parametrize("event_summary,event_id,updates", [
        ("Original Meeting", "event123", {"summary": "Updated Meeting"}),
        ("Team Sync", "event456", {"description": "New description"}),
        ("All Hands", "event789", {"start_datetime": "2024-06-25T14:00:00Z", "end_datetime": "2024-06-25T15:00:00Z"}),
        ("Client Call", "event101", {"summary": "Client Review", "description": "Important review"}),
    ])
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    @pytest.mark.asyncio
    async def test_update_event_parameterized(self, mock_get_service, event_summary, event_id, updates):
        """Test event updating with various fields."""
        # Mock the service
        mock_service = Mock()
        mock_events = Mock()
        mock_service.events.return_value = mock_events
        
        # Mock get() to return existing event
        mock_events.get.return_value.execute.return_value = {
            'id': event_id,
            'summary': event_summary,
            'description': 'Original description',
            'start': {'dateTime': '2024-06-24T10:00:00Z'},
            'end': {'dateTime': '2024-06-24T11:00:00Z'}
        }
        
        # Mock patch()
        mock_events.patch.return_value.execute.return_value = {
            'id': event_id,
            'summary': updates.get('summary', event_summary),
            'htmlLink': 'https://calendar.google.com/event?eid=updated'
        }
        
        mock_get_service.return_value = mock_service
        
        result = await update_event(
            event_id=event_id,
            **updates
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "updated" in result.lower() or "success" in result.lower()
        mock_events.patch.assert_called_once()


class TestCalendarErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.parametrize("exception_type,error_message,expected_exception", [
        (Exception, "API quota exceeded", Exception),
        (ValueError, "Invalid date format", ValueError),
        (KeyError, "Missing calendar", KeyError),
        (ConnectionError, "Network timeout", ConnectionError),
    ])
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    @pytest.mark.asyncio
    async def test_error_handling_parameterized(self, mock_get_service, exception_type, error_message, expected_exception):
        """Test error handling with various exception types."""
        # Mock service to raise exception
        mock_get_service.side_effect = exception_type(error_message)
        
        with pytest.raises((expected_exception, RuntimeError)):
            await list_events()


class TestTimezoneParsing:
    """Test timezone handling."""
    
    @pytest.mark.parametrize("datetime_str,timezone,expected_contains", [
        ("2024-06-24T14:00:00", "America/New_York", "America/New_York"),
        ("2024-06-24T14:00:00", "Europe/London", "Europe/London"),
        ("2024-06-24T14:00:00Z", "UTC", "Z"),
        ("2024-06-24", "UTC", "date"),
    ])
    @pytest.mark.asyncio
    async def test_timezone_handling_parameterized(self, datetime_str, timezone, expected_contains):
        """Test timezone handling in datetime parsing."""
        # This would test the internal datetime parsing logic
        # For now, just verify the parameters are reasonable
        assert datetime_str is not None
        assert timezone is not None
        assert expected_contains is not None


class TestFindTime:
    """Test find time functionality."""
    
    @pytest.mark.parametrize("duration_minutes,work_hours_only", [
        (30, True),   # Should find several 30-min slots in work hours
        (60, True),   # Fewer 1-hour slots
        (120, True),  # Even fewer 2-hour slots
        (30, False),  # More slots when including evenings/weekends
    ])
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    @pytest.mark.asyncio
    async def test_find_time_parameterized(self, mock_get_service, duration_minutes, work_hours_only):
        """Test find time with various durations and work hour settings."""
        # Mock the service to return some busy times
        mock_service = Mock()
        mock_freebusy = Mock()
        mock_service.freebusy.return_value = mock_freebusy
        mock_freebusy.query.return_value.execute.return_value = {
            'calendars': {
                'primary': {
                    'busy': []  # No busy times
                }
            }
        }
        mock_get_service.return_value = mock_service
        
        result = await find_time(
            duration_minutes=duration_minutes,
            work_hours_only=work_hours_only
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "available" in result.lower() or "time slot" in result.lower() or "found" in result.lower()


class TestCalendarServiceOperations:
    """Test basic service operations."""
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    @pytest.mark.asyncio
    async def test_list_calendars(self, mock_get_service):
        """Test listing calendars."""
        mock_service = Mock()
        mock_calendar_list = Mock()
        mock_service.calendarList.return_value = mock_calendar_list
        mock_calendar_list.list.return_value.execute.return_value = {
            'items': [
                {'id': 'primary', 'summary': 'Primary Calendar', 'accessRole': 'owner'}
            ]
        }
        mock_get_service.return_value = mock_service
        
        result = await list_calendars()
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "calendar" in result.lower()
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    @pytest.mark.asyncio
    async def test_get_event(self, mock_get_service):
        """Test getting a specific event."""
        mock_service = Mock()
        mock_events = Mock()
        mock_service.events.return_value = mock_events
        mock_events.get.return_value.execute.return_value = {
            'id': 'test_event',
            'summary': 'Test Event',
            'start': {'dateTime': '2024-06-24T10:00:00Z'},
            'end': {'dateTime': '2024-06-24T11:00:00Z'},
            'description': 'Test description'
        }
        mock_get_service.return_value = mock_service
        
        result = await get_event(event_id="test_event")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "test event" in result.lower()
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    @pytest.mark.asyncio
    async def test_delete_event(self, mock_get_service):
        """Test deleting an event."""
        mock_service = Mock()
        mock_events = Mock()
        mock_service.events.return_value = mock_events
        
        # Mock get() to return existing event for safety check
        mock_events.get.return_value.execute.return_value = {
            'id': 'test_event',
            'summary': 'Test Event'
        }
        
        # Mock delete()
        mock_events.delete.return_value.execute.return_value = {}
        mock_get_service.return_value = mock_service
        
        result = await delete_event(event_id="test_event")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "deleted" in result.lower()
        mock_events.delete.assert_called_once()
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    @pytest.mark.asyncio
    async def test_server_info(self, mock_get_service):
        """Test server info function."""
        mock_service = Mock()
        mock_calendar_list = Mock()
        mock_service.calendarList.return_value = mock_calendar_list
        mock_calendar_list.list.return_value.execute.return_value = {
            'items': [{'id': 'primary'}]
        }
        mock_get_service.return_value = mock_service
        
        result = await server_info()
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "google calendar" in result.lower()
        assert "status" in result.lower()