"""Date handling utilities for Excel.

Excel stores dates as floating-point numbers representing days since January 1, 1900.
Times are stored as fractions of a day.

The "1900 bug": Excel incorrectly treats 1900 as a leap year, believing February 29, 1900
existed. This means dates on or after March 1, 1900 are off by one day in the serial system.
We handle this by adding 1 to the serial for dates >= March 1, 1900.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

# Excel epoch: January 1, 1900 = serial 1
# So epoch is December 31, 1899 (serial 0 conceptually)
EXCEL_EPOCH = date(1899, 12, 31)

# The 1900 bug: Excel thinks Feb 29, 1900 exists (serial 60)
# Dates >= March 1, 1900 (Python) need +1 adjustment when converting TO Excel
# Serials >= 60 need -1 adjustment when converting FROM Excel
MARCH_1_1900 = date(1900, 3, 1)
FAKE_FEB_29_SERIAL = 60


def datetime_to_excel(dt: datetime | date | time) -> float:
    """Convert a Python datetime/date/time to Excel serial number.

    Args:
        dt: Python datetime, date, or time object.

    Returns:
        Excel serial number (days since Dec 30, 1899, with time as fraction).

    Examples:
        >>> datetime_to_excel(date(1900, 1, 1))
        1.0
        >>> datetime_to_excel(date(2024, 1, 1))
        45292.0
        >>> datetime_to_excel(datetime(2024, 1, 1, 12, 0, 0))
        45292.5
    """
    if isinstance(dt, time):
        # Time only - return fraction of day
        return _time_to_fraction(dt)

    if isinstance(dt, datetime):
        d = dt.date()
        t = dt.time()
        time_fraction = _time_to_fraction(t)
    else:
        d = dt
        time_fraction = 0.0

    # Calculate days since epoch
    delta = d - EXCEL_EPOCH
    serial = float(delta.days)

    # Apply 1900 bug adjustment: dates >= March 1, 1900 need +1
    # because Excel has a fake Feb 29, 1900 at serial 60
    if d >= MARCH_1_1900:
        serial += 1.0

    return serial + time_fraction


def excel_to_datetime(serial: float, date_only: bool = False) -> datetime | date:
    """Convert an Excel serial number to Python datetime.

    Args:
        serial: Excel serial number.
        date_only: If True, return date object instead of datetime.

    Returns:
        Python datetime (or date if date_only=True).

    Examples:
        >>> excel_to_datetime(1.0)
        datetime(1900, 1, 1, 0, 0)
        >>> excel_to_datetime(45292.5)
        datetime(2024, 1, 1, 12, 0, 0)
    """
    # Handle 1900 bug: serials >= 60 (fake Feb 29, 1900 and later) need adjustment
    adjusted_serial = serial
    if serial >= FAKE_FEB_29_SERIAL:
        adjusted_serial -= 1.0

    # Split into days and time fraction
    days = int(adjusted_serial)
    time_fraction = adjusted_serial - days

    # Calculate date
    d = EXCEL_EPOCH + timedelta(days=days)

    if date_only:
        return d

    # Calculate time from fraction
    t = _fraction_to_time(time_fraction)
    return datetime.combine(d, t)


def excel_to_date(serial: float) -> date:
    """Convert an Excel serial number to Python date.

    Convenience function that always returns a date object.
    """
    result = excel_to_datetime(serial, date_only=True)
    if isinstance(result, datetime):
        return result.date()
    return result


def excel_to_time(serial: float) -> time:
    """Convert an Excel serial fraction to Python time.

    Only the fractional part is used; the integer part (days) is ignored.
    """
    fraction = serial - int(serial)
    return _fraction_to_time(fraction)


def is_date_format(format_code: str | None) -> bool:
    """Check if a number format code indicates a date/time format.

    This is a heuristic check based on common date/time format patterns.

    Args:
        format_code: Excel number format code (e.g., "mm-dd-yy", "h:mm:ss").

    Returns:
        True if the format appears to be a date/time format.
    """
    if not format_code:
        return False

    # Normalize for comparison
    code = format_code.lower()

    # Skip obvious non-date formats
    if code in ("general", "@", "0", "0.00", "#,##0", "#,##0.00"):
        return False

    # Date indicators (case-insensitive)
    date_tokens = {"y", "m", "d"}  # year, month, day
    time_tokens = {"h", "s"}  # hour, second (m is ambiguous - could be minute)

    # Check for date/time tokens outside of quoted strings
    in_quote = False
    found_date = False
    found_time = False

    i = 0
    while i < len(code):
        char = code[i]

        if char == '"':
            in_quote = not in_quote
        elif not in_quote:
            if char in date_tokens:
                found_date = True
            elif char in time_tokens:
                found_time = True
            # 'm' next to 'h' or 's' is minutes, otherwise it's month
            elif char == "m":
                # Check context
                prev_char = code[i - 1] if i > 0 else ""
                next_char = code[i + 1] if i < len(code) - 1 else ""
                if prev_char in ("h", ":") or next_char in ("s", ":"):
                    found_time = True  # minutes
                else:
                    found_date = True  # month

        i += 1

    return found_date or found_time


def _time_to_fraction(t: time) -> float:
    """Convert time to fraction of day."""
    seconds = t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1_000_000
    return seconds / 86400  # 86400 = seconds per day


def _fraction_to_time(fraction: float) -> time:
    """Convert fraction of day to time."""
    total_seconds = fraction * 86400
    hours = int(total_seconds // 3600)
    remaining = total_seconds - hours * 3600
    minutes = int(remaining // 60)
    seconds = int(remaining - minutes * 60)
    microseconds = int((remaining - minutes * 60 - seconds) * 1_000_000)

    # Clamp to valid range
    hours = min(hours, 23)
    minutes = min(minutes, 59)
    seconds = min(seconds, 59)
    microseconds = min(microseconds, 999999)

    return time(hours, minutes, seconds, microseconds)
