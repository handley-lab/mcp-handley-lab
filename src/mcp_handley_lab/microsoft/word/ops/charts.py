"""Chart operations for Word documents.

Inserts DrawingML charts with embedded Excel workbooks as data sources.
Charts are placed inline using wp:inline within w:drawing elements.
"""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.common.charts import (
    CHART_NSMAP,
    CT_CHART,
    CT_XLSX,
    RT_CHART,
    RT_PACKAGE,
    _qn_c,
    _qn_r,
    compute_chart_refs,
    create_chart_xml,
    validate_chart_data,
)
from mcp_handley_lab.microsoft.common.embedding import create_embedded_excel
from mcp_handley_lab.microsoft.word.constants import NSMAP, qn
from mcp_handley_lab.microsoft.word.models import ChartInfo
from mcp_handley_lab.microsoft.word.ops.core import (
    mark_dirty,
    resolve_target,
)
from mcp_handley_lab.microsoft.word.package import WordPackage

_EMU_PER_INCH = 914400


def _next_chart_number(pkg: WordPackage) -> int:
    """Find next available chart number."""
    max_num = 0
    for partname in pkg.iter_partnames():
        if partname.startswith("/word/charts/chart") and partname.endswith(".xml"):
            try:
                num = int(partname[len("/word/charts/chart") : -4])
                max_num = max(max_num, num)
            except ValueError:
                pass
    return max_num + 1


def _next_embed_number(pkg: WordPackage) -> int:
    """Find next available embedding number."""
    max_num = 0
    for partname in pkg.iter_partnames():
        if partname.startswith(
            "/word/embeddings/Microsoft_Excel_Worksheet"
        ) and partname.endswith(".xlsx"):
            try:
                num = int(
                    partname[len("/word/embeddings/Microsoft_Excel_Worksheet") : -5]
                )
                max_num = max(max_num, num)
            except ValueError:
                pass
    return max_num + 1


def _next_docPr_id(pkg: WordPackage) -> int:
    """Find next available docPr id by scanning the document."""
    doc = pkg.document_xml
    max_id = 0
    for elem in doc.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "docPr":
            try:
                max_id = max(max_id, int(elem.get("id", "0")))
            except ValueError:
                pass
    return max_id + 1


def _embedding_referenced_elsewhere(
    pkg: WordPackage, excluding_chart: str, embed_path: str
) -> bool:
    """Check if an embedding is referenced by any chart other than the given one."""
    for partname in pkg.iter_partnames():
        if not partname.startswith("/word/charts/chart") or partname == excluding_chart:
            continue
        rels = pkg.get_rels(partname)
        for _rid, rel in rels.items():
            if rel.reltype == RT_PACKAGE:
                resolved = pkg.resolve_rel_target(partname, _rid)
                if resolved == embed_path:
                    return True
    return False


def create_chart(
    pkg: WordPackage,
    target_id: str,
    chart_type: str,
    data: list[list],
    title: str | None = None,
    width_inches: float = 5.0,
    height_inches: float = 3.0,
) -> str:
    """Insert a chart after the target paragraph.

    Args:
        pkg: Word package
        target_id: Block ID of paragraph to insert after
        chart_type: bar, column, line, pie, scatter, area
        data: 2D list, e.g. [["Category", "S1", "S2"], ["A", 10, 30], ["B", 20, 40]]
        title: Optional chart title
        width_inches: Chart width in inches
        height_inches: Chart height in inches

    Returns:
        chart_id string (chart_N)
    """
    validate_chart_data(data)

    # 1. Resolve target paragraph
    target = resolve_target(pkg, target_id)

    # 2. Create embedded Excel workbook
    xlsx_bytes, sheet_name, n_rows, n_cols = create_embedded_excel(data)

    # 3. Store embedding
    embed_num = _next_embed_number(pkg)
    embed_partname = f"/word/embeddings/Microsoft_Excel_Worksheet{embed_num}.xlsx"
    pkg.set_bytes(embed_partname, xlsx_bytes, CT_XLSX)

    # 4. Create chart part
    chart_num = _next_chart_number(pkg)
    chart_partname = f"/word/charts/chart{chart_num}.xml"

    # 5. Wire chart → embedding relationship first (need rId for chart XML)
    embed_rel_target = f"../embeddings/Microsoft_Excel_Worksheet{embed_num}.xlsx"
    embed_rid = pkg.relate_to(chart_partname, embed_rel_target, RT_PACKAGE)

    # 6. Compute data references and create chart XML
    cat_range, series_list = compute_chart_refs(sheet_name, n_rows, n_cols)
    chart_xml = create_chart_xml(
        chart_type,
        sheet_name,
        cat_range,
        series_list,
        title=title,
        external_data_rid=embed_rid,
    )
    pkg.set_xml(chart_partname, chart_xml, CT_CHART)

    # 7. Wire document → chart relationship
    chart_rel_target = f"charts/chart{chart_num}.xml"
    chart_rid = pkg.relate_to("/word/document.xml", chart_rel_target, RT_CHART)

    # 8. Create drawing element
    cx = int(width_inches * _EMU_PER_INCH)
    cy = int(height_inches * _EMU_PER_INCH)
    doc_pr_id = _next_docPr_id(pkg)

    drawing = _create_inline_chart_drawing(chart_rid, cx, cy, doc_pr_id, chart_num)

    # 9. Insert drawing into a new paragraph after target
    new_p = etree.Element(qn("w:p"))
    r = etree.SubElement(new_p, qn("w:r"))
    r.append(drawing)

    target_el = target.leaf_el
    parent = target_el.getparent()
    idx = list(parent).index(target_el)
    parent.insert(idx + 1, new_p)

    mark_dirty(pkg)

    return f"chart_{chart_num}"


