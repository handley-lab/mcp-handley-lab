"""Cell operations for Excel.

Reading and writing cell values, formulas, and styles.
"""

from __future__ import annotations

from typing import Any

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import NSMAP, qn
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    parse_cell_ref,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    get_sheet_path as _get_sheet_path,
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


def get_cell_value(pkg: ExcelPackage, sheet_name: str, cell_ref: str) -> Any:
    """Get just the cell value (ignoring type and formula).

    Returns: JSON primitive (int, float, str, bool, None)
    """
    value, _type, _formula = get_cell_data(pkg, sheet_name, cell_ref)
    return value


def get_cell_formula(pkg: ExcelPackage, sheet_name: str, cell_ref: str) -> str | None:
    """Get just the cell formula (ignoring value and type).

    Returns: Formula string without leading '=', or None if no formula.
    """
    _value, _type, formula = get_cell_data(pkg, sheet_name, cell_ref)
    return formula


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
    return sheet.find(f".//x:c[@r='{col}{row}']", namespaces=NSMAP)


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

    # Formula without cached value
    if has_formula:
        return None, TYPE_FORMULA, formula

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


# =============================================================================
# Write Operations
# =============================================================================


def set_cell_value(
    pkg: ExcelPackage, sheet_name: str, cell_ref: str, value: Any
) -> None:
    """Set a cell's value.

    Handles type inference:
    - None: clears the cell
    - bool: sets boolean cell
    - int/float: sets numeric cell
    - str: adds to shared strings and sets string cell

    After editing, call pkg.drop_calc_chain() to force recalculation.
    """
    sheet = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    col, row, _, _ = parse_cell_ref(cell_ref)
    cell = _ensure_cell(sheet, f"{col}{row}", row)

    if value is None:
        # Clear the cell
        _clear_cell(cell)
    elif isinstance(value, bool):
        _set_boolean_cell(cell, value)
    elif isinstance(value, int | float):
        _set_number_cell(cell, value)
    else:
        _set_string_cell(pkg, cell, str(value))

    pkg.mark_xml_dirty(sheet_path)
    pkg.drop_calc_chain()


def set_cell_formula(
    pkg: ExcelPackage, sheet_name: str, cell_ref: str, formula: str
) -> None:
    """Set a cell's formula.

    The formula should not include the leading '=' sign.
    Example: set_cell_formula(pkg, "Sheet1", "A1", "SUM(B1:B10)")
    """
    sheet = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    col, row, _, _ = parse_cell_ref(cell_ref)
    cell = _ensure_cell(sheet, f"{col}{row}", row)

    # Remove any existing value
    for v_el in cell.findall(qn("x:v")):
        cell.remove(v_el)

    # Set formula
    f_el = cell.find(qn("x:f"))
    if f_el is None:
        f_el = etree.SubElement(cell, qn("x:f"))
    f_el.text = formula

    # Clear type attribute (result type determined on calculation)
    if "t" in cell.attrib:
        del cell.attrib["t"]

    pkg.mark_xml_dirty(sheet_path)
    pkg.drop_calc_chain()


def set_cell_style(
    pkg: ExcelPackage, sheet_name: str, cell_ref: str, style_index: int
) -> None:
    """Set a cell's style index.

    The style_index references the cellXfs array in styles.xml.
    """
    sheet = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    col, row, _, _ = parse_cell_ref(cell_ref)
    cell = _ensure_cell(sheet, f"{col}{row}", row)
    cell.set("s", str(style_index))

    pkg.mark_xml_dirty(sheet_path)


def _ensure_cell(sheet: etree._Element, cell_ref: str, row_num: int) -> etree._Element:
    """Ensure a cell element exists, creating row and cell if needed."""
    sheet_data = sheet.find(qn("x:sheetData"))
    if sheet_data is None:
        sheet_data = etree.SubElement(sheet, qn("x:sheetData"))

    # Find or create the row
    row_el = None
    for r in sheet_data.findall(qn("x:row")):
        if r.get("r") == str(row_num):
            row_el = r
            break

    if row_el is None:
        # Create row in correct position (sorted by row number)
        row_el = etree.Element(qn("x:row"), r=str(row_num))
        inserted = False
        for r in sheet_data.findall(qn("x:row")):
            if int(r.get("r", "0")) > row_num:
                r.addprevious(row_el)
                inserted = True
                break
        if not inserted:
            sheet_data.append(row_el)

    # Find or create the cell
    cell_el = None
    for c in row_el.findall(qn("x:c")):
        if c.get("r", "").upper() == cell_ref.upper():
            cell_el = c
            break

    if cell_el is None:
        # Create cell in correct position (sorted by column)
        cell_el = etree.Element(qn("x:c"), r=cell_ref)
        col, _, _, _ = parse_cell_ref(cell_ref)
        col_idx = column_letter_to_index(col)

        inserted = False
        for c in row_el.findall(qn("x:c")):
            c_col, _, _, _ = parse_cell_ref(c.get("r", "A1"))
            c_idx = column_letter_to_index(c_col)
            if c_idx > col_idx:
                c.addprevious(cell_el)
                inserted = True
                break
        if not inserted:
            row_el.append(cell_el)

    return cell_el


def _clear_cell(cell: etree._Element) -> None:
    """Clear a cell's value, formula, and type."""
    for v_el in cell.findall(qn("x:v")):
        cell.remove(v_el)
    for f_el in cell.findall(qn("x:f")):
        cell.remove(f_el)
    if "t" in cell.attrib:
        del cell.attrib["t"]


def _set_boolean_cell(cell: etree._Element, value: bool) -> None:
    """Set a cell to a boolean value."""
    _clear_cell(cell)
    cell.set("t", "b")
    v_el = etree.SubElement(cell, qn("x:v"))
    v_el.text = "1" if value else "0"


