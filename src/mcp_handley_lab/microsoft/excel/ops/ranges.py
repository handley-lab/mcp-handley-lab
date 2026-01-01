"""Range operations for Excel.

Bulk cell operations, row/column insertion/deletion, and cell merging.
"""

from __future__ import annotations

from typing import Any

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.ops.cells import (
    get_cell_data,
    set_cell_value,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    insert_sheet_element,
    make_cell_ref,
    parse_cell_ref,
    parse_range_ref,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    get_sheet_path as _get_sheet_path,
)
from mcp_handley_lab.microsoft.excel.ops.formula_refactor import (
    update_formulas_after_delete,
    update_formulas_after_insert,
)
from mcp_handley_lab.microsoft.excel.ops.structural_update import (
    update_dependent_structures_after_delete,
    update_dependent_structures_after_insert,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def get_range_values(
    pkg: ExcelPackage, sheet_name: str, range_ref: str
) -> list[list[Any]]:
    """Get values from a range as a 2D array.

    Returns: 2D list of values (None for empty cells).
    """
    start_ref, end_ref = parse_range_ref(range_ref)
    start_col, start_row, _, _ = parse_cell_ref(start_ref)
    end_col, end_row, _, _ = parse_cell_ref(end_ref)

    start_col_idx = column_letter_to_index(start_col)
    end_col_idx = column_letter_to_index(end_col)

    # Normalize range
    if start_col_idx > end_col_idx:
        start_col_idx, end_col_idx = end_col_idx, start_col_idx
    if start_row > end_row:
        start_row, end_row = end_row, start_row

    num_rows = end_row - start_row + 1
    num_cols = end_col_idx - start_col_idx + 1

    # Initialize empty grid
    result: list[list[Any]] = [[None] * num_cols for _ in range(num_rows)]

    # Fill in values
    for row_offset in range(num_rows):
        for col_offset in range(num_cols):
            cell_ref = make_cell_ref(start_col_idx + col_offset, start_row + row_offset)
            value, _, _ = get_cell_data(pkg, sheet_name, cell_ref)
            result[row_offset][col_offset] = value

    return result


def set_range_values(
    pkg: ExcelPackage, sheet_name: str, start_ref: str, values: list[list[Any]]
) -> int:
    """Set values in a range from a 2D array.

    Args:
        start_ref: Top-left cell reference (e.g., "A1")
        values: 2D list of values to set

    Returns: Number of cells modified.
    """
    if not values or not values[0]:
        return 0

    start_col, start_row, _, _ = parse_cell_ref(start_ref)
    start_col_idx = column_letter_to_index(start_col)

    count = 0
    for row_offset, row_values in enumerate(values):
        for col_offset, value in enumerate(row_values):
            cell_ref = make_cell_ref(start_col_idx + col_offset, start_row + row_offset)
            set_cell_value(pkg, sheet_name, cell_ref, value)
            count += 1

    return count


def insert_rows(
    pkg: ExcelPackage, sheet_name: str, row_num: int, count: int = 1
) -> None:
    """Insert rows at the specified position.

    All rows at row_num and below are shifted down by count.
    Formulas referencing cells at or after the insertion point are updated.
    """
    sheet = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)
    sheet_data = sheet.find(qn("x:sheetData"))

    if sheet_data is None:
        return

    # Shift existing rows down
    for row_el in sheet_data.findall(qn("x:row")):
        current_row = int(row_el.get("r", "0"))
        if current_row >= row_num:
            new_row = current_row + count
            row_el.set("r", str(new_row))

            # Update cell references in this row
            for cell in row_el.findall(qn("x:c")):
                old_ref = cell.get("r", "")
                if old_ref:
                    col, _, c_abs, r_abs = parse_cell_ref(old_ref)
                    cell.set(
                        "r", make_cell_ref(col, new_row, col_abs=c_abs, row_abs=r_abs)
                    )

    # Re-sort rows by row number to maintain XML structure
    _sort_rows(sheet_data)

    # Update merge cells
    _shift_merge_cells(sheet, row_num, count, is_row=True)

    pkg.mark_xml_dirty(sheet_path)

    # Update formulas in all sheets
    update_formulas_after_insert(pkg, sheet_name, row_num, count, is_row=True)

    # Update dependent structures (autoFilter, validations, tables, names, charts, pivots)
    update_dependent_structures_after_insert(
        pkg, sheet_name, row_num, count, is_row=True
    )

    pkg.drop_calc_chain()


