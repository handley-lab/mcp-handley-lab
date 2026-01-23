import subprocess
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image

mcp = FastMCP("Screenshot Tool")


@mcp.tool()
def take(window: str = "", list_windows: bool = False):
    """
    Take screenshots of windows.

    - take(list_windows=True) - list all window names
    - take(window="Figure 1") - capture window by name, returns image
    - take(window="0x1234567") - capture window by ID
    """
    if list_windows:
        result = subprocess.run(
            ["xdotool", "search", "--name", ""],
            capture_output=True, text=True
        )
        window_ids = [w for w in result.stdout.strip().split("\n") if w]

        windows = []
        for wid in window_ids[:50]:  # Limit to 50
            name_result = subprocess.run(
                ["xdotool", "getwindowname", wid],
                capture_output=True, text=True
            )
            name = name_result.stdout.strip()
            if name:
                windows.append({"id": wid, "name": name})

        return {"windows": windows}

    if not window:
        return {"error": "Specify window name or use list_windows=True"}

    # Check if window is an ID (hex) or name
    if window.startswith("0x"):
        window_id = window
    else:
        result = subprocess.run(
            ["xdotool", "search", "--name", window],
            capture_output=True, text=True
        )
        window_ids = [w for w in result.stdout.strip().split("\n") if w]
        if not window_ids:
            return {"error": f"No window found matching '{window}'"}
        window_id = window_ids[0]

    # Capture window
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        temp_path = f.name

    subprocess.run(["import", "-window", window_id, temp_path], check=True)
    png_bytes = Path(temp_path).read_bytes()
    Path(temp_path).unlink()

    return [Image(data=png_bytes, format="png")]