def _set_number_cell(cell: etree._Element, value: int | float) -> None:
    """Set a cell to a numeric value."""
    _clear_cell(cell)
    if "t" in cell.attrib:
        del cell.attrib["t"]  # Numbers have no type attribute
    v_el = etree.SubElement(cell, qn("x:v"))
    # Use repr to preserve precision, but strip trailing .0 for integers
    if isinstance(value, float) and value.is_integer():
        v_el.text = str(int(value))
    else:
        v_el.text = str(value)


def _set_string_cell(pkg: ExcelPackage, cell: etree._Element, value: str) -> None:
    """Set a cell to a string value using shared strings."""
    _clear_cell(cell)
    idx = pkg.shared_strings.add(value)
    cell.set("t", "s")
    v_el = etree.SubElement(cell, qn("x:v"))
    v_el.text = str(idx)


def _set_inline_string(cell: etree._Element, value: str) -> None:
    """Set a cell to an inline string value (doesn't affect shared strings).

    Used for find/replace to avoid affecting other cells using the same shared string.
    Sets t="inlineStr" and adds <is><t>value</t></is>.
    """
    _clear_cell(cell)
    # Remove any existing inline string
    for is_el in cell.findall(qn("x:is")):
        cell.remove(is_el)

    cell.set("t", "inlineStr")
    is_el = etree.SubElement(cell, qn("x:is"))
    t_el = etree.SubElement(is_el, qn("x:t"))
    t_el.text = value
    # Preserve leading/trailing whitespace
    if value and (value[0].isspace() or value[-1].isspace()):
        t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def find_replace(
    pkg: ExcelPackage,
    search: str,
    replace: str,
    sheet_name: str | None = None,
    match_case: bool = True,
) -> int:
    """Find and replace text in cell values.

    Skips formula cells to avoid breaking formulas.
    Uses inline strings for replacement to avoid affecting other cells
    using the same shared string.

    Args:
        pkg: ExcelPackage
        search: Text to search for
        replace: Replacement text
        sheet_name: Optional sheet to limit search. If None, searches all sheets.
        match_case: If True (default), search is case-sensitive. If False,
            performs case-insensitive search while preserving original case
            in non-matched portions.

    Returns:
        Total number of replacements made.
    """
    if not search:
        raise ValueError("search text cannot be empty")

    total_count = 0

    # Determine sheets to process
    if sheet_name:
        sheets_to_check = [sheet_name]
    else:
        from mcp_handley_lab.microsoft.excel.ops.sheets import list_sheets

        sheets_to_check = [s.name for s in list_sheets(pkg)]

    for sname in sheets_to_check:
        sheet_xml = pkg.get_sheet_xml(sname)
        sheet_part = _get_sheet_path(pkg, sname)

        for row in sheet_xml.findall(qn("x:sheetData") + "/" + qn("x:row")):
            for cell in row.findall(qn("x:c")):
                # Skip formula cells (Risk B)
                if cell.find(qn("x:f")) is not None:
                    continue

                # Get current value
                value, _, _ = _extract_cell_data(pkg, cell)
                if value is None:
                    continue

                # Convert to string and check for match
                str_value = str(value)
                if match_case:
                    if search in str_value:
                        new_value = str_value.replace(search, replace)
                        _set_inline_string(cell, new_value)
                        total_count += str_value.count(search)
                        pkg.mark_xml_dirty(sheet_part)
                else:
                    # Case-insensitive replacement
                    import re

                    pattern = re.compile(re.escape(search), re.IGNORECASE)
                    matches = pattern.findall(str_value)
                    if matches:
                        new_value = pattern.sub(replace, str_value)
                        _set_inline_string(cell, new_value)
                        total_count += len(matches)
                        pkg.mark_xml_dirty(sheet_part)

    return total_count


def find_cells(
    pkg: ExcelPackage,
    query: str,
    sheet_name: str | None = None,
    match_case: bool = False,
    exact: bool = False,
) -> list[dict[str, Any]]:
    """Find cells containing specific text.

    Searches cell values (not formulas) across sheets. Handles all cell types:
    - Shared strings (t="s")
    - Inline strings (t="inlineStr")
    - Formula string results (t="str")
    - Numbers (no type or t="n")
    - Booleans (t="b")
    - Errors (t="e")

    Args:
        pkg: ExcelPackage
        query: Text to search for
        sheet_name: Optional sheet to limit search. If None, searches all sheets.
        match_case: Case-sensitive search (default False)
        exact: Exact match only (default False for substring matching)

    Returns:
        List of dicts with 'sheet', 'ref', and 'value' for each match.
    """
    from mcp_handley_lab.microsoft.excel.ops.sheets import list_sheets

    if not query:
        raise ValueError("query cannot be empty")

    results: list[dict[str, Any]] = []
    query_norm = query if match_case else query.lower()

    # Determine sheets to process
    sheets_to_check = [sheet_name] if sheet_name else [s.name for s in list_sheets(pkg)]

    for sname in sheets_to_check:
        sheet_xml = pkg.get_sheet_xml(sname)
        sheet_data = sheet_xml.find(qn("x:sheetData"))
        if sheet_data is None:
            continue

        for row in sheet_data.findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                cell_ref = cell.get("r", "")
                if not cell_ref:
                    continue

                # Get cell value (handles all types)
                value, type_code, _ = _extract_cell_data(pkg, cell)
                if value is None:
                    continue

                # Convert to string for matching
                val_str = str(value)
                check_val = val_str if match_case else val_str.lower()

                # Check for match
                match = check_val == query_norm if exact else query_norm in check_val

                if match:
                    results.append(
                        {
                            "sheet": sname,
                            "ref": cell_ref,
                            "value": value,
                        }
                    )

    return results