def delete_rows(
    pkg: ExcelPackage, sheet_name: str, row_num: int, count: int = 1
) -> None:
    """Delete rows starting at the specified position.

    All rows below are shifted up by count.
    Formulas referencing deleted cells become #REF!; others are updated.
    """
    sheet = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)
    sheet_data = sheet.find(qn("x:sheetData"))

    if sheet_data is None:
        return

    # Remove rows in the deletion range
    rows_to_remove = []
    for row_el in sheet_data.findall(qn("x:row")):
        current_row = int(row_el.get("r", "0"))
        if row_num <= current_row < row_num + count:
            rows_to_remove.append(row_el)

    for row_el in rows_to_remove:
        sheet_data.remove(row_el)

    # Shift remaining rows up
    for row_el in sheet_data.findall(qn("x:row")):
        current_row = int(row_el.get("r", "0"))
        if current_row >= row_num + count:
            new_row = current_row - count
            row_el.set("r", str(new_row))

            # Update cell references
            for cell in row_el.findall(qn("x:c")):
                old_ref = cell.get("r", "")
                if old_ref:
                    col, _, c_abs, r_abs = parse_cell_ref(old_ref)
                    cell.set(
                        "r", make_cell_ref(col, new_row, col_abs=c_abs, row_abs=r_abs)
                    )

    # Re-sort rows by row number to maintain XML structure
    _sort_rows(sheet_data)

    # Update merge cells
    _shift_merge_cells(sheet, row_num, -count, is_row=True)

    pkg.mark_xml_dirty(sheet_path)

    # Update formulas in all sheets
    update_formulas_after_delete(pkg, sheet_name, row_num, count, is_row=True)

    # Update dependent structures (autoFilter, validations, tables, names, charts, pivots)
    update_dependent_structures_after_delete(
        pkg, sheet_name, row_num, count, is_row=True
    )

    pkg.drop_calc_chain()


def insert_columns(
    pkg: ExcelPackage, sheet_name: str, col_ref: str | int, count: int = 1
) -> None:
    """Insert columns at the specified position.

    All columns at col_ref and to the right are shifted right by count.
    col_ref can be a letter ("A") or 1-based index (1).
    Formulas referencing cells at or after the insertion point are updated.
    """
    col_idx = col_ref if isinstance(col_ref, int) else column_letter_to_index(col_ref)

    sheet = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)
    sheet_data = sheet.find(qn("x:sheetData"))

    if sheet_data is None:
        return

    # Update cell references in all rows
    for row_el in sheet_data.findall(qn("x:row")):
        cells_to_update = []
        for cell in row_el.findall(qn("x:c")):
            old_ref = cell.get("r", "")
            if old_ref:
                col, row, c_abs, r_abs = parse_cell_ref(old_ref)
                cell_col_idx = column_letter_to_index(col)
                if cell_col_idx >= col_idx:
                    new_col_idx = cell_col_idx + count
                    cells_to_update.append((cell, new_col_idx, row, c_abs, r_abs))

        # Update cells (do separately to avoid iteration issues)
        for cell, new_col_idx, row, c_abs, r_abs in cells_to_update:
            cell.set("r", make_cell_ref(new_col_idx, row, col_abs=c_abs, row_abs=r_abs))

        # Re-sort cells by column to maintain XML structure
        _sort_cells(row_el)

    # Update merge cells
    _shift_merge_cells(sheet, col_idx, count, is_row=False)

    pkg.mark_xml_dirty(sheet_path)

    # Update formulas in all sheets
    update_formulas_after_insert(pkg, sheet_name, col_idx, count, is_row=False)

    # Update dependent structures (autoFilter, validations, tables, names, charts, pivots)
    update_dependent_structures_after_insert(
        pkg, sheet_name, col_idx, count, is_row=False
    )

    pkg.drop_calc_chain()


