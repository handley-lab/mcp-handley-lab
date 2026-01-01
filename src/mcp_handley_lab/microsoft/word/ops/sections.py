"""Section and page layout operations.

Contains functions for:
- Page setup reading (margins, orientation, columns, line numbering)
- Setting page margins and orientation
- Adding sections
- Multi-column layout
- Line numbering
"""

from __future__ import annotations

import copy
import re

from lxml import etree

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.enums import WdSection
from mcp_handley_lab.microsoft.word.models import LineNumberingInfo, PageSetupInfo

# EMU per inch for unit conversions
_EMU_PER_INCH = 914400

# =============================================================================
# Constants
# =============================================================================

# Section start type mapping
_SECTION_START_MAP = {
    "new_page": WdSection.NEW_PAGE,
    "continuous": WdSection.CONTINUOUS,
    "even_page": WdSection.EVEN_PAGE,
    "odd_page": WdSection.ODD_PAGE,
    "new_column": WdSection.NEW_COLUMN,
}

# OOXML schema order for w:sectPr children (partial list for insertion)
_SECTPR_ORDER = [
    "footnotePr",
    "endnotePr",
    "type",
    "pgSz",
    "pgMar",
    "paperSrc",
    "pgBorders",
    "lnNumType",
    "pgNumType",
    "cols",
    "formProt",
    "vAlign",
    "noEndnote",
    "titlePg",
    "textDirection",
    "bidi",
    "rtlGutter",
    "docGrid",
]


# =============================================================================
# Page Setup Reading
# =============================================================================


def _parse_sectpr(sectPr, idx: int) -> PageSetupInfo:
    """Parse a w:sectPr element into PageSetupInfo (pure OOXML)."""
    # Page size from w:pgSz
    pgSz = sectPr.find(qn("w:pgSz"))
    page_width = 0.0
    page_height = 0.0
    orientation = "portrait"
    if pgSz is not None:
        w = pgSz.get(qn("w:w"))
        h = pgSz.get(qn("w:h"))
        page_width = round(int(w) / 1440, 2) if w else 0.0  # twips to inches
        page_height = round(int(h) / 1440, 2) if h else 0.0
        orient = pgSz.get(qn("w:orient"))
        orientation = "landscape" if orient == "landscape" else "portrait"

    # Margins from w:pgMar
    pgMar = sectPr.find(qn("w:pgMar"))
    top_margin = bottom_margin = left_margin = right_margin = 0.0
    if pgMar is not None:
        t = pgMar.get(qn("w:top"))
        b = pgMar.get(qn("w:bottom"))
        left = pgMar.get(qn("w:left"))
        right = pgMar.get(qn("w:right"))
        top_margin = round(int(t) / 1440, 2) if t else 0.0
        bottom_margin = round(int(b) / 1440, 2) if b else 0.0
        left_margin = round(int(left) / 1440, 2) if left else 0.0
        right_margin = round(int(right) / 1440, 2) if right else 0.0

    # Column settings from w:cols
    columns = 1
    column_spacing = 0.5
    column_separator = False
    cols_el = sectPr.find(qn("w:cols"))
    if cols_el is not None:
        num = cols_el.get(qn("w:num"))
        columns = int(num) if num else 1
        space = cols_el.get(qn("w:space"))
        if space:
            column_spacing = round(int(space) / 1440, 2)
        sep = cols_el.get(qn("w:sep"))
        column_separator = sep == "1" or sep == "true"

    # Line numbering from w:lnNumType
    line_numbering = None
    ln_el = sectPr.find(qn("w:lnNumType"))
    if ln_el is not None:
        restart_map = {
            "newPage": "newPage",
            "newSection": "newSection",
            "continuous": "continuous",
        }
        restart_val = ln_el.get(qn("w:restart")) or "newPage"
        start_val = ln_el.get(qn("w:start")) or "1"
        count_by_val = ln_el.get(qn("w:countBy")) or "1"
        distance_val = ln_el.get(qn("w:distance")) or "720"
        line_numbering = LineNumberingInfo(
            enabled=True,
            restart=restart_map.get(restart_val, "newPage"),
            start=int(start_val),
            count_by=int(count_by_val),
            distance_inches=round(int(distance_val) / 1440, 2),
        )

    return PageSetupInfo(
        section_index=idx,
        orientation=orientation,
        page_width=page_width,
        page_height=page_height,
        top_margin=top_margin,
        bottom_margin=bottom_margin,
        left_margin=left_margin,
        right_margin=right_margin,
        columns=columns,
        column_spacing=column_spacing,
        column_separator=column_separator,
        line_numbering=line_numbering,
    )


