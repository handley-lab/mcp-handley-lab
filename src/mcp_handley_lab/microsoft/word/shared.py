"""Core Word document functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Image
from mcp.types import TextContent

from mcp_handley_lab.microsoft.word import document as word_ops
from mcp_handley_lab.microsoft.word.models import (
    BibAuthor,
    BibSourceInfo,
    Block,
    BookmarkInfo,
    CaptionInfo,
    CommentInfo,
    ContentControlInfo,
    DocumentReadResult,
    EditResult,
    EquationInfo,
    FootnoteInfo,
    ListInfo,
    OpResult,
    RevisionInfo,
    TextBoxInfo,
    ThemeColors,
    TOCInfo,
)
from mcp_handley_lab.microsoft.word.package import WordPackage

if TYPE_CHECKING:
    pass


# Helper dispatch dicts for header/footer operations
_HF_SET_OPS = {
    "set_header": "header",
    "set_footer": "footer",
    "set_first_page_header": "first_page_header",
    "set_first_page_footer": "first_page_footer",
    "set_even_page_header": "even_page_header",
    "set_even_page_footer": "even_page_footer",
}
_HF_APPEND_OPS = {"append_header": "header", "append_footer": "footer"}
_HF_CLEAR_OPS = {"clear_header": "header", "clear_footer": "footer"}


def _parse_json_param(
    value: Any, field_name: str, expected_type: type | tuple = dict
) -> Any:
    """Parse parameter that may be JSON string or already-parsed object.

    Args:
        value: The parameter value (string, dict, list, or None)
        field_name: Name for error messages
        expected_type: Expected type(s) after parsing (default: dict)

    Returns:
        Parsed value if string, passthrough if already correct type,
        None if falsy (caller handles default).

    Raises:
        ValueError: If value is wrong type or invalid JSON.
    """
    if not value:
        return None  # Let caller handle default
    if isinstance(value, expected_type):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"{field_name} must be valid JSON: {e}")
        if not isinstance(parsed, expected_type):
            if isinstance(expected_type, tuple):
                type_names = "/".join(t.__name__ for t in expected_type)
            else:
                type_names = expected_type.__name__
            raise ValueError(
                f"{field_name} must be {type_names}, got {type(parsed).__name__}"
            )
        return parsed
    if isinstance(expected_type, tuple):
        type_names = "/".join(t.__name__ for t in expected_type)
    else:
        type_names = expected_type.__name__
    raise ValueError(
        f"{field_name} must be {type_names} or JSON string, got {type(value).__name__}"
    )


def _parse_bool_param(value: Any, field_name: str) -> bool:
    """Parse a boolean parameter that may be bool, string, or JSON.

    Args:
        value: The parameter value
        field_name: Name for error messages

    Returns:
        Boolean value.

    Raises:
        ValueError: If value cannot be interpreted as boolean.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.lower().strip()
        if lower in ("true", "1", "yes"):
            return True
        if lower in ("false", "0", "no"):
            return False
        raise ValueError(
            f"{field_name} must be boolean (true/false/yes/no/1/0), got '{value}'"
        )
    raise ValueError(f"{field_name} must be boolean, got {type(value).__name__}")


def _recalc_table_id(doc, t) -> str:
    """Recalculate table element ID after modification. Requires base_kind == 'table'."""
    if t.base_kind != "table":
        raise ValueError("Expected base_kind=table for table ID recalculation")
    tbl_el = t.base_el  # Use element, not wrapper
    content = word_ops.table_content_for_hash(tbl_el)
    occurrence = word_ops.count_occurrence(doc, "table", content, tbl_el)
    return word_ops.make_block_id("table", content, occurrence)


def _recalc_block_id(doc, t) -> str:
    """Recalculate block element ID after modification. Pure OOXML-based."""
    # Get block type from element (handles headings correctly)
    block_kind, _ = word_ops.paragraph_kind_and_level(t.leaf_el)
    # Get text from element directly (pure OOXML)
    text = word_ops.get_paragraph_text_ooxml(t.leaf_el)
    occurrence = word_ops.count_occurrence(doc, block_kind, text, t.leaf_el)
    return word_ops.make_block_id(block_kind, text, occurrence)


