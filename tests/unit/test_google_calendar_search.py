"""Unit tests for Google Calendar search functionality."""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
import sys
sys.path.insert(0, 'src')

# Test the client-side filtering functionality directly since it doesn't require Google dependencies
from mcp_handley_lab.google_calendar.tool import _client_side_filter


class TestClientSideFilter:
    """Test client-side filtering functionality."""
    
    def test_basic_search(self):
        """Test basic search functionality."""
        events = [
            {'summary': 'Team Meeting', 'description': 'Weekly sync'},
            {'summary': 'Client Call', 'description': 'Important discussion'},
            {'summary': 'Code Review', 'description': 'Weekly team sync'}
        ]
        
        # Test basic search (case-insensitive by default)
        filtered = _client_side_filter(events, search_text="team")
        assert len(filtered) == 2  # "Team Meeting" and "Code Review" (contains "team")
        assert any('Team Meeting' in event['summary'] for event in filtered)
        assert any('Code Review' in event['summary'] for event in filtered)
        
        # Test case-sensitive search
        filtered = _client_side_filter(events, search_text="Team", case_sensitive=True)
        assert len(filtered) == 1  # Only "Team Meeting"
        assert filtered[0]['summary'] == 'Team Meeting'
    
    def test_and_or_logic(self):
        """Test AND vs OR search logic."""
        events = [
            {'summary': 'Team Meeting', 'description': 'Weekly sync'},
            {'summary': 'Client Call', 'description': 'Important discussion'},
            {'summary': 'Code Review', 'description': 'Weekly team sync'}
        ]
        
        # Test AND logic (default) - both terms must be present
        filtered = _client_side_filter(events, search_text="weekly sync")
        assert len(filtered) == 2  # Both events have "weekly" and "sync"
        
        # Test OR logic - any term can be present
        filtered = _client_side_filter(events, search_text="weekly important", match_all_terms=False)
        assert len(filtered) == 3  # All events match either "weekly" or "important"
    
    def test_field_specific_search(self):
        """Test searching in specific fields."""
        events = [
            {'summary': 'Meeting', 'description': 'Team discussion', 'location': 'Office'},
            {'summary': 'Call', 'description': 'Client update', 'location': 'Remote'}
        ]
        
        # Search only in summary
        filtered = _client_side_filter(events, search_text="team", search_fields=["summary"])
        assert len(filtered) == 0  # "team" is not in any summary
        
        # Search only in description
        filtered = _client_side_filter(events, search_text="team", search_fields=["description"])
        assert len(filtered) == 1  # "team" is in description of first event
        assert filtered[0]['summary'] == 'Meeting'
        
        # Search in multiple fields
        filtered = _client_side_filter(events, search_text="remote", search_fields=["summary", "location"])
        assert len(filtered) == 1  # "remote" is in location of second event
        assert filtered[0]['summary'] == 'Call'
    
    def test_attendee_search(self):
        """Test searching by attendees."""
        events = [
            {
                'summary': 'Team Meeting',
                'attendees': [
                    {'email': 'alice@company.com', 'displayName': 'Alice Smith'},
                    {'email': 'bob@company.com', 'displayName': 'Bob Jones'}
                ]
            },
            {
                'summary': 'Client Call',
                'attendees': [
                    {'email': 'client@external.com', 'displayName': 'Client Rep'}
                ]
            }
        ]
        
        # Search in attendees by name
        filtered = _client_side_filter(events, search_text="alice", search_fields=["attendees"])
        assert len(filtered) == 1
        assert filtered[0]['summary'] == 'Team Meeting'
        
        # Search by email domain
        filtered = _client_side_filter(events, search_text="company.com", search_fields=["attendees"])
        assert len(filtered) == 1  # Only first event has company.com attendees
        
        # Search by display name
        filtered = _client_side_filter(events, search_text="Smith", search_fields=["attendees"])
        assert len(filtered) == 1
        assert filtered[0]['summary'] == 'Team Meeting'
    
    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        events = [
            {'summary': 'Test Event'},
            {'description': 'Another event'}
        ]
        
        # Empty search text
        filtered = _client_side_filter(events, search_text="")
        assert len(filtered) == 2  # Returns all events
        
        # None search text
        filtered = _client_side_filter(events, search_text=None)
        assert len(filtered) == 2  # Returns all events
        
        # Search in non-existent field
        filtered = _client_side_filter(events, search_text="test", search_fields=["nonexistent"])
        assert len(filtered) == 0  # No matches
        
        # Empty events list
        filtered = _client_side_filter([], search_text="test")
        assert len(filtered) == 0
    
    def test_missing_fields(self):
        """Test handling of events with missing fields."""
        events_with_missing = [
            {'summary': 'Complete Event', 'description': 'Has everything'},
            {'summary': 'Partial Event'},  # Missing description
            {}  # Missing everything
        ]
        
        # Should handle missing fields gracefully
        filtered = _client_side_filter(events_with_missing, search_text="event")
        assert len(filtered) == 2  # Should find events with "event" in summary
        
        # Search in description field with missing descriptions
        filtered = _client_side_filter(events_with_missing, search_text="everything", search_fields=["description"])
        assert len(filtered) == 1  # Only first event has description with "everything"


