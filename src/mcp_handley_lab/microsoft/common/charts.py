"""Shared DrawingML chart XML builders for Word, Excel, and PowerPoint.

Generates c:chartSpace XML with proper category/series semantics.
Supports: bar, column, line, pie, scatter, area chart types.
"""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.opc.constants import CT, RT

# Chart-specific namespaces (not tied to any one format)
CHART_NSMAP = {
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

# Re-export from opc/constants for convenience
CT_CHART = CT.CHART
RT_CHART = RT.CHART
RT_PACKAGE = RT.PACKAGE

# Content type for embedded xlsx
CT_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

VALID_CHART_TYPES = {"bar", "column", "line", "pie", "scatter", "area"}


def _qn_c(tag: str) -> str:
    return f"{{{CHART_NSMAP['c']}}}{tag}"


def _qn_a(tag: str) -> str:
    return f"{{{CHART_NSMAP['a']}}}{tag}"


def _qn_r(tag: str) -> str:
    return f"{{{CHART_NSMAP['r']}}}{tag}"


def validate_chart_data(data: list[list]) -> None:
    """Validate a 2D data array for chart creation.

    Raises ValueError if data is invalid.
    """
    if not data:
        raise ValueError("Data array must not be empty")
    if len(data) < 2:
        raise ValueError("Data must have at least 2 rows (header + 1 data row)")
    if len(data[0]) < 2:
        raise ValueError("Data must have at least 2 columns (categories + 1 series)")
    row_len = len(data[0])
    for i, row in enumerate(data):
        if len(row) != row_len:
            raise ValueError(
                f"Row {i} has {len(row)} columns, expected {row_len} (data must be rectangular)"
            )


def compute_chart_refs(
    sheet_name: str, n_rows: int, n_cols: int
) -> tuple[str, list[tuple[str, str, str]]]:
    """Convert 2D array dimensions to categories_range + series list.

    Assumes row 0 = headers (series names), col 0 = categories, cols 1..n = series values.
    For scatter charts: col 0 = X values, cols 1..n = Y series.

    Args:
        sheet_name: Worksheet name
        n_rows: Total rows including header
        n_cols: Total columns including category column

    Returns:
        (categories_range, [(name_ref, name_text, values_range), ...])
        where name_ref is cell reference for series name, name_text is placeholder,
        and values_range is the data column reference.
    """
    # Categories are in col A, rows 2..n_rows (skip header)
    cat_range = f"'{sheet_name}'!$A$2:$A${n_rows}"

    series = []
    for col_idx in range(1, n_cols):
        col_letter = _col_letter(col_idx)
        # Series name is in the header row (row 1)
        name_ref = f"'{sheet_name}'!${col_letter}$1"
        # Values are rows 2..n_rows
        values_range = f"'{sheet_name}'!${col_letter}$2:${col_letter}${n_rows}"
        # name_text is a placeholder; actual text comes from embedded workbook
        series.append((name_ref, "", values_range))

    return cat_range, series


def _col_letter(idx: int) -> str:
    """Convert 0-based column index to Excel column letter (0=A, 1=B, ..., 25=Z, 26=AA)."""
    result = []
    n = idx
    while True:
        result.append(chr(ord("A") + n % 26))
        n = n // 26 - 1
        if n < 0:
            break
    return "".join(reversed(result))


def create_chart_xml(
    chart_type: str,
    sheet_name: str,
    categories_range: str | None,
    series: list[tuple[str, str, str]],
    title: str | None = None,
    external_data_rid: str | None = None,
) -> etree._Element:
    """Create a c:chartSpace XML element.

    Args:
        chart_type: bar, column, line, pie, scatter, area
        sheet_name: Name of the data worksheet
        categories_range: Cell range for categories (e.g. "'Sheet1'!$A$2:$A$4"),
            or None to omit category references (Excel simple mode)
        series: List of (name_ref, name_text, values_range) tuples per series.
            name_ref can be empty string to omit c:serTx.
        title: Optional chart title
        external_data_rid: rId for c:externalData (Word/PPT charts only)

    Returns:
        c:chartSpace lxml element
    """
    chart_type = chart_type.lower()
    if chart_type not in VALID_CHART_TYPES:
        raise ValueError(
            f"Unsupported chart type: {chart_type!r}. "
            f"Must be one of: {', '.join(sorted(VALID_CHART_TYPES))}"
        )
    if not series:
        raise ValueError("At least one data series is required")

    chart_space = etree.Element(
        _qn_c("chartSpace"),
        nsmap={"c": CHART_NSMAP["c"], "a": CHART_NSMAP["a"], "r": CHART_NSMAP["r"]},
    )

    etree.SubElement(chart_space, _qn_c("date1904"), val="0")
    etree.SubElement(chart_space, _qn_c("lang"), val="en-US")
    etree.SubElement(chart_space, _qn_c("roundedCorners"), val="0")

    chart = etree.SubElement(chart_space, _qn_c("chart"))

    if title:
        _add_title(chart, title)

    etree.SubElement(chart, _qn_c("autoTitleDeleted"), val="0" if title else "1")

    plot_area = etree.SubElement(chart, _qn_c("plotArea"))
    etree.SubElement(plot_area, _qn_c("layout"))

    if chart_type == "bar":
        _add_bar_chart(plot_area, categories_range, series, bar_dir="bar")
    elif chart_type == "column":
        _add_bar_chart(plot_area, categories_range, series, bar_dir="col")
    elif chart_type == "line":
        _add_line_chart(plot_area, categories_range, series)
    elif chart_type == "pie":
        _add_pie_chart(plot_area, categories_range, series)
    elif chart_type == "scatter":
        _add_scatter_chart(plot_area, categories_range, series)
    elif chart_type == "area":
        _add_area_chart(plot_area, categories_range, series)

    if chart_type != "pie":
        _add_axes(plot_area, chart_type)

    legend = etree.SubElement(chart, _qn_c("legend"))
    etree.SubElement(legend, _qn_c("legendPos"), val="r")
    etree.SubElement(legend, _qn_c("overlay"), val="0")

    etree.SubElement(chart, _qn_c("plotVisOnly"), val="1")
    etree.SubElement(chart, _qn_c("dispBlanksAs"), val="gap")
    etree.SubElement(chart, _qn_c("showDLblsOverMax"), val="0")

    # External data reference (for Word/PowerPoint embedded charts)
    if external_data_rid:
        ext_data = etree.SubElement(chart_space, _qn_c("externalData"))
        ext_data.set(_qn_r("id"), external_data_rid)
        etree.SubElement(ext_data, _qn_c("autoUpdate"), val="0")

    # Print settings
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


def _add_title(chart: etree._Element, title: str) -> None:
    """Add chart title element."""
    title_elem = etree.SubElement(chart, _qn_c("title"))
    tx = etree.SubElement(title_elem, _qn_c("tx"))
    rich = etree.SubElement(tx, _qn_c("rich"))
    etree.SubElement(rich, _qn_a("bodyPr"))
    etree.SubElement(rich, _qn_a("lstStyle"))
    p = etree.SubElement(rich, _qn_a("p"))
    p_pr = etree.SubElement(p, _qn_a("pPr"))
    etree.SubElement(p_pr, _qn_a("defRPr"))
    r = etree.SubElement(p, _qn_a("r"))
    etree.SubElement(r, _qn_a("rPr"), lang="en-US")
    t = etree.SubElement(r, _qn_a("t"))
    t.text = title
    etree.SubElement(title_elem, _qn_c("overlay"), val="0")


def _add_series_common(
    parent: etree._Element,
    idx: int,
    name_ref: str,
    name_text: str,
) -> etree._Element:
    """Add common series elements (idx, order, serTx). Returns the c:ser element."""
    ser = etree.SubElement(parent, _qn_c("ser"))
    etree.SubElement(ser, _qn_c("idx"), val=str(idx))
    etree.SubElement(ser, _qn_c("order"), val=str(idx))

    # Series name reference
    if name_ref:
        ser_tx = etree.SubElement(ser, _qn_c("tx"))
        str_ref = etree.SubElement(ser_tx, _qn_c("strRef"))
        f = etree.SubElement(str_ref, _qn_c("f"))
        f.text = name_ref

    return ser


def _add_cat_ref(ser: etree._Element, categories_range: str | None) -> None:
    """Add c:cat element with strRef to a series. No-op if categories_range is None."""
    if categories_range is None:
        return
    cat = etree.SubElement(ser, _qn_c("cat"))
    str_ref = etree.SubElement(cat, _qn_c("strRef"))
    f = etree.SubElement(str_ref, _qn_c("f"))
    f.text = categories_range


def _add_val_ref(ser: etree._Element, values_range: str) -> None:
    """Add c:val element with numRef to a series."""
    val = etree.SubElement(ser, _qn_c("val"))
    num_ref = etree.SubElement(val, _qn_c("numRef"))
    f = etree.SubElement(num_ref, _qn_c("f"))
    f.text = values_range


def _add_data_labels(parent: etree._Element) -> None:
    """Add standard data labels (all hidden)."""
    d_lbls = etree.SubElement(parent, _qn_c("dLbls"))
    for attr in (
        "showLegendKey",
        "showVal",
        "showCatName",
        "showSerName",
        "showPercent",
        "showBubbleSize",
    ):
        etree.SubElement(d_lbls, _qn_c(attr), val="0")


def _add_bar_chart(
    plot_area: etree._Element,
    categories_range: str | None,
    series: list[tuple[str, str, str]],
    bar_dir: str = "col",
) -> None:
    """Add bar/column chart with categories and multiple series."""
    bar_chart = etree.SubElement(plot_area, _qn_c("barChart"))
    etree.SubElement(bar_chart, _qn_c("barDir"), val=bar_dir)
    etree.SubElement(bar_chart, _qn_c("grouping"), val="clustered")
    etree.SubElement(bar_chart, _qn_c("varyColors"), val="0")

    for idx, (name_ref, name_text, values_range) in enumerate(series):
        ser = _add_series_common(bar_chart, idx, name_ref, name_text)
        _add_cat_ref(ser, categories_range)
        _add_val_ref(ser, values_range)

    _add_data_labels(bar_chart)
    etree.SubElement(bar_chart, _qn_c("gapWidth"), val="150")
    etree.SubElement(bar_chart, _qn_c("axId"), val="100")
    etree.SubElement(bar_chart, _qn_c("axId"), val="200")


def _add_line_chart(
    plot_area: etree._Element,
    categories_range: str | None,
    series: list[tuple[str, str, str]],
) -> None:
    """Add line chart with categories and multiple series."""
    line_chart = etree.SubElement(plot_area, _qn_c("lineChart"))
    etree.SubElement(line_chart, _qn_c("grouping"), val="standard")
    etree.SubElement(line_chart, _qn_c("varyColors"), val="0")

    for idx, (name_ref, name_text, values_range) in enumerate(series):
        ser = _add_series_common(line_chart, idx, name_ref, name_text)
        marker = etree.SubElement(ser, _qn_c("marker"))
        etree.SubElement(marker, _qn_c("symbol"), val="none")
        _add_cat_ref(ser, categories_range)
        _add_val_ref(ser, values_range)

    _add_data_labels(line_chart)
    etree.SubElement(line_chart, _qn_c("smooth"), val="0")
    etree.SubElement(line_chart, _qn_c("axId"), val="100")
    etree.SubElement(line_chart, _qn_c("axId"), val="200")


def _add_pie_chart(
    plot_area: etree._Element,
    categories_range: str | None,
    series: list[tuple[str, str, str]],
) -> None:
    """Add pie chart with categories and single value series."""
    pie_chart = etree.SubElement(plot_area, _qn_c("pieChart"))
    etree.SubElement(pie_chart, _qn_c("varyColors"), val="1")

    # Pie charts use only the first series
    if series:
        name_ref, name_text, values_range = series[0]
        ser = _add_series_common(pie_chart, 0, name_ref, name_text)
        _add_cat_ref(ser, categories_range)
        _add_val_ref(ser, values_range)

    _add_data_labels(pie_chart)
    etree.SubElement(pie_chart, _qn_c("firstSliceAng"), val="0")


def _add_scatter_chart(
    plot_area: etree._Element,
    categories_range: str | None,
    series: list[tuple[str, str, str]],
) -> None:
    """Add scatter chart with xVal/yVal per series.

    When categories_range is None (Excel simple mode), only yVal is emitted.
    """
    scatter_chart = etree.SubElement(plot_area, _qn_c("scatterChart"))
    etree.SubElement(scatter_chart, _qn_c("scatterStyle"), val="lineMarker")
    etree.SubElement(scatter_chart, _qn_c("varyColors"), val="0")

    for idx, (name_ref, name_text, values_range) in enumerate(series):
        ser = _add_series_common(scatter_chart, idx, name_ref, name_text)

        marker = etree.SubElement(ser, _qn_c("marker"))
        etree.SubElement(marker, _qn_c("symbol"), val="circle")
        etree.SubElement(marker, _qn_c("size"), val="5")

        # X values from categories column (omitted in Excel simple mode)
        if categories_range is not None:
            x_val = etree.SubElement(ser, _qn_c("xVal"))
            num_ref_x = etree.SubElement(x_val, _qn_c("numRef"))
            f_x = etree.SubElement(num_ref_x, _qn_c("f"))
            f_x.text = categories_range

        # Y values from series column
        y_val = etree.SubElement(ser, _qn_c("yVal"))
        num_ref_y = etree.SubElement(y_val, _qn_c("numRef"))
        f_y = etree.SubElement(num_ref_y, _qn_c("f"))
        f_y.text = values_range

        etree.SubElement(ser, _qn_c("smooth"), val="0")

    _add_data_labels(scatter_chart)
    etree.SubElement(scatter_chart, _qn_c("axId"), val="100")
    etree.SubElement(scatter_chart, _qn_c("axId"), val="200")


def _add_area_chart(
    plot_area: etree._Element,
    categories_range: str | None,
    series: list[tuple[str, str, str]],
) -> None:
    """Add area chart with categories and multiple series."""
    area_chart = etree.SubElement(plot_area, _qn_c("areaChart"))
    etree.SubElement(area_chart, _qn_c("grouping"), val="standard")
    etree.SubElement(area_chart, _qn_c("varyColors"), val="0")

    for idx, (name_ref, name_text, values_range) in enumerate(series):
        ser = _add_series_common(area_chart, idx, name_ref, name_text)
        _add_cat_ref(ser, categories_range)
        _add_val_ref(ser, values_range)

    _add_data_labels(area_chart)
    etree.SubElement(area_chart, _qn_c("axId"), val="100")
    etree.SubElement(area_chart, _qn_c("axId"), val="200")


def _add_axes(plot_area: etree._Element, chart_type: str) -> None:
    """Add axes to plot area. Scatter uses two valAx; others use catAx + valAx."""
    if chart_type == "scatter":
        _add_scatter_axes(plot_area)
    else:
        _add_category_axes(plot_area)


def _add_category_axes(plot_area: etree._Element) -> None:
    """Add catAx (X) + valAx (Y) for non-scatter charts."""
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

    _add_val_ax(plot_area, ax_id="200", cross_ax="100", position="l")


def _add_scatter_axes(plot_area: etree._Element) -> None:
    """Add two valAx (X + Y) for scatter charts. No catAx-specific properties."""
    _add_val_ax(plot_area, ax_id="100", cross_ax="200", position="b")
    _add_val_ax(plot_area, ax_id="200", cross_ax="100", position="l")


def _add_val_ax(
    plot_area: etree._Element,
    ax_id: str,
    cross_ax: str,
    position: str,
) -> None:
    """Add a single c:valAx element."""
    val_ax = etree.SubElement(plot_area, _qn_c("valAx"))
    etree.SubElement(val_ax, _qn_c("axId"), val=ax_id)
    scaling = etree.SubElement(val_ax, _qn_c("scaling"))
    etree.SubElement(scaling, _qn_c("orientation"), val="minMax")
    etree.SubElement(val_ax, _qn_c("delete"), val="0")
    etree.SubElement(val_ax, _qn_c("axPos"), val=position)
    if position == "l":
        etree.SubElement(val_ax, _qn_c("majorGridlines"))
    etree.SubElement(val_ax, _qn_c("numFmt"), formatCode="General", sourceLinked="1")
    etree.SubElement(val_ax, _qn_c("majorTickMark"), val="out")
    etree.SubElement(val_ax, _qn_c("minorTickMark"), val="none")
    etree.SubElement(val_ax, _qn_c("tickLblPos"), val="nextTo")
    etree.SubElement(val_ax, _qn_c("crossAx"), val=cross_ax)
    etree.SubElement(val_ax, _qn_c("crosses"), val="autoZero")
    etree.SubElement(val_ax, _qn_c("crossBetween"), val="between")
