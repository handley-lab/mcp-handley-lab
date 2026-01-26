"""Google Maps MCP tool for directions and routing.

Usage:
    from mcp_handley_lab.google_maps import get_directions, server_info

    # Get directions
    result = get_directions(
        origin="Cambridge, UK",
        destination="London, UK",
        mode="transit",
        departure_time="tomorrow 9am",
    )

    # Get server info
    info = server_info()
"""

from mcp_handley_lab.google_maps.shared import get_directions, server_info

__all__ = ["get_directions", "server_info"]
