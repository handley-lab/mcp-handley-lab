"""Screenshot tool for MCP framework.

Usage:
    from mcp_handley_lab.screenshot import grab

    # List windows
    windows = grab()

    # Capture window by name
    image = grab(window="Firefox")

    # Capture full screen to file
    result = grab(window="screen", output_file="~/screenshot.png")
"""

from mcp_handley_lab.screenshot.shared import grab
from mcp_handley_lab.screenshot.tool import mcp

__all__ = ["grab", "mcp"]
