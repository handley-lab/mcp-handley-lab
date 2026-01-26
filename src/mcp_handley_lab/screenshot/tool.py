from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Screenshot Tool")


@mcp.tool()
def grab(window: str = "", output_file: str = ""):
    """Grab screenshots.

    - grab() - list all window names
    - grab(window="Figure 1") - capture window by name, returns image
    - grab(window="0x1234567") - capture window by ID
    - grab(window="screen") - capture full screen
    - Add output_file to save to file instead of returning image
    """
    from mcp_handley_lab.screenshot.shared import grab as _grab

    return _grab(window=window, output_file=output_file)
