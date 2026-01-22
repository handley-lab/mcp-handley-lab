"""Table operations for Word documents.

Contains functions for table manipulation, formatting, and conversion.
Pure OOXML implementation - works directly with lxml elements.
"""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.models import CellInfo, RowInfo, TableLayoutInfo
from mcp_handley_lab.microsoft.word.ops.core import (
    _insert_at,
    get_cell_tables,
    get_cell_text,
)

# Element tag constants
_W_TR = qn("w:tr")
_W_TC = qn("w:tc")
_W_TCPR = qn("w:tcPr")
_W_TRPR = qn("w:trPr")
_W_GRIDSPAN = qn("w:gridSpan")
_W_VMERGE = qn("w:vMerge")
_W_VAL = qn("w:val")
_W_TBL_HEADER = qn("w:tblHeader")
_W_TBL_BORDERS = qn("w:tcBorders")
_W_SHD = qn("w:shd")
_W_FILL = qn("w:fill")
_W_SZ = qn("w:sz")
_W_COLOR = qn("w:color")
_W_TBLGRID = qn("w:tblGrid")
_W_GRIDCOL = qn("w:gridCol")


def _get_tc_text(tc_el: etree._Element) -> str:
    """Get text from a table cell element."""
    return get_cell_text(tc_el)


def _get_grid_span(tc_el: etree._Element) -> int:
    """Get gridSpan value (horizontal merge) from tc element."""
    tcPr = tc_el.find(_W_TCPR)
    if tcPr is not None:
        gridSpan = tcPr.find(_W_GRIDSPAN)
        if gridSpan is not None:
            val = gridSpan.get(_W_VAL)
            return int(val) if val else 1
    return 1


def table_to_markdown(
    tbl_el: etree._Element, max_chars: int = 500, max_rows: int = 20, max_cols: int = 10
) -> tuple[str, int, int]:
    """Convert table to markdown preview with truncation.

    Pure OOXML: Takes w:tbl element.
    """
    tr_els = tbl_el.findall(_W_TR)
    rows = len(tr_els)

    # Count columns from first row
    if rows == 0:
        return "", 0, 0
    cols = sum(_get_grid_span(tc) for tc in tr_els[0].findall(_W_TC))

    r_lim, c_lim = min(rows, max_rows), min(cols, max_cols)

    grid = []
    for r in range(r_lim):
        tr_el = tr_els[r]
        row_data = []
        col_idx = 0
        for tc in tr_el.findall(_W_TC):
            if col_idx >= c_lim:
                break
            text = _get_tc_text(tc).strip().replace("|", "\\|").replace("\n", "<br>")
            row_data.append(text)
            span = _get_grid_span(tc)
            col_idx += span
            # Add empty strings for spanned cells
            for _ in range(1, span):
                if len(row_data) < c_lim:
                    row_data.append("")
        # Pad if row has fewer cells
        while len(row_data) < c_lim:
            row_data.append("")
        grid.append(row_data[:c_lim])

    if not grid:
        return "", rows, cols

    header = grid[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in grid[1:])

    if rows > r_lim:
        lines.append(f"... ({rows - r_lim} more rows)")
    if cols > c_lim:
        lines.append(f"... ({cols - c_lim} more cols)")

    md = "\n".join(lines)
    if len(md) > max_chars:
        md = md[:max_chars] + "\n... (truncated)"
    return md, rows, cols


def populate_table(tbl_el: etree._Element, data: list[list]) -> None:
    """Populate table cells from 2D list.

    Pure OOXML: Takes w:tbl element.
    """
    tr_els = tbl_el.findall(_W_TR)
    for r, row in enumerate(data):
        if r >= len(tr_els):
            break
        tc_els = tr_els[r].findall(_W_TC)
        for c, val in enumerate(row):
            if c >= len(tc_els):
                break
            # Clear existing content and add new
            tc = tc_els[c]
            # Find or create paragraph
            p = tc.find(qn("w:p"))
            if p is None:
                p = etree.SubElement(tc, qn("w:p"))
            # Clear runs
            for r_el in list(p.findall(qn("w:r"))):
                p.remove(r_el)
            # Add new run with text
            r_el = etree.SubElement(p, qn("w:r"))
            t = etree.SubElement(r_el, qn("w:t"))
            t.text = str(val)


# =============================================================================
# Cell Merge Helpers
# =============================================================================


