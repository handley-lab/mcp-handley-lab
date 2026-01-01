"""Protection operations for Excel.

Sheet protection, workbook protection, and cell locking/unlocking.
"""

from __future__ import annotations

import copy

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import qn
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
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def _hash_password(password: str) -> str:
    """Hash password using legacy Excel algorithm.

    Excel uses a simple hash algorithm for worksheet protection.
    This is NOT cryptographically secure - it's for compatibility only.
    """
    # Excel's legacy hash algorithm
    password_bytes = password.encode("UTF-16LE")
    hash_val = 0
    for i, byte in enumerate(password_bytes):
        hash_val ^= (byte << (i % 15)) & 0xFFFF
        hash_val ^= (byte >> (15 - (i % 15))) & 0x7FFF
    hash_val ^= len(password_bytes)
    hash_val ^= 0xCE4B
    return format(hash_val & 0xFFFF, "04X")


def protect_sheet(
    pkg: ExcelPackage,
    sheet_name: str,
    password: str | None = None,
    sheet: bool = True,
    objects: bool = True,
    scenarios: bool = True,
    format_cells: bool = True,
    format_columns: bool = True,
    format_rows: bool = True,
    insert_columns: bool = True,
    insert_rows: bool = True,
    insert_hyperlinks: bool = True,
    delete_columns: bool = True,
    delete_rows: bool = True,
    select_locked_cells: bool = False,
    sort: bool = True,
    auto_filter: bool = True,
    pivot_tables: bool = True,
    select_unlocked_cells: bool = False,
) -> None:
    """Protect a worksheet from modification.

    Args:
        sheet_name: Name of the sheet to protect.
        password: Optional password for protection.
        sheet: Protect sheet structure.
        objects: Protect drawing objects.
        scenarios: Protect scenarios.
        format_cells: Prevent cell formatting (True = locked).
        format_columns: Prevent column formatting.
        format_rows: Prevent row formatting.
        insert_columns: Prevent column insertion.
        insert_rows: Prevent row insertion.
        insert_hyperlinks: Prevent hyperlink insertion.
        delete_columns: Prevent column deletion.
        delete_rows: Prevent row deletion.
        select_locked_cells: Prevent selection of locked cells.
        sort: Prevent sorting.
        auto_filter: Prevent autofilter use.
        pivot_tables: Prevent pivot table use.
        select_unlocked_cells: Prevent selection of unlocked cells.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    # Remove existing protection element
    existing = sheet_xml.find(qn("x:sheetProtection"))
    if existing is not None:
        sheet_xml.remove(existing)

    # Create protection element with attributes
    attrs = {}
    if password:
        attrs["password"] = _hash_password(password)
    if sheet:
        attrs["sheet"] = "1"
    if objects:
        attrs["objects"] = "1"
    if scenarios:
        attrs["scenarios"] = "1"
    if format_cells:
        attrs["formatCells"] = "1"
    if format_columns:
        attrs["formatColumns"] = "1"
    if format_rows:
        attrs["formatRows"] = "1"
    if insert_columns:
        attrs["insertColumns"] = "1"
    if insert_rows:
        attrs["insertRows"] = "1"
    if insert_hyperlinks:
        attrs["insertHyperlinks"] = "1"
    if delete_columns:
        attrs["deleteColumns"] = "1"
    if delete_rows:
        attrs["deleteRows"] = "1"
    if select_locked_cells:
        attrs["selectLockedCells"] = "1"
    if sort:
        attrs["sort"] = "1"
    if auto_filter:
        attrs["autoFilter"] = "1"
    if pivot_tables:
        attrs["pivotTables"] = "1"
    if select_unlocked_cells:
        attrs["selectUnlockedCells"] = "1"

    protection = etree.Element(qn("x:sheetProtection"), **attrs)

    # Insert at correct OOXML position
    insert_sheet_element(sheet_xml, "sheetProtection", protection)

    pkg.mark_xml_dirty(sheet_path)


def unprotect_sheet(
    pkg: ExcelPackage, sheet_name: str, password: str | None = None
) -> None:
    """Remove protection from a worksheet.

    Args:
        sheet_name: Name of the sheet to unprotect.
        password: Password to verify (if sheet was protected with one).

    Raises:
        ValueError: If password is incorrect.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    protection = sheet_xml.find(qn("x:sheetProtection"))
    if protection is None:
        return  # Already unprotected

    # Check password if one was set
    stored_hash = protection.get("password")
    if stored_hash:
        if not password:
            raise ValueError("Sheet is password-protected")
        if _hash_password(password) != stored_hash:
            raise ValueError("Incorrect password")

    sheet_xml.remove(protection)
    pkg.mark_xml_dirty(sheet_path)


