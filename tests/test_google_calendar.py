"""Tests for Google Calendar tool."""
import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timedelta
from pathlib import Path
import pickle
import os

from mcp_handley_lab.google_calendar.tool import (
    list_events, get_event, create_event, update_event, delete_event,
    list_calendars, find_time, server_info,
    _get_calendar_service, _resolve_calendar_id, _format_datetime
)


@pytest.fixture
def mock_service():
    """Mock Google Calendar service."""
    service = Mock()
    
    # Mock calendar list
    service.calendarList().list().execute.return_value = {
        'items': [
            {
                'id': 'primary',
                'summary': 'Primary Calendar',
                'accessRole': 'owner',
                'colorId': '1'
            },
            {
                'id': 'work@example.com',
                'summary': 'Work',
                'accessRole': 'writer',
                'colorId': '2'
            }
        ]
    }
    
    # Mock events list
    service.events().list().execute.return_value = {
        'items': [
            {
                'id': 'event1',
                'summary': 'Test Meeting',
                'start': {'dateTime': '2025-01-15T10:00:00Z'},
                'end': {'dateTime': '2025-01-15T11:00:00Z'},
                'description': 'Test description',
                'location': 'Conference Room A'
            },
            {
                'id': 'event2',
                'summary': 'All Day Event',
                'start': {'date': '2025-01-16'},
                'end': {'date': '2025-01-17'}
            }
        ]
    }
    
    # Mock single event get
    service.events().get().execute.return_value = {
        'id': 'event1',
        'summary': 'Test Meeting',
        'start': {'dateTime': '2025-01-15T10:00:00Z'},
        'end': {'dateTime': '2025-01-15T11:00:00Z'},
        'description': 'Test description',
        'location': 'Conference Room A',
        'attendees': [
            {'email': 'user1@example.com', 'responseStatus': 'accepted'},
            {'email': 'user2@example.com', 'responseStatus': 'needsAction'}
        ],
        'created': '2025-01-10T09:00:00Z',
        'updated': '2025-01-10T09:30:00Z'
    }
    
    # Mock event creation
    service.events().insert().execute.return_value = {
        'id': 'new_event_id',
        'summary': 'New Meeting',
        'start': {'dateTime': '2025-01-20T14:00:00Z'},
        'end': {'dateTime': '2025-01-20T15:00:00Z'}
    }
    
    # Mock event update
    service.events().update().execute.return_value = {
        'id': 'event1',
        'summary': 'Updated Meeting',
        'start': {'dateTime': '2025-01-15T10:00:00Z'},
        'end': {'dateTime': '2025-01-15T11:00:00Z'}
    }
    
    # Mock freebusy query
    service.freebusy().query().execute.return_value = {
        'calendars': {
            'primary': {
                'busy': [
                    {
                        'start': '2025-01-15T10:00:00Z',
                        'end': '2025-01-15T11:00:00Z'
                    }
                ]
            }
        }
    }
    
    return service


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_format_datetime_with_time(self):
        """Test datetime formatting with time."""
        dt_str = "2025-01-15T10:00:00Z"
        result = _format_datetime(dt_str)
        assert "2025-01-15 10:00:00" in result
    
    def test_format_datetime_date_only(self):
        """Test datetime formatting for all-day events."""
        dt_str = "2025-01-15"
        result = _format_datetime(dt_str)
        assert result == "2025-01-15 (all-day)"
    
    def test_resolve_calendar_id_primary(self, mock_service):
        """Test resolving primary calendar ID."""
        result = _resolve_calendar_id("primary", mock_service)
        assert result == "primary"
    
    def test_resolve_calendar_id_email(self, mock_service):
        """Test resolving email calendar ID."""
        result = _resolve_calendar_id("test@example.com", mock_service)
        assert result == "test@example.com"
    
    def test_resolve_calendar_id_by_name(self, mock_service):
        """Test resolving calendar ID by name."""
        result = _resolve_calendar_id("Work", mock_service)
        assert result == "work@example.com"
    
    def test_resolve_calendar_id_not_found(self, mock_service):
        """Test resolving unknown calendar ID."""
        result = _resolve_calendar_id("unknown", mock_service)
        assert result == "unknown"
    
    def test_resolve_calendar_id_api_error(self, mock_service):
        """Test resolving calendar ID when API call fails."""
        from googleapiclient.errors import HttpError
        mock_service.calendarList().list().execute.side_effect = HttpError(
            Mock(status=403), b'Forbidden'
        )
        
        result = _resolve_calendar_id("unknown", mock_service)
        assert result == "unknown"


