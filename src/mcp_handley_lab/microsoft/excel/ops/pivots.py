"""Pivot table operations for Excel.

Excel pivot tables have a complex structure:
- pivotTable*.xml: The pivot table definition (fields, layout)
- pivotCacheDefinition*.xml: Describes the source data structure
- pivotCacheRecords*.xml: Cached values from source data

Key concepts:
- Cache: Stores unique values from source data for efficient filtering
- Fields: Columns from source data (become rows/columns/values in pivot)
- Items: Unique values within a field
- Data fields: Aggregated values (sum, count, average, etc.)
"""

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import CT, RT, qn
from mcp_handley_lab.microsoft.excel.models import PivotInfo
from mcp_handley_lab.microsoft.excel.ops.cells import get_cell_value
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    index_to_column_letter,
    make_pivot_id,
    parse_cell_ref,
    parse_range_ref,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    get_sheet_path as _get_sheet_path,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def list_pivots(pkg: ExcelPackage, sheet_name: str) -> list[PivotInfo]:
    """List all pivot tables on a sheet.

    Args:
        pkg: Excel package
        sheet_name: Sheet name

    Returns:
        List of pivot table info
    """
    result = []
    sheet_path = _get_sheet_path(pkg, sheet_name)

    # Get sheet relationships
    sheet_rels = pkg.get_rels(sheet_path)

    # Find all pivot table relationships
    for rel in sheet_rels.all_for_reltype(RT.PIVOT_TABLE):
        pivot_path = pkg.resolve_rel_target(sheet_path, rel.rId)
        pivot_xml = pkg.get_xml(pivot_path)

        # Extract pivot table info
        name = pivot_xml.get("name", "")

        # Get location (where pivot table renders)
        location_elem = pivot_xml.find(qn("x:location"))
        location = ""
        if location_elem is not None:
            location = location_elem.get("ref", "")

        # Get cache definition to find source data range
        cache_id = pivot_xml.get("cacheId")
        data_range = _get_pivot_data_range(pkg, cache_id) if cache_id else ""

        # Extract field info
        row_fields = []
        col_fields = []
        value_fields = []

        field_names = _get_field_names_from_cache(pkg, cache_id) if cache_id else []

        # Row fields
        row_fields_elem = pivot_xml.find(qn("x:rowFields"))
        if row_fields_elem is not None:
            for field in row_fields_elem.findall(qn("x:field")):
                x = field.get("x")
                if x is not None:
                    idx = int(x)
                    if 0 <= idx < len(field_names):
                        row_fields.append(field_names[idx])

        # Column fields
        col_fields_elem = pivot_xml.find(qn("x:colFields"))
        if col_fields_elem is not None:
            for field in col_fields_elem.findall(qn("x:field")):
                x = field.get("x")
                if x is not None:
                    idx = int(x)
                    if 0 <= idx < len(field_names):
                        col_fields.append(field_names[idx])

        # Data (value) fields
        data_fields_elem = pivot_xml.find(qn("x:dataFields"))
        if data_fields_elem is not None:
            for data_field in data_fields_elem.findall(qn("x:dataField")):
                fld = data_field.get("fld")
                if fld is not None:
                    idx = int(fld)
                    if 0 <= idx < len(field_names):
                        value_fields.append(field_names[idx])

        result.append(
            PivotInfo(
                id=make_pivot_id(pivot_path),
                name=name,
                data_range=data_range,
                location=location,
                row_fields=row_fields,
                col_fields=col_fields,
                value_fields=value_fields,
            )
        )

    return result


def _get_cache_path_by_id(pkg: ExcelPackage, cache_id: str) -> str | None:
    """Get cache definition path by cacheId using pivotCaches in workbook.xml.

    Args:
        pkg: Excel package
        cache_id: Cache ID from pivot table's cacheId attribute

    Returns:
        Path to cache definition or None if not found
    """
    workbook_path = "/xl/workbook.xml"
    workbook_xml = pkg.get_xml(workbook_path)
    pkg.get_rels(workbook_path)

    # Find <pivotCaches> element
    pivot_caches = workbook_xml.find(qn("x:pivotCaches"))
    if pivot_caches is None:
        return None

    # Find pivotCache with matching cacheId
    for pc in pivot_caches.findall(qn("x:pivotCache")):
        if pc.get("cacheId") == cache_id:
            # Get relationship ID
            r_id = pc.get(qn("r:id"))
            if r_id:
                return pkg.resolve_rel_target(workbook_path, r_id)

    return None


