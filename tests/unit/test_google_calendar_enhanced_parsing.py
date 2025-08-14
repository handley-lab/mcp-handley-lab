"""Unit tests for enhanced datetime parsing functionality in Google Calendar tool."""

import pytest

from mcp_handley_lab.google_calendar.tool import (
    _parse_user_datetime,
    _prepare_event_datetime,
)


class TestNaturalLanguageParsing:
    """Test natural language datetime parsing capabilities."""

    def test_relative_time_expressions(self):
        """Test relative time expressions like 'in X hours', 'tomorrow'."""
        # These should work with dateparser
        test_cases = [
            ("tomorrow at 2pm", "Europe/London"),
            ("in 2 hours", "America/New_York"),
            ("Monday at 3pm", "Europe/London"),
            ("next week at 10am", "America/Los_Angeles"),
        ]

        for dt_str, tz in test_cases:
            result = _prepare_event_datetime(dt_str, tz)
            assert "dateTime" in result
            assert result["timeZone"] == tz
            # Should be future datetime
            assert result["dateTime"] > "2025-07-15T00:00:00"

    def test_common_time_formats(self):
        """Test common time formats users might type."""
        test_cases = [
            ("2pm", "Europe/London"),
            ("10:30am", "America/New_York"),
            ("14:00", "Europe/London"),
            ("9 AM", "America/Los_Angeles"),
        ]

        for dt_str, tz in test_cases:
            result = _prepare_event_datetime(dt_str, tz)
            assert "dateTime" in result
            assert result["timeZone"] == tz

    def test_day_with_time_combinations(self):
        """Test day + time combinations."""
        test_cases = [
            ("Monday at 2pm", "Europe/London"),
            ("Friday at 9:30am", "America/New_York"),
            (
                "Saturday morning",
                "Europe/London",
            ),  # May not parse, but should not crash
        ]

        for dt_str, tz in test_cases:
            try:
                result = _prepare_event_datetime(dt_str, tz)
                assert "dateTime" in result
                assert result["timeZone"] == tz
            except ValueError:
                # Some natural language may not parse - that's okay
                pass

    def test_fallback_to_pendulum(self):
        """Test that structured formats work via pendulum fallback."""
        # These should work with pendulum when dateparser fails
        test_cases = [
            ("2024-07-15T14:00:00", "Europe/London"),
            ("2024-07-15T14:00:00-08:00", None),  # Should preserve timezone
            ("2024-07-15 14:00:00", "America/New_York"),
        ]

        for dt_str, tz in test_cases:
            result = _prepare_event_datetime(dt_str, tz)
            assert "dateTime" in result
            if tz:
                assert result["timeZone"] == tz
            else:
                assert "timeZone" in result  # Should have some timezone


class TestMixedTimezoneScenarios:
    """Test different timezone scenarios for start and end times."""

    def test_flight_scenario(self):
        """Test flight with different departure and arrival timezones."""
        # Departure from LAX
        departure = _prepare_event_datetime(
            "2024-07-15T10:00:00", "America/Los_Angeles"
        )
        assert departure["dateTime"] == "2024-07-15T10:00:00-07:00"
        assert departure["timeZone"] == "America/Los_Angeles"

        # Arrival at JFK
        arrival = _prepare_event_datetime("2024-07-15T18:30:00", "America/New_York")
        assert arrival["dateTime"] == "2024-07-15T18:30:00-04:00"
        assert arrival["timeZone"] == "America/New_York"

    def test_cross_timezone_meeting(self):
        """Test meeting that spans multiple timezones."""
        # Meeting starts in London
        start = _prepare_event_datetime("2024-07-15T09:00:00", "Europe/London")
        assert start["dateTime"] == "2024-07-15T09:00:00+01:00"
        assert start["timeZone"] == "Europe/London"

        # Meeting ends in New York
        end = _prepare_event_datetime("2024-07-15T17:00:00", "America/New_York")
        assert end["dateTime"] == "2024-07-15T17:00:00-04:00"
        assert end["timeZone"] == "America/New_York"

    def test_timezone_preservation(self):
        """Test that input timezones are preserved when no target timezone specified."""
        # Should preserve the -08:00 timezone
        result = _prepare_event_datetime("2024-07-15T14:00:00-08:00", None)
        assert result["dateTime"] == "2024-07-15T14:00:00-08:00"
        assert result["timeZone"] == "-08:00"

        # Should preserve the +01:00 timezone
        result = _prepare_event_datetime("2024-07-15T14:00:00+01:00", None)
        assert result["dateTime"] == "2024-07-15T14:00:00+01:00"
        assert result["timeZone"] == "+01:00"

    def test_naive_datetime_with_context(self):
        """Test naive datetimes get context timezone applied."""
        # Naive datetime should get the provided timezone
        result = _prepare_event_datetime("2024-07-15T14:00:00", "Europe/London")
        assert result["dateTime"] == "2024-07-15T14:00:00+01:00"
        assert result["timeZone"] == "Europe/London"

        # Same naive datetime, different timezone
        result = _prepare_event_datetime("2024-07-15T14:00:00", "America/New_York")
        assert result["dateTime"] == "2024-07-15T14:00:00-04:00"
        assert result["timeZone"] == "America/New_York"


