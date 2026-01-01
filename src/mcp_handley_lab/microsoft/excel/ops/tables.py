"""Table operations for Excel.

Excel tables (ListObjects) are structured ranges with headers, auto-filters,
and optional total rows. They are stored as separate XML parts related to worksheets.
"""

from __future__ import annotations

from typing import Any

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import CT, NSMAP, RT, qn
from mcp_handley_lab.microsoft.excel.models import TableInfo
from mcp_handley_lab.microsoft.excel.ops.cells import get_cell_value, set_cell_value
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    index_to_column_letter,
    insert_sheet_element,
    make_range_ref,
    parse_cell_ref,
    parse_range_ref,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def _find_table(pkg: ExcelPackage, table_name: str) -> tuple[str, str]:
    """Find table by name. Returns (table_path, sheet_name)."""
    for sname, _rId, spartname in pkg.get_sheet_paths():
        sheet_rels = pkg.get_rels(spartname)
        for rel in sheet_rels.all_for_reltype(RT.TABLE):
            tpath = pkg.resolve_rel_target(spartname, rel.rId)
            if pkg.has_part(tpath):
                table_xml = pkg.get_xml(tpath)
                if table_xml.get("name") == table_name:
                    return tpath, sname
    raise KeyError(f"Table not found: {table_name}")


def list_tables(pkg: ExcelPackage) -> list[TableInfo]:
    """List all tables in the workbook.

    Returns: List of TableInfo for all tables across all sheets.
    """
    result = []
    for sheet_name, _rId, sheet_partname in pkg.get_sheet_paths():
        sheet_rels = pkg.get_rels(sheet_partname)
        for rel in sheet_rels.all_for_reltype(RT.TABLE):
            table_path = pkg.resolve_rel_target(sheet_partname, rel.rId)
            if pkg.has_part(table_path):
                table_xml = pkg.get_xml(table_path)
                info = _parse_table_info(table_xml, sheet_name)
                result.append(info)
    return result


def get_table_by_name(pkg: ExcelPackage, table_name: str) -> TableInfo:
    """Get table info by name.

    Raises: KeyError if table not found.
    """
    for info in list_tables(pkg):
        if info.name == table_name:
            return info
    raise KeyError(f"Table not found: {table_name}")


def get_table_data(
    pkg: ExcelPackage, table_name: str, include_headers: bool = False
) -> list[list[Any]]:
    """Get table data as a 2D array.

    Args:
        table_name: Name of the table.
        include_headers: If True, first row is column headers.

    Returns: 2D array of values.
    Raises: KeyError if table not found.
    """
    table_info = get_table_by_name(pkg, table_name)
    start_ref, end_ref = parse_range_ref(table_info.ref)
    start_col, start_row, _, _ = parse_cell_ref(start_ref)
    end_col, end_row, _, _ = parse_cell_ref(end_ref)
    start_col_idx = column_letter_to_index(start_col)
    end_col_idx = column_letter_to_index(end_col)

    # Skip header row unless requested
    data_start_row = start_row if include_headers else start_row + 1

    result = []
    for row_num in range(data_start_row, end_row + 1):
        row_values = []
        for col_idx in range(start_col_idx, end_col_idx + 1):
            col_letter = index_to_column_letter(col_idx)
            cell_ref = f"{col_letter}{row_num}"
            value = get_cell_value(pkg, table_info.sheet, cell_ref)
            row_values.append(value)
        result.append(row_values)
    return result


