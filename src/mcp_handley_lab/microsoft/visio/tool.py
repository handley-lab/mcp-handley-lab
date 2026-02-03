"""Visio MCP tool for reading and editing .vsdx files."""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.microsoft.common.batch import (
    convert_custom_property_value,
    run_batch_edit,
)
from mcp_handley_lab.microsoft.common.properties import get_core_properties
from mcp_handley_lab.microsoft.visio.models import (
    DocumentProperties,
    VisioEditResult,
    VisioMeta,
    VisioOpResult,
    VisioReadResult,
)
from mcp_handley_lab.microsoft.visio.ops.comments import list_comments
from mcp_handley_lab.microsoft.visio.ops.connections import list_connections
from mcp_handley_lab.microsoft.visio.ops.edit import (
    add_page,
    delete_page,
    delete_shape,
    rename_page,
    set_shape_cell,
    set_shape_data,
    set_shape_text,
)
from mcp_handley_lab.microsoft.visio.ops.masters import (
    list_masters,
)
from mcp_handley_lab.microsoft.visio.ops.pages import list_pages
from mcp_handley_lab.microsoft.visio.ops.properties import (
    delete_custom_property,
    set_custom_property,
    set_property,
)
from mcp_handley_lab.microsoft.visio.ops.shapes import (
    add_connector,
    add_shape_from_master,
    get_shape_cells,
    get_shape_data,
    get_text_in_reading_order,
    group_shapes,
    list_shapes,
    set_z_order,
    ungroup,
)
from mcp_handley_lab.microsoft.visio.package import VisioPackage

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

_PREV_FIELDS = {"shape_key"}

_TEXT_FIELDS: dict[str, set[str]] = {
    "set_text": {"text"},
}


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
    pkg = VisioPackage.open(file_path)

    if scope == "meta":
        return _read_meta(pkg).model_dump(exclude_none=True)

    elif scope == "pages":
        return _read_pages(pkg).model_dump(exclude_none=True)

    elif scope == "shapes":
        if not page_num:
            raise ValueError("page_num required for shapes scope")
        return _read_shapes(pkg, page_num).model_dump(exclude_none=True)

    elif scope == "text":
        if not page_num:
            raise ValueError("page_num required for text scope")
        return _read_text(pkg, page_num).model_dump(exclude_none=True)

    elif scope == "connections":
        if not page_num:
            raise ValueError("page_num required for connections scope")
        return _read_connections(pkg, page_num).model_dump(exclude_none=True)

    elif scope == "shape_data":
        if not page_num:
            raise ValueError("page_num required for shape_data scope")
        if not shape_id:
            raise ValueError("shape_id required for shape_data scope")
        return _read_shape_data(pkg, page_num, shape_id).model_dump(exclude_none=True)

    elif scope == "shape_cells":
        if not page_num:
            raise ValueError("page_num required for shape_cells scope")
        if not shape_id:
            raise ValueError("shape_id required for shape_cells scope")
        return _read_shape_cells(pkg, page_num, shape_id).model_dump(exclude_none=True)

    elif scope == "masters":
        return _read_masters(pkg).model_dump(exclude_none=True)

    elif scope == "properties":
        return _read_properties(pkg).model_dump(exclude_none=True)

    elif scope == "comments":
        return _read_comments(pkg, page_num or None).model_dump(exclude_none=True)

    else:
        raise ValueError(f"Unknown scope: {scope}")


# =============================================================================
# Read Helpers
# =============================================================================


def _get_document_properties(pkg: VisioPackage) -> DocumentProperties:
    """Get document properties from core.xml."""
    core = get_core_properties(pkg)
    return DocumentProperties(
        title=core["title"],
        author=core["author"],
        subject=core["subject"],
        keywords=core["keywords"],
        category=core["category"],
        description=core.get("comments", ""),
        created=core["created"],
        modified=core["modified"],
        last_modified_by=core["last_modified_by"],
    )


def _read_meta(pkg: VisioPackage) -> VisioReadResult:
    pages = list_pages(pkg)
    masters = list_masters(pkg)
    return VisioReadResult(
        scope="meta",
        meta=VisioMeta(
            page_count=len(pages),
            master_count=len(masters),
            properties=_get_document_properties(pkg),
        ),
    )


def _read_pages(pkg: VisioPackage) -> VisioReadResult:
    return VisioReadResult(scope="pages", pages=list_pages(pkg))


def _read_shapes(pkg: VisioPackage, page_num: int) -> VisioReadResult:
    return VisioReadResult(scope="shapes", shapes=list_shapes(pkg, page_num))


