"""Chart operations for PowerPoint presentations.

Inserts DrawingML charts with embedded Excel workbooks as data sources.
Charts are placed as p:graphicFrame elements on slides.
"""

from __future__ import annotations

import re

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
from mcp_handley_lab.microsoft.powerpoint.constants import NSMAP, qn
from mcp_handley_lab.microsoft.powerpoint.models import ChartInfo
from mcp_handley_lab.microsoft.powerpoint.ops.core import (
    inches_to_emu,
    make_shape_key,
    parse_shape_key,
)
from mcp_handley_lab.microsoft.powerpoint.package import PowerPointPackage


def _embedding_referenced_elsewhere(
    pkg: PowerPointPackage, excluding_chart: str, embed_path: str
) -> bool:
    """Check if an embedding is referenced by any chart other than the given one."""
    for partname in pkg.iter_partnames():
        if not partname.startswith("/ppt/charts/chart") or partname == excluding_chart:
            continue
        rels = pkg.get_rels(partname)
        for _rid, rel in rels.items():
            if rel.reltype == RT_PACKAGE:
                resolved = pkg.resolve_rel_target(partname, _rid)
                if resolved == embed_path:
                    return True
    return False


def create_chart(
    pkg: PowerPointPackage,
    slide_num: int,
    chart_type: str,
    data: list[list],
    x: float = 1.0,
    y: float = 1.5,
    width: float = 8.0,
    height: float = 5.0,
    title: str | None = None,
) -> str:
    """Add a chart to a slide.

    Args:
        pkg: PowerPoint package
        slide_num: Target slide number (1-based)
        chart_type: bar, column, line, pie, scatter, area
        data: 2D list, e.g. [["Category", "S1", "S2"], ["A", 10, 30], ["B", 20, 40]]
        x: X position in inches
        y: Y position in inches
        width: Chart width in inches
        height: Chart height in inches
        title: Optional chart title

    Returns:
        Shape key (slide_num:shape_id)
    """
    validate_chart_data(data)

    slide_partname = pkg.get_slide_partname(slide_num)
    slide_xml = pkg.get_slide_xml(slide_num)
    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        raise ValueError(f"Slide {slide_num} has no spTree")

    # 1. Create embedded Excel workbook
    xlsx_bytes, sheet_name, n_rows, n_cols = create_embedded_excel(data)

    # 2. Store embedding
    embed_partname = pkg.next_partname(
        "/ppt/embeddings/Microsoft_Excel_Worksheet", ".xlsx"
    )
    pkg.set_bytes(embed_partname, xlsx_bytes, CT_XLSX)

    # 3. Create chart part
    chart_partname = pkg.next_partname("/ppt/charts/chart", ".xml")

    # 4. Wire chart → embedding relationship (need rId for chart XML)
    # Relative target from /ppt/charts/ to /ppt/embeddings/
    embed_basename = embed_partname.split("/")[-1]
    embed_rid = pkg.relate_to(
        chart_partname, f"../embeddings/{embed_basename}", RT_PACKAGE
    )

    # 5. Compute data references and create chart XML
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

    # 6. Wire slide → chart relationship
    chart_basename = chart_partname.split("/")[-1]
    chart_rid = pkg.relate_to(slide_partname, f"../charts/{chart_basename}", RT_CHART)

    # 7. Get next shape ID
    max_id = 0
    for cNvPr in sp_tree.findall(".//" + qn("p:cNvPr"), NSMAP):
        id_str = cNvPr.get("id", "0")
        if id_str.isdigit():
            max_id = max(max_id, int(id_str))
    shape_id = max_id + 1

    # Extract chart number from partname
    m = re.search(r"chart(\d+)\.xml$", chart_partname)
    chart_num = m.group(1) if m else str(shape_id)

    # 8. Create graphicFrame
    graphic_frame = _create_chart_graphic_frame(
        shape_id,
        chart_rid,
        chart_num,
        x,
        y,
        width,
        height,
    )
    sp_tree.append(graphic_frame)

    pkg.mark_xml_dirty(slide_partname)
    return make_shape_key(slide_num, shape_id)


