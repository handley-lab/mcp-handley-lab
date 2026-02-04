"""Table operations for PowerPoint."""

from __future__ import annotations

import copy

from lxml import etree

from mcp_handley_lab.microsoft.powerpoint.constants import NSMAP, qn
from mcp_handley_lab.microsoft.powerpoint.ops.core import (
    get_shape_id,
    inches_to_emu,
    make_shape_key,
    parse_shape_key,
)
from mcp_handley_lab.microsoft.powerpoint.package import PowerPointPackage


def add_table(
    pkg: PowerPointPackage,
    slide_num: int,
    rows: int,
    cols: int,
    x: float = 1.0,
    y: float = 1.0,
    width: float = 6.0,
    height: float = 2.0,
) -> str:
    """Add a table to a slide.

    Args:
        pkg: PowerPoint package
        slide_num: Target slide number
        rows: Number of rows
        cols: Number of columns
        x: X position in inches
        y: Y position in inches
        width: Table width in inches
        height: Table height in inches

    Returns:
        Shape key for the new table (slide_num:shape_id)
    """
    if rows < 1 or cols < 1:
        raise ValueError("Table must have at least 1 row and 1 column")

    slide_partname = pkg.get_slide_partname(slide_num)
    slide_xml = pkg.get_slide_xml(slide_num)
    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        raise ValueError(f"Slide {slide_num} has no spTree")

    # Get next shape ID
    max_id = 0
    for sp in sp_tree.findall(".//" + qn("p:cNvPr"), NSMAP):
        id_str = sp.get("id", "0")
        if id_str.isdigit():
            max_id = max(max_id, int(id_str))
    new_id = max_id + 1

    # Calculate cell dimensions
    cell_width = inches_to_emu(width) // cols
    cell_height = inches_to_emu(height) // rows

    # Create graphicFrame element
    graphic_frame = _create_table_graphic_frame(
        new_id, rows, cols, x, y, width, height, cell_width, cell_height
    )
    sp_tree.append(graphic_frame)

    pkg.mark_xml_dirty(slide_partname)
    return make_shape_key(slide_num, new_id)


def set_table_cell(
    pkg: PowerPointPackage,
    shape_key: str,
    row: int,
    col: int,
    text: str,
) -> None:
    """Set text in a table cell.

    Args:
        pkg: PowerPoint package
        shape_key: Table shape key (slide_num:shape_id)
        row: Row index (0-based)
        col: Column index (0-based)
        text: Text to set

    Raises:
        ValueError: If table not found or cell out of range
    """
    slide_num, shape_id = parse_shape_key(shape_key)
    slide_partname = pkg.get_slide_partname(slide_num)
    slide_xml = pkg.get_slide_xml(slide_num)
    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        raise ValueError(f"Slide {slide_num} has no shape tree")

    # Find the graphic frame with matching shape_id
    for gf in sp_tree.findall(qn("p:graphicFrame"), NSMAP):
        gf_id = get_shape_id(gf)
        if gf_id == shape_id:
            # Find the table
            tbl = gf.find(
                qn("a:graphic") + "/" + qn("a:graphicData") + "/" + qn("a:tbl"), NSMAP
            )
            if tbl is None:
                raise ValueError(f"Shape {shape_id} is not a table")

            # Find the cell
            tr_list = tbl.findall(qn("a:tr"), NSMAP)
            if row >= len(tr_list):
                raise ValueError(
                    f"Row {row} out of range (table has {len(tr_list)} rows)"
                )

            tc_list = tr_list[row].findall(qn("a:tc"), NSMAP)
            if col >= len(tc_list):
                raise ValueError(
                    f"Column {col} out of range (row has {len(tc_list)} columns)"
                )

            tc = tc_list[col]

            # Update the cell text
            _set_cell_text(tc, text)
            pkg.mark_xml_dirty(slide_partname)
            return

    raise ValueError(f"Table {shape_id} not found on slide {slide_num}")


