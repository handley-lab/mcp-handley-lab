"""Unit tests for Google Maps tool functionality."""
from unittest.mock import MagicMock, patch

import pytest
from mcp_handley_lab.google_maps.tool import (
    DirectionLeg,
    DirectionRoute,
    DirectionStep,
    _get_maps_client,
    _parse_leg,
    _parse_route,
    _parse_step,
    server_info,
)


class TestClientInitialization:
    """Test Google Maps client initialization."""

    @patch("mcp_handley_lab.google_maps.tool.settings")
    @patch("mcp_handley_lab.google_maps.tool.googlemaps.Client")
    def test_get_maps_client(self, mock_client_class, mock_settings):
        """Test client initialization with API key from config."""
        mock_settings.google_maps_api_key = "test_api_key"
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        client = _get_maps_client()

        mock_client_class.assert_called_once_with(key="test_api_key")
        assert client == mock_client


class TestDataParsing:
    """Test data parsing functions."""

    @pytest.mark.parametrize(
        "step_data,expected_instruction,expected_distance,expected_duration",
        [
            (
                {
                    "html_instructions": "Turn left onto Main St",
                    "distance": {"text": "0.5 km"},
                    "duration": {"text": "2 min"},
                    "start_location": {"lat": 40.7128, "lng": -74.0060},
                    "end_location": {"lat": 40.7130, "lng": -74.0065},
                },
                "Turn left onto Main St",
                "0.5 km",
                "2 min",
            ),
            (
                {
                    "html_instructions": "Continue straight",
                    "distance": {"text": "1.2 km"},
                    "duration": {"text": "5 min"},
                    "start_location": {"lat": 40.7200, "lng": -74.0100},
                    "end_location": {"lat": 40.7250, "lng": -74.0150},
                },
                "Continue straight",
                "1.2 km",
                "5 min",
            ),
        ],
    )
    def test_parse_step(
        self, step_data, expected_instruction, expected_distance, expected_duration
    ):
        """Test step parsing from API response."""
        step = _parse_step(step_data)

        assert isinstance(step, DirectionStep)
        assert step.instruction == expected_instruction
        assert step.distance == expected_distance
        assert step.duration == expected_duration
        assert step.start_location == step_data["start_location"]
        assert step.end_location == step_data["end_location"]

    @pytest.mark.parametrize(
        "leg_data,expected_distance,expected_duration,expected_steps_count",
        [
            (
                {
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
                },
                "5.2 km",
                "12 min",
                1,
            ),
            (
                {
                    "distance": {"text": "10.5 km"},
                    "duration": {"text": "25 min"},
                    "start_address": "Origin Location",
                    "end_address": "Destination Location",
                    "steps": [
                        {
                            "html_instructions": "Head east",
                            "distance": {"text": "0.2 km"},
                            "duration": {"text": "1 min"},
                            "start_location": {"lat": 40.7128, "lng": -74.0060},
                            "end_location": {"lat": 40.7129, "lng": -74.0060},
                        },
                        {
                            "html_instructions": "Turn right",
                            "distance": {"text": "0.3 km"},
                            "duration": {"text": "2 min"},
                            "start_location": {"lat": 40.7129, "lng": -74.0060},
                            "end_location": {"lat": 40.7130, "lng": -74.0065},
                        },
                    ],
                },
                "10.5 km",
                "25 min",
                2,
            ),
        ],
    )
    def test_parse_leg(
        self, leg_data, expected_distance, expected_duration, expected_steps_count
    ):
        """Test leg parsing from API response."""
        leg = _parse_leg(leg_data)

        assert isinstance(leg, DirectionLeg)
        assert leg.distance == expected_distance
        assert leg.duration == expected_duration
        assert leg.start_address == leg_data["start_address"]
        assert leg.end_address == leg_data["end_address"]
        assert len(leg.steps) == expected_steps_count

    @pytest.mark.parametrize(
        "route_data,expected_summary,expected_warnings_count",
        [
            (
                {
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
                },
                "Main St to Broadway",
                1,
            ),
            (
                {
                    "summary": "Highway Route",
                    "legs": [
                        {
                            "distance": {"text": "10.0 km", "value": 10000},
                            "duration": {"text": "15 min", "value": 900},
                            "start_address": "Origin",
                            "end_address": "Destination",
                            "steps": [
                                {
                                    "html_instructions": "Take highway",
                                    "distance": {"text": "10.0 km"},
                                    "duration": {"text": "15 min"},
                                    "start_location": {"lat": 40.7128, "lng": -74.0060},
                                    "end_location": {"lat": 40.7129, "lng": -74.0060},
                                }
                            ],
                        }
                    ],
                    "overview_polyline": {"points": "different_polyline"},
                    "warnings": [],
                },
                "Highway Route",
                0,
            ),
        ],
    )
    def test_parse_route(self, route_data, expected_summary, expected_warnings_count):
        """Test route parsing from API response."""
        route = _parse_route(route_data)

        assert isinstance(route, DirectionRoute)
        assert route.summary == expected_summary
        assert (
            route.distance
            == f"{sum(leg['distance']['value'] for leg in route_data['legs']) / 1000:.1f} km"
        )
        assert (
            route.duration
            == f"{sum(leg['duration']['value'] for leg in route_data['legs']) // 60} min"
        )
        assert route.polyline == route_data["overview_polyline"]["points"]
        assert len(route.warnings) == expected_warnings_count
        assert len(route.legs) == 1


class TestServerInfo:
    """Test server information functionality."""

    def test_server_info(self):
        """Test server info returns expected data."""
        info = server_info()

        assert info.name == "Google Maps Tool"
        assert info.version == "0.4.0"
        assert info.status == "active"
        assert "directions" in info.capabilities
        assert "multiple_transport_modes" in info.capabilities
        assert "waypoint_support" in info.capabilities
        assert "traffic_aware_routing" in info.capabilities
        assert "alternative_routes" in info.capabilities
        assert "googlemaps" in info.dependencies
