"""Word document MCP tool - read and edit operations."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.microsoft.word import document as word_ops

if TYPE_CHECKING:
    pass
from mcp_handley_lab.microsoft.word.models import (
    DocumentReadResult,
    EditResult,
    OpResult,
)
from mcp_handley_lab.microsoft.word.package import WordPackage

mcp = FastMCP("Word Document Tool")


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
    target_id = params.get("target_id", "")
    content_type = params.get("content_type", "paragraph")
    content_data = params.get("content_data", "")
    style_name = params.get("style_name", "")
    formatting = params.get("formatting", "")
    heading_level = params.get("heading_level", 1)
    row = params.get("row", 0)
    col = params.get("col", 0)
    run_index = params.get("run_index", -1)
    author = params.get("author", "")
    initials = params.get("initials", "")
    section_index = params.get("section_index", 0)

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
        level = heading_level if content_type == "heading" else 0
        element_id = word_ops.get_element_id_ooxml(pkg, el, level)
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Inserted {content_type} {position} {target_id}"

    elif operation == "append":
        el = word_ops.append_content_ooxml(
            pkg, content_type, content_data, style_name, heading_level
        )
        level = heading_level if content_type == "heading" else 0
        element_id = word_ops.get_element_id_ooxml(pkg, el, level)
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Appended {content_type} to document"

    elif operation == "edit_style":
        fmt = json.loads(formatting)
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
            table_data = json.loads(content_data)
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
        data = json.loads(content_data) if content_data else None
        row_idx = word_ops.add_table_row(t.leaf_el, data)
        pkg.mark_xml_dirty("/word/document.xml")
        element_id = _recalc_table_id(pkg, t)
        message = f"Added row {row_idx}"

    elif operation == "add_column":
        t = word_ops.resolve_target(pkg, target_id)
        fmt = json.loads(formatting) if formatting else {}
        width_inches = float(fmt.get("width", 1.0))
        width_twips = int(width_inches * 1440)  # 1440 twips per inch
        data = json.loads(content_data) if content_data else None
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
        try:
            merge_data = json.loads(content_data)
        except json.JSONDecodeError:
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
        autofit_value = json.loads(content_data.lower())
        word_ops.set_table_autofit(t.leaf_el, autofit_value)
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Set table autofit to {autofit_value}"

    elif operation == "set_table_fixed_layout":
        t = word_ops.resolve_target(pkg, target_id)
        widths = json.loads(content_data)
        word_ops.set_table_fixed_layout(t.leaf_el, widths)
        pkg.mark_xml_dirty("/word/document.xml")
        message = f"Set table fixed layout with {len(widths)} columns"

    elif operation == "set_row_height":
        t = word_ops.resolve_target(pkg, target_id)
        height_data = json.loads(content_data)
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
        border_data = json.loads(content_data)
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
        data = json.loads(content_data) if content_data else {}
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
        data = json.loads(content_data) if content_data else {}
        text = data.get("text", "")
        position = data.get("position", "after")
        level = data.get("level")  # None = inherit
        new_p = word_ops.add_to_list(pkg, t.leaf_el, text, position, level)
        new_id = word_ops.get_element_id_ooxml(pkg, new_p)
        element_id = new_id
        message = f"Added list item {position} target"

    elif operation == "set_custom_property":
        prop_data = json.loads(content_data)
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

    elif operation == "set_meta":
        meta_data = json.loads(content_data) if content_data else {}
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
            fmt = json.loads(formatting)
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
                fmt = json.loads(formatting)
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
        data = json.loads(content_data)
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
        margins = json.loads(formatting)
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
        col_data = json.loads(content_data)
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
        ln_data = json.loads(content_data)
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
        fmt = json.loads(formatting) if formatting else {}
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
        if content_data and content_data.strip().startswith("{"):
            caption_data = json.loads(content_data)
            if not isinstance(caption_data, dict):
                raise ValueError("content_data must be a JSON object or plain text")
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
        toc_data = json.loads(content_data) if content_data else {}
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
        fn_data = json.loads(content_data)
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
        try:
            link_data = json.loads(content_data)
        except json.JSONDecodeError:
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
        style_data = json.loads(content_data)
        formatting_dict = json.loads(formatting) if formatting else None
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
        fmt = json.loads(formatting) if formatting else {}
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
        fmt = json.loads(formatting) if formatting else {}
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
        tab_data = json.loads(content_data)
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
        data = json.loads(content_data)
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
        data = json.loads(content_data) if content_data else {}
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
        chart_data = json.loads(content_data)
        fmt = json.loads(formatting) if formatting else {}
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
        chart_data = json.loads(content_data)
        word_ops.update_chart_data_op(pkg, target_id, chart_data["data"])
        element_id = target_id
        message = f"Updated chart data for {target_id}"

    else:
        raise ValueError(f"Unknown operation: {operation}")

    return OpResult(
        success=True,
        element_id=element_id,
        comment_id=comment_id,
        message=message,
    )


@mcp.tool(
    description="Read Word document content. Scopes: 'meta' (doc info), 'outline' (headings only), 'blocks' (all content), 'search' (find text), 'table_cells' (cells of a table), 'table_layout' (table alignment/autofit/row heights), 'runs' (text runs in a paragraph), 'comments' (all comments), 'headers_footers' (headers/footers per section), 'page_setup' (margins, orientation per section), 'images' (embedded inline images), 'hyperlinks' (all hyperlinks with URLs), 'styles' (all document styles), 'style' (detailed formatting for a specific style by name in target_id), 'revisions' (tracked changes/revisions), 'list' (list properties for a paragraph by target_id), 'text_boxes' (all text boxes/floating content), 'text_box_content' (paragraphs inside a text box by target_id), 'bookmarks' (all bookmarks), 'captions' (all captions), 'toc' (table of contents info), 'footnotes' (all footnotes and endnotes), 'content_controls' (all content controls/SDTs), 'equations' (math equations with simplified text), 'bibliography' (bibliography sources), 'charts' (embedded charts). Block IDs are content-addressed (type_hash_occurrence) and CHANGE when content changes or after inserts/deletes shift occurrence index - use element_id from edit response for chaining."
)
def read(
    file_path: str = Field(..., description="Path to .docx file"),
    scope: str = Field(
        "outline",
        description="What to read: 'meta', 'outline', 'blocks', 'search', 'table_cells', 'table_layout', 'runs', 'comments', 'headers_footers', 'page_setup', 'images', 'hyperlinks', 'styles', 'style', 'revisions', 'list', 'text_boxes', 'text_box_content', 'bookmarks', 'captions', 'toc', 'footnotes', 'content_controls', 'equations', 'bibliography', 'charts'",
    ),
    target_id: str = Field(
        "",
        description="Block ID for table_cells/runs/table_layout/list scopes, style name for 'style' scope, or text box ID for 'text_box_content' scope. For nested tables use hierarchical paths: 'table_abc_0#r0c1/tbl0' (nested table 0 inside cell row=0,col=1). Path segments: #rXcY (cell), /tblN (Nth descendant table in document order), /pN (paragraph). Deep nesting: 'table_abc_0#r0c0/tbl0/r0c0/tbl0'. Note: /tblN indexes ALL descendant tables in the cell, not just direct children.",
    ),
    search_query: str = Field("", description="Text to search for (scope='search')"),
    limit: int = Field(50, description="Max blocks to return"),
    offset: int = Field(0, description="Pagination offset"),
) -> DocumentReadResult:
    """Read Word document content."""
    from mcp_handley_lab.microsoft.word.shared import read as _read

    return _read(
        file_path=file_path,
        scope=scope,
        target_id=target_id,
        search_query=search_query,
        limit=limit,
        offset=offset,
    )


@mcp.tool(
    description="Render Word document for visual inspection or sharing. Use read to get document structure, render to see it visually. output='png' (default) returns labeled images for Claude to see. output='pdf' returns PDF bytes for sharing. Requires libreoffice (and pdftoppm for PNG)."
)
def render(
    file_path: str = Field(..., description="Path to .docx file"),
    pages: list[int] = Field(
        default=[],
        description="Page numbers to render (1-based). Required for PNG output. Max 5 pages.",
    ),
    dpi: int = Field(150, description="Resolution for PNG (default 150, max 300)"),
    output: str = Field(
        "png", description="Output format: 'png' (images) or 'pdf' (full document)"
    ),
):  # No return type - allows mixed TextContent + Image content
    """Render Word document for visual inspection or sharing."""
    from mcp_handley_lab.microsoft.word.shared import render as _render

    return _render(file_path=file_path, pages=pages or None, dpi=dpi, output=output)


@mcp.tool(
    description="Edit Word document with batch operations. Supported ops: 'insert_before', 'insert_after', 'append', 'delete', 'replace', 'style', 'edit_cell', 'edit_run', 'edit_style', 'add_comment', 'reply_comment', 'resolve_comment', 'unresolve_comment', 'set_header', 'set_footer', 'set_first_page_header', 'set_first_page_footer', 'set_even_page_header', 'set_even_page_footer', 'append_header', 'append_footer', 'clear_header', 'clear_footer', 'set_margins', 'set_orientation', 'set_columns', 'set_line_numbering', 'set_page_borders', 'set_custom_property', 'delete_custom_property', 'create_style', 'delete_style', 'insert_image', 'insert_floating_image', 'delete_image', 'add_row', 'add_column', 'delete_row', 'delete_column', 'add_page_break', 'add_break', 'set_meta', 'add_section', 'merge_cells', 'set_table_alignment', 'set_table_autofit', 'set_table_fixed_layout', 'set_row_height', 'set_cell_width', 'set_cell_vertical_alignment', 'set_cell_borders', 'set_cell_shading', 'set_header_row', 'add_tab_stop', 'clear_tab_stops', 'insert_field', 'insert_page_x_of_y', 'accept_change', 'reject_change', 'accept_all_changes', 'reject_all_changes', 'create_list', 'set_list_level', 'promote_list', 'demote_list', 'restart_numbering', 'remove_list', 'add_to_list', 'edit_text_box', 'add_bookmark', 'add_hyperlink', 'insert_cross_ref', 'insert_caption', 'insert_toc', 'update_toc', 'add_footnote', 'delete_footnote', 'set_content_control', 'create_content_control', 'add_source', 'delete_source', 'insert_citation', 'insert_bibliography', 'insert_chart', 'delete_chart', 'update_chart_data'. Block IDs are content-addressed and CHANGE when content changes or after inserts/deletes shift occurrence index. Always use element_id from response for chaining operations on modified content. Creates a new file if file_path doesn't exist. 'update_toc' sets dirty flag; Word updates content on open. 'add_to_list' adds a new paragraph to an existing list; content_data: {\"text\": \"...\", \"position\": \"before|after\", \"level\": 0-8 (optional)}. 'add_hyperlink' content_data: {\"text\": \"...\", \"address\"?: \"...\", \"fragment\"?: \"...\", \"replace\"?: true}. 'insert_chart' content_data: {\"chart_type\": \"bar|column|line|pie|scatter|area\", \"data\": [[\"Cat\",\"S1\"],[\"A\",10]], \"title\"?: \"...\"}, formatting: {\"width\"?: 5.0, \"height\"?: 3.0}."
)
def edit(
    file_path: str = Field(..., description="Path to .docx file"),
    ops: str = Field(
        ...,
        description='JSON array of operation objects. Each object must have an "op" field and operation-specific parameters. Example: [{"op": "edit_cell", "target_id": "table_abc_0", "row": 0, "col": 0, "content_data": "A1"}]. Use $prev[N] in target_id to reference element_id from operation N (0-indexed). Supported ops: insert_before, insert_after, append, delete, replace, style, edit_cell, edit_run, edit_style, add_comment, reply_comment, resolve_comment, unresolve_comment, set_header, set_footer, set_first_page_header, set_first_page_footer, set_even_page_header, set_even_page_footer, append_header, append_footer, clear_header, clear_footer, set_margins, set_orientation, set_columns, set_line_numbering, set_page_borders, set_custom_property, delete_custom_property, create_style, delete_style, insert_image, insert_floating_image, delete_image, add_row, add_column, delete_row, delete_column, add_page_break, add_break, set_meta, add_section, merge_cells, set_table_alignment, set_table_autofit, set_table_fixed_layout, set_row_height, set_cell_width, set_cell_vertical_alignment, set_cell_borders, set_cell_shading, set_header_row, add_tab_stop, clear_tab_stops, insert_field, insert_page_x_of_y, accept_change, reject_change, accept_all_changes, reject_all_changes, create_list, set_list_level, promote_list, demote_list, restart_numbering, remove_list, add_to_list, edit_text_box, add_bookmark, add_hyperlink, insert_cross_ref, insert_caption, insert_toc, update_toc, add_footnote, delete_footnote, set_content_control, create_content_control, add_source, delete_source, insert_citation, insert_bibliography.',
    ),
    mode: str = Field(
        "atomic",
        description="Batch mode: 'atomic' (all-or-nothing, file unchanged on any failure) or 'partial' (save successful ops before failure).",
    ),
) -> EditResult:
    """Edit Word document with batch operations. Creates a new file if file_path doesn't exist."""
    from mcp_handley_lab.microsoft.word.shared import edit as _edit

    return _edit(file_path=file_path, ops=ops, mode=mode)


if __name__ == "__main__":
    mcp.run()