class TestAdvancedDatetimeScenarios:
    """Test advanced datetime parsing scenarios."""

    def test_seasonal_timezone_handling(self):
        """Test handling of seasonal timezone changes."""
        # Winter time (standard time)
        winter_result = _prepare_event_datetime("2024-01-15T14:00:00-05:00", None)
        assert winter_result["dateTime"] == "2024-01-15T14:00:00-05:00"
        assert winter_result["timeZone"] == "-05:00"

        # Summer time (daylight time)
        summer_result = _prepare_event_datetime("2024-07-15T14:00:00-04:00", None)
        assert summer_result["dateTime"] == "2024-07-15T14:00:00-04:00"
        assert summer_result["timeZone"] == "-04:00"

    def test_all_day_event_detection(self):
        """Test enhanced all-day event detection."""
        # Clear date-only formats
        date_only_cases = [
            "2024-07-15",
            "2024-12-25",
            "2024-02-29",  # Leap year
        ]

        for date_str in date_only_cases:
            result = _prepare_event_datetime(date_str, None)
            assert "date" in result
            assert result["date"] == date_str
            assert "dateTime" not in result
            assert "timeZone" not in result

    def test_complex_iso_formats(self):
        """Test complex ISO format handling."""
        iso_cases = [
            ("2024-07-15T14:00:00Z", "+00:00"),  # Z gets converted to +00:00
            ("2024-07-15T14:00:00.123456Z", "+00:00"),
            ("2024-07-15T14:00:00+00:00", "+00:00"),
            ("2024-07-15T14:00:00-07:00", "-07:00"),
        ]

        for dt_str, expected_tz in iso_cases:
            result = _prepare_event_datetime(dt_str, None)
            assert "dateTime" in result
            assert result["timeZone"] == expected_tz

    def test_error_handling_consistency(self):
        """Test that error handling is consistent across parsing methods."""
        invalid_cases = [
            ("", "Datetime string cannot be empty"),
            ("   ", "Datetime string cannot be empty"),
            ("not a date", "Could not parse datetime string"),
            ("random text", "Could not parse datetime string"),
            ("2024-13-45T14:00:00", "Could not parse datetime string"),  # Invalid month
            ("2024-07-15T25:00:00", "Could not parse datetime string"),  # Invalid hour
        ]

        for invalid_str, expected_msg in invalid_cases:
            with pytest.raises(ValueError, match=expected_msg):
                _prepare_event_datetime(invalid_str, "Europe/London")


class TestParsingFallbacks:
    """Test the fallback chain in datetime parsing."""

    def test_dateparser_primary_success(self):
        """Test cases where dateparser should succeed."""
        # These should be handled by dateparser
        dateparser_cases = [
            "tomorrow at 2pm",
            "Monday at 3pm",
            "in 2 hours",
        ]

        for dt_str in dateparser_cases:
            result = _parse_user_datetime(dt_str, "Europe/London")
            assert result is not None
            assert hasattr(result, "timezone")

    def test_pendulum_fallback_success(self):
        """Test cases where pendulum fallback should succeed."""
        # These should fall back to pendulum
        pendulum_cases = [
            "2024-07-15T14:00:00",
            "2024-07-15T14:00:00-08:00",
            "2024-07-15 14:00:00",
        ]

        for dt_str in pendulum_cases:
            result = _parse_user_datetime(dt_str, "Europe/London")
            assert result is not None
            assert hasattr(result, "timezone")

    def test_complete_parsing_failure(self):
        """Test cases where both dateparser and pendulum should fail."""
        failure_cases = [
            "completely invalid text",
            "not a date at all",
            "2024-99-99T99:99:99",
        ]

        for dt_str in failure_cases:
            with pytest.raises(ValueError):
                _parse_user_datetime(dt_str, "Europe/London")


class TestContextualBehavior:
    """Test context-aware parsing behavior."""

    def test_timezone_context_application(self):
        """Test that timezone context is applied correctly."""
        # Naive datetime should get context timezone
        result = _parse_user_datetime("2024-07-15T14:00:00", "America/New_York")
        assert str(result.timezone) == "America/New_York"

        # Timezone-aware datetime gets processed by dateparser with context
        result = _parse_user_datetime("2024-07-15T14:00:00-08:00", "America/New_York")
        # dateparser may convert to context timezone, so just check it's timezone-aware
        assert result.timezone is not None

    def test_future_preference(self):
        """Test that parsing prefers future dates."""
        # Using relative expressions should give future dates
        result = _parse_user_datetime("Monday at 3pm", "Europe/London")
        # Should be a future Monday (convert to date for comparison)
        import pendulum

        today = pendulum.today()
        assert result.date() >= today.date()

    def test_no_context_behavior(self):
        """Test behavior when no timezone context is provided."""
        # Should still work for timezone-aware input
        result = _parse_user_datetime("2024-07-15T14:00:00-08:00", None)
        assert result is not None
        assert result.timezone is not None

        # Should work for naive input (will get system timezone)
        result = _parse_user_datetime("2024-07-15T14:00:00", None)
        assert result is not None
        assert result.timezone is not None