def build_page_setup(pkg) -> list[PageSetupInfo]:
    """Build list of PageSetupInfo for all sections.

    Args:
        pkg: WordPackage
    """
    body = pkg.body
    result = []
    idx = 0

    # Section breaks within paragraphs (w:p/w:pPr/w:sectPr)
    for p in body.findall(qn("w:p")):
        pPr = p.find(qn("w:pPr"))
        if pPr is not None:
            sectPr = pPr.find(qn("w:sectPr"))
            if sectPr is not None:
                result.append(_parse_sectpr(sectPr, idx))
                idx += 1

    # Final section (w:body/w:sectPr)
    body_sectPr = body.find(qn("w:sectPr"))
    if body_sectPr is not None:
        result.append(_parse_sectpr(body_sectPr, idx))

    return result


# =============================================================================
# Section Element Lookup (pure OOXML)
# =============================================================================


def _get_sectpr_by_index(pkg, section_index: int) -> etree._Element:
    """Find sectPr by index in WordPackage (pure OOXML).

    Sections are stored as:
    - w:p/w:pPr/w:sectPr for section breaks within document
    - w:body/w:sectPr for final section
    """
    body = pkg.body
    sectprs = []

    # Section breaks within paragraphs
    for p in body.findall(qn("w:p")):
        pPr = p.find(qn("w:pPr"))
        if pPr is not None:
            sectPr = pPr.find(qn("w:sectPr"))
            if sectPr is not None:
                sectprs.append(sectPr)

    # Final section (w:body/w:sectPr)
    body_sectPr = body.find(qn("w:sectPr"))
    if body_sectPr is not None:
        sectprs.append(body_sectPr)

    return sectprs[section_index]


def _mark_dirty(pkg) -> None:
    """Mark document.xml as dirty."""
    pkg.mark_xml_dirty("/word/document.xml")


# =============================================================================
# Page Settings
# =============================================================================


def set_page_margins(
    pkg,
    section_index: int,
    top: float | None = None,
    bottom: float | None = None,
    left: float | None = None,
    right: float | None = None,
) -> None:
    """Set page margins for a section. Values in inches.

    Args:
        pkg: WordPackage
        section_index: 0-based section index
        top, bottom, left, right: Margins in inches (None = keep existing)
    """
    sectPr = _get_sectpr_by_index(pkg, section_index)

    # Get or create w:pgMar element
    pgMar = sectPr.find(qn("w:pgMar"))
    if pgMar is None:
        pgMar = etree.Element(qn("w:pgMar"))
        _insert_sectpr_element(sectPr, pgMar, "pgMar")

    # Set margins in twips (1440 twips = 1 inch), only if provided
    if top is not None:
        pgMar.set(qn("w:top"), str(int(top * 1440)))
    if bottom is not None:
        pgMar.set(qn("w:bottom"), str(int(bottom * 1440)))
    if left is not None:
        pgMar.set(qn("w:left"), str(int(left * 1440)))
    if right is not None:
        pgMar.set(qn("w:right"), str(int(right * 1440)))
    _mark_dirty(pkg)