def is_sheet_protected(pkg: ExcelPackage, sheet_name: str) -> bool:
    """Check if a worksheet is protected.

    Returns: True if the sheet has protection enabled.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    protection = sheet_xml.find(qn("x:sheetProtection"))
    return protection is not None


def get_sheet_protection(pkg: ExcelPackage, sheet_name: str) -> dict | None:
    """Get protection settings for a worksheet.

    Returns: Dictionary of protection settings, or None if unprotected.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    protection = sheet_xml.find(qn("x:sheetProtection"))
    if protection is None:
        return None

    return {
        "password_set": protection.get("password") is not None,
        "sheet": protection.get("sheet") == "1",
        "objects": protection.get("objects") == "1",
        "scenarios": protection.get("scenarios") == "1",
        "format_cells": protection.get("formatCells") == "1",
        "format_columns": protection.get("formatColumns") == "1",
        "format_rows": protection.get("formatRows") == "1",
        "insert_columns": protection.get("insertColumns") == "1",
        "insert_rows": protection.get("insertRows") == "1",
        "insert_hyperlinks": protection.get("insertHyperlinks") == "1",
        "delete_columns": protection.get("deleteColumns") == "1",
        "delete_rows": protection.get("deleteRows") == "1",
        "select_locked_cells": protection.get("selectLockedCells") == "1",
        "sort": protection.get("sort") == "1",
        "auto_filter": protection.get("autoFilter") == "1",
        "pivot_tables": protection.get("pivotTables") == "1",
        "select_unlocked_cells": protection.get("selectUnlockedCells") == "1",
    }


def protect_workbook(
    pkg: ExcelPackage,
    password: str | None = None,
    lock_structure: bool = True,
    lock_windows: bool = False,
) -> None:
    """Protect workbook structure and/or windows.

    Args:
        password: Optional password for protection.
        lock_structure: Prevent adding/deleting/renaming sheets.
        lock_windows: Prevent window resizing/moving.
    """
    workbook = pkg.workbook_xml

    # Remove existing protection
    existing = workbook.find(qn("x:workbookProtection"))
    if existing is not None:
        workbook.remove(existing)

    attrs = {}
    if password:
        attrs["workbookPassword"] = _hash_password(password)
    if lock_structure:
        attrs["lockStructure"] = "1"
    if lock_windows:
        attrs["lockWindows"] = "1"

    protection = etree.Element(qn("x:workbookProtection"), **attrs)

    # Insert after sheets element
    sheets = workbook.find(qn("x:sheets"))
    if sheets is not None:
        idx = list(workbook).index(sheets)
        workbook.insert(idx + 1, protection)
    else:
        workbook.append(protection)

    pkg.mark_xml_dirty(pkg.workbook_path)


def unprotect_workbook(pkg: ExcelPackage, password: str | None = None) -> None:
    """Remove workbook protection.

    Args:
        password: Password to verify (if workbook was protected with one).

    Raises:
        ValueError: If password is incorrect.
    """
    workbook = pkg.workbook_xml

    protection = workbook.find(qn("x:workbookProtection"))
    if protection is None:
        return  # Already unprotected

    # Check password if one was set
    stored_hash = protection.get("workbookPassword")
    if stored_hash:
        if not password:
            raise ValueError("Workbook is password-protected")
        if _hash_password(password) != stored_hash:
            raise ValueError("Incorrect password")

    workbook.remove(protection)
    pkg.mark_xml_dirty(pkg.workbook_path)


