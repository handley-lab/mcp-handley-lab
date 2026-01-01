"""Formatting and style operations for Excel.

Excel uses indexed styles - cells reference style indices, and styles are
defined in styles.xml. This module provides read access to style definitions.
"""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import NSMAP, qn
from mcp_handley_lab.microsoft.excel.models import ConditionalFormatInfo, StyleInfo
from mcp_handley_lab.microsoft.excel.ops.core import (
    get_sheet_path as _get_sheet_path,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    insert_sheet_element,
    make_range_id,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def list_styles(pkg: ExcelPackage) -> list[StyleInfo]:
    """List all cell styles in the workbook.

    Returns: List of StyleInfo for each cell format (cellXf).
    """
    styles_xml = pkg.styles_xml
    if styles_xml is None:
        return []

    result = []
    cell_xfs = styles_xml.find(qn("x:cellXfs"))
    if cell_xfs is None:
        return []

    # Pre-fetch element lists once for O(1) lookup
    fonts_el = styles_xml.find(qn("x:fonts"))
    fills_el = styles_xml.find(qn("x:fills"))
    borders_el = styles_xml.find(qn("x:borders"))
    fonts = fonts_el.findall(qn("x:font")) if fonts_el is not None else []
    fills = fills_el.findall(qn("x:fill")) if fills_el is not None else []
    borders = borders_el.findall(qn("x:border")) if borders_el is not None else []

    # Build number format lookup
    num_fmt_map = _get_builtin_number_formats()
    num_fmts = styles_xml.find(qn("x:numFmts"))
    if num_fmts is not None:
        for nf in num_fmts.findall(qn("x:numFmt")):
            fmt_id = nf.get("numFmtId")
            fmt_code = nf.get("formatCode")
            if fmt_id and fmt_code:
                num_fmt_map[int(fmt_id)] = fmt_code

    for idx, xf in enumerate(cell_xfs.findall(qn("x:xf"))):
        info = StyleInfo(index=idx)

        font_id = xf.get("fontId")
        if font_id and int(font_id) < len(fonts):
            info.font = _describe_font(fonts[int(font_id)])

        fill_id = xf.get("fillId")
        if fill_id and int(fill_id) < len(fills):
            info.fill = _describe_fill(fills[int(fill_id)])

        border_id = xf.get("borderId")
        if border_id and int(border_id) < len(borders):
            info.border = _describe_border(borders[int(border_id)])

        num_fmt_id = xf.get("numFmtId")
        if num_fmt_id:
            fmt_code = num_fmt_map.get(int(num_fmt_id))
            if fmt_code:
                info.number_format = fmt_code

        result.append(info)

    return result


def get_style_by_index(pkg: ExcelPackage, index: int) -> StyleInfo:
    """Get style info by index."""
    return list_styles(pkg)[index]


def get_number_format(pkg: ExcelPackage, format_index: int) -> str | None:
    """Get number format code by format ID.

    Returns format code string or None if not found.
    """
    # Check built-in formats first
    builtin = _get_builtin_number_formats()
    if format_index in builtin:
        return builtin[format_index]

    # Check custom formats in styles.xml
    styles_xml = pkg.styles_xml
    if styles_xml is None:
        return None

    num_fmts = styles_xml.find(qn("x:numFmts"))
    if num_fmts is None:
        return None

    for nf in num_fmts.findall(qn("x:numFmt")):
        if nf.get("numFmtId") == str(format_index):
            return nf.get("formatCode")

    return None


def _describe_font(font_el: etree._Element) -> str:
    """Generate human-readable font description."""
    parts = []

    name = font_el.find(qn("x:name"))
    if name is not None:
        parts.append(name.get("val", ""))

    sz = font_el.find(qn("x:sz"))
    if sz is not None:
        parts.append(f"{sz.get('val')}pt")

    if font_el.find(qn("x:b")) is not None:
        parts.append("bold")
    if font_el.find(qn("x:i")) is not None:
        parts.append("italic")
    if font_el.find(qn("x:u")) is not None:
        parts.append("underline")

    color = font_el.find(qn("x:color"))
    if color is not None:
        rgb = color.get("rgb")
        if rgb:
            parts.append(f"#{rgb}")
        theme = color.get("theme")
        if theme:
            parts.append(f"theme:{theme}")

    return " ".join(parts) if parts else "default"


def _describe_fill(fill_el: etree._Element) -> str:
    """Generate human-readable fill description."""
    pattern = fill_el.find(qn("x:patternFill"))
    if pattern is not None:
        pattern_type = pattern.get("patternType", "none")
        if pattern_type == "none":
            return "none"
        if pattern_type == "solid":
            fg = pattern.find(qn("x:fgColor"))
            if fg is not None:
                rgb = fg.get("rgb")
                if rgb:
                    return f"solid #{rgb}"
                theme = fg.get("theme")
                if theme:
                    return f"solid theme:{theme}"
            return "solid"
        return pattern_type

    gradient = fill_el.find(qn("x:gradientFill"))
    if gradient is not None:
        return "gradient"

    return "none"


def _describe_border(border_el: etree._Element) -> str:
    """Generate human-readable border description."""
    sides = []
    for side in ("left", "right", "top", "bottom"):
        side_el = border_el.find(qn(f"x:{side}"))
        if side_el is not None:
            style = side_el.get("style")
            if style:
                sides.append(f"{side}:{style}")

    return ", ".join(sides) if sides else "none"


def _get_builtin_number_formats() -> dict[int, str]:
    """Return built-in Excel number formats (0-49 are predefined)."""
    return {
        0: "General",
        1: "0",
        2: "0.00",
        3: "#,##0",
        4: "#,##0.00",
        9: "0%",
        10: "0.00%",
        11: "0.00E+00",
        12: "# ?/?",
        13: "# ??/??",
        14: "mm-dd-yy",
        15: "d-mmm-yy",
        16: "d-mmm",
        17: "mmm-yy",
        18: "h:mm AM/PM",
        19: "h:mm:ss AM/PM",
        20: "h:mm",
        21: "h:mm:ss",
        22: "m/d/yy h:mm",
        37: "#,##0 ;(#,##0)",
        38: "#,##0 ;[Red](#,##0)",
        39: "#,##0.00;(#,##0.00)",
        40: "#,##0.00;[Red](#,##0.00)",
        45: "mm:ss",
        46: "[h]:mm:ss",
        47: "mmss.0",
        48: "##0.0E+0",
        49: "@",
    }


def get_conditional_formats(
    pkg: ExcelPackage, sheet_name: str
) -> list[ConditionalFormatInfo]:
    """Get conditional formatting rules for a sheet.

    Returns: List of ConditionalFormatInfo for each rule.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    result = []

    for cf in sheet_xml.findall(qn("x:conditionalFormatting")):
        sqref = cf.get("sqref", "")

        for rule in cf.findall(qn("x:cfRule")):
            rule_type = rule.get("type", "")
            priority = int(rule.get("priority", "0"))

            info = ConditionalFormatInfo(
                id=make_range_id(sheet_name, sqref),
                ref=sqref,
                type=rule_type,
                priority=priority,
            )

            # Operator for cellIs rules
            operator = rule.get("operator")
            if operator:
                info.operator = operator

            # Formula(s) for the rule
            formulas = rule.findall(qn("x:formula"))
            if formulas:
                # Join multiple formulas (e.g., between operator uses two)
                info.formula = ";".join(f.text or "" for f in formulas)

            # Style index (dxfId - differential formatting)
            dxf_id = rule.get("dxfId")
            if dxf_id is not None:
                info.style_index = int(dxf_id)

            result.append(info)

    return result


def add_conditional_format(
    pkg: ExcelPackage,
    sheet_name: str,
    range_ref: str,
    rule_type: str,
    operator: str | None = None,
    formula: str | None = None,
    style_index: int | None = None,
    priority: int = 1,
) -> ConditionalFormatInfo:
    """Add a conditional formatting rule to a sheet.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        range_ref: Range to apply formatting (e.g., "A1:C10").
        rule_type: Rule type (cellIs, colorScale, dataBar, etc.).
        operator: Operator for cellIs (lessThan, greaterThan, equal, etc.).
        formula: Formula or value for comparison.
        style_index: Differential formatting index (dxfId).
        priority: Rule priority (lower = higher priority).

    Returns: ConditionalFormatInfo for the created rule.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)

    # Find or create conditionalFormatting element for this range
    cf_elem = None
    for cf in sheet_xml.findall(qn("x:conditionalFormatting")):
        if cf.get("sqref") == range_ref:
            cf_elem = cf
            break

    if cf_elem is None:
        # Create new conditionalFormatting element at correct OOXML position
        cf_elem = etree.Element(qn("x:conditionalFormatting"), nsmap=NSMAP)
        cf_elem.set("sqref", range_ref)
        insert_sheet_element(sheet_xml, "conditionalFormatting", cf_elem)

    # Create the rule
    rule_elem = etree.SubElement(cf_elem, qn("x:cfRule"))
    rule_elem.set("type", rule_type)
    rule_elem.set("priority", str(priority))

    if operator:
        rule_elem.set("operator", operator)

    if style_index is not None:
        rule_elem.set("dxfId", str(style_index))

    if formula:
        # Support multiple formulas separated by semicolon
        for f in formula.split(";"):
            formula_elem = etree.SubElement(rule_elem, qn("x:formula"))
            formula_elem.text = f.strip()

    # Mark sheet as modified
    sheet_path = _get_sheet_path(pkg, sheet_name)
    pkg.mark_xml_dirty(sheet_path)

    return ConditionalFormatInfo(
        id=make_range_id(sheet_name, range_ref),
        ref=range_ref,
        type=rule_type,
        priority=priority,
        operator=operator,
        formula=formula,
        style_index=style_index,
    )