def _read_text(pkg: VisioPackage, page_num: int) -> VisioReadResult:
    return VisioReadResult(scope="text", text=get_text_in_reading_order(pkg, page_num))


def _read_connections(pkg: VisioPackage, page_num: int) -> VisioReadResult:
    return VisioReadResult(
        scope="connections", connections=list_connections(pkg, page_num)
    )


def _read_shape_data(
    pkg: VisioPackage, page_num: int, shape_id: int
) -> VisioReadResult:
    return VisioReadResult(
        scope="shape_data", shape_data=get_shape_data(pkg, page_num, shape_id)
    )


def _read_shape_cells(
    pkg: VisioPackage, page_num: int, shape_id: int
) -> VisioReadResult:
    return VisioReadResult(
        scope="shape_cells", shape_cells=get_shape_cells(pkg, page_num, shape_id)
    )


def _read_masters(pkg: VisioPackage) -> VisioReadResult:
    return VisioReadResult(scope="masters", masters=list_masters(pkg))


def _read_properties(pkg: VisioPackage) -> VisioReadResult:
    return VisioReadResult(scope="properties", properties=_get_document_properties(pkg))


def _read_comments(pkg: VisioPackage, page_num: int | None) -> VisioReadResult:
    """Read comments from the document."""
    comments = list_comments(pkg, page_num)
    return VisioReadResult(scope="comments", comments=comments)


# =============================================================================
# Edit Tool
# =============================================================================