def _get_vmerge_val(tc_el: etree._Element) -> str | None:
    """Get vMerge value from a tc element.

    Returns:
        'restart' for merge origin, 'continue' for continuation, None for no merge.
    """
    tcPr = tc_el.find(_W_TCPR)
    if tcPr is None:
        return None
    vMerge = tcPr.find(_W_VMERGE)
    if vMerge is None:
        return None
    # vMerge with val="restart" is origin, vMerge without val is continue
    val = vMerge.get(_W_VAL)
    return val if val else "continue"


def _tc_at_grid_col(tr_el: etree._Element, grid_col: int) -> etree._Element | None:
    """Find the tc element at a given grid column, accounting for gridSpan.

    Returns the tc element or None if not found.
    """
    c = 0
    for tc in tr_el.findall(_W_TC):
        span = _get_grid_span(tc)
        if c == grid_col:
            return tc
        c += span
        if c > grid_col:
            # Grid column falls within a span, no tc origin at this position
            return None
    return None


def _calculate_row_span(tbl_el: etree._Element, start_row: int, col: int) -> int:
    """Calculate vertical span by checking vMerge='continue' in subsequent rows.

    Pure OOXML: Takes w:tbl element.
    """
    tr_els = tbl_el.findall(_W_TR)
    span = 1
    for r in range(start_row + 1, len(tr_els)):
        tc = _tc_at_grid_col(tr_els[r], col)
        if tc is not None:
            vmerge = _get_vmerge_val(tc)
            if vmerge == "continue":
                span += 1
            else:
                break
        else:
            break
    return span


def _get_cell_border(tc_el: etree._Element, side: str) -> str | None:
    """Extract border info from tc element. Returns 'style:size:color' or None."""
    tcPr = tc_el.find(_W_TCPR)
    borders = tcPr.find(_W_TBL_BORDERS) if tcPr is not None else None
    border_el = borders.find(qn(f"w:{side}")) if borders is not None else None
    if border_el is None:
        return None
    style = border_el.get(_W_VAL) or "single"
    sz = border_el.get(_W_SZ) or "4"
    color = border_el.get(_W_COLOR) or "auto"
    return f"{style}:{sz}:{color}"


def _get_cell_shading(tc_el: etree._Element) -> str | None:
    """Extract fill color from tc element. Returns hex color or None."""
    tcPr = tc_el.find(_W_TCPR)
    shd = tcPr.find(_W_SHD) if tcPr is not None else None
    if shd is None:
        return None
    fill = shd.get(_W_FILL)
    return fill.upper() if fill and fill.lower() != "auto" else None


# =============================================================================
# Table Reading Functions
# =============================================================================


# XML attribute constants for table properties
_W_VALIGN = qn("w:vAlign")
_W_W = qn("w:w")
_W_TBL_PR = qn("w:tblPr")
_W_JC = qn("w:jc")
_W_TBL_LAYOUT = qn("w:tblLayout")
_W_TYPE = qn("w:type")
_W_TR_HEIGHT = qn("w:trHeight")
_W_H_RULE = qn("w:hRule")

# EMU to inches conversion
_EMUS_PER_INCH = 914400
_TWIPS_PER_INCH = 1440


def _get_cell_width(tc_el: etree._Element) -> float | None:
    """Get cell width in inches from tc element. Returns None if not set."""
    tcPr = tc_el.find(_W_TCPR)
    if tcPr is None:
        return None
    tcW = tcPr.find(qn("w:tcW"))
    if tcW is None:
        return None
    w_val = tcW.get(_W_W)
    w_type = tcW.get(_W_TYPE) or "dxa"  # dxa (twips) is default
    if w_val is None:
        return None
    try:
        val = int(w_val)
    except ValueError:
        raise ValueError(f"Invalid cell width value: {w_val!r}")
    if w_type == "dxa":
        return val / _TWIPS_PER_INCH
    elif w_type == "pct":
        return None  # Percentage width, no absolute value
    elif w_type in ("auto", "nil"):
        return None  # Auto-width, no absolute value
    raise ValueError(f"Unknown cell width type: {w_type!r}")


def _get_cell_valign(tc_el: etree._Element) -> str | None:
    """Get vertical alignment from tc element. Returns 'top', 'center', or 'bottom'."""
    tcPr = tc_el.find(_W_TCPR)
    if tcPr is None:
        return None
    vAlign = tcPr.find(_W_VALIGN)
    if vAlign is None:
        return None
    val = vAlign.get(_W_VAL)
    if val in ("top", "center", "bottom"):
        return val
    return None