class TestGoogleCalendarService:
    """Test Google Calendar service setup."""
    
    @patch('mcp_handley_lab.google_calendar.tool.build')
    @patch('mcp_handley_lab.google_calendar.tool.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pickle.load')
    def test_get_calendar_service_existing_token(self, mock_pickle_load, mock_file, mock_exists, mock_build):
        """Test getting service with existing valid token."""
        # Mock valid credentials
        mock_creds = Mock()
        mock_creds.valid = True
        mock_pickle_load.return_value = mock_creds
        mock_exists.return_value = True
        
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        result = _get_calendar_service()
        
        assert result == mock_service
        mock_build.assert_called_once_with('calendar', 'v3', credentials=mock_creds)
    
    @patch('mcp_handley_lab.google_calendar.tool.build')
    @patch('mcp_handley_lab.google_calendar.tool.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pickle.load')
    @patch('pickle.dump')
    @patch('mcp_handley_lab.google_calendar.tool.Request')
    def test_get_calendar_service_expired_token_refresh(self, mock_request, mock_pickle_dump, 
                                                       mock_pickle_load, mock_file, mock_exists, mock_build):
        """Test getting service with expired token that can be refreshed."""
        # Mock expired but refreshable credentials
        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_pickle_load.return_value = mock_creds
        mock_exists.return_value = True
        
        # After refresh, credentials become valid
        def side_effect(*args):
            mock_creds.valid = True
        mock_creds.refresh.side_effect = side_effect
        
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        result = _get_calendar_service()
        
        assert result == mock_service
        mock_creds.refresh.assert_called_once()
        mock_pickle_dump.assert_called_once()
    
    @patch('mcp_handley_lab.google_calendar.tool.build')
    @patch('mcp_handley_lab.google_calendar.tool.Path')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pickle.load')
    @patch('pickle.dump')
    @patch('mcp_handley_lab.google_calendar.tool.InstalledAppFlow')
    def test_get_calendar_service_new_auth_flow(self, mock_flow_class, mock_pickle_dump,
                                               mock_pickle_load, mock_file, mock_path_class, mock_build):
        """Test getting service with new OAuth flow."""
        # Mock invalid credentials that cannot be refreshed
        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = None
        mock_pickle_load.return_value = mock_creds
        
        # Mock Path instances - both files exist
        mock_token_file = Mock()
        mock_token_file.exists.return_value = True
        mock_token_file.parent.mkdir = Mock()
        mock_credentials_file = Mock() 
        mock_credentials_file.exists.return_value = True
        
        def mock_path_side_effect(path):
            if 'token' in str(path):
                return mock_token_file
            else:
                return mock_credentials_file
        
        mock_path_class.side_effect = mock_path_side_effect
        
        # Mock OAuth flow
        mock_flow = Mock()
        mock_new_creds = Mock()
        mock_flow.run_local_server.return_value = mock_new_creds
        mock_flow_class.from_client_secrets_file.return_value = mock_flow
        
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        result = _get_calendar_service()
        
        assert result == mock_service
        mock_flow_class.from_client_secrets_file.assert_called_once()
        mock_flow.run_local_server.assert_called_once_with(port=0)
        mock_pickle_dump.assert_called_once()
    
    @patch('mcp_handley_lab.google_calendar.tool.build')
    @patch('mcp_handley_lab.google_calendar.tool.settings')
    def test_get_calendar_service_no_credentials(self, mock_settings, mock_build):
        """Test getting service without credentials file."""
        # Create temp files that don't exist
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_token_path = Mock()
            mock_token_path.exists.return_value = False
            mock_credentials_path = Mock()
            mock_credentials_path.exists.return_value = False
            
            mock_settings.google_token_path = mock_token_path
            mock_settings.google_credentials_path = mock_credentials_path
            
            with pytest.raises(FileNotFoundError) as exc_info:
                _get_calendar_service()
        
        assert "Google Calendar credentials file not found" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool.build')
    @patch('mcp_handley_lab.google_calendar.tool.settings')
    @patch('pickle.dump')
    @patch('mcp_handley_lab.google_calendar.tool.InstalledAppFlow')
    def test_get_calendar_service_no_existing_token(self, mock_flow_class, mock_pickle_dump,
                                                   mock_settings, mock_build):
        """Test getting service when no token file exists."""
        # Mock paths
        mock_token_path = Mock()
        mock_token_path.exists.return_value = False
        mock_token_path.parent.mkdir = Mock()
        
        mock_credentials_path = Mock()
        mock_credentials_path.exists.return_value = True
        
        mock_settings.google_token_path = mock_token_path
        mock_settings.google_credentials_path = mock_credentials_path
        
        # Mock OAuth flow
        mock_flow = Mock()
        mock_new_creds = Mock()
        mock_flow.run_local_server.return_value = mock_new_creds
        mock_flow_class.from_client_secrets_file.return_value = mock_flow
        
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        with patch('builtins.open', mock_open()):
            result = _get_calendar_service()
        
        assert result == mock_service
        mock_flow_class.from_client_secrets_file.assert_called_once()
        mock_pickle_dump.assert_called_once()


