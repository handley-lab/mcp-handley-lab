"""Style creation operations for Excel.

Create fonts, fills, borders, number formats, and cell styles.
All functions return the 0-based index of the created element.
"""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import CT, NSMAP, RT, qn
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def _get_styles_path(pkg: ExcelPackage) -> str:
    """Get styles.xml path from workbook relationships."""
    wb_rels = pkg.get_rels(pkg.workbook_path)
    rId = wb_rels.rId_for_reltype(RT.STYLES)
    if rId:
        return pkg.resolve_rel_target(pkg.workbook_path, rId)
    return "/xl/styles.xml"


def _ensure_styles_xml(pkg: ExcelPackage) -> etree._Element:
    """Get styles.xml, creating if needed."""
    styles = pkg.styles_xml
    if styles is not None:
        return styles

    # Create minimal styles.xml
    styles = etree.Element(qn("x:styleSheet"), nsmap={None: NSMAP["x"]})

    # Required elements with minimal content
    fonts = etree.SubElement(styles, qn("x:fonts"), count="1")
    font = etree.SubElement(fonts, qn("x:font"))
    etree.SubElement(font, qn("x:sz"), val="11")
    etree.SubElement(font, qn("x:name"), val="Calibri")

    fills = etree.SubElement(styles, qn("x:fills"), count="2")
    fill1 = etree.SubElement(fills, qn("x:fill"))
    etree.SubElement(fill1, qn("x:patternFill"), patternType="none")
    fill2 = etree.SubElement(fills, qn("x:fill"))
    etree.SubElement(fill2, qn("x:patternFill"), patternType="gray125")

    borders = etree.SubElement(styles, qn("x:borders"), count="1")
    border = etree.SubElement(borders, qn("x:border"))
    for side in ("left", "right", "top", "bottom", "diagonal"):
        etree.SubElement(border, qn(f"x:{side}"))

    cellStyleXfs = etree.SubElement(styles, qn("x:cellStyleXfs"), count="1")
    etree.SubElement(
        cellStyleXfs, qn("x:xf"), numFmtId="0", fontId="0", fillId="0", borderId="0"
    )

    cellXfs = etree.SubElement(styles, qn("x:cellXfs"), count="1")
    etree.SubElement(
        cellXfs,
        qn("x:xf"),
        numFmtId="0",
        fontId="0",
        fillId="0",
        borderId="0",
        xfId="0",
    )

    pkg.set_xml("/xl/styles.xml", styles, CT.SML_STYLES)
    pkg.relate_to(pkg.workbook_path, "styles.xml", RT.STYLES)
    return styles


def _get_index_and_update_count(element: etree._Element, child_tag: str) -> int:
    """Get actual child count, update count attribute, and return index for new element.

    Uses actual child count rather than @count attribute to handle stale/missing values.
    The new element should already be appended before calling this.
    """
    children = element.findall(child_tag)
    actual_count = len(children)
    element.set("count", str(actual_count))
    return actual_count - 1  # Return index of last (just-added) element


def create_font(
    pkg: ExcelPackage,
    name: str = "Calibri",
    size: float = 11,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    color: str | None = None,
) -> int:
    """Create a font definition and return its index.

    Args:
        pkg: Excel package.
        name: Font family name (default: Calibri).
        size: Font size in points (default: 11).
        bold: If True, make bold.
        italic: If True, make italic.
        underline: If True, add underline.
        color: RGB hex color (e.g., "FF0000" for red). No leading #.

    Returns: 0-based font index for use in create_cell_style.
    """
    styles = _ensure_styles_xml(pkg)
    fonts = styles.find(qn("x:fonts"))
    if fonts is None:
        fonts = etree.SubElement(styles, qn("x:fonts"), count="0")

    font = etree.SubElement(fonts, qn("x:font"))

    if bold:
        etree.SubElement(font, qn("x:b"))
    if italic:
        etree.SubElement(font, qn("x:i"))
    if underline:
        etree.SubElement(font, qn("x:u"))

    etree.SubElement(font, qn("x:sz"), val=str(size))
    if color:
        # Normalize color - strip # if present, ensure 6 or 8 chars
        color = color.lstrip("#").upper()
        if len(color) == 6:
            color = "FF" + color  # Add full opacity alpha
        etree.SubElement(font, qn("x:color"), rgb=color)
    etree.SubElement(font, qn("x:name"), val=name)

    idx = _get_index_and_update_count(fonts, qn("x:font"))
    pkg.mark_xml_dirty(_get_styles_path(pkg))
    return idx