def _create_chart_graphic_frame(
    shape_id: int,
    chart_rid: str,
    chart_num: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> etree._Element:
    """Create p:graphicFrame element for a chart."""
    gf = etree.Element(qn("p:graphicFrame"))

    # Non-visual properties
    nvGfPr = etree.SubElement(gf, qn("p:nvGraphicFramePr"))
    etree.SubElement(
        nvGfPr,
        qn("p:cNvPr"),
        id=str(shape_id),
        name=f"Chart {chart_num}",
    )
    cNvGfPr = etree.SubElement(nvGfPr, qn("p:cNvGraphicFramePr"))
    etree.SubElement(cNvGfPr, qn("a:graphicFrameLocks"), noGrp="1")
    etree.SubElement(nvGfPr, qn("p:nvPr"))

    # Transform
    xfrm = etree.SubElement(gf, qn("p:xfrm"))
    etree.SubElement(
        xfrm, qn("a:off"), x=str(inches_to_emu(x)), y=str(inches_to_emu(y))
    )
    etree.SubElement(
        xfrm, qn("a:ext"), cx=str(inches_to_emu(width)), cy=str(inches_to_emu(height))
    )

    # Graphic with chart reference
    graphic = etree.SubElement(gf, qn("a:graphic"))
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

    return gf


def list_charts(pkg: PowerPointPackage, slide_num: int) -> list[ChartInfo]:
    """List all charts on a slide."""
    slide_xml = pkg.get_slide_xml(slide_num)
    slide_partname = pkg.get_slide_partname(slide_num)
    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        return []

    charts = []
    for gf in sp_tree.findall(qn("p:graphicFrame"), NSMAP):
        chart_ref = gf.find(
            ".//a:graphicData/c:chart",
            {"a": NSMAP["a"], "c": NSMAP["c"]},
        )
        if chart_ref is None:
            continue

        chart_rid = chart_ref.get(_qn_r("id"))
        if not chart_rid:
            continue

        chart_path = pkg.resolve_rel_target(slide_partname, chart_rid)
        chart_xml = pkg.get_xml(chart_path)

        # Get shape ID for the shape_key
        nvGfPr = gf.find(qn("p:nvGraphicFramePr"), NSMAP)
        cNvPr = nvGfPr.find(qn("p:cNvPr"), NSMAP) if nvGfPr is not None else None
        shape_id = int(cNvPr.get("id", "0")) if cNvPr is not None else 0

        info = _extract_chart_info(chart_xml, chart_path, slide_num, shape_id)
        charts.append(info)

    return charts


def _extract_chart_info(
    chart_xml: etree._Element,
    chart_path: str,
    slide_num: int,
    shape_id: int,
) -> ChartInfo:
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

    return ChartInfo(
        shape_key=make_shape_key(slide_num, shape_id),
        type=chart_type,
        title=title_text,
    )


def delete_chart(pkg: PowerPointPackage, slide_num: int, shape_key: str) -> None:
    """Delete a chart from a slide.

    Removes the graphicFrame, slide→chart relationship,
    chart part, chart→embedding relationship, and embedded xlsx.
    """
    target_slide, target_shape_id = parse_shape_key(shape_key)
    if target_slide != slide_num:
        raise ValueError(f"Shape key {shape_key} is not on slide {slide_num}")

    slide_partname = pkg.get_slide_partname(slide_num)
    slide_xml = pkg.get_slide_xml(slide_num)
    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        raise ValueError(f"Slide {slide_num} has no spTree")

    for gf in list(sp_tree.findall(qn("p:graphicFrame"), NSMAP)):
        nvGfPr = gf.find(qn("p:nvGraphicFramePr"), NSMAP)
        cNvPr = nvGfPr.find(qn("p:cNvPr"), NSMAP) if nvGfPr is not None else None
        if cNvPr is None:
            continue
        sid = int(cNvPr.get("id", "0"))
        if sid != target_shape_id:
            continue

        chart_ref = gf.find(
            ".//a:graphicData/c:chart",
            {"a": NSMAP["a"], "c": NSMAP["c"]},
        )
        if chart_ref is None:
            raise ValueError(f"Shape {shape_key} is not a chart")

        chart_rid = chart_ref.get(_qn_r("id"))
        if chart_rid:
            chart_path = pkg.resolve_rel_target(slide_partname, chart_rid)

            # Remove chart → embedding (only if unreferenced by other charts)
            chart_rels = pkg.get_rels(chart_path)
            for rid, rel in chart_rels.items():
                if rel.reltype == RT_PACKAGE:
                    embed_path = pkg.resolve_rel_target(chart_path, rid)
                    if not _embedding_referenced_elsewhere(pkg, chart_path, embed_path):
                        pkg.drop_part(embed_path)
                    break

            # Remove chart part and slide→chart relationship
            pkg.drop_part(chart_path)
            pkg.remove_rel(slide_partname, chart_rid)

        # Remove graphicFrame from spTree
        sp_tree.remove(gf)
        pkg.mark_xml_dirty(slide_partname)
        return

    raise KeyError(f"Chart not found: {shape_key}")


def update_chart_data(
    pkg: PowerPointPackage,
    slide_num: int,
    shape_key: str,
    data: list[list],
) -> None:
    """Update chart data by replacing the embedded workbook and chart references.

    Args:
        pkg: PowerPoint package
        slide_num: Slide number
        shape_key: Shape key of the chart
        data: New 2D data array
    """
    validate_chart_data(data)

    target_slide, target_shape_id = parse_shape_key(shape_key)
    if target_slide != slide_num:
        raise ValueError(f"Shape key {shape_key} is not on slide {slide_num}")

    slide_partname = pkg.get_slide_partname(slide_num)
    slide_xml = pkg.get_slide_xml(slide_num)
    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        raise ValueError(f"Slide {slide_num} has no spTree")

    for gf in sp_tree.findall(qn("p:graphicFrame"), NSMAP):
        nvGfPr = gf.find(qn("p:nvGraphicFramePr"), NSMAP)
        cNvPr = nvGfPr.find(qn("p:cNvPr"), NSMAP) if nvGfPr is not None else None
        if cNvPr is None:
            continue
        sid = int(cNvPr.get("id", "0"))
        if sid != target_shape_id:
            continue

        chart_ref = gf.find(
            ".//a:graphicData/c:chart",
            {"a": NSMAP["a"], "c": NSMAP["c"]},
        )
        if chart_ref is None:
            raise ValueError(f"Shape {shape_key} is not a chart")

        chart_rid = chart_ref.get(_qn_r("id"))
        if not chart_rid:
            raise ValueError("Chart reference has no rId")

        chart_path = pkg.resolve_rel_target(slide_partname, chart_rid)

        # Create new embedded workbook
        xlsx_bytes, sheet_name, n_rows, n_cols = create_embedded_excel(data)

        # Find and replace the embedded xlsx
        chart_rels = pkg.get_rels(chart_path)
        embed_rid = None
        for rid, rel in chart_rels.items():
            if rel.reltype == RT_PACKAGE:
                embed_path = pkg.resolve_rel_target(chart_path, rid)
                pkg.set_bytes(embed_path, xlsx_bytes, CT_XLSX)
                embed_rid = rid
                break

        if embed_rid is None:
            raise ValueError(f"No embedded workbook found for {shape_key}")

        # Get chart type and title from existing chart
        old_chart = pkg.get_xml(chart_path)
        old_chart_elem = old_chart.find(_qn_c("chart"))
        chart_type = "column"
        title = None

        if old_chart_elem is not None:
            pa = old_chart_elem.find(_qn_c("plotArea"))
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

            title_elem = old_chart_elem.find(_qn_c("title"))
            if title_elem is not None:
                tx = title_elem.find(_qn_c("tx"))
                if tx is not None:
                    rich = tx.find(_qn_c("rich"))
                    if rich is not None:
                        from mcp_handley_lab.microsoft.common.charts import _qn_a

                        texts = [t.text for t in rich.iter(_qn_a("t")) if t.text]
                        if texts:
                            title = "".join(texts)

        # Regenerate chart XML
        cat_range, series_list = compute_chart_refs(sheet_name, n_rows, n_cols)
        new_chart = create_chart_xml(
            chart_type,
            sheet_name,
            cat_range,
            series_list,
            title=title,
            external_data_rid=embed_rid,
        )
        pkg.set_xml(chart_path, new_chart, CT_CHART)
        return

    raise KeyError(f"Chart not found: {shape_key}")
