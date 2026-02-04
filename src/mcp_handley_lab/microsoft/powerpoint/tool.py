"""PowerPoint MCP tool for reading and editing .pptx files."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.microsoft.powerpoint.ops.render import (
    render_to_images,
    render_to_pdf,
)
from mcp_handley_lab.microsoft.powerpoint.shared import ReadScope

mcp = FastMCP("PowerPoint Tool")


@mcp.tool()
def read(
    file_path: str,
    scope: ReadScope = "slides",
    slide_num: int = 0,
) -> dict:
    """Read from a PowerPoint presentation.

    Args:
        file_path: Path to .pptx file
        scope: What to read:
            - "meta": Presentation metadata (slide count, dimensions, properties)
            - "slides": List all slides with summaries
            - "shapes": Shapes on a slide (spatially sorted for reading order)
            - "text": All text from a slide in reading order
            - "notes": Speaker notes for a slide
            - "layouts": List available slide layouts
            - "images": List images (all slides, or specific slide if slide_num given)
            - "tables": List tables with structure (requires slide_num)
            - "charts": List charts on a slide (requires slide_num)
            - "properties": Document properties (title, author, custom properties)
        slide_num: Slide number (1-based). Required for shapes/text/notes/tables; optional for images (0 = all slides)

    Returns:
        PowerPointReadResult with scope-specific data
    """
    from mcp_handley_lab.microsoft.powerpoint.shared import read as _read

    return _read(file_path=file_path, scope=scope, slide_num=slide_num)


@mcp.tool()
def edit(
    file_path: str = Field(description="Path to .pptx file"),
    ops: str = Field(
        description='JSON array of operation objects. Each object has "op" (operation name) '
        "plus operation-specific fields. Use $prev[N] to reference element_id from operation N."
    ),
) -> dict[str, Any]:
    """Edit a PowerPoint presentation using batch operations. Creates a new file if file_path doesn't exist.

    Fail-fast semantics: raises on first operation error, file unchanged on any failure.
    Use read() first to discover slides, shapes, and layouts.

    Args:
        file_path: Path to .pptx file
        ops: JSON array of operation objects, e.g.:
            [{"op": "add_shape", "slide_num": 1, "x": 1.0, "y": 1.0, "width": 4.0, "height": 1.0, "text": "Title"},
             {"op": "set_text_style", "shape_key": "$prev[0]", "bold": true}]

    Available operations:
        - add_slide: Add slide {layout_name}
        - delete_slide: Delete slide {slide_num}
        - reorder_slide: Move slide {slide_num, new_position}
        - duplicate_slide: Copy slide {slide_num, new_position}
        - set_dimensions: Set dimensions {preset} or {width, height}
        - set_placeholder: Set placeholder {slide_num, placeholder_type/placeholder_idx, text}
        - set_notes: Set speaker notes {slide_num, text}
        - add_shape: Add text box {slide_num, x, y, width, height, text}
        - edit_shape: Edit shape text {shape_key, text, bullet_style}
        - delete_shape: Delete shape {shape_key}
        - transform_shape: Move/resize {shape_key, x, y, width, height}
        - add_image: Add image {slide_num, image_path, x, y, width, height}
        - delete_image: Delete image {shape_key}
        - add_table: Add table {slide_num, rows, cols, x, y, width, height}
        - set_table_cell: Set cell {shape_key, row, col, text}
        - add_table_row: Add row {shape_key, row}
        - add_table_column: Add column {shape_key, col}
        - delete_table_row: Delete row {shape_key, row}
        - delete_table_column: Delete column {shape_key, col}
        - set_shape_fill: Fill color {shape_key, color}
        - set_shape_line: Border {shape_key, color, line_width}
        - set_text_style: Text style {shape_key, size, bold, italic, color, alignment, font}
        - set_slide_background: Background {slide_num, color}
        - add_hyperlink: Hyperlink {shape_key, url/target_slide, tooltip}
        - hide_slide: Hide/show {slide_num, hidden}
        - set_property: Core property {property_name, property_value}
        - set_custom_property: Custom property {property_name, property_value, property_type}
        - delete_custom_property: Delete property {property_name}
        - add_chart: Add chart {slide_num, chart_type, data, x, y, width, height, title}
        - delete_chart: Delete chart {slide_num, shape_key}
        - update_chart_data: Update chart {slide_num, shape_key, data}
        - find_replace: Find/replace text {search, replace, slide_num?, match_case?}
        - group_shapes: Group shapes {slide_num, shape_keys} (shape_keys is list of "slide:id" strings)
        - ungroup: Ungroup a group {shape_key}

    $prev chaining:
        Reference results of previous operations using $prev[N] where N is the
        operation index (0-based). Only works for shape_key (NOT slide_num).

    Returns:
        PowerPointEditResult with success status, counts, and per-operation results
    """
    from mcp_handley_lab.microsoft.powerpoint.shared import edit as _edit

    return _edit(file_path=file_path, ops=ops)


# =============================================================================
# Render Tool
# =============================================================================


@mcp.tool()
def render(
    file_path: str,
    pages: list[int] = Field(
        default_factory=list,
        description="Slide numbers to render (1-based). Required for PNG (max 5). Ignored for PDF.",
    ),
    dpi: int = 150,
    output: str = "png",
):
    """Render PowerPoint slides for visual inspection or sharing.

    Use read to get presentation structure, render to see it visually.
    output='png' (default) returns labeled images for Claude to see.
    output='pdf' returns PDF bytes for sharing.
    Requires libreoffice (and pdftoppm for PNG).

    Args:
        file_path: Path to .pptx file
        pages: Slide numbers to render (1-based). Required for PNG output. Max 5.
        dpi: Resolution for PNG (default 150, max 300)
        output: Output format: 'png' (images) or 'pdf' (full document)

    Returns:
        List of TextContent and Image objects
    """
    import base64

    from mcp.types import ImageContent, TextContent

    if output == "pdf":
        pdf_bytes = render_to_pdf(file_path)
        return [
            TextContent(type="text", text=f"PDF ({len(pdf_bytes):,} bytes)"),
            ImageContent(
                type="image",
                data=base64.b64encode(pdf_bytes).decode(),
                mimeType="application/pdf",
            ),
        ]

    # PNG output (default)
    if not pages:
        raise ValueError("pages is required for PNG output")
    if dpi > 300:
        raise ValueError("dpi max is 300")

    result = []
    for slide_num, png_bytes in render_to_images(file_path, pages, dpi):
        result.append(TextContent(type="text", text=f"Slide {slide_num}:"))
        result.append(
            ImageContent(
                type="image",
                data=base64.b64encode(png_bytes).decode(),
                mimeType="image/png",
            )
        )
    return result