def create_fill(
    pkg: ExcelPackage,
    pattern: str = "solid",
    fg_color: str | None = None,
    bg_color: str | None = None,
) -> int:
    """Create a fill definition and return its index.

    Args:
        pkg: Excel package.
        pattern: Pattern type (solid, gray125, none, etc.). Default: solid.
        fg_color: Foreground RGB hex (for solid, this is the fill color).
        bg_color: Background RGB hex (for patterns).

    Returns: 0-based fill index for use in create_cell_style.
    """
    styles = _ensure_styles_xml(pkg)
    fills = styles.find(qn("x:fills"))
    if fills is None:
        fills = etree.SubElement(styles, qn("x:fills"), count="0")

    fill = etree.SubElement(fills, qn("x:fill"))
    pattern_fill = etree.SubElement(fill, qn("x:patternFill"), patternType=pattern)

    if fg_color:
        fg_color = fg_color.lstrip("#").upper()
        if len(fg_color) == 6:
            fg_color = "FF" + fg_color
        etree.SubElement(pattern_fill, qn("x:fgColor"), rgb=fg_color)

    if bg_color:
        bg_color = bg_color.lstrip("#").upper()
        if len(bg_color) == 6:
            bg_color = "FF" + bg_color
        etree.SubElement(pattern_fill, qn("x:bgColor"), rgb=bg_color)

    idx = _get_index_and_update_count(fills, qn("x:fill"))
    pkg.mark_xml_dirty(_get_styles_path(pkg))
    return idx


def create_border(
    pkg: ExcelPackage,
    left: str | None = None,
    right: str | None = None,
    top: str | None = None,
    bottom: str | None = None,
    diagonal: str | None = None,
    color: str | None = None,
) -> int:
    """Create a border definition and return its index.

    Args:
        pkg: Excel package.
        left: Left border style (thin, medium, thick, dotted, dashed, etc.).
        right: Right border style.
        top: Top border style.
        bottom: Bottom border style.
        diagonal: Diagonal border style.
        color: RGB hex color for all borders (default: black).

    Returns: 0-based border index for use in create_cell_style.
    """
    styles = _ensure_styles_xml(pkg)
    borders = styles.find(qn("x:borders"))
    if borders is None:
        borders = etree.SubElement(styles, qn("x:borders"), count="0")

    border = etree.SubElement(borders, qn("x:border"))

    # Normalize color
    if color:
        color = color.lstrip("#").upper()
        if len(color) == 6:
            color = "FF" + color

    for side_name, style in [
        ("left", left),
        ("right", right),
        ("top", top),
        ("bottom", bottom),
        ("diagonal", diagonal),
    ]:
        side_elem = etree.SubElement(border, qn(f"x:{side_name}"))
        if style:
            side_elem.set("style", style)
            if color:
                etree.SubElement(side_elem, qn("x:color"), rgb=color)

    idx = _get_index_and_update_count(borders, qn("x:border"))
    pkg.mark_xml_dirty(_get_styles_path(pkg))
    return idx


def create_number_format(pkg: ExcelPackage, format_code: str) -> int:
    """Create a custom number format and return its ID.

    Args:
        pkg: Excel package.
        format_code: Excel format string (e.g., "#,##0.00", "yyyy-mm-dd").

    Returns: Number format ID (starting from 164 for custom formats).

    Note: Built-in formats use IDs 0-163. Custom formats start at 164.
    """
    styles = _ensure_styles_xml(pkg)
    num_fmts = styles.find(qn("x:numFmts"))
    if num_fmts is None:
        # Insert numFmts at the start (before fonts)
        num_fmts = etree.Element(qn("x:numFmts"), count="0")
        styles.insert(0, num_fmts)

    # Find next available ID (custom formats start at 164)
    existing_ids = {
        int(nf.get("numFmtId", "0")) for nf in num_fmts.findall(qn("x:numFmt"))
    }
    next_id = 164
    while next_id in existing_ids:
        next_id += 1

    etree.SubElement(
        num_fmts, qn("x:numFmt"), numFmtId=str(next_id), formatCode=format_code
    )
    _get_index_and_update_count(num_fmts, qn("x:numFmt"))
    pkg.mark_xml_dirty(_get_styles_path(pkg))
    return next_id


def create_cell_style(
    pkg: ExcelPackage,
    font_id: int | None = None,
    fill_id: int | None = None,
    border_id: int | None = None,
    num_fmt_id: int | None = None,
) -> int:
    """Create a cell style (cellXf) combining font, fill, border, and number format.

    Args:
        pkg: Excel package.
        font_id: Font index from create_font (default: 0).
        fill_id: Fill index from create_fill (default: 0).
        border_id: Border index from create_border (default: 0).
        num_fmt_id: Number format ID from create_number_format (default: 0).

    Returns: 0-based style index for use with set_cell_style or apply_style.
    """
    styles = _ensure_styles_xml(pkg)
    cell_xfs = styles.find(qn("x:cellXfs"))
    if cell_xfs is None:
        cell_xfs = etree.SubElement(styles, qn("x:cellXfs"), count="0")

    xf = etree.SubElement(
        cell_xfs,
        qn("x:xf"),
        numFmtId=str(num_fmt_id or 0),
        fontId=str(font_id or 0),
        fillId=str(fill_id or 0),
        borderId=str(border_id or 0),
        xfId="0",  # Reference to cellStyleXfs
    )

    # Add apply flags for non-default values
    if font_id is not None and font_id != 0:
        xf.set("applyFont", "1")
    if fill_id is not None and fill_id != 0:
        xf.set("applyFill", "1")
    if border_id is not None and border_id != 0:
        xf.set("applyBorder", "1")
    if num_fmt_id is not None and num_fmt_id != 0:
        xf.set("applyNumberFormat", "1")

    idx = _get_index_and_update_count(cell_xfs, qn("x:xf"))
    pkg.mark_xml_dirty(_get_styles_path(pkg))
    return idx
