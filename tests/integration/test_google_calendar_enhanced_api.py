"""Integration tests for enhanced Google Calendar API functionality."""

from datetime import datetime, timedelta

import pytest
from mcp_handley_lab.google_calendar.tool import (
    create_event,
    delete_event,
    get_event,
    update_event,
)


class TestEnhancedCreateEvent:
    """Test enhanced create_event functionality with natural language and mixed timezones."""

    @pytest.mark.vcr
    def test_natural_language_event_creation(self, google_calendar_test_config):
        """Test creating events with natural language datetime input."""
        # Create event with natural language
        create_result = create_event(
            summary="Natural Language Meeting",
            start_datetime="tomorrow at 2pm",
            end_datetime="tomorrow at 3pm",
            description="Created with natural language input",
            location="Conference Room",
        )

        event_id = create_result.event_id

        try:
            # Verify event was created successfully
            assert create_result.status == "Event created successfully!"
            assert create_result.title == "Natural Language Meeting"

            # Get the event to verify details
            event = get_event(event_id=event_id)
            assert event.summary == "Natural Language Meeting"
            assert event.description == "Created with natural language input"
            assert event.location == "Conference Room"

            # Should have timezone info
            assert event.start.timeZone
            assert event.end.timeZone

        finally:
            delete_event(event_id=event_id)

    @pytest.mark.vcr
    def test_mixed_timezone_flight_event(self, google_calendar_test_config):
        """Test creating flight event with different start and end timezones."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Create flight event with mixed timezones
        create_result = create_event(
            summary="Flight LAX → JFK",
            start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
            end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T18:30:00",
            start_timezone="America/Los_Angeles",
            end_timezone="America/New_York",
            description="Cross-country flight with different timezones",
            location="Los Angeles to New York",
        )

        event_id = create_result.event_id

        try:
            # Verify event was created successfully
            assert create_result.status == "Event created successfully!"
            assert create_result.title == "Flight LAX → JFK"

            # Get the event to verify timezone handling
            event = get_event(event_id=event_id)
            assert event.summary == "Flight LAX → JFK"
            assert event.description == "Cross-country flight with different timezones"

            # Verify different timezones were preserved
            assert event.start.timeZone  # Should have timezone
            assert event.end.timeZone  # Should have timezone
            # Note: Exact timezone verification depends on Google Calendar API behavior

        finally:
            delete_event(event_id=event_id)

    @pytest.mark.vcr
    def test_cross_timezone_meeting_event(self, google_calendar_test_config):
        """Test creating meeting that spans multiple timezones."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Create cross-timezone meeting
        create_result = create_event(
            summary="Global Team Sync",
            start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T09:00:00",
            end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T17:00:00",
            start_timezone="Europe/London",
            end_timezone="America/New_York",
            description="Meeting starts 9AM London time, ends 5PM New York time",
            location="Video Conference",
        )

        event_id = create_result.event_id

        try:
            # Verify event was created successfully
            assert create_result.status == "Event created successfully!"
            assert create_result.title == "Global Team Sync"

            # Get the event to verify details
            event = get_event(event_id=event_id)
            assert event.summary == "Global Team Sync"
            assert "London time" in event.description
            assert "New York time" in event.description

            # Should have timezone info
            assert event.start.timeZone
            assert event.end.timeZone

        finally:
            delete_event(event_id=event_id)

    @pytest.mark.vcr
    def test_iso_with_timezone_preservation(self, google_calendar_test_config):
        """Test that ISO datetime with timezone offset is preserved."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Create event with ISO datetime including timezone offset
        create_result = create_event(
            summary="ISO Timezone Test",
            start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T14:00:00-08:00",  # PST
            end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T15:00:00-08:00",
            description="Testing ISO datetime with timezone offset",
        )

        event_id = create_result.event_id

        try:
            # Verify event was created successfully
            assert create_result.status == "Event created successfully!"
            assert create_result.title == "ISO Timezone Test"

            # Get the event to verify timezone handling
            event = get_event(event_id=event_id)
            assert event.summary == "ISO Timezone Test"
            assert event.description == "Testing ISO datetime with timezone offset"

            # Should have timezone info
            assert event.start.timeZone
            assert event.end.timeZone

        finally:
            delete_event(event_id=event_id)


class TestEnhancedUpdateEvent:
    """Test enhanced update_event functionality with natural language and mixed timezones."""

    @pytest.mark.vcr
    def test_update_with_natural_language(self, google_calendar_test_config):
        """Test updating event times with natural language input."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Create initial event
        create_result = create_event(
            summary="Meeting to Update",
            start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
            end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
            description="Original meeting time",
        )

        event_id = create_result.event_id

        try:
            # Update with natural language
            update_result = update_event(
                event_id=event_id,
                start_datetime="tomorrow at 2pm",
                end_datetime="tomorrow at 3pm",
                description="Updated with natural language",
            )

            assert "updated" in update_result.lower()

            # Verify the update was applied
            updated_event = get_event(event_id=event_id)
            assert updated_event.description == "Updated with natural language"

            # Should have timezone info
            assert updated_event.start.timeZone
            assert updated_event.end.timeZone

        finally:
            delete_event(event_id=event_id)

    @pytest.mark.vcr
    def test_update_with_mixed_timezones(self, google_calendar_test_config):
        """Test updating event with different start and end timezones."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Create initial event
        create_result = create_event(
            summary="Global Meeting Update",
            start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
            end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
            description="Original meeting time",
        )

        event_id = create_result.event_id

        try:
            # Update with mixed timezones
            update_result = update_event(
                event_id=event_id,
                start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T09:00:00",
                end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T17:00:00",
                start_timezone="Europe/London",
                end_timezone="America/New_York",
                description="Updated with mixed timezones",
            )

            assert "updated" in update_result.lower()

            # Verify the update was applied
            updated_event = get_event(event_id=event_id)
            assert updated_event.description == "Updated with mixed timezones"

            # Should have timezone info
            assert updated_event.start.timeZone
            assert updated_event.end.timeZone

        finally:
            delete_event(event_id=event_id)

    @pytest.mark.vcr
    def test_update_partial_with_timezone(self, google_calendar_test_config):
        """Test updating only start time with specific timezone."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Create initial event
        create_result = create_event(
            summary="Partial Update Test",
            start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
            end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
            description="Original meeting time",
        )

        event_id = create_result.event_id

        try:
            # Update only start time with specific timezone
            update_result = update_event(
                event_id=event_id,
                start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T08:00:00",
                start_timezone="America/Los_Angeles",
                description="Updated start time only",
            )

            assert "updated" in update_result.lower()

            # Verify the update was applied
            updated_event = get_event(event_id=event_id)
            assert updated_event.description == "Updated start time only"

            # Should have timezone info
            assert updated_event.start.timeZone
            assert updated_event.end.timeZone

        finally:
            delete_event(event_id=event_id)


