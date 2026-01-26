"""Core Google Maps functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

from typing import Literal

from mcp_handley_lab.google_maps.tool import (
    DEFAULT_TIMEZONE,
    DirectionsResult,
    _generate_maps_url,
    _get_maps_client,
    _parse_flexible_datetime,
    _parse_route,
)
from mcp_handley_lab.shared.models import ServerInfo


def get_directions(
    origin: str,
    destination: str,
    mode: Literal["driving", "walking", "bicycling", "transit"] = "driving",
    departure_time: str = "",
    arrival_time: str = "",
    user_timezone: str = DEFAULT_TIMEZONE,
    avoid: list[Literal["tolls", "highways", "ferries"]] | None = None,
    alternatives: bool = False,
    waypoints: list[str] | None = None,
    transit_mode: list[Literal["bus", "subway", "train", "tram", "rail"]] | None = None,
    transit_routing_preference: Literal["", "less_walking", "fewer_transfers"] = "",
) -> DirectionsResult:
    """Get directions between an origin and destination.

    Args:
        origin: The starting address, place name, or coordinates.
        destination: The ending address, place name, or coordinates.
        mode: The mode of transport ('driving', 'walking', 'bicycling', 'transit').
        departure_time: The desired departure time. Supports natural language
            ('17:00', '5pm', 'tomorrow 5pm'), relative times ('in 2 hours'),
            or ISO 8601 formats. Cannot be used with arrival_time.
        arrival_time: The desired arrival time. Same format as departure_time.
            Cannot be used with departure_time.
        user_timezone: The timezone for interpreting times (e.g., 'Europe/London').
        avoid: A list of route features to avoid ('tolls', 'highways', 'ferries').
            Only for 'driving' mode.
        alternatives: If True, requests alternative routes in the response.
        waypoints: A list of addresses/coordinates to route through.
        transit_mode: Preferred modes of public transit. Only for 'transit' mode.
        transit_routing_preference: Preferences for transit routes
            ('less_walking', 'fewer_transfers'). Only for 'transit' mode.

    Returns:
        DirectionsResult with routes and status.
    """
    gmaps = _get_maps_client()

    # Parse departure/arrival time with flexible parsing
    departure_dt = None
    arrival_dt = None
    if departure_time:
        departure_dt = _parse_flexible_datetime(departure_time, user_timezone)
    if arrival_time:
        arrival_dt = _parse_flexible_datetime(arrival_time, user_timezone)

    # Make API request
    result = gmaps.directions(
        origin=origin,
        destination=destination,
        mode=mode,
        departure_time=departure_dt,
        arrival_time=arrival_dt,
        avoid=avoid or [],
        alternatives=alternatives,
        waypoints=waypoints or [],
        transit_mode=transit_mode or [],
        transit_routing_preference=transit_routing_preference,
    )

    if not result:
        return DirectionsResult(
            routes=[],
            status="NO_ROUTES_FOUND",
            origin=origin,
            destination=destination,
            mode=mode,
            departure_time=departure_time,
            maps_url="",
        )

    # Parse routes
    routes = [_parse_route(route, user_timezone) for route in result]

    # Generate Google Maps URL
    maps_url = _generate_maps_url(
        origin,
        destination,
        mode,
        waypoints,
        departure_dt.isoformat() if departure_dt else "",
        arrival_dt.isoformat() if arrival_dt else "",
        avoid,
        transit_mode,
        transit_routing_preference,
        api_result=result,
    )

    return DirectionsResult(
        routes=routes,
        status="OK",
        origin=origin,
        destination=destination,
        mode=mode,
        departure_time=departure_time,
        maps_url=maps_url,
    )


def server_info() -> ServerInfo:
    """Get Google Maps Tool server information and capabilities.

    Returns:
        ServerInfo with name, version, status, and capabilities.
    """
    return ServerInfo(
        name="Google Maps Tool",
        version="0.4.0",
        status="active",
        capabilities=[
            "get_directions",
            "server_info",
            "directions",
            "multiple_transport_modes",
            "waypoint_support",
            "traffic_aware_routing",
            "alternative_routes",
        ],
        dependencies={"googlemaps": "4.0.0+", "pydantic": "2.0.0+", "mcp": "1.0.0+"},
    )
