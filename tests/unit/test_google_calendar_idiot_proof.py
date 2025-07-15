"""Unit tests for idiot-proof timezone handling in Google Calendar tool."""


import pytest
from mcp_handley_lab.google_calendar.tool import _prepare_event_datetime


class TestIdiotProofTimezoneHandling:
    """Test that users can copy-paste datetime strings from any website."""

    def test_us_website_formats(self):
        """Test datetime formats commonly found on US websites."""
        # US East Coast (EDT/EST)
        result = _prepare_event_datetime("2024-07-15T14:00:00-04:00", "Europe/London")
        assert result["dateTime"] == "2024-07-15T19:00:00"
        assert result["timeZone"] == "Europe/London"

        # US West Coast (PDT/PST)
        result = _prepare_event_datetime("2024-07-15T14:00:00-07:00", "Europe/London")
        assert result["dateTime"] == "2024-07-15T22:00:00"
        assert result["timeZone"] == "Europe/London"

        # US Central Time (CDT/CST)
        result = _prepare_event_datetime("2024-07-15T14:00:00-05:00", "Europe/London")
        assert result["dateTime"] == "2024-07-15T20:00:00"
        assert result["timeZone"] == "Europe/London"

    def test_international_website_formats(self):
        """Test datetime formats from international websites."""
        # UTC format (common on international sites)
        result = _prepare_event_datetime("2024-07-15T14:00:00Z", "America/New_York")
        assert result["dateTime"] == "2024-07-15T10:00:00"
        assert result["timeZone"] == "America/New_York"

        # European timezone (CET/CEST)
        result = _prepare_event_datetime(
            "2024-07-15T14:00:00+01:00", "America/Los_Angeles"
        )
        assert result["dateTime"] == "2024-07-15T06:00:00"
        assert result["timeZone"] == "America/Los_Angeles"

        # Asian timezone (JST)
        result = _prepare_event_datetime("2024-07-15T14:00:00+09:00", "Europe/London")
        assert result["dateTime"] == "2024-07-15T06:00:00"
        assert result["timeZone"] == "Europe/London"

    def test_seasonal_timezone_changes(self):
        """Test that seasonal timezone changes are handled correctly."""
        # Winter time (EST vs EDT)
        winter_result = _prepare_event_datetime(
            "2024-01-15T14:00:00-05:00", "Europe/London"
        )
        assert winter_result["dateTime"] == "2024-01-15T19:00:00"
        assert winter_result["timeZone"] == "Europe/London"

        # Summer time (EDT vs EST)
        summer_result = _prepare_event_datetime(
            "2024-07-15T14:00:00-04:00", "Europe/London"
        )
        assert summer_result["dateTime"] == "2024-07-15T19:00:00"
        assert summer_result["timeZone"] == "Europe/London"

        # UK summer time (BST)
        uk_summer = _prepare_event_datetime(
            "2024-07-15T14:00:00+01:00", "America/New_York"
        )
        assert uk_summer["dateTime"] == "2024-07-15T09:00:00"
        assert uk_summer["timeZone"] == "America/New_York"

    def test_naive_datetime_handling(self):
        """Test that naive datetime strings are interpreted in calendar timezone."""
        # Should be treated as local time in target timezone
        result = _prepare_event_datetime("2024-07-15T14:00:00", "Europe/London")
        assert result["dateTime"] == "2024-07-15T14:00:00"
        assert result["timeZone"] == "Europe/London"

        # Same input, different target timezone
        result = _prepare_event_datetime("2024-07-15T14:00:00", "America/New_York")
        assert result["dateTime"] == "2024-07-15T14:00:00"
        assert result["timeZone"] == "America/New_York"

    def test_all_day_event_handling(self):
        """Test various all-day event formats."""
        # Standard ISO date
        result = _prepare_event_datetime("2024-07-15", "Europe/London")
        assert result == {"date": "2024-07-15"}

        # Alternative date format
        result = _prepare_event_datetime("2024-12-25", "America/New_York")
        assert result == {"date": "2024-12-25"}

    def test_microsecond_handling(self):
        """Test that microseconds are handled gracefully."""
        result = _prepare_event_datetime("2024-07-15T14:00:00.123456Z", "Europe/London")
        assert result["dateTime"] == "2024-07-15T15:00:00"  # Microseconds stripped
        assert result["timeZone"] == "Europe/London"

    def test_cross_timezone_conversions(self):
        """Test various cross-timezone conversion scenarios."""
        conversions = [
            # (input, target_tz, expected_time)
            (
                "2024-07-15T14:00:00-08:00",
                "Europe/London",
                "2024-07-15T23:00:00",
            ),  # PDT→BST (summer)
            (
                "2024-07-15T14:00:00Z",
                "America/New_York",
                "2024-07-15T10:00:00",
            ),  # UTC→EDT
            (
                "2024-07-15T14:00:00+01:00",
                "America/Los_Angeles",
                "2024-07-15T06:00:00",
            ),  # CET→PDT (summer)
            (
                "2024-01-15T14:00:00+08:00",
                "Europe/London",
                "2024-01-15T06:00:00",
            ),  # JST→GMT (winter)
        ]

        for input_dt, target_tz, expected_time in conversions:
            result = _prepare_event_datetime(input_dt, target_tz)
            assert result["dateTime"] == expected_time
            assert result["timeZone"] == target_tz

    def test_year_boundary_handling(self):
        """Test datetime handling around year boundaries."""
        # New Year's Eve UTC → EST (crosses year boundary)
        result = _prepare_event_datetime("2024-12-31T23:59:59Z", "America/New_York")
        assert result["dateTime"] == "2024-12-31T18:59:59"
        assert result["timeZone"] == "America/New_York"

        # New Year's Day EST → JST (crosses year boundary forward)
        result = _prepare_event_datetime("2024-01-01T02:00:00-05:00", "Asia/Tokyo")
        assert result["dateTime"] == "2024-01-01T16:00:00"
        assert result["timeZone"] == "Asia/Tokyo"

    def test_leap_year_handling(self):
        """Test leap year date handling."""
        # Leap day in 2024
        result = _prepare_event_datetime("2024-02-29T14:00:00", "Europe/London")
        assert result["dateTime"] == "2024-02-29T14:00:00"
        assert result["timeZone"] == "Europe/London"

        # Leap day as all-day event
        result = _prepare_event_datetime("2024-02-29", "America/New_York")
        assert result == {"date": "2024-02-29"}