def _get_pivot_data_range(pkg: ExcelPackage, cache_id: str) -> str:
    """Get source data range from pivot cache.

    Args:
        pkg: Excel package
        cache_id: Cache ID from pivot table

    Returns:
        Source data range like "'Sheet1'!A1:D10"
    """
    cache_path = _get_cache_path_by_id(pkg, cache_id)
    if cache_path is None:
        return ""

    cache_xml = pkg.get_xml(cache_path)

    # Look for cacheSource with worksheetSource
    cache_source = cache_xml.find(qn("x:cacheSource"))
    if cache_source is not None:
        ws_source = cache_source.find(qn("x:worksheetSource"))
        if ws_source is not None:
            ref = ws_source.get("ref", "")
            sheet = ws_source.get("sheet", "")
            if sheet and ref:
                return f"'{sheet}'!{ref}"
            return ref

    return ""


def _get_field_names_from_cache(pkg: ExcelPackage, cache_id: str) -> list[str]:
    """Get field names from pivot cache definition.

    Args:
        pkg: Excel package
        cache_id: Cache ID

    Returns:
        List of field names
    """
    cache_path = _get_cache_path_by_id(pkg, cache_id)
    if cache_path is None:
        return []

    cache_xml = pkg.get_xml(cache_path)

    cache_fields = cache_xml.find(qn("x:cacheFields"))
    if cache_fields is not None:
        return [
            field.get("name", "") for field in cache_fields.findall(qn("x:cacheField"))
        ]

    return []


def create_pivot(
    pkg: ExcelPackage,
    sheet_name: str,
    data_range: str,
    dest: str,
    rows: list[str],
    cols: list[str],
    values: list[str],
    name: str | None = None,
    agg_func: str = "sum",
) -> PivotInfo:
    """Create a new pivot table.

    Args:
        pkg: Excel package
        sheet_name: Sheet where pivot will be placed
        data_range: Source data range (e.g., "'Sheet1'!A1:D10" or "A1:D10")
        dest: Top-left cell for pivot table placement
        rows: Field names for row labels
        cols: Field names for column labels
        values: Field names for values (aggregated)
        name: Optional pivot table name
        agg_func: Aggregation function (sum, count, average, min, max)

    Returns:
        PivotInfo for created pivot table
    """
    # Parse data range to get sheet and ref
    source_sheet, source_ref = _parse_data_range(data_range, sheet_name)

    # Get field names from source data (header row)
    field_names = _get_source_headers(pkg, source_sheet, source_ref)

    sheet_path = _get_sheet_path(pkg, sheet_name)

    # Generate IDs for new parts
    cache_num = _next_cache_num(pkg)
    pivot_num = _next_pivot_num(pkg)
    pivot_name = name or f"PivotTable{pivot_num}"

    # Create paths
    cache_def_path = f"/xl/pivotCache/pivotCacheDefinition{cache_num}.xml"
    cache_rec_path = f"/xl/pivotCache/pivotCacheRecords{cache_num}.xml"
    pivot_path = f"/xl/pivotTables/pivotTable{pivot_num}.xml"

    # Create cache records first to get record count
    cache_rec_xml = _create_cache_records(pkg, source_sheet, source_ref, field_names)
    record_count = cache_rec_xml.get("count", "0")

    # Create cache definition with correct record count
    cache_def_xml = _create_cache_definition(
        source_sheet, source_ref, field_names, cache_num
    )
    cache_def_xml.set("recordCount", record_count)
    pkg.set_xml(cache_def_path, cache_def_xml, CT.SML_PIVOT_CACHE_DEF)

    # Save cache records
    pkg.set_xml(cache_rec_path, cache_rec_xml, CT.SML_PIVOT_CACHE_REC)

    # Link cache definition to records (relative path within pivotCache folder)
    pkg.relate_to(
        cache_def_path, f"pivotCacheRecords{cache_num}.xml", RT.PIVOT_CACHE_REC
    )

    # Add cache to workbook relationships
    workbook_path = "/xl/workbook.xml"
    cache_rId = pkg.relate_to(
        workbook_path,
        f"pivotCache/pivotCacheDefinition{cache_num}.xml",
        RT.PIVOT_CACHE_DEF,
    )

    # Add pivotCaches to workbook
    _add_pivot_cache_to_workbook(pkg, cache_num, cache_rId)

    # Create pivot table
    pivot_xml = _create_pivot_table(
        field_names, rows, cols, values, pivot_name, dest, cache_num, agg_func
    )
    pkg.set_xml(pivot_path, pivot_xml, CT.SML_PIVOT_TABLE)

    # Link pivot table to cache definition (relative path from pivotTables to pivotCache)
    pkg.relate_to(
        pivot_path,
        f"../pivotCache/pivotCacheDefinition{cache_num}.xml",
        RT.PIVOT_CACHE_DEF,
    )

    # Add pivot table to sheet relationships (relative path from worksheets to pivotTables)
    pkg.relate_to(
        sheet_path, f"../pivotTables/pivotTable{pivot_num}.xml", RT.PIVOT_TABLE
    )

    return PivotInfo(
        id=make_pivot_id(pivot_path),
        name=pivot_name,
        data_range=f"'{source_sheet}'!{source_ref}",
        location=dest,
        row_fields=rows,
        col_fields=cols,
        value_fields=values,
    )