def delete_columns(
    pkg: ExcelPackage, sheet_name: str, col_ref: str | int, count: int = 1
) -> None:
    """Delete columns starting at the specified position.

    All columns to the right are shifted left by count.
    col_ref can be a letter ("A") or 1-based index (1).
    Formulas referencing deleted cells become #REF!; others are updated.
    """
    col_idx = col_ref if isinstance(col_ref, int) else column_letter_to_index(col_ref)

    sheet = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)
    sheet_data = sheet.find(qn("x:sheetData"))

    if sheet_data is None:
        return

    # Process each row
    for row_el in sheet_data.findall(qn("x:row")):
        cells_to_remove = []
        cells_to_update = []

        for cell in row_el.findall(qn("x:c")):
            old_ref = cell.get("r", "")
            if old_ref:
                col, row, c_abs, r_abs = parse_cell_ref(old_ref)
                cell_col_idx = column_letter_to_index(col)

                if col_idx <= cell_col_idx < col_idx + count:
                    # Cell is in deletion range
                    cells_to_remove.append(cell)
                elif cell_col_idx >= col_idx + count:
                    # Cell is after deletion range - shift left
                    new_col_idx = cell_col_idx - count
                    cells_to_update.append((cell, new_col_idx, row, c_abs, r_abs))

        for cell in cells_to_remove:
            row_el.remove(cell)

        for cell, new_col_idx, row, c_abs, r_abs in cells_to_update:
            cell.set("r", make_cell_ref(new_col_idx, row, col_abs=c_abs, row_abs=r_abs))

        # Re-sort cells by column to maintain XML structure
        _sort_cells(row_el)

    # Update merge cells
    _shift_merge_cells(sheet, col_idx, -count, is_row=False)

    pkg.mark_xml_dirty(sheet_path)

    # Update formulas in all sheets
    update_formulas_after_delete(pkg, sheet_name, col_idx, count, is_row=False)

    # Update dependent structures (autoFilter, validations, tables, names, charts, pivots)
    update_dependent_structures_after_delete(
        pkg, sheet_name, col_idx, count, is_row=False
    )

    pkg.drop_calc_chain()


def merge_cells(pkg: ExcelPackage, sheet_name: str, range_ref: str) -> None:
    """Merge cells in the specified range.

    Only the top-left cell's value is preserved; other cells are cleared.
    """
    sheet = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    # Find or create mergeCells element
    merge_cells_el = sheet.find(qn("x:mergeCells"))
    if merge_cells_el is None:
        # Create mergeCells element at correct OOXML position
        merge_cells_el = etree.Element(qn("x:mergeCells"))
        insert_sheet_element(sheet, "mergeCells", merge_cells_el)

    # Check if range overlaps with existing merges
    for existing in merge_cells_el.findall(qn("x:mergeCell")):
        existing_ref = existing.get("ref", "")
        if _ranges_overlap(range_ref, existing_ref):
            raise ValueError(
                f"Range {range_ref} overlaps with existing merge {existing_ref}"
            )

    # Add merge cell entry
    etree.SubElement(merge_cells_el, qn("x:mergeCell"), ref=range_ref)

    # Update count attribute
    count = len(merge_cells_el.findall(qn("x:mergeCell")))
    merge_cells_el.set("count", str(count))

    # Clear all cells except top-left
    start_ref, end_ref = parse_range_ref(range_ref)
    start_col, start_row, _, _ = parse_cell_ref(start_ref)
    end_col, end_row, _, _ = parse_cell_ref(end_ref)

    start_col_idx = column_letter_to_index(start_col)
    end_col_idx = column_letter_to_index(end_col)

    if start_col_idx > end_col_idx:
        start_col_idx, end_col_idx = end_col_idx, start_col_idx
    if start_row > end_row:
        start_row, end_row = end_row, start_row

    for row in range(start_row, end_row + 1):
        for col_idx in range(start_col_idx, end_col_idx + 1):
            if row == start_row and col_idx == start_col_idx:
                continue  # Skip top-left cell
            cell_ref = make_cell_ref(col_idx, row)
            set_cell_value(pkg, sheet_name, cell_ref, None)

    pkg.mark_xml_dirty(sheet_path)


def unmerge_cells(pkg: ExcelPackage, sheet_name: str, range_ref: str) -> None:
    """Unmerge cells in the specified range.

    The range must match an existing merge exactly.
    """
    sheet = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    merge_cells_el = sheet.find(qn("x:mergeCells"))
    if merge_cells_el is None:
        raise ValueError("No merged cells found")

    # Find and remove the merge
    found = False
    for merge_cell in merge_cells_el.findall(qn("x:mergeCell")):
        if merge_cell.get("ref", "").upper() == range_ref.upper():
            merge_cells_el.remove(merge_cell)
            found = True
            break

    if not found:
        raise ValueError(f"Merge not found: {range_ref}")

    # Update count or remove mergeCells element if empty
    remaining = merge_cells_el.findall(qn("x:mergeCell"))
    if not remaining:
        sheet.remove(merge_cells_el)
    else:
        merge_cells_el.set("count", str(len(remaining)))

    pkg.mark_xml_dirty(sheet_path)


# =============================================================================
# Helper Functions
# =============================================================================


def _sort_rows(sheet_data: etree._Element) -> None:
    """Sort row elements by row number to maintain valid XML structure."""
    rows = list(sheet_data.findall(qn("x:row")))
    rows.sort(key=lambda r: int(r.get("r", "0")))

    # Remove all rows and re-add in sorted order
    for row in rows:
        sheet_data.remove(row)
    for row in rows:
        sheet_data.append(row)


