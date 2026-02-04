"""Core PowerPoint functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

from __future__ import annotations

from typing import Any, Literal

from mcp_handley_lab.microsoft.common.batch import (
    convert_custom_property_value,
    run_batch_edit,
)
from mcp_handley_lab.microsoft.common.colors import get_theme_colors_from_package
from mcp_handley_lab.microsoft.common.properties import (
    delete_custom_property,
    get_core_properties,
    get_custom_properties,
    set_core_properties,
    set_custom_property,
)
from mcp_handley_lab.microsoft.opc.constants import RT as OPC_RT
from mcp_handley_lab.microsoft.powerpoint.constants import EMU_PER_INCH
from mcp_handley_lab.microsoft.powerpoint.models import (
    CustomPropertyInfo,
    DocumentProperties,
    PowerPointEditResult,
    PowerPointOpResult,
    PowerPointReadResult,
    PresentationMeta,
    TableCell,
    TableInfo,
    ThemeColors,
)
from mcp_handley_lab.microsoft.powerpoint.ops.charts import (
    create_chart as create_chart_op,
)
from mcp_handley_lab.microsoft.powerpoint.ops.charts import (
    delete_chart as delete_chart_op,
)
from mcp_handley_lab.microsoft.powerpoint.ops.charts import (
    list_charts as list_charts_op,
)
from mcp_handley_lab.microsoft.powerpoint.ops.charts import (
    update_chart_data as update_chart_data_op,
)
from mcp_handley_lab.microsoft.powerpoint.ops.comments import (
    list_comments,
)
from mcp_handley_lab.microsoft.powerpoint.ops.images import (
    add_image,
    delete_image,
    list_images,
)
from mcp_handley_lab.microsoft.powerpoint.ops.notes import get_notes, set_notes
from mcp_handley_lab.microsoft.powerpoint.ops.placeholders import set_placeholder_text
from mcp_handley_lab.microsoft.powerpoint.ops.shapes import (
    add_connector,
    add_shape,
    delete_shape,
    edit_shape,
    get_text_in_reading_order,
    group_shapes,
    list_shapes,
    set_shape_transform,
    set_z_order,
    ungroup,
)
from mcp_handley_lab.microsoft.powerpoint.ops.slides import (
    add_slide,
    delete_slide,
    duplicate_slide,
    get_notes_count,
    get_slide_count,
    hide_slide,
    list_layouts,
    list_slides,
    reorder_slide,
    set_slide_dimensions,
)
from mcp_handley_lab.microsoft.powerpoint.ops.styling import (
    set_shape_fill,
    set_shape_line,
    set_slide_background,
    set_text_style,
)
from mcp_handley_lab.microsoft.powerpoint.ops.tables import (
    add_table,
    add_table_column,
    add_table_row,
    delete_table_column,
    delete_table_row,
    list_tables,
    set_table_cell,
)
from mcp_handley_lab.microsoft.powerpoint.ops.text import (
    add_hyperlink,
)
from mcp_handley_lab.microsoft.powerpoint.ops.text import (
    find_replace as find_replace_text,
)
from mcp_handley_lab.microsoft.powerpoint.package import PowerPointPackage

ReadScope = Literal[
    "meta",
    "slides",
    "shapes",
    "text",
    "notes",
    "layouts",
    "images",
    "tables",
    "charts",
    "properties",
    "theme",
    "comments",
]

_PREV_FIELDS = {"shape_key"}

_TEXT_FIELDS: dict[str, set[str]] = {
    "add_shape": {"text"},
    "edit_shape": {"text"},
    "set_notes": {"text"},
    "set_placeholder": {"text"},
    "set_table_cell": {"text"},
}


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
    - comments: Slide comments (all slides, or specific slide if slide_num given)

    Args:
        file_path: Path to .pptx file.
        scope: What to read.
        slide_num: Slide number (1-based). Required for shapes/text/notes/tables;
            optional for images (0 = all slides).

    Returns:
        Dict with scope-specific data.
    """
    pkg = PowerPointPackage.open(file_path)

    if scope == "meta":
        return _read_meta(pkg).model_dump(exclude_none=True)

    elif scope == "slides":
        return _read_slides(pkg).model_dump(exclude_none=True)

    elif scope == "shapes":
        if not slide_num:
            raise ValueError("slide_num required for shapes scope")
        return _read_shapes(pkg, slide_num).model_dump(exclude_none=True)

    elif scope == "text":
        if not slide_num:
            raise ValueError("slide_num required for text scope")
        return _read_text(pkg, slide_num).model_dump(exclude_none=True)

    elif scope == "notes":
        if not slide_num:
            raise ValueError("slide_num required for notes scope")
        return _read_notes(pkg, slide_num).model_dump(exclude_none=True)

    elif scope == "layouts":
        return _read_layouts(pkg).model_dump(exclude_none=True)

    elif scope == "images":
        return _read_images(pkg, slide_num or None).model_dump(exclude_none=True)

    elif scope == "tables":
        if not slide_num:
            raise ValueError("slide_num required for tables scope")
        return _read_tables(pkg, slide_num).model_dump(exclude_none=True)

    elif scope == "charts":
        if not slide_num:
            raise ValueError("slide_num required for charts scope")
        return _read_charts(pkg, slide_num).model_dump(exclude_none=True)

    elif scope == "properties":
        return _read_properties(pkg).model_dump(exclude_none=True)

    elif scope == "theme":
        return _read_theme(pkg).model_dump(exclude_none=True)

    elif scope == "comments":
        return _read_comments(pkg, slide_num or None).model_dump(exclude_none=True)

    else:
        raise ValueError(f"Unknown scope: {scope}")