def _parse_data_range(data_range: str, default_sheet: str) -> tuple[str, str]:
    """Parse data range into sheet and ref.

    Args:
        data_range: Range like "'Sheet1'!A1:D10" or "A1:D10"
        default_sheet: Default sheet if not specified

    Returns:
        Tuple of (sheet_name, ref)
    """
    if "!" in data_range:
        parts = data_range.split("!", 1)
        sheet = parts[0].strip("'")
        ref = parts[1]
        return sheet, ref
    return default_sheet, data_range


def _parse_range_to_coords(range_ref: str) -> tuple[int, int, int, int]:
    """Parse range reference to (start_col, start_row, end_col, end_row).

    All values are 1-based indices.
    """
    start_ref, end_ref = parse_range_ref(range_ref)
    start_col_letter, start_row, _, _ = parse_cell_ref(start_ref)
    end_col_letter, end_row, _, _ = parse_cell_ref(end_ref)
    start_col = column_letter_to_index(start_col_letter)
    end_col = column_letter_to_index(end_col_letter)
    return start_col, start_row, end_col, end_row


def _get_source_headers(
    pkg: ExcelPackage, sheet_name: str, range_ref: str
) -> list[str]:
    """Get header names from first row of source data.

    Args:
        pkg: Excel package
        sheet_name: Sheet containing data
        range_ref: Range reference

    Returns:
        List of header names
    """
    start_col, start_row, end_col, end_row = _parse_range_to_coords(range_ref)

    headers = []
    for col in range(start_col, end_col + 1):
        cell_ref = f"{index_to_column_letter(col)}{start_row}"
        value = get_cell_value(pkg, sheet_name, cell_ref)
        headers.append(str(value) if value is not None else f"Field{col}")

    return headers


def _next_cache_num(pkg: ExcelPackage) -> int:
    """Find next available cache number."""
    max_num = 0
    for partname in pkg.iter_partnames():
        if partname.startswith(
            "/xl/pivotCache/pivotCacheDefinition"
        ) and partname.endswith(".xml"):
            try:
                num = int(partname[35:-4])  # Extract number from path
                max_num = max(max_num, num)
            except ValueError:
                pass
    return max_num + 1