def _apply_operation(pkg: WordPackage, file_path: str, params: dict) -> OpResult:
    """Apply a single operation to an open package. Does NOT save the file.

    Args:
        pkg: Open WordPackage instance
        file_path: Path to the .docx file (for operations that need to read external files)
        params: Operation parameters dict with 'op' and operation-specific fields

    Returns:
        OpResult with success status, element_id, and message/error
    """
    operation = params.get("op", "")
    if not operation:
        raise ValueError("op required")

    target_id = params.get("target_id", "")
    content_type = params.get("content_type", "paragraph")
    content_data = params.get("content_data", "") or params.get("content", "")
    style_name = params.get("style_name", "")
    formatting = params.get("formatting", "")
    heading_level = params.get("heading_level", 1)
    row = params.get("row", 0)
    col = params.get("col", 0)
    run_index = params.get("run_index", -1)
    author = params.get("author", "")
    initials = params.get("initials", "")
    section_index = params.get("section_index", 0)

    # --- Per-operation required parameter validation ---
    # Operations that require target_id
    _TARGET_OPS = {
        "insert_before",
        "insert_after",
        "replace",
        "delete",
        "edit_cell",
        "add_row",
        "add_column",
        "delete_row",
        "delete_column",
        "set_table_alignment",
        "set_table_autofit",
        "set_table_fixed_layout",
        "set_row_height",
        "set_cell_width",
        "set_cell_vertical_alignment",
        "set_cell_borders",
        "set_cell_shading",
        "set_header_row",
        "style",
        "edit_run",
        "set_list_level",
        "promote_list",
        "demote_list",
        "restart_numbering",
        "remove_list",
        "create_list",
        "add_to_list",
        "insert_image",
        "insert_floating_image",
        "delete_image",
        "delete_chart",
        "update_chart_data",
        "insert_chart",
        "add_tab_stop",
        "clear_tab_stops",
        "insert_field",
        "insert_citation",
        "insert_bibliography",
        "accept_change",
        "reject_change",
        "add_break",
        "edit_style",
        "delete_style",
        "add_comment",
        "reply_comment",
        "resolve_comment",
        "unresolve_comment",
        "add_hyperlink",
        "merge_cells",
    }
    if operation in _TARGET_OPS and not target_id:
        raise ValueError(f"target_id required for {operation}")

    # Operations that require content_data
    _CONTENT_OPS = {
        "insert_before",
        "insert_after",
        "replace",
        "set_table_alignment",
        "set_table_autofit",
        "set_table_fixed_layout",
        "set_row_height",
        "set_cell_width",
        "set_cell_vertical_alignment",
        "set_cell_borders",
        "set_cell_shading",
        "set_custom_property",
        "set_property",
        "create_style",
        "insert_image",
        "insert_floating_image",
        "insert_chart",
        "update_chart_data",
        "add_source",
        "delete_source",
        "add_comment",
        "add_hyperlink",
        "insert_citation",
        "merge_cells",
    }
    if operation in _CONTENT_OPS and not content_data:
        raise ValueError(f"content_data required for {operation}")

    # append needs content_data for headings/tables but not for empty paragraphs or page breaks
    _APPEND_CONTENT_OPTIONAL = {"paragraph", "page_break"}
    if (
        operation == "append"
        and not content_data
        and content_type not in _APPEND_CONTENT_OPTIONAL
    ):
        raise ValueError(
            f"content_data required for append with content_type={content_type}"
        )

    element_id = target_id
    message = f"Completed {operation}"
    comment_id = None

    if operation in ("insert_before", "insert_after"):
        t = word_ops.resolve_target(pkg, target_id)
        position = "before" if operation == "insert_before" else "after"
        el = word_ops.insert_content_ooxml(
            pkg,
            t.leaf_el,
            position,
            content_type,
            content_data,
            style_name,
            heading_level,
        )
        # Apply formatting if provided
        fmt = _parse_json_param(formatting, "formatting") or {}
        if fmt:
            from mcp_handley_lab.microsoft.word.constants import qn as _qn

            if el.tag == _qn("w:p"):  # paragraph or heading
                if "style" in fmt:
                    word_ops.set_paragraph_style_ooxml(el, fmt.pop("style"))
                if fmt:  # remaining formatting keys
                    word_ops.apply_paragraph_formatting(el, fmt)
            elif el.tag == _qn("w:tbl"):  # table
                if "style" in fmt:
                    word_ops.set_table_style(el, fmt["style"])
        level = heading_level if content_type == "heading" else 0
        element_id = word_ops.get_element_id_ooxml(pkg, el, level)
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Inserted {content_type} {position} {target_id}"

    elif operation == "append":
        el = word_ops.append_content_ooxml(
            pkg, content_type, content_data, style_name, heading_level
        )
        # Apply formatting if provided
        fmt = _parse_json_param(formatting, "formatting") or {}
        style_override = False
        if fmt:
            from mcp_handley_lab.microsoft.word.constants import qn as _qn

            if el.tag == _qn("w:p"):  # paragraph or heading
                if "style" in fmt:
                    word_ops.set_paragraph_style_ooxml(el, fmt.pop("style"))
                    style_override = True
                if fmt:  # remaining formatting keys
                    word_ops.apply_paragraph_formatting(el, fmt)
            elif el.tag == _qn("w:tbl"):  # table
                if "style" in fmt:
                    word_ops.set_table_style(el, fmt["style"])
        # If style was overridden, use level=0 to let paragraph_kind_and_level
        # determine the block type from the actual style
        level = (
            0 if style_override else (heading_level if content_type == "heading" else 0)
        )
        element_id = word_ops.get_element_id_ooxml(pkg, el, level)
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Appended {content_type} to document"

    elif operation == "edit_style":
        fmt = _parse_json_param(formatting, "formatting") or {}
        word_ops.edit_style(pkg, target_id, fmt)
        message = f"Modified style: {target_id}"

    elif operation == "delete":
        t = word_ops.resolve_target(pkg, target_id)
        t.base_el.getparent().remove(t.base_el)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = ""  # Deleted elements have no ID to chain
        message = f"Deleted block {target_id}"

    elif operation == "replace":
        t = word_ops.resolve_target(pkg, target_id)
        if t.leaf_kind.startswith("heading") or t.leaf_kind == "paragraph":
            word_ops.set_paragraph_text_ooxml(t.leaf_el, content_data)
            element_id = _recalc_block_id(pkg, t)
        elif t.leaf_kind == "table":
            table_data = _parse_json_param(content_data, "content_data", list) or []
            new_tbl_el = word_ops.replace_table(t.leaf_el, table_data)
            table_content = word_ops.table_content_for_hash(new_tbl_el)
            occurrence = word_ops.count_occurrence(
                pkg, "table", table_content, new_tbl_el
            )
            element_id = word_ops.make_block_id("table", table_content, occurrence)
        else:
            raise ValueError(f"Unsupported leaf_kind: {t.leaf_kind}")
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Replaced content of {target_id}"

    elif operation == "edit_cell":
        t = word_ops.resolve_target(pkg, target_id)
        word_ops.replace_table_cell(t.leaf_el, row, col, content_data)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = _recalc_table_id(pkg, t)
        message = f"Updated cell r{row}c{col}"

    elif operation == "add_row":
        t = word_ops.resolve_target(pkg, target_id)
        data = (
            _parse_json_param(content_data, "content_data", list)
            if content_data
            else None
        )
        row_idx = word_ops.add_table_row(t.leaf_el, data)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = _recalc_table_id(pkg, t)
        message = f"Added row {row_idx}"

    elif operation == "add_column":
        t = word_ops.resolve_target(pkg, target_id)
        fmt = _parse_json_param(formatting, "formatting") or {}
        width_inches = float(fmt.get("width", 1.0))
        width_twips = int(width_inches * 1440)  # 1440 twips per inch
        data = (
            _parse_json_param(content_data, "content_data", list)
            if content_data
            else None
        )
        col_idx = word_ops.add_table_column(t.leaf_el, width_twips, data)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = _recalc_table_id(pkg, t)
        message = f"Added column {col_idx}"

    elif operation == "delete_row":
        t = word_ops.resolve_target(pkg, target_id)
        word_ops.delete_table_row(t.leaf_el, row)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = _recalc_table_id(pkg, t)
        message = f"Deleted row {row}"

    elif operation == "delete_column":
        t = word_ops.resolve_target(pkg, target_id)
        word_ops.delete_table_column(t.leaf_el, col)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = _recalc_table_id(pkg, t)
        message = f"Deleted column {col}"

    elif operation == "merge_cells":
        t = word_ops.resolve_target(pkg, target_id)
        if not content_data:
            raise ValueError(
                "merge_cells requires content_data JSON with end_row, end_col"
            )
        merge_data = _parse_json_param(content_data, "content_data")
        if not merge_data:
            raise ValueError(
                "merge_cells content_data must be valid JSON with end_row, end_col"
            )
        start_row = merge_data.get("start_row", merge_data.get("row", row))
        start_col = merge_data.get("start_col", merge_data.get("col", col))
        end_row = merge_data.get("end_row")
        end_col = merge_data.get("end_col")
        if end_row is None or end_col is None:
            raise ValueError("merge_cells requires end_row and end_col in content_data")
        word_ops.merge_cells(t.leaf_el, start_row, start_col, end_row, end_col)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = _recalc_table_id(pkg, t)
        message = (
            f"Merged cells from ({start_row},{start_col}) to ({end_row},{end_col})"
        )

    elif operation == "set_table_alignment":
        t = word_ops.resolve_target(pkg, target_id)
        word_ops.set_table_alignment(t.leaf_el, content_data)
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Set table alignment to {content_data}"

    elif operation == "set_table_autofit":
        t = word_ops.resolve_target(pkg, target_id)
        autofit_value = _parse_bool_param(content_data, "content_data")
        word_ops.set_table_autofit(t.leaf_el, autofit_value)
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Set table autofit to {autofit_value}"

    elif operation == "set_table_fixed_layout":
        t = word_ops.resolve_target(pkg, target_id)
        widths = _parse_json_param(content_data, "content_data", list) or []
        word_ops.set_table_fixed_layout(t.leaf_el, widths)
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Set table fixed layout with {len(widths)} columns"

    elif operation == "set_row_height":
        t = word_ops.resolve_target(pkg, target_id)
        height_data = _parse_json_param(content_data, "content_data") or {}
        word_ops.set_row_height(
            t.leaf_el,
            row,
            height_data["height"],
            height_data.get("rule", "at_least"),
        )
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Set row {row} height to {height_data['height']} inches"

    elif operation == "set_cell_width":
        t = word_ops.resolve_target(pkg, target_id)
        word_ops.set_cell_width(t.leaf_el, row, col, float(content_data))
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Set cell ({row},{col}) width to {content_data} inches"

    elif operation == "set_cell_vertical_alignment":
        t = word_ops.resolve_target(pkg, target_id)
        word_ops.set_cell_vertical_alignment(t.leaf_el, row, col, content_data)
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Set cell ({row},{col}) vertical alignment to {content_data}"

    elif operation == "set_cell_borders":
        t = word_ops.resolve_target(pkg, target_id)
        border_data = _parse_json_param(content_data, "content_data") or {}
        word_ops.set_cell_borders(
            t.leaf_el,
            row,
            col,
            top=border_data.get("top"),
            bottom=border_data.get("bottom"),
            left=border_data.get("left"),
            right=border_data.get("right"),
        )
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Set borders on cell ({row},{col})"

    elif operation == "set_cell_shading":
        t = word_ops.resolve_target(pkg, target_id)
        word_ops.set_cell_shading(t.leaf_el, row, col, content_data)
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Set shading on cell ({row},{col}) to {content_data}"

    elif operation == "set_header_row":
        t = word_ops.resolve_target(pkg, target_id)
        is_header = content_data.lower() in ("true", "1", "yes")
        word_ops.set_header_row(t.leaf_el, row, is_header)
        pkg.mark_xml_dirty("/word/document.xml")
        action = "marked as" if is_header else "unmarked as"
        message = f"Row {row} {action} header row"

    elif operation == "add_page_break":
        body = pkg.body
        p_el = word_ops.add_page_break_ooxml(body)
        pkg.mark_xml_dirty("/word/document.xml")
        text = word_ops.get_paragraph_text_ooxml(p_el)
        occurrence = word_ops.count_occurrence(pkg, "paragraph", text, p_el)
        element_id = word_ops.make_block_id("paragraph", text, occurrence)
        message = "Added page break"

    elif operation == "add_break":
        t = word_ops.resolve_target(pkg, target_id)
        break_type = content_data or "page"
        p_el = word_ops.add_break_after_ooxml(t.leaf_el, break_type)
        pkg.mark_xml_dirty("/word/document.xml")
        text = word_ops.get_paragraph_text_ooxml(p_el)
        occurrence = word_ops.count_occurrence(pkg, "paragraph", text, p_el)
        element_id = word_ops.make_block_id("paragraph", text, occurrence)
        message = f"Added {break_type} break after {target_id}"

    elif operation == "accept_change":
        word_ops.accept_change(pkg, target_id)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = ""  # No element to chain after accepting
        message = f"Accepted change {target_id}"

    elif operation == "reject_change":
        word_ops.reject_change(pkg, target_id)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = ""  # No element to chain after rejecting
        message = f"Rejected change {target_id}"

    elif operation == "accept_all_changes":
        count = word_ops.accept_all_changes(pkg)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = ""
        message = f"Accepted {count} changes"

    elif operation == "reject_all_changes":
        count = word_ops.reject_all_changes(pkg)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = ""
        message = f"Rejected {count} changes"

    elif operation == "set_list_level":
        p_el = word_ops.find_paragraph_by_id(pkg, target_id)
        level = int(content_data) if content_data else 0
        if level < 0 or level > 8:
            raise ValueError("List level must be 0-8")
        word_ops.set_list_level(pkg, p_el, level)
        message = f"Set list level to {level}"

    elif operation == "promote_list":
        p_el = word_ops.find_paragraph_by_id(pkg, target_id)
        word_ops.promote_list_item(pkg, p_el)
        message = "Promoted list item"

    elif operation == "demote_list":
        p_el = word_ops.find_paragraph_by_id(pkg, target_id)
        word_ops.demote_list_item(pkg, p_el)
        message = "Demoted list item"

    elif operation == "restart_numbering":
        p_el = word_ops.find_paragraph_by_id(pkg, target_id)
        start_value = int(content_data) if content_data else 1
        word_ops.restart_numbering(pkg, p_el, start_value)
        message = f"Restarted numbering at {start_value}"

    elif operation == "remove_list":
        p_el = word_ops.find_paragraph_by_id(pkg, target_id)
        word_ops.remove_list_formatting(pkg, p_el)
        message = "Removed list formatting"

    elif operation == "create_list":
        t = word_ops.resolve_target(pkg, target_id)
        from mcp_handley_lab.microsoft.word.constants import qn as _qn

        if t.leaf_el.tag != _qn("w:p"):
            raise ValueError("create_list requires a paragraph target")
        data = _parse_json_param(content_data, "content_data") if content_data else {}
        list_type = data.get("list_type", "bullet")
        level = data.get("level", 0)
        num_id = word_ops.create_list(pkg, t.leaf_el, list_type, level)
        element_id = word_ops.get_element_id_ooxml(pkg, t.leaf_el)
        message = f"Created {list_type} list (numId={num_id})"

    elif operation == "add_to_list":
        t = word_ops.resolve_target(pkg, target_id)
        if t.base_kind not in (
            "paragraph",
            "heading1",
            "heading2",
            "heading3",
            "heading4",
            "heading5",
            "heading6",
            "heading7",
            "heading8",
            "heading9",
        ):
            raise ValueError("add_to_list requires a paragraph target")
        data = _parse_json_param(content_data, "content_data") if content_data else {}
        text = data.get("text", "")
        position = data.get("position", "after")
        level = data.get("level")  # None = inherit
        new_p = word_ops.add_to_list(pkg, t.leaf_el, text, position, level)
        new_id = word_ops.get_element_id_ooxml(pkg, new_p)
        element_id = new_id
        message = f"Added list item {position} target"

    elif operation == "set_custom_property":
        prop_data = _parse_json_param(content_data, "content_data") or {}
        word_ops.set_custom_property(
            pkg,
            name=prop_data["name"],
            value=prop_data["value"],
            prop_type=prop_data.get("type", "string"),
        )
        element_id = ""
        message = f"Set custom property '{prop_data['name']}'"

    elif operation == "delete_custom_property":
        prop_name = content_data
        deleted = word_ops.delete_custom_property(pkg, prop_name)
        element_id = ""
        if deleted:
            message = f"Deleted custom property '{prop_name}'"
        else:
            message = f"Custom property '{prop_name}' not found"

    elif operation == "set_property":
        meta_data = (
            _parse_json_param(content_data, "content_data") if content_data else {}
        )
        word_ops.set_document_meta(
            pkg,
            title=meta_data.get("title"),
            author=meta_data.get("author"),
            subject=meta_data.get("subject"),
            keywords=meta_data.get("keywords"),
            category=meta_data.get("category"),
        )
        element_id = ""
        message = "Updated document metadata"

    elif operation == "edit_run":
        t = word_ops.resolve_target(pkg, target_id)
        if t.leaf_kind not in (
            "paragraph",
            "heading1",
            "heading2",
            "heading3",
            "heading4",
            "heading5",
            "heading6",
            "heading7",
            "heading8",
            "heading9",
        ):
            from mcp_handley_lab.microsoft.word.constants import qn

            if t.leaf_el.tag != qn("w:p"):
                raise ValueError(
                    f"edit_run requires a paragraph target, got {t.leaf_kind}"
                )
        if content_data:
            word_ops.edit_run_text(t.leaf_el, run_index, content_data)
        if formatting:
            fmt = _parse_json_param(formatting, "formatting") or {}
            word_ops.edit_run_formatting(t.leaf_el, run_index, fmt)
        element_id = word_ops.get_element_id_ooxml(pkg, t.leaf_el, 0)
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Updated run {run_index}"

    elif operation == "style":
        t = word_ops.resolve_target(pkg, target_id)
        if style_name:
            word_ops.set_paragraph_style_ooxml(t.leaf_el, style_name)
        if t.base_kind == "table":
            element_id = target_id
        else:
            if formatting:
                fmt = _parse_json_param(formatting, "formatting") or {}
                word_ops.apply_paragraph_formatting(t.leaf_el, fmt)
            element_id = word_ops.get_element_id_ooxml(pkg, t.leaf_el, 0)
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Applied style to {target_id}"

    elif operation == "edit_text_box":
        if not target_id:
            raise ValueError("target_id (text box ID) required for edit_text_box")
        word_ops.edit_text_box_text(pkg, target_id, row, content_data)
        element_id = ""
        message = f"Edited text box {target_id} paragraph {row}"

    elif operation == "set_content_control":
        if not target_id:
            raise ValueError(
                "target_id (content control ID) required for set_content_control"
            )
        if not content_data:
            raise ValueError(
                "content_data (new value) required for set_content_control"
            )
        sdt_id = int(target_id)
        word_ops.set_content_control_value(pkg, sdt_id, content_data)
        element_id = ""
        message = f"Set content control {sdt_id} to '{content_data}'"

    elif operation == "create_content_control":
        if not target_id:
            raise ValueError("target_id required for create_content_control")
        if not content_data:
            raise ValueError(
                "content_data (JSON with type and optional tag/alias/options) "
                "required for create_content_control"
            )
        data = _parse_json_param(content_data, "content_data") or {}
        sdt_type_val = data.get("type", "text")
        t = word_ops.resolve_target(pkg, target_id)
        from mcp_handley_lab.microsoft.word.constants import qn as _qn

        if t.leaf_el.tag != _qn("w:p"):
            raise ValueError("create_content_control requires a paragraph target")
        parent = t.leaf_el.getparent()
        if parent is None or parent.tag not in (_qn("w:body"), _qn("w:tc")):
            raise ValueError(
                "Content controls can only be inserted in block-level contexts "
                "(w:body or w:tc)"
            )
        sdt_el = word_ops.create_content_control(
            pkg,
            None,
            t.leaf_el,
            sdt_type=sdt_type_val,
            tag=data.get("tag"),
            alias=data.get("alias"),
            placeholder=data.get("placeholder", "Click here"),
            position=data.get("position", "after"),
            options=data.get("options"),
            checked=data.get("checked", False),
            date_format=data.get("date_format", "yyyy-MM-dd"),
        )
        # Extract the SDT id for the response (numeric id usable with set_content_control)
        sdt_pr = sdt_el.find(_qn("w:sdtPr"))
        id_el = sdt_pr.find(_qn("w:id")) if sdt_pr is not None else None
        created_id = id_el.get(_qn("w:val")) if id_el is not None else ""
        if not created_id or not created_id.isdigit():
            raise ValueError("Failed to determine created content control id")
        element_id = created_id
        message = f"Created {sdt_type_val} content control (id={created_id})"

    elif operation == "set_margins":
        margins = _parse_json_param(formatting, "formatting") or {}
        if not any(margins.get(k) for k in ("top", "bottom", "left", "right")):
            raise ValueError("set_margins requires at least one margin in formatting")
        word_ops.set_page_margins(
            pkg,
            section_index,
            top=margins.get("top"),
            bottom=margins.get("bottom"),
            left=margins.get("left"),
            right=margins.get("right"),
        )
        element_id = ""
        message = f"Set margins for section {section_index}"

    elif operation == "set_orientation":
        word_ops.set_page_orientation(pkg, section_index, content_data)
        element_id = ""
        message = f"Set orientation to {content_data} for section {section_index}"

    elif operation == "set_columns":
        col_data = _parse_json_param(content_data, "content_data") or {}
        word_ops.set_section_columns(
            pkg,
            section_index,
            int(col_data["num_columns"]),
            float(col_data.get("spacing_inches", 0.5)),
            col_data.get("separator", False),
        )
        element_id = ""
        message = f"Set {col_data['num_columns']} columns for section {section_index}"

    elif operation == "set_line_numbering":
        ln_data = _parse_json_param(content_data, "content_data") or {}
        word_ops.set_line_numbering(
            pkg,
            section_index,
            enabled=ln_data.get("enabled", True),
            restart=ln_data.get("restart", "newPage"),
            start=int(ln_data.get("start", 1)),
            count_by=int(ln_data.get("count_by", 1)),
            distance_inches=float(ln_data.get("distance_inches", 0.5)),
        )
        enabled = ln_data.get("enabled", True)
        action = "Enabled" if enabled else "Disabled"
        element_id = ""
        message = f"{action} line numbering for section {section_index}"

    elif operation == "set_page_borders":
        fmt = _parse_json_param(formatting, "formatting") or {}
        word_ops.set_page_borders(
            pkg,
            section_index,
            top=fmt.get("top"),
            bottom=fmt.get("bottom"),
            left=fmt.get("left"),
            right=fmt.get("right"),
            offset_from=fmt.get("offset_from", "text"),
        )
        sides = [s for s in ["top", "bottom", "left", "right"] if fmt.get(s)]
        element_id = ""
        message = f"Set page borders ({', '.join(sides) or 'none'}) for section {section_index}"

    elif operation == "add_bookmark":
        if not target_id:
            raise ValueError("target_id (paragraph ID) required for add_bookmark")
        if not content_data:
            raise ValueError("content_data (bookmark name) required for add_bookmark")
        target = word_ops.resolve_target(pkg, target_id)
        bm_id = word_ops.add_bookmark(pkg, content_data, target.leaf_el)
        element_id = ""
        message = f"Added bookmark '{content_data}' with ID {bm_id}"

    elif operation == "insert_cross_ref":
        if not target_id:
            raise ValueError("target_id (paragraph ID) required for insert_cross_ref")
        if not content_data:
            raise ValueError(
                "content_data (bookmark name) required for insert_cross_ref"
            )
        target = word_ops.resolve_target(pkg, target_id)
        ref_type = style_name if style_name else "text"
        word_ops.insert_cross_reference(target.leaf_el, content_data, ref_type)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = ""
        message = f"Inserted cross-reference to '{content_data}' ({ref_type})"

    elif operation == "insert_caption":
        if not target_id:
            raise ValueError("target_id (block ID) required for insert_caption")
        # content_data can be JSON object or plain text
        caption_data = (
            _parse_json_param(content_data, "content_data")
            if content_data
            and (isinstance(content_data, dict) or content_data.strip().startswith("{"))
            else None
        )
        if caption_data:
            label = caption_data.get("label", "Figure")
            caption_text = caption_data.get("text", "")
            position = caption_data.get("position", "below")
        else:
            label = "Figure"
            caption_text = content_data if content_data else ""
            position = "below"
        if position not in ("above", "below"):
            raise ValueError(
                f"Invalid position '{position}'. Valid: ['above', 'below']"
            )
        element_id = word_ops.insert_caption(
            pkg, target_id, label, caption_text, position
        )
        message = f"Inserted {label} caption {position} {target_id}"

    elif operation == "insert_toc":
        if not target_id:
            raise ValueError("target_id (block ID) required for insert_toc")
        toc_data = (
            _parse_json_param(content_data, "content_data") if content_data else {}
        )
        position = toc_data.get("position", "before")
        heading_levels = toc_data.get("heading_levels", "1-3")
        element_id = word_ops.insert_toc(pkg, target_id, position, heading_levels)
        message = f"Inserted TOC {position} {target_id}"

    elif operation == "update_toc":
        word_ops.update_toc_field(pkg)
        element_id = ""
        message = "Set TOC dirty flag for update on open"

    elif operation == "add_footnote":
        if not target_id:
            raise ValueError("target_id (paragraph ID) required for add_footnote")
        if not content_data:
            raise ValueError("content_data (JSON with text) required for add_footnote")
        fn_data = _parse_json_param(content_data, "content_data") or {}
        fn_text = fn_data.get("text", "")
        note_type = fn_data.get("note_type", "footnote")
        position = fn_data.get("position", "after")
        fn_id = word_ops.add_footnote_ooxml(
            pkg, target_id, fn_text, note_type, position
        )
        element_id = ""
        message = f"Added {note_type} {fn_id}"

    elif operation == "delete_footnote":
        if not target_id:
            raise ValueError("target_id (note ID) required for delete_footnote")
        note_id = int(target_id)
        note_type = content_data.strip() if content_data else "footnote"
        word_ops.delete_footnote_ooxml(pkg, note_id, note_type)
        element_id = ""
        message = f"Deleted {note_type} {note_id}"

    elif operation == "add_section":
        start_type = content_data.strip().lower() if content_data else "new_page"
        new_idx = word_ops.add_section(pkg, start_type)
        element_id = ""
        message = f"Added section {new_idx} ({start_type})"

    elif operation == "add_comment":
        if not target_id:
            raise ValueError("target_id (paragraph ID) required for add_comment")
        target = word_ops.resolve_target(pkg, target_id)
        from mcp_handley_lab.microsoft.word.constants import qn as _qn

        if target.leaf_el.tag != _qn("w:p"):
            raise ValueError(
                f"Cannot add comment to {target.leaf_kind}. "
                "Comments can only be added to paragraphs."
            )
        comment_id = word_ops.add_comment_to_block(
            pkg, target.leaf_el, content_data, author, initials
        )
        message = f"Added comment {comment_id} to {target_id}"

    elif operation == "reply_comment":
        parent_id = int(target_id)
        comment_id = word_ops.reply_to_comment(
            pkg, parent_id, content_data, author, initials
        )
        message = f"Added reply {comment_id} to comment {parent_id}"

    elif operation == "resolve_comment":
        cid = int(target_id)
        word_ops.resolve_comment(pkg, cid)
        element_id = ""
        message = f"Resolved comment {cid}"

    elif operation == "unresolve_comment":
        cid = int(target_id)
        word_ops.unresolve_comment(pkg, cid)
        element_id = ""
        message = f"Unresolved comment {cid}"

    elif operation == "add_hyperlink":
        if not target_id:
            raise ValueError("target_id required for add_hyperlink")
        if not content_data:
            raise ValueError("content_data (JSON with text, address/fragment) required")
        link_data = _parse_json_param(content_data, "content_data")
        if not link_data:
            raise ValueError(
                "content_data must be valid JSON: {text, address?, fragment?}"
            )
        text = link_data.get("text", "")
        address = link_data.get("address", "")
        fragment = link_data.get("fragment", "")
        target = word_ops.resolve_target(pkg, target_id)
        from mcp_handley_lab.microsoft.word.constants import qn as _qn

        if target.leaf_kind == "cell":
            p_el = target.leaf_el.find(_qn("w:p"))
            if p_el is None:
                raise ValueError("Cell has no paragraph to add hyperlink to")
        elif target.leaf_el.tag == _qn("w:p"):
            p_el = target.leaf_el
        else:
            raise ValueError(
                f"Cannot add hyperlink to {target.leaf_kind}. "
                "Hyperlinks can only be added to paragraphs or table cells."
            )
        replace = link_data.get("replace", False)
        word_ops.add_hyperlink(pkg, p_el, text, address, fragment, replace)
        if target.leaf_kind == "cell":
            element_id = word_ops.get_element_id_ooxml(pkg, target.base_el)
        else:
            element_id = word_ops.get_element_id_ooxml(pkg, p_el)
        message = f"Added hyperlink '{text}' to {address or '#' + fragment}"

    elif operation in _HF_SET_OPS:
        location = _HF_SET_OPS[operation]
        word_ops.set_header_footer_text(pkg, section_index, content_data, location)
        element_id = ""
        message = f"Set {location.replace('_', ' ')} for section {section_index}"

    elif operation in _HF_APPEND_OPS:
        location = _HF_APPEND_OPS[operation]
        element_id = word_ops.append_to_header_footer(
            pkg, section_index, content_type, content_data, location
        )
        message = f"Appended {content_type} to {location} for section {section_index}"

    elif operation in _HF_CLEAR_OPS:
        location = _HF_CLEAR_OPS[operation]
        word_ops.clear_header_footer(pkg, section_index, location)
        element_id = ""
        message = f"Cleared {location} for section {section_index}"

    elif operation == "insert_page_x_of_y":
        location = content_data.strip().lower() or "footer"
        word_ops.insert_page_x_of_y(pkg, section_index, location)
        element_id = ""
        message = f"Inserted 'Page X of Y' in {location} of section {section_index}"

    elif operation == "create_style":
        style_data = _parse_json_param(content_data, "content_data") or {}
        formatting_dict = _parse_json_param(formatting, "formatting")
        style_id = word_ops.create_style(
            pkg,
            name=style_data["name"],
            style_type=style_data.get("style_type", "paragraph"),
            base_style=style_data.get("base_style", "Normal"),
            formatting=formatting_dict,
        )
        element_id = style_id
        message = f"Created style '{style_data['name']}'"

    elif operation == "delete_style":
        deleted = word_ops.delete_style(pkg, target_id)
        element_id = ""
        if deleted:
            message = f"Deleted style '{target_id}'"
        else:
            message = f"Style '{target_id}' not found or is builtin"

    elif operation == "insert_image":
        fmt = _parse_json_param(formatting, "formatting") or {}
        element_id = word_ops.insert_image(
            pkg,
            content_data,
            target_id,
            "after",
            width_inches=float(fmt.get("width", 0)),
            height_inches=float(fmt.get("height", 0)),
        )
        message = "Inserted image"

    elif operation == "delete_image":
        word_ops.delete_image(pkg, target_id)
        element_id = ""
        message = f"Deleted {target_id}"

    elif operation == "insert_floating_image":
        fmt = _parse_json_param(formatting, "formatting") or {}
        element_id = word_ops.insert_floating_image(
            pkg,
            content_data,
            target_id,
            position_h=float(fmt.get("position_h", 0)),
            position_v=float(fmt.get("position_v", 0)),
            relative_h=fmt.get("relative_h", "column"),
            relative_v=fmt.get("relative_v", "paragraph"),
            wrap_type=fmt.get("wrap_type", "square"),
            width_inches=float(fmt.get("width", 0)),
            height_inches=float(fmt.get("height", 0)),
            behind_doc=bool(fmt.get("behind_doc", False)),
        )
        message = "Inserted floating image"

    elif operation == "add_tab_stop":
        t = word_ops.resolve_target(pkg, target_id)
        tab_data = _parse_json_param(content_data, "content_data") or {}
        word_ops.add_tab_stop(
            t.leaf_el,
            float(tab_data["position"]),
            tab_data.get("alignment", "left"),
            tab_data.get("leader", "spaces"),
        )
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Added tab stop at {tab_data['position']} inches ({tab_data.get('alignment', 'left')}, {tab_data.get('leader', 'spaces')})"

    elif operation == "clear_tab_stops":
        t = word_ops.resolve_target(pkg, target_id)
        word_ops.clear_tab_stops(t.leaf_el)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = ""
        message = "Cleared all tab stops"

    elif operation == "insert_field":
        t = word_ops.resolve_target(pkg, target_id)
        field_code = content_data.strip().upper()
        word_ops.insert_field(t.leaf_el, field_code)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = ""
        message = f"Inserted {field_code} field"

    elif operation == "add_source":
        data = _parse_json_param(content_data, "content_data") or {}
        tag = word_ops.add_source(
            pkg,
            tag=data["tag"],
            source_type=data["source_type"],
            title=data["title"],
            authors=data.get("authors"),
            year=data.get("year"),
            publisher=data.get("publisher"),
            city=data.get("city"),
            journal_name=data.get("journal_name"),
            volume=data.get("volume"),
            issue=data.get("issue"),
            pages=data.get("pages"),
            url=data.get("url"),
        )
        element_id = ""
        message = f"Added bibliography source: {tag}"

    elif operation == "delete_source":
        tag = content_data.strip()
        if word_ops.delete_source(pkg, tag):
            element_id = ""
            message = f"Deleted bibliography source: {tag}"
        else:
            element_id = ""
            message = f"Source not found: {tag}"

    elif operation == "insert_citation":
        t = word_ops.resolve_target(pkg, target_id)
        data = _parse_json_param(content_data, "content_data") if content_data else {}
        tag = data.get("tag", "")
        display_text = data.get("display_text", "")
        locale = int(data.get("locale", 1033))
        word_ops.insert_citation(t.leaf_el, tag, display_text, locale)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = ""
        message = f"Inserted citation: {tag}"

    elif operation == "insert_bibliography":
        t = word_ops.resolve_target(pkg, target_id)
        word_ops.insert_bibliography(t.leaf_el)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = ""
        message = "Inserted bibliography field"

    elif operation == "insert_chart":
        chart_data = _parse_json_param(content_data, "content_data") or {}
        fmt = _parse_json_param(formatting, "formatting") or {}
        chart_id = word_ops.create_chart_op(
            pkg,
            target_id,
            chart_type=chart_data.get("chart_type", "column"),
            data=chart_data["data"],
            title=chart_data.get("title"),
            width_inches=float(fmt.get("width", 5.0)),
            height_inches=float(fmt.get("height", 3.0)),
        )
        element_id = chart_id
        message = f"Inserted {chart_data.get('chart_type', 'column')} chart"

    elif operation == "delete_chart":
        word_ops.delete_chart_op(pkg, target_id)
        element_id = ""
        message = f"Deleted chart {target_id}"

    elif operation == "update_chart_data":
        chart_data = _parse_json_param(content_data, "content_data") or {}
        word_ops.update_chart_data_op(pkg, target_id, chart_data["data"])
        element_id = target_id
        message = f"Updated chart data for {target_id}"

    elif operation == "find_replace":
        search = content_data
        replace_text = params.get("replace", "")
        match_case = params.get("match_case", True)  # Default to case-sensitive
        if not search:
            raise ValueError("content_data (search text) required for find_replace")
        count = word_ops.find_replace(pkg, search, replace_text, match_case=match_case)
        element_id = ""
        message = f"Replaced {count} occurrences of '{search}'"

    elif operation == "mail_merge":
        replacements = _parse_json_param(content_data, "content_data") or {}
        if not replacements:
            raise ValueError(
                "content_data (JSON dict of placeholder:value) required for mail_merge"
            )
        count = word_ops.mail_merge(pkg, replacements)
        element_id = ""
        message = f"Replaced {count} placeholders"

    else:
        raise ValueError(f"Unknown operation: {operation}")

    return OpResult(
        success=True,
        element_id=element_id,
        comment_id=comment_id,
        message=message,
    )