def _create_table_graphic_frame(
    shape_id: int,
    rows: int,
    cols: int,
    x: float,
    y: float,
    width: float,
    height: float,
    cell_width: int,
    cell_height: int,
) -> etree._Element:
    """Create a graphicFrame containing a table."""
    gf = etree.Element(qn("p:graphicFrame"), nsmap={"p": NSMAP["p"], "a": NSMAP["a"]})

    # nvGraphicFramePr
    nvGfPr = etree.SubElement(gf, qn("p:nvGraphicFramePr"))
    cNvPr = etree.SubElement(nvGfPr, qn("p:cNvPr"))
    cNvPr.set("id", str(shape_id))
    cNvPr.set("name", f"Table {shape_id - 1}")
    cNvGfPr = etree.SubElement(nvGfPr, qn("p:cNvGraphicFramePr"))
    etree.SubElement(cNvGfPr, qn("a:graphicFrameLocks"), noGrp="1")
    etree.SubElement(nvGfPr, qn("p:nvPr"))

    # xfrm (position and size)
    xfrm = etree.SubElement(gf, qn("p:xfrm"))
    off = etree.SubElement(xfrm, qn("a:off"))
    off.set("x", str(inches_to_emu(x)))
    off.set("y", str(inches_to_emu(y)))
    ext = etree.SubElement(xfrm, qn("a:ext"))
    ext.set("cx", str(inches_to_emu(width)))
    ext.set("cy", str(inches_to_emu(height)))

    # graphic container
    graphic = etree.SubElement(gf, qn("a:graphic"))
    graphicData = etree.SubElement(graphic, qn("a:graphicData"))
    graphicData.set("uri", "http://schemas.openxmlformats.org/drawingml/2006/table")

    # Table element
    tbl = etree.SubElement(graphicData, qn("a:tbl"))

    # Table properties
    tblPr = etree.SubElement(tbl, qn("a:tblPr"))
    tblPr.set("firstRow", "1")
    tblPr.set("bandRow", "1")
    # Standard table style ID for PowerPoint compatibility
    tableStyleId = etree.SubElement(tblPr, qn("a:tableStyleId"))
    tableStyleId.text = "{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"

    # Table grid (column widths)
    tblGrid = etree.SubElement(tbl, qn("a:tblGrid"))
    for _ in range(cols):
        gridCol = etree.SubElement(tblGrid, qn("a:gridCol"))
        gridCol.set("w", str(cell_width))

    # Table rows
    for _ in range(rows):
        tr = etree.SubElement(tbl, qn("a:tr"))
        tr.set("h", str(cell_height))
        for _ in range(cols):
            tc = _create_empty_cell()
            tr.append(tc)

    return gf


def _create_empty_cell() -> etree._Element:
    """Create an empty table cell."""
    tc = etree.Element(qn("a:tc"))

    # txBody with empty paragraph
    txBody = etree.SubElement(tc, qn("a:txBody"))
    etree.SubElement(txBody, qn("a:bodyPr"))
    etree.SubElement(txBody, qn("a:lstStyle"))
    p = etree.SubElement(txBody, qn("a:p"))
    etree.SubElement(p, qn("a:endParaRPr"), lang="en-US")

    # Cell properties
    etree.SubElement(tc, qn("a:tcPr"))

    return tc


def _clear_cell_text(tc: etree._Element) -> None:
    """Clear text from a table cell while preserving all formatting.

    Preserves a:tcPr, paragraph props, run props, and endParaRPr formatting.
    """
    txBody = tc.find(qn("a:txBody"), NSMAP)
    if txBody is None:
        return

    # Find first paragraph to get formatting
    existing_p = txBody.find(qn("a:p"), NSMAP)
    existing_pPr = None
    existing_endParaRPr = None

    if existing_p is not None:
        pPr = existing_p.find(qn("a:pPr"), NSMAP)
        if pPr is not None:
            existing_pPr = copy.deepcopy(pPr)
        endParaRPr = existing_p.find(qn("a:endParaRPr"), NSMAP)
        if endParaRPr is not None:
            existing_endParaRPr = copy.deepcopy(endParaRPr)

    # Remove all existing paragraphs
    for p in list(txBody.findall(qn("a:p"), NSMAP)):
        txBody.remove(p)

    # Create a single empty paragraph with preserved formatting
    p = etree.SubElement(txBody, qn("a:p"))
    if existing_pPr is not None:
        p.append(existing_pPr)
    if existing_endParaRPr is not None:
        p.append(existing_endParaRPr)
    else:
        etree.SubElement(p, qn("a:endParaRPr"), lang="en-US")