def is_workbook_protected(pkg: ExcelPackage) -> bool:
    """Check if workbook is protected.

    Returns: True if workbook has protection enabled.
    """
    workbook = pkg.workbook_xml
    protection = workbook.find(qn("x:workbookProtection"))
    return protection is not None


def get_workbook_protection(pkg: ExcelPackage) -> dict | None:
    """Get workbook protection settings.

    Returns: Dictionary of protection settings, or None if unprotected.
    """
    workbook = pkg.workbook_xml
    protection = workbook.find(qn("x:workbookProtection"))
    if protection is None:
        return None

    return {
        "password_set": protection.get("workbookPassword") is not None,
        "lock_structure": protection.get("lockStructure") == "1",
        "lock_windows": protection.get("lockWindows") == "1",
    }


def _clone_style_with_protection(
    pkg: ExcelPackage, base_style_idx: int | None, locked: bool
) -> int:
    """Clone a style and set its protection state, preserving other attributes.

    Args:
        pkg: Excel package.
        base_style_idx: Index of existing style to clone, or None for default.
        locked: Whether cells should be locked.

    Returns: Style index (xf index) with the desired protection state.
    """
    styles_xml = pkg.get_xml("/xl/styles.xml")

    # Find cellXfs element
    cell_xfs = styles_xml.find(qn("x:cellXfs"))
    if cell_xfs is None:
        cell_xfs = etree.SubElement(styles_xml, qn("x:cellXfs"), count="0")

    xfs = cell_xfs.findall(qn("x:xf"))

    # Get base xf to clone (or create from scratch)
    if base_style_idx is not None and 0 <= base_style_idx < len(xfs):
        base_xf = xfs[base_style_idx]
        # Check if base already has the desired protection
        protection = base_xf.find(qn("x:protection"))
        if protection is not None:
            current_locked = protection.get("locked", "1") == "1"
            if current_locked == locked:
                return base_style_idx  # Already has correct protection

        # Look for existing style that matches base + desired protection
        for i, xf in enumerate(xfs):
            if _styles_match_except_protection(base_xf, xf):
                protection = xf.find(qn("x:protection"))
                if protection is not None:
                    xf_locked = protection.get("locked", "1") == "1"
                    if xf_locked == locked:
                        return i

        # Clone the base xf
        new_xf = copy.deepcopy(base_xf)
    else:
        # Create minimal style
        new_xf = etree.Element(qn("x:xf"))

    # Set/update protection
    protection = new_xf.find(qn("x:protection"))
    if protection is None:
        protection = etree.SubElement(new_xf, qn("x:protection"))
    protection.set("locked", "1" if locked else "0")
    new_xf.set("applyProtection", "1")

    # Append and update count
    cell_xfs.append(new_xf)
    count = len(cell_xfs.findall(qn("x:xf")))
    cell_xfs.set("count", str(count))

    pkg.mark_xml_dirty("/xl/styles.xml")
    return count - 1


def _styles_match_except_protection(xf1: etree._Element, xf2: etree._Element) -> bool:
    """Check if two xf elements match except for protection settings."""
    # Compare key attributes
    for attr in ["numFmtId", "fontId", "fillId", "borderId"]:
        if xf1.get(attr) != xf2.get(attr):
            return False
    return True


def lock_cells(pkg: ExcelPackage, sheet_name: str, range_ref: str) -> None:
    """Lock cells in the specified range.

    Locked cells cannot be edited when the sheet is protected.
    By default, all cells start as locked - use unlock_cells to make them editable.

    Args:
        sheet_name: Name of the sheet.
        range_ref: Cell reference or range (e.g., "A1" or "A1:B10").
    """
    _set_cell_protection(pkg, sheet_name, range_ref, locked=True)