def build_table_cells(tbl_el: etree._Element, table_id: str = "") -> list[CellInfo]:
    """Build list of CellInfo with merge information.

    Pure OOXML: Takes w:tbl element.

    Detects:
    - Horizontal merges via gridSpan attribute
    - Vertical merges via vMerge XML attribute
    """
    result = []
    tr_els = tbl_el.findall(_W_TR)

    for r, tr_el in enumerate(tr_els):
        tc_els = tr_el.findall(_W_TC)
        c = 0
        for tc in tc_els:
            vmerge = _get_vmerge_val(tc)
            grid_span = _get_grid_span(tc)

            if vmerge == "continue":
                # Vertical continuation cell
                result.append(
                    CellInfo(
                        row=r,
                        col=c,
                        text="",
                        hierarchical_id=f"{table_id}#r{r}c{c}" if table_id else "",
                        is_merge_origin=False,
                        grid_span=1,
                        row_span=1,
                    )
                )
                # Add horizontal continuation entries for wide continuation cells
                for span_c in range(1, grid_span):
                    result.append(
                        CellInfo(
                            row=r,
                            col=c + span_c,
                            text="",
                            hierarchical_id=(
                                f"{table_id}#r{r}c{c + span_c}" if table_id else ""
                            ),
                            is_merge_origin=False,
                            grid_span=1,
                            row_span=1,
                        )
                    )
                c += grid_span
            else:
                # Origin cell (vmerge='restart' or None) or normal cell
                row_span = (
                    _calculate_row_span(tbl_el, r, c) if vmerge == "restart" else 1
                )
                # Get text and properties from the cell element
                text = get_cell_text(tc)
                width_inches = _get_cell_width(tc)
                valign = _get_cell_valign(tc)
                # Extract border and shading from tc element
                border_top = _get_cell_border(tc, "top")
                border_bottom = _get_cell_border(tc, "bottom")
                border_left = _get_cell_border(tc, "left")
                border_right = _get_cell_border(tc, "right")
                fill_color = _get_cell_shading(tc)
                result.append(
                    CellInfo(
                        row=r,
                        col=c,
                        text=text,
                        hierarchical_id=f"{table_id}#r{r}c{c}" if table_id else "",
                        is_merge_origin=True,
                        grid_span=grid_span,
                        row_span=row_span,
                        width_inches=width_inches,
                        vertical_alignment=valign,
                        border_top=border_top,
                        border_bottom=border_bottom,
                        border_left=border_left,
                        border_right=border_right,
                        fill_color=fill_color,
                        nested_tables=len(get_cell_tables(tc)),
                    )
                )
                # Add continuation entries for horizontal span
                for span_c in range(1, grid_span):
                    result.append(
                        CellInfo(
                            row=r,
                            col=c + span_c,
                            text="",
                            hierarchical_id=(
                                f"{table_id}#r{r}c{c + span_c}" if table_id else ""
                            ),
                            is_merge_origin=False,
                            grid_span=1,
                            row_span=1,
                        )
                    )
                c += grid_span
    return result


def _get_table_alignment(tbl_el: etree._Element) -> str | None:
    """Get table horizontal alignment. Returns 'left', 'center', 'right', or None."""
    tblPr = tbl_el.find(_W_TBL_PR)
    if tblPr is None:
        return None
    jc = tblPr.find(_W_JC)
    if jc is None:
        return None
    val = jc.get(_W_VAL)
    if val in ("left", "center", "right", "start", "end"):
        return "left" if val == "start" else ("right" if val == "end" else val)
    return None


def _get_table_autofit(tbl_el: etree._Element) -> bool:
    """Check if table uses autofit layout. Returns True if autofit, False if fixed."""
    tblPr = tbl_el.find(_W_TBL_PR)
    if tblPr is None:
        return True  # Default is autofit
    tblLayout = tblPr.find(_W_TBL_LAYOUT)
    if tblLayout is None:
        return True
    layout_type = tblLayout.get(_W_TYPE)
    return layout_type != "fixed"


