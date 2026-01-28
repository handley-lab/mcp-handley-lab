"""Core PowerPoint functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

from typing import Any


def read(
    file_path: str,
    scope: str = "slides",
    slide_num: int = 0,
) -> dict[str, Any]:
    """Read from a PowerPoint presentation.

    Uses progressive disclosure with scopes:
    - meta: Presentation metadata (slide count, dimensions, properties)
    - slides: List all slides with summaries
    - shapes: Shapes on a slide (spatially sorted for reading order)
    - text: All text from a slide in reading order
    - notes: Speaker notes for a slide
    - layouts: List available slide layouts
    - images: List images (all slides, or specific slide if slide_num given)
    - tables: List tables with structure (requires slide_num)
    - properties: Document properties (title, author, custom properties)

    Args:
        file_path: Path to .pptx file.
        scope: What to read.
        slide_num: Slide number (1-based). Required for shapes/text/notes/tables;
            optional for images (0 = all slides).

    Returns:
        Dict with scope-specific data.
    """
    from mcp_handley_lab.microsoft.powerpoint.tool import read as _read

    return _read(file_path=file_path, scope=scope, slide_num=slide_num)


def edit(
    file_path: str,
    ops: str,
    mode: str = "atomic",
) -> dict[str, Any]:
    """Edit a PowerPoint presentation using batch operations. Creates a new file if file_path doesn't exist.

    Batch operations allow multiple edits in a single call with $prev chaining.
    Use read() first to discover slides, shapes, and layouts.

    Args:
        file_path: Path to .pptx file (created if it doesn't exist).
        ops: JSON array of operation objects, e.g.:
            [{"op": "add_shape", "slide_num": 1, "x": 1.0, "y": 1.0, "width": 4.0, "height": 1.0, "text": "Title"},
             {"op": "set_text_style", "shape_key": "$prev[0]", "bold": true}]
        mode: 'atomic' (all-or-nothing) or 'partial' (save successful ops).

    Returns:
        Dict with success status, counts, and per-operation results.
    """
    from mcp_handley_lab.microsoft.powerpoint.tool import edit as _edit

    return _edit(file_path=file_path, ops=ops, mode=mode)