@mcp.tool()
def edit(
    file_path: str = Field(description="Path to .vsdx file"),
    ops: str = Field(
        description='JSON array of operation objects. Each object has "op" (operation name) '
        "plus operation-specific fields. Use $prev[N] to reference element_id from operation N."
    ),
    mode: str = Field(
        default="atomic",
        description="'atomic' (save only if all succeed) or 'partial' (save if any succeed)",
    ),
) -> dict[str, Any]:
    """Edit a Visio diagram using batch operations. Creates a new file if file_path doesn't exist.

    Batch operations allow multiple edits in a single call with $prev chaining.
    Use read() first to discover pages, shapes, and structure.

    Args:
        file_path: Path to .vsdx file
        ops: JSON array of operation objects, e.g.:
            [{"op": "set_text", "page_num": 1, "shape_id": 1, "text": "Hello"},
             {"op": "set_cell", "shape_key": "$prev[0]", "cell_name": "Width", "value": "3.0"}]
        mode: 'atomic' (all-or-nothing) or 'partial' (save successful ops)

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
    return run_batch_edit(
        file_path=file_path,
        ops=ops,
        mode=mode,
        open_pkg=VisioPackage.open,
        new_pkg=VisioPackage.new,
        apply_op=_apply_op,
        make_op_result=VisioOpResult,
        make_edit_result=VisioEditResult,
        prev_fields=_PREV_FIELDS,
        text_fields=_TEXT_FIELDS,
    )


# =============================================================================
# Operation Dispatcher
# =============================================================================


def _apply_op(pkg: VisioPackage, op: str, params: dict[str, Any]) -> dict[str, Any]:
    """Apply a single operation. Returns dict with 'message' and optionally 'element_id'."""
    if op == "set_text":
        return _op_set_text(pkg, params)
    elif op == "set_cell":
        return _op_set_cell(pkg, params)
    elif op == "set_shape_data":
        return _op_set_shape_data(pkg, params)
    elif op == "delete_shape":
        return _op_delete_shape(pkg, params)
    elif op == "add_page":
        return _op_add_page(pkg, params)
    elif op == "delete_page":
        return _op_delete_page(pkg, params)
    elif op == "rename_page":
        return _op_rename_page(pkg, params)
    elif op == "set_property":
        return _op_set_property(pkg, params)
    elif op == "set_custom_property":
        return _op_set_custom_property(pkg, params)
    elif op == "delete_custom_property":
        return _op_delete_custom_property(pkg, params)
    elif op == "set_z_order":
        return _op_set_z_order(pkg, params)
    elif op == "add_shape":
        return _op_add_shape(pkg, params)
    elif op == "add_connector":
        return _op_add_connector(pkg, params)
    elif op == "group_shapes":
        return _op_group_shapes(pkg, params)
    elif op == "ungroup":
        return _op_ungroup(pkg, params)
    else:
        raise ValueError(f"Unknown operation: {op}")


# =============================================================================
# Operation Handlers
# =============================================================================


def _resolve_shape_params(params: dict[str, Any]) -> tuple[int, int]:
    """Extract page_num and shape_id from params, supporting shape_key."""
    if "shape_key" in params:
        parts = params["shape_key"].split(":")
        return int(parts[0]), int(parts[1])
    page_num = params.get("page_num")
    shape_id = params.get("shape_id")
    if not page_num:
        raise ValueError("page_num required")
    if not shape_id:
        raise ValueError("shape_id required")
    return int(page_num), int(shape_id)


def _op_set_text(pkg: VisioPackage, params: dict[str, Any]) -> dict[str, Any]:
    page_num, shape_id = _resolve_shape_params(params)
    text = params.get("text")
    if text is None:
        raise ValueError("text required for set_text")
    shape_key = set_shape_text(pkg, page_num, shape_id, text)
    return {"message": f"Set text on shape {shape_key}", "element_id": shape_key}


def _op_set_cell(pkg: VisioPackage, params: dict[str, Any]) -> dict[str, Any]:
    page_num, shape_id = _resolve_shape_params(params)
    cell_name = params.get("cell_name")
    value = params.get("value")
    if cell_name is None:
        raise ValueError("cell_name required for set_cell")
    if value is None:
        raise ValueError("value required for set_cell")
    shape_key = set_shape_cell(
        pkg,
        page_num,
        shape_id,
        cell_name,
        str(value),
        formula=params.get("formula"),
        unit=params.get("unit"),
    )
    return {
        "message": f"Set cell {cell_name} on shape {shape_key}",
        "element_id": shape_key,
    }


def _op_set_shape_data(pkg: VisioPackage, params: dict[str, Any]) -> dict[str, Any]:
    page_num, shape_id = _resolve_shape_params(params)
    row_name = params.get("row_name")
    value = params.get("value")
    if row_name is None:
        raise ValueError("row_name required for set_shape_data")
    if value is None:
        raise ValueError("value required for set_shape_data")
    shape_key = set_shape_data(pkg, page_num, shape_id, row_name, str(value))
    return {
        "message": f"Set shape data {row_name} on {shape_key}",
        "element_id": shape_key,
    }


def _op_delete_shape(pkg: VisioPackage, params: dict[str, Any]) -> dict[str, Any]:
    page_num, shape_id = _resolve_shape_params(params)
    delete_shape(pkg, page_num, shape_id)
    return {
        "message": f"Deleted shape {shape_id} from page {page_num}",
        "element_id": "",
    }


def _op_add_page(pkg: VisioPackage, params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    new_num = add_page(pkg, name)
    return {"message": f"Added page {new_num}", "element_id": ""}


def _op_delete_page(pkg: VisioPackage, params: dict[str, Any]) -> dict[str, Any]:
    page_num = params.get("page_num")
    if not page_num:
        raise ValueError("page_num required for delete_page")
    delete_page(pkg, int(page_num))
    return {"message": f"Deleted page {page_num}", "element_id": ""}


def _op_rename_page(pkg: VisioPackage, params: dict[str, Any]) -> dict[str, Any]:
    page_num = params.get("page_num")
    name = params.get("name")
    if not page_num:
        raise ValueError("page_num required for rename_page")
    if name is None:
        raise ValueError("name required for rename_page")
    rename_page(pkg, int(page_num), name)
    return {"message": f"Renamed page {page_num} to '{name}'", "element_id": ""}


def _op_set_property(pkg: VisioPackage, params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("property_name")
    value = params.get("property_value")
    if name is None:
        raise ValueError("property_name required for set_property")
    if value is None:
        raise ValueError("property_value required for set_property")
    set_property(pkg, name, str(value))
    return {"message": f"Set core property '{name}'", "element_id": ""}


def _op_set_custom_property(
    pkg: VisioPackage, params: dict[str, Any]
) -> dict[str, Any]:
    name = params.get("property_name")
    value = params.get("property_value")
    prop_type = params.get("property_type", "string")
    if name is None:
        raise ValueError("property_name required for set_custom_property")
    if value is None:
        raise ValueError("property_value required for set_custom_property")

    actual_value, prop_type = convert_custom_property_value(value, prop_type)
    set_custom_property(pkg, name, actual_value, prop_type)
    return {"message": f"Set custom property '{name}'", "element_id": ""}


def _op_delete_custom_property(
    pkg: VisioPackage, params: dict[str, Any]
) -> dict[str, Any]:
    name = params.get("property_name")
    if name is None:
        raise ValueError("property_name required for delete_custom_property")
    deleted = delete_custom_property(pkg, name)
    if deleted:
        return {"message": f"Deleted custom property '{name}'", "element_id": ""}
    raise ValueError(f"Custom property '{name}' not found")


def _op_set_z_order(pkg: VisioPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Change z-order (stacking order) of a shape."""
    page_num, shape_id = _resolve_shape_params(params)
    action = params.get("action")
    if action is None:
        raise ValueError("action required for set_z_order")
    set_z_order(pkg, page_num, shape_id, action)
    shape_key = f"{page_num}:{shape_id}"
    return {
        "message": f"Set z-order of {shape_key}: {action}",
        "element_id": shape_key,
    }