def _next_pivot_num(pkg: ExcelPackage) -> int:
    """Find next available pivot table number."""
    max_num = 0
    for partname in pkg.iter_partnames():
        if partname.startswith("/xl/pivotTables/pivotTable") and partname.endswith(
            ".xml"
        ):
            try:
                num = int(partname[26:-4])  # Extract number from path
                max_num = max(max_num, num)
            except ValueError:
                pass
    return max_num + 1


def _create_cache_definition(
    source_sheet: str, source_ref: str, field_names: list[str], cache_id: int
) -> etree._Element:
    """Create pivot cache definition XML.

    Args:
        source_sheet: Source data sheet
        source_ref: Source data range
        field_names: Column headers
        cache_id: Cache ID

    Returns:
        Cache definition XML element
    """
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

    root = etree.Element(
        f"{{{ns}}}pivotCacheDefinition",
        nsmap={None: ns, "r": r_ns},
    )
    root.set("createdVersion", "6")
    root.set("minRefreshableVersion", "3")
    root.set("refreshedVersion", "6")
    root.set("recordCount", "0")

    # Cache source
    cache_source = etree.SubElement(root, f"{{{ns}}}cacheSource")
    cache_source.set("type", "worksheet")

    ws_source = etree.SubElement(cache_source, f"{{{ns}}}worksheetSource")
    ws_source.set("ref", source_ref)
    ws_source.set("sheet", source_sheet)

    # Cache fields
    cache_fields = etree.SubElement(root, f"{{{ns}}}cacheFields")
    cache_fields.set("count", str(len(field_names)))

    for name in field_names:
        cache_field = etree.SubElement(cache_fields, f"{{{ns}}}cacheField")
        cache_field.set("name", name)
        cache_field.set("numFmtId", "0")

        # Empty shared items (populated by Excel on refresh)
        shared_items = etree.SubElement(cache_field, f"{{{ns}}}sharedItems")
        shared_items.set("containsBlank", "1")

    return root


def _create_cache_records(
    pkg: ExcelPackage, source_sheet: str, source_ref: str, field_names: list[str]
) -> etree._Element:
    """Create pivot cache records XML.

    This stores the actual data values for the pivot cache.

    Args:
        pkg: Excel package
        source_sheet: Source data sheet
        source_ref: Source data range
        field_names: Column headers

    Returns:
        Cache records XML element
    """
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

    root = etree.Element(
        f"{{{ns}}}pivotCacheRecords",
        nsmap={None: ns},
    )

    # Parse range
    start_col, start_row, end_col, end_row = _parse_range_to_coords(source_ref)

    # Add records (skip header row)
    record_count = 0
    for row in range(start_row + 1, end_row + 1):
        record = etree.SubElement(root, f"{{{ns}}}r")

        for col in range(start_col, end_col + 1):
            cell_ref = f"{index_to_column_letter(col)}{row}"
            value = get_cell_value(pkg, source_sheet, cell_ref)

            if value is None:
                # Missing value
                etree.SubElement(record, f"{{{ns}}}m")
            elif isinstance(value, bool):
                elem = etree.SubElement(record, f"{{{ns}}}b")
                elem.set("v", "1" if value else "0")
            elif isinstance(value, int | float):
                elem = etree.SubElement(record, f"{{{ns}}}n")
                elem.set("v", str(value))
            else:
                elem = etree.SubElement(record, f"{{{ns}}}s")
                elem.set("v", str(value))

        record_count += 1

    root.set("count", str(record_count))

    return root


