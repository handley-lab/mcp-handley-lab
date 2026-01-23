import subprocess

from mcp.server.fastmcp import FastMCP, Image

mcp = FastMCP("Screenshot Tool")


@mcp.tool()
def grab(window: str = ""):
    """
    Grab screenshots.

    - grab() - list all window names
    - grab(window="Figure 1") - capture window by name, returns image
    - grab(window="0x1234567") - capture window by ID
    """
    if not window:
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

    # Capture window using maim (outputs PNG to stdout by default)
    result = subprocess.run(
        ["maim", "-i", window_id],
        capture_output=True
    )
    if result.returncode != 0:
        return {"error": f"Capture failed: {result.stderr.decode()}"}

    return Image(data=result.stdout, format="png")