def set_page_orientation(pkg, section_index: int, orientation: str) -> None:
    """Set page orientation for a section. Valid: 'portrait' or 'landscape'.

    Args:
        pkg: WordPackage
        section_index: 0-based section index
        orientation: 'portrait' or 'landscape'
    """
    sectPr = _get_sectpr_by_index(pkg, section_index)

    # Get or create w:pgSz element
    pgSz = sectPr.find(qn("w:pgSz"))
    if pgSz is None:
        pgSz = etree.Element(qn("w:pgSz"))
        _insert_sectpr_element(sectPr, pgSz, "pgSz")
        # Default letter size in twips (8.5" x 11")
        pgSz.set(qn("w:w"), str(int(8.5 * 1440)))
        pgSz.set(qn("w:h"), str(int(11 * 1440)))

    # Get current dimensions
    w = int(pgSz.get(qn("w:w")) or str(int(8.5 * 1440)))
    h = int(pgSz.get(qn("w:h")) or str(int(11 * 1440)))

    # Set orientation attribute
    if orientation.lower() == "landscape":
        pgSz.set(qn("w:orient"), "landscape")
        # Swap dimensions if currently portrait
        if h > w:
            pgSz.set(qn("w:w"), str(h))
            pgSz.set(qn("w:h"), str(w))
    else:
        # Remove orient attribute for portrait (default)
        if qn("w:orient") in pgSz.attrib:
            del pgSz.attrib[qn("w:orient")]
        # Swap dimensions if currently landscape
        if w > h:
            pgSz.set(qn("w:w"), str(h))
            pgSz.set(qn("w:h"), str(w))

    _mark_dirty(pkg)


def add_section(pkg, start_type: str = "new_page") -> int:
    """Add new section. Returns new section index (0-based).

    Args:
        pkg: WordPackage
        start_type: 'new_page', 'continuous', 'even_page', 'odd_page', 'new_column'
    """
    # OOXML type values
    _TYPE_MAP = {
        "new_page": "nextPage",
        "continuous": "continuous",
        "even_page": "evenPage",
        "odd_page": "oddPage",
        "new_column": "nextColumn",
    }
    type_val = _TYPE_MAP[start_type.lower()]

    body = pkg.body

    # Get the body's sectPr (defines final section properties)
    body_sectPr = body.find(qn("w:sectPr"))
    if body_sectPr is None:
        # Create minimal sectPr if not present
        body_sectPr = etree.SubElement(body, qn("w:sectPr"))

    # Deep copy the body sectPr to create the new section break
    new_sectPr = copy.deepcopy(body_sectPr)

    # Set the section type on the new sectPr
    type_el = new_sectPr.find(qn("w:type"))
    if type_el is None:
        type_el = etree.Element(qn("w:type"))
        _insert_sectpr_element(new_sectPr, type_el, "type")
    type_el.set(qn("w:val"), type_val)

    # Find or create the last paragraph in the body
    paras = body.findall(qn("w:p"))
    if not paras:
        # Create empty paragraph
        last_para = etree.Element(qn("w:p"))
        # Insert before sectPr
        body.insert(list(body).index(body_sectPr), last_para)
    else:
        last_para = paras[-1]

    # Get or create pPr in the last paragraph
    pPr = last_para.find(qn("w:pPr"))
    if pPr is None:
        pPr = etree.Element(qn("w:pPr"))
        last_para.insert(0, pPr)

    # Remove any existing sectPr in pPr (shouldn't be one, but just in case)
    existing_sectPr = pPr.find(qn("w:sectPr"))
    if existing_sectPr is not None:
        pPr.remove(existing_sectPr)

    # Add the new sectPr to pPr
    pPr.append(new_sectPr)

    # Mark document.xml as dirty
    _mark_dirty(pkg)

    # Count sections (sectPr in paragraphs + body sectPr)
    section_count = len(
        [
            p
            for p in body.findall(qn("w:p"))
            if p.find(qn("w:pPr")) is not None
            and p.find(qn("w:pPr")).find(qn("w:sectPr")) is not None
        ]
    )
    if body.find(qn("w:sectPr")) is not None:
        section_count += 1

    return section_count - 1


# =============================================================================
# Section Element Helpers
# =============================================================================