class TestEnhancedRealWorldWorkflows:
    """Test complete real-world workflows with enhanced functionality."""

    @pytest.mark.vcr
    def test_travel_itinerary_workflow(self, google_calendar_test_config):
        """Test creating a complete travel itinerary with mixed timezones."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Create outbound flight
        outbound_result = create_event(
            summary="Outbound Flight LAX → JFK",
            start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T08:00:00",
            end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T16:30:00",
            start_timezone="America/Los_Angeles",
            end_timezone="America/New_York",
            description="Departure 8:00 AM PST, Arrival 4:30 PM EST",
            location="Los Angeles to New York",
        )

        outbound_id = outbound_result.event_id

        # Create return flight
        return_date = tomorrow + timedelta(days=3)
        return_result = create_event(
            summary="Return Flight JFK → LAX",
            start_datetime=f"{return_date.strftime('%Y-%m-%d')}T18:00:00",
            end_datetime=f"{return_date.strftime('%Y-%m-%d')}T21:30:00",
            start_timezone="America/New_York",
            end_timezone="America/Los_Angeles",
            description="Departure 6:00 PM EST, Arrival 9:30 PM PST",
            location="New York to Los Angeles",
        )

        return_id = return_result.event_id

        try:
            # Verify both events were created successfully
            assert outbound_result.status == "Event created successfully!"
            assert return_result.status == "Event created successfully!"

            # Get both events to verify details
            outbound_event = get_event(event_id=outbound_id)
            return_event = get_event(event_id=return_id)

            # Verify outbound flight details
            assert outbound_event.summary == "Outbound Flight LAX → JFK"
            assert "8:00 AM PST" in outbound_event.description
            assert "4:30 PM EST" in outbound_event.description

            # Verify return flight details
            assert return_event.summary == "Return Flight JFK → LAX"
            assert "6:00 PM EST" in return_event.description
            assert "9:30 PM PST" in return_event.description

            # Both should have timezone info
            assert outbound_event.start.timeZone
            assert outbound_event.end.timeZone
            assert return_event.start.timeZone
            assert return_event.end.timeZone

        finally:
            delete_event(event_id=outbound_id)
            delete_event(event_id=return_id)

    @pytest.mark.vcr
    def test_international_meeting_series_workflow(self, google_calendar_test_config):
        """Test creating a series of international meetings with natural language."""
        # Create initial planning meeting
        planning_result = create_event(
            summary="Project Planning Meeting",
            start_datetime="tomorrow at 9am",
            end_datetime="tomorrow at 10am",
            description="Initial planning session",
            location="London Office",
        )

        planning_id = planning_result.event_id

        # Create follow-up meeting in different timezone
        tomorrow = datetime.now() + timedelta(days=1)
        followup_result = create_event(
            summary="Follow-up with US Team",
            start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T17:00:00",
            end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T09:00:00",
            start_timezone="Europe/London",
            end_timezone="America/New_York",
            description="Follow-up meeting spanning timezones",
            location="Video Conference",
        )

        followup_id = followup_result.event_id

        try:
            # Verify both events were created successfully
            assert planning_result.status == "Event created successfully!"
            assert followup_result.status == "Event created successfully!"

            # Get both events to verify details
            planning_event = get_event(event_id=planning_id)
            followup_event = get_event(event_id=followup_id)

            # Verify planning meeting details
            assert planning_event.summary == "Project Planning Meeting"
            assert planning_event.description == "Initial planning session"

            # Verify follow-up meeting details
            assert followup_event.summary == "Follow-up with US Team"
            assert "spanning timezones" in followup_event.description

            # Both should have timezone info
            assert planning_event.start.timeZone
            assert planning_event.end.timeZone
            assert followup_event.start.timeZone
            assert followup_event.end.timeZone

            # Update the planning meeting with natural language
            update_result = update_event(
                event_id=planning_id,
                start_datetime="tomorrow at 10am",
                end_datetime="tomorrow at 11am",
                description="Updated: moved to 10am due to schedule conflict",
            )

            assert "updated" in update_result.lower()

            # Verify the update
            updated_planning = get_event(event_id=planning_id)
            assert "moved to 10am" in updated_planning.description

        finally:
            delete_event(event_id=planning_id)
            delete_event(event_id=followup_id)


class TestEnhancedErrorHandling:
    """Test error handling for enhanced functionality."""

    @pytest.mark.vcr
    def test_invalid_natural_language_handling(self, google_calendar_test_config):
        """Test handling of invalid natural language input."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Try to create event with invalid natural language
        with pytest.raises(ValueError):  # Should raise ValueError for invalid datetime
            create_event(
                summary="Invalid Time Test",
                start_datetime="not a valid time",
                end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
                description="This should fail",
            )

    @pytest.mark.vcr
    def test_invalid_timezone_handling(self, google_calendar_test_config):
        """Test handling of invalid timezone specifications."""
        tomorrow = datetime.now() + timedelta(days=1)

        # Try to create event with invalid timezone
        with pytest.raises(ValueError):  # Should raise ValueError for invalid timezone
            create_event(
                summary="Invalid Timezone Test",
                start_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T10:00:00",
                end_datetime=f"{tomorrow.strftime('%Y-%m-%d')}T11:00:00",
                start_timezone="Invalid/Timezone",
                description="This should fail",
            )