def _set_cell_text(tc: etree._Element, text: str) -> None:
    """Set text in a table cell, preserving existing formatting."""
    txBody = tc.find(qn("a:txBody"), NSMAP)
    if txBody is None:
        txBody = etree.SubElement(tc, qn("a:txBody"))
        etree.SubElement(txBody, qn("a:bodyPr"))
        etree.SubElement(txBody, qn("a:lstStyle"))

    # Preserve first paragraph/run/endPara properties
    existing_p = txBody.find(qn("a:p"), NSMAP)
    existing_pPr = None
    existing_rPr = None
    existing_endParaRPr = None
    if existing_p is not None:
        pPr = existing_p.find(qn("a:pPr"), NSMAP)
        if pPr is not None:
            existing_pPr = copy.deepcopy(pPr)
        endParaRPr = existing_p.find(qn("a:endParaRPr"), NSMAP)
        if endParaRPr is not None:
            existing_endParaRPr = copy.deepcopy(endParaRPr)
        existing_r = existing_p.find(qn("a:r"), NSMAP)
        if existing_r is not None:
            rPr = existing_r.find(qn("a:rPr"), NSMAP)
            if rPr is not None:
                existing_rPr = copy.deepcopy(rPr)

    # Remove existing paragraphs
    for p in list(txBody.findall(qn("a:p"), NSMAP)):
        txBody.remove(p)

    # Add new paragraphs preserving formatting
    for line in text.split("\n"):
        p = etree.SubElement(txBody, qn("a:p"))
        if existing_pPr is not None:
            p.append(copy.deepcopy(existing_pPr))
        if line:
            # Split on tabs and create a:tab elements between segments
            segments = line.split("\t")
            for i, segment in enumerate(segments):
                if i > 0:
                    etree.SubElement(p, qn("a:tab"))
                if segment:
                    r = etree.SubElement(p, qn("a:r"))
                    if existing_rPr is not None:
                        r.append(copy.deepcopy(existing_rPr))
                    else:
                        etree.SubElement(r, qn("a:rPr"), lang="en-US")
                    t = etree.SubElement(r, qn("a:t"))
                    t.text = segment
        # Always append endParaRPr
        if existing_endParaRPr is not None:
            p.append(copy.deepcopy(existing_endParaRPr))
        else:
            etree.SubElement(p, qn("a:endParaRPr"), lang="en-US")


def list_tables(
    pkg: PowerPointPackage,
    slide_num: int,
) -> list[dict]:
    """List all tables on a slide with their structure.

    Args:
        pkg: PowerPoint package
        slide_num: Slide number

    Returns:
        List of table info dicts with rows, cols, cells
    """
    from mcp_handley_lab.microsoft.powerpoint.ops.core import (
        emu_to_inches,
        get_shape_name,
    )

    slide_xml = pkg.get_slide_xml(slide_num)
    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        return []

    tables = []

    for gf in sp_tree.findall(qn("p:graphicFrame"), NSMAP):
        # Check if this is a table
        tbl = gf.find(
            qn("a:graphic") + "/" + qn("a:graphicData") + "/" + qn("a:tbl"), NSMAP
        )
        if tbl is None:
            continue

        shape_id = get_shape_id(gf)
        if shape_id is None:
            continue

        # Get position from p:xfrm (graphicFrame uses p:xfrm, not a:xfrm)
        xfrm = gf.find(qn("p:xfrm"), NSMAP)
        if xfrm is not None:
            off = xfrm.find(qn("a:off"), NSMAP)
            ext = xfrm.find(qn("a:ext"), NSMAP)
            if off is not None and ext is not None:
                x = int(off.get("x", "0"))
                y = int(off.get("y", "0"))
                cx = int(ext.get("cx", "0"))
                cy = int(ext.get("cy", "0"))
            else:
                x = y = cx = cy = 0
        else:
            x = y = cx = cy = 0

        # Extract table structure
        tr_list = tbl.findall(qn("a:tr"), NSMAP)
        rows = len(tr_list)
        cols = 0
        cells = []

        for row_idx, tr in enumerate(tr_list):
            tc_list = tr.findall(qn("a:tc"), NSMAP)
            cols = max(cols, len(tc_list))

            for col_idx, tc in enumerate(tc_list):
                cell_text = _extract_cell_text(tc)
                cells.append({"row": row_idx, "col": col_idx, "text": cell_text})

        tables.append(
            {
                "shape_key": make_shape_key(slide_num, shape_id),
                "shape_id": shape_id,
                "name": get_shape_name(gf),
                "x_inches": emu_to_inches(x),
                "y_inches": emu_to_inches(y),
                "width_inches": emu_to_inches(cx),
                "height_inches": emu_to_inches(cy),
                "rows": rows,
                "cols": cols,
                "cells": cells,
            }
        )

    return tables


def _extract_cell_text(tc: etree._Element) -> str:
    """Extract text from a table cell."""
    from mcp_handley_lab.microsoft.powerpoint.ops.text import extract_text_from_txBody

    txBody = tc.find(qn("a:txBody"), NSMAP)
    return extract_text_from_txBody(txBody)