def edit(
    file_path: str,
    ops: str,
) -> dict[str, Any]:
    """Edit a PowerPoint presentation using batch operations. Creates a new file if file_path doesn't exist.

    Fail-fast semantics: raises on first operation error, file unchanged on any failure.
    Use read() first to discover slides, shapes, and layouts.

    Args:
        file_path: Path to .pptx file (created if it doesn't exist).
        ops: JSON array of operation objects, e.g.:
            [{"op": "add_shape", "slide_num": 1, "x": 1.0, "y": 1.0, "width": 4.0, "height": 1.0, "text": "Title"},
             {"op": "set_text_style", "shape_key": "$prev[0]", "bold": true}]

    Available operations:
        - add_slide, delete_slide, reorder_slide, duplicate_slide, hide_slide
        - add_shape, add_connector, edit_shape, delete_shape, transform_shape, set_z_order
        - group_shapes, ungroup (group/ungroup shapes; V1: no rotation/flip/nested groups)
        - add_image, delete_image
        - add_table, set_table_cell, add_table_row, add_table_column
        - delete_table_row, delete_table_column
        - set_shape_fill, set_shape_line, set_text_style, set_slide_background
        - set_dimensions, set_placeholder, set_notes
        - add_hyperlink
        - set_property, set_custom_property, delete_custom_property
        - add_chart, delete_chart, update_chart_data
        - find_replace (text search/replace in shape text bodies)

    Returns:
        Dict with success status, counts, and per-operation results.

    Raises:
        ValueError: Invalid JSON, invalid operation, missing required params.
        RuntimeError: Save failed after successful operations.
    """
    return run_batch_edit(
        file_path=file_path,
        ops=ops,
        open_pkg=PowerPointPackage.open,
        new_pkg=PowerPointPackage.new,
        apply_op=_apply_op,
        make_op_result=PowerPointOpResult,
        make_edit_result=PowerPointEditResult,
        prev_fields=_PREV_FIELDS,
        text_fields=_TEXT_FIELDS,
    )


# =============================================================================
# Read Helpers
# =============================================================================


def _get_document_properties(pkg: PowerPointPackage) -> DocumentProperties:
    """Get document properties from core.xml and custom.xml."""
    core = get_core_properties(pkg)
    custom = get_custom_properties(pkg)

    return DocumentProperties(
        title=core["title"],
        author=core["author"],
        subject=core["subject"],
        keywords=core["keywords"],
        category=core["category"],
        comments=core["comments"],
        created=core["created"],
        modified=core["modified"],
        revision=core["revision"],
        last_modified_by=core["last_modified_by"],
        custom_properties=[
            CustomPropertyInfo(name=p["name"], value=p["value"], type=p["type"])
            for p in custom
        ],
    )


