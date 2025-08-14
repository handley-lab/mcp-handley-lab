"""Google Maps tool for directions and routing via MCP."""

import zoneinfo
from datetime import datetime
from typing import Any, Literal

import dateparser
import googlemaps
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.shared.models import ServerInfo

# Default timezone for time parsing
DEFAULT_TIMEZONE = "Europe/London"


def _parse_flexible_datetime(
    time_str: str, default_tz: str = DEFAULT_TIMEZONE
) -> datetime:
    """
    Parse flexible datetime string into timezone-aware datetime object.

    Relies on dateparser to handle natural language, ISO 8601, and relative times.
    Naive times are interpreted in the default timezone.
    """
    if not time_str:
        raise ValueError("Time string cannot be empty")

    settings = {
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TIMEZONE": default_tz,
    }

    parsed_dt = dateparser.parse(time_str, settings=settings)
    if not parsed_dt:
        raise ValueError(f"Could not parse datetime string: '{time_str}'")

    # Ensure we return a standard datetime object for library interop
    if isinstance(parsed_dt, datetime):
        return parsed_dt
    return datetime.fromisoformat(parsed_dt.isoformat())


class TransitDetails(BaseModel):
    """Transit-specific information for a step."""

    departure_time: datetime = Field(
        ...,
        description="The scheduled departure time for this transit step in UK local time (BST/GMT with proper offset).",
    )
    arrival_time: datetime = Field(
        ...,
        description="The scheduled arrival time for this transit step in UK local time (BST/GMT with proper offset).",
    )
    line_name: str = Field(
        ...,
        description="The full name of the transit line (e.g., 'Red Line', 'Route 101').",
    )
    line_short_name: str = Field(
        default="", description="The short name or number of the transit line."
    )
    vehicle_type: str = Field(
        ..., description="The type of transit vehicle (e.g., 'BUS', 'SUBWAY', 'TRAIN')."
    )
    headsign: str = Field(
        default="", description="The destination sign displayed on the transit vehicle."
    )
    num_stops: int = Field(
        ..., description="The number of stops between boarding and alighting."
    )


class DirectionStep(BaseModel):
    """A single step in a route."""

    instruction: str = Field(
        ..., description="Human-readable navigation instruction for this step."
    )
    distance: str = Field(
        ..., description="The distance for this step (e.g., '0.5 km', '500 ft')."
    )
    duration: str = Field(
        ..., description="The estimated time for this step (e.g., '5 mins', '2 hours')."
    )
    start_location: dict[str, float] = Field(
        ...,
        description="The latitude and longitude coordinates where this step begins.",
    )
    end_location: dict[str, float] = Field(
        ..., description="The latitude and longitude coordinates where this step ends."
    )
    travel_mode: str = Field(
        default="",
        description="The mode of transport for this step (e.g., 'WALKING', 'DRIVING', 'TRANSIT').",
    )
    transit_details: TransitDetails | None = Field(
        default=None,
        description="Additional details if this step involves public transit.",
    )


class DirectionLeg(BaseModel):
    """A leg of a route (origin to destination or waypoint)."""

    distance: str = Field(
        ..., description="The total distance for this leg of the journey."
    )
    duration: str = Field(
        ..., description="The estimated total time for this leg of the journey."
    )
    start_address: str = Field(
        ..., description="The human-readable address where this leg begins."
    )
    end_address: str = Field(
        ..., description="The human-readable address where this leg ends."
    )
    steps: list[DirectionStep] = Field(
        ..., description="The individual navigation steps that make up this leg."
    )


class DirectionRoute(BaseModel):
    """A complete route with all legs and steps."""

    summary: str = Field(
        ...,
        description="A short textual description of the route (e.g., 'via I-95 N').",
    )
    legs: list[DirectionLeg] = Field(
        ..., description="The individual legs that make up this complete route."
    )
    distance: str = Field(..., description="The total distance for the entire route.")
    duration: str = Field(
        ..., description="The estimated total time for the entire route."
    )
    polyline: str = Field(
        ..., description="An encoded polyline representation of the route path."
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Any warnings about the route (e.g., tolls, traffic).",
    )


class DirectionsResult(BaseModel):
    """Result of a directions request."""

    routes: list[DirectionRoute] = Field(
        ..., description="A list of possible routes from origin to destination."
    )
    status: str = Field(
        ..., description="The status of the API request (e.g., 'OK', 'ZERO_RESULTS')."
    )
    origin: str = Field(
        ..., description="The address or coordinates of the starting point."
    )
    destination: str = Field(
        ..., description="The address or coordinates of the ending point."
    )
    mode: str = Field(
        ...,
        description="The travel mode used for the directions (e.g., 'driving', 'transit').",
    )
    departure_time: str = Field(
        default="",
        description="The requested departure time as an ISO 8601 string, if provided.",
    )
    maps_url: str = Field(
        default="", description="A direct URL to Google Maps with the requested route."
    )


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


