"""Visio MCP tool for reading and editing .vsdx files."""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("Visio Tool")

ReadScope = Literal[
    "meta",
    "pages",
    "shapes",
    "text",
    "connections",
    "shape_data",
    "shape_cells",
    "masters",
    "properties",
    "comments",
]


@mcp.tool()
def read(
    file_path: str = Field(description="Path to .vsdx file"),
    scope: ReadScope = Field(
        default="pages",
        description="What to read: meta, pages, shapes, text, connections, shape_data, shape_cells, masters, properties, comments",
    ),
    page_num: int = 0,
    shape_id: int = 0,
) -> dict:
    """Read from a Visio diagram (.vsdx).

    Progressive disclosure: start with 'pages' for overview, then drill into
    shapes, text, connections, or shape details per page.

    Args:
        file_path: Path to .vsdx file
        scope: What to read:
            - "meta": Page count, master count, document properties
            - "pages": Page list with name, size, shape count, background flag
            - "shapes": Shapes on page (ID, name, text, position, type, master)
            - "text": All text from page in spatial reading order
            - "connections": Connector relationships (from/to shape IDs and names)
            - "shape_data": Custom properties (Property section) for a shape
            - "shape_cells": All singleton cells for a shape (ShapeSheet dump)
            - "masters": Master shapes (stencils) with name and shape count
            - "properties": Document properties (title, author, etc.)
            - "comments": Comments with page/shape reference, author, text
        page_num: Required for shapes/text/connections/shape_data/shape_cells (1-based). Optional for comments.
        shape_id: Required for shape_data/shape_cells

    Returns:
        VisioReadResult with scope-specific data
    """
    from mcp_handley_lab.microsoft.visio.shared import read as _read

    return _read(file_path=file_path, scope=scope, page_num=page_num, shape_id=shape_id)


@mcp.tool()
def edit(
    file_path: str = Field(description="Path to .vsdx file"),
    ops: str = Field(
        description='JSON array of operation objects. Each object has "op" (operation name) '
        "plus operation-specific fields. Use $prev[N] to reference element_id from operation N."
    ),
) -> dict[str, Any]:
    """Edit a Visio diagram using batch operations. Creates a new file if file_path doesn't exist.

    Fail-fast semantics: raises on first operation error, file unchanged on any failure.
    Use read() first to discover pages, shapes, and structure.

    Args:
        file_path: Path to .vsdx file
        ops: JSON array of operation objects, e.g.:
            [{"op": "set_text", "page_num": 1, "shape_id": 1, "text": "Hello"},
             {"op": "set_cell", "shape_key": "$prev[0]", "cell_name": "Width", "value": "3.0"}]

    Available operations:
        Shape operations:
        - add_shape: Add shape from master {page_num, master_name, x, y, width?, height?, text?}
        - add_connector: Add connector between shapes {page_num, from_shape_id, to_shape_id, text?}
        - set_text: Set shape text {page_num, shape_id, text}
        - set_cell: Set ShapeSheet cell {page_num, shape_id, cell_name, value, formula?, unit?}
        - set_shape_data: Set Property row value {page_num, shape_id, row_name, value}
        - delete_shape: Delete shape {page_num, shape_id}
        - set_z_order: Change z-order {page_num, shape_id, action} (action: bring_to_front, send_to_back, bring_forward, send_backward)
        - group_shapes: Group shapes {page_num, shape_ids} (V1: no rotation/nested groups)
        - ungroup: Ungroup a group {page_num, group_id} (V1: no rotation/nested groups)

        Page operations:
        - add_page: Add blank page {name?}
        - delete_page: Delete page {page_num}
        - rename_page: Rename page {page_num, name}

        Document properties:
        - set_property: Set core property {property_name, property_value}
        - set_custom_property: Set custom property {property_name, property_value, property_type?}
        - delete_custom_property: Delete custom property {property_name}

    $prev chaining:
        Reference results of previous operations using $prev[N] where N is the
        operation index (0-based). Only works for shape_key fields.
        set_text/set_cell/set_shape_data return shape_key as element_id ("page_num:shape_id").

    Returns:
        VisioEditResult with success status, counts, and per-operation results
    """
    from mcp_handley_lab.microsoft.visio.shared import edit as _edit

    return _edit(file_path=file_path, ops=ops)


@mcp.tool()
def render(
    file_path: str,
    pages: list[int] = Field(
        default_factory=list,
        description="Page numbers to render (1-based). Required for PNG (max 5 unique). Ignored for PDF.",
    ),
    dpi: int = 150,
    output: str = "png",
):
    """Render Visio pages for visual inspection or sharing.

    Use read to get diagram structure, render to see it visually.
    output='png' (default) returns labeled images for Claude to see.
    output='pdf' saves PDF to disk alongside the source file.
    Requires libreoffice (and pdftoppm for PNG).

    Args:
        file_path: Path to .vsdx file
        pages: Page numbers to render (1-based). Required for PNG (max 5 unique). Ignored for PDF.
        dpi: Resolution for PNG (default 150, max 300)
        output: Output format: 'png' (images) or 'pdf' (full document)

    Returns:
        List of TextContent and Image objects
    """
    import base64

    from mcp.types import ImageContent, TextContent

    from mcp_handley_lab.microsoft.visio.shared import render as _render

    result = _render(
        file_path=file_path,
        pages=pages or None,
        dpi=dpi,
        output=output,
    )

    if result["format"] == "pdf":
        return [
            TextContent(
                type="text",
                text=f"PDF saved to {result['pdf_path']} ({result['size']:,} bytes)",
            ),
        ]

    # PNG output
    contents = []
    for img in result["images"]:
        contents.append(TextContent(type="text", text=f"Page {img['page_num']}:"))
        contents.append(
            ImageContent(
                type="image",
                data=base64.b64encode(img["png_bytes"]).decode(),
                mimeType="image/png",
            )
        )
    return contents
