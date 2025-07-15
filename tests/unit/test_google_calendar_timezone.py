"""Unit tests for Google Calendar timezone handling functionality."""

import zoneinfo

import pytest
from mcp_handley_lab.google_calendar.tool import (
    CalendarEvent,
    EventDateTime,
    _build_event_model,
    _get_normalization_patch,
    _has_timezone_inconsistency,
)


class TestTimezoneInconsistencyDetection:
    """Test _has_timezone_inconsistency() function."""

    def test_detects_utc_with_timezone_label(self):
        """Should detect UTC time with timezone label."""
        event = {
            "start": {"dateTime": "2024-07-21T10:00:00Z", "timeZone": "Europe/London"}
        }
        assert _has_timezone_inconsistency(event) is True

    def test_ignores_utc_without_timezone_label(self):
        """Should not flag UTC time without timezone label."""
        event = {"start": {"dateTime": "2024-07-21T10:00:00Z"}}
        assert _has_timezone_inconsistency(event) is False

    def test_ignores_utc_timezone_label(self):
        """Should not flag UTC time with UTC timezone."""
        event = {"start": {"dateTime": "2024-07-21T10:00:00Z", "timeZone": "UTC"}}
        assert _has_timezone_inconsistency(event) is False

    def test_ignores_local_time_with_timezone(self):
        """Should not flag local time with timezone."""
        event = {
            "start": {"dateTime": "2024-07-21T11:00:00", "timeZone": "Europe/London"}
        }
        assert _has_timezone_inconsistency(event) is False

    def test_ignores_all_day_events(self):
        """Should not flag all-day events."""
        event = {"start": {"date": "2024-07-21"}}
        assert _has_timezone_inconsistency(event) is False

    def test_handles_missing_start(self):
        """Should handle events with missing start data."""
        event = {}
        assert _has_timezone_inconsistency(event) is False

    def test_handles_empty_start(self):
        """Should handle events with empty start object."""
        event = {"start": {}}
        assert _has_timezone_inconsistency(event) is False


class TestNormalizationPatch:
    """Test _get_normalization_patch() function."""

    def test_creates_patch_for_inconsistent_event(self):
        """Should create normalization patch for inconsistent timezone."""
        event = {
            "start": {"dateTime": "2024-07-21T10:00:00Z", "timeZone": "Europe/London"},
            "end": {"dateTime": "2024-07-21T11:00:00Z", "timeZone": "Europe/London"},
        }

        patch = _get_normalization_patch(event)

        assert "start" in patch
        assert "end" in patch
        assert patch["start"]["timeZone"] == "Europe/London"
        assert patch["end"]["timeZone"] == "Europe/London"
        # UTC 10:00 should become local 11:00 in Europe/London (BST)
        assert "11:00:00" in patch["start"]["dateTime"]
        assert "12:00:00" in patch["end"]["dateTime"]

    def test_returns_empty_for_consistent_event(self):
        """Should return empty patch for consistent timezone."""
        event = {
            "start": {"dateTime": "2024-07-21T11:00:00", "timeZone": "Europe/London"},
            "end": {"dateTime": "2024-07-21T12:00:00", "timeZone": "Europe/London"},
        }

        patch = _get_normalization_patch(event)
        assert patch == {}

    def test_handles_different_timezones(self):
        """Should handle different timezone conversions."""
        event = {
            "start": {
                "dateTime": "2024-01-15T17:00:00Z",  # Winter time
                "timeZone": "America/New_York",
            },
            "end": {"dateTime": "2024-01-15T18:00:00Z", "timeZone": "America/New_York"},
        }

        patch = _get_normalization_patch(event)

        # UTC 17:00 should become EST 12:00 in winter
        assert "12:00:00" in patch["start"]["dateTime"]
        assert "13:00:00" in patch["end"]["dateTime"]

    def test_preserves_timezone_labels(self):
        """Should preserve original timezone labels in patch."""
        event = {
            "start": {"dateTime": "2024-07-21T10:00:00Z", "timeZone": "Asia/Tokyo"},
            "end": {"dateTime": "2024-07-21T11:00:00Z", "timeZone": "Asia/Tokyo"},
        }

        patch = _get_normalization_patch(event)

        assert patch["start"]["timeZone"] == "Asia/Tokyo"
        assert patch["end"]["timeZone"] == "Asia/Tokyo"


