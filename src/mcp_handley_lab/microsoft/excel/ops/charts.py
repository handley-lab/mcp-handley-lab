"""Chart operations for Excel workbooks.

Charts in OOXML consist of multiple related parts:
- /xl/charts/chart{n}.xml - DrawingML chart definition
- /xl/drawings/drawing{n}.xml - anchor/positioning on sheet
- Sheet relationship to drawing
- Drawing relationship to chart

Supports: bar, column, line, pie, scatter, area chart types.
"""

import contextlib

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import RT, qn
from mcp_handley_lab.microsoft.excel.models import ChartInfo
from mcp_handley_lab.microsoft.excel.ops.core import (
    insert_sheet_element,
    make_chart_id,
    parse_cell_ref,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage

# DrawingML namespaces
DRAWING_NSMAP = {
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

# Content types
CT_DRAWING = "application/vnd.openxmlformats-officedocument.drawing+xml"
CT_CHART = "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"

# Relationship types
RT_CHART = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"


def _qn_xdr(tag: str) -> str:
    """Clark notation for spreadsheetDrawing namespace."""
    return f"{{{DRAWING_NSMAP['xdr']}}}{tag}"


def _qn_a(tag: str) -> str:
    """Clark notation for drawingml main namespace."""
    return f"{{{DRAWING_NSMAP['a']}}}{tag}"


def _qn_c(tag: str) -> str:
    """Clark notation for chart namespace."""
    return f"{{{DRAWING_NSMAP['c']}}}{tag}"


def _qn_r(tag: str) -> str:
    """Clark notation for relationships namespace."""
    return f"{{{DRAWING_NSMAP['r']}}}{tag}"


def _get_sheet_drawing_path(pkg: ExcelPackage, sheet_name: str) -> str | None:
    """Get drawing part path for sheet, if any."""
    for name, _rId, partname in pkg.get_sheet_paths():
        if name == sheet_name:
            sheet_rels = pkg.get_rels(partname)
            drawing_rId = sheet_rels.rId_for_reltype(RT.DRAWING)
            if drawing_rId:
                return pkg.resolve_rel_target(partname, drawing_rId)
            return None
    raise KeyError(f"Sheet not found: {sheet_name}")


def _get_or_create_drawing(
    pkg: ExcelPackage, sheet_name: str
) -> tuple[str, etree._Element]:
    """Get or create drawing part for sheet. Returns (path, root element)."""
    for name, _rId, partname in pkg.get_sheet_paths():
        if name == sheet_name:
            sheet_rels = pkg.get_rels(partname)
            drawing_rId = sheet_rels.rId_for_reltype(RT.DRAWING)

            if drawing_rId:
                # Existing drawing
                drawing_path = pkg.resolve_rel_target(partname, drawing_rId)
                drawing_xml = pkg.get_xml(drawing_path)
                return drawing_path, drawing_xml

            # Create new drawing
            drawing_num = _find_next_drawing_number(pkg)
            drawing_path = f"/xl/drawings/drawing{drawing_num}.xml"

            # Create drawing XML
            drawing_xml = etree.Element(
                _qn_xdr("wsDr"),
                nsmap={
                    None: DRAWING_NSMAP["xdr"],
                    "a": DRAWING_NSMAP["a"],
                    "r": DRAWING_NSMAP["r"],
                },
            )
            pkg.set_xml(drawing_path, drawing_xml, CT_DRAWING)

            # Add relationship from sheet to drawing
            pkg.relate_to(partname, f"../drawings/drawing{drawing_num}.xml", RT.DRAWING)

            # Add <drawing> element to sheet XML at correct position
            sheet_xml = pkg.get_sheet_xml(sheet_name)
            drawing_elem = etree.Element(qn("x:drawing"))
            # Get the rId we just created
            new_rId = pkg.get_rels(partname).rId_for_reltype(RT.DRAWING)
            drawing_elem.set(qn("r:id"), new_rId)
            insert_sheet_element(sheet_xml, "drawing", drawing_elem)
            pkg.mark_xml_dirty(partname)

            return drawing_path, drawing_xml

    raise KeyError(f"Sheet not found: {sheet_name}")


def _find_next_drawing_number(pkg: ExcelPackage) -> int:
    """Find next available drawing number."""
    max_num = 0
    for partname in pkg.iter_partnames():
        if partname.startswith("/xl/drawings/drawing") and partname.endswith(".xml"):
            try:
                num = int(partname[20:-4])  # Extract number from path
                max_num = max(max_num, num)
            except ValueError:
                pass
    return max_num + 1


def _find_next_chart_number(pkg: ExcelPackage) -> int:
    """Find next available chart number."""
    max_num = 0
    for partname in pkg.iter_partnames():
        if partname.startswith("/xl/charts/chart") and partname.endswith(".xml"):
            try:
                num = int(partname[16:-4])  # Extract number from path
                max_num = max(max_num, num)
            except ValueError:
                pass
    return max_num + 1


def _parse_position(position: str) -> tuple[int, int]:
    """Parse position like 'E5' to (col, row) 0-indexed."""
    col_letter, row_num, _, _ = parse_cell_ref(position)
    from mcp_handley_lab.microsoft.excel.ops.core import column_letter_to_index

    col = column_letter_to_index(col_letter)
    return col - 1, row_num - 1  # Convert to 0-indexed


def _create_chart_xml(
    chart_type: str,
    data_range: str,
    sheet_name: str,
    title: str | None,
) -> etree._Element:
    """Create chart XML for the given type and data.

    Chart types: bar, column, line, pie, scatter, area
    """
    # Normalize chart type
    chart_type = chart_type.lower()

    # Create chart root
    chart_space = etree.Element(
        _qn_c("chartSpace"),
        nsmap={
            None: DRAWING_NSMAP["c"],
            "a": DRAWING_NSMAP["a"],
            "r": DRAWING_NSMAP["r"],
        },
    )

    # Add date1904 element (false for standard date system)
    etree.SubElement(chart_space, _qn_c("date1904"), val="0")

    # Add lang
    etree.SubElement(chart_space, _qn_c("lang"), val="en-US")

    # Add roundedCorners
    etree.SubElement(chart_space, _qn_c("roundedCorners"), val="0")

    # Create chart element
    chart = etree.SubElement(chart_space, _qn_c("chart"))

    # Add title if provided
    if title:
        title_elem = etree.SubElement(chart, _qn_c("title"))
        tx = etree.SubElement(title_elem, _qn_c("tx"))
        rich = etree.SubElement(tx, _qn_c("rich"))
        etree.SubElement(rich, _qn_a("bodyPr"))
        etree.SubElement(rich, _qn_a("lstStyle"))
        p = etree.SubElement(rich, _qn_a("p"))
        pPr = etree.SubElement(p, _qn_a("pPr"))
        etree.SubElement(pPr, _qn_a("defRPr"))
        r = etree.SubElement(p, _qn_a("r"))
        etree.SubElement(r, _qn_a("rPr"), lang="en-US")
        t = etree.SubElement(r, _qn_a("t"))
        t.text = title
        etree.SubElement(title_elem, _qn_c("overlay"), val="0")

    # Add autoTitleDeleted
    etree.SubElement(chart, _qn_c("autoTitleDeleted"), val="0" if title else "1")

    # Create plot area
    plot_area = etree.SubElement(chart, _qn_c("plotArea"))
    etree.SubElement(plot_area, _qn_c("layout"))

    # Format data range with sheet name
    full_range = f"'{sheet_name}'!{data_range}"

    # Add chart type-specific elements
    if chart_type == "bar":
        _add_bar_chart(plot_area, full_range, bar_dir="bar")
    elif chart_type == "column":
        _add_bar_chart(plot_area, full_range, bar_dir="col")
    elif chart_type == "line":
        _add_line_chart(plot_area, full_range)
    elif chart_type == "pie":
        _add_pie_chart(plot_area, full_range)
    elif chart_type == "scatter":
        _add_scatter_chart(plot_area, full_range)
    elif chart_type == "area":
        _add_area_chart(plot_area, full_range)
    else:
        raise ValueError(f"Unsupported chart type: {chart_type}")

    # Add axes for non-pie charts
    if chart_type != "pie":
        _add_axes(plot_area, chart_type)

    # Add legend
    legend = etree.SubElement(chart, _qn_c("legend"))
    etree.SubElement(legend, _qn_c("legendPos"), val="r")
    etree.SubElement(legend, _qn_c("overlay"), val="0")

    # Add plotVisOnly
    etree.SubElement(chart, _qn_c("plotVisOnly"), val="1")

    # Add dispBlanksAs
    etree.SubElement(chart, _qn_c("dispBlanksAs"), val="gap")

    # Add showDLblsOverMax
    etree.SubElement(chart, _qn_c("showDLblsOverMax"), val="0")

    # Add printSettings
    print_settings = etree.SubElement(chart_space, _qn_c("printSettings"))
    etree.SubElement(print_settings, _qn_c("headerFooter"))
    etree.SubElement(
        print_settings,
        _qn_c("pageMargins"),
        b="0.75",
        l="0.7",
        r="0.7",
        t="0.75",
        header="0.3",
        footer="0.3",
    )
    etree.SubElement(print_settings, _qn_c("pageSetup"))

    return chart_space


def _add_bar_chart(
    plot_area: etree._Element, data_range: str, bar_dir: str = "col"
) -> None:
    """Add bar/column chart to plot area."""
    bar_chart = etree.SubElement(plot_area, _qn_c("barChart"))
    etree.SubElement(bar_chart, _qn_c("barDir"), val=bar_dir)
    etree.SubElement(bar_chart, _qn_c("grouping"), val="clustered")
    etree.SubElement(bar_chart, _qn_c("varyColors"), val="0")

    # Add series
    ser = etree.SubElement(bar_chart, _qn_c("ser"))
    etree.SubElement(ser, _qn_c("idx"), val="0")
    etree.SubElement(ser, _qn_c("order"), val="0")

    # Add values reference
    val = etree.SubElement(ser, _qn_c("val"))
    num_ref = etree.SubElement(val, _qn_c("numRef"))
    f = etree.SubElement(num_ref, _qn_c("f"))
    f.text = data_range

    # Add data labels
    d_lbls = etree.SubElement(bar_chart, _qn_c("dLbls"))
    etree.SubElement(d_lbls, _qn_c("showLegendKey"), val="0")
    etree.SubElement(d_lbls, _qn_c("showVal"), val="0")
    etree.SubElement(d_lbls, _qn_c("showCatName"), val="0")
    etree.SubElement(d_lbls, _qn_c("showSerName"), val="0")
    etree.SubElement(d_lbls, _qn_c("showPercent"), val="0")
    etree.SubElement(d_lbls, _qn_c("showBubbleSize"), val="0")

    # Gap width
    etree.SubElement(bar_chart, _qn_c("gapWidth"), val="150")

    # Axis IDs
    etree.SubElement(bar_chart, _qn_c("axId"), val="100")
    etree.SubElement(bar_chart, _qn_c("axId"), val="200")


def _add_line_chart(plot_area: etree._Element, data_range: str) -> None:
    """Add line chart to plot area."""
    line_chart = etree.SubElement(plot_area, _qn_c("lineChart"))
    etree.SubElement(line_chart, _qn_c("grouping"), val="standard")
    etree.SubElement(line_chart, _qn_c("varyColors"), val="0")

    # Add series
    ser = etree.SubElement(line_chart, _qn_c("ser"))
    etree.SubElement(ser, _qn_c("idx"), val="0")
    etree.SubElement(ser, _qn_c("order"), val="0")

    # Add marker
    marker = etree.SubElement(ser, _qn_c("marker"))
    etree.SubElement(marker, _qn_c("symbol"), val="none")

    # Add values reference
    val = etree.SubElement(ser, _qn_c("val"))
    num_ref = etree.SubElement(val, _qn_c("numRef"))
    f = etree.SubElement(num_ref, _qn_c("f"))
    f.text = data_range

    # Data labels
    d_lbls = etree.SubElement(line_chart, _qn_c("dLbls"))
    etree.SubElement(d_lbls, _qn_c("showLegendKey"), val="0")
    etree.SubElement(d_lbls, _qn_c("showVal"), val="0")
    etree.SubElement(d_lbls, _qn_c("showCatName"), val="0")
    etree.SubElement(d_lbls, _qn_c("showSerName"), val="0")
    etree.SubElement(d_lbls, _qn_c("showPercent"), val="0")
    etree.SubElement(d_lbls, _qn_c("showBubbleSize"), val="0")

    # Smooth
    etree.SubElement(line_chart, _qn_c("smooth"), val="0")

    # Axis IDs
    etree.SubElement(line_chart, _qn_c("axId"), val="100")
    etree.SubElement(line_chart, _qn_c("axId"), val="200")


def _add_pie_chart(plot_area: etree._Element, data_range: str) -> None:
    """Add pie chart to plot area."""
    pie_chart = etree.SubElement(plot_area, _qn_c("pieChart"))
    etree.SubElement(pie_chart, _qn_c("varyColors"), val="1")

    # Add series
    ser = etree.SubElement(pie_chart, _qn_c("ser"))
    etree.SubElement(ser, _qn_c("idx"), val="0")
    etree.SubElement(ser, _qn_c("order"), val="0")

    # Add values reference
    val = etree.SubElement(ser, _qn_c("val"))
    num_ref = etree.SubElement(val, _qn_c("numRef"))
    f = etree.SubElement(num_ref, _qn_c("f"))
    f.text = data_range

    # Data labels
    d_lbls = etree.SubElement(pie_chart, _qn_c("dLbls"))
    etree.SubElement(d_lbls, _qn_c("showLegendKey"), val="0")
    etree.SubElement(d_lbls, _qn_c("showVal"), val="0")
    etree.SubElement(d_lbls, _qn_c("showCatName"), val="0")
    etree.SubElement(d_lbls, _qn_c("showSerName"), val="0")
    etree.SubElement(d_lbls, _qn_c("showPercent"), val="0")
    etree.SubElement(d_lbls, _qn_c("showBubbleSize"), val="0")

    # First slice angle
    etree.SubElement(pie_chart, _qn_c("firstSliceAng"), val="0")


def _add_scatter_chart(plot_area: etree._Element, data_range: str) -> None:
    """Add scatter chart to plot area."""
    scatter_chart = etree.SubElement(plot_area, _qn_c("scatterChart"))
    etree.SubElement(scatter_chart, _qn_c("scatterStyle"), val="lineMarker")
    etree.SubElement(scatter_chart, _qn_c("varyColors"), val="0")

    # Add series
    ser = etree.SubElement(scatter_chart, _qn_c("ser"))
    etree.SubElement(ser, _qn_c("idx"), val="0")
    etree.SubElement(ser, _qn_c("order"), val="0")

    # Add marker
    marker = etree.SubElement(ser, _qn_c("marker"))
    etree.SubElement(marker, _qn_c("symbol"), val="circle")
    etree.SubElement(marker, _qn_c("size"), val="5")

    # Y values reference
    y_val = etree.SubElement(ser, _qn_c("yVal"))
    num_ref = etree.SubElement(y_val, _qn_c("numRef"))
    f = etree.SubElement(num_ref, _qn_c("f"))
    f.text = data_range

    # Smooth
    etree.SubElement(ser, _qn_c("smooth"), val="0")

    # Data labels
    d_lbls = etree.SubElement(scatter_chart, _qn_c("dLbls"))
    etree.SubElement(d_lbls, _qn_c("showLegendKey"), val="0")
    etree.SubElement(d_lbls, _qn_c("showVal"), val="0")
    etree.SubElement(d_lbls, _qn_c("showCatName"), val="0")
    etree.SubElement(d_lbls, _qn_c("showSerName"), val="0")
    etree.SubElement(d_lbls, _qn_c("showPercent"), val="0")
    etree.SubElement(d_lbls, _qn_c("showBubbleSize"), val="0")

    # Axis IDs
    etree.SubElement(scatter_chart, _qn_c("axId"), val="100")
    etree.SubElement(scatter_chart, _qn_c("axId"), val="200")


def _add_area_chart(plot_area: etree._Element, data_range: str) -> None:
    """Add area chart to plot area."""
    area_chart = etree.SubElement(plot_area, _qn_c("areaChart"))
    etree.SubElement(area_chart, _qn_c("grouping"), val="standard")
    etree.SubElement(area_chart, _qn_c("varyColors"), val="0")

    # Add series
    ser = etree.SubElement(area_chart, _qn_c("ser"))
    etree.SubElement(ser, _qn_c("idx"), val="0")
    etree.SubElement(ser, _qn_c("order"), val="0")

    # Add values reference
    val = etree.SubElement(ser, _qn_c("val"))
    num_ref = etree.SubElement(val, _qn_c("numRef"))
    f = etree.SubElement(num_ref, _qn_c("f"))
    f.text = data_range

    # Data labels
    d_lbls = etree.SubElement(area_chart, _qn_c("dLbls"))
    etree.SubElement(d_lbls, _qn_c("showLegendKey"), val="0")
    etree.SubElement(d_lbls, _qn_c("showVal"), val="0")
    etree.SubElement(d_lbls, _qn_c("showCatName"), val="0")
    etree.SubElement(d_lbls, _qn_c("showSerName"), val="0")
    etree.SubElement(d_lbls, _qn_c("showPercent"), val="0")
    etree.SubElement(d_lbls, _qn_c("showBubbleSize"), val="0")

    # Axis IDs
    etree.SubElement(area_chart, _qn_c("axId"), val="100")
    etree.SubElement(area_chart, _qn_c("axId"), val="200")


def _add_axes(plot_area: etree._Element, chart_type: str) -> None:
    """Add category and value axes to plot area."""
    # Category axis (X)
    if chart_type == "scatter":
        cat_ax = etree.SubElement(plot_area, _qn_c("valAx"))
    else:
        cat_ax = etree.SubElement(plot_area, _qn_c("catAx"))

    etree.SubElement(cat_ax, _qn_c("axId"), val="100")
    scaling = etree.SubElement(cat_ax, _qn_c("scaling"))
    etree.SubElement(scaling, _qn_c("orientation"), val="minMax")
    etree.SubElement(cat_ax, _qn_c("delete"), val="0")
    etree.SubElement(cat_ax, _qn_c("axPos"), val="b")
    etree.SubElement(cat_ax, _qn_c("majorTickMark"), val="out")
    etree.SubElement(cat_ax, _qn_c("minorTickMark"), val="none")
    etree.SubElement(cat_ax, _qn_c("tickLblPos"), val="nextTo")
    etree.SubElement(cat_ax, _qn_c("crossAx"), val="200")
    etree.SubElement(cat_ax, _qn_c("crosses"), val="autoZero")
    etree.SubElement(cat_ax, _qn_c("auto"), val="1")
    etree.SubElement(cat_ax, _qn_c("lblAlgn"), val="ctr")
    etree.SubElement(cat_ax, _qn_c("lblOffset"), val="100")

    # Value axis (Y)
    val_ax = etree.SubElement(plot_area, _qn_c("valAx"))
    etree.SubElement(val_ax, _qn_c("axId"), val="200")
    scaling2 = etree.SubElement(val_ax, _qn_c("scaling"))
    etree.SubElement(scaling2, _qn_c("orientation"), val="minMax")
    etree.SubElement(val_ax, _qn_c("delete"), val="0")
    etree.SubElement(val_ax, _qn_c("axPos"), val="l")
    etree.SubElement(val_ax, _qn_c("majorGridlines"))
    etree.SubElement(val_ax, _qn_c("numFmt"), formatCode="General", sourceLinked="1")
    etree.SubElement(val_ax, _qn_c("majorTickMark"), val="out")
    etree.SubElement(val_ax, _qn_c("minorTickMark"), val="none")
    etree.SubElement(val_ax, _qn_c("tickLblPos"), val="nextTo")
    etree.SubElement(val_ax, _qn_c("crossAx"), val="100")
    etree.SubElement(val_ax, _qn_c("crosses"), val="autoZero")
    etree.SubElement(val_ax, _qn_c("crossBetween"), val="between")


def _next_drawing_object_id(drawing_xml: etree._Element) -> int:
    """Find next available drawing object ID.

    Scans all cNvPr elements in the drawing and returns max(id)+1.
    """
    max_id = 0
    # Find all cNvPr elements (they have id attributes)
    for elem in drawing_xml.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "cNvPr":
            id_str = elem.get("id")
            if id_str:
                with contextlib.suppress(ValueError):
                    max_id = max(max_id, int(id_str))
    return max_id + 1


def _create_anchor(
    col: int,
    row: int,
    chart_rId: str,
    object_id: int,
    chart_name: str,
    width_cols: int = 10,
    height_rows: int = 15,
) -> etree._Element:
    """Create twoCellAnchor element for chart positioning.

    Args:
        col: 0-indexed column for top-left
        row: 0-indexed row for top-left
        chart_rId: Relationship ID to chart part
        object_id: Unique drawing object ID for cNvPr
        chart_name: Name for the chart object
        width_cols: Chart width in columns
        height_rows: Chart height in rows
    """
    anchor = etree.Element(_qn_xdr("twoCellAnchor"))

    # From position (top-left)
    from_elem = etree.SubElement(anchor, _qn_xdr("from"))
    etree.SubElement(from_elem, _qn_xdr("col")).text = str(col)
    etree.SubElement(from_elem, _qn_xdr("colOff")).text = "0"
    etree.SubElement(from_elem, _qn_xdr("row")).text = str(row)
    etree.SubElement(from_elem, _qn_xdr("rowOff")).text = "0"

    # To position (bottom-right)
    to_elem = etree.SubElement(anchor, _qn_xdr("to"))
    etree.SubElement(to_elem, _qn_xdr("col")).text = str(col + width_cols)
    etree.SubElement(to_elem, _qn_xdr("colOff")).text = "0"
    etree.SubElement(to_elem, _qn_xdr("row")).text = str(row + height_rows)
    etree.SubElement(to_elem, _qn_xdr("rowOff")).text = "0"

    # Graphic frame
    graphic_frame = etree.SubElement(anchor, _qn_xdr("graphicFrame"), macro="")

    # Non-visual properties with unique ID
    nv_graphic_frame_pr = etree.SubElement(graphic_frame, _qn_xdr("nvGraphicFramePr"))
    etree.SubElement(
        nv_graphic_frame_pr, _qn_xdr("cNvPr"), id=str(object_id), name=chart_name
    )
    etree.SubElement(nv_graphic_frame_pr, _qn_xdr("cNvGraphicFramePr"))

    # Transform
    xfrm = etree.SubElement(graphic_frame, _qn_xdr("xfrm"))
    etree.SubElement(xfrm, _qn_a("off"), x="0", y="0")
    etree.SubElement(xfrm, _qn_a("ext"), cx="0", cy="0")

    # Graphic
    graphic = etree.SubElement(graphic_frame, _qn_a("graphic"))
    graphic_data = etree.SubElement(
        graphic,
        _qn_a("graphicData"),
        uri="http://schemas.openxmlformats.org/drawingml/2006/chart",
    )
    chart_ref = etree.SubElement(
        graphic_data,
        _qn_c("chart"),
        nsmap={"c": DRAWING_NSMAP["c"], "r": DRAWING_NSMAP["r"]},
    )
    chart_ref.set(_qn_r("id"), chart_rId)

    # Client data
    etree.SubElement(anchor, _qn_xdr("clientData"))

    return anchor


def list_charts(pkg: ExcelPackage, sheet_name: str) -> list[ChartInfo]:
    """List all charts on a sheet.

    Returns list of ChartInfo with id, type, title, data_range, position.
    """
    drawing_path = _get_sheet_drawing_path(pkg, sheet_name)
    if drawing_path is None:
        return []

    drawing_xml = pkg.get_xml(drawing_path)
    charts = []

    # Find all chart references in drawing
    for anchor in drawing_xml.findall(_qn_xdr("twoCellAnchor")):
        graphic_frame = anchor.find(_qn_xdr("graphicFrame"))
        if graphic_frame is None:
            continue

        graphic = graphic_frame.find(_qn_a("graphic"))
        if graphic is None:
            continue

        graphic_data = graphic.find(_qn_a("graphicData"))
        if graphic_data is None:
            continue

        chart_ref = graphic_data.find(_qn_c("chart"))
        if chart_ref is None:
            continue

        chart_rId = chart_ref.get(_qn_r("id"))
        if chart_rId is None:
            continue

        # Resolve chart path
        chart_path = pkg.resolve_rel_target(drawing_path, chart_rId)
        chart_xml = pkg.get_xml(chart_path)

        # Extract chart info
        chart_info = _extract_chart_info(chart_xml, chart_path, anchor)
        charts.append(chart_info)

    return charts


def _extract_chart_info(
    chart_xml: etree._Element, chart_path: str, anchor: etree._Element
) -> ChartInfo:
    """Extract ChartInfo from chart XML and anchor."""
    # Get chart type
    chart = chart_xml.find(_qn_c("chart"))
    plot_area = chart.find(_qn_c("plotArea")) if chart is not None else None

    chart_type = "unknown"
    data_range = ""

    if plot_area is not None:
        # Determine chart type from first chart element
        for child in plot_area:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "barChart":
                bar_dir = child.find(_qn_c("barDir"))
                if bar_dir is not None and bar_dir.get("val") == "bar":
                    chart_type = "bar"
                else:
                    chart_type = "column"
                break
            elif tag == "lineChart":
                chart_type = "line"
                break
            elif tag == "pieChart":
                chart_type = "pie"
                break
            elif tag == "scatterChart":
                chart_type = "scatter"
                break
            elif tag == "areaChart":
                chart_type = "area"
                break

        # Extract data range from first series
        for chart_elem in plot_area:
            ser = chart_elem.find(_qn_c("ser"))
            if ser is not None:
                # Try val first, then yVal for scatter
                val = ser.find(_qn_c("val"))
                if val is None:
                    val = ser.find(_qn_c("yVal"))
                if val is not None:
                    num_ref = val.find(_qn_c("numRef"))
                    if num_ref is not None:
                        f = num_ref.find(_qn_c("f"))
                        if f is not None and f.text:
                            data_range = f.text
                            break

    # Get title
    title = None
    if chart is not None:
        title_elem = chart.find(_qn_c("title"))
        if title_elem is not None:
            tx = title_elem.find(_qn_c("tx"))
            if tx is not None:
                rich = tx.find(_qn_c("rich"))
                if rich is not None:
                    # Collect all text from <a:t> elements
                    texts = []
                    for t in rich.iter(_qn_a("t")):
                        if t.text:
                            texts.append(t.text)
                    if texts:
                        title = "".join(texts)

    # Get position from anchor
    from_elem = anchor.find(_qn_xdr("from"))
    position = ""
    if from_elem is not None:
        col_elem = from_elem.find(_qn_xdr("col"))
        row_elem = from_elem.find(_qn_xdr("row"))
        if col_elem is not None and row_elem is not None:
            col = int(col_elem.text or "0")
            row = int(row_elem.text or "0")
            # Convert to cell reference (1-indexed)
            from mcp_handley_lab.microsoft.excel.ops.core import index_to_column_letter

            position = f"{index_to_column_letter(col + 1)}{row + 1}"

    return ChartInfo(
        id=make_chart_id(chart_path),
        type=chart_type,
        title=title,
        data_range=data_range,
        position=position,
    )


def create_chart(
    pkg: ExcelPackage,
    sheet_name: str,
    chart_type: str,
    data_range: str,
    position: str,
    title: str | None = None,
) -> ChartInfo:
    """Create a chart on the sheet.

    Args:
        pkg: Excel package
        sheet_name: Sheet name to add chart to
        chart_type: bar, column, line, pie, scatter, or area
        data_range: Cell range like "A1:B10" (without sheet name)
        position: Cell reference for top-left corner like "E5"
        title: Optional chart title

    Returns:
        ChartInfo for the created chart
    """
    # Get or create drawing for sheet
    drawing_path, drawing_xml = _get_or_create_drawing(pkg, sheet_name)

    # Create chart part
    chart_num = _find_next_chart_number(pkg)
    chart_path = f"/xl/charts/chart{chart_num}.xml"

    chart_xml = _create_chart_xml(chart_type, data_range, sheet_name, title)
    pkg.set_xml(chart_path, chart_xml, CT_CHART)

    # Create relationship from drawing to chart
    rel_target = f"../charts/chart{chart_num}.xml"
    chart_rId = pkg.relate_to(drawing_path, rel_target, RT_CHART)

    # Parse position and create anchor with unique object ID
    col, row = _parse_position(position)
    object_id = _next_drawing_object_id(drawing_xml)
    chart_name = f"Chart {object_id}"
    anchor = _create_anchor(col, row, chart_rId, object_id, chart_name)
    drawing_xml.append(anchor)
    pkg.mark_xml_dirty(drawing_path)

    return ChartInfo(
        id=make_chart_id(chart_path),
        type=chart_type.lower(),
        title=title,
        data_range=f"'{sheet_name}'!{data_range}",
        position=position,
    )


def delete_chart(pkg: ExcelPackage, sheet_name: str, chart_id: str) -> None:
    """Delete a chart by its ID.

    Args:
        pkg: Excel package
        sheet_name: Sheet containing the chart
        chart_id: Chart ID (from ChartInfo.id)
    """
    drawing_path = _get_sheet_drawing_path(pkg, sheet_name)
    if drawing_path is None:
        raise KeyError(f"No charts on sheet: {sheet_name}")

    drawing_xml = pkg.get_xml(drawing_path)

    # Find and remove the anchor for this chart
    for anchor in list(drawing_xml.findall(_qn_xdr("twoCellAnchor"))):
        graphic_frame = anchor.find(_qn_xdr("graphicFrame"))
        if graphic_frame is None:
            continue

        graphic = graphic_frame.find(_qn_a("graphic"))
        if graphic is None:
            continue

        graphic_data = graphic.find(_qn_a("graphicData"))
        if graphic_data is None:
            continue

        chart_ref = graphic_data.find(_qn_c("chart"))
        if chart_ref is None:
            continue

        chart_rId = chart_ref.get(_qn_r("id"))
        if chart_rId is None:
            continue

        chart_path = pkg.resolve_rel_target(drawing_path, chart_rId)
        if make_chart_id(chart_path) == chart_id:
            # Remove anchor from drawing
            drawing_xml.remove(anchor)
            pkg.mark_xml_dirty(drawing_path)

            # Remove chart part
            pkg.drop_part(chart_path)

            # Remove relationship
            pkg.remove_rel(drawing_path, chart_rId)
            return

    raise KeyError(f"Chart not found: {chart_id}")


def update_chart_data(
    pkg: ExcelPackage, sheet_name: str, chart_id: str, data_range: str
) -> None:
    """Update the data range for a chart.

    Args:
        pkg: Excel package
        sheet_name: Sheet containing the chart
        chart_id: Chart ID (from ChartInfo.id)
        data_range: New data range like "A1:B20" (without sheet name)
    """
    drawing_path = _get_sheet_drawing_path(pkg, sheet_name)
    if drawing_path is None:
        raise KeyError(f"No charts on sheet: {sheet_name}")

    drawing_xml = pkg.get_xml(drawing_path)

    # Find the chart
    for anchor in drawing_xml.findall(_qn_xdr("twoCellAnchor")):
        graphic_frame = anchor.find(_qn_xdr("graphicFrame"))
        if graphic_frame is None:
            continue

        graphic = graphic_frame.find(_qn_a("graphic"))
        if graphic is None:
            continue

        graphic_data = graphic.find(_qn_a("graphicData"))
        if graphic_data is None:
            continue

        chart_ref = graphic_data.find(_qn_c("chart"))
        if chart_ref is None:
            continue

        chart_rId = chart_ref.get(_qn_r("id"))
        if chart_rId is None:
            continue

        chart_path = pkg.resolve_rel_target(drawing_path, chart_rId)
        if make_chart_id(chart_path) == chart_id:
            # Update the chart data range
            chart_xml = pkg.get_xml(chart_path)
            full_range = f"'{sheet_name}'!{data_range}"

            # Find all formula elements in series and update
            for f_elem in chart_xml.iter(_qn_c("f")):
                f_elem.text = full_range

            pkg.mark_xml_dirty(chart_path)
            return

    raise KeyError(f"Chart not found: {chart_id}")