def _add_pivot_cache_to_workbook(
    pkg: ExcelPackage, cache_id: int, cache_rId: str
) -> None:
    """Add pivotCache element to workbook.xml.

    Args:
        pkg: Excel package
        cache_id: Cache ID
        cache_rId: Relationship ID
    """
    workbook_path = "/xl/workbook.xml"
    workbook_xml = pkg.get_xml(workbook_path)

    # Find or create pivotCaches element
    pivot_caches = workbook_xml.find(qn("x:pivotCaches"))
    if pivot_caches is None:
        # Insert after definedNames or sheets
        insert_after = workbook_xml.find(qn("x:definedNames"))
        if insert_after is None:
            insert_after = workbook_xml.find(qn("x:sheets"))

        pivot_caches = etree.Element(qn("x:pivotCaches"))

        if insert_after is not None:
            parent = insert_after.getparent()
            idx = list(parent).index(insert_after) + 1
            parent.insert(idx, pivot_caches)
        else:
            workbook_xml.append(pivot_caches)

    # Add pivotCache
    r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pivot_cache = etree.SubElement(pivot_caches, qn("x:pivotCache"))
    pivot_cache.set("cacheId", str(cache_id))
    pivot_cache.set(f"{{{r_ns}}}id", cache_rId)

    pkg.mark_xml_dirty(workbook_path)


def _create_pivot_table(
    field_names: list[str],
    rows: list[str],
    cols: list[str],
    values: list[str],
    name: str,
    dest: str,
    cache_id: int,
    agg_func: str,
) -> etree._Element:
    """Create pivot table XML.

    Args:
        field_names: All field names from source
        rows: Row field names
        cols: Column field names
        values: Value field names
        name: Pivot table name
        dest: Destination cell
        cache_id: Cache ID
        agg_func: Aggregation function

    Returns:
        Pivot table XML element
    """
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

    root = etree.Element(
        f"{{{ns}}}pivotTableDefinition",
        nsmap={None: ns},
    )
    root.set("name", name)
    root.set("cacheId", str(cache_id))
    root.set("applyNumberFormats", "0")
    root.set("applyBorderFormats", "0")
    root.set("applyFontFormats", "0")
    root.set("applyPatternFormats", "0")
    root.set("applyAlignmentFormats", "0")
    root.set("applyWidthHeightFormats", "1")
    root.set("dataCaption", "Values")
    root.set("updatedVersion", "6")
    root.set("minRefreshableVersion", "3")
    root.set("useAutoFormatting", "1")
    root.set("itemPrintTitles", "1")
    root.set("createdVersion", "6")
    root.set("indent", "0")
    root.set("outline", "1")
    root.set("outlineData", "1")
    root.set("multipleFieldFilters", "0")

    # Location
    location = etree.SubElement(root, f"{{{ns}}}location")
    location.set("ref", dest)
    location.set("firstHeaderRow", "1")
    location.set("firstDataRow", "1")
    location.set("firstDataCol", "1")

    # Pivot fields
    pivot_fields = etree.SubElement(root, f"{{{ns}}}pivotFields")
    pivot_fields.set("count", str(len(field_names)))

    for _i, field_name in enumerate(field_names):
        pivot_field = etree.SubElement(pivot_fields, f"{{{ns}}}pivotField")

        if field_name in rows:
            pivot_field.set("axis", "axisRow")
            pivot_field.set("showAll", "0")
            # Add items
            items = etree.SubElement(pivot_field, f"{{{ns}}}items")
            items.set("count", "1")
            item = etree.SubElement(items, f"{{{ns}}}item")
            item.set("t", "default")
        elif field_name in cols:
            pivot_field.set("axis", "axisCol")
            pivot_field.set("showAll", "0")
            items = etree.SubElement(pivot_field, f"{{{ns}}}items")
            items.set("count", "1")
            item = etree.SubElement(items, f"{{{ns}}}item")
            item.set("t", "default")
        elif field_name in values:
            pivot_field.set("dataField", "1")
            pivot_field.set("showAll", "0")
        else:
            pivot_field.set("showAll", "0")

    # Row fields
    if rows:
        row_fields = etree.SubElement(root, f"{{{ns}}}rowFields")
        row_fields.set("count", str(len(rows)))
        for field_name in rows:
            field = etree.SubElement(row_fields, f"{{{ns}}}field")
            field.set("x", str(field_names.index(field_name)))

    # Row items
    if rows:
        row_items = etree.SubElement(root, f"{{{ns}}}rowItems")
        row_items.set("count", "1")
        row_item = etree.SubElement(row_items, f"{{{ns}}}i")
        row_item.set("t", "grand")

    # Column fields
    if cols:
        col_fields = etree.SubElement(root, f"{{{ns}}}colFields")
        col_fields.set("count", str(len(cols)))
        for field_name in cols:
            field = etree.SubElement(col_fields, f"{{{ns}}}field")
            field.set("x", str(field_names.index(field_name)))

    # Column items
    if cols:
        col_items = etree.SubElement(root, f"{{{ns}}}colItems")
        col_items.set("count", "1")
        col_item = etree.SubElement(col_items, f"{{{ns}}}i")
        col_item.set("t", "grand")

    # Data fields
    if values:
        # Map aggregation function to display label
        agg_labels = {
            "sum": "Sum of",
            "count": "Count of",
            "average": "Average of",
            "min": "Min of",
            "max": "Max of",
        }
        agg_label = agg_labels.get(agg_func, "Sum of")

        data_fields = etree.SubElement(root, f"{{{ns}}}dataFields")
        data_fields.set("count", str(len(values)))
        for field_name in values:
            data_field = etree.SubElement(data_fields, f"{{{ns}}}dataField")
            data_field.set("name", f"{agg_label} {field_name}")
            data_field.set("fld", str(field_names.index(field_name)))
            data_field.set("subtotal", agg_func)

    # Pivot table style
    pivot_table_style = etree.SubElement(root, f"{{{ns}}}pivotTableStyleInfo")
    pivot_table_style.set("name", "PivotStyleLight16")
    pivot_table_style.set("showRowHeaders", "1")
    pivot_table_style.set("showColHeaders", "1")
    pivot_table_style.set("showRowStripes", "0")
    pivot_table_style.set("showColStripes", "0")
    pivot_table_style.set("showLastColumn", "1")

    return root


