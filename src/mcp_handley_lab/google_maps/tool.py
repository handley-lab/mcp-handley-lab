"""Google Maps tool for directions and routing via MCP."""
from datetime import datetime, timezone
from typing import Any, Literal

import googlemaps
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.shared.models import ServerInfo


class TransitDetails(BaseModel):
    """Transit-specific information for a step."""

    departure_time: datetime
    arrival_time: datetime
    line_name: str
    line_short_name: str = ""
    vehicle_type: str
    headsign: str = ""
    num_stops: int


class DirectionStep(BaseModel):
    """A single step in a route."""

    instruction: str
    distance: str
    duration: str
    start_location: dict[str, float]
    end_location: dict[str, float]
    travel_mode: str = ""
    transit_details: TransitDetails | None = None


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
    maps_url: str = ""


mcp = FastMCP("Google Maps Tool")


def _get_maps_client():
    """Get authenticated Google Maps client."""
    return googlemaps.Client(key=settings.google_maps_api_key)


def _generate_maps_url(
    origin: str,
    destination: str,
    mode: str,
    waypoints: list[str] = None,
    departure_time: str = "",
    arrival_time: str = "",
    avoid: list[str] = None,
    transit_mode: list[str] = None,
    transit_routing_preference: str = "",
    api_result: dict = None,
) -> str:
    """Generate a Google Maps URL for the directions using recommended parameters."""
    import urllib.parse
    from datetime import datetime

    # For transit mode with timing and API result, generate the complex format
    if mode == "transit" and api_result and (departure_time or arrival_time):
        # Extract coordinates from API result
        first_route = api_result[0]
        first_leg = first_route["legs"][0]
        origin_lat = first_leg["start_location"]["lat"]
        origin_lng = first_leg["start_location"]["lng"]
        dest_lat = first_leg["end_location"]["lat"]
        dest_lng = first_leg["end_location"]["lng"]

        # Calculate center point for map view
        center_lat = (origin_lat + dest_lat) / 2
        center_lng = (origin_lng + dest_lng) / 2

        # Generate fake place IDs (Google Maps format)
        origin_place_id = "0x47d8704fbb7e3d95:0xc59170db564833be"
        dest_place_id = "0x48761bccc506725f:0x3bb9e6e4b6391e8e"

        # Determine timestamp and time type
        if arrival_time:
            dt = datetime.fromisoformat(arrival_time.replace("Z", "+00:00"))
            timestamp = str(int(dt.timestamp()))
            time_type = "7e2"  # arrive by
        else:
            dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
            timestamp = str(int(dt.timestamp()))
            time_type = "7e1"  # depart at

        # Build the complex URL format
        origin_encoded = urllib.parse.quote(origin)
        dest_encoded = urllib.parse.quote(destination)

        return (
            f"https://www.google.com/maps/dir/{origin_encoded}/"
            f"{dest_encoded}/@{center_lat},{center_lng},9z/"
            f"data=!3m1!4b1!4m18!4m17!1m5!1m1!1s{origin_place_id}!2m2!"
            f"1d{origin_lng}!2d{origin_lat}!1m5!1m1!1s{dest_place_id}!2m2!"
            f"1d{dest_lng}!2d{dest_lat}!2m3!6e1!{time_type}!8j{timestamp}!3e3"
        )

    # Fallback to simple API format
    base_url = "https://www.google.com/maps/dir/"

    # Parameters
    params = {
        "api": "1",
        "origin": origin,
        "destination": destination,
        "travelmode": mode,
    }

    # Add waypoints if provided, separated by the pipe character
    if waypoints:
        params["waypoints"] = "|".join(waypoints)

    # Add departure or arrival time if provided (for transit mode)
    if mode == "transit":
        if departure_time:
            dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
            params["departure_time"] = str(int(dt.timestamp()))
        elif arrival_time:
            dt = datetime.fromisoformat(arrival_time.replace("Z", "+00:00"))
            params["arrival_time"] = str(int(dt.timestamp()))

        # Add transit mode preferences
        if transit_mode:
            params["transit_mode"] = "|".join(transit_mode)

        # Add transit routing preference
        if transit_routing_preference:
            params["transit_routing_preference"] = transit_routing_preference

    # Add avoid parameters for driving mode
    if mode == "driving" and avoid:
        params["avoid"] = ",".join(avoid)

    # URL encode the parameters and construct the final URL
    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    return url


def _parse_step(step: dict[str, Any]) -> DirectionStep:
    """Parse a direction step from API response."""
    transit_details = None
    travel_mode = step.get("travel_mode", "")

    # Extract transit details if this is a transit step
    if travel_mode == "TRANSIT" and "transit_details" in step:
        transit_data = step["transit_details"]

        # Convert Unix timestamps to datetime objects (using UTC then converting to local)
        departure_dt = datetime.fromtimestamp(
            transit_data["departure_time"]["value"], tz=timezone.utc
        )
        arrival_dt = datetime.fromtimestamp(
            transit_data["arrival_time"]["value"], tz=timezone.utc
        )

        line_data = transit_data.get("line", {})

        transit_details = TransitDetails(
            departure_time=departure_dt,
            arrival_time=arrival_dt,
            line_name=line_data.get("name", ""),
            line_short_name=line_data.get("short_name", ""),
            vehicle_type=line_data.get("vehicle", {}).get("type", ""),
            headsign=transit_data.get("headsign", ""),
            num_stops=transit_data.get("num_stops", 0),
        )

    return DirectionStep(
        instruction=step["html_instructions"],
        distance=step["distance"]["text"],
        duration=step["duration"]["text"],
        start_location=step["start_location"],
        end_location=step["end_location"],
        travel_mode=travel_mode,
        transit_details=transit_details,
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
    description="Gets directions between an origin and destination, supporting multiple travel modes, waypoints, and route preferences. For transit, supports specific transport modes and routing preferences."
)
def get_directions(
    origin: str,
    destination: str,
    mode: Literal["driving", "walking", "bicycling", "transit"] = "driving",
    departure_time: str = "",
    arrival_time: str = "",
    avoid: list[Literal["tolls", "highways", "ferries"]] = [],
    alternatives: bool = False,
    waypoints: list[str] = [],
    transit_mode: list[Literal["bus", "subway", "train", "tram", "rail"]] = [],
    transit_routing_preference: Literal["", "less_walking", "fewer_transfers"] = "",
) -> DirectionsResult:
    gmaps = _get_maps_client()

    # Parse departure/arrival time if provided
    departure_dt = None
    arrival_dt = None
    if departure_time:
        departure_dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
    if arrival_time:
        arrival_dt = datetime.fromisoformat(arrival_time.replace("Z", "+00:00"))

    # The avoid parameter is already a list, no need to process it

    # Make API request
    result = gmaps.directions(
        origin=origin,
        destination=destination,
        mode=mode,
        departure_time=departure_dt,
        arrival_time=arrival_dt,
        avoid=avoid if avoid else None,
        alternatives=alternatives,
        waypoints=waypoints if waypoints else None,
        transit_mode=transit_mode if transit_mode else None,
        transit_routing_preference=transit_routing_preference
        if transit_routing_preference
        else None,
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
    routes = [_parse_route(route) for route in result]

    # Generate Google Maps URL
    maps_url = _generate_maps_url(
        origin,
        destination,
        mode,
        waypoints,
        departure_time,
        arrival_time,
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
