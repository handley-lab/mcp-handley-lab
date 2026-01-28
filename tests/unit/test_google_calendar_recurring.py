"""Unit tests for Google Calendar recurring event functionality."""

import pytest

from mcp_handley_lab.google_calendar.shared import _merge_recurrence
from mcp_handley_lab.google_calendar.tool import (
    _build_event_model,
    _get_series_master_id,
    _validate_recurrence,
)


class TestValidateRecurrence:
    """Tests for recurrence rule validation."""

    def test_empty_list_is_valid(self):
        """Empty list means no recurrence - valid."""
        _validate_recurrence([])

    def test_single_rrule_is_valid(self):
        """Single RRULE is valid."""
        _validate_recurrence(["RRULE:FREQ=WEEKLY;COUNT=10"])

    def test_rrule_with_until_is_valid(self):
        """RRULE with UNTIL is valid."""
        _validate_recurrence(["RRULE:FREQ=WEEKLY;UNTIL=20261231T235959Z"])

    def test_rrule_with_byday_is_valid(self):
        """RRULE with BYDAY is valid."""
        _validate_recurrence(["RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"])

    def test_multiple_rules_with_exdate(self):
        """Multiple rules with EXDATE is valid."""
        _validate_recurrence(["RRULE:FREQ=WEEKLY;COUNT=10", "EXDATE:20260115T090000Z"])

    def test_multiple_rules_with_rdate(self):
        """Multiple rules with RDATE is valid."""
        _validate_recurrence(["RRULE:FREQ=WEEKLY", "RDATE:20260115T090000Z"])

    def test_count_and_until_together_invalid(self):
        """Cannot use both COUNT and UNTIL in RRULE."""
        with pytest.raises(ValueError, match="Cannot use both COUNT and UNTIL"):
            _validate_recurrence(["RRULE:FREQ=WEEKLY;COUNT=10;UNTIL=20261231T235959Z"])

    def test_invalid_prefix_rejected(self):
        """Invalid rule prefix is rejected."""
        with pytest.raises(ValueError, match="Invalid recurrence rule"):
            _validate_recurrence(["INVALID:FREQ=WEEKLY"])

    def test_empty_string_rejected(self):
        """Empty string rule is rejected."""
        with pytest.raises(ValueError, match="Empty recurrence rule"):
            _validate_recurrence([""])

    def test_whitespace_only_rejected(self):
        """Whitespace-only rule is rejected."""
        with pytest.raises(ValueError, match="Empty recurrence rule"):
            _validate_recurrence(["   "])


class TestGetSeriesMasterId:
    """Tests for series master ID resolution."""

    def test_master_event_returns_own_id(self):
        """Event with recurrence rules returns its own ID."""
        event = {"id": "master123", "recurrence": ["RRULE:FREQ=WEEKLY"]}
        assert _get_series_master_id(event) == "master123"

    def test_instance_returns_master_id(self):
        """Instance event returns its recurringEventId."""
        event = {"id": "instance456", "recurringEventId": "master123"}
        assert _get_series_master_id(event) == "master123"

    def test_single_event_returns_none(self):
        """Non-recurring event returns None."""
        event = {"id": "single789"}
        assert _get_series_master_id(event) is None

    def test_prefers_recurrence_over_recurring_event_id(self):
        """If both recurrence and recurringEventId exist, prefers recurrence (is master)."""
        # This case shouldn't happen in practice, but tests priority
        event = {
            "id": "event123",
            "recurrence": ["RRULE:FREQ=WEEKLY"],
            "recurringEventId": "other456",
        }
        assert _get_series_master_id(event) == "event123"