def _insert_sectpr_element(sectPr, element, local_name: str) -> None:
    """Insert element into sectPr at schema-correct position."""
    if local_name not in _SECTPR_ORDER:
        raise ValueError(f"Unknown sectPr element: {local_name}")
    target_idx = _SECTPR_ORDER.index(local_name)

    # Find first child that should come after this element
    for i, child in enumerate(sectPr):
        child_local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        try:
            child_idx = _SECTPR_ORDER.index(child_local)
            if child_idx > target_idx:
                sectPr.insert(i, element)
                return
        except ValueError:
            pass

    # No later element found, append
    sectPr.append(element)


# =============================================================================
# Columns and Line Numbering
# =============================================================================


def set_section_columns(
    pkg,
    section_index: int,
    num_columns: int,
    spacing_inches: float = 0.5,
    separator: bool = False,
) -> None:
    """Set multi-column layout for a section.

    Args:
        pkg: WordPackage
        section_index: 0-based section index
        num_columns: Number of columns (1-16)
        spacing_inches: Space between columns in inches
        separator: True to show line between columns
    """
    sectPr = _get_sectpr_by_index(pkg, section_index)

    # Get or create w:cols element
    cols = sectPr.find(qn("w:cols"))
    if cols is None:
        cols = etree.Element(qn("w:cols"))
        _insert_sectpr_element(sectPr, cols, "cols")

    # Set attributes
    cols.set(qn("w:num"), str(num_columns))
    cols.set(qn("w:space"), str(int(spacing_inches * 1440)))  # inches to twips
    cols.set(qn("w:sep"), "1" if separator else "0")

    _mark_dirty(pkg)


def set_line_numbering(
    pkg,
    section_index: int,
    enabled: bool = True,
    restart: str = "newPage",
    start: int = 1,
    count_by: int = 1,
    distance_inches: float = 0.5,
) -> None:
    """Enable/configure line numbering for a section.

    Args:
        pkg: WordPackage
        section_index: 0-based section index
        enabled: True to enable, False to disable line numbering
        restart: When to restart: 'newPage', 'newSection', or 'continuous'
        start: Starting number
        count_by: Show number every N lines
        distance_inches: Distance from margin in inches
    """
    sectPr = _get_sectpr_by_index(pkg, section_index)

    # Find existing w:lnNumType
    lnNumType = sectPr.find(qn("w:lnNumType"))

    if not enabled:
        # Remove if exists
        if lnNumType is not None:
            sectPr.remove(lnNumType)
        _mark_dirty(pkg)
        return

    # Create if not exists
    if lnNumType is None:
        lnNumType = etree.Element(qn("w:lnNumType"))
        _insert_sectpr_element(sectPr, lnNumType, "lnNumType")

    # Set attributes
    lnNumType.set(qn("w:restart"), restart)
    lnNumType.set(qn("w:start"), str(start))
    lnNumType.set(qn("w:countBy"), str(count_by))
    lnNumType.set(qn("w:distance"), str(int(distance_inches * 1440)))  # inches to twips

    _mark_dirty(pkg)


# =============================================================================
# Page Borders
# =============================================================================

# Supported page border styles (curated subset of ST_Border for common use cases)
# Full ST_Border has 100+ values including decorative art borders (apples, etc.)
# Unknown styles are passed through to allow power-user OOXML access
_SUPPORTED_BORDER_STYLES = {
    "single",
    "double",
    "dotted",
    "dashed",
    "dashSmallGap",
    "dotDash",
    "dotDotDash",
    "triple",
    "thinThickSmallGap",
    "thickThinSmallGap",
    "thinThickThinSmallGap",
    "thinThickMediumGap",
    "thickThinMediumGap",
    "thinThickThinMediumGap",
    "thinThickLargeGap",
    "thickThinLargeGap",
    "thinThickThinLargeGap",
    "wave",
    "doubleWave",
    "threeDEmboss",
    "threeDEngrave",
    "outset",
    "inset",
    "nil",
    "none",
    "thick",
    "hairline",
}

# Case-normalized lookup for border styles
_BORDER_STYLE_LOOKUP = {s.lower(): s for s in _SUPPORTED_BORDER_STYLES}

_HEX_COLOR_RE = re.compile(r"^[0-9A-Fa-f]{6}$")


