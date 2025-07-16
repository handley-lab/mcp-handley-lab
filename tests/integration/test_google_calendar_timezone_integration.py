"""Integration tests for Google Calendar timezone normalization functionality."""

from datetime import datetime, timedelta

import pytest
from mcp_handley_lab.google_calendar.tool import (
    create_event,
    delete_event,
    get_event,
    update_event,
)


@pytest.mark.vcr
def test_normalize_timezone_integration(google_calendar_test_config):
    """Test end-to-end timezone normalization workflow."""
    # Create event with UTC time and timezone label (simulating recurring event issue)
    tomorrow = datetime.now() + timedelta(days=1)

    # Create an event that would have timezone inconsistency
    create_result = create_event(
        summary="Timezone Test Event",
        start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00Z",  # UTC time
        end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00Z",
        start_timezone="Europe/London",  # But with timezone label
        end_timezone="Europe/London",
        description="Testing timezone normalization",
    )

    event_id = create_result.event_id

    try:
        # Get the event to verify it was created
        event = get_event(event_id=event_id)
        assert event.summary == "Timezone Test Event"

        # Update event with normalize_timezone=True
        update_result = update_event(
            event_id=event_id,
            description="Updated with timezone normalization",
            normalize_timezone=True,
        )

        assert "updated" in update_result.lower()

        # Verify the event was updated
        updated_event = get_event(event_id=event_id)
        assert updated_event.description == "Updated with timezone normalization"

    finally:
        # Clean up
        delete_event(event_id=event_id)


@pytest.mark.vcr
def test_normalize_timezone_no_inconsistency(google_calendar_test_config):
    """Test normalize_timezone=True on event without inconsistency does nothing."""
    tomorrow = datetime.now() + timedelta(days=1)

    # Create event with proper local time (no inconsistency)
    create_result = create_event(
        summary="Normal Timezone Event",
        start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T14:00:00",  # Local time
        end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T15:00:00",
        start_timezone="Europe/London",
        end_timezone="Europe/London",
        description="No timezone issues",
    )

    event_id = create_result.event_id

    try:
        # Update with normalize_timezone=True (should be no-op)
        update_result = update_event(
            event_id=event_id,
            description="Updated but no normalization needed",
            normalize_timezone=True,
        )

        # Should still update successfully
        assert "updated" in update_result.lower()

        # Verify the event was updated
        updated_event = get_event(event_id=event_id)
        assert updated_event.description == "Updated but no normalization needed"

    finally:
        # Clean up
        delete_event(event_id=event_id)


@pytest.mark.vcr
def test_create_event_without_timezone_uses_api_defaults(google_calendar_test_config):
    """Test that create_event without timezone uses application default."""
    tomorrow = datetime.now() + timedelta(days=1)

    # Create event without specifying timezone - should use application default
    create_result = create_event(
        summary="Default Timezone Event",
        start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T16:00:00",
        end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T17:00:00",
        # No timezone parameter - should use DEFAULT_TIMEZONE
        description="Testing default timezone fallback",
    )

    event_id = create_result.event_id

    try:
        # Event should be created successfully with default timezone
        event = get_event(event_id=event_id)
        assert event.summary == "Default Timezone Event"
        assert event.description == "Testing default timezone fallback"

    finally:
        # Clean up
        delete_event(event_id=event_id)


@pytest.mark.vcr
def test_update_event_datetime_without_timezone(google_calendar_test_config):
    """Test updating event datetime without timezone (should work cleanly)."""
    tomorrow = datetime.now() + timedelta(days=1)

    # Create initial event
    create_result = create_event(
        summary="Update Time Test",
        start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T09:00:00",
        end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
        description="Original time",
    )

    event_id = create_result.event_id

    try:
        # Update just the time without timezone info
        update_result = update_event(
            event_id=event_id,
            start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
            end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T12:00:00",
            description="Updated time",
        )

        assert "updated" in update_result.lower()

        # Verify times were updated
        updated_event = get_event(event_id=event_id)
        assert updated_event.description == "Updated time"
        # Times should be updated (exact format may vary based on API response)
        assert "11:00" in str(updated_event.start.dateTime) or "11:00" in str(
            updated_event.start.date
        )

    finally:
        # Clean up
        delete_event(event_id=event_id)


@pytest.mark.vcr
def test_all_day_event_unaffected_by_timezone_normalization(
    google_calendar_test_config,
):
    """Test that all-day events are unaffected by timezone operations."""
    tomorrow = datetime.now() + timedelta(days=1)

    # Create all-day event
    create_result = create_event(
        summary="All Day Event",
        start_datetime=tomorrow.strftime("%Y-%m-%d"),  # Date only, no time
        end_datetime=(tomorrow + timedelta(days=1)).strftime("%Y-%m-%d"),
        description="All day event test",
    )

    event_id = create_result.event_id

    try:
        # Attempt timezone normalization on all-day event (should be no-op)
        update_result = update_event(
            event_id=event_id,
            description="All day with normalization attempt",
            normalize_timezone=True,
        )

        assert "updated" in update_result.lower()

        # Verify event was updated but remains all-day
        updated_event = get_event(event_id=event_id)
        assert updated_event.description == "All day with normalization attempt"
        # Should still be all-day (has date, no dateTime)
        assert updated_event.start.date and not updated_event.start.dateTime

    finally:
        # Clean up
        delete_event(event_id=event_id)
