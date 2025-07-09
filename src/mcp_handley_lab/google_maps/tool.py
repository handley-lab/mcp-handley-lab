"""Google Maps tool for directions and routing via MCP."""
from datetime import datetime
from typing import Any, Literal

import googlemaps
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.shared.models import ServerInfo


class DirectionStep(BaseModel):
    """A single step in a route."""

    instruction: str
    distance: str
    duration: str
    start_location: dict[str, float]
    end_location: dict[str, float]


class DirectionLeg(BaseModel):
    """A leg of a route (origin to destination or waypoint)."""

    distance: str
    duration: str
    start_address: str
    end_address: str
    steps: list[DirectionStep]


class DirectionRoute(BaseModel):
    """A complete route with all legs and steps."""

    summary: str
    legs: list[DirectionLeg]
    distance: str
    duration: str
    polyline: str
    warnings: list[str] = Field(default_factory=list)


class DirectionsResult(BaseModel):
    """Result of a directions request."""

    routes: list[DirectionRoute]
    status: str
    origin: str
    destination: str
    mode: str
    departure_time: str = ""


mcp = FastMCP("Google Maps Tool")


def _get_maps_client():
    """Get authenticated Google Maps client."""
    return googlemaps.Client(key=settings.google_maps_api_key)


def _parse_step(step: dict[str, Any]) -> DirectionStep:
    """Parse a direction step from API response."""
    return DirectionStep(
        instruction=step["html_instructions"],
        distance=step["distance"]["text"],
        duration=step["duration"]["text"],
        start_location=step["start_location"],
        end_location=step["end_location"],
    )


def _parse_leg(leg: dict[str, Any]) -> DirectionLeg:
    """Parse a direction leg from API response."""
    return DirectionLeg(
        distance=leg["distance"]["text"],
        duration=leg["duration"]["text"],
        start_address=leg["start_address"],
        end_address=leg["end_address"],
        steps=[_parse_step(step) for step in leg["steps"]],
    )


def _parse_route(route: dict[str, Any]) -> DirectionRoute:
    """Parse a route from API response."""
    legs = [_parse_leg(leg) for leg in route["legs"]]

    # Calculate total distance and duration
    total_distance = sum(leg["distance"]["value"] for leg in route["legs"])
    total_duration = sum(leg["duration"]["value"] for leg in route["legs"])

    # Convert to human-readable format
    distance_text = f"{total_distance / 1000:.1f} km"
    duration_text = f"{total_duration // 60} min"

    return DirectionRoute(
        summary=route["summary"],
        legs=legs,
        distance=distance_text,
        duration=duration_text,
        polyline=route["overview_polyline"]["points"],
        warnings=route.get("warnings", []),
    )


@mcp.tool(
    description="Gets directions between an origin and destination, supporting multiple travel modes, waypoints, and route preferences like avoiding tolls or highways."
)
def get_directions(
    origin: str,
    destination: str,
    mode: Literal["driving", "walking", "bicycling", "transit"] = "driving",
    departure_time: str = "",
    avoid_tolls: bool = False,
    avoid_highways: bool = False,
    avoid_ferries: bool = False,
    alternatives: bool = False,
    waypoints: list[str] = [],
) -> DirectionsResult:
    gmaps = _get_maps_client()

    # Parse departure time if provided
    departure_dt = None
    if departure_time:
        departure_dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))

    # Build avoid list
    avoid_options = {
        "tolls": avoid_tolls,
        "highways": avoid_highways,
        "ferries": avoid_ferries,
    }
    avoid = [option for option, enabled in avoid_options.items() if enabled]

    # Make API request
    result = gmaps.directions(
        origin=origin,
        destination=destination,
        mode=mode,
        departure_time=departure_dt,
        avoid=avoid if avoid else None,
        alternatives=alternatives,
        waypoints=waypoints if waypoints else None,
    )

    if not result:
        return DirectionsResult(
            routes=[],
            status="NO_ROUTES_FOUND",
            origin=origin,
            destination=destination,
            mode=mode,
            departure_time=departure_time,
        )

    # Parse routes
    routes = [_parse_route(route) for route in result]

    return DirectionsResult(
        routes=routes,
        status="OK",
        origin=origin,
        destination=destination,
        mode=mode,
        departure_time=departure_time,
    )


@mcp.tool(description="Get Google Maps Tool server information and capabilities.")
def server_info() -> ServerInfo:
    return ServerInfo(
        name="Google Maps Tool",
        version="0.4.0",
        status="active",
        capabilities=[
            "directions",
            "multiple_transport_modes",
            "waypoint_support",
            "traffic_aware_routing",
            "alternative_routes",
        ],
        dependencies={"googlemaps": "4.0.0+", "pydantic": "2.0.0+", "mcp": "1.0.0+"},
    )


if __name__ == "__main__":
    mcp.run()