def delete_pivot(pkg: ExcelPackage, sheet_name: str, pivot_id: str) -> None:
    """Delete a pivot table.

    Args:
        pkg: Excel package
        sheet_name: Sheet containing the pivot table
        pivot_id: Pivot table ID (from PivotInfo.id)
    """
    sheet_path = _get_sheet_path(pkg, sheet_name)

    # Find pivot table
    sheet_rels = pkg.get_rels(sheet_path)
    pivot_path = None
    pivot_rId = None

    for rel in sheet_rels.all_for_reltype(RT.PIVOT_TABLE):
        path = pkg.resolve_rel_target(sheet_path, rel.rId)
        if make_pivot_id(path) == pivot_id:
            pivot_path = path
            pivot_rId = rel.rId
            break

    if pivot_path is None:
        raise KeyError(f"Pivot table not found: {pivot_id}")

    # Get cache path from pivot table
    pivot_rels = pkg.get_rels(pivot_path)
    cache_path = None
    for rel in pivot_rels.all_for_reltype(RT.PIVOT_CACHE_DEF):
        cache_path = pkg.resolve_rel_target(pivot_path, rel.rId)
        break

    # Remove pivot table
    pkg.drop_part(pivot_path)
    pkg.remove_rel(sheet_path, pivot_rId)

    # Remove cache (if not used by other pivots)
    if cache_path:
        # Check if ANY other pivot (on ALL sheets) uses this cache
        cache_in_use = False
        for _name, _rId, partname in pkg.get_sheet_paths():
            s_rels = pkg.get_rels(partname)
            for rel in s_rels.all_for_reltype(RT.PIVOT_TABLE):
                p_path = pkg.resolve_rel_target(partname, rel.rId)
                # Skip the pivot we just deleted
                if p_path == pivot_path:
                    continue
                p_rels = pkg.get_rels(p_path)
                for prel in p_rels.all_for_reltype(RT.PIVOT_CACHE_DEF):
                    if pkg.resolve_rel_target(p_path, prel.rId) == cache_path:
                        cache_in_use = True
                        break
                if cache_in_use:
                    break
            if cache_in_use:
                break

        if not cache_in_use:
            # Get cache records path
            cache_rels = pkg.get_rels(cache_path)
            for rel in cache_rels.all_for_reltype(RT.PIVOT_CACHE_REC):
                rec_path = pkg.resolve_rel_target(cache_path, rel.rId)
                pkg.drop_part(rec_path)
                break

            # Remove cache definition
            pkg.drop_part(cache_path)

            # Find the relationship ID for this cache in workbook
            workbook_path = "/xl/workbook.xml"
            workbook_rels = pkg.get_rels(workbook_path)
            cache_rel_id = None
            for rel in workbook_rels.all_for_reltype(RT.PIVOT_CACHE_DEF):
                if pkg.resolve_rel_target(workbook_path, rel.rId) == cache_path:
                    cache_rel_id = rel.rId
                    pkg.remove_rel(workbook_path, rel.rId)
                    break

            # Remove the CORRECT pivotCache element from workbook (by matching r:id)
            workbook_xml = pkg.get_xml(workbook_path)
            pivot_caches = workbook_xml.find(qn("x:pivotCaches"))
            if pivot_caches is not None and cache_rel_id is not None:
                for pc in list(pivot_caches.findall(qn("x:pivotCache"))):
                    if pc.get(qn("r:id")) == cache_rel_id:
                        pivot_caches.remove(pc)
                        break
                # Remove empty pivotCaches
                if len(pivot_caches) == 0:
                    pivot_caches.getparent().remove(pivot_caches)
                pkg.mark_xml_dirty(workbook_path)


