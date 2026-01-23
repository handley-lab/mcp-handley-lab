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

    def run(*cmd, **kw):
        return subprocess.run(cmd, capture_output=True, check=True, **kw)

    if not window:
        ids = run("xdotool", "search", "--name", "", text=True).stdout.splitlines()
        return {
            "windows": [
                {
                    "id": wid,
                    "name": run(
                        "xdotool", "getwindowname", wid, text=True
                    ).stdout.strip(),
                }
                for wid in ids[:50]
                if wid
            ]
        }

    wid = (
        window
        if window.startswith("0x")
        else run("xdotool", "search", "--name", window, text=True).stdout.splitlines()[
            0
        ]
    )
    return Image(data=run("maim", "-i", wid).stdout, format="png")