class TestListEvents:
    """Test list_events function."""
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_list_events_basic(self, mock_get_service, mock_service):
        """Test basic event listing."""
        mock_get_service.return_value = mock_service
        
        result = list_events()
        
        assert "Found 2 events" in result
        assert "Test Meeting" in result
        assert "All Day Event" in result
        assert "event1" in result
        assert "event2" in result
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_list_events_with_dates(self, mock_get_service, mock_service):
        """Test event listing with specific date range."""
        mock_get_service.return_value = mock_service
        
        result = list_events(
            start_date="2025-01-15",
            end_date="2025-01-16",
            max_results=10
        )
        
        assert "Found 2 events" in result
        mock_service.events().list.assert_called()
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_list_events_all_calendars(self, mock_get_service, mock_service):
        """Test listing events from all calendars."""
        mock_get_service.return_value = mock_service
        
        result = list_events(calendar_id="all")
        
        assert "Calendar:" in result
        # Should call list for each calendar
        assert mock_service.events().list.call_count >= 2
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_list_events_no_events(self, mock_get_service, mock_service):
        """Test listing when no events found."""
        mock_get_service.return_value = mock_service
        mock_service.events().list().execute.return_value = {'items': []}
        
        result = list_events()
        
        assert "No events found" in result
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_list_events_api_error(self, mock_get_service, mock_service):
        """Test handling API errors."""
        mock_get_service.return_value = mock_service
        from googleapiclient.errors import HttpError
        mock_service.events().list().execute.side_effect = HttpError(
            Mock(status=400), b'Bad Request'
        )
        
        with pytest.raises(RuntimeError) as exc_info:
            list_events()
        
        assert "Google Calendar API error" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_list_events_service_error(self, mock_get_service):
        """Test handling service connection errors."""
        mock_get_service.side_effect = Exception("Connection failed")
        
        with pytest.raises(RuntimeError) as exc_info:
            list_events()
        
        assert "Calendar service error" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_list_events_all_calendars_with_errors(self, mock_get_service, mock_service):
        """Test listing all calendars when some calendars have access errors."""
        mock_get_service.return_value = mock_service
        
        # Mock calendar list with multiple calendars
        mock_service.calendarList().list().execute.return_value = {
            'items': [
                {'id': 'calendar1', 'summary': 'Calendar 1'},
                {'id': 'calendar2', 'summary': 'Calendar 2'},
                {'id': 'calendar3', 'summary': 'Calendar 3'}
            ]
        }
        
        # Mock events list to succeed for some calendars and fail for others
        from googleapiclient.errors import HttpError
        def mock_events_list(*args, **kwargs):
            calendar_id = kwargs.get('calendarId', '')
            if calendar_id == 'calendar2':
                # Simulate access denied for one calendar
                raise HttpError(Mock(status=403), b'Forbidden')
            return Mock(execute=Mock(return_value={'items': []}))
        
        mock_service.events().list.side_effect = mock_events_list
        
        result = list_events(calendar_id="all")
        
        assert "No events found" in result