class TestSearchIntegration:
    """Test search integration (requires mocking since we don't have Google dependencies)."""
    
    def test_chris_lovell_scenario(self):
        """Test the specific Chris Lovell search scenario."""
        # Simulate what the Google API would return
        mock_events = [
            {
                'id': 'event1',
                'summary': 'Chris Lovell start date',
                'start': {'dateTime': '2024-07-17T09:00:00Z'},
                'end': {'dateTime': '2024-07-17T10:00:00Z'},
                'description': 'New team member onboarding'
            },
            {
                'id': 'event2', 
                'summary': 'Team Meeting',
                'start': {'dateTime': '2024-07-15T10:00:00Z'},
                'description': 'Weekly sync'
            }
        ]
        
        # Test server-side filtering would find the Chris Lovell event
        # (In real usage, Google API 'q=Chris Lovell' would return only matching events)
        
        # Test client-side filtering can refine results
        filtered = _client_side_filter(mock_events, search_text="Chris Lovell")
        assert len(filtered) == 1
        assert filtered[0]['summary'] == 'Chris Lovell start date'
        
        # Test partial matching
        filtered = _client_side_filter(mock_events, search_text="Chris")
        assert len(filtered) == 1
        assert filtered[0]['summary'] == 'Chris Lovell start date'
        
        # Test searching in specific fields
        filtered = _client_side_filter(mock_events, search_text="onboarding", search_fields=["description"])
        assert len(filtered) == 1
        assert filtered[0]['summary'] == 'Chris Lovell start date'
    
    def test_natalie_scenario(self):
        """Test the Natalie Hogg search scenario."""
        mock_events = [
            {
                'id': 'event1',
                'summary': 'Natalie Hogg start date',
                'start': {'date': '2025-10-06'},
                'end': {'date': '2025-10-07'},
                'description': 'New team member starting'
            }
        ]
        
        # Test finding by first name only
        filtered = _client_side_filter(mock_events, search_text="Natalie")
        assert len(filtered) == 1
        
        # Test finding by last name only
        filtered = _client_side_filter(mock_events, search_text="Hogg") 
        assert len(filtered) == 1
        
        # Test finding by "start date" pattern
        filtered = _client_side_filter(mock_events, search_text="start date")
        assert len(filtered) == 1
        
        # Test OR logic for flexible matching
        filtered = _client_side_filter(mock_events, search_text="Natalie starting", match_all_terms=False)
        assert len(filtered) == 1  # Matches either "Natalie" OR "starting"


class TestSearchParameterValidation:
    """Test search parameter validation and combinations."""
    
    def test_search_field_combinations(self):
        """Test different search field combinations."""
        event = {
            'summary': 'Important Meeting',
            'description': 'Quarterly review with team',
            'location': 'Conference Room A',
            'attendees': [
                {'email': 'manager@company.com', 'displayName': 'Jane Manager'}
            ]
        }
        
        events = [event]
        
        # Test default fields (summary, description, location)
        filtered = _client_side_filter(events, search_text="quarterly")
        assert len(filtered) == 1
        
        # Test summary only
        filtered = _client_side_filter(events, search_text="quarterly", search_fields=["summary"])
        assert len(filtered) == 0  # "quarterly" is in description, not summary
        
        # Test all possible fields
        filtered = _client_side_filter(events, search_text="manager", 
                                     search_fields=["summary", "description", "location", "attendees"])
        assert len(filtered) == 1  # Found in attendees
    
    def test_complex_search_scenarios(self):
        """Test complex real-world search scenarios."""
        events = [
            {
                'summary': 'Weekly Team Standup',
                'description': 'Engineering team sync',
                'location': 'Room 101',
                'attendees': [{'email': 'alice@eng.com', 'displayName': 'Alice'}]
            },
            {
                'summary': 'Client Review Meeting', 
                'description': 'Quarterly business review',
                'location': 'Conference Room',
                'attendees': [{'email': 'client@external.com', 'displayName': 'Client'}]
            },
            {
                'summary': 'Engineering All-Hands',
                'description': 'Monthly team meeting',
                'location': 'Auditorium'
            }
        ]
        
        # Find all engineering-related events
        filtered = _client_side_filter(events, search_text="engineering", case_sensitive=False)
        assert len(filtered) == 2
        
        # Find team meetings (should match multiple events with OR logic)
        filtered = _client_side_filter(events, search_text="team meeting", match_all_terms=False)
        assert len(filtered) == 3  # All have either "team" or "meeting"
        
        # Find specific room
        filtered = _client_side_filter(events, search_text="room 101", search_fields=["location"])
        assert len(filtered) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])