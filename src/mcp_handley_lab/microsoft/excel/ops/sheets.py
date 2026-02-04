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
from mcp_handley_lab.microsoft.excel.ops.core import (
    get_sheet_path as _get_sheet_path,
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
    """Get sheet info by 0-based index."""
    return list_sheets(pkg)[idx]


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

            col, cell_row, _, _ = parse_cell_ref(cell_ref)
            col_idx = column_letter_to_index(col)

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
    """
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

    Raises: KeyError if sheet not found.
    """
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
    Raises: KeyError if source not found.
    """

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


# =============================================================================
# Column and Row Sizing
# =============================================================================


def _get_or_create_cols(sheet_xml: etree._Element) -> etree._Element:
    """Get or create <cols> element, positioned after sheetViews/before sheetData."""
    cols = sheet_xml.find(qn("x:cols"))
    if cols is not None:
        return cols

    # Create <cols> element and insert in correct position
    cols = etree.Element(qn("x:cols"))

    # Find insertion point: after sheetViews, sheetFormatPr, before sheetData
    sheet_data = sheet_xml.find(qn("x:sheetData"))
    if sheet_data is not None:
        idx = list(sheet_xml).index(sheet_data)
        sheet_xml.insert(idx, cols)
    else:
        sheet_xml.append(cols)

    return cols


def set_column_width(
    pkg: ExcelPackage, sheet_name: str, col: str | int, width: float
) -> None:
    """Set the width of a column.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        col: Column letter (e.g., "A") or 1-based column index.
        width: Column width in character units (Excel's width unit).

    Note: Excel column width is measured in character widths of the default font.
    A width of 8.43 is the default. Width 0 hides the column.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    cols = _get_or_create_cols(sheet_xml)

    # Normalize column to 1-based index
    col_idx = column_letter_to_index(col) if isinstance(col, str) else col

    # Find existing col element for this column
    for col_el in list(cols.findall(qn("x:col"))):
        min_col = int(col_el.get("min", "0"))
        max_col = int(col_el.get("max", "0"))
        if min_col == col_idx == max_col:
            # Exact match - update existing
            col_el.set("width", str(width))
            col_el.set("customWidth", "1")
            pkg.mark_xml_dirty(_get_sheet_path(pkg, sheet_name))
            return
        elif min_col <= col_idx <= max_col:
            # Column is part of a range - split it properly
            # Save original attributes to copy to split elements
            orig_attribs = dict(col_el.attrib)
            del orig_attribs["min"]
            del orig_attribs["max"]

            # Remove the original range
            cols.remove(col_el)

            # Create elements for the split ranges
            if min_col < col_idx:
                # Left portion: min to col_idx-1
                left_el = etree.SubElement(cols, qn("x:col"))
                left_el.set("min", str(min_col))
                left_el.set("max", str(col_idx - 1))
                for k, v in orig_attribs.items():
                    left_el.set(k, v)

            # Middle: the target column with new width
            mid_el = etree.SubElement(cols, qn("x:col"))
            mid_el.set("min", str(col_idx))
            mid_el.set("max", str(col_idx))
            mid_el.set("width", str(width))
            mid_el.set("customWidth", "1")

            if max_col > col_idx:
                # Right portion: col_idx+1 to max
                right_el = etree.SubElement(cols, qn("x:col"))
                right_el.set("min", str(col_idx + 1))
                right_el.set("max", str(max_col))
                for k, v in orig_attribs.items():
                    right_el.set(k, v)

            pkg.mark_xml_dirty(_get_sheet_path(pkg, sheet_name))
            return

    # No existing col element covers this column - add new
    col_el = etree.SubElement(cols, qn("x:col"))
    col_el.set("min", str(col_idx))
    col_el.set("max", str(col_idx))
    col_el.set("width", str(width))
    col_el.set("customWidth", "1")

    pkg.mark_xml_dirty(_get_sheet_path(pkg, sheet_name))


def get_column_width(pkg: ExcelPackage, sheet_name: str, col: str | int) -> float:
    """Get the width of a column.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        col: Column letter (e.g., "A") or 1-based column index.

    Returns: Column width in character units, or default width (8.43) if not set.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)

    # Normalize column to 1-based index
    col_idx = column_letter_to_index(col) if isinstance(col, str) else col

    # Check sheetFormatPr for default column width
    default_width = 8.43  # Excel default
    fmt_pr = sheet_xml.find(qn("x:sheetFormatPr"))
    if fmt_pr is not None:
        default_col_width = fmt_pr.get("defaultColWidth")
        if default_col_width:
            default_width = float(default_col_width)

    # Find col element
    cols = sheet_xml.find(qn("x:cols"))
    if cols is None:
        return default_width

    for col_el in cols.findall(qn("x:col")):
        min_col = int(col_el.get("min", "0"))
        max_col = int(col_el.get("max", "0"))
        if min_col <= col_idx <= max_col:
            width = col_el.get("width")
            if width:
                return float(width)

    return default_width


def set_row_height(pkg: ExcelPackage, sheet_name: str, row: int, height: float) -> None:
    """Set the height of a row.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        row: 1-based row number.
        height: Row height in points.

    Note: Excel row height is measured in points. Default is about 15 points.
    Height 0 hides the row.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_data = sheet_xml.find(qn("x:sheetData"))
    if sheet_data is None:
        sheet_data = etree.SubElement(sheet_xml, qn("x:sheetData"))

    # Find or create row element
    row_el = None
    for r in sheet_data.findall(qn("x:row")):
        if int(r.get("r", "0")) == row:
            row_el = r
            break

    if row_el is None:
        # Create new row element in sorted position
        row_el = etree.Element(qn("x:row"))
        row_el.set("r", str(row))

        # Insert in sorted order
        inserted = False
        for idx, r in enumerate(sheet_data.findall(qn("x:row"))):
            if int(r.get("r", "0")) > row:
                sheet_data.insert(idx, row_el)
                inserted = True
                break
        if not inserted:
            sheet_data.append(row_el)

    row_el.set("ht", str(height))
    row_el.set("customHeight", "1")

    pkg.mark_xml_dirty(_get_sheet_path(pkg, sheet_name))


def get_row_height(pkg: ExcelPackage, sheet_name: str, row: int) -> float:
    """Get the height of a row.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        row: 1-based row number.

    Returns: Row height in points, or default height (15) if not set.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)

    # Check sheetFormatPr for default row height
    default_height = 15.0  # Excel default in points
    fmt_pr = sheet_xml.find(qn("x:sheetFormatPr"))
    if fmt_pr is not None:
        default_row_height = fmt_pr.get("defaultRowHeight")
        if default_row_height:
            default_height = float(default_row_height)

    # Find row element
    sheet_data = sheet_xml.find(qn("x:sheetData"))
    if sheet_data is None:
        return default_height

    for r in sheet_data.findall(qn("x:row")):
        if int(r.get("r", "0")) == row:
            ht = r.get("ht")
            if ht:
                return float(ht)
            break

    return default_height