def unlock_cells(pkg: ExcelPackage, sheet_name: str, range_ref: str) -> None:
    """Unlock cells in the specified range.

    Unlocked cells can be edited even when the sheet is protected.

    Args:
        sheet_name: Name of the sheet.
        range_ref: Cell reference or range (e.g., "A1" or "A1:B10").
    """
    _set_cell_protection(pkg, sheet_name, range_ref, locked=False)


def _set_cell_protection(
    pkg: ExcelPackage, sheet_name: str, range_ref: str, locked: bool
) -> None:
    """Set protection state for cells in a range, preserving existing styles."""
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)
    sheet_data = sheet_xml.find(qn("x:sheetData"))

    if sheet_data is None:
        sheet_data = etree.SubElement(sheet_xml, qn("x:sheetData"))

    # Parse range
    if ":" in range_ref:
        start_ref, end_ref = parse_range_ref(range_ref)
    else:
        start_ref = end_ref = range_ref

    start_col, start_row, _, _ = parse_cell_ref(start_ref)
    end_col, end_row, _, _ = parse_cell_ref(end_ref)

    start_col_idx = column_letter_to_index(start_col)
    end_col_idx = column_letter_to_index(end_col)

    # Normalize range
    if start_col_idx > end_col_idx:
        start_col_idx, end_col_idx = end_col_idx, start_col_idx
    if start_row > end_row:
        start_row, end_row = end_row, start_row

    # Cache style mappings to avoid redundant style creation
    style_cache: dict[int | None, int] = {}

    # Apply protection to each cell in range
    for row_num in range(start_row, end_row + 1):
        # Find or create row
        row_el = None
        for r in sheet_data.findall(qn("x:row")):
            if int(r.get("r", "0")) == row_num:
                row_el = r
                break

        if row_el is None:
            row_el = etree.SubElement(sheet_data, qn("x:row"), r=str(row_num))

        for col_idx in range(start_col_idx, end_col_idx + 1):
            cell_ref = make_cell_ref(col_idx, row_num)

            # Find or create cell
            cell_el = None
            for c in row_el.findall(qn("x:c")):
                if c.get("r") == cell_ref:
                    cell_el = c
                    break

            if cell_el is None:
                cell_el = etree.SubElement(row_el, qn("x:c"), r=cell_ref)

            # Get existing style index and clone with new protection
            existing_style = cell_el.get("s")
            base_idx = int(existing_style) if existing_style else None

            if base_idx not in style_cache:
                style_cache[base_idx] = _clone_style_with_protection(
                    pkg, base_idx, locked
                )

            cell_el.set("s", str(style_cache[base_idx]))

    pkg.mark_xml_dirty(sheet_path)


def is_cell_locked(pkg: ExcelPackage, sheet_name: str, cell_ref: str) -> bool:
    """Check if a cell is locked.

    Returns: True if the cell is locked (default is True for all cells).
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_data = sheet_xml.find(qn("x:sheetData"))

    if sheet_data is None:
        return True  # Default is locked

    col, row, _, _ = parse_cell_ref(cell_ref)

    # Find cell
    for row_el in sheet_data.findall(qn("x:row")):
        if int(row_el.get("r", "0")) != row:
            continue
        for cell_el in row_el.findall(qn("x:c")):
            if cell_el.get("r") == cell_ref:
                style_idx = cell_el.get("s")
                if style_idx is None:
                    return True  # Default

                # Look up style
                styles_xml = pkg.get_xml("/xl/styles.xml")
                cell_xfs = styles_xml.find(qn("x:cellXfs"))
                if cell_xfs is not None:
                    xfs = cell_xfs.findall(qn("x:xf"))
                    idx = int(style_idx)
                    if 0 <= idx < len(xfs):
                        xf = xfs[idx]
                        protection = xf.find(qn("x:protection"))
                        if protection is not None:
                            return protection.get("locked", "1") == "1"
                return True  # Default

    return True  # Cell doesn't exist, default is locked