def _get_row_height(tr_el: etree._Element) -> tuple[float | None, str | None]:
    """Get row height in inches and height rule. Returns (height, rule)."""
    trPr = tr_el.find(_W_TRPR)
    if trPr is None:
        return None, None
    trHeight = trPr.find(_W_TR_HEIGHT)
    if trHeight is None:
        return None, None
    val = trHeight.get(_W_VAL)
    rule = trHeight.get(_W_H_RULE)
    # Map rule values
    rule_map = {"exact": "exactly", "atLeast": "at_least", "auto": "auto"}
    height_rule = rule_map.get(rule, "at_least") if rule else "at_least"
    # Convert twips to inches
    if val is None:
        height_inches = None
    else:
        try:
            height_inches = int(val) / _TWIPS_PER_INCH
        except ValueError:
            raise ValueError(f"Invalid row height value: {val!r}")
    return height_inches, height_rule


def _is_header_row(tr_el: etree._Element) -> bool:
    """Check if row is marked as header (repeats on page break)."""
    trPr = tr_el.find(_W_TRPR)
    if trPr is None:
        return False
    return trPr.find(_W_TBL_HEADER) is not None


def build_table_layout(tbl_el: etree._Element, table_id: str) -> TableLayoutInfo:
    """Build table layout info including row heights and alignment.

    Pure OOXML: Takes w:tbl element.
    """
    rows = []
    tr_els = tbl_el.findall(_W_TR)

    for i, tr_el in enumerate(tr_els):
        height_inches, height_rule = _get_row_height(tr_el)
        is_header = _is_header_row(tr_el)
        rows.append(
            RowInfo(
                index=i,
                height_inches=height_inches,
                height_rule=height_rule,
                is_header=is_header,
            )
        )

    return TableLayoutInfo(
        table_id=table_id,
        alignment=_get_table_alignment(tbl_el),
        autofit=_get_table_autofit(tbl_el),
        rows=rows,
    )


# =============================================================================
# Table Modification Functions
# =============================================================================


def _create_table_element(
    rows: int, cols: int, col_width_twips: int = 2160
) -> etree._Element:
    """Create a new w:tbl element with grid and rows.

    Pure OOXML: Returns w:tbl element.

    Args:
        rows: Number of rows
        cols: Number of columns
        col_width_twips: Column width in twips (default 2160 = 1.5 inches)
    """
    tbl = etree.Element(qn("w:tbl"))

    # Table properties with borders
    tblPr = etree.SubElement(tbl, qn("w:tblPr"))
    tblBorders = etree.SubElement(tblPr, qn("w:tblBorders"))
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = etree.SubElement(tblBorders, qn(f"w:{side}"))
        border.set(_W_VAL, "single")
        border.set(_W_SZ, "4")
        border.set(_W_COLOR, "auto")

    # Grid definition
    tblGrid = etree.SubElement(tbl, _W_TBLGRID)
    for _ in range(cols):
        gridCol = etree.SubElement(tblGrid, _W_GRIDCOL)
        gridCol.set(_W_W, str(col_width_twips))

    # Rows
    for _ in range(rows):
        tr = etree.SubElement(tbl, _W_TR)
        for _ in range(cols):
            tc = etree.SubElement(tr, _W_TC)
            # Each cell needs at least one paragraph
            p = etree.SubElement(tc, qn("w:p"))
            etree.SubElement(p, qn("w:r"))

    return tbl


def insert_table_relative(
    target_el: etree._Element,
    table_data: list[list[str]],
    position: str,
) -> etree._Element:
    """Insert table before/after target element.

    Pure OOXML: Takes target element, returns w:tbl element.
    """
    rows = len(table_data)
    cols = max((len(r) for r in table_data), default=1)
    tbl = _create_table_element(rows, cols)
    populate_table(tbl, table_data)
    _insert_at(target_el, tbl, position)
    return tbl


def replace_table(
    old_tbl_el: etree._Element, table_data: list[list[str]]
) -> etree._Element:
    """Replace table with new data.

    Pure OOXML: Takes w:tbl element, returns new w:tbl element.
    """
    rows = len(table_data)
    cols = max((len(r) for r in table_data), default=1)
    new_tbl = _create_table_element(rows, cols)
    populate_table(new_tbl, table_data)
    old_tbl_el.addprevious(new_tbl)
    old_tbl_el.getparent().remove(old_tbl_el)
    return new_tbl