def _find_table(
    pkg: PowerPointPackage, shape_key: str
) -> tuple[etree._Element, etree._Element, str]:
    """Find a table by shape_key.

    Returns:
        Tuple of (tbl element, graphicFrame element, slide_partname)

    Raises:
        ValueError: If table not found or shape is not a table
    """
    slide_num, shape_id = parse_shape_key(shape_key)
    slide_partname = pkg.get_slide_partname(slide_num)
    slide_xml = pkg.get_slide_xml(slide_num)
    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        raise ValueError(f"Slide {slide_num} has no shape tree")

    for gf in sp_tree.findall(qn("p:graphicFrame"), NSMAP):
        gf_id = get_shape_id(gf)
        if gf_id == shape_id:
            tbl = gf.find(
                qn("a:graphic") + "/" + qn("a:graphicData") + "/" + qn("a:tbl"), NSMAP
            )
            if tbl is not None:
                return tbl, gf, slide_partname
            raise ValueError(f"Shape {shape_id} is not a table")

    raise ValueError(f"Table {shape_id} not found on slide {slide_num}")


def add_table_row(
    pkg: PowerPointPackage,
    shape_key: str,
    position: int | None = None,
) -> None:
    """Add a row to an existing table.

    Copies the structure and formatting from an adjacent row (the row before
    the insertion point, or the last row if appending). Cell text is cleared
    while preserving cell properties, paragraph formatting, and run properties.

    Args:
        pkg: PowerPoint package
        shape_key: Table shape key (slide_num:shape_id)
        position: Row index to insert at (0-based). None or -1 appends to end.

    Raises:
        ValueError: If table not found or empty
    """
    tbl, gf, slide_partname = _find_table(pkg, shape_key)
    tr_list = tbl.findall(qn("a:tr"), NSMAP)
    num_rows = len(tr_list)

    if num_rows == 0:
        raise ValueError("Cannot add row to empty table")

    # Calculate position
    if position is None or position < 0 or position >= num_rows:
        insert_pos = num_rows
    else:
        insert_pos = position

    # Copy formatting from row before insertion point (or first row)
    source_row = tr_list[insert_pos - 1] if insert_pos > 0 else tr_list[0]

    # Deep copy the source row
    new_tr = copy.deepcopy(source_row)

    # Clear text from all cells in the copied row while preserving formatting
    for tc in new_tr.findall(qn("a:tc"), NSMAP):
        _clear_cell_text(tc)

    # Insert at position
    if insert_pos >= num_rows:
        # Append after last row
        tbl.append(new_tr)
    else:
        # Insert before specified row
        tbl.insert(list(tbl).index(tr_list[insert_pos]), new_tr)

    # Update table height in xfrm (use height from copied row)
    row_height = int(new_tr.get("h", str(inches_to_emu(0.5))))
    xfrm = gf.find(qn("p:xfrm"), NSMAP)
    if xfrm is not None:
        ext = xfrm.find(qn("a:ext"), NSMAP)
        if ext is not None:
            current_height = int(ext.get("cy", "0"))
            ext.set("cy", str(current_height + row_height))

    pkg.mark_xml_dirty(slide_partname)