def read(
    file_path: str,
    scope: str = "outline",
    target_id: str = "",
    search_query: str = "",
    limit: int = 50,
    offset: int = 0,
) -> DocumentReadResult:
    """Read Word document content.

    Args:
        file_path: Path to .docx file.
        scope: What to read. Options:
            - 'meta': Document info
            - 'outline': Headings only
            - 'blocks': All content
            - 'search': Find text
            - 'table_cells': Cells of a table
            - 'table_layout': Table alignment/autofit/row heights
            - 'runs': Text runs in a paragraph
            - 'comments': All comments
            - 'headers_footers': Headers/footers per section
            - 'page_setup': Margins, orientation per section
            - 'images': Embedded inline images
            - 'hyperlinks': All hyperlinks with URLs
            - 'styles': All document styles
            - 'style': Detailed formatting for a specific style
            - 'revisions': Tracked changes/revisions
            - 'list': List properties for a paragraph
            - 'text_boxes': All text boxes/floating content
            - 'text_box_content': Paragraphs inside a text box
            - 'bookmarks': All bookmarks
            - 'captions': All captions
            - 'toc': Table of contents info
            - 'footnotes': All footnotes and endnotes
            - 'content_controls': All content controls/SDTs
            - 'equations': Math equations with simplified text
            - 'bibliography': Bibliography sources
            - 'theme': Theme color scheme (base colors only)
        target_id: Block ID for table_cells/runs/table_layout/list scopes,
            style name for 'style' scope, or text box ID for 'text_box_content' scope.
        search_query: Text to search for (scope='search').
        limit: Max blocks to return.
        offset: Pagination offset.

    Returns:
        DocumentReadResult with requested content.
    """
    from mcp_handley_lab.microsoft.word.constants import qn

    pkg = WordPackage.open(file_path)

    if scope == "meta":
        meta = word_ops.get_document_meta(pkg)
        _, block_count = word_ops.build_blocks(pkg, offset=0, limit=0)
        return DocumentReadResult(block_count=block_count, meta=meta)
    if scope == "outline":
        blocks, block_count = word_ops.build_blocks(
            pkg, offset=offset, limit=limit, heading_only=True
        )
        return DocumentReadResult(block_count=block_count, blocks=blocks)
    if scope == "blocks":
        blocks, block_count = word_ops.build_blocks(pkg, offset=offset, limit=limit)
        return DocumentReadResult(block_count=block_count, blocks=blocks)
    if scope == "search":
        blocks, block_count = word_ops.build_blocks(
            pkg, offset=offset, limit=limit, search_query=search_query
        )
        return DocumentReadResult(block_count=block_count, blocks=blocks)
    if scope == "table_cells":
        t = word_ops.resolve_target(pkg, target_id)
        tbl_el = t.leaf_el
        cells = word_ops.build_table_cells(tbl_el, target_id)
        rows = tbl_el.findall(qn("w:tr"))
        max_cols = max((len(tr.findall(qn("w:tc"))) for tr in rows), default=0)
        return DocumentReadResult(
            block_count=len(cells),
            cells=cells,
            table_rows=len(rows),
            table_cols=max_cols,
        )
    if scope == "table_layout":
        t = word_ops.resolve_target(pkg, target_id)
        tbl_el = t.leaf_el
        table_layout = word_ops.build_table_layout(tbl_el, target_id)
        return DocumentReadResult(block_count=1, table_layout=table_layout)
    if scope == "runs":
        t = word_ops.resolve_target(pkg, target_id)
        if t.leaf_kind != "paragraph":
            raise ValueError(
                f"Target is not a paragraph: {target_id} (resolved to {t.leaf_kind})"
            )
        p_el = t.leaf_el
        doc_rels = pkg.get_rels("/word/document.xml")
        runs = word_ops.build_runs(p_el, doc_rels)
        paragraph_format = word_ops.build_paragraph_format(p_el)
        return DocumentReadResult(
            block_count=len(runs), runs=runs, paragraph_format=paragraph_format
        )
    if scope == "comments":
        comments_data = word_ops.build_comments_with_threading(pkg)
        comments = [CommentInfo(**c) for c in comments_data]
        return DocumentReadResult(block_count=len(comments), comments=comments)
    if scope == "headers_footers":
        headers_footers = word_ops.build_headers_footers(pkg)
        return DocumentReadResult(
            block_count=len(headers_footers), headers_footers=headers_footers
        )
    if scope == "page_setup":
        page_setup = word_ops.build_page_setup(pkg)
        return DocumentReadResult(block_count=len(page_setup), page_setup=page_setup)
    if scope == "images":
        images = word_ops.build_images(pkg)
        return DocumentReadResult(block_count=len(images), images=images)
    if scope == "hyperlinks":
        hyperlinks = word_ops.build_hyperlinks(pkg)
        return DocumentReadResult(block_count=len(hyperlinks), hyperlinks=hyperlinks)
    if scope == "styles":
        styles = word_ops.build_styles(pkg)
        return DocumentReadResult(block_count=len(styles), styles=styles)
    if scope == "style":
        style_format = word_ops.get_style_format(pkg, target_id)
        return DocumentReadResult(block_count=1, style_format=style_format)
    if scope == "revisions":
        has_changes = word_ops.has_tracked_changes(pkg)
        revisions = (
            [RevisionInfo(**r) for r in word_ops.read_tracked_changes(pkg)]
            if has_changes
            else []
        )
        return DocumentReadResult(
            block_count=len(revisions),
            has_tracked_changes=has_changes,
            revisions=revisions,
        )
    if scope == "list":
        if not target_id:
            raise ValueError("target_id required for list scope")
        p_el = word_ops.find_paragraph_by_id(pkg, target_id)
        list_info_dict = word_ops.get_list_info(pkg, p_el)
        list_info = ListInfo(**list_info_dict) if list_info_dict else None
        return DocumentReadResult(
            block_count=1 if list_info else 0, list_info=list_info
        )
    if scope == "text_boxes":
        text_boxes_data = word_ops.build_text_boxes(pkg)
        text_boxes = [TextBoxInfo(**tb) for tb in text_boxes_data]
        return DocumentReadResult(block_count=len(text_boxes), text_boxes=text_boxes)
    if scope == "text_box_content":
        if not target_id:
            raise ValueError("target_id required for text_box_content scope")
        paragraphs = word_ops.read_text_box_content(pkg, target_id)
        blocks = [
            Block(id=p["id"], type="paragraph", text=p["text"], style="Normal")
            for p in paragraphs
        ]
        return DocumentReadResult(block_count=len(blocks), blocks=blocks)
    if scope == "bookmarks":
        bookmarks_data = word_ops.build_bookmarks(pkg)
        bookmarks = [BookmarkInfo(**bm) for bm in bookmarks_data]
        return DocumentReadResult(block_count=len(bookmarks), bookmarks=bookmarks)
    if scope == "captions":
        captions_data = word_ops.build_captions(pkg)
        captions = [CaptionInfo(**c) for c in captions_data]
        return DocumentReadResult(block_count=len(captions), captions=captions)
    if scope == "toc":
        toc_data = word_ops.get_toc_info(pkg)
        toc_info = TOCInfo(**toc_data)
        return DocumentReadResult(
            block_count=1 if toc_info.exists else 0, toc_info=toc_info
        )
    if scope == "footnotes":
        footnotes_data = word_ops.build_footnotes(pkg)
        footnotes = [FootnoteInfo(**fn) for fn in footnotes_data]
        return DocumentReadResult(block_count=len(footnotes), footnotes=footnotes)
    if scope == "content_controls":
        cc_data = word_ops.build_content_controls(pkg)
        controls = [ContentControlInfo(**cc) for cc in cc_data]
        return DocumentReadResult(block_count=len(controls), content_controls=controls)
    if scope == "equations":
        eq_data = word_ops.build_equations(pkg)
        equations = [EquationInfo(**eq) for eq in eq_data]
        return DocumentReadResult(block_count=len(equations), equations=equations)
    if scope == "bibliography":
        sources = word_ops.build_sources(pkg)
        bib_sources = [
            BibSourceInfo(
                tag=s["tag"],
                source_type=s["source_type"],
                title=s["title"],
                authors=[BibAuthor(**a) for a in s.get("authors", [])],
                year=s.get("year"),
                publisher=s.get("publisher"),
                city=s.get("city"),
                journal_name=s.get("journal_name"),
                volume=s.get("volume"),
                issue=s.get("issue"),
                pages=s.get("pages"),
                url=s.get("url"),
            )
            for s in sources
        ]
        return DocumentReadResult(
            block_count=len(bib_sources), bibliography_sources=bib_sources
        )
    if scope == "charts":
        charts = word_ops.list_charts_op(pkg)
        return DocumentReadResult(block_count=len(charts), charts=charts)
    if scope == "theme":
        from mcp_handley_lab.microsoft.common.colors import (
            get_theme_colors_from_package,
        )
        from mcp_handley_lab.microsoft.opc.constants import RT as OPC_RT

        colors = get_theme_colors_from_package(pkg, "/word/document.xml", OPC_RT.THEME)
        theme_colors = ThemeColors(**colors) if colors else None
        return DocumentReadResult(
            block_count=1 if theme_colors else 0, theme_colors=theme_colors
        )
    raise ValueError(f"Unknown scope: {scope}")