class TestBuildEventModel:
    """Test _build_event_model() helper function."""

    def test_builds_complete_event_model(self):
        """Should build complete CalendarEvent from API data."""
        event_data = {
            "id": "event123",
            "summary": "Test Meeting",
            "description": "Important meeting",
            "location": "Conference Room A",
            "start": {"dateTime": "2024-07-21T10:00:00Z", "timeZone": "Europe/London"},
            "end": {"dateTime": "2024-07-21T11:00:00Z", "timeZone": "Europe/London"},
            "attendees": [{"email": "test@example.com", "responseStatus": "accepted"}],
            "created": "2024-07-20T12:00:00Z",
            "updated": "2024-07-21T08:00:00Z",
            "calendar_name": "Primary",
        }

        result = _build_event_model(event_data)

        assert isinstance(result, CalendarEvent)
        assert result.id == "event123"
        assert result.summary == "Test Meeting"
        assert result.description == "Important meeting"
        assert result.location == "Conference Room A"
        assert isinstance(result.start, EventDateTime)
        assert isinstance(result.end, EventDateTime)
        assert len(result.attendees) == 1
        assert result.attendees[0].email == "test@example.com"
        assert result.calendar_name == "Primary"

    def test_handles_minimal_event_data(self):
        """Should handle minimal event data with defaults."""
        event_data = {"id": "event456", "start": {}, "end": {}}

        result = _build_event_model(event_data)

        assert result.id == "event456"
        assert result.summary == "No Title"
        assert result.description == ""
        assert result.location == ""
        assert len(result.attendees) == 0

    def test_handles_missing_optional_fields(self):
        """Should handle missing optional fields gracefully."""
        event_data = {
            "id": "event789",
            "start": {"date": "2024-07-21"},
            "end": {"date": "2024-07-21"},
        }

        result = _build_event_model(event_data)

        assert result.id == "event789"
        assert result.summary == "No Title"
        assert result.start.date == "2024-07-21"
        assert result.end.date == "2024-07-21"
        assert result.calendar_name == ""

    def test_processes_attendees_with_defaults(self):
        """Should process attendees with proper defaults."""
        event_data = {
            "id": "event101",
            "start": {},
            "end": {},
            "attendees": [
                {"email": "user1@example.com"},  # Missing responseStatus
                {"responseStatus": "declined"},  # Missing email
                {"email": "user2@example.com", "responseStatus": "tentative"},
            ],
        }

        result = _build_event_model(event_data)

        assert len(result.attendees) == 3
        assert result.attendees[0].email == "user1@example.com"
        assert result.attendees[0].responseStatus == "needsAction"
        assert result.attendees[1].email == "Unknown"
        assert result.attendees[1].responseStatus == "declined"
        assert result.attendees[2].email == "user2@example.com"
        assert result.attendees[2].responseStatus == "tentative"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_inconsistency_with_malformed_timezone(self):
        """Should handle events with malformed timezone data."""
        event = {
            "start": {
                "dateTime": "2024-07-21T10:00:00Z",
                "timeZone": "",  # Empty timezone
            }
        }
        # Empty timezone should not be considered inconsistent
        assert _has_timezone_inconsistency(event) is False

    def test_normalization_fails_gracefully_with_invalid_timezone(self):
        """Should fail fast with invalid timezone in normalization."""
        event = {
            "start": {
                "dateTime": "2024-07-21T10:00:00Z",
                "timeZone": "Invalid/Timezone",
            },
            "end": {"dateTime": "2024-07-21T11:00:00Z", "timeZone": "Invalid/Timezone"},
        }

        # Should raise ZoneInfoNotFoundError (fail fast)
        with pytest.raises(zoneinfo.ZoneInfoNotFoundError):
            _get_normalization_patch(event)

    def test_build_model_with_invalid_datetime_structure(self):
        """Should handle events with unexpected datetime structure."""
        event_data = {
            "id": "event_bad",
            "start": {"invalidField": "badData"},
            "end": {"invalidField": "badData"},
        }

        # EventDateTime should handle unexpected fields gracefully
        result = _build_event_model(event_data)
        assert result.id == "event_bad"
        assert isinstance(result.start, EventDateTime)
        assert isinstance(result.end, EventDateTime)