def create_table(
    pkg: ExcelPackage,
    sheet_name: str,
    range_ref: str,
    table_name: str,
    has_headers: bool = True,
) -> TableInfo:
    """Create a new table in the specified range.

    Args:
        sheet_name: Name of the sheet.
        range_ref: Range like "A1:C10".
        table_name: Name for the table (must be unique).
        has_headers: If True, first row contains column headers.

    Returns: TableInfo for the created table.
    """
    # Parse range
    start_ref, end_ref = parse_range_ref(range_ref)
    start_col, start_row, _, _ = parse_cell_ref(start_ref)
    end_col, end_row, _, _ = parse_cell_ref(end_ref)
    start_col_idx = column_letter_to_index(start_col)
    end_col_idx = column_letter_to_index(end_col)
    num_cols = end_col_idx - start_col_idx + 1

    # Get column names from first row if has_headers
    columns = []
    if has_headers:
        for i, col_idx in enumerate(range(start_col_idx, end_col_idx + 1), 1):
            col_letter = index_to_column_letter(col_idx)
            cell_ref = f"{col_letter}{start_row}"
            value = get_cell_value(pkg, sheet_name, cell_ref)
            # Use table-relative column index (1-based) for auto-generated names
            columns.append(str(value) if value is not None else f"Column{i}")
    else:
        columns = [f"Column{i + 1}" for i in range(num_cols)]

    # Find next available table ID
    max_table_id = 0
    for _sheet_name_iter, _rId, sheet_partname in pkg.get_sheet_paths():
        sheet_rels = pkg.get_rels(sheet_partname)
        for rel in sheet_rels.all_for_reltype(RT.TABLE):
            table_path = pkg.resolve_rel_target(sheet_partname, rel.rId)
            if pkg.has_part(table_path):
                table_xml = pkg.get_xml(table_path)
                table_id = int(table_xml.get("id", "0"))
                max_table_id = max(max_table_id, table_id)

    new_table_id = max_table_id + 1
    display_name = table_name.replace(" ", "_")

    # Create table XML
    table_el = etree.Element(
        qn("x:table"),
        nsmap={None: NSMAP["x"]},
        id=str(new_table_id),
        name=table_name,
        displayName=display_name,
        ref=range_ref,
        totalsRowShown="0",
    )

    # Auto-filter covers the entire table range
    etree.SubElement(table_el, qn("x:autoFilter"), ref=range_ref)

    # Table columns
    table_cols = etree.SubElement(table_el, qn("x:tableColumns"), count=str(num_cols))
    for i, col_name in enumerate(columns, 1):
        etree.SubElement(table_cols, qn("x:tableColumn"), id=str(i), name=col_name)

    # Table style (default)
    etree.SubElement(
        table_el,
        qn("x:tableStyleInfo"),
        name="TableStyleMedium2",
        showFirstColumn="0",
        showLastColumn="0",
        showRowStripes="1",
        showColumnStripes="0",
    )

    # Save table part
    table_path = f"/xl/tables/table{new_table_id}.xml"
    pkg.set_xml(table_path, table_el, CT.SML_TABLE)

    # Get sheet partname and create relationship
    sheet_partname = None
    for name, _rId, partname in pkg.get_sheet_paths():
        if name == sheet_name:
            sheet_partname = partname
            break

    if sheet_partname is None:
        raise KeyError(f"Sheet not found: {sheet_name}")

    # Relate table from worksheet (use relative path)
    rel_target = f"../tables/table{new_table_id}.xml"
    rId = pkg.relate_to(sheet_partname, rel_target, RT.TABLE)

    # Add tablePart to worksheet at correct OOXML position
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    table_parts = sheet_xml.find(qn("x:tableParts"))
    if table_parts is None:
        table_parts = etree.Element(qn("x:tableParts"), count="0")
        insert_sheet_element(sheet_xml, "tableParts", table_parts)
    table_parts.set("count", str(int(table_parts.get("count", "0")) + 1))
    etree.SubElement(table_parts, qn("x:tablePart"), attrib={qn("r:id"): rId})
    pkg.mark_xml_dirty(sheet_partname)

    row_count = end_row - start_row  # Exclude header
    if not has_headers:
        row_count += 1

    return TableInfo(
        name=table_name,
        sheet=sheet_name,
        ref=range_ref,
        columns=columns,
        row_count=row_count,
    )


def delete_table(pkg: ExcelPackage, table_name: str) -> None:
    """Delete a table by name.

    The table definition is removed but cell data remains.

    Raises: KeyError if table not found.
    """
    # Find the table
    for sheet_name, _rId, sheet_partname in pkg.get_sheet_paths():
        sheet_rels = pkg.get_rels(sheet_partname)
        for rel in sheet_rels.all_for_reltype(RT.TABLE):
            table_path = pkg.resolve_rel_target(sheet_partname, rel.rId)
            if pkg.has_part(table_path):
                table_xml = pkg.get_xml(table_path)
                name = table_xml.get("name", "")
                if name == table_name:
                    # Remove tablePart from worksheet
                    sheet_xml = pkg.get_sheet_xml(sheet_name)
                    table_parts = sheet_xml.find(qn("x:tableParts"))
                    if table_parts is not None:
                        for tp in table_parts.findall(qn("x:tablePart")):
                            if tp.get(qn("r:id")) == rel.rId:
                                table_parts.remove(tp)
                                count = int(table_parts.get("count", "1")) - 1
                                if count > 0:
                                    table_parts.set("count", str(count))
                                else:
                                    # Remove empty tableParts element
                                    sheet_xml.remove(table_parts)
                                break
                        pkg.mark_xml_dirty(sheet_partname)

                    # Remove relationship and part
                    pkg.remove_rel(sheet_partname, rel.rId)
                    pkg.drop_part(table_path)
                    return

    raise KeyError(f"Table not found: {table_name}")


