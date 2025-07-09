"""Integration tests for Google Maps tool with VCR recording."""
import os
from pathlib import Path

import pytest
import vcr
from mcp_handley_lab.google_maps.tool import (
    DirectionsResult,
    get_directions,
)


# VCR configuration for Google Maps API
def scrub_api_key(response):
    """Scrub API key from recorded requests."""
    return response


google_maps_vcr = vcr.VCR(
    serializer="json",
    cassette_library_dir=str(Path(__file__).parent / "vcr_cassettes"),
    record_mode="once",
    match_on=["method", "scheme", "host", "port", "path", "query"],
    filter_query_parameters=["key"],
    before_record_response=scrub_api_key,
)


@pytest.fixture
def api_key():
    """Provide API key for testing."""
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key:
        pytest.skip("GOOGLE_MAPS_API_KEY not set")
    return key


@pytest.fixture
def mock_api_key(monkeypatch):
    """Mock API key for VCR tests."""
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test_api_key")


@pytest.mark.integration
class TestGoogleMapsIntegration:
    """Integration tests for Google Maps functionality."""

    @google_maps_vcr.use_cassette("test_directions_basic.json")
    def test_directions_basic(self, mock_api_key):
        """Test basic directions request."""
        result = get_directions(
            origin="Times Square, New York, NY",
            destination="Brooklyn Bridge, New York, NY",
            mode="driving",
        )

        assert isinstance(result, DirectionsResult)
        assert result.status == "OK"
        assert len(result.routes) >= 1

        route = result.routes[0]
        assert route.summary
        assert route.distance
        assert route.duration
        assert route.polyline
        assert len(route.legs) >= 1

        leg = route.legs[0]
        assert leg.start_address
        assert leg.end_address
        assert leg.distance
        assert leg.duration
        assert len(leg.steps) >= 1

    @google_maps_vcr.use_cassette("test_directions_transit.json")
    def test_directions_transit(self, mock_api_key):
        """Test transit directions request."""
        result = get_directions(
            origin="Grand Central Terminal, New York, NY",
            destination="JFK Airport, New York, NY",
            mode="transit",
        )

        assert isinstance(result, DirectionsResult)
        assert result.status == "OK"
        assert result.mode == "transit"
        assert len(result.routes) >= 1

    @google_maps_vcr.use_cassette("test_directions_with_waypoints.json")
    def test_directions_with_waypoints(self, mock_api_key):
        """Test directions with waypoints."""
        result = get_directions(
            origin="Times Square, New York, NY",
            destination="Brooklyn Bridge, New York, NY",
            waypoints=["Central Park, New York, NY"],
            mode="driving",
        )

        assert isinstance(result, DirectionsResult)
        assert result.status == "OK"
        assert len(result.routes) >= 1

    @google_maps_vcr.use_cassette("test_directions_alternatives.json")
    def test_directions_alternatives(self, mock_api_key):
        """Test directions with alternatives."""
        result = get_directions(
            origin="Times Square, New York, NY",
            destination="Brooklyn Bridge, New York, NY",
            alternatives=True,
            mode="driving",
        )

        assert isinstance(result, DirectionsResult)
        assert result.status == "OK"
        # May have multiple routes if alternatives are available
        assert len(result.routes) >= 1

    @google_maps_vcr.use_cassette("test_directions_avoid_options.json")
    def test_directions_avoid_options(self, mock_api_key):
        """Test directions with avoid options."""
        result = get_directions(
            origin="Times Square, New York, NY",
            destination="Brooklyn Bridge, New York, NY",
            avoid_tolls=True,
            avoid_highways=True,
            mode="driving",
        )

        assert isinstance(result, DirectionsResult)
        assert result.status == "OK"
        assert len(result.routes) >= 1

    @google_maps_vcr.use_cassette("test_walking_directions.json")
    def test_walking_directions(self, mock_api_key):
        """Test walking directions."""
        result = get_directions(
            origin="Times Square, New York, NY",
            destination="Central Park, New York, NY",
            mode="walking",
        )

        assert isinstance(result, DirectionsResult)
        assert result.status == "OK"
        assert result.mode == "walking"
        assert len(result.routes) >= 1

    @google_maps_vcr.use_cassette("test_bicycling_directions.json")
    def test_bicycling_directions(self, mock_api_key):
        """Test bicycling directions."""
        result = get_directions(
            origin="Times Square, New York, NY",
            destination="Central Park, New York, NY",
            mode="bicycling",
        )

        assert isinstance(result, DirectionsResult)
        assert result.status == "OK"
        assert result.mode == "bicycling"
        assert len(result.routes) >= 1


@pytest.mark.integration
class TestGoogleMapsErrorHandling:
    """Test error handling in integration scenarios."""

    @google_maps_vcr.use_cassette("test_invalid_location.json")
    def test_invalid_location(self, mock_api_key):
        """Test handling of invalid location fails fast."""
        import googlemaps.exceptions

        with pytest.raises(googlemaps.exceptions.ApiError):
            get_directions(
                origin="Invalid Location That Does Not Exist",
                destination="Another Invalid Location",
                mode="driving",
            )

    @google_maps_vcr.use_cassette("test_unreachable_destination.json")
    def test_unreachable_destination(self, mock_api_key):
        """Test handling of unreachable destination."""
        result = get_directions(
            origin="New York, NY", destination="Hawaii", mode="driving"
        )

        # Should handle gracefully
        assert isinstance(result, DirectionsResult)
        # May return no routes or a specific error
        assert result.status in ["NO_ROUTES_FOUND", "OK"] or result.status.startswith(
            "ERROR:"
        )


@pytest.mark.integration
class TestGoogleMapsSpecialCases:
    """Test special cases and edge scenarios."""

    @google_maps_vcr.use_cassette("test_same_origin_destination.json")
    def test_same_origin_destination(self, mock_api_key):
        """Test directions with same origin and destination."""
        result = get_directions(
            origin="Times Square, New York, NY",
            destination="Times Square, New York, NY",
            mode="driving",
        )

        assert isinstance(result, DirectionsResult)
        # Should handle gracefully
        assert result.status in ["OK", "NO_ROUTES_FOUND"] or result.status.startswith(
            "ERROR:"
        )

    @google_maps_vcr.use_cassette("test_coordinates_input.json")
    def test_coordinates_input(self, mock_api_key):
        """Test directions with coordinate inputs."""
        result = get_directions(
            origin="40.7128,-74.0060",  # NYC coordinates
            destination="40.7580,-73.9855",  # Times Square coordinates
            mode="driving",
        )

        assert isinstance(result, DirectionsResult)
        assert result.status == "OK"
        assert len(result.routes) >= 1