class TestGetEvent:
    """Test get_event function."""
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_get_event_success(self, mock_get_service, mock_service):
        """Test successful event retrieval."""
        mock_get_service.return_value = mock_service
        
        result = get_event("event1")
        
        assert "Event Details:" in result
        assert "Test Meeting" in result
        assert "Test description" in result
        assert "Conference Room A" in result
        assert "user1@example.com" in result
        assert "accepted" in result
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_get_event_not_found(self, mock_get_service, mock_service):
        """Test event not found."""
        mock_get_service.return_value = mock_service
        from googleapiclient.errors import HttpError
        mock_response = Mock()
        mock_response.status = 404
        mock_service.events().get().execute.side_effect = HttpError(
            mock_response, b'Not Found'
        )
        
        with pytest.raises(ValueError) as exc_info:
            get_event("nonexistent")
        
        assert "not found" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_get_event_api_error(self, mock_get_service, mock_service):
        """Test get event API error."""
        mock_get_service.return_value = mock_service
        from googleapiclient.errors import HttpError
        mock_response = Mock()
        mock_response.status = 500
        mock_service.events().get().execute.side_effect = HttpError(
            mock_response, b'Internal Server Error'
        )
        
        with pytest.raises(RuntimeError) as exc_info:
            get_event("event1")
        
        assert "Google Calendar API error" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_get_event_service_error(self, mock_get_service):
        """Test get event service error."""
        mock_get_service.side_effect = Exception("Service unavailable")
        
        with pytest.raises(RuntimeError) as exc_info:
            get_event("event1")
        
        assert "Calendar service error" in str(exc_info.value)


class TestCreateEvent:
    """Test create_event function."""
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_create_event_success(self, mock_get_service, mock_service):
        """Test successful event creation."""
        mock_get_service.return_value = mock_service
        
        result = create_event(
            summary="New Meeting",
            start_datetime="2025-01-20T14:00:00",
            end_datetime="2025-01-20T15:00:00",
            description="Test event",
            attendees=["user@example.com"]
        )
        
        assert "Event created successfully" in result
        assert "New Meeting" in result
        assert "new_event_id" in result
        assert "user@example.com" in result
        
        # Verify the service was called correctly
        mock_service.events().insert().execute.assert_called_once()
        # Verify insert was called with the correct parameters
        assert mock_service.events().insert.called
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_create_event_all_day(self, mock_get_service, mock_service):
        """Test creating all-day event."""
        mock_get_service.return_value = mock_service
        
        result = create_event(
            summary="All Day Meeting",
            start_datetime="2025-01-20",
            end_datetime="2025-01-21"
        )
        
        assert "Event created successfully" in result
        
        # Verify date format is used for all-day events
        call_args = mock_service.events().insert.call_args
        event_body = call_args[1]['body']
        assert 'date' in event_body['start']
        assert 'date' in event_body['end']
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_create_event_api_error(self, mock_get_service, mock_service):
        """Test create event API error."""
        mock_get_service.return_value = mock_service
        from googleapiclient.errors import HttpError
        mock_service.events().insert().execute.side_effect = HttpError(
            Mock(status=400), b'Bad Request'
        )
        
        with pytest.raises(RuntimeError) as exc_info:
            create_event(
                summary="Test Meeting",
                start_datetime="2025-01-20T14:00:00",
                end_datetime="2025-01-20T15:00:00"
            )
        
        assert "Google Calendar API error" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_create_event_service_error(self, mock_get_service):
        """Test create event service error."""
        mock_get_service.side_effect = Exception("Service unavailable")
        
        with pytest.raises(RuntimeError) as exc_info:
            create_event(
                summary="Test Meeting",
                start_datetime="2025-01-20T14:00:00",
                end_datetime="2025-01-20T15:00:00"
            )
        
        assert "Calendar service error" in str(exc_info.value)


