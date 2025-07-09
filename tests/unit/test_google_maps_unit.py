"""Unit tests for Google Maps tool functionality."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import googlemaps
import pytest
from mcp_handley_lab.google_maps.tool import (
    DirectionLeg,
    DirectionRoute,
    DirectionsResult,
    DirectionStep,
    _get_maps_client,
    _parse_leg,
    _parse_route,
    _parse_step,
    estimate_travel_time,
    get_directions,
    get_route_alternatives,
    server_info,
)


class TestClientInitialization:
    """Test Google Maps client initialization."""

    @patch("mcp_handley_lab.google_maps.tool.settings")
    @patch("mcp_handley_lab.google_maps.tool.googlemaps.Client")
    def test_get_maps_client_with_config_key(self, mock_client_class, mock_settings):
        """Test client initialization with API key from config."""
        mock_settings.google_maps_api_key = "test_api_key"
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        client = _get_maps_client()

        mock_client_class.assert_called_once_with(key="test_api_key")
        assert client == mock_client

    @patch("mcp_handley_lab.google_maps.tool.settings")
    @patch("mcp_handley_lab.google_maps.tool.os.environ")
    @patch("mcp_handley_lab.google_maps.tool.googlemaps.Client")
    def test_get_maps_client_with_env_key(
        self, mock_client_class, mock_environ, mock_settings
    ):
        """Test client initialization with API key from environment."""
        mock_settings.google_maps_api_key = "YOUR_API_KEY_HERE"
        mock_environ.get.return_value = "env_api_key"
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        client = _get_maps_client()

        mock_environ.get.assert_called_once_with("GOOGLE_MAPS_API_KEY")
        mock_client_class.assert_called_once_with(key="env_api_key")
        assert client == mock_client

    @patch("mcp_handley_lab.google_maps.tool.settings")
    @patch("mcp_handley_lab.google_maps.tool.os.environ")
    def test_get_maps_client_no_key(self, mock_environ, mock_settings):
        """Test client initialization fails without API key."""
        mock_settings.google_maps_api_key = "YOUR_API_KEY_HERE"
        mock_environ.get.return_value = None

        with pytest.raises(ValueError, match="Google Maps API key not found"):
            _get_maps_client()


class TestDataParsing:
    """Test data parsing functions."""

    def test_parse_step(self):
        """Test step parsing from API response."""
        step_data = {
            "html_instructions": "Turn left onto Main St",
            "distance": {"text": "0.5 km"},
            "duration": {"text": "2 min"},
            "start_location": {"lat": 40.7128, "lng": -74.0060},
            "end_location": {"lat": 40.7130, "lng": -74.0065},
        }

        step = _parse_step(step_data)

        assert isinstance(step, DirectionStep)
        assert step.instruction == "Turn left onto Main St"
        assert step.distance == "0.5 km"
        assert step.duration == "2 min"
        assert step.start_location == {"lat": 40.7128, "lng": -74.0060}
        assert step.end_location == {"lat": 40.7130, "lng": -74.0065}

    def test_parse_leg(self):
        """Test leg parsing from API response."""
        leg_data = {
            "distance": {"text": "5.2 km"},
            "duration": {"text": "12 min"},
            "start_address": "123 Start St, City, State",
            "end_address": "456 End Ave, City, State",
            "steps": [
                {
                    "html_instructions": "Head north",
                    "distance": {"text": "0.1 km"},
                    "duration": {"text": "1 min"},
                    "start_location": {"lat": 40.7128, "lng": -74.0060},
                    "end_location": {"lat": 40.7129, "lng": -74.0060},
                }
            ],
        }

        leg = _parse_leg(leg_data)

        assert isinstance(leg, DirectionLeg)
        assert leg.distance == "5.2 km"
        assert leg.duration == "12 min"
        assert leg.start_address == "123 Start St, City, State"
        assert leg.end_address == "456 End Ave, City, State"
        assert len(leg.steps) == 1
        assert leg.steps[0].instruction == "Head north"

    def test_parse_route(self):
        """Test route parsing from API response."""
        route_data = {
            "summary": "Main St to Broadway",
            "legs": [
                {
                    "distance": {"text": "5.2 km", "value": 5200},
                    "duration": {"text": "12 min", "value": 720},
                    "start_address": "123 Start St",
                    "end_address": "456 End Ave",
                    "steps": [
                        {
                            "html_instructions": "Head north",
                            "distance": {"text": "0.1 km"},
                            "duration": {"text": "1 min"},
                            "start_location": {"lat": 40.7128, "lng": -74.0060},
                            "end_location": {"lat": 40.7129, "lng": -74.0060},
                        }
                    ],
                }
            ],
            "overview_polyline": {"points": "encoded_polyline_string"},
            "warnings": ["Toll road ahead"],
        }

        route = _parse_route(route_data)

        assert isinstance(route, DirectionRoute)
        assert route.summary == "Main St to Broadway"
        assert route.distance == "5.2 km"
        assert route.duration == "12 min"
        assert route.polyline == "encoded_polyline_string"
        assert route.warnings == ["Toll road ahead"]
        assert len(route.legs) == 1


class TestDirectionsFunction:
    """Test directions functionality."""

    @patch("mcp_handley_lab.google_maps.tool._get_maps_client")
    def test_get_directions_success(self, mock_get_client):
        """Test successful directions request."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock API response
        mock_response = [
            {
                "summary": "Route via Main St",
                "legs": [
                    {
                        "distance": {"text": "5.2 km", "value": 5200},
                        "duration": {"text": "12 min", "value": 720},
                        "start_address": "Origin Address",
                        "end_address": "Destination Address",
                        "steps": [
                            {
                                "html_instructions": "Head north",
                                "distance": {"text": "0.1 km"},
                                "duration": {"text": "1 min"},
                                "start_location": {"lat": 40.7128, "lng": -74.0060},
                                "end_location": {"lat": 40.7129, "lng": -74.0060},
                            }
                        ],
                    }
                ],
                "overview_polyline": {"points": "encoded_polyline"},
                "warnings": [],
            }
        ]
        mock_client.directions.return_value = mock_response

        result = get_directions("Origin", "Destination", mode="driving")

        assert isinstance(result, DirectionsResult)
        assert result.status == "OK"
        assert result.origin == "Origin"
        assert result.destination == "Destination"
        assert result.mode == "driving"
        assert len(result.routes) == 1
        assert result.routes[0].summary == "Route via Main St"

        mock_client.directions.assert_called_once_with(
            origin="Origin",
            destination="Destination",
            mode="driving",
            departure_time=None,
            avoid=None,
            alternatives=False,
            waypoints=None,
        )

    @patch("mcp_handley_lab.google_maps.tool._get_maps_client")
    def test_get_directions_with_options(self, mock_get_client):
        """Test directions request with advanced options."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.directions.return_value = []

        departure_time = "2024-01-01T09:00:00"

        get_directions(
            "Origin",
            "Destination",
            mode="transit",
            departure_time=departure_time,
            avoid_tolls=True,
            avoid_highways=True,
            alternatives=True,
            waypoints=["Waypoint1", "Waypoint2"],
        )

        # Should parse the departure time
        expected_dt = datetime.fromisoformat(departure_time)

        mock_client.directions.assert_called_once_with(
            origin="Origin",
            destination="Destination",
            mode="transit",
            departure_time=expected_dt,
            avoid=["tolls", "highways"],
            alternatives=True,
            waypoints=["Waypoint1", "Waypoint2"],
        )

    @patch("mcp_handley_lab.google_maps.tool._get_maps_client")
    def test_get_directions_no_routes(self, mock_get_client):
        """Test directions request with no routes found."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.directions.return_value = []

        result = get_directions("Origin", "Destination")

        assert isinstance(result, DirectionsResult)
        assert result.status == "NO_ROUTES_FOUND"
        assert len(result.routes) == 0

    @patch("mcp_handley_lab.google_maps.tool._get_maps_client")
    def test_get_directions_api_error(self, mock_get_client):
        """Test directions request with API error."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.directions.side_effect = googlemaps.exceptions.ApiError("API Error")

        result = get_directions("Origin", "Destination")

        assert isinstance(result, DirectionsResult)
        assert result.status.startswith("ERROR:")
        assert len(result.routes) == 0


class TestTravelTimeEstimation:
    """Test travel time estimation functionality."""

    @patch("mcp_handley_lab.google_maps.tool.get_directions")
    def test_estimate_travel_time_success(self, mock_get_directions):
        """Test successful travel time estimation."""
        mock_route = DirectionRoute(
            summary="Test Route",
            legs=[],
            distance="5.2 km",
            duration="12 min",
            polyline="encoded_polyline",
        )

        mock_result = DirectionsResult(
            routes=[mock_route],
            status="OK",
            origin="Origin",
            destination="Destination",
            mode="driving",
        )
        mock_get_directions.return_value = mock_result

        result = estimate_travel_time("Origin", "Destination")

        assert result["status"] == "OK"
        assert result["travel_time"] == "12 min"
        assert result["distance"] == "5.2 km"
        assert result["summary"] == "Test Route"

    @patch("mcp_handley_lab.google_maps.tool.get_directions")
    def test_estimate_travel_time_no_routes(self, mock_get_directions):
        """Test travel time estimation with no routes."""
        mock_result = DirectionsResult(
            routes=[],
            status="NO_ROUTES_FOUND",
            origin="Origin",
            destination="Destination",
            mode="driving",
        )
        mock_get_directions.return_value = mock_result

        result = estimate_travel_time("Origin", "Destination")

        assert result["error"] == "NO_ROUTES_FOUND"
        assert result["travel_time"] is None


class TestRouteAlternatives:
    """Test route alternatives functionality."""

    @patch("mcp_handley_lab.google_maps.tool.get_directions")
    def test_get_route_alternatives(self, mock_get_directions):
        """Test getting route alternatives."""
        mock_result = DirectionsResult(
            routes=[],
            status="OK",
            origin="Origin",
            destination="Destination",
            mode="driving",
        )
        mock_get_directions.return_value = mock_result

        result = get_route_alternatives("Origin", "Destination", "walking")

        mock_get_directions.assert_called_once_with(
            origin="Origin",
            destination="Destination",
            mode="walking",
            departure_time="",
            alternatives=True,
        )
        assert result == mock_result


class TestServerInfo:
    """Test server information functionality."""

    def test_server_info(self):
        """Test server info returns expected data."""
        info = server_info()

        assert info.name == "Google Maps Tool"
        assert info.version == "0.4.0"
        assert info.status == "active"
        assert "directions" in info.capabilities
        assert "travel_time_estimation" in info.capabilities
        assert "alternative_routes" in info.capabilities
        assert "googlemaps" in info.dependencies