def _set_cell_vmerge(tc_el: etree._Element, val: str | None) -> None:
    """Set or remove vMerge on a cell. val='restart' for origin, 'continue' for span, None to remove."""
    tcPr = tc_el.find(_W_TCPR)
    if tcPr is None:
        tcPr = etree.Element(_W_TCPR)
        tc_el.insert(0, tcPr)

    vMerge = tcPr.find(_W_VMERGE)
    if val is None:
        if vMerge is not None:
            tcPr.remove(vMerge)
    else:
        if vMerge is None:
            vMerge = etree.SubElement(tcPr, _W_VMERGE)
        if val == "restart":
            vMerge.set(_W_VAL, "restart")
        else:
            # 'continue' is represented by vMerge without val attribute
            if _W_VAL in vMerge.attrib:
                del vMerge.attrib[_W_VAL]


def _set_cell_gridspan(tc_el: etree._Element, span: int) -> None:
    """Set gridSpan on a cell. span=1 removes the attribute."""
    tcPr = tc_el.find(_W_TCPR)
    if tcPr is None:
        tcPr = etree.Element(_W_TCPR)
        tc_el.insert(0, tcPr)

    gridSpan = tcPr.find(_W_GRIDSPAN)
    if span <= 1:
        if gridSpan is not None:
            tcPr.remove(gridSpan)
    else:
        if gridSpan is None:
            gridSpan = etree.SubElement(tcPr, _W_GRIDSPAN)
        gridSpan.set(_W_VAL, str(span))


def merge_cells(
    tbl_el: etree._Element, start_row: int, start_col: int, end_row: int, end_col: int
) -> None:
    """Merge a rectangular region of cells. All indices are 0-based.

    Pure OOXML: Takes w:tbl element.

    Sets gridSpan for horizontal merge and vMerge for vertical merge.
    """
    tr_els = tbl_el.findall(_W_TR)
    rows = len(tr_els)

    # Count columns from grid
    tblGrid = tbl_el.find(_W_TBLGRID)
    cols = len(tblGrid.findall(_W_GRIDCOL)) if tblGrid is not None else 0
    if cols == 0:
        # Fallback: count cells in first row
        cols = len(tr_els[0].findall(_W_TC)) if tr_els else 0

    # Validate bounds
    if not (0 <= start_row < rows and 0 <= end_row < rows):
        raise ValueError(
            f"Row indices must be 0-{rows - 1}, got start_row={start_row}, end_row={end_row}"
        )
    if not (0 <= start_col < cols and 0 <= end_col < cols):
        raise ValueError(
            f"Column indices must be 0-{cols - 1}, got start_col={start_col}, end_col={end_col}"
        )
    if start_row > end_row or start_col > end_col:
        raise ValueError(
            f"Start must be <= end: ({start_row},{start_col}) to ({end_row},{end_col})"
        )

    h_span = end_col - start_col + 1
    v_span = end_row - start_row + 1

    for r in range(start_row, end_row + 1):
        tr_el = tr_els[r]
        tc_els = tr_el.findall(_W_TC)

        for c in range(start_col, end_col + 1):
            tc = tc_els[c]
            is_origin = r == start_row and c == start_col

            if is_origin:
                # Origin cell: set gridSpan and vMerge=restart if needed
                if h_span > 1:
                    _set_cell_gridspan(tc, h_span)
                if v_span > 1:
                    _set_cell_vmerge(tc, "restart")
            else:
                # Continuation cells
                if r == start_row:
                    # First row, horizontal continuation: remove cell content
                    # In proper merge, these cells would be removed, but we simplify
                    for p in tc.findall(qn("w:p")):
                        for r_el in list(p.findall(qn("w:r"))):
                            p.remove(r_el)
                else:
                    # Subsequent rows: set vMerge=continue
                    _set_cell_vmerge(tc, "continue")
                    if c == start_col and h_span > 1:
                        _set_cell_gridspan(tc, h_span)


