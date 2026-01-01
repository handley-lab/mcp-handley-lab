"""Sheet operations for Excel.

Listing sheets, getting sheet info, and determining used ranges.
"""

from __future__ import annotations

import copy

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import CT, NSMAP, RT, qn
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


# =============================================================================
# Write Operations
# =============================================================================


def add_sheet(pkg: ExcelPackage, name: str) -> SheetInfo:
    """Add a new sheet to the workbook.

    Returns: SheetInfo for the new sheet.
    Raises: ValueError if sheet name already exists.
    """
    # Check for duplicate name
    for info in list_sheets(pkg):
        if info.name == name:
            raise ValueError(f"Sheet already exists: {name}")

    # Get next sheet ID
    workbook = pkg.workbook_xml
    sheets_el = workbook.find(qn("x:sheets"))
    if sheets_el is None:
        sheets_el = etree.SubElement(workbook, qn("x:sheets"))

    max_sheet_id = 0
    for sheet in sheets_el.findall(qn("x:sheet")):
        sheet_id = int(sheet.get("sheetId", "0"))
        max_sheet_id = max(max_sheet_id, sheet_id)

    new_sheet_id = max_sheet_id + 1
    new_index = len(sheets_el)

    # Create worksheet XML
    worksheet = etree.Element(qn("x:worksheet"), nsmap={None: NSMAP["x"]})
    etree.SubElement(worksheet, qn("x:sheetData"))

    # Determine sheet path
    sheet_path = f"/xl/worksheets/sheet{new_sheet_id}.xml"
    pkg.set_xml(sheet_path, worksheet, CT.SML_WORKSHEET)

    # Create relationship
    rId = pkg.relate_to(
        pkg.workbook_path, f"worksheets/sheet{new_sheet_id}.xml", RT.WORKSHEET
    )

    # Add sheet element to workbook
    etree.SubElement(
        sheets_el,
        qn("x:sheet"),
        name=name,
        sheetId=str(new_sheet_id),
        attrib={qn("r:id"): rId},
    )

    pkg.mark_xml_dirty(pkg.workbook_path)

    return SheetInfo(name=name, index=new_index)


def rename_sheet(pkg: ExcelPackage, old_name: str, new_name: str) -> None:
    """Rename a sheet.

    Raises: KeyError if sheet not found, ValueError if new name exists.
    """
    # Check new name doesn't exist
    for info in list_sheets(pkg):
        if info.name == new_name:
            raise ValueError(f"Sheet already exists: {new_name}")

    # Find and rename
    workbook = pkg.workbook_xml
    sheets_el = workbook.find(qn("x:sheets"))
    if sheets_el is None:
        raise KeyError(f"Sheet not found: {old_name}")

    found = False
    for sheet in sheets_el.findall(qn("x:sheet")):
        if sheet.get("name") == old_name:
            sheet.set("name", new_name)
            found = True
            break

    if not found:
        raise KeyError(f"Sheet not found: {old_name}")

    pkg.mark_xml_dirty(pkg.workbook_path)


def delete_sheet(pkg: ExcelPackage, name: str) -> None:
    """Delete a sheet from the workbook.

    Raises: KeyError if sheet not found, ValueError if last sheet.
    """
    workbook = pkg.workbook_xml
    sheets_el = workbook.find(qn("x:sheets"))
    if sheets_el is None:
        raise KeyError(f"Sheet not found: {name}")

    # Find the sheet and its rId first
    sheet_el = None
    rId = None
    for sheet in sheets_el.findall(qn("x:sheet")):
        if sheet.get("name") == name:
            sheet_el = sheet
            rId = sheet.get(qn("r:id"))
            break

    if sheet_el is None:
        raise KeyError(f"Sheet not found: {name}")

    # Now check if it's the last sheet
    sheets = list_sheets(pkg)
    if len(sheets) <= 1:
        raise ValueError("Cannot delete the last sheet")

    # Get sheet path before removing
    sheet_path = pkg.resolve_rel_target(pkg.workbook_path, rId)

    # Remove sheet element from workbook
    sheets_el.remove(sheet_el)
    pkg.mark_xml_dirty(pkg.workbook_path)

    # Remove relationship
    pkg.remove_rel(pkg.workbook_path, rId)

    # Remove sheet part
    pkg.drop_part(sheet_path)


def copy_sheet(pkg: ExcelPackage, source_name: str, new_name: str) -> SheetInfo:
    """Copy a sheet to a new sheet.

    Returns: SheetInfo for the new sheet.
    Raises: KeyError if source not found, ValueError if new name exists.
    """
    # Check source exists
    source_info = None
    for info in list_sheets(pkg):
        if info.name == source_name:
            source_info = info
        if info.name == new_name:
            raise ValueError(f"Sheet already exists: {new_name}")

    if source_info is None:
        raise KeyError(f"Sheet not found: {source_name}")

    # Get source sheet XML
    source_xml = pkg.get_sheet_xml(source_name)

    # Deep copy the XML
    new_xml = copy.deepcopy(source_xml)

    # Get next sheet ID
    workbook = pkg.workbook_xml
    sheets_el = workbook.find(qn("x:sheets"))

    max_sheet_id = 0
    for sheet in sheets_el.findall(qn("x:sheet")):
        sheet_id = int(sheet.get("sheetId", "0"))
        max_sheet_id = max(max_sheet_id, sheet_id)

    new_sheet_id = max_sheet_id + 1
    new_index = len(sheets_el)

    # Save new sheet
    sheet_path = f"/xl/worksheets/sheet{new_sheet_id}.xml"
    pkg.set_xml(sheet_path, new_xml, CT.SML_WORKSHEET)

    # Create relationship
    rId = pkg.relate_to(
        pkg.workbook_path, f"worksheets/sheet{new_sheet_id}.xml", RT.WORKSHEET
    )

    # Add sheet element
    etree.SubElement(
        sheets_el,
        qn("x:sheet"),
        name=new_name,
        sheetId=str(new_sheet_id),
        attrib={qn("r:id"): rId},
    )

    pkg.mark_xml_dirty(pkg.workbook_path)

    return SheetInfo(name=new_name, index=new_index)