def render(
    file_path: str,
    pages: list[int] | None = None,
    dpi: int = 150,
    output: str = "png",
) -> list[Any]:
    """Render Word document for visual inspection or sharing.

    Args:
        file_path: Path to .docx file.
        pages: Page numbers to render (1-based). Required for PNG output. Max 5 pages.
        dpi: Resolution for PNG (default 150, max 300).
        output: Output format: 'png' (images) or 'pdf' (full document).

    Returns:
        List of TextContent and Image objects.
    """
    if output == "pdf":
        pdf_bytes = word_ops.render_to_pdf(file_path)
        return [
            TextContent(type="text", text=f"PDF ({len(pdf_bytes):,} bytes)"),
            Image(data=pdf_bytes, format="pdf"),
        ]
    # PNG output (default)
    if not pages:
        raise ValueError("pages is required for PNG output")
    result = []
    for page_num, png_bytes in word_ops.render_to_images(file_path, pages, dpi):
        result.append(TextContent(type="text", text=f"Page {page_num}:"))
        result.append(Image(data=png_bytes, format="png"))
    return result


# Pattern for $prev[N] references
_PREV_REF_PATTERN = re.compile(r"^\$prev\[(\d+)\]$")


def edit(
    file_path: str,
    ops: str,
    mode: str = "atomic",
) -> EditResult:
    """Edit Word document with batch operations. Creates a new file if file_path doesn't exist.

    Args:
        file_path: Path to .docx file (created if it doesn't exist).
        ops: JSON array of operation objects. Each object must have an "op" field.
            Use $prev[N] in target_id to reference element_id from operation N (0-indexed).
        mode: Batch mode: 'atomic' (all-or-nothing, file unchanged on any failure)
            or 'partial' (save successful ops before failure).

    Available operations:
        - append_paragraph, append_heading, insert_paragraph, insert_heading
        - append_table, insert_table_relative, populate_table
        - set_text, set_style, edit_run_text, edit_run_formatting
        - add_hyperlink, add_tab_stop, clear_tab_stops
        - add_bookmark, insert_caption, insert_cross_reference
        - add_footnote, delete_footnote, insert_citation, insert_bibliography
        - add_section, set_page_margins, set_page_orientation, set_page_size
        - set_line_numbering, set_page_borders, set_section_columns
        - create_list, add_to_list, set_list_level, restart_numbering
        - promote_list_item, demote_list_item, remove_list_formatting
        - add_table_row, add_table_column, delete_table_row, delete_table_column
        - set_table_cell, merge_table_cells, set_header_row
        - set_cell_borders, set_cell_shading, set_cell_width, set_row_height
        - insert_image, insert_floating_image, delete_image, edit_text_box
        - add_source, delete_source, insert_toc
        - accept_change, reject_change, accept_all_changes, reject_all_changes
        - add_comment, reply_comment, resolve_comment, unresolve_comment
        - create_content_control, set_content_control_value
        - set_property, set_custom_property, delete_custom_property
        - find_replace (text search/replace in document)
        - mail_merge (replace {{placeholder}} patterns with values)

    Returns:
        EditResult with batch fields (total, succeeded, failed, results, saved).
    """
    # Parse ops JSON
    try:
        operations = json.loads(ops)
    except json.JSONDecodeError as e:
        return EditResult(
            success=False,
            message="Invalid JSON in ops parameter",
            error=f"JSON parse error: {e}",
            total=0,
            succeeded=0,
            failed=0,
            results=[],
            saved=False,
        )

    if not isinstance(operations, list):
        return EditResult(
            success=False,
            message="ops must be a JSON array",
            error="Expected array, got " + type(operations).__name__,
            total=0,
            succeeded=0,
            failed=0,
            results=[],
            saved=False,
        )

    for i, op_obj in enumerate(operations):
        if not isinstance(op_obj, dict):
            return EditResult(
                success=False,
                message=f"ops[{i}] is not an object",
                error=f"Expected object at index {i}, got {type(op_obj).__name__}",
                total=0,
                succeeded=0,
                failed=0,
                results=[],
                saved=False,
            )

    if len(operations) == 0:
        return EditResult(
            success=True,
            message="No operations to execute",
            total=0,
            succeeded=0,
            failed=0,
            results=[],
            saved=False,
        )

    if len(operations) > 500:
        return EditResult(
            success=False,
            message=f"Too many operations: {len(operations)} (max 500)",
            error="Operation count exceeds limit of 500",
            total=len(operations),
            succeeded=0,
            failed=0,
            results=[],
            saved=False,
        )

    for i, op_obj in enumerate(operations):
        if "op" not in op_obj:
            return EditResult(
                success=False,
                message=f"ops[{i}] missing 'op' field",
                error=f"Operation at index {i} has no 'op' field",
                total=len(operations),
                succeeded=0,
                failed=0,
                results=[],
                saved=False,
            )
    try:
        if os.path.exists(file_path):
            pkg = WordPackage.open(file_path)
        else:
            from mcp_handley_lab.microsoft.word.constants import qn

            pkg = WordPackage.new()
            # Strip default empty paragraphs so ops start with a clean body
            for p in list(pkg.body.findall(qn("w:p"))):
                pkg.body.remove(p)
    except Exception as e:
        return EditResult(
            success=False,
            message="Failed to open document",
            error=str(e),
            total=len(operations),
            succeeded=0,
            failed=0,
            results=[],
            saved=False,
        )

    results: list[OpResult] = []
    element_ids: list[str] = []
    succeeded = 0
    failed = 0
    last_element_id = ""
    last_comment_id = None

    for i, op_obj in enumerate(operations):
        op_name = op_obj.get("op", "")

        target_id = op_obj.get("target_id", "")
        if target_id:
            match = _PREV_REF_PATTERN.match(target_id)
            if match:
                ref_idx = int(match.group(1))
                if ref_idx >= i:
                    result = OpResult(
                        index=i,
                        op=op_name,
                        success=False,
                        element_id="",
                        error=f"Invalid $prev reference: $prev[{ref_idx}] references index >= current ({i})",
                    )
                    results.append(result)
                    element_ids.append("")
                    failed += 1
                    break
                resolved_id = element_ids[ref_idx]
                if not resolved_id:
                    result = OpResult(
                        index=i,
                        op=op_name,
                        success=False,
                        element_id="",
                        error=f"Invalid $prev reference: $prev[{ref_idx}] has empty element_id",
                    )
                    results.append(result)
                    element_ids.append("")
                    failed += 1
                    break
                op_obj = dict(op_obj)
                op_obj["target_id"] = resolved_id

        try:
            op_result = _apply_operation(pkg, file_path, op_obj)
            op_result.index = i
            op_result.op = op_name
            results.append(op_result)
            element_ids.append(op_result.element_id)

            if op_result.success:
                succeeded += 1
                last_element_id = op_result.element_id
                if op_result.comment_id is not None:
                    last_comment_id = op_result.comment_id
            else:
                failed += 1
                break

        except Exception as e:
            result = OpResult(
                index=i,
                op=op_name,
                success=False,
                element_id="",
                error=str(e),
            )
            results.append(result)
            element_ids.append("")
            failed += 1
            break

    saved = False
    if mode == "atomic":
        if failed == 0 and succeeded > 0:
            try:
                pkg.save(file_path)
                saved = True
            except Exception as e:
                return EditResult(
                    success=False,
                    element_id=last_element_id,
                    comment_id=last_comment_id,
                    message="All operations succeeded but save failed",
                    error=f"Save failed: {e}",
                    total=len(operations),
                    succeeded=succeeded,
                    failed=1,
                    results=results,
                    saved=False,
                )
    else:
        if succeeded > 0:
            try:
                pkg.save(file_path)
                saved = True
            except Exception as e:
                return EditResult(
                    success=False,
                    element_id=last_element_id,
                    comment_id=last_comment_id,
                    message=f"{succeeded} ops succeeded but save failed",
                    error=f"Save failed: {e}",
                    total=len(operations),
                    succeeded=succeeded,
                    failed=failed,
                    results=results,
                    saved=False,
                )

    all_success = failed == 0 and succeeded == len(operations)
    if all_success:
        message = f"Completed {succeeded} operation(s)"
    elif succeeded > 0 and failed > 0:
        message = f"{succeeded} succeeded, {failed} failed"
    elif failed > 0:
        message = f"Failed at operation {len(results) - 1}"
    else:
        message = "No operations executed"

    return EditResult(
        success=all_success,
        element_id=last_element_id,
        comment_id=last_comment_id,
        message=message,
        total=len(operations),
        succeeded=succeeded,
        failed=failed,
        results=results,
        saved=saved,
    )