def _parse_step(step: dict[str, Any], user_timezone: str) -> DirectionStep:
    """Parse a direction step from API response."""
    transit_details = None
    travel_mode = step.get("travel_mode", "")

    # Extract transit details if this is a transit step
    if travel_mode == "TRANSIT" and "transit_details" in step:
        transit_data = step["transit_details"]

        # Convert Unix timestamps to user's local time for LLM-friendly display
        local_tz = zoneinfo.ZoneInfo(user_timezone)
        departure_dt = datetime.fromtimestamp(
            transit_data["departure_time"]["value"], tz=local_tz
        )
        arrival_dt = datetime.fromtimestamp(
            transit_data["arrival_time"]["value"], tz=local_tz
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


def _parse_leg(leg: dict[str, Any], user_timezone: str) -> DirectionLeg:
    """Parse a direction leg from API response."""
    return DirectionLeg(
        distance=leg["distance"]["text"],
        duration=leg["duration"]["text"],
        start_address=leg["start_address"],
        end_address=leg["end_address"],
        steps=[_parse_step(step, user_timezone) for step in leg["steps"]],
    )


def _parse_route(route: dict[str, Any], user_timezone: str) -> DirectionRoute:
    """Parse a route from API response."""
    legs = [_parse_leg(leg, user_timezone) for leg in route["legs"]]

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
    origin: str = Field(
        ...,
        description="The starting address, place name, or coordinates (e.g., '1600 Amphitheatre Parkway, Mountain View, CA').",
    ),
    destination: str = Field(
        ...,
        description="The ending address, place name, or coordinates (e.g., 'San Francisco, CA').",
    ),
    mode: Literal["driving", "walking", "bicycling", "transit"] = Field(
        "driving", description="The mode of transport to use for the directions."
    ),
    departure_time: str = Field(
        "",
        description="The desired departure time. Supports natural language ('17:00', '5pm', 'tomorrow 5pm'), relative times ('in 2 hours'), or ISO 8601 formats. Times are interpreted as UK local time unless explicitly specified. Cannot be used with arrival_time.",
    ),
    arrival_time: str = Field(
        "",
        description="The desired arrival time. Supports natural language ('17:00', '5pm', 'tomorrow 5pm'), relative times ('in 2 hours'), or ISO 8601 formats. Times are interpreted as UK local time unless explicitly specified. Cannot be used with departure_time.",
    ),
    user_timezone: str = Field(
        DEFAULT_TIMEZONE,
        description="The timezone to use for interpreting departure/arrival times when not explicitly specified (e.g., 'Europe/London', 'America/New_York'). Defaults to UK timezone.",
    ),
    avoid: list[Literal["tolls", "highways", "ferries"]] = Field(
        default_factory=list,
        description="A list of route features to avoid (e.g., 'tolls', 'highways'). Only for 'driving' mode.",
    ),
    alternatives: bool = Field(
        False,
        description="If True, requests that alternative routes be provided in the response.",
    ),
    waypoints: list[str] = Field(
        default_factory=list,
        description="A list of addresses or coordinates to route through between the origin and destination.",
    ),
    transit_mode: list[Literal["bus", "subway", "train", "tram", "rail"]] = Field(
        default_factory=list,
        description="Preferred modes of public transit. Only for 'transit' mode.",
    ),
    transit_routing_preference: Literal["", "less_walking", "fewer_transfers"] = Field(
        "",
        description="Specifies preferences for transit routes, such as fewer transfers or less walking. Only for 'transit' mode.",
    ),
) -> DirectionsResult:
    gmaps = _get_maps_client()

    # Parse departure/arrival time with flexible parsing
    departure_dt = None
    arrival_dt = None
    if departure_time:
        departure_dt = _parse_flexible_datetime(departure_time, user_timezone)
    if arrival_time:
        arrival_dt = _parse_flexible_datetime(arrival_time, user_timezone)

    # The avoid parameter is already a list, no need to process it

    # Make API request
    result = gmaps.directions(
        origin=origin,
        destination=destination,
        mode=mode,
        departure_time=departure_dt,
        arrival_time=arrival_dt,
        avoid=avoid,
        alternatives=alternatives,
        waypoints=waypoints,
        transit_mode=transit_mode,
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