class TestErrorHandling:
    """Test that invalid inputs fail gracefully with clear error messages."""

    def test_empty_string_handling(self):
        """Test that empty strings are rejected."""
        with pytest.raises(ValueError, match="Datetime string cannot be empty"):
            _prepare_event_datetime("", "Europe/London")

        with pytest.raises(ValueError, match="Datetime string cannot be empty"):
            _prepare_event_datetime("   ", "Europe/London")

    def test_invalid_datetime_formats(self):
        """Test that invalid datetime formats are rejected."""
        invalid_formats = [
            "2024-13-45T14:00:00",  # Invalid month
            "2024-07-15T25:00:00",  # Invalid hour
            "2024-07-15T14:60:00",  # Invalid minute
            "2024-07-15T14:00:60",  # Invalid second
        ]

        for invalid_dt in invalid_formats:
            with pytest.raises(ValueError, match="Could not parse datetime string"):
                _prepare_event_datetime(invalid_dt, "Europe/London")

    def test_invalid_timezone_handling(self):
        """Test that invalid timezones are rejected."""
        with pytest.raises(ValueError, match="Could not parse datetime string"):
            _prepare_event_datetime("2024-07-15T14:00:00", "Invalid/Timezone")

        with pytest.raises(ValueError, match="Could not parse datetime string"):
            _prepare_event_datetime("2024-07-15T14:00:00", "Not/A/Real/Timezone")

    def test_unparseable_text_handling(self):
        """Test that random text is rejected for dates."""
        with pytest.raises(ValueError, match="Could not parse datetime string"):
            _prepare_event_datetime("not a date", "Europe/London")

        with pytest.raises(ValueError, match="Could not parse datetime string"):
            _prepare_event_datetime("random text", "Europe/London")

    def test_partial_datetime_handling(self):
        """Test that partial datetime strings are handled appropriately."""
        # This should work - dateutil.parser is quite flexible
        result = _prepare_event_datetime("2024-07-15T", "Europe/London")
        assert result["dateTime"] == "2024-07-15T00:00:00"
        assert result["timeZone"] == "Europe/London"