class TestUpdateEvent:
    """Test update_event function."""
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_update_event_success(self, mock_get_service, mock_service):
        """Test successful event update."""
        mock_get_service.return_value = mock_service
        
        result = update_event(
            event_summary="Test Meeting",
            event_id="event1",
            summary="Updated Meeting",
            description="Updated description"
        )
        
        assert "Event updated successfully" in result
        assert "Updated fields: summary, description" in result
        mock_service.events().update().execute.assert_called_once()
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_update_event_summary_mismatch(self, mock_get_service, mock_service):
        """Test update with wrong event summary."""
        mock_get_service.return_value = mock_service
        
        with pytest.raises(ValueError) as exc_info:
            update_event(
                event_summary="Wrong Summary",
                event_id="event1",
                summary="Updated Meeting"
            )
        
        assert "Event summary mismatch" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_update_event_no_changes(self, mock_get_service, mock_service):
        """Test update with no changes specified."""
        mock_get_service.return_value = mock_service
        
        result = update_event(
            event_summary="Test Meeting",
            event_id="event1"
        )
        
        assert "No updates specified" in result
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_update_event_with_date_times(self, mock_get_service, mock_service):
        """Test update with both date and datetime formats."""
        mock_get_service.return_value = mock_service
        
        # Test with timed event
        result = update_event(
            event_summary="Test Meeting",
            event_id="event1",
            start_datetime="2025-01-15T10:30:00",
            end_datetime="2025-01-15T11:30:00"
        )
        
        assert "Event updated successfully" in result
        
        # Test with all-day event
        result = update_event(
            event_summary="Test Meeting",
            event_id="event1",
            start_datetime="2025-01-15",
            end_datetime="2025-01-16"
        )
        
        assert "Event updated successfully" in result
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_update_event_not_found(self, mock_get_service, mock_service):
        """Test update event when event not found."""
        mock_get_service.return_value = mock_service
        from googleapiclient.errors import HttpError
        mock_response = Mock()
        mock_response.status = 404
        mock_service.events().get().execute.side_effect = HttpError(
            mock_response, b'Not Found'
        )
        
        with pytest.raises(ValueError) as exc_info:
            update_event(
                event_summary="Test Meeting",
                event_id="nonexistent",
                summary="Updated Meeting"
            )
        
        assert "not found" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_update_event_api_error(self, mock_get_service, mock_service):
        """Test update event API error."""
        mock_get_service.return_value = mock_service
        from googleapiclient.errors import HttpError
        mock_response = Mock()
        mock_response.status = 500
        mock_service.events().update().execute.side_effect = HttpError(
            mock_response, b'Internal Server Error'
        )
        
        with pytest.raises(RuntimeError) as exc_info:
            update_event(
                event_summary="Test Meeting",
                event_id="event1",
                summary="Updated Meeting"
            )
        
        assert "Google Calendar API error" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_update_event_service_error(self, mock_get_service):
        """Test update event service error."""
        mock_get_service.side_effect = Exception("Service unavailable")
        
        with pytest.raises(RuntimeError) as exc_info:
            update_event(
                event_summary="Test Meeting",
                event_id="event1",
                summary="Updated Meeting"
            )
        
        assert "Calendar service error" in str(exc_info.value)


class TestDeleteEvent:
    """Test delete_event function."""
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_delete_event_success(self, mock_get_service, mock_service):
        """Test successful event deletion."""
        mock_get_service.return_value = mock_service
        
        result = delete_event(
            event_summary="Test Meeting",
            event_id="event1"
        )
        
        assert "permanently deleted" in result
        assert "Test Meeting" in result
        mock_service.events().delete().execute.assert_called_once()
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_delete_event_summary_mismatch(self, mock_get_service, mock_service):
        """Test delete with wrong event summary."""
        mock_get_service.return_value = mock_service
        
        with pytest.raises(ValueError) as exc_info:
            delete_event(
                event_summary="Wrong Summary",
                event_id="event1"
            )
        
        assert "Event summary mismatch" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_delete_event_not_found(self, mock_get_service, mock_service):
        """Test delete event when event not found."""
        mock_get_service.return_value = mock_service
        from googleapiclient.errors import HttpError
        mock_response = Mock()
        mock_response.status = 404
        mock_service.events().get().execute.side_effect = HttpError(
            mock_response, b'Not Found'
        )
        
        with pytest.raises(ValueError) as exc_info:
            delete_event(
                event_summary="Test Meeting",
                event_id="nonexistent"
            )
        
        assert "not found" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_delete_event_api_error(self, mock_get_service, mock_service):
        """Test delete event API error."""
        mock_get_service.return_value = mock_service
        from googleapiclient.errors import HttpError
        mock_response = Mock()
        mock_response.status = 500
        mock_service.events().delete().execute.side_effect = HttpError(
            mock_response, b'Internal Server Error'
        )
        
        with pytest.raises(RuntimeError) as exc_info:
            delete_event(
                event_summary="Test Meeting",
                event_id="event1"
            )
        
        assert "Google Calendar API error" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_delete_event_service_error(self, mock_get_service):
        """Test delete event service error."""
        mock_get_service.side_effect = Exception("Service unavailable")
        
        with pytest.raises(RuntimeError) as exc_info:
            delete_event(
                event_summary="Test Meeting",
                event_id="event1"
            )
        
        assert "Calendar service error" in str(exc_info.value)