def _op_add_shape(pkg: VisioPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add a shape by dropping a master from the document stencil."""
    page_num = params.get("page_num")
    master_name = params.get("master_name")
    x = params.get("x")
    y = params.get("y")

    if not page_num:
        raise ValueError("page_num required for add_shape")
    if not master_name:
        raise ValueError("master_name required for add_shape")
    if x is None:
        raise ValueError("x required for add_shape")
    if y is None:
        raise ValueError("y required for add_shape")

    width = params.get("width")
    height = params.get("height")
    text = params.get("text")

    new_id = add_shape_from_master(
        pkg,
        int(page_num),
        master_name,
        float(x),
        float(y),
        width=float(width) if width is not None else None,
        height=float(height) if height is not None else None,
        text=text,
    )
    shape_key = f"{page_num}:{new_id}"
    return {
        "message": f"Added shape '{master_name}' with ID {new_id}",
        "element_id": shape_key,
    }


def _op_add_connector(pkg: VisioPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add a connector between two shapes."""
    page_num = params.get("page_num")
    from_shape_id = params.get("from_shape_id")
    to_shape_id = params.get("to_shape_id")

    if not page_num:
        raise ValueError("page_num required for add_connector")
    if from_shape_id is None:
        raise ValueError("from_shape_id required for add_connector")
    if to_shape_id is None:
        raise ValueError("to_shape_id required for add_connector")

    text = params.get("text", "")

    new_id = add_connector(
        pkg,
        int(page_num),
        int(from_shape_id),
        int(to_shape_id),
        text=text,
    )
    shape_key = f"{page_num}:{new_id}"
    return {
        "message": f"Added connector from shape {from_shape_id} to {to_shape_id}",
        "element_id": shape_key,
    }


def _op_group_shapes(pkg: VisioPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Group multiple shapes into a new group."""
    page_num = params.get("page_num")
    shape_ids = params.get("shape_ids")

    if not page_num:
        raise ValueError("page_num required for group_shapes")
    if not shape_ids or len(shape_ids) < 2:
        raise ValueError("shape_ids (list of at least 2) required for group_shapes")

    group_id = group_shapes(
        pkg,
        int(page_num),
        [int(sid) for sid in shape_ids],
    )
    shape_key = f"{page_num}:{group_id}"
    return {
        "message": f"Created group {group_id} from {len(shape_ids)} shapes",
        "element_id": shape_key,
    }


def _op_ungroup(pkg: VisioPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Ungroup a group, promoting children to page level."""
    page_num = params.get("page_num")
    group_id = params.get("group_id")

    if not page_num:
        raise ValueError("page_num required for ungroup")
    if group_id is None:
        raise ValueError("group_id required for ungroup")

    child_ids = ungroup(
        pkg,
        int(page_num),
        int(group_id),
    )
    return {
        "message": f"Ungrouped {group_id} into {len(child_ids)} shapes: {child_ids}",
        "element_id": f"{page_num}:{child_ids[0]}" if child_ids else "",
    }


# =============================================================================
# Render Tool
# =============================================================================


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
    output='pdf' returns PDF bytes for sharing.
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

    from mcp_handley_lab.microsoft.visio.ops import render as _render_mod

    if output == "pdf":
        pdf_bytes = _render_mod.render_to_pdf(file_path)
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
    if len(set(pages)) > 5:
        raise ValueError(f"max 5 pages allowed; requested {len(set(pages))}")
    if dpi > 300:
        raise ValueError("dpi max is 300")

    result = []
    for page_num, png_bytes in _render_mod.render_to_images(file_path, pages, dpi):
        result.append(TextContent(type="text", text=f"Page {page_num}:"))
        result.append(
            ImageContent(
                type="image",
                data=base64.b64encode(png_bytes).decode(),
                mimeType="image/png",
            )
        )
    return result