def add_table_row(pkg: ExcelPackage, table_name: str, values: list[Any]) -> str:
    """Add a row to a table.

    The row is added at the end of the table data (before totals row if present).
    The table reference is expanded to include the new row.

    Args:
        table_name: Name of the table.
        values: List of values for the new row (must match column count).

    Returns: Cell reference of the first cell in the new row.
    Raises: KeyError if table not found.
    """
    table_path, sheet_name = _find_table(pkg, table_name)
    table_xml = pkg.get_xml(table_path)
    old_ref = table_xml.get("ref", "")
    start_ref, end_ref = parse_range_ref(old_ref)
    start_col, start_row, _, _ = parse_cell_ref(start_ref)
    end_col, end_row, _, _ = parse_cell_ref(end_ref)

    start_col_idx = column_letter_to_index(start_col)

    # New row is after current last row
    new_row_num = end_row + 1

    # Write values to cells
    for i, value in enumerate(values):
        col_letter = index_to_column_letter(start_col_idx + i)
        cell_ref = f"{col_letter}{new_row_num}"
        set_cell_value(pkg, sheet_name, cell_ref, value)

    # Expand table reference
    new_ref = make_range_ref(f"{start_col}{start_row}", f"{end_col}{new_row_num}")
    table_xml.set("ref", new_ref)

    # Update autoFilter ref if present
    auto_filter = table_xml.find(qn("x:autoFilter"))
    if auto_filter is not None:
        auto_filter.set("ref", new_ref)

    pkg.mark_xml_dirty(table_path)

    return f"{start_col}{new_row_num}"


def delete_table_row(pkg: ExcelPackage, table_name: str, row_index: int) -> None:
    """Delete a row from a table by 0-based index (relative to data rows).

    For multi-row tables, subsequent rows shift up and the table contracts.
    For single-row tables, the row data is cleared but the table keeps one
    empty data row (Excel requires tables to have at least header + 1 row).

    Args:
        table_name: Name of the table.
        row_index: 0-based index of the data row to delete (0 = first data row).

    Raises: KeyError if table not found, IndexError if row_index out of range.
    """
    table_path, sheet_name = _find_table(pkg, table_name)
    table_xml = pkg.get_xml(table_path)
    old_ref = table_xml.get("ref", "")
    start_ref, end_ref = parse_range_ref(old_ref)
    start_col, start_row, _, _ = parse_cell_ref(start_ref)
    end_col, end_row, _, _ = parse_cell_ref(end_ref)

    # Data rows start after header
    data_start_row = start_row + 1
    data_row_count = end_row - data_start_row + 1

    if not 0 <= row_index < data_row_count:
        raise IndexError(
            f"Row index out of range: {row_index} (0-{data_row_count - 1})"
        )

    # Row to delete (1-based Excel row number)
    delete_row_num = data_start_row + row_index

    # Clear cell values in the row
    start_col_idx = column_letter_to_index(start_col)
    end_col_idx = column_letter_to_index(end_col)
    for col_idx in range(start_col_idx, end_col_idx + 1):
        col_letter = index_to_column_letter(col_idx)
        cell_ref = f"{col_letter}{delete_row_num}"
        set_cell_value(pkg, sheet_name, cell_ref, None)

    # If this is the last data row, keep it cleared but don't contract
    # (Excel requires tables to have at least one data row for compatibility)
    if data_row_count == 1:
        # Row is already cleared above, table ref stays the same
        pass
    else:
        # Shift subsequent rows up in the table data
        for row_num in range(delete_row_num, end_row):
            for col_idx in range(start_col_idx, end_col_idx + 1):
                col_letter = index_to_column_letter(col_idx)
                src_ref = f"{col_letter}{row_num + 1}"
                dst_ref = f"{col_letter}{row_num}"
                value = get_cell_value(pkg, sheet_name, src_ref)
                set_cell_value(pkg, sheet_name, dst_ref, value)
                set_cell_value(pkg, sheet_name, src_ref, None)

        # Contract table reference
        new_ref = make_range_ref(f"{start_col}{start_row}", f"{end_col}{end_row - 1}")
        table_xml.set("ref", new_ref)

        # Update autoFilter ref if present
        auto_filter = table_xml.find(qn("x:autoFilter"))
        if auto_filter is not None:
            auto_filter.set("ref", new_ref)

    pkg.mark_xml_dirty(table_path)


def _parse_table_info(table_xml: etree._Element, sheet_name: str) -> TableInfo:
    """Parse TableInfo from table XML element."""
    name = table_xml.get("name", "")
    ref = table_xml.get("ref", "")

    # Get columns
    columns = []
    table_cols = table_xml.find(qn("x:tableColumns"))
    if table_cols is not None:
        for col in table_cols.findall(qn("x:tableColumn")):
            columns.append(col.get("name", ""))

    # Calculate row count
    start_ref, end_ref = parse_range_ref(ref)
    _, start_row, _, _ = parse_cell_ref(start_ref)
    _, end_row, _, _ = parse_cell_ref(end_ref)
    row_count = end_row - start_row  # Exclude header row

    return TableInfo(
        name=name,
        sheet=sheet_name,
        ref=ref,
        columns=columns,
        row_count=row_count,
    )
