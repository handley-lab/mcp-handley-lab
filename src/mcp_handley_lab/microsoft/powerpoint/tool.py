"""PowerPoint MCP tool for reading and editing .pptx files."""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.microsoft.common.properties import (
    delete_custom_property,
    get_core_properties,
    get_custom_properties,
    set_core_properties,
    set_custom_property,
)
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
)
from mcp_handley_lab.microsoft.powerpoint.ops.images import (
    add_image,
    delete_image,
    list_images,
)
from mcp_handley_lab.microsoft.powerpoint.ops.notes import get_notes, set_notes
from mcp_handley_lab.microsoft.powerpoint.ops.placeholders import set_placeholder_text
from mcp_handley_lab.microsoft.powerpoint.ops.render import (
    render_to_images,
    render_to_pdf,
)
from mcp_handley_lab.microsoft.powerpoint.ops.shapes import (
    add_shape,
    delete_shape,
    edit_shape,
    get_text_in_reading_order,
    list_shapes,
    set_shape_transform,
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
from mcp_handley_lab.microsoft.powerpoint.ops.text import add_hyperlink
from mcp_handley_lab.microsoft.powerpoint.package import PowerPointPackage

mcp = FastMCP("PowerPoint Tool")

ReadScope = Literal[
    "meta",
    "slides",
    "shapes",
    "text",
    "notes",
    "layouts",
    "images",
    "tables",
    "properties",
]

# Pattern to match $prev[N] references
_PREV_PATTERN = re.compile(r"^\$prev\[(\d+)\]$")

# Operations that cannot be used in batch mode
_EXCLUDED_OPS: set[str] = set()

# Fields that can use $prev references (shape_key only, NOT slide_num)
_PREV_FIELDS = {"shape_key"}

# Fields that should have text normalization (\\n -> \n, \\t -> \t)
_TEXT_FIELDS: dict[str, set[str]] = {
    "add_shape": {"text"},
    "edit_shape": {"text"},
    "set_notes": {"text"},
    "set_placeholder": {"text"},
    "set_table_cell": {"text"},
}

# Maximum operations per batch
_MAX_OPS = 500


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
            - "properties": Document properties (title, author, custom properties)
        slide_num: Slide number (1-based). Required for shapes/text/notes/tables; optional for images (0 = all slides)

    Returns:
        PowerPointReadResult with scope-specific data
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

    elif scope == "properties":
        return _read_properties(pkg).model_dump(exclude_none=True)

    else:
        raise ValueError(f"Unknown scope: {scope}")


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


def _normalize_text(op: str, params: dict[str, Any]) -> dict[str, Any]:
    """Normalize escaped characters in text fields.

    Converts \\n to newline and \\t to tab only for known text fields.
    """
    fields = _TEXT_FIELDS.get(op, set())
    for field in fields:
        if field in params and isinstance(params[field], str):
            params[field] = params[field].replace("\\n", "\n").replace("\\t", "\t")
    return params


def _resolve_prev_refs(
    params: dict[str, Any],
    results: list[PowerPointOpResult],
    index: int,
) -> dict[str, Any]:
    """Resolve $prev[N] references in operation parameters.

    Args:
        params: Operation parameters (copied before modification)
        results: Results from previous operations
        index: Current operation index (for validation)

    Returns:
        Modified params dict

    Raises:
        ValueError: If $prev reference is invalid
    """
    resolved = copy.copy(params)
    for field in _PREV_FIELDS:
        if field not in resolved:
            continue
        value = resolved[field]
        if not isinstance(value, str):
            continue
        match = _PREV_PATTERN.match(value)
        if match:
            ref_idx = int(match.group(1))
            if ref_idx >= index:
                raise ValueError(
                    f"$prev[{ref_idx}] at index {index}: cannot reference future operation"
                )
            if ref_idx >= len(results):
                raise ValueError(f"$prev[{ref_idx}]: index out of range")
            prev_result = results[ref_idx]
            if not prev_result.success:
                raise ValueError(f"$prev[{ref_idx}]: referenced operation failed")
            if not prev_result.element_id:
                raise ValueError(
                    f"$prev[{ref_idx}]: referenced operation has no element_id"
                )
            resolved[field] = prev_result.element_id
    return resolved


@mcp.tool()
def edit(
    file_path: str = Field(description="Path to .pptx file"),
    ops: str = Field(
        description='JSON array of operation objects. Each object has "op" (operation name) '
        "plus operation-specific fields. Use $prev[N] to reference element_id from operation N."
    ),
    mode: str = Field(
        default="atomic",
        description="'atomic' (save only if all succeed) or 'partial' (save if any succeed)",
    ),
) -> dict[str, Any]:
    """Edit a PowerPoint presentation using batch operations. Creates a new file if file_path doesn't exist.

    Batch operations allow multiple edits in a single call with $prev chaining.
    Use read() first to discover slides, shapes, and layouts.

    Args:
        file_path: Path to .pptx file
        ops: JSON array of operation objects, e.g.:
            [{"op": "add_shape", "slide_num": 1, "x": 1.0, "y": 1.0, "width": 4.0, "height": 1.0, "text": "Title"},
             {"op": "set_text_style", "shape_key": "$prev[0]", "bold": true}]
        mode: 'atomic' (all-or-nothing) or 'partial' (save successful ops)

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

    $prev chaining:
        Reference results of previous operations using $prev[N] where N is the
        operation index (0-based). Only works for shape_key (NOT slide_num).

    Returns:
        PowerPointEditResult with success status, counts, and per-operation results
    """
    # Handle direct calls (Field descriptors not resolved outside MCP)
    if not isinstance(mode, str):
        mode = "atomic"

    # Parse operations
    try:
        operations = json.loads(ops)
    except json.JSONDecodeError as e:
        return PowerPointEditResult(
            success=False,
            message=f"Invalid JSON in ops: {e}",
        ).model_dump(exclude_none=True)

    if not isinstance(operations, list):
        return PowerPointEditResult(
            success=False,
            message="ops must be a JSON array",
        ).model_dump(exclude_none=True)

    if len(operations) == 0:
        return PowerPointEditResult(
            success=False,
            message="ops array is empty",
        ).model_dump(exclude_none=True)

    if len(operations) > _MAX_OPS:
        return PowerPointEditResult(
            success=False,
            message=f"ops array exceeds maximum of {_MAX_OPS} operations",
        ).model_dump(exclude_none=True)

    if mode not in ("atomic", "partial"):
        return PowerPointEditResult(
            success=False,
            message=f"Invalid mode '{mode}': must be 'atomic' or 'partial'",
        ).model_dump(exclude_none=True)

    # Validate operations
    for i, op_dict in enumerate(operations):
        if not isinstance(op_dict, dict):
            return PowerPointEditResult(
                success=False,
                message=f"Operation at index {i} is not an object",
            ).model_dump(exclude_none=True)
        if "op" not in op_dict:
            return PowerPointEditResult(
                success=False,
                message=f"Operation at index {i} missing 'op' field",
            ).model_dump(exclude_none=True)
        if op_dict["op"] in _EXCLUDED_OPS:
            return PowerPointEditResult(
                success=False,
                message=f"Operation '{op_dict['op']}' at index {i} is not allowed in batch mode",
            ).model_dump(exclude_none=True)

    # Open package (or create new if file doesn't exist)
    if os.path.exists(file_path):
        pkg = PowerPointPackage.open(file_path)
    else:
        pkg = PowerPointPackage.new()
    results: list[PowerPointOpResult] = []

    # Execute operations
    for i, op_dict in enumerate(operations):
        op_name = op_dict["op"]
        params = {k: v for k, v in op_dict.items() if k != "op"}

        try:
            # Resolve $prev references
            params = _resolve_prev_refs(params, results, i)

            # Normalize text fields
            params = _normalize_text(op_name, params)

            # Execute operation
            result = _apply_op(pkg, op_name, params)
            results.append(
                PowerPointOpResult(
                    index=i,
                    op=op_name,
                    success=True,
                    element_id=result.get("element_id", ""),
                    message=result.get("message", ""),
                )
            )
        except Exception as e:
            results.append(
                PowerPointOpResult(
                    index=i,
                    op=op_name,
                    success=False,
                    error=str(e),
                )
            )
            # In atomic mode, stop on first failure
            if mode == "atomic":
                break

    # Calculate summary
    succeeded = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    total = len(operations)

    # Determine if we should save
    should_save = (failed == 0 and succeeded > 0) if mode == "atomic" else succeeded > 0

    # Save if appropriate
    saved = False
    if should_save:
        try:
            pkg.save(file_path)
            saved = True
        except Exception as e:
            return PowerPointEditResult(
                success=False,
                message=f"Operations succeeded but save failed: {e}",
                total=total,
                succeeded=succeeded,
                failed=failed,
                results=results,
                saved=False,
            ).model_dump(exclude_none=True)

    # Build response
    if mode == "atomic":
        if failed > 0:
            message = f"Batch failed: {failed} operation(s) failed, file unchanged"
            success = False
        else:
            message = f"Batch completed: {succeeded}/{total} operation(s) succeeded"
            success = True
    else:  # partial
        message = (
            f"Batch completed: {succeeded}/{total} succeeded, {failed}/{total} failed"
        )
        success = succeeded > 0

    return PowerPointEditResult(
        success=success,
        message=message,
        total=total,
        succeeded=succeeded,
        failed=failed,
        results=results,
        saved=saved,
    ).model_dump(exclude_none=True)


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
    elif op == "edit_shape":
        return _op_edit_shape(pkg, params)
    elif op == "delete_shape":
        return _op_delete_shape(pkg, params)
    elif op == "transform_shape":
        return _op_transform_shape(pkg, params)
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
    result = set_placeholder_text(
        pkg, slide_num, text, placeholder_type, placeholder_idx
    )
    if not result:
        raise ValueError(f"Placeholder not found on slide {slide_num}")
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
    if slide_num is None:
        raise ValueError("slide_num required for add_shape")
    if x is None or y is None or width is None or height is None:
        raise ValueError("x, y, width, height required for add_shape")
    shape_key = add_shape(pkg, slide_num, x, y, width, height, text)
    return {"message": f"Added shape on slide {slide_num}", "element_id": shape_key}


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
    from datetime import datetime, timezone

    property_name = params.get("property_name")
    property_value = params.get("property_value")
    property_type = params.get("property_type", "string")
    if property_name is None:
        raise ValueError("property_name required for set_custom_property")
    if property_value is None:
        raise ValueError("property_value required for set_custom_property")

    # Convert value to appropriate type
    actual_value: Any = property_value
    if property_type in ("int", "i4"):
        actual_value = int(property_value)
    elif property_type in ("float", "r8"):
        actual_value = float(property_value)
    elif property_type == "bool":
        actual_value = property_value.lower() in ("true", "1", "yes")
    elif property_type in ("datetime", "filetime"):
        property_type = "datetime"
        dt = datetime.fromisoformat(property_value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        actual_value = dt

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


# =============================================================================
# Render Tool
# =============================================================================


@mcp.tool()
def render(
    file_path: str,
    slides: list[int] = Field(default_factory=list),
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
        slides: Slide numbers to render (1-based). Required for PNG output. Max 5 slides.
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
    if not slides:
        raise ValueError("slides is required for PNG output")
    if dpi > 300:
        raise ValueError("dpi max is 300")

    result = []
    for slide_num, png_bytes in render_to_images(file_path, slides, dpi):
        result.append(TextContent(type="text", text=f"Slide {slide_num}:"))
        result.append(
            ImageContent(
                type="image",
                data=base64.b64encode(png_bytes).decode(),
                mimeType="image/png",
            )
        )
    return result
