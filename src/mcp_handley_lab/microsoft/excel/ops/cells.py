"""Cell operations for Excel.

Reading and writing cell values, formulas, and styles.
"""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    parse_cell_ref,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def get_cell_value(
    pkg: ExcelPackage, sheet_name: str, cell_ref: str
) -> tuple[str | None, str]:
    """Get cell value and type.

    Returns: (value, cell_type)
    Where cell_type is one of: "string", "number", "boolean", "error", "empty"

    Handles:
    - t="s" -> shared string index
    - t="inlineStr" -> inline <is><t>...</t></is>
    - t="str" -> formula string result
    - t="b" -> boolean (0/1)
    - t="e" -> error
    - absent t -> number
    """
    sheet = pkg.get_sheet_xml(sheet_name)
    cell = _find_cell(sheet, cell_ref)

    if cell is None:
        return None, "empty"

    cell_type = cell.get("t", "")
    v_el = cell.find(qn("x:v"))

    # Handle by type attribute
    if cell_type == "s":
        # Shared string - v contains index
        if v_el is not None and v_el.text:
            idx = int(v_el.text)
            return pkg.shared_strings[idx], "string"
        return None, "empty"

    elif cell_type == "inlineStr":
        # Inline string - <is><t>text</t></is>
        is_el = cell.find(qn("x:is"))
        if is_el is not None:
            t_el = is_el.find(qn("x:t"))
            if t_el is not None and t_el.text:
                return t_el.text, "string"
            # Rich text in inline string
            parts = []
            for r in is_el.findall(qn("x:r")):
                t = r.find(qn("x:t"))
                if t is not None and t.text:
                    parts.append(t.text)
            if parts:
                return "".join(parts), "string"
        return None, "empty"

    elif cell_type == "str":
        # Formula string result
        if v_el is not None and v_el.text:
            return v_el.text, "string"
        return None, "empty"

    elif cell_type == "b":
        # Boolean
        if v_el is not None and v_el.text:
            return "TRUE" if v_el.text == "1" else "FALSE", "boolean"
        return None, "empty"

    elif cell_type == "e":
        # Error
        if v_el is not None and v_el.text:
            return v_el.text, "error"
        return None, "empty"

    else:
        # No type or numeric - could be number or date
        # Date detection requires checking the style (numFmtId)
        # For now, return as number
        if v_el is not None and v_el.text:
            return v_el.text, "number"
        return None, "empty"


def get_cell_formula(pkg: ExcelPackage, sheet_name: str, cell_ref: str) -> str | None:
    """Get cell formula if present.

    Returns: Formula string without leading '=', or None if no formula.
    """
    sheet = pkg.get_sheet_xml(sheet_name)
    cell = _find_cell(sheet, cell_ref)

    if cell is None:
        return None

    f_el = cell.find(qn("x:f"))
    if f_el is not None and f_el.text:
        return f_el.text
    return None


def get_cell_style_index(
    pkg: ExcelPackage, sheet_name: str, cell_ref: str
) -> int | None:
    """Get cell style index (s attribute).

    Returns: Style index into cellXfs, or None if no style.
    """
    sheet = pkg.get_sheet_xml(sheet_name)
    cell = _find_cell(sheet, cell_ref)

    if cell is None:
        return None

    s = cell.get("s")
    return int(s) if s else None


def get_cells_in_range(
    pkg: ExcelPackage, sheet_name: str, start_ref: str, end_ref: str
) -> list[tuple[str, str | None, str]]:
    """Get all cells in a range.

    Returns: list of (cell_ref, value, cell_type) tuples
    Only includes non-empty cells.
    """
    start_col, start_row, _, _ = parse_cell_ref(start_ref)
    end_col, end_row, _, _ = parse_cell_ref(end_ref)

    start_col_idx = column_letter_to_index(start_col)
    end_col_idx = column_letter_to_index(end_col)

    # Normalize range (ensure start <= end)
    if start_col_idx > end_col_idx:
        start_col_idx, end_col_idx = end_col_idx, start_col_idx
    if start_row > end_row:
        start_row, end_row = end_row, start_row

    sheet = pkg.get_sheet_xml(sheet_name)
    sheet_data = sheet.find(qn("x:sheetData"))
    if sheet_data is None:
        return []

    results = []
    for row in sheet_data.findall(qn("x:row")):
        row_num = int(row.get("r", "0"))
        if not (start_row <= row_num <= end_row):
            continue

        for cell in row.findall(qn("x:c")):
            cell_ref = cell.get("r", "")
            if not cell_ref:
                continue

            try:
                col, _, _, _ = parse_cell_ref(cell_ref)
                col_idx = column_letter_to_index(col)
            except ValueError:
                continue

            if start_col_idx <= col_idx <= end_col_idx:
                value, cell_type = _get_cell_value_from_element(pkg, cell)
                if cell_type != "empty":
                    results.append((cell_ref, value, cell_type))

    return results


def _find_cell(sheet: etree._Element, cell_ref: str) -> etree._Element | None:
    """Find cell element by reference."""
    col, row, _, _ = parse_cell_ref(cell_ref)
    normalized_ref = f"{col}{row}"

    sheet_data = sheet.find(qn("x:sheetData"))
    if sheet_data is None:
        return None

    # Find the row
    for row_el in sheet_data.findall(qn("x:row")):
        if row_el.get("r") == str(row):
            # Find the cell in this row
            for cell_el in row_el.findall(qn("x:c")):
                if cell_el.get("r", "").upper() == normalized_ref.upper():
                    return cell_el
            break
    return None


def _get_cell_value_from_element(
    pkg: ExcelPackage, cell: etree._Element
) -> tuple[str | None, str]:
    """Extract value and type from cell element."""
    cell_type = cell.get("t", "")
    v_el = cell.find(qn("x:v"))

    if cell_type == "s":
        if v_el is not None and v_el.text:
            idx = int(v_el.text)
            return pkg.shared_strings[idx], "string"
        return None, "empty"

    elif cell_type == "inlineStr":
        is_el = cell.find(qn("x:is"))
        if is_el is not None:
            t_el = is_el.find(qn("x:t"))
            if t_el is not None and t_el.text:
                return t_el.text, "string"
            # Rich text in inline string: <r><t>part1</t></r><r><t>part2</t></r>
            parts = []
            for r in is_el.findall(qn("x:r")):
                t = r.find(qn("x:t"))
                if t is not None and t.text:
                    parts.append(t.text)
            if parts:
                return "".join(parts), "string"
        return None, "empty"

    elif cell_type == "str":
        if v_el is not None and v_el.text:
            return v_el.text, "string"
        return None, "empty"

    elif cell_type == "b":
        if v_el is not None and v_el.text:
            return "TRUE" if v_el.text == "1" else "FALSE", "boolean"
        return None, "empty"

    elif cell_type == "e":
        if v_el is not None and v_el.text:
            return v_el.text, "error"
        return None, "empty"

    else:
        if v_el is not None and v_el.text:
            return v_el.text, "number"
        return None, "empty"
