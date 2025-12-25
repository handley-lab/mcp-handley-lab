"""Unit tests for Google Calendar timezone handling functionality."""

import zoneinfo

import pytest

from mcp_handley_lab.google_calendar.tool import (
    CalendarEvent,
    EventDateTime,
    _build_event_model,
    _get_normalization_patch,
    _has_timezone_inconsistency,
    _is_all_day_event,
    _parse_datetime_to_utc,
    _would_be_timed_event,
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


class TestAllDayEventDetection:
    """Test _is_all_day_event() function."""

    def test_detects_all_day_event(self):
        """Should detect all-day events using date field."""
        event = {"start": {"date": "2024-07-21"}}
        assert _is_all_day_event(event) is True

    def test_rejects_timed_event(self):
        """Should not flag timed events."""
        event = {"start": {"dateTime": "2024-07-21T10:00:00Z"}}
        assert _is_all_day_event(event) is False

    def test_rejects_event_with_both_fields(self):
        """Should not flag events with both date and dateTime."""
        event = {"start": {"date": "2024-07-21", "dateTime": "2024-07-21T10:00:00Z"}}
        assert _is_all_day_event(event) is False

    def test_handles_empty_event(self):
        """Should handle events with empty start."""
        event = {"start": {}}
        assert _is_all_day_event(event) is False

    def test_handles_missing_start(self):
        """Should handle events with missing start."""
        event = {}
        assert _is_all_day_event(event) is False


class TestWouldBeTimedEvent:
    """Test _would_be_timed_event() function."""

    def test_detects_iso_datetime(self):
        """Should detect ISO datetime as timed."""
        assert _would_be_timed_event("2024-07-21T10:00:00") is True
        assert _would_be_timed_event("2024-07-21T10:00:00Z") is True
        assert _would_be_timed_event("2024-07-21T10:00:00+01:00") is True

    def test_rejects_date_only(self):
        """Should not flag date-only as timed."""
        assert _would_be_timed_event("2024-07-21") is False

    def test_detects_natural_language_with_time(self):
        """Should detect natural language with time as timed."""
        assert _would_be_timed_event("tomorrow at 3pm") is True
        assert _would_be_timed_event("10:00") is True
        assert _would_be_timed_event("3:30pm") is True

    def test_handles_empty_string(self):
        """Should handle empty string."""
        assert _would_be_timed_event("") is False
        assert _would_be_timed_event("   ") is False

    def test_handles_none_like_values(self):
        """Should handle None-like values."""
        assert _would_be_timed_event(None) is False


class TestParseDatetimeToUtc:
    """Test _parse_datetime_to_utc() function with naive datetime handling."""

    def test_handles_utc_datetime(self):
        """Should pass through UTC datetime unchanged."""
        result = _parse_datetime_to_utc("2024-07-21T10:00:00Z")
        assert result == "2024-07-21T10:00:00Z"

    def test_converts_timezone_offset_to_utc(self):
        """Should convert timezone offset to UTC."""
        result = _parse_datetime_to_utc("2024-07-21T11:00:00+01:00")
        assert result == "2024-07-21T10:00:00Z"

    def test_interprets_naive_datetime_in_default_timezone(self):
        """Should interpret naive datetime in default timezone."""
        # With Europe/London default, 11:00 local in summer (BST) = 10:00 UTC
        result = _parse_datetime_to_utc("2024-07-21T11:00:00", "Europe/London")
        assert result == "2024-07-21T10:00:00Z"

    def test_interprets_naive_datetime_in_custom_timezone(self):
        """Should interpret naive datetime in custom timezone."""
        # With America/New_York, 10:00 local in summer (EDT, -04:00) = 14:00 UTC
        result = _parse_datetime_to_utc("2024-07-21T10:00:00", "America/New_York")
        assert result == "2024-07-21T14:00:00Z"

    def test_interprets_date_only_in_default_timezone(self):
        """Should interpret date-only in default timezone."""
        # With Europe/London default, midnight local in summer (BST) = 23:00 previous day UTC
        result = _parse_datetime_to_utc("2024-07-21", "Europe/London")
        assert result == "2024-07-20T23:00:00Z"

    def test_handles_empty_string(self):
        """Should handle empty string by returning current UTC time."""
        result = _parse_datetime_to_utc("")
        assert result.endswith("Z")
        assert "T" in result