def _create_inline_chart_drawing(
    chart_rid: str, cx: int, cy: int, doc_pr_id: int, chart_num: int
) -> etree._Element:
    """Create w:drawing element with wp:inline containing chart reference."""
    drawing = etree.Element(qn("w:drawing"))

    inline = etree.SubElement(
        drawing,
        qn("wp:inline"),
        distT="0",
        distB="0",
        distL="0",
        distR="0",
    )

    etree.SubElement(inline, qn("wp:extent"), cx=str(cx), cy=str(cy))
    etree.SubElement(inline, qn("wp:effectExtent"), l="0", t="0", r="0", b="0")
    etree.SubElement(
        inline,
        qn("wp:docPr"),
        id=str(doc_pr_id),
        name=f"Chart {chart_num}",
    )
    etree.SubElement(inline, qn("wp:cNvGraphicFramePr"))

    graphic = etree.SubElement(
        inline,
        qn("a:graphic"),
        nsmap={"a": NSMAP["a"]},
    )
    graphic_data = etree.SubElement(
        graphic,
        qn("a:graphicData"),
        uri="http://schemas.openxmlformats.org/drawingml/2006/chart",
    )
    chart_ref = etree.SubElement(
        graphic_data,
        _qn_c("chart"),
        nsmap={"c": CHART_NSMAP["c"], "r": CHART_NSMAP["r"]},
    )
    chart_ref.set(_qn_r("id"), chart_rid)

    return drawing


def list_charts(pkg: WordPackage) -> list[ChartInfo]:
    """List all charts in the document."""
    doc = pkg.document_xml
    charts = []

    for drawing in doc.iter(qn("w:drawing")):
        chart_ref = drawing.find(
            ".//a:graphicData/c:chart",
            {
                "a": NSMAP["a"],
                "c": NSMAP["c"],
            },
        )
        if chart_ref is None:
            continue

        chart_rid = chart_ref.get(_qn_r("id"))
        if not chart_rid:
            continue

        chart_path = pkg.resolve_rel_target("/word/document.xml", chart_rid)
        chart_xml = pkg.get_xml(chart_path)

        chart_info = _extract_chart_info(chart_xml, chart_path)
        charts.append(chart_info)

    return charts


def _extract_chart_info(chart_xml: etree._Element, chart_path: str) -> ChartInfo:
    """Extract ChartInfo from chart XML."""
    chart = chart_xml.find(_qn_c("chart"))
    plot_area = chart.find(_qn_c("plotArea")) if chart is not None else None

    chart_type = "unknown"
    if plot_area is not None:
        for child in plot_area:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "barChart":
                bar_dir = child.find(_qn_c("barDir"))
                chart_type = (
                    "bar"
                    if bar_dir is not None and bar_dir.get("val") == "bar"
                    else "column"
                )
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

    # Extract title
    title_text = None
    if chart is not None:
        title_elem = chart.find(_qn_c("title"))
        if title_elem is not None:
            tx = title_elem.find(_qn_c("tx"))
            if tx is not None:
                rich = tx.find(_qn_c("rich"))
                if rich is not None:
                    from mcp_handley_lab.microsoft.common.charts import _qn_a

                    texts = [t.text for t in rich.iter(_qn_a("t")) if t.text]
                    if texts:
                        title_text = "".join(texts)

    # Extract chart_id from path: /word/charts/chart1.xml -> chart_1
    import re

    m = re.search(r"chart(\d+)\.xml$", chart_path)
    chart_id = f"chart_{m.group(1)}" if m else chart_path

    return ChartInfo(
        id=chart_id,
        type=chart_type,
        title=title_text,
    )


