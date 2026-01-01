"""Sheet operations for Excel.

Listing sheets, getting sheet info, and determining used ranges.
"""

from __future__ import annotations

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.models import SheetInfo
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    index_to_column_letter,
    make_range_ref,
    parse_cell_ref,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def list_sheets(pkg: ExcelPackage) -> list[SheetInfo]:
    """List all sheets in workbook.

    Returns: List of SheetInfo with name and index.
    """
    sheet_paths = pkg.get_sheet_paths()
    result = []
    for idx, (name, _rId, _partname) in enumerate(sheet_paths):
        result.append(SheetInfo(name=name, index=idx))
    return result


def get_sheet_by_name(pkg: ExcelPackage, sheet_name: str) -> SheetInfo:
    """Get sheet info by name.

    Raises: KeyError if sheet not found.
    """
    for info in list_sheets(pkg):
        if info.name == sheet_name:
            return info
    raise KeyError(f"Sheet not found: {sheet_name}")


def get_sheet_by_index(pkg: ExcelPackage, idx: int) -> SheetInfo:
    """Get sheet info by 0-based index.

    Raises: IndexError if index out of range.
    """
    sheets = list_sheets(pkg)
    if not 0 <= idx < len(sheets):
        raise IndexError(f"Sheet index out of range: {idx}")
    return sheets[idx]


def get_used_range(pkg: ExcelPackage, sheet_name: str) -> str | None:
    """Determine the used range of a sheet.

    Scans sheetData to find the bounding box of all cells with data.
    Returns: Range reference like 'A1:C10', or None if sheet is empty.
    """
    sheet = pkg.get_sheet_xml(sheet_name)
    sheet_data = sheet.find(qn("x:sheetData"))
    if sheet_data is None:
        return None

    min_row = float("inf")
    max_row = 0
    min_col = float("inf")
    max_col = 0
    has_data = False

    for row in sheet_data.findall(qn("x:row")):
        row_num = int(row.get("r", "0"))
        if row_num == 0:
            continue

        for cell in row.findall(qn("x:c")):
            cell_ref = cell.get("r", "")
            if not cell_ref:
                continue

            # Check if cell has content (v or is element)
            v_el = cell.find(qn("x:v"))
            is_el = cell.find(qn("x:is"))
            f_el = cell.find(qn("x:f"))
            if v_el is None and is_el is None and f_el is None:
                continue

            try:
                col, cell_row, _, _ = parse_cell_ref(cell_ref)
                col_idx = column_letter_to_index(col)
            except ValueError:
                continue

            has_data = True
            min_row = min(min_row, cell_row)
            max_row = max(max_row, cell_row)
            min_col = min(min_col, col_idx)
            max_col = max(max_col, col_idx)

    if not has_data:
        return None

    start_ref = f"{index_to_column_letter(int(min_col))}{int(min_row)}"
    end_ref = f"{index_to_column_letter(int(max_col))}{int(max_row)}"
    return make_range_ref(start_ref, end_ref)


def get_dimension(pkg: ExcelPackage, sheet_name: str) -> str | None:
    """Get sheet dimension from dimension element.

    This is the range Excel reports, which may differ from actual used range.
    Returns: Range reference like 'A1:C10', or None if no dimension element.
    """
    sheet = pkg.get_sheet_xml(sheet_name)
    dim = sheet.find(qn("x:dimension"))
    if dim is not None:
        return dim.get("ref")
    return None