class TestListCalendars:
    """Test list_calendars function."""
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_list_calendars_success(self, mock_get_service, mock_service):
        """Test successful calendar listing."""
        mock_get_service.return_value = mock_service
        
        result = list_calendars()
        
        assert "Found 2 accessible calendars" in result
        assert "Primary Calendar" in result
        assert "Work" in result
        assert "owner" in result
        assert "writer" in result
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_list_calendars_empty(self, mock_get_service, mock_service):
        """Test calendar listing when no calendars found."""
        mock_get_service.return_value = mock_service
        mock_service.calendarList().list().execute.return_value = {'items': []}
        
        result = list_calendars()
        
        assert "No calendars found" in result
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_list_calendars_api_error(self, mock_get_service, mock_service):
        """Test list calendars API error."""
        mock_get_service.return_value = mock_service
        from googleapiclient.errors import HttpError
        mock_service.calendarList().list().execute.side_effect = HttpError(
            Mock(status=403), b'Forbidden'
        )
        
        with pytest.raises(RuntimeError) as exc_info:
            list_calendars()
        
        assert "Google Calendar API error" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_list_calendars_service_error(self, mock_get_service):
        """Test list calendars service error."""
        mock_get_service.side_effect = Exception("Service unavailable")
        
        with pytest.raises(RuntimeError) as exc_info:
            list_calendars()
        
        assert "Calendar service error" in str(exc_info.value)