def delete_chart(pkg: WordPackage, chart_id: str) -> None:
    """Delete a chart by its ID (e.g. 'chart_1').

    Removes the drawing paragraph, document→chart relationship,
    chart part, chart→embedding relationship, and embedded xlsx.
    """
    chart_num = chart_id.split("_")[-1]
    chart_partname = f"/word/charts/chart{chart_num}.xml"

    if not pkg.has_part(chart_partname):
        raise KeyError(f"Chart not found: {chart_id}")

    # Find and remove the drawing paragraph containing this chart
    doc = pkg.document_xml
    chart_rels = pkg.get_rels("/word/document.xml")
    target_rid = None

    for rid, rel in chart_rels.items():
        resolved = pkg.resolve_rel_target("/word/document.xml", rid)
        if resolved == chart_partname:
            target_rid = rid
            break

    if target_rid:
        # Find drawing referencing this rId
        for drawing in doc.iter(qn("w:drawing")):
            chart_ref = drawing.find(
                ".//a:graphicData/c:chart",
                {"a": NSMAP["a"], "c": NSMAP["c"]},
            )
            if chart_ref is not None and chart_ref.get(_qn_r("id")) == target_rid:
                # Remove the paragraph containing this drawing
                p = drawing.getparent()
                while p is not None and p.tag != qn("w:p"):
                    p = p.getparent()
                if p is not None and p.getparent() is not None:
                    p.getparent().remove(p)
                break

        # Remove document → chart relationship
        pkg.remove_rel("/word/document.xml", target_rid)

    # Remove chart → embedding relationship and embedded xlsx (if unreferenced)
    chart_rels_obj = pkg.get_rels(chart_partname)
    for rid, rel in chart_rels_obj.items():
        if rel.reltype == RT_PACKAGE:
            embed_path = pkg.resolve_rel_target(chart_partname, rid)
            if not _embedding_referenced_elsewhere(pkg, chart_partname, embed_path):
                pkg.drop_part(embed_path)
            break

    # Remove chart part
    pkg.drop_part(chart_partname)
    mark_dirty(pkg)


def update_chart_data(
    pkg: WordPackage,
    chart_id: str,
    data: list[list],
) -> None:
    """Update chart data by replacing the embedded workbook and chart references.

    Args:
        pkg: Word package
        chart_id: Chart ID (e.g. 'chart_1')
        data: New 2D data array
    """
    validate_chart_data(data)

    chart_num = chart_id.split("_")[-1]
    chart_partname = f"/word/charts/chart{chart_num}.xml"

    if not pkg.has_part(chart_partname):
        raise KeyError(f"Chart not found: {chart_id}")

    # Create new embedded workbook
    xlsx_bytes, sheet_name, n_rows, n_cols = create_embedded_excel(data)

    # Find and replace the embedded xlsx
    chart_rels = pkg.get_rels(chart_partname)
    embed_rid = None
    for rid, rel in chart_rels.items():
        if rel.reltype == RT_PACKAGE:
            embed_path = pkg.resolve_rel_target(chart_partname, rid)
            pkg.set_bytes(embed_path, xlsx_bytes, CT_XLSX)
            embed_rid = rid
            break

    if embed_rid is None:
        raise ValueError(f"No embedded workbook found for {chart_id}")

    # Get existing chart XML to determine type
    old_chart = pkg.get_xml(chart_partname)
    old_plot = old_chart.find(_qn_c("chart"))
    chart_type = "column"
    if old_plot is not None:
        pa = old_plot.find(_qn_c("plotArea"))
        if pa is not None:
            for child in pa:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "barChart":
                    bar_dir = child.find(_qn_c("barDir"))
                    chart_type = (
                        "bar"
                        if bar_dir is not None and bar_dir.get("val") == "bar"
                        else "column"
                    )
                    break
                elif tag in ("lineChart", "pieChart", "scatterChart", "areaChart"):
                    chart_type = tag.replace("Chart", "")
                    break

    # Extract title from old chart
    title = None
    if old_plot is not None:
        title_elem = old_plot.find(_qn_c("title"))
        if title_elem is not None:
            tx = title_elem.find(_qn_c("tx"))
            if tx is not None:
                rich = tx.find(_qn_c("rich"))
                if rich is not None:
                    from mcp_handley_lab.microsoft.common.charts import _qn_a

                    texts = [t.text for t in rich.iter(_qn_a("t")) if t.text]
                    if texts:
                        title = "".join(texts)

    # Regenerate chart XML with new references
    cat_range, series_list = compute_chart_refs(sheet_name, n_rows, n_cols)
    new_chart = create_chart_xml(
        chart_type,
        sheet_name,
        cat_range,
        series_list,
        title=title,
        external_data_rid=embed_rid,
    )
    pkg.set_xml(chart_partname, new_chart, CT_CHART)