def refresh_pivot(pkg: ExcelPackage, sheet_name: str, pivot_id: str) -> None:
    """Refresh a pivot table's cache from source data.

    Args:
        pkg: Excel package
        sheet_name: Sheet containing the pivot table
        pivot_id: Pivot table ID (from PivotInfo.id)
    """
    sheet_path = _get_sheet_path(pkg, sheet_name)

    # Find pivot table
    sheet_rels = pkg.get_rels(sheet_path)
    pivot_path = None

    for rel in sheet_rels.all_for_reltype(RT.PIVOT_TABLE):
        path = pkg.resolve_rel_target(sheet_path, rel.rId)
        if make_pivot_id(path) == pivot_id:
            pivot_path = path
            break

    if pivot_path is None:
        raise KeyError(f"Pivot table not found: {pivot_id}")

    # Get cache path
    pivot_rels = pkg.get_rels(pivot_path)
    cache_path = None
    for rel in pivot_rels.all_for_reltype(RT.PIVOT_CACHE_DEF):
        cache_path = pkg.resolve_rel_target(pivot_path, rel.rId)
        break

    if cache_path is None:
        raise KeyError("Pivot cache not found")

    # Get source info from cache
    cache_xml = pkg.get_xml(cache_path)
    cache_source = cache_xml.find(qn("x:cacheSource"))
    if cache_source is None:
        return

    ws_source = cache_source.find(qn("x:worksheetSource"))
    if ws_source is None:
        return

    source_ref = ws_source.get("ref", "")
    source_sheet = ws_source.get("sheet", "")

    if not source_ref or not source_sheet:
        return

    # Get field names
    field_names = []
    cache_fields = cache_xml.find(qn("x:cacheFields"))
    if cache_fields is not None:
        field_names = [
            field.get("name", "") for field in cache_fields.findall(qn("x:cacheField"))
        ]

    # Find cache records path
    cache_rels = pkg.get_rels(cache_path)
    cache_rec_path = None
    for rel in cache_rels.all_for_reltype(RT.PIVOT_CACHE_REC):
        cache_rec_path = pkg.resolve_rel_target(cache_path, rel.rId)
        break

    if cache_rec_path is None:
        return

    # Rebuild cache records
    new_cache_rec = _create_cache_records(pkg, source_sheet, source_ref, field_names)
    pkg.set_xml(cache_rec_path, new_cache_rec, CT.SML_PIVOT_CACHE_REC)

    # Update record count in cache definition
    record_count = new_cache_rec.get("count", "0")
    cache_xml.set("recordCount", record_count)
    pkg.mark_xml_dirty(cache_path)
