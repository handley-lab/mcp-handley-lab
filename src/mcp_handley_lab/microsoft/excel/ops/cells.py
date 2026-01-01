"""Cell operations for Excel.

Reading and writing cell values, formulas, and styles.
"""

from __future__ import annotations

from typing import Any

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    parse_cell_ref,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage

# Type codes for cell types
TYPE_NUMBER = "n"
TYPE_STRING = "s"
TYPE_BOOLEAN = "b"
TYPE_ERROR = "e"
TYPE_FORMULA = "f"  # Has formula (value may be any type)
TYPE_EMPTY = None


def get_cell_data(
    pkg: ExcelPackage, sheet_name: str, cell_ref: str
) -> tuple[Any, str | None, str | None]:
    """Get cell value, type, and formula.

    Returns: (value, type_code, formula)
    - value: JSON primitive (int, float, str, bool, None)
    - type_code: n=number, s=string, b=boolean, e=error, f=formula, None=empty
    - formula: formula string if present, else None
    """
    sheet = pkg.get_sheet_xml(sheet_name)
    cell = _find_cell(sheet, cell_ref)

    if cell is None:
        return None, TYPE_EMPTY, None

    return _extract_cell_data(pkg, cell)


def get_cells_in_range(
    pkg: ExcelPackage, sheet_name: str, start_ref: str, end_ref: str
) -> list[tuple[str, Any, str | None, str | None]]:
    """Get all cells in a range.

    Returns: list of (cell_ref, value, type_code, formula) tuples
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
                value, type_code, formula = _extract_cell_data(pkg, cell)
                if type_code is not None:  # Not empty
                    results.append((cell_ref, value, type_code, formula))

    return results


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


def _extract_cell_data(
    pkg: ExcelPackage, cell: etree._Element
) -> tuple[Any, str | None, str | None]:
    """Extract value, type code, and formula from cell element.

    Returns JSON primitives for values:
    - Numbers as int or float
    - Booleans as True/False
    - Strings as str
    - Errors as str (e.g., "#N/A")
    """
    cell_type = cell.get("t", "")
    v_el = cell.find(qn("x:v"))
    f_el = cell.find(qn("x:f"))

    formula = f_el.text if f_el is not None and f_el.text else None
    has_formula = formula is not None

    # Shared string
    if cell_type == "s":
        if v_el is not None and v_el.text:
            idx = int(v_el.text)
            value = pkg.shared_strings[idx]
            return value, TYPE_FORMULA if has_formula else TYPE_STRING, formula
        return None, TYPE_EMPTY, None

    # Inline string
    if cell_type == "inlineStr":
        is_el = cell.find(qn("x:is"))
        if is_el is not None:
            t_el = is_el.find(qn("x:t"))
            if t_el is not None and t_el.text:
                return t_el.text, TYPE_FORMULA if has_formula else TYPE_STRING, formula
            # Rich text: concatenate <r><t>...</t></r> runs
            parts = []
            for r in is_el.findall(qn("x:r")):
                t = r.find(qn("x:t"))
                if t is not None and t.text:
                    parts.append(t.text)
            if parts:
                return (
                    "".join(parts),
                    TYPE_FORMULA if has_formula else TYPE_STRING,
                    formula,
                )
        return None, TYPE_EMPTY, None

    # Formula with string result
    if cell_type == "str":
        if v_el is not None and v_el.text:
            return v_el.text, TYPE_FORMULA if has_formula else TYPE_STRING, formula
        return None, TYPE_EMPTY, None

    # Boolean
    if cell_type == "b":
        if v_el is not None and v_el.text:
            value = v_el.text == "1"
            return value, TYPE_FORMULA if has_formula else TYPE_BOOLEAN, formula
        return None, TYPE_EMPTY, None

    # Error
    if cell_type == "e":
        if v_el is not None and v_el.text:
            return v_el.text, TYPE_ERROR, formula
        return None, TYPE_EMPTY, None

    # Number (default when no type attribute)
    if v_el is not None and v_el.text:
        value = _parse_number(v_el.text)
        return value, TYPE_FORMULA if has_formula else TYPE_NUMBER, formula

    return None, TYPE_EMPTY, None


def _parse_number(text: str) -> int | float:
    """Parse numeric string to int or float.

    Returns int if value is whole number, float otherwise.
    """
    try:
        f = float(text)
        if f.is_integer():
            return int(f)
        return f
    except ValueError:
        return text  # Fallback to string if unparseable
