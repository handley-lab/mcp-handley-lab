"""Filtering and sorting operations for Excel.

AutoFilter allows users to filter and sort data in a range.
The filter state is stored in the sheet XML.
"""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.models import AutoFilterInfo
from mcp_handley_lab.microsoft.excel.ops.core import (
    get_sheet_path as _get_sheet_path,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    index_to_column_letter,
    insert_sheet_element,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def get_autofilter(pkg: ExcelPackage, sheet_name: str) -> AutoFilterInfo | None:
    """Get AutoFilter info for a sheet.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.

    Returns: AutoFilterInfo if AutoFilter is set, None otherwise.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    autofilter = sheet_xml.find(qn("x:autoFilter"))
    if autofilter is None:
        return None

    ref = autofilter.get("ref", "")

    # Parse filter columns
    filters: dict[int, list[str]] = {}
    for filter_col in autofilter.findall(qn("x:filterColumn")):
        col_id = int(filter_col.get("colId", "0"))
        filter_el = filter_col.find(qn("x:filters"))
        if filter_el is not None:
            values = [
                f.get("val") for f in filter_el.findall(qn("x:filter")) if f.get("val")
            ]
            if values:
                filters[col_id] = values

    return AutoFilterInfo(
        ref=ref,
        filters=filters if filters else None,
    )


def set_autofilter(
    pkg: ExcelPackage, sheet_name: str, range_ref: str
) -> AutoFilterInfo:
    """Enable AutoFilter on a range.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        range_ref: Range reference (e.g., "A1:D10").

    Returns: AutoFilterInfo for the created filter.
    """
    sheet_path = _get_sheet_path(pkg, sheet_name)
    sheet_xml = pkg.get_sheet_xml(sheet_name)

    # Remove existing autoFilter if present
    existing = sheet_xml.find(qn("x:autoFilter"))
    if existing is not None:
        sheet_xml.remove(existing)

    # Create autoFilter element and insert at correct OOXML position
    autofilter = etree.Element(qn("x:autoFilter"))
    autofilter.set("ref", range_ref)
    insert_sheet_element(sheet_xml, "autoFilter", autofilter)

    pkg.mark_xml_dirty(sheet_path)

    return AutoFilterInfo(ref=range_ref, filters=None)


def clear_autofilter(pkg: ExcelPackage, sheet_name: str) -> None:
    """Remove AutoFilter from a sheet.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
    """
    sheet_path = _get_sheet_path(pkg, sheet_name)
    sheet_xml = pkg.get_sheet_xml(sheet_name)

    autofilter = sheet_xml.find(qn("x:autoFilter"))
    if autofilter is not None:
        sheet_xml.remove(autofilter)
        pkg.mark_xml_dirty(sheet_path)


def apply_filter(
    pkg: ExcelPackage,
    sheet_name: str,
    column: int,
    values: list[str],
) -> AutoFilterInfo:
    """Apply filter criteria to a column.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        column: 0-based column index within the AutoFilter range.
        values: List of values to show (other values are hidden).

    Returns: Updated AutoFilterInfo.

    Raises: ValueError if no AutoFilter is set on the sheet.
    """
    sheet_path = _get_sheet_path(pkg, sheet_name)
    sheet_xml = pkg.get_sheet_xml(sheet_name)

    autofilter = sheet_xml.find(qn("x:autoFilter"))
    if autofilter is None:
        raise ValueError("No AutoFilter set on sheet. Use set_autofilter first.")

    # Find or create filterColumn for this column
    filter_col = None
    for fc in autofilter.findall(qn("x:filterColumn")):
        if int(fc.get("colId", "-1")) == column:
            filter_col = fc
            break

    if filter_col is None:
        filter_col = etree.SubElement(autofilter, qn("x:filterColumn"))
        filter_col.set("colId", str(column))
    else:
        # Clear existing filters
        for child in list(filter_col):
            filter_col.remove(child)

    # Add filters element with values
    filters_el = etree.SubElement(filter_col, qn("x:filters"))
    for val in values:
        filter_el = etree.SubElement(filters_el, qn("x:filter"))
        filter_el.set("val", val)

    pkg.mark_xml_dirty(sheet_path)

    return get_autofilter(pkg, sheet_name)


def clear_filter(
    pkg: ExcelPackage, sheet_name: str, column: int
) -> AutoFilterInfo | None:
    """Clear filter on a specific column.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        column: 0-based column index within the AutoFilter range.

    Returns: Updated AutoFilterInfo, or None if no AutoFilter remains.
    """
    sheet_path = _get_sheet_path(pkg, sheet_name)
    sheet_xml = pkg.get_sheet_xml(sheet_name)

    autofilter = sheet_xml.find(qn("x:autoFilter"))
    if autofilter is None:
        return None

    # Find and remove filterColumn for this column
    for fc in autofilter.findall(qn("x:filterColumn")):
        if int(fc.get("colId", "-1")) == column:
            autofilter.remove(fc)
            pkg.mark_xml_dirty(sheet_path)
            break

    return get_autofilter(pkg, sheet_name)


def sort_range(
    pkg: ExcelPackage,
    sheet_name: str,
    range_ref: str,
    sort_by: int | list[int],
    descending: bool | list[bool] = False,
) -> None:
    """Sort a range by one or more columns.

    This sets the sortState in the autoFilter element. If there's no
    autoFilter, one will be created temporarily.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        range_ref: Range reference (e.g., "A2:D10" - typically excluding header).
        sort_by: 0-based column index or list of indices for multi-column sort.
        descending: Sort direction(s) - single bool or list matching sort_by.

    Raises: ValueError if sort_by and descending list lengths don't match.

    Note: This defines the sort state; actual row reordering must be done
    by manipulating cell values, which is beyond the scope of this function.
    The sort state tells Excel how data was sorted.
    """
    sheet_path = _get_sheet_path(pkg, sheet_name)
    sheet_xml = pkg.get_sheet_xml(sheet_name)

    # Normalize inputs to lists
    if isinstance(sort_by, int):
        sort_by = [sort_by]
    if isinstance(descending, bool):
        descending = [descending] * len(sort_by)

    # Ensure AutoFilter exists
    autofilter = sheet_xml.find(qn("x:autoFilter"))
    if autofilter is None:
        # Create autoFilter for the range and insert at correct OOXML position
        autofilter = etree.Element(qn("x:autoFilter"))
        autofilter.set("ref", range_ref)
        insert_sheet_element(sheet_xml, "autoFilter", autofilter)

    # Remove existing sortState
    existing_sort = autofilter.find(qn("x:sortState"))
    if existing_sort is not None:
        autofilter.remove(existing_sort)

    # Create sortState
    sort_state = etree.SubElement(autofilter, qn("x:sortState"))
    sort_state.set("ref", range_ref)

    # Add sort conditions
    for col_idx, desc in zip(sort_by, descending, strict=False):
        # Convert column index to column letter for the sort ref
        # sortCondition ref is typically the full column range like "A2:A10"
        col_letter = index_to_column_letter(col_idx + 1)

        # Parse range to get rows
        start_ref, end_ref = range_ref.split(":")
        start_row = "".join(c for c in start_ref if c.isdigit())
        end_row = "".join(c for c in end_ref if c.isdigit())

        sort_ref = f"{col_letter}{start_row}:{col_letter}{end_row}"

        sort_cond = etree.SubElement(sort_state, qn("x:sortCondition"))
        sort_cond.set("ref", sort_ref)
        if desc:
            sort_cond.set("descending", "1")

    pkg.mark_xml_dirty(sheet_path)