def _sort_cells(row_el: etree._Element) -> None:
    """Sort cell elements within a row by column to maintain valid XML structure."""
    cells = list(row_el.findall(qn("x:c")))
    cells.sort(
        key=lambda c: column_letter_to_index(parse_cell_ref(c.get("r", "A1"))[0])
    )

    # Remove all cells and re-add in sorted order
    for cell in cells:
        row_el.remove(cell)
    for cell in cells:
        row_el.append(cell)


def _shift_merge_cells(
    sheet: etree._Element, start: int, delta: int, is_row: bool
) -> None:
    """Shift merge cell references after row/column insertion or deletion.

    Args:
        start: Row number or column index where shift begins
        delta: Amount to shift (positive = insert, negative = delete)
        is_row: True for row operations, False for column operations

    For deletions, if a merge overlaps (even partially) with the deleted range,
    the merge is removed entirely to avoid corrupted merge regions.
    """
    merge_cells_el = sheet.find(qn("x:mergeCells"))
    if merge_cells_el is None:
        return

    merges_to_remove = []
    end_of_deletion = start - delta  # For delta < 0, this is start + abs(delta)

    for merge_cell in merge_cells_el.findall(qn("x:mergeCell")):
        old_ref = merge_cell.get("ref", "")
        if not old_ref:
            continue

        try:
            start_ref, end_ref = parse_range_ref(old_ref)
            s_col, s_row, s_col_abs, s_row_abs = parse_cell_ref(start_ref)
            e_col, e_row, e_col_abs, e_row_abs = parse_cell_ref(end_ref)

            s_col_idx = column_letter_to_index(s_col)
            e_col_idx = column_letter_to_index(e_col)

            if is_row:
                # Deletion: remove merge if it overlaps at all with deleted rows
                overlaps = not (e_row < start or s_row >= end_of_deletion)
                if delta < 0 and overlaps:
                    merges_to_remove.append(merge_cell)
                    continue

                # Shift rows
                if s_row >= start:
                    s_row = max(1, s_row + delta)
                if e_row >= start:
                    e_row = max(1, e_row + delta)
            else:
                # Deletion: remove merge if it overlaps at all with deleted columns
                overlaps = not (e_col_idx < start or s_col_idx >= end_of_deletion)
                if delta < 0 and overlaps:
                    merges_to_remove.append(merge_cell)
                    continue

                # Shift columns
                if s_col_idx >= start:
                    s_col_idx = max(1, s_col_idx + delta)
                if e_col_idx >= start:
                    e_col_idx = max(1, e_col_idx + delta)

            # Rebuild reference
            new_start = make_cell_ref(
                s_col_idx, s_row, col_abs=s_col_abs, row_abs=s_row_abs
            )
            new_end = make_cell_ref(
                e_col_idx, e_row, col_abs=e_col_abs, row_abs=e_row_abs
            )
            merge_cell.set("ref", f"{new_start}:{new_end}")

        except ValueError:
            continue

    for merge_cell in merges_to_remove:
        merge_cells_el.remove(merge_cell)

    # Update count
    remaining = merge_cells_el.findall(qn("x:mergeCell"))
    if remaining:
        merge_cells_el.set("count", str(len(remaining)))
    else:
        sheet.remove(merge_cells_el)


def _ranges_overlap(range1: str, range2: str) -> bool:
    """Check if two ranges overlap."""
    try:
        s1, e1 = parse_range_ref(range1)
        s2, e2 = parse_range_ref(range2)

        s1_col, s1_row, _, _ = parse_cell_ref(s1)
        e1_col, e1_row, _, _ = parse_cell_ref(e1)
        s2_col, s2_row, _, _ = parse_cell_ref(s2)
        e2_col, e2_row, _, _ = parse_cell_ref(e2)

        s1_col_idx = column_letter_to_index(s1_col)
        e1_col_idx = column_letter_to_index(e1_col)
        s2_col_idx = column_letter_to_index(s2_col)
        e2_col_idx = column_letter_to_index(e2_col)

        # Normalize ranges
        if s1_col_idx > e1_col_idx:
            s1_col_idx, e1_col_idx = e1_col_idx, s1_col_idx
        if s1_row > e1_row:
            s1_row, e1_row = e1_row, s1_row
        if s2_col_idx > e2_col_idx:
            s2_col_idx, e2_col_idx = e2_col_idx, s2_col_idx
        if s2_row > e2_row:
            s2_row, e2_row = e2_row, s2_row

        # Check for overlap
        col_overlap = s1_col_idx <= e2_col_idx and e1_col_idx >= s2_col_idx
        row_overlap = s1_row <= e2_row and e1_row >= s2_row

        return col_overlap and row_overlap
    except ValueError:
        return False