def _read_meta(pkg: PowerPointPackage) -> PowerPointReadResult:
    """Read presentation metadata."""
    width_emu, height_emu = pkg.get_slide_dimensions()

    return PowerPointReadResult(
        scope="meta",
        meta=PresentationMeta(
            slide_count=get_slide_count(pkg),
            slide_width_inches=width_emu / EMU_PER_INCH,
            slide_height_inches=height_emu / EMU_PER_INCH,
            notes_count=get_notes_count(pkg),
            properties=_get_document_properties(pkg),
        ),
    )


def _read_properties(pkg: PowerPointPackage) -> PowerPointReadResult:
    """Read document properties."""
    return PowerPointReadResult(
        scope="properties",
        properties=_get_document_properties(pkg),
    )


def _read_slides(pkg: PowerPointPackage) -> PowerPointReadResult:
    """Read all slides summary."""
    return PowerPointReadResult(
        scope="slides",
        slides=list_slides(pkg),
    )


def _read_shapes(pkg: PowerPointPackage, slide_num: int) -> PowerPointReadResult:
    """Read shapes from a slide."""
    return PowerPointReadResult(
        scope="shapes",
        shapes=list_shapes(pkg, slide_num),
    )


def _read_text(pkg: PowerPointPackage, slide_num: int) -> PowerPointReadResult:
    """Read all text from a slide in reading order."""
    return PowerPointReadResult(
        scope="text",
        text=get_text_in_reading_order(pkg, slide_num),
    )


def _read_notes(pkg: PowerPointPackage, slide_num: int) -> PowerPointReadResult:
    """Read speaker notes for a slide."""
    notes = get_notes(pkg, slide_num)
    return PowerPointReadResult(
        scope="notes",
        notes=notes,
    )


def _read_layouts(pkg: PowerPointPackage) -> PowerPointReadResult:
    """Read available slide layouts."""
    return PowerPointReadResult(
        scope="layouts",
        layouts=list_layouts(pkg),
    )


def _read_images(pkg: PowerPointPackage, slide_num: int | None) -> PowerPointReadResult:
    """Read images from the presentation."""
    return PowerPointReadResult(
        scope="images",
        images=list_images(pkg, slide_num),
    )


def _read_tables(pkg: PowerPointPackage, slide_num: int) -> PowerPointReadResult:
    """Read tables from a slide with structure."""
    raw_tables = list_tables(pkg, slide_num)

    # Convert to TableInfo models
    tables = []
    for t in raw_tables:
        cells = [TableCell(**c) for c in t["cells"]]
        tables.append(
            TableInfo(
                shape_key=t["shape_key"],
                shape_id=t["shape_id"],
                name=t["name"],
                x_inches=t["x_inches"],
                y_inches=t["y_inches"],
                width_inches=t["width_inches"],
                height_inches=t["height_inches"],
                rows=t["rows"],
                cols=t["cols"],
                cells=cells,
            )
        )

    return PowerPointReadResult(
        scope="tables",
        tables=tables,
    )


def _read_charts(pkg: PowerPointPackage, slide_num: int) -> PowerPointReadResult:
    """Read charts from a slide."""
    charts = list_charts_op(pkg, slide_num)
    return PowerPointReadResult(
        scope="charts",
        charts=charts,
    )


def _read_theme(pkg: PowerPointPackage) -> PowerPointReadResult:
    """Read theme colors from the presentation."""
    colors = get_theme_colors_from_package(pkg, pkg.presentation_path, OPC_RT.THEME)

    # Convert dict to ThemeColors model
    theme_colors = ThemeColors(**colors) if colors else None

    return PowerPointReadResult(
        scope="theme",
        theme_colors=theme_colors,
    )


