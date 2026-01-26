"""Core screenshot functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

import subprocess
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Image


def _parse_wmctrl() -> list[dict[str, Any]]:
    """Parse wmctrl -lx output into list of {id, desktop, class, name}."""
    result = subprocess.run(
        ["wmctrl", "-lx"], capture_output=True, text=True, check=True
    )
    windows = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 4)  # id, desktop, class, host, title
        if len(parts) >= 4:
            windows.append(
                {
                    "id": parts[0],
                    "desktop": int(parts[1]),
                    "class": parts[2].split(".")[0],  # instance.class -> class
                    "name": parts[4] if len(parts) > 4 else "",
                }
            )
    return windows


def grab(window: str = "", output_file: str = "") -> dict[str, Any] | Image:
    """Grab screenshots.

    Args:
        window: Window to capture. Options:
            - "" (empty): List all window names
            - "Figure 1": Capture window by name (fuzzy match)
            - "0x1234567": Capture window by ID
            - "screen": Capture full screen
        output_file: If provided, save to file instead of returning image.

    Returns:
        - If window is empty: dict with "windows" list
        - If output_file provided: dict with "saved" path and "size_bytes"
        - Otherwise: Image object with PNG data
    """

    def run(*cmd):
        return subprocess.run(cmd, capture_output=True, check=True)

    if not window:
        return {"windows": _parse_wmctrl()}

    # Capture: full screen or specific window
    if window == "screen":
        png = run("maim").stdout
    elif window.startswith("0x") or window.isdigit():
        png = run("maim", "-i", window).stdout
    else:
        # Find window by name match
        matches = [w for w in _parse_wmctrl() if window.lower() in w["name"].lower()]
        if not matches:
            raise ValueError(f"No window matching '{window}'")
        png = run("maim", "-i", matches[0]["id"]).stdout

    if output_file:
        path = Path(output_file).expanduser()
        path.write_bytes(png)
        return {"saved": str(path), "size_bytes": len(png)}

    return Image(data=png, format="png")
