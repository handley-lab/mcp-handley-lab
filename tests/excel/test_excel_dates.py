"""Tests for Excel date utilities."""

from datetime import date, datetime, time

from mcp_handley_lab.microsoft.excel.ops.dates import (
    datetime_to_excel,
    excel_to_date,
    excel_to_datetime,
    excel_to_time,
    is_date_format,
)


class TestDatetimeToExcel:
    """Tests for datetime_to_excel."""

    def test_excel_epoch(self) -> None:
        """January 1, 1900 is serial 1."""
        assert datetime_to_excel(date(1900, 1, 1)) == 1.0

    def test_date_2024(self) -> None:
        """Modern date conversion."""
        # January 1, 2024 is 45292 days since Dec 30, 1899 (with 1900 bug adjustment)
        serial = datetime_to_excel(date(2024, 1, 1))
        assert serial == 45292.0

    def test_datetime_with_time(self) -> None:
        """Datetime includes time as fraction."""
        # Noon is 0.5 of a day
        serial = datetime_to_excel(datetime(2024, 1, 1, 12, 0, 0))
        assert serial == 45292.5

    def test_time_only(self) -> None:
        """Time only returns fraction."""
        serial = datetime_to_excel(time(12, 0, 0))
        assert serial == 0.5

    def test_1900_bug_feb_28(self) -> None:
        """Feb 28, 1900 is serial 59 (before bug date)."""
        serial = datetime_to_excel(date(1900, 2, 28))
        assert serial == 59.0

    def test_1900_bug_mar_1(self) -> None:
        """March 1, 1900 is serial 61 (after nonexistent Feb 29)."""
        serial = datetime_to_excel(date(1900, 3, 1))
        assert serial == 61.0


class TestExcelToDatetime:
    """Tests for excel_to_datetime."""

    def test_serial_1(self) -> None:
        """Serial 1 is January 1, 1900."""
        dt = excel_to_datetime(1.0)
        assert dt == datetime(1900, 1, 1)

    def test_modern_date(self) -> None:
        """Modern date roundtrip."""
        dt = excel_to_datetime(45292.0)
        assert dt.date() == date(2024, 1, 1)

    def test_with_time_fraction(self) -> None:
        """Time fraction is converted."""
        dt = excel_to_datetime(45292.5)
        assert dt.hour == 12
        assert dt.minute == 0

    def test_1900_bug_serial_59(self) -> None:
        """Serial 59 is Feb 28, 1900."""
        dt = excel_to_datetime(59.0)
        assert dt.date() == date(1900, 2, 28)

    def test_1900_bug_serial_61(self) -> None:
        """Serial 61 is March 1, 1900 (skipping fake Feb 29)."""
        dt = excel_to_datetime(61.0)
        assert dt.date() == date(1900, 3, 1)


class TestExcelToDate:
    """Tests for excel_to_date."""

    def test_returns_date(self) -> None:
        """Returns date object."""
        d = excel_to_date(45292.5)
        assert isinstance(d, date)
        assert d == date(2024, 1, 1)


class TestExcelToTime:
    """Tests for excel_to_time."""

    def test_noon(self) -> None:
        """0.5 is noon."""
        t = excel_to_time(0.5)
        assert t.hour == 12
        assert t.minute == 0

    def test_quarter_past(self) -> None:
        """Time calculation accuracy."""
        t = excel_to_time(0.51041666667)  # ~12:15
        assert t.hour == 12
        assert t.minute == 15


class TestRoundtrip:
    """Tests for datetime <-> Excel roundtrip."""

    def test_date_roundtrip(self) -> None:
        """Date survives roundtrip."""
        original = date(2024, 6, 15)
        serial = datetime_to_excel(original)
        result = excel_to_date(serial)
        assert result == original

    def test_datetime_roundtrip(self) -> None:
        """Datetime survives roundtrip (to second precision)."""
        original = datetime(2024, 6, 15, 14, 30, 45)
        serial = datetime_to_excel(original)
        result = excel_to_datetime(serial)
        # Check to second precision (microseconds may drift)
        assert result.date() == original.date()
        assert result.hour == original.hour
        assert result.minute == original.minute
        assert result.second == original.second


class TestIsDateFormat:
    """Tests for is_date_format."""

    def test_general_not_date(self) -> None:
        """General format is not a date."""
        assert not is_date_format("General")

    def test_number_not_date(self) -> None:
        """Number formats are not dates."""
        assert not is_date_format("0")
        assert not is_date_format("0.00")
        assert not is_date_format("#,##0")

    def test_text_not_date(self) -> None:
        """Text format is not a date."""
        assert not is_date_format("@")

    def test_simple_date(self) -> None:
        """Simple date formats."""
        assert is_date_format("mm-dd-yy")
        assert is_date_format("yyyy-mm-dd")
        assert is_date_format("d/m/yy")

    def test_date_with_time(self) -> None:
        """Date with time formats."""
        assert is_date_format("m/d/yy h:mm")
        assert is_date_format("yyyy-mm-dd hh:mm:ss")

    def test_time_only(self) -> None:
        """Time-only formats."""
        assert is_date_format("h:mm")
        assert is_date_format("h:mm:ss")
        assert is_date_format("[h]:mm:ss")

    def test_none_input(self) -> None:
        """None input returns False."""
        assert not is_date_format(None)

    def test_empty_input(self) -> None:
        """Empty string returns False."""
        assert not is_date_format("")