def _read_comments(
    pkg: PowerPointPackage, slide_num: int | None
) -> PowerPointReadResult:
    """Read comments from the presentation."""
    comments = list_comments(pkg, slide_num)
    return PowerPointReadResult(
        scope="comments",
        comments=comments,
    )


# =============================================================================
# Operation Dispatcher
# =============================================================================


def _apply_op(
    pkg: PowerPointPackage, op: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Apply a single operation to an open package.

    Returns dict with 'message' and optionally 'element_id' for $prev chaining.
    """
    if op == "add_slide":
        return _op_add_slide(pkg, params)
    elif op == "delete_slide":
        return _op_delete_slide(pkg, params)
    elif op == "reorder_slide":
        return _op_reorder_slide(pkg, params)
    elif op == "duplicate_slide":
        return _op_duplicate_slide(pkg, params)
    elif op == "set_dimensions":
        return _op_set_dimensions(pkg, params)
    elif op == "set_placeholder":
        return _op_set_placeholder(pkg, params)
    elif op == "set_notes":
        return _op_set_notes(pkg, params)
    elif op == "add_shape":
        return _op_add_shape(pkg, params)
    elif op == "add_connector":
        return _op_add_connector(pkg, params)
    elif op == "edit_shape":
        return _op_edit_shape(pkg, params)
    elif op == "delete_shape":
        return _op_delete_shape(pkg, params)
    elif op == "transform_shape":
        return _op_transform_shape(pkg, params)
    elif op == "set_z_order":
        return _op_set_z_order(pkg, params)
    elif op == "add_image":
        return _op_add_image(pkg, params)
    elif op == "delete_image":
        return _op_delete_image(pkg, params)
    elif op == "add_table":
        return _op_add_table(pkg, params)
    elif op == "set_table_cell":
        return _op_set_table_cell(pkg, params)
    elif op == "add_table_row":
        return _op_add_table_row(pkg, params)
    elif op == "add_table_column":
        return _op_add_table_column(pkg, params)
    elif op == "delete_table_row":
        return _op_delete_table_row(pkg, params)
    elif op == "delete_table_column":
        return _op_delete_table_column(pkg, params)
    elif op == "set_shape_fill":
        return _op_set_shape_fill(pkg, params)
    elif op == "set_shape_line":
        return _op_set_shape_line(pkg, params)
    elif op == "set_text_style":
        return _op_set_text_style(pkg, params)
    elif op == "set_slide_background":
        return _op_set_slide_background(pkg, params)
    elif op == "add_hyperlink":
        return _op_add_hyperlink(pkg, params)
    elif op == "hide_slide":
        return _op_hide_slide(pkg, params)
    elif op == "set_property":
        return _op_set_property(pkg, params)
    elif op == "set_custom_property":
        return _op_set_custom_property(pkg, params)
    elif op == "delete_custom_property":
        return _op_delete_custom_property(pkg, params)
    elif op == "add_chart":
        return _op_add_chart(pkg, params)
    elif op == "delete_chart":
        return _op_delete_chart(pkg, params)
    elif op == "update_chart_data":
        return _op_update_chart_data(pkg, params)
    elif op == "find_replace":
        return _op_find_replace(pkg, params)
    elif op == "group_shapes":
        return _op_group_shapes(pkg, params)
    elif op == "ungroup":
        return _op_ungroup(pkg, params)
    else:
        raise ValueError(f"Unknown operation: {op}")


# =============================================================================
# Individual Operation Handlers
# =============================================================================


def _op_add_slide(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add a new slide."""
    layout_name = params.get("layout_name")
    new_num = add_slide(pkg, layout_name)
    return {"message": f"Added slide {new_num}", "element_id": ""}


def _op_delete_slide(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Delete a slide."""
    slide_num = params.get("slide_num")
    if slide_num is None:
        raise ValueError("slide_num required for delete_slide")
    delete_slide(pkg, slide_num)
    return {"message": f"Deleted slide {slide_num}", "element_id": ""}


def _op_reorder_slide(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Reorder a slide."""
    slide_num = params.get("slide_num")
    new_position = params.get("new_position")
    if slide_num is None:
        raise ValueError("slide_num required for reorder_slide")
    if new_position is None:
        raise ValueError("new_position required for reorder_slide")
    reorder_slide(pkg, slide_num, new_position)
    return {
        "message": f"Moved slide {slide_num} to position {new_position}",
        "element_id": "",
    }


def _op_duplicate_slide(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Duplicate a slide."""
    slide_num = params.get("slide_num")
    position = params.get("new_position")
    if slide_num is None:
        raise ValueError("slide_num required for duplicate_slide")
    new_num = duplicate_slide(pkg, slide_num, position)
    pos_msg = f" at position {new_num}" if position else ""
    return {
        "message": f"Duplicated slide {slide_num} as slide {new_num}{pos_msg}",
        "element_id": "",
    }


def _op_set_dimensions(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Set slide dimensions."""
    preset = params.get("preset")
    width = params.get("width")
    height = params.get("height")
    set_slide_dimensions(pkg, preset=preset, width=width, height=height)
    if preset:
        return {"message": f"Set slide dimensions to {preset}", "element_id": ""}
    else:
        return {
            "message": f"Set slide dimensions to {width}x{height} inches",
            "element_id": "",
        }


def _op_set_placeholder(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Set placeholder text."""
    slide_num = params.get("slide_num")
    text = params.get("text")
    placeholder_type = params.get("placeholder_type")
    placeholder_idx = params.get("placeholder_idx")
    if slide_num is None:
        raise ValueError("slide_num required for set_placeholder")
    if text is None:
        raise ValueError("text required for set_placeholder")
    set_placeholder_text(pkg, slide_num, text, placeholder_type, placeholder_idx)
    return {
        "message": f"Set placeholder text on slide {slide_num}",
        "element_id": "",
    }


def _op_set_notes(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Set speaker notes."""
    slide_num = params.get("slide_num")
    text = params.get("text")
    if slide_num is None:
        raise ValueError("slide_num required for set_notes")
    if text is None:
        raise ValueError("text required for set_notes")
    set_notes(pkg, slide_num, text)
    return {"message": f"Set notes for slide {slide_num}", "element_id": ""}


def _op_add_shape(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add a shape."""
    slide_num = params.get("slide_num")
    x = params.get("x")
    y = params.get("y")
    width = params.get("width")
    height = params.get("height")
    text = params.get("text", "")
    shape_type = params.get("shape_type", "rect")
    if slide_num is None:
        raise ValueError("slide_num required for add_shape")
    if x is None or y is None or width is None or height is None:
        raise ValueError("x, y, width, height required for add_shape")
    shape_key = add_shape(pkg, slide_num, x, y, width, height, text, shape_type)
    return {
        "message": f"Added {shape_type} shape on slide {slide_num}",
        "element_id": shape_key,
    }


def _op_add_connector(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add a connector between two shapes."""
    slide_num = params.get("slide_num")
    from_shape_key = params.get("from_shape_key")
    to_shape_key = params.get("to_shape_key")
    connector_type = params.get("connector_type", "straightConnector1")

    if slide_num is None:
        raise ValueError("slide_num required for add_connector")
    if from_shape_key is None:
        raise ValueError("from_shape_key required for add_connector")
    if to_shape_key is None:
        raise ValueError("to_shape_key required for add_connector")

    shape_key = add_connector(
        pkg, slide_num, from_shape_key, to_shape_key, connector_type
    )
    return {
        "message": f"Added connector from {from_shape_key} to {to_shape_key}",
        "element_id": shape_key,
    }


def _op_edit_shape(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Edit shape text."""
    shape_key = params.get("shape_key")
    text = params.get("text")
    bullet_style = params.get("bullet_style")
    if shape_key is None:
        raise ValueError("shape_key required for edit_shape")
    if text is None:
        raise ValueError("text required for edit_shape")
    edit_shape(pkg, shape_key, text, bullet_style)
    return {"message": f"Edited shape {shape_key}", "element_id": shape_key}


def _op_delete_shape(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Delete a shape."""
    shape_key = params.get("shape_key")
    if shape_key is None:
        raise ValueError("shape_key required for delete_shape")
    delete_shape(pkg, shape_key)
    return {"message": f"Deleted shape {shape_key}", "element_id": ""}


def _op_transform_shape(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Move/resize a shape."""
    shape_key = params.get("shape_key")
    x = params.get("x")
    y = params.get("y")
    width = params.get("width")
    height = params.get("height")
    if shape_key is None:
        raise ValueError("shape_key required for transform_shape")
    set_shape_transform(pkg, shape_key, x, y, width, height)
    return {"message": f"Transformed shape {shape_key}", "element_id": shape_key}


def _op_set_z_order(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Change z-order (stacking order) of a shape."""
    shape_key = params.get("shape_key")
    action = params.get("action")
    if shape_key is None:
        raise ValueError("shape_key required for set_z_order")
    if action is None:
        raise ValueError("action required for set_z_order")
    set_z_order(pkg, shape_key, action)
    return {"message": f"Set z-order of {shape_key}: {action}", "element_id": shape_key}


def _op_add_image(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add an image."""
    slide_num = params.get("slide_num")
    image_path = params.get("image_path")
    if slide_num is None:
        raise ValueError("slide_num required for add_image")
    if image_path is None:
        raise ValueError("image_path required for add_image")
    shape_key = add_image(
        pkg,
        slide_num,
        image_path,
        **{k: params[k] for k in ("x", "y", "width", "height") if k in params},
    )
    return {"message": f"Added image on slide {slide_num}", "element_id": shape_key}


def _op_delete_image(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Delete an image."""
    shape_key = params.get("shape_key")
    if shape_key is None:
        raise ValueError("shape_key required for delete_image")
    slide_num_str, shape_id_str = shape_key.split(":")
    slide_num = int(slide_num_str)
    shape_id = int(shape_id_str)
    delete_image(pkg, slide_num, shape_id)
    return {"message": f"Deleted image {shape_key}", "element_id": ""}


def _op_add_table(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add a table."""
    slide_num = params.get("slide_num")
    rows = params.get("rows")
    cols = params.get("cols")
    if slide_num is None:
        raise ValueError("slide_num required for add_table")
    if rows is None or cols is None:
        raise ValueError("rows and cols required for add_table")
    shape_key = add_table(
        pkg,
        slide_num,
        rows,
        cols,
        **{k: params[k] for k in ("x", "y", "width", "height") if k in params},
    )
    return {
        "message": f"Added {rows}x{cols} table on slide {slide_num}",
        "element_id": shape_key,
    }


def _op_set_table_cell(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Set table cell text."""
    shape_key = params.get("shape_key")
    row = params.get("row")
    col = params.get("col")
    text = params.get("text")
    if shape_key is None:
        raise ValueError("shape_key required for set_table_cell")
    if row is None or col is None:
        raise ValueError("row and col required for set_table_cell")
    if text is None:
        raise ValueError("text required for set_table_cell")
    set_table_cell(pkg, shape_key, row, col, text)
    return {
        "message": f"Set cell ({row},{col}) in table {shape_key}",
        "element_id": shape_key,
    }


def _op_add_table_row(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add a table row."""
    shape_key = params.get("shape_key")
    position = params.get("row")
    if shape_key is None:
        raise ValueError("shape_key required for add_table_row")
    add_table_row(pkg, shape_key, position)
    return {
        "message": f"Added row to table {shape_key}",
        "element_id": shape_key,
    }


def _op_add_table_column(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Add a table column."""
    shape_key = params.get("shape_key")
    position = params.get("col")
    if shape_key is None:
        raise ValueError("shape_key required for add_table_column")
    add_table_column(pkg, shape_key, position)
    return {
        "message": f"Added column to table {shape_key}",
        "element_id": shape_key,
    }


def _op_delete_table_row(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Delete a table row."""
    shape_key = params.get("shape_key")
    row = params.get("row")
    if shape_key is None:
        raise ValueError("shape_key required for delete_table_row")
    if row is None:
        raise ValueError("row required for delete_table_row")
    delete_table_row(pkg, shape_key, row)
    return {
        "message": f"Deleted row {row} from table {shape_key}",
        "element_id": shape_key,
    }


def _op_delete_table_column(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Delete a table column."""
    shape_key = params.get("shape_key")
    col = params.get("col")
    if shape_key is None:
        raise ValueError("shape_key required for delete_table_column")
    if col is None:
        raise ValueError("col required for delete_table_column")
    delete_table_column(pkg, shape_key, col)
    return {
        "message": f"Deleted column {col} from table {shape_key}",
        "element_id": shape_key,
    }


def _op_set_shape_fill(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Set shape fill color."""
    shape_key = params.get("shape_key")
    color = params.get("color")
    if shape_key is None:
        raise ValueError("shape_key required for set_shape_fill")
    if color is None:
        raise ValueError("color required for set_shape_fill")
    set_shape_fill(pkg, shape_key, color)
    return {"message": f"Set fill color for shape {shape_key}", "element_id": shape_key}


def _op_set_shape_line(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Set shape line/border."""
    shape_key = params.get("shape_key")
    color = params.get("color")
    line_width = params.get("line_width")
    if shape_key is None:
        raise ValueError("shape_key required for set_shape_line")
    set_shape_line(pkg, shape_key, color, line_width)
    return {"message": f"Set line style for shape {shape_key}", "element_id": shape_key}


def _op_set_text_style(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Set text style."""
    shape_key = params.get("shape_key")
    size = params.get("size")
    bold = params.get("bold")
    italic = params.get("italic")
    color = params.get("color")
    alignment = params.get("alignment")
    font = params.get("font")
    if shape_key is None:
        raise ValueError("shape_key required for set_text_style")
    set_text_style(pkg, shape_key, size, bold, italic, color, alignment, font)
    return {"message": f"Set text style for shape {shape_key}", "element_id": shape_key}


def _op_set_slide_background(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Set slide background color."""
    slide_num = params.get("slide_num")
    color = params.get("color")
    if slide_num is None:
        raise ValueError("slide_num required for set_slide_background")
    if color is None:
        raise ValueError("color required for set_slide_background")
    set_slide_background(pkg, slide_num, color)
    return {"message": f"Set background color for slide {slide_num}", "element_id": ""}


def _op_add_hyperlink(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add hyperlink to shape."""
    shape_key = params.get("shape_key")
    url = params.get("url")
    tooltip = params.get("tooltip")
    target_slide = params.get("target_slide")
    if shape_key is None:
        raise ValueError("shape_key required for add_hyperlink")
    if url is None and target_slide is None:
        raise ValueError("Either url or target_slide required for add_hyperlink")
    if url is not None and target_slide is not None:
        raise ValueError("Cannot specify both url and target_slide")
    add_hyperlink(pkg, shape_key, url, tooltip, target_slide)
    link_type = "external URL" if url else f"slide {target_slide}"
    return {
        "message": f"Added hyperlink to {link_type} on shape {shape_key}",
        "element_id": shape_key,
    }


def _op_hide_slide(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Hide or show a slide."""
    slide_num = params.get("slide_num")
    hidden = params.get("hidden", True)
    if slide_num is None:
        raise ValueError("slide_num required for hide_slide")
    hide_slide(pkg, slide_num, hidden)
    action = "Hidden" if hidden else "Shown"
    return {"message": f"{action} slide {slide_num}", "element_id": ""}


def _op_set_property(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Set core document property."""
    property_name = params.get("property_name")
    property_value = params.get("property_value")
    if property_name is None:
        raise ValueError("property_name required for set_property")
    if property_value is None:
        raise ValueError("property_value required for set_property")
    set_core_properties(pkg, **{property_name: property_value})
    return {"message": f"Set core property '{property_name}'", "element_id": ""}


def _op_set_custom_property(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Set custom document property."""
    property_name = params.get("property_name")
    property_value = params.get("property_value")
    property_type = params.get("property_type", "string")
    if property_name is None:
        raise ValueError("property_name required for set_custom_property")
    if property_value is None:
        raise ValueError("property_value required for set_custom_property")

    actual_value, property_type = convert_custom_property_value(
        property_value, property_type
    )
    set_custom_property(pkg, property_name, actual_value, property_type)
    return {"message": f"Set custom property '{property_name}'", "element_id": ""}


def _op_delete_custom_property(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Delete custom document property."""
    property_name = params.get("property_name")
    if property_name is None:
        raise ValueError("property_name required for delete_custom_property")
    deleted = delete_custom_property(pkg, property_name)
    if deleted:
        return {
            "message": f"Deleted custom property '{property_name}'",
            "element_id": "",
        }
    else:
        raise ValueError(f"Custom property '{property_name}' not found")


def _op_add_chart(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add a chart to a slide."""
    slide_num = params.get("slide_num")
    if not slide_num:
        raise ValueError("slide_num required for add_chart")
    chart_type = params.get("chart_type", "column")
    data = params.get("data")
    if not data:
        raise ValueError("data required for add_chart (2D list)")
    title = params.get("title")
    x = float(params.get("x", 1.0))
    y = float(params.get("y", 1.5))
    width = float(params.get("width", 8.0))
    height = float(params.get("height", 5.0))

    shape_key = create_chart_op(
        pkg,
        slide_num,
        chart_type,
        data,
        x=x,
        y=y,
        width=width,
        height=height,
        title=title,
    )
    return {
        "message": f"Added {chart_type} chart to slide {slide_num}",
        "element_id": shape_key,
    }


def _op_delete_chart(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Delete a chart from a slide."""
    slide_num = params.get("slide_num")
    if not slide_num:
        raise ValueError("slide_num required for delete_chart")
    shape_key = params.get("shape_key")
    if not shape_key:
        raise ValueError("shape_key required for delete_chart")
    delete_chart_op(pkg, slide_num, shape_key)
    return {"message": f"Deleted chart {shape_key}", "element_id": ""}


def _op_update_chart_data(
    pkg: PowerPointPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Update chart data."""
    slide_num = params.get("slide_num")
    if not slide_num:
        raise ValueError("slide_num required for update_chart_data")
    shape_key = params.get("shape_key")
    if not shape_key:
        raise ValueError("shape_key required for update_chart_data")
    data = params.get("data")
    if not data:
        raise ValueError("data required for update_chart_data (2D list)")
    update_chart_data_op(pkg, slide_num, shape_key, data)
    return {"message": f"Updated chart data for {shape_key}", "element_id": shape_key}


def _op_find_replace(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Find and replace text in shape text bodies."""
    search = params.get("search")
    if not search:
        raise ValueError("search required for find_replace")
    replace_text_str = params.get("replace", "")
    slide_num = params.get(
        "slide_num"
    )  # Optional - if not provided, searches all slides
    match_case = params.get("match_case", True)  # Default to case-sensitive

    count = find_replace_text(
        pkg, search, replace_text_str, slide_num, match_case=match_case
    )
    if slide_num:
        return {
            "message": f"Replaced {count} occurrences of '{search}' on slide {slide_num}",
            "element_id": "",
        }
    else:
        return {
            "message": f"Replaced {count} occurrences of '{search}' across all slides",
            "element_id": "",
        }


def _op_group_shapes(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Group multiple shapes into a new group."""
    slide_num = params.get("slide_num")
    shape_keys = params.get("shape_keys")
    if slide_num is None:
        raise ValueError("slide_num required for group_shapes")
    if not shape_keys or len(shape_keys) < 2:
        raise ValueError("shape_keys (list of at least 2) required for group_shapes")
    group_key = group_shapes(pkg, slide_num, shape_keys)
    return {
        "message": f"Created group {group_key} from {len(shape_keys)} shapes",
        "element_id": group_key,
    }


def _op_ungroup(pkg: PowerPointPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Ungroup a group, promoting children to parent level."""
    shape_key = params.get("shape_key")
    if not shape_key:
        raise ValueError("shape_key required for ungroup")
    child_keys = ungroup(pkg, shape_key)
    return {
        "message": f"Ungrouped {shape_key} into {len(child_keys)} shapes: {child_keys}",
        "element_id": child_keys[0] if child_keys else "",
    }