class TestFindTime:
    """Test find_time function."""
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    @patch('mcp_handley_lab.google_calendar.tool.datetime')
    def test_find_time_success(self, mock_datetime, mock_get_service, mock_service):
        """Test successful free time finding."""
        mock_get_service.return_value = mock_service
        
        # Mock current time
        mock_now = datetime(2025, 1, 15, 9, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromisoformat = datetime.fromisoformat
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        result = find_time(duration_minutes=60)
        
        assert "free 60-minute slots" in result
        mock_service.freebusy().query().execute.assert_called_once()
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_find_time_with_dates(self, mock_get_service, mock_service):
        """Test free time finding with specific dates."""
        mock_get_service.return_value = mock_service
        
        result = find_time(
            start_date="2025-01-15",
            end_date="2025-01-16",
            duration_minutes=30,
            work_hours_only=False
        )
        
        mock_service.freebusy().query().execute.assert_called_once()
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_find_time_no_slots(self, mock_get_service, mock_service):
        """Test find time when no free slots available."""
        mock_get_service.return_value = mock_service
        
        # Mock busy times that cover the entire search period
        mock_service.freebusy().query().execute.return_value = {
            'calendars': {
                'primary': {
                    'busy': [
                        {
                            'start': '2025-01-15T00:00:00Z',
                            'end': '2025-01-22T23:59:59Z'
                        }
                    ]
                }
            }
        }
        
        result = find_time(
            start_date="2025-01-15",
            end_date="2025-01-22",
            duration_minutes=60
        )
        
        assert "No free 60-minute slots found" in result
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_find_time_api_error(self, mock_get_service, mock_service):
        """Test find time API error."""
        mock_get_service.return_value = mock_service
        from googleapiclient.errors import HttpError
        mock_service.freebusy().query().execute.side_effect = HttpError(
            Mock(status=400), b'Bad Request'
        )
        
        with pytest.raises(RuntimeError) as exc_info:
            find_time()
        
        assert "Google Calendar API error" in str(exc_info.value)
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_find_time_service_error(self, mock_get_service):
        """Test find time service error."""
        mock_get_service.side_effect = Exception("Service unavailable")
        
        with pytest.raises(RuntimeError) as exc_info:
            find_time()
        
        assert "Calendar service error" in str(exc_info.value)


class TestServerInfo:
    """Test server_info function."""
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_server_info_success(self, mock_get_service, mock_service):
        """Test successful server info."""
        mock_get_service.return_value = mock_service
        
        result = server_info()
        
        assert "Connected and ready" in result
        assert "API Connection: ✓ Active" in result
        assert "list_events" in result
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_server_info_connection_error(self, mock_get_service):
        """Test server info with connection error."""
        mock_get_service.side_effect = Exception("Connection failed")
        
        result = server_info()
        
        assert "Connection Error" in result
        assert "Connection failed" in result
    
    @patch('mcp_handley_lab.google_calendar.tool._get_calendar_service')
    def test_server_info_credentials_error(self, mock_get_service):
        """Test server info with credentials error."""
        mock_get_service.side_effect = FileNotFoundError("Credentials not found")
        
        result = server_info()
        
        assert "Configuration Error" in result
        assert "Credentials not found" in result


TEST_CREDENTIALS_FILE = Path("~/.google_calendar_test_credentials.json").expanduser()
GOOGLE_CALENDAR_AVAILABLE = TEST_CREDENTIALS_FILE.exists()

@pytest.mark.skipif(not GOOGLE_CALENDAR_AVAILABLE, reason="Google Calendar test credentials not available")
class TestGoogleCalendarIntegration:
    """Integration tests that use real Google Calendar API with test credentials."""
    
    @pytest.fixture(autouse=True)
    def setup_environment(self, monkeypatch):
        """Set up test environment with test credentials."""
        # Use monkeypatch to set environment variables for this test
        monkeypatch.setenv('GOOGLE_CREDENTIALS_FILE', str(TEST_CREDENTIALS_FILE))
        monkeypatch.setenv('GOOGLE_TOKEN_FILE', str(Path("~/.google_calendar_test_token.json").expanduser()))
        
        # Force reload the settings module to pick up new environment variables
        import importlib
        from mcp_handley_lab import google_calendar
        from mcp_handley_lab.common import config
        
        # Reload the config module to pick up the new environment variables
        importlib.reload(config)
        # Update the reference in the google_calendar.tool module
        google_calendar.tool.settings = config.settings
        
        yield
    
    def test_server_info_integration(self):
        """Test server info with real Google Calendar API."""
        
        try:
            result = server_info()
            
            # Should connect successfully and show available calendars
            assert "Google Calendar Tool Server Status" in result
            assert "Connected and ready" in result
            # Should show calendars are accessible
            assert "calendars accessible" in result.lower()
            
        except Exception as e:
            if "credentials" in str(e).lower() or "authentication" in str(e).lower():
                pytest.skip(f"Google Calendar authentication failed: {e}")
            else:
                raise
    
    def test_list_calendars_integration(self):
        """Test listing calendars with real API."""
        
        try:
            result = list_calendars()
            
            # Should return calendar list
            assert "calendars" in result.lower()
            assert "Found" in result
            
            # Should show calendar details
            assert "ID:" in result
            assert "Access:" in result
            assert "owner" in result or "reader" in result or "writer" in result
            
        except Exception as e:
            if "credentials" in str(e).lower() or "authentication" in str(e).lower():
                pytest.skip(f"Google Calendar authentication failed: {e}")
            else:
                raise
    
    def test_list_events_integration(self):
        """Test listing events with real API."""
        
        try:
            from datetime import datetime, timedelta
            
            # Get events for the next 7 days - use correct parameter names
            end_time = (datetime.now() + timedelta(days=7)).isoformat()
            
            result = list_events(
                calendar_id="primary",
                end_date=end_time,
                max_results=10
            )
            
            # Should return events list (may be empty, but should be valid format)
            assert "Found" in result and "events" in result or "No events found" in result
            
            # If events exist, should show proper formatting
            if "No events found" not in result:
                assert "•" in result  # Events should have bullet points
            
        except Exception as e:
            if "credentials" in str(e).lower() or "authentication" in str(e).lower():
                pytest.skip(f"Google Calendar authentication failed: {e}")
            else:
                raise
    
    def test_create_and_delete_event_integration(self):
        """Test creating and deleting an event with real API."""
        
        try:
            from datetime import datetime, timedelta
            
            # Create a test event for tomorrow
            start_time = datetime.now() + timedelta(days=1)
            end_time = start_time + timedelta(hours=1)
            
            test_summary = "[INTEGRATION TEST] Test Event - Safe to Delete"
            test_description = "This is a test event created by integration tests. Safe to delete."
            
            # Create the event
            create_result = create_event(
                calendar_id="primary",
                summary=test_summary,
                start_datetime=start_time.isoformat(),
                end_datetime=end_time.isoformat(),
                description=test_description
            )
            
            assert "Event created successfully" in create_result
            assert "Event ID:" in create_result
            
            # Extract event ID from result
            lines = create_result.split('\n')
            event_id_line = [line for line in lines if "Event ID:" in line][0]
            event_id = event_id_line.split("Event ID:")[1].strip()
            
            # Verify the event was created by getting it
            get_result = get_event(
                calendar_id="primary",
                event_id=event_id
            )
            
            assert test_summary in get_result
            assert test_description in get_result
            
            # Clean up: delete the test event
            delete_result = delete_event(
                event_summary=test_summary,
                event_id=event_id,
                calendar_id="primary"
            )
            
            assert "permanently deleted" in delete_result
            
        except Exception as e:
            if "credentials" in str(e).lower() or "authentication" in str(e).lower():
                pytest.skip(f"Google Calendar authentication failed: {e}")
            else:
                raise
    
    def test_find_time_integration(self):
        """Test finding available time with real API."""
        
        try:
            from datetime import datetime, timedelta
            
            # Look for free time in the next 3 days - use correct parameter names
            start_time = datetime.now()
            end_time = start_time + timedelta(days=3)
            
            result = find_time(
                calendar_id="primary",
                start_date=start_time.isoformat(),
                end_date=end_time.isoformat(),
                duration_minutes=60
            )
            
            # Should return available time slots
            assert ("free" in result.lower() and "slots" in result.lower()) or "No free" in result
            
            # If slots are found, should show proper formatting
            if "No free" not in result:
                assert "Found" in result and "slots" in result
            
        except Exception as e:
            if "credentials" in str(e).lower() or "authentication" in str(e).lower():
                pytest.skip(f"Google Calendar authentication failed: {e}")
            else:
                raise
    
    def test_update_event_integration(self):
        """Test updating an event with real API (if any events exist)."""
        
        try:
            # First try to find an existing event to update
            from datetime import datetime, timedelta
            
            # Look for events in the next 30 days
            end_time = (datetime.now() + timedelta(days=30)).isoformat()
            
            events_result = list_events(
                calendar_id="primary", 
                end_date=end_time,
                max_results=5
            )
            
            # If no events exist, create one for testing
            if "No events found" in events_result:
                # Create a test event first
                start_time = datetime.now() + timedelta(days=1)
                end_time_event = start_time + timedelta(hours=1)
                
                create_result = create_event(
                    calendar_id="primary",
                    summary="[INTEGRATION TEST] Update Test Event",
                    start_datetime=start_time.isoformat(),
                    end_datetime=end_time_event.isoformat(),
                    description="Test event for update testing"
                )
                
                # Extract event ID and test update
                lines = create_result.split('\n')
                event_id_line = [line for line in lines if "Event ID:" in line][0]
                event_id = event_id_line.split("Event ID:")[1].strip()
                
                # Update the event
                update_result = update_event(
                    event_summary="[INTEGRATION TEST] Update Test Event",
                    event_id=event_id,
                    calendar_id="primary",
                    summary="[INTEGRATION TEST] Updated Event Title",
                    description="Updated description via integration test"
                )
                
                assert "Event updated successfully" in update_result
                
                # Clean up: delete the test event
                delete_event(
                    event_summary="[INTEGRATION TEST] Updated Event Title",
                    event_id=event_id,
                    calendar_id="primary"
                )
            
            else:
                # If we found existing events, we'll skip updating them
                # to avoid modifying real calendar data
                pytest.skip("Skipping event update test to avoid modifying existing calendar events")
            
        except Exception as e:
            if "credentials" in str(e).lower() or "authentication" in str(e).lower():
                pytest.skip(f"Google Calendar authentication failed: {e}")
            else:
                raise