def replace_table_cell(tbl_el: etree._Element, row: int, col: int, text: str) -> None:
    """Replace text in a table cell. Row/col are 0-based.

    Pure OOXML: Takes w:tbl element.
    """
    tr_els = tbl_el.findall(_W_TR)
    tc_els = tr_els[row].findall(_W_TC)
    tc = tc_els[col]

    # Clear existing paragraphs and add new one with text
    for p in list(tc.findall(qn("w:p"))):
        tc.remove(p)
    p = etree.SubElement(tc, qn("w:p"))
    r = etree.SubElement(p, qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = text


def add_table_row(tbl_el: etree._Element, data: list[str] | None = None) -> int:
    """Add row to table. Returns new row index (0-based).

    Pure OOXML: Takes w:tbl element.
    """
    tr_els = tbl_el.findall(_W_TR)
    # Get column count from grid or existing row
    tblGrid = tbl_el.find(_W_TBLGRID)
    if tblGrid is not None:
        cols = len(tblGrid.findall(_W_GRIDCOL))
    else:
        cols = len(tr_els[0].findall(_W_TC)) if tr_els else 1

    # Create new row
    tr = etree.SubElement(tbl_el, _W_TR)
    for c in range(cols):
        tc = etree.SubElement(tr, _W_TC)
        p = etree.SubElement(tc, qn("w:p"))
        r_el = etree.SubElement(p, qn("w:r"))
        t = etree.SubElement(r_el, qn("w:t"))
        if data and c < len(data):
            t.text = data[c]

    return len(tr_els)  # 0-based index of new row


def add_table_column(
    tbl_el: etree._Element, width_twips: int = 2160, data: list[str] | None = None
) -> int:
    """Add column to table. Returns new col index (0-based).

    Pure OOXML: Takes w:tbl element.

    Args:
        tbl_el: The table element
        width_twips: Column width in twips (default 2160 = 1.5 inches)
        data: Optional list of cell values for the new column
    """
    # Add to grid definition
    tblGrid = tbl_el.find(_W_TBLGRID)
    if tblGrid is not None:
        gridCol = etree.SubElement(tblGrid, _W_GRIDCOL)
        gridCol.set(_W_W, str(width_twips))
        col_idx = len(tblGrid.findall(_W_GRIDCOL)) - 1
    else:
        col_idx = 0

    # Add cell to each row
    tr_els = tbl_el.findall(_W_TR)
    for i, tr in enumerate(tr_els):
        tc = etree.SubElement(tr, _W_TC)
        # Set width
        tcPr = etree.SubElement(tc, _W_TCPR)
        tcW = etree.SubElement(tcPr, qn("w:tcW"))
        tcW.set(_W_W, str(width_twips))
        tcW.set(_W_TYPE, "dxa")
        # Add paragraph with optional text
        p = etree.SubElement(tc, qn("w:p"))
        r_el = etree.SubElement(p, qn("w:r"))
        t = etree.SubElement(r_el, qn("w:t"))
        if data and i < len(data):
            t.text = data[i]

    return col_idx


def delete_table_row(tbl_el: etree._Element, row_index: int) -> None:
    """Delete row from table (0-based index).

    Pure OOXML: Takes w:tbl element.
    """
    tr_els = tbl_el.findall(_W_TR)
    tr = tr_els[row_index]  # Let IndexError propagate
    tbl_el.remove(tr)


def delete_table_column(tbl_el: etree._Element, col_index: int) -> None:
    """Delete column from table (0-based index). Removes grid definition and cells.

    Pure OOXML: Takes w:tbl element.
    """
    # 1. Remove the grid column definition
    tblGrid = tbl_el.find(_W_TBLGRID)
    if tblGrid is not None:
        tblGrid.remove(tblGrid.findall(_W_GRIDCOL)[col_index])

    # 2. Remove the cell from every row
    for tr in tbl_el.findall(_W_TR):
        tc_els = tr.findall(_W_TC)
        if col_index < len(tc_els):
            tr.remove(tc_els[col_index])


# =============================================================================
# Table Layout Functions
# =============================================================================


def set_table_alignment(tbl_el: etree._Element, alignment: str) -> None:
    """Set table horizontal alignment. Valid: left, center, right.

    Pure OOXML: Takes w:tbl element.
    """
    tblPr = tbl_el.find(_W_TBL_PR)
    if tblPr is None:
        tblPr = etree.Element(_W_TBL_PR)
        tbl_el.insert(0, tblPr)

    jc = tblPr.find(_W_JC)
    if jc is None:
        jc = etree.SubElement(tblPr, _W_JC)
    jc.set(_W_VAL, alignment.lower())


def set_row_height(
    tbl_el: etree._Element, row_index: int, height_inches: float, rule: str = "at_least"
) -> None:
    """Set row height. Rule: auto, at_least, exactly.

    Pure OOXML: Takes w:tbl element.

    Args:
        tbl_el: The table element
        row_index: 0-based row index
        height_inches: Height in inches
        rule: 'auto', 'at_least' (default, prevents clipping), or 'exactly'
    """
    rule_map = {"auto": "auto", "at_least": "atLeast", "exactly": "exact"}

    tr_els = tbl_el.findall(_W_TR)
    tr = tr_els[row_index]  # Let IndexError propagate

    trPr = tr.find(_W_TRPR)
    if trPr is None:
        trPr = etree.Element(_W_TRPR)
        tr.insert(0, trPr)

    trHeight = trPr.find(_W_TR_HEIGHT)
    if rule.lower() == "auto":
        # Remove height specification for auto
        if trHeight is not None:
            trPr.remove(trHeight)
    else:
        if trHeight is None:
            trHeight = etree.SubElement(trPr, _W_TR_HEIGHT)
        # Convert inches to twips
        height_twips = int(height_inches * _TWIPS_PER_INCH)
        trHeight.set(_W_VAL, str(height_twips))
        trHeight.set(_W_H_RULE, rule_map[rule.lower()])


def set_table_autofit(tbl_el: etree._Element, autofit: bool) -> None:
    """Set table autofit mode.

    Pure OOXML: Takes w:tbl element.
    When autofit=True, removes fixed layout (autofit is default).
    When autofit=False, sets layout to fixed.
    """
    tblPr = tbl_el.find(_W_TBL_PR)
    if autofit:
        # Remove tblLayout to use default autofit
        if tblPr is not None:
            tblLayout = tblPr.find(_W_TBL_LAYOUT)
            if tblLayout is not None:
                tblPr.remove(tblLayout)
    else:
        # Set to fixed layout
        if tblPr is None:
            tblPr = etree.Element(_W_TBL_PR)
            tbl_el.insert(0, tblPr)
        tblLayout = tblPr.find(_W_TBL_LAYOUT)
        if tblLayout is None:
            tblLayout = etree.SubElement(tblPr, _W_TBL_LAYOUT)
        tblLayout.set(_W_TYPE, "fixed")


def set_table_fixed_layout(tbl_el: etree._Element, column_widths: list[float]) -> None:
    """Set table to fixed layout with explicit column widths (inches).

    Pure OOXML: Takes w:tbl element.
    """
    # Set layout type to fixed
    tblPr = tbl_el.find(_W_TBL_PR)
    if tblPr is None:
        tblPr = etree.Element(_W_TBL_PR)
        tbl_el.insert(0, tblPr)

    tblLayout = tblPr.find(_W_TBL_LAYOUT)
    if tblLayout is None:
        tblLayout = etree.SubElement(tblPr, _W_TBL_LAYOUT)
    tblLayout.set(_W_TYPE, "fixed")

    # Set column widths in grid
    tblGrid = tbl_el.find(_W_TBLGRID)
    if tblGrid is not None:
        gridCols = tblGrid.findall(_W_GRIDCOL)
        for i, width in enumerate(column_widths):
            if i < len(gridCols):
                width_twips = int(width * _TWIPS_PER_INCH)
                gridCols[i].set(_W_W, str(width_twips))


def set_cell_width(
    tbl_el: etree._Element, row: int, col: int, width_inches: float
) -> None:
    """Set cell width.

    Pure OOXML: Takes w:tbl element.
    """
    tr_els = tbl_el.findall(_W_TR)
    tc_els = tr_els[row].findall(_W_TC)
    tc = tc_els[col]

    tcPr = tc.find(_W_TCPR)
    if tcPr is None:
        tcPr = etree.Element(_W_TCPR)
        tc.insert(0, tcPr)

    tcW = tcPr.find(qn("w:tcW"))
    if tcW is None:
        tcW = etree.SubElement(tcPr, qn("w:tcW"))

    width_twips = int(width_inches * _TWIPS_PER_INCH)
    tcW.set(_W_W, str(width_twips))
    tcW.set(_W_TYPE, "dxa")


def set_cell_vertical_alignment(
    tbl_el: etree._Element, row: int, col: int, alignment: str
) -> None:
    """Set cell vertical alignment. Valid: top, center, bottom.

    Pure OOXML: Takes w:tbl element.
    """

    tr_els = tbl_el.findall(_W_TR)
    tc_els = tr_els[row].findall(_W_TC)
    tc = tc_els[col]

    tcPr = tc.find(_W_TCPR)
    if tcPr is None:
        tcPr = etree.Element(_W_TCPR)
        tc.insert(0, tcPr)

    vAlign = tcPr.find(_W_VALIGN)
    if vAlign is None:
        vAlign = etree.SubElement(tcPr, _W_VALIGN)
    vAlign.set(_W_VAL, alignment.lower())


def set_cell_borders(
    tbl_el: etree._Element,
    row: int,
    col: int,
    top: str | None = None,
    bottom: str | None = None,
    left: str | None = None,
    right: str | None = None,
) -> None:
    """Set cell borders. Format: 'style:size:color' e.g. 'single:24:000000'.

    Pure OOXML: Takes w:tbl element.

    Args:
        tbl_el: The table element
        row: 0-based row index
        col: 0-based column index
        top, bottom, left, right: Border specs in 'style:size:color' format
            - style: single, double, dotted, dashed, etc.
            - size: in eighths of a point (24 = 3pt)
            - color: hex color (e.g., '000000' for black)
    """
    tr_els = tbl_el.findall(_W_TR)
    tc_els = tr_els[row].findall(_W_TC)
    tc = tc_els[col]

    # Get or create tcPr
    tcPr = tc.find(_W_TCPR)
    if tcPr is None:
        tcPr = etree.Element(_W_TCPR)
        tc.insert(0, tcPr)

    # Get or create tcBorders
    tcBorders = tcPr.find(_W_TBL_BORDERS)
    if tcBorders is None:
        tcBorders = etree.SubElement(tcPr, _W_TBL_BORDERS)

    def set_border(side: str, spec: str) -> None:
        style, sz, color = spec.split(":")
        border_el = tcBorders.find(qn(f"w:{side}"))
        if border_el is None:
            border_el = etree.SubElement(tcBorders, qn(f"w:{side}"))
        border_el.set(_W_VAL, style)
        border_el.set(_W_SZ, sz)
        border_el.set(_W_COLOR, color)

    if top:
        set_border("top", top)
    if bottom:
        set_border("bottom", bottom)
    if left:
        set_border("left", left)
    if right:
        set_border("right", right)


def set_cell_shading(
    tbl_el: etree._Element, row: int, col: int, fill_color: str
) -> None:
    """Set cell background color.

    Pure OOXML: Takes w:tbl element.

    Args:
        tbl_el: The table element
        row: 0-based row index
        col: 0-based column index
        fill_color: Hex color (e.g., 'FF0000' for red)
    """
    tr_els = tbl_el.findall(_W_TR)
    tc_els = tr_els[row].findall(_W_TC)
    tc = tc_els[col]

    # Get or create tcPr
    tcPr = tc.find(_W_TCPR)
    if tcPr is None:
        tcPr = etree.Element(_W_TCPR)
        tc.insert(0, tcPr)

    # Get or create shd
    shd = tcPr.find(_W_SHD)
    if shd is None:
        shd = etree.SubElement(tcPr, _W_SHD)

    shd.set(_W_VAL, "clear")
    shd.set(_W_FILL, fill_color.upper())


def set_header_row(
    tbl_el: etree._Element, row_index: int, is_header: bool = True
) -> None:
    """Mark row as header (repeats on each page in multi-page tables).

    Pure OOXML: Takes w:tbl element.

    Args:
        tbl_el: The table element
        row_index: 0-based row index
        is_header: True to mark as header, False to unmark
    """
    tr_els = tbl_el.findall(_W_TR)
    tr = tr_els[row_index]  # Let IndexError propagate

    # Get or create trPr
    trPr = tr.find(_W_TRPR)
    if trPr is None:
        trPr = etree.Element(_W_TRPR)
        tr.insert(0, trPr)

    # Find existing tblHeader
    tblHeader = trPr.find(_W_TBL_HEADER)

    if is_header:
        if tblHeader is None:
            etree.SubElement(trPr, _W_TBL_HEADER)
    else:
        if tblHeader is not None:
            trPr.remove(tblHeader)


def get_header_rows(tbl_el: etree._Element) -> list[int]:
    """Get indices of rows marked as headers.

    Pure OOXML: Takes w:tbl element.

    Returns:
        List of 0-based row indices that are marked as headers
    """
    result = []
    for i, tr in enumerate(tbl_el.findall(_W_TR)):
        trPr = tr.find(_W_TRPR)
        if trPr is not None and trPr.find(_W_TBL_HEADER) is not None:
            result.append(i)
    return result
