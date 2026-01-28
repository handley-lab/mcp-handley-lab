"""PowerPoint MCP tool for reading and editing .pptx files.

Provides read(), edit(), and render() functions for PowerPoint presentations (.pptx).
Pure OOXML implementation.

Usage:
    from mcp_handley_lab.microsoft.powerpoint import read, edit

    # Read slide list
    result = read(file_path="deck.pptx", scope="slides")

    # Edit presentation (auto-creates file if it doesn't exist)
    result = edit(
        file_path="deck.pptx",
        ops='[{"op": "add_slide", "layout_name": "Title Slide"}]'
    )
"""

from mcp_handley_lab.microsoft.powerpoint.package import PowerPointPackage
from mcp_handley_lab.microsoft.powerpoint.shared import edit, read

__all__ = ["PowerPointPackage", "read", "edit"]