class TestMergeRecurrence:
    """Tests for recurrence merge logic."""

    def test_none_means_no_change(self):
        """None input means no change to recurrence."""
        existing = ["RRULE:FREQ=WEEKLY"]
        assert _merge_recurrence(existing, None) is None

    def test_empty_list_clears_recurrence(self):
        """Empty list clears all recurrence (converts to single event)."""
        existing = ["RRULE:FREQ=WEEKLY"]
        assert _merge_recurrence(existing, []) == []

    def test_new_rrule_preserves_exceptions(self):
        """New RRULE preserves existing EXDATE/RDATE."""
        existing = [
            "RRULE:FREQ=WEEKLY;COUNT=10",
            "EXDATE:20260115T090000Z",
            "RDATE:20260120T090000Z",
        ]
        new = ["RRULE:FREQ=DAILY;COUNT=5"]
        result = _merge_recurrence(existing, new)
        assert "RRULE:FREQ=DAILY;COUNT=5" in result
        assert "EXDATE:20260115T090000Z" in result
        assert "RDATE:20260120T090000Z" in result
        # Old RRULE should be replaced
        assert "RRULE:FREQ=WEEKLY;COUNT=10" not in result

    def test_full_spec_replaces_everything(self):
        """If caller provides EXDATE/RDATE, use new spec as-is."""
        existing = [
            "RRULE:FREQ=WEEKLY;COUNT=10",
            "EXDATE:20260115T090000Z",
        ]
        new = ["RRULE:FREQ=DAILY;COUNT=5", "EXDATE:20260122T090000Z"]
        result = _merge_recurrence(existing, new)
        assert result == new
        # Old exception should not be preserved
        assert "EXDATE:20260115T090000Z" not in result


class TestBuildEventModelRecurrence:
    """Tests for _build_event_model with recurring event fields."""

    def test_builds_master_event_with_recurrence(self):
        """Master event includes recurrence rules."""
        event_data = {
            "id": "master123",
            "summary": "Weekly Meeting",
            "start": {"dateTime": "2026-01-15T10:00:00+00:00", "timeZone": "UTC"},
            "end": {"dateTime": "2026-01-15T11:00:00+00:00", "timeZone": "UTC"},
            "recurrence": ["RRULE:FREQ=WEEKLY;COUNT=10"],
        }
        event = _build_event_model(event_data)
        assert event.recurrence == ["RRULE:FREQ=WEEKLY;COUNT=10"]
        assert event.recurringEventId == ""
        assert event.originalStartTime is None

    def test_builds_instance_with_original_start_time(self):
        """Instance event includes recurringEventId and originalStartTime."""
        event_data = {
            "id": "instance456",
            "summary": "Weekly Meeting",
            "start": {"dateTime": "2026-01-22T10:30:00+00:00", "timeZone": "UTC"},
            "end": {"dateTime": "2026-01-22T11:30:00+00:00", "timeZone": "UTC"},
            "recurringEventId": "master123",
            "originalStartTime": {
                "dateTime": "2026-01-22T10:00:00+00:00",
                "timeZone": "UTC",
            },
        }
        event = _build_event_model(event_data)
        assert event.recurrence == []
        assert event.recurringEventId == "master123"
        assert event.originalStartTime is not None
        assert event.originalStartTime.dateTime == "2026-01-22T10:00:00+00:00"

    def test_builds_single_event_with_empty_recurrence_fields(self):
        """Single event has empty recurrence fields."""
        event_data = {
            "id": "single789",
            "summary": "One-time Meeting",
            "start": {"dateTime": "2026-01-15T10:00:00+00:00", "timeZone": "UTC"},
            "end": {"dateTime": "2026-01-15T11:00:00+00:00", "timeZone": "UTC"},
        }
        event = _build_event_model(event_data)
        assert event.recurrence == []
        assert event.recurringEventId == ""
        assert event.originalStartTime is None

    def test_all_day_instance_with_date_original_start(self):
        """All-day instance can have originalStartTime with date instead of dateTime."""
        event_data = {
            "id": "instance456",
            "summary": "Weekly Review",
            "start": {"date": "2026-01-22"},
            "end": {"date": "2026-01-23"},
            "recurringEventId": "master123",
            "originalStartTime": {"date": "2026-01-22"},
        }
        event = _build_event_model(event_data)
        assert event.recurringEventId == "master123"
        assert event.originalStartTime is not None
        assert event.originalStartTime.date == "2026-01-22"
        assert event.originalStartTime.dateTime == ""