class TestDatetimeFormats:
    """Test various datetime formats that dateutil.parser can handle."""

    def test_iso_format_variations(self):
        """Test various ISO 8601 format variations."""
        variations = [
            "2024-07-15T14:00:00",
            "2024-07-15T14:00:00.000",
            "2024-07-15T14:00:00.123456",
            "2024-07-15 14:00:00",  # Space instead of T
        ]

        for dt_str in variations:
            result = _prepare_event_datetime(dt_str, "Europe/London")
            assert result["dateTime"] == "2024-07-15T14:00:00"
            assert result["timeZone"] == "Europe/London"

    def test_human_readable_formats(self):
        """Test that some human-readable formats work."""
        # These should be parsed as timed events
        human_formats = [
            "2024-07-15 14:00:00",
            "2024-07-15 2:00 PM",
        ]

        for dt_str in human_formats:
            result = _prepare_event_datetime(dt_str, "Europe/London")
            assert "dateTime" in result
            assert result["timeZone"] == "Europe/London"

    def test_date_only_detection(self):
        """Test that date-only strings are correctly identified."""
        date_only_formats = [
            "2024-07-15",
            "2024-12-25",
            "2024-02-29",  # Leap year
        ]

        for date_str in date_only_formats:
            result = _prepare_event_datetime(date_str, "Europe/London")
            assert "date" in result
            assert result["date"] == date_str
            assert "dateTime" not in result
            assert "timeZone" not in result


class TestRealWorldScenarios:
    """Test real-world scenarios users might encounter."""

    def test_conference_website_scenario(self):
        """Test copying datetime from a conference website."""
        # User copies "2024-12-25T14:00:00-08:00" from US conference site
        result = _prepare_event_datetime("2024-12-25T14:00:00-08:00", "Europe/London")

        # Should convert PST to GMT (14:00 PST = 22:00 GMT)
        assert result["dateTime"] == "2024-12-25T22:00:00"
        assert result["timeZone"] == "Europe/London"

    def test_international_webinar_scenario(self):
        """Test copying UTC time from international webinar."""
        # User copies "2024-12-25T14:00:00Z" from international webinar
        result = _prepare_event_datetime("2024-12-25T14:00:00Z", "America/New_York")

        # Should convert UTC to EST (14:00 UTC = 09:00 EST)
        assert result["dateTime"] == "2024-12-25T09:00:00"
        assert result["timeZone"] == "America/New_York"

    def test_local_meeting_entry_scenario(self):
        """Test user typing local meeting time."""
        # User types "2024-12-25T14:00:00" for local meeting
        result = _prepare_event_datetime("2024-12-25T14:00:00", "Europe/London")

        # Should treat as local time (14:00 stays 14:00 in London)
        assert result["dateTime"] == "2024-12-25T14:00:00"
        assert result["timeZone"] == "Europe/London"

    def test_email_invitation_scenario(self):
        """Test copying datetime from email invitation."""
        # User copies "2024-12-25T14:00:00+01:00" from email invitation
        result = _prepare_event_datetime(
            "2024-12-25T14:00:00+01:00", "America/Los_Angeles"
        )

        # Should convert CET to PST (14:00 CET = 05:00 PST)
        assert result["dateTime"] == "2024-12-25T05:00:00"
        assert result["timeZone"] == "America/Los_Angeles"

    def test_holiday_event_scenario(self):
        """Test creating all-day holiday event."""
        # User creates "2024-12-25" holiday event
        result = _prepare_event_datetime("2024-12-25", "America/New_York")

        # Should be all-day event (no timezone conversion needed)
        assert result == {"date": "2024-12-25"}