def add_table_column(
    pkg: PowerPointPackage,
    shape_key: str,
    position: int | None = None,
) -> None:
    """Add a column to an existing table.

    Copies the structure and formatting from an adjacent cell (the cell before
    the insertion point, or the last cell if appending). Cell text is cleared
    while preserving cell properties, paragraph formatting, and run properties.

    Args:
        pkg: PowerPoint package
        shape_key: Table shape key (slide_num:shape_id)
        position: Column index to insert at (0-based). None or -1 appends to end.

    Raises:
        ValueError: If table not found, has no grid, or is empty
    """
    tbl, gf, slide_partname = _find_table(pkg, shape_key)

    # Find tblGrid
    tbl_grid = tbl.find(qn("a:tblGrid"), NSMAP)
    if tbl_grid is None:
        raise ValueError("Table has no grid definition")

    grid_cols = tbl_grid.findall(qn("a:gridCol"), NSMAP)
    num_cols = len(grid_cols)

    if num_cols == 0:
        raise ValueError("Cannot add column to empty table")

    # Calculate position
    if position is None or position < 0 or position >= num_cols:
        insert_pos = num_cols
    else:
        insert_pos = position

    # Copy formatting from column before insertion point (or first column)
    source_col_idx = insert_pos - 1 if insert_pos > 0 else 0

    # Get column width from source column
    col_width = int(grid_cols[source_col_idx].get("w", str(inches_to_emu(1.0))))

    # Add new gridCol (copy attributes from source)
    new_grid_col = copy.deepcopy(grid_cols[source_col_idx])

    if insert_pos >= num_cols:
        tbl_grid.append(new_grid_col)
    else:
        tbl_grid.insert(insert_pos, new_grid_col)

    # Add cell to each row by copying the source cell and clearing its text
    for tr in tbl.findall(qn("a:tr"), NSMAP):
        tc_list = tr.findall(qn("a:tc"), NSMAP)
        if not tc_list:
            continue

        # Get source cell (cell before insertion point, or last cell if appending)
        source_cell = tc_list[source_col_idx]
        new_cell = copy.deepcopy(source_cell)
        _clear_cell_text(new_cell)

        if insert_pos >= len(tc_list):
            tr.append(new_cell)
        else:
            tr.insert(list(tr).index(tc_list[insert_pos]), new_cell)

    # Update table width in xfrm
    xfrm = gf.find(qn("p:xfrm"), NSMAP)
    if xfrm is not None:
        ext = xfrm.find(qn("a:ext"), NSMAP)
        if ext is not None:
            current_width = int(ext.get("cx", "0"))
            ext.set("cx", str(current_width + col_width))

    pkg.mark_xml_dirty(slide_partname)


def delete_table_row(
    pkg: PowerPointPackage,
    shape_key: str,
    row: int,
) -> None:
    """Delete a row from an existing table.

    Args:
        pkg: PowerPoint package
        shape_key: Table shape key (slide_num:shape_id)
        row: Row index to delete (0-based)

    Raises:
        ValueError: If table not found, row out of range, or would delete last row
    """
    tbl, gf, slide_partname = _find_table(pkg, shape_key)
    tr_list = tbl.findall(qn("a:tr"), NSMAP)

    if row < 0 or row >= len(tr_list):
        raise ValueError(f"Row {row} out of range (table has {len(tr_list)} rows)")

    # Must keep at least one row
    if len(tr_list) <= 1:
        raise ValueError("Cannot delete last row from table")

    tr_to_delete = tr_list[row]
    row_height = int(tr_to_delete.get("h", "0"))
    tbl.remove(tr_to_delete)

    # Update table height in xfrm
    xfrm = gf.find(qn("p:xfrm"), NSMAP)
    if xfrm is not None:
        ext = xfrm.find(qn("a:ext"), NSMAP)
        if ext is not None:
            current_height = int(ext.get("cy", "0"))
            new_height = max(0, current_height - row_height)
            ext.set("cy", str(new_height))

    pkg.mark_xml_dirty(slide_partname)


def delete_table_column(
    pkg: PowerPointPackage,
    shape_key: str,
    col: int,
) -> None:
    """Delete a column from an existing table.

    Args:
        pkg: PowerPoint package
        shape_key: Table shape key (slide_num:shape_id)
        col: Column index to delete (0-based)

    Raises:
        ValueError: If table not found, column out of range, or would delete last column
    """
    tbl, gf, slide_partname = _find_table(pkg, shape_key)

    # Find tblGrid
    tbl_grid = tbl.find(qn("a:tblGrid"), NSMAP)
    if tbl_grid is None:
        raise ValueError("Table has no grid definition")

    grid_cols = tbl_grid.findall(qn("a:gridCol"), NSMAP)

    if col < 0 or col >= len(grid_cols):
        raise ValueError(
            f"Column {col} out of range (table has {len(grid_cols)} columns)"
        )

    # Must keep at least one column
    if len(grid_cols) <= 1:
        raise ValueError("Cannot delete last column from table")

    # Get column width before removing
    col_width = int(grid_cols[col].get("w", "0"))
    tbl_grid.remove(grid_cols[col])

    # Remove cell from each row
    for tr in tbl.findall(qn("a:tr"), NSMAP):
        tc_list = tr.findall(qn("a:tc"), NSMAP)
        if col < len(tc_list):
            tr.remove(tc_list[col])

    # Update table width in xfrm
    xfrm = gf.find(qn("p:xfrm"), NSMAP)
    if xfrm is not None:
        ext = xfrm.find(qn("a:ext"), NSMAP)
        if ext is not None:
            current_width = int(ext.get("cx", "0"))
            new_width = max(0, current_width - col_width)
            ext.set("cx", str(new_width))

    pkg.mark_xml_dirty(slide_partname)