def _parse_border_spec(spec: str) -> tuple[str, int, int, str]:
    """Parse border spec 'style:size:space:color' into components.

    Args:
        spec: Format 'style:size:space:color' e.g., 'single:4:24:000000'
              - style: border style name or 'nil' to remove (case-insensitive)
              - size: eighths of a point (4 = 0.5pt, 12 = 1.5pt), 0-255
              - space: points from text/page edge, 0-31
              - color: hex RRGGBB (no #) or 'auto'

    Returns:
        Tuple of (style, size, space, color)
    """
    parts = spec.split(":")
    if len(parts) != 4:
        raise ValueError(f"Border spec must be 'style:size:space:color', got: {spec}")

    style_input, size_str, space_str, color = parts

    # Normalize style (case-insensitive, allow unknown for power users)
    style_lower = style_input.lower()
    style = _BORDER_STYLE_LOOKUP.get(style_lower, style_input)

    # Validate and parse size (eighths of a point, 0-255)
    try:
        size = int(size_str)
    except ValueError:
        raise ValueError(f"Border size must be integer, got: {size_str}")
    if size < 0 or size > 255:
        raise ValueError(f"Border size must be 0-255, got: {size}")

    # Validate and parse space (points, 0-31 per OOXML spec)
    try:
        space = int(space_str)
    except ValueError:
        raise ValueError(f"Border space must be integer, got: {space_str}")
    if space < 0 or space > 31:
        raise ValueError(f"Border space must be 0-31 points, got: {space}")

    # Validate color: 'auto' or 6-digit hex
    color = color.strip()
    if color.startswith("#"):
        color = color[1:]
    color_upper = color.upper()
    if color_upper != "AUTO" and not _HEX_COLOR_RE.match(color):
        raise ValueError(
            f"Border color must be 'auto' or 6-digit hex (RRGGBB), got: {color}"
        )
    color = "auto" if color_upper == "AUTO" else color_upper

    return style, size, space, color


def set_page_borders(
    pkg,
    section_index: int = 0,
    top: str | None = None,
    bottom: str | None = None,
    left: str | None = None,
    right: str | None = None,
    offset_from: str = "text",
) -> None:
    """Set page borders for a section.

    Args:
        pkg: WordPackage
        section_index: 0-based section index
        top, bottom, left, right: Border spec 'style:size:space:color'
            e.g., 'single:4:24:000000' (0.5pt single black border, 24pt from text)
            Use 'nil:0:0:auto' to remove a border
        offset_from: 'text' (from text margin) or 'page' (from page edge)
    """
    offset_from = offset_from.lower()
    if offset_from not in ("text", "page"):
        raise ValueError(f"offset_from must be 'text' or 'page', got: {offset_from}")

    sectPr = _get_sectpr_by_index(pkg, section_index)

    # Get or create w:pgBorders element
    pgBorders = sectPr.find(qn("w:pgBorders"))
    if pgBorders is None:
        pgBorders = etree.Element(qn("w:pgBorders"))
        _insert_sectpr_element(sectPr, pgBorders, "pgBorders")

    pgBorders.set(qn("w:offsetFrom"), offset_from)

    # Process each border side
    for side, spec in [
        ("top", top),
        ("bottom", bottom),
        ("left", left),
        ("right", right),
    ]:
        if spec is None:
            continue

        style, size, space, color = _parse_border_spec(spec)

        # Find or create the side element
        side_el = pgBorders.find(qn(f"w:{side}"))
        if side_el is None:
            side_el = etree.SubElement(pgBorders, qn(f"w:{side}"))

        if style.lower() == "nil":
            # Remove this border
            side_el.set(qn("w:val"), "nil")
            # Clear other attributes
            for attr in ["sz", "space", "color"]:
                if qn(f"w:{attr}") in side_el.attrib:
                    del side_el.attrib[qn(f"w:{attr}")]
        else:
            side_el.set(qn("w:val"), style)
            side_el.set(qn("w:sz"), str(size))
            side_el.set(qn("w:space"), str(space))
            side_el.set(qn("w:color"), color)

    _mark_dirty(pkg)
