"""Style, font, and paragraph formatting operations.

Contains functions for:
- Run and paragraph formatting
- Style management (list, get, create, edit, delete)
- Tab stops
- Hyperlinks
"""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.word.constants import RT, qn
from mcp_handley_lab.microsoft.word.models import (
    HyperlinkInfo,
    ParagraphFormatInfo,
    RunInfo,
    StyleFormatInfo,
    StyleInfo,
    TabStopInfo,
)

# =============================================================================
# Constants
# =============================================================================

# Run formatting keys that should be applied to runs in apply_paragraph_formatting
_RUN_FORMAT_KEYS = {
    "bold",
    "italic",
    "underline",
    "strike",
    "double_strike",
    "subscript",
    "superscript",
    "all_caps",
    "small_caps",
    "hidden",
    "emboss",
    "imprint",
    "outline",
    "shadow",
    "font_name",
    "style",
    "font_size",
    "color",
    "highlight_color",
}


# =============================================================================
# Run Building
# =============================================================================

# OOXML highlight color mapping (w:highlight/@w:val -> API string)
_HIGHLIGHT_OOXML_MAP = {
    "yellow": "yellow",
    "green": "green",
    "cyan": "cyan",
    "magenta": "pink",
    "blue": "blue",
    "red": "red",
    "darkBlue": "dark_blue",
    "darkCyan": "cyan",
    "darkGreen": "green",
    "darkMagenta": "pink",
    "darkRed": "dark_red",
    "darkYellow": "dark_yellow",
    "lightGray": "gray",
    "darkGray": "dark_gray",
    "black": "black",
    "white": "white",
}


def _parse_bool_prop(rPr, tag: str) -> bool | None:
    """Parse boolean property from w:rPr (presence or w:val != '0')."""
    el = rPr.find(qn(tag)) if rPr is not None else None
    if el is None:
        return None
    val = el.get(qn("w:val"))
    return val != "0" if val else True


def _build_run_info_ooxml(
    run_el,
    index: int,
    is_hyperlink: bool = False,
    hyperlink_url: str | None = None,
) -> RunInfo:
    """Build RunInfo from a w:r element (pure OOXML)."""
    # Extract text from run content in document order
    # Handle: w:t (text), w:tab (tab), w:br/w:cr (line break), special chars
    text_parts = []
    for child in run_el:
        tag = child.tag
        if tag == qn("w:t"):
            if child.text is not None:
                text_parts.append(child.text)
        elif tag == qn("w:tab"):
            text_parts.append("\t")
        elif tag in (qn("w:br"), qn("w:cr")):
            text_parts.append("\n")
        elif tag == qn("w:noBreakHyphen"):
            text_parts.append("\u2011")  # Non-breaking hyphen
        elif tag == qn("w:softHyphen"):
            text_parts.append("\u00ad")  # Soft hyphen
    text = "".join(text_parts)

    # Get run properties
    rPr = run_el.find(qn("w:rPr"))

    # Font name (w:rFonts/@w:ascii)
    font_name = None
    if rPr is not None:
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is not None:
            font_name = rFonts.get(qn("w:ascii"))

    # Font size (w:sz/@w:val in half-points)
    font_size = None
    if rPr is not None:
        sz = rPr.find(qn("w:sz"))
        if sz is not None:
            val = sz.get(qn("w:val"))
            font_size = int(val) / 2 if val else None

    # Color (w:color/@w:val)
    color = None
    if rPr is not None:
        color_el = rPr.find(qn("w:color"))
        if color_el is not None:
            val = color_el.get(qn("w:val"))
            if val and val != "auto":
                color = val.upper()

    # Highlight (w:highlight/@w:val)
    highlight_color = None
    if rPr is not None:
        highlight = rPr.find(qn("w:highlight"))
        if highlight is not None:
            val = highlight.get(qn("w:val"))
            highlight_color = _HIGHLIGHT_OOXML_MAP.get(val)

    # Underline (w:u presence with @w:val != "none")
    underline = None
    if rPr is not None:
        u = rPr.find(qn("w:u"))
        if u is not None:
            val = u.get(qn("w:val"))
            underline = val not in (None, "none", "0", "false")

    # Vertical alignment (subscript/superscript)
    subscript = None
    superscript = None
    if rPr is not None:
        vertAlign = rPr.find(qn("w:vertAlign"))
        if vertAlign is not None:
            val = vertAlign.get(qn("w:val"))
            subscript = val == "subscript"
            superscript = val == "superscript"

    # Character style (w:rStyle/@w:val)
    style = None
    if rPr is not None:
        rStyle = rPr.find(qn("w:rStyle"))
        if rStyle is not None:
            style = rStyle.get(qn("w:val"))

    return RunInfo(
        index=index,
        text=text,
        bold=_parse_bool_prop(rPr, "w:b"),
        italic=_parse_bool_prop(rPr, "w:i"),
        underline=underline,
        font_name=font_name,
        font_size=font_size,
        color=color,
        highlight_color=highlight_color,
        strike=_parse_bool_prop(rPr, "w:strike"),
        double_strike=_parse_bool_prop(rPr, "w:dstrike"),
        subscript=subscript,
        superscript=superscript,
        style=style,
        is_hyperlink=is_hyperlink,
        hyperlink_url=hyperlink_url,
        all_caps=_parse_bool_prop(rPr, "w:caps"),
        small_caps=_parse_bool_prop(rPr, "w:smallCaps"),
        hidden=_parse_bool_prop(rPr, "w:vanish"),
        emboss=_parse_bool_prop(rPr, "w:emboss"),
        imprint=_parse_bool_prop(rPr, "w:imprint"),
        outline=_parse_bool_prop(rPr, "w:outline"),
        shadow=_parse_bool_prop(rPr, "w:shadow"),
    )


def _build_runs_ooxml(p_el, doc_rels) -> list[RunInfo]:
    """Build runs list from a w:p element (pure OOXML)."""
    result = []
    idx = 0

    # Iterate direct children to maintain order (w:r and w:hyperlink)
    for child in p_el:
        tag = child.tag
        if tag == qn("w:r"):
            result.append(_build_run_info_ooxml(child, idx))
            idx += 1
        elif tag == qn("w:hyperlink"):
            # Get hyperlink URL from relationships
            rId = child.get(qn("r:id"))
            anchor = child.get(qn("w:anchor"))
            url = None
            if rId and doc_rels:
                rel = doc_rels.get(rId)
                if rel and rel.is_external:
                    url = rel.target
            elif anchor:
                url = f"#{anchor}"

            # Process runs inside hyperlink (use iter for nested runs in smartTag/sdt)
            for run_el in child.iter(qn("w:r")):
                result.append(
                    _build_run_info_ooxml(
                        run_el, idx, is_hyperlink=True, hyperlink_url=url
                    )
                )
                idx += 1

    return result


def build_runs(p_el, doc_rels) -> list[RunInfo]:
    """Build list of RunInfo for all runs in a paragraph.

    Args:
        p_el: lxml w:p element
        doc_rels: Relationships collection for resolving hyperlink targets
    """
    return _build_runs_ooxml(p_el, doc_rels)


def build_hyperlinks(pkg) -> list[HyperlinkInfo]:
    """Build list of all hyperlinks in the document.

    Args:
        pkg: WordPackage
    """
    doc_element = pkg.document_xml
    doc_rels = pkg.get_rels("/word/document.xml")
    return _build_hyperlinks_ooxml(doc_element, doc_rels)


def _build_hyperlinks_ooxml(doc_element, doc_rels) -> list[HyperlinkInfo]:
    """Build hyperlinks using pure OOXML."""
    result = []

    # Find all w:hyperlink elements in body (including in tables)
    for idx, hyperlink in enumerate(doc_element.iter(qn("w:hyperlink"))):
        # Get rId for external links
        rId = hyperlink.get(qn("r:id"))
        # Get anchor for internal bookmarks
        anchor = hyperlink.get(qn("w:anchor"))

        # Extract text from all runs
        text_parts = []
        for t in hyperlink.iter(qn("w:t")):
            if t.text:
                text_parts.append(t.text)
        text = "".join(text_parts)

        # Resolve URL from relationships
        address = ""
        is_external = False
        if rId:
            rel = doc_rels.get(rId)
            if rel:
                # Only use target as URL if it's an external relationship
                if rel.is_external:
                    address = rel.target
                    is_external = True
                # Non-external hyperlinks (rare) - rel.target is a part path, not URL

        # Build URL (external address or internal #fragment)
        if address:
            url = f"{address}#{anchor}" if anchor else address
        elif anchor:
            url = f"#{anchor}"
        else:
            url = ""

        result.append(
            HyperlinkInfo(
                index=idx,
                text=text,
                url=url,
                address=address,
                fragment=anchor or "",
                is_external=is_external,
            )
        )

    return result


def add_hyperlink(
    pkg,
    p_el,
    text: str,
    address: str = "",
    fragment: str = "",
) -> None:
    """Add hyperlink to paragraph.

    Args:
        pkg: WordPackage
        p_el: Paragraph element (w:p)
        text: Visible link text
        address: URL or file path (external link)
        fragment: Bookmark name (internal link) or URL anchor

    Either address or fragment must be provided.
    For external links: address="https://example.com"
    For internal links: address="", fragment="BookmarkName"
    For external with anchor: address="https://example.com", fragment="section"
    """
    if not text:
        raise ValueError("Hyperlink text cannot be empty")
    if not address and not fragment:
        raise ValueError("Either address or fragment must be provided")

    # Normalize fragment (strip leading #)
    if fragment.startswith("#"):
        fragment = fragment[1:]

    # Validate: fragment must not be empty after normalization for internal links
    if not address and not fragment:
        raise ValueError("Fragment cannot be empty for internal links")

    # Create the w:hyperlink element
    hyperlink = etree.Element(qn("w:hyperlink"))

    if address:
        # External link - create relationship
        full_url = f"{address}#{fragment}" if fragment else address
        r_id = pkg.relate_to(
            "/word/document.xml", full_url, RT.HYPERLINK, is_external=True
        )
        hyperlink.set(qn("r:id"), r_id)
    else:
        # Internal link - use anchor attribute
        hyperlink.set(qn("w:anchor"), fragment)

    # Set history attribute (standard Word behavior)
    hyperlink.set(qn("w:history"), "1")

    # Create run with text
    run = etree.Element(qn("w:r"))
    run_text = etree.Element(qn("w:t"))
    # Preserve whitespace if needed
    if text[:1].isspace() or text[-1:].isspace() or "  " in text:
        run_text.set(qn("xml:space"), "preserve")
    run_text.text = text
    run.append(run_text)
    hyperlink.append(run)

    # Append hyperlink to paragraph
    p_el.append(hyperlink)
    pkg.mark_xml_dirty("/word/document.xml")


# =============================================================================
# Style Management
# =============================================================================


def _build_styles_ooxml(styles_xml) -> list[StyleInfo]:
    """Build styles list from styles.xml element (pure OOXML)."""
    # Map OOXML type values to API strings
    type_map = {
        "paragraph": "paragraph",
        "character": "character",
        "table": "table",
        "numbering": "list",  # OOXML uses "numbering" for list styles
    }

    # First pass: build styleId -> name mapping for resolving references
    id_to_name = {}
    for style in styles_xml.findall(qn("w:style")):
        style_id = style.get(qn("w:styleId"))
        name_el = style.find(qn("w:name"))
        name = name_el.get(qn("w:val")) if name_el is not None else style_id
        if style_id:
            id_to_name[style_id] = name

    # Second pass: build StyleInfo list
    result = []
    for style in styles_xml.findall(qn("w:style")):
        style_id = style.get(qn("w:styleId"))
        style_type = style.get(qn("w:type"), "paragraph")
        # w:customStyle="1" indicates a custom/user-defined style
        # Absence means built-in (NOT w:default which means "default for type")
        is_builtin = style.get(qn("w:customStyle")) != "1"

        # Get name
        name_el = style.find(qn("w:name"))
        name = name_el.get(qn("w:val")) if name_el is not None else style_id

        # Get base style (w:basedOn)
        based_on = style.find(qn("w:basedOn"))
        base_style_id = based_on.get(qn("w:val")) if based_on is not None else None
        base_style = id_to_name.get(base_style_id) if base_style_id else None

        # Get next style (w:next)
        next_el = style.find(qn("w:next"))
        next_style_id = next_el.get(qn("w:val")) if next_el is not None else None
        next_style = id_to_name.get(next_style_id) if next_style_id else None
        # Don't report next style if it's same as current
        if next_style == name:
            next_style = None

        # Check hidden (w:semiHidden or w:hidden)
        hidden = (
            style.find(qn("w:semiHidden")) is not None
            or style.find(qn("w:hidden")) is not None
        )

        # Check quick style (w:qFormat)
        quick_style = style.find(qn("w:qFormat")) is not None

        result.append(
            StyleInfo(
                name=name,
                style_id=style_id,
                type=type_map.get(style_type, "unknown"),
                builtin=is_builtin,
                base_style=base_style,
                next_style=next_style,
                hidden=hidden,
                quick_style=quick_style,
            )
        )
    return result


def build_styles(pkg) -> list[StyleInfo]:
    """Build list of all styles in the document.

    Args:
        pkg: WordPackage
    """
    if not pkg.has_part("/word/styles.xml"):
        return []
    return _build_styles_ooxml(pkg.styles_xml)


def _get_style_format_ooxml(styles_xml, style_name: str) -> StyleFormatInfo:
    """Get style formatting from styles.xml (pure OOXML)."""
    # OOXML alignment values
    align_map = {
        "left": "left",
        "center": "center",
        "right": "right",
        "both": "justify",
    }
    type_map = {
        "paragraph": "paragraph",
        "character": "character",
        "table": "table",
        "numbering": "list",
    }

    # Find style by name (w:name/@w:val)
    style_el = None
    for s in styles_xml.findall(qn("w:style")):
        name_el = s.find(qn("w:name"))
        if name_el is not None and name_el.get(qn("w:val")) == style_name:
            style_el = s
            break

    if style_el is None:
        raise ValueError(f"Style not found: {style_name}")

    style_id = style_el.get(qn("w:styleId"))
    style_type = type_map.get(style_el.get(qn("w:type"), "paragraph"), "unknown")
    name_el = style_el.find(qn("w:name"))
    name = name_el.get(qn("w:val")) if name_el is not None else style_id

    # Extract run properties (w:rPr)
    rPr = style_el.find(qn("w:rPr"))
    font_name = None
    font_size = None
    bold = None
    italic = None
    color = None

    if rPr is not None:
        # Font name (w:rFonts/@w:ascii)
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is not None:
            font_name = rFonts.get(qn("w:ascii"))

        # Font size (w:sz/@w:val in half-points)
        sz = rPr.find(qn("w:sz"))
        if sz is not None:
            val = sz.get(qn("w:val"))
            font_size = int(val) / 2 if val else None  # half-points to points

        # Bold (w:b presence or @w:val != "0")
        b = rPr.find(qn("w:b"))
        if b is not None:
            val = b.get(qn("w:val"))
            bold = val != "0" if val else True

        # Italic (w:i)
        i = rPr.find(qn("w:i"))
        if i is not None:
            val = i.get(qn("w:val"))
            italic = val != "0" if val else True

        # Color (w:color/@w:val)
        color_el = rPr.find(qn("w:color"))
        if color_el is not None:
            val = color_el.get(qn("w:val"))
            if val and val != "auto":
                color = val.upper()

    # Extract paragraph properties (w:pPr)
    pPr = style_el.find(qn("w:pPr"))
    alignment = None
    left_indent = None
    space_before = None
    space_after = None
    line_spacing = None

    if pPr is not None:
        # Alignment (w:jc/@w:val)
        jc = pPr.find(qn("w:jc"))
        if jc is not None:
            alignment = align_map.get(jc.get(qn("w:val")))

        # Indentation (w:ind/@w:left in twips)
        ind = pPr.find(qn("w:ind"))
        if ind is not None:
            left_val = ind.get(qn("w:left"))
            if left_val:
                left_indent = int(left_val) / 1440  # twips to inches

        # Spacing (w:spacing/@w:before, @w:after in twips)
        # w:line interpretation depends on w:lineRule:
        # - "auto" (default): 240ths of a line (240 = single, 360 = 1.5)
        # - "exact" or "atLeast": twips (20 per point)
        spacing = pPr.find(qn("w:spacing"))
        if spacing is not None:
            before = spacing.get(qn("w:before"))
            after = spacing.get(qn("w:after"))
            line = spacing.get(qn("w:line"))
            line_rule = spacing.get(qn("w:lineRule"))
            if before:
                space_before = int(before) / 20  # twips to points
            if after:
                space_after = int(after) / 20  # twips to points
            if line:
                if line_rule in ("exact", "atLeast"):
                    line_spacing = int(line) / 20  # twips to points
                else:
                    line_spacing = int(line) / 240  # 240ths of a line

    return StyleFormatInfo(
        name=name,
        style_id=style_id,
        type=style_type,
        font_name=font_name,
        font_size=font_size,
        bold=bold,
        italic=italic,
        color=color,
        alignment=alignment,
        left_indent=left_indent,
        space_before=space_before,
        space_after=space_after,
        line_spacing=line_spacing,
    )


def get_style_format(pkg, style_name: str) -> StyleFormatInfo:
    """Get detailed formatting for a specific style.

    Args:
        pkg: WordPackage
        style_name: Name of the style to get formatting for
    """
    if not pkg.has_part("/word/styles.xml"):
        raise ValueError(f"No styles.xml found, cannot get style: {style_name}")
    return _get_style_format_ooxml(pkg.styles_xml, style_name)


def edit_style(pkg, style_name: str, fmt: dict) -> None:
    """Modify a style definition.

    Args:
        pkg: WordPackage
        style_name: Name or ID of the style to modify
        fmt: Dict of formatting properties to apply
    """
    if not pkg.has_part("/word/styles.xml"):
        raise ValueError("Document has no styles.xml")

    styles_xml = pkg.styles_xml

    # Find the style element by name or styleId
    style_el = None
    for style in styles_xml.findall(qn("w:style")):
        name_el = style.find(qn("w:name"))
        style_id = style.get(qn("w:styleId"))
        if style_id == style_name or (
            name_el is not None and name_el.get(qn("w:val")) == style_name
        ):
            style_el = style
            break

    if style_el is None:
        raise ValueError(f"Style '{style_name}' not found")

    # Get or create rPr (run properties) for font formatting
    rPr = style_el.find(qn("w:rPr"))
    if rPr is None and any(
        k in fmt for k in ("font_name", "font_size", "bold", "italic", "color")
    ):
        rPr = etree.SubElement(style_el, qn("w:rPr"))

    # Get or create pPr (paragraph properties)
    pPr = style_el.find(qn("w:pPr"))
    if pPr is None and any(
        k in fmt
        for k in (
            "alignment",
            "left_indent",
            "space_before",
            "space_after",
            "line_spacing",
        )
    ):
        pPr = etree.SubElement(style_el, qn("w:pPr"))

    # Apply font formatting
    if rPr is not None:
        if "font_name" in fmt:
            rFonts = rPr.find(qn("w:rFonts"))
            if rFonts is None:
                rFonts = etree.SubElement(rPr, qn("w:rFonts"))
            rFonts.set(qn("w:ascii"), fmt["font_name"])
            rFonts.set(qn("w:hAnsi"), fmt["font_name"])

        if "font_size" in fmt:
            sz = rPr.find(qn("w:sz"))
            if sz is None:
                sz = etree.SubElement(rPr, qn("w:sz"))
            sz.set(qn("w:val"), str(int(fmt["font_size"] * 2)))  # half-points

        if "bold" in fmt:
            b = rPr.find(qn("w:b"))
            if fmt["bold"]:
                if b is None:
                    etree.SubElement(rPr, qn("w:b"))
                else:
                    # Remove val="0" if present (explicit not-bold)
                    b.attrib.pop(qn("w:val"), None)
            elif b is not None:
                rPr.remove(b)

        if "italic" in fmt:
            i = rPr.find(qn("w:i"))
            if fmt["italic"]:
                if i is None:
                    etree.SubElement(rPr, qn("w:i"))
                else:
                    # Remove val="0" if present (explicit not-italic)
                    i.attrib.pop(qn("w:val"), None)
            elif i is not None:
                rPr.remove(i)

        if "color" in fmt:
            color = rPr.find(qn("w:color"))
            if color is None:
                color = etree.SubElement(rPr, qn("w:color"))
            color.set(qn("w:val"), fmt["color"].lstrip("#"))

    # Apply paragraph formatting
    if pPr is not None:
        if "alignment" in fmt:
            # Map API values to OOXML values (OOXML uses "both" for justify)
            align_to_ooxml = {
                "justify": "both",
                "left": "left",
                "center": "center",
                "right": "right",
            }
            jc = pPr.find(qn("w:jc"))
            if jc is None:
                jc = etree.SubElement(pPr, qn("w:jc"))
            jc.set(
                qn("w:val"),
                align_to_ooxml.get(fmt["alignment"].lower(), fmt["alignment"].lower()),
            )

        if "left_indent" in fmt:
            ind = pPr.find(qn("w:ind"))
            if ind is None:
                ind = etree.SubElement(pPr, qn("w:ind"))
            ind.set(
                qn("w:left"), str(int(fmt["left_indent"] * 1440))
            )  # inches to twips

        spacing = pPr.find(qn("w:spacing"))
        if spacing is None and any(
            k in fmt for k in ("space_before", "space_after", "line_spacing")
        ):
            spacing = etree.SubElement(pPr, qn("w:spacing"))

        if spacing is not None:
            if "space_before" in fmt:
                spacing.set(
                    qn("w:before"), str(int(fmt["space_before"] * 20))
                )  # points to twips
            if "space_after" in fmt:
                spacing.set(
                    qn("w:after"), str(int(fmt["space_after"] * 20))
                )  # points to twips
            if "line_spacing" in fmt:
                val = fmt["line_spacing"]
                if val < 5:  # Multiplier (e.g., 1.5, 2.0)
                    spacing.set(
                        qn("w:line"), str(int(val * 240))
                    )  # 240 = single spacing
                    spacing.set(qn("w:lineRule"), "auto")
                else:  # Absolute points
                    spacing.set(qn("w:line"), str(int(val * 20)))  # points to twips
                    spacing.set(qn("w:lineRule"), "exact")

    # Mark styles.xml as dirty so changes are saved
    pkg.mark_xml_dirty("/word/styles.xml")


def create_style(
    pkg,
    name: str,
    style_type: str = "paragraph",
    base_style: str = "Normal",
    formatting: dict | None = None,
) -> str:
    """Create a new custom style. Returns the style ID.

    Args:
        pkg: WordPackage
        name: Name for the new style
        style_type: 'paragraph', 'character', or 'table'
        base_style: Style to inherit from
        formatting: Optional dict of formatting properties
    """
    return _create_style_ooxml(pkg, name, style_type, base_style, formatting)


def _create_style_ooxml(
    pkg,
    name: str,
    style_type: str = "paragraph",
    base_style: str = "Normal",
    formatting: dict | None = None,
) -> str:
    """Create a new custom style via pure OOXML."""
    # Type mapping to OOXML type attribute
    type_map = {"paragraph": "paragraph", "character": "character", "table": "table"}
    ooxml_type = type_map[style_type.lower()]

    # Generate styleId from name (remove spaces, capitalize)
    style_id = name.replace(" ", "")

    if not pkg.has_part("/word/styles.xml"):
        raise ValueError("Document has no styles.xml")

    styles_xml = pkg.styles_xml

    # Create the style element
    style_el = etree.SubElement(
        styles_xml,
        qn("w:style"),
        {qn("w:type"): ooxml_type, qn("w:styleId"): style_id, qn("w:customStyle"): "1"},
    )

    # Add name element
    name_el = etree.SubElement(style_el, qn("w:name"))
    name_el.set(qn("w:val"), name)

    # Add basedOn if base_style exists
    if base_style:
        # Find base style to get its styleId
        base_style_id = None
        for style in styles_xml.findall(qn("w:style")):
            name_elem = style.find(qn("w:name"))
            sid = style.get(qn("w:styleId"))
            if sid == base_style or (
                name_elem is not None and name_elem.get(qn("w:val")) == base_style
            ):
                base_style_id = sid
                break

        if base_style_id:
            basedOn = etree.SubElement(style_el, qn("w:basedOn"))
            basedOn.set(qn("w:val"), base_style_id)

    pkg.mark_xml_dirty("/word/styles.xml")

    # Apply formatting if provided
    if formatting:
        edit_style(pkg, style_id, formatting)

    return style_id


def delete_style(pkg, style_name: str) -> bool:
    """Delete a custom style. Returns True if deleted, False if builtin or not found.

    Args:
        pkg: WordPackage
        style_name: Name or ID of the style to delete
    """
    return _delete_style_ooxml(pkg, style_name)


def _delete_style_ooxml(pkg, style_name: str) -> bool:
    """Delete a custom style via pure OOXML."""
    if not pkg.has_part("/word/styles.xml"):
        return False

    styles_xml = pkg.styles_xml

    # Find the style element
    style_el = None
    for style in styles_xml.findall(qn("w:style")):
        name_el = style.find(qn("w:name"))
        style_id = style.get(qn("w:styleId"))
        if style_id == style_name or (
            name_el is not None and name_el.get(qn("w:val")) == style_name
        ):
            style_el = style
            break

    if style_el is None:
        return False

    # Check if it's a custom style (w:customStyle="1" means custom)
    # Absence of customStyle or customStyle="0" means builtin
    custom_attr = style_el.get(qn("w:customStyle"))
    if custom_attr != "1":
        return False

    # Remove the style
    styles_xml.remove(style_el)
    pkg.mark_xml_dirty("/word/styles.xml")
    return True


# =============================================================================
# Paragraph Formatting
# =============================================================================

# Conversion constants
_TWIPS_PER_INCH = 1440
_TWIPS_PER_PT = 20  # 1 point = 20 twips

# OOXML alignment mapping (API -> w:jc/@w:val)
_ALIGNMENT_OOXML_MAP = {
    "left": "left",
    "center": "center",
    "right": "right",
    "justify": "both",
    "distribute": "distribute",
}


def _apply_paragraph_formatting_ooxml(p_el: etree._Element, fmt: dict) -> None:
    """Apply direct formatting to paragraph element (pure OOXML)."""
    from mcp_handley_lab.microsoft.word.ops.core import get_or_create_pPr

    pPr = get_or_create_pPr(p_el)

    # Alignment (w:jc)
    if "alignment" in fmt:
        alignment = fmt["alignment"].lower()
        jc = pPr.find(qn("w:jc"))
        if jc is None:
            jc = etree.SubElement(pPr, qn("w:jc"))
        jc.set(qn("w:val"), _ALIGNMENT_OOXML_MAP.get(alignment, alignment))

    # Indentation (w:ind) - values in twips
    if any(k in fmt for k in ("left_indent", "right_indent", "first_line_indent")):
        ind = pPr.find(qn("w:ind"))
        if ind is None:
            ind = etree.SubElement(pPr, qn("w:ind"))
        if "left_indent" in fmt:
            ind.set(qn("w:left"), str(int(fmt["left_indent"] * _TWIPS_PER_INCH)))
        if "right_indent" in fmt:
            ind.set(qn("w:right"), str(int(fmt["right_indent"] * _TWIPS_PER_INCH)))
        if "first_line_indent" in fmt:
            first = fmt["first_line_indent"]
            if first >= 0:
                ind.set(qn("w:firstLine"), str(int(first * _TWIPS_PER_INCH)))
                # Remove hanging if present
                if qn("w:hanging") in ind.attrib:
                    del ind.attrib[qn("w:hanging")]
            else:
                # Negative first_line_indent = hanging indent
                ind.set(qn("w:hanging"), str(int(-first * _TWIPS_PER_INCH)))
                # Remove firstLine if present
                if qn("w:firstLine") in ind.attrib:
                    del ind.attrib[qn("w:firstLine")]

    # Spacing (w:spacing) - before/after in twips
    if any(k in fmt for k in ("space_before", "space_after", "line_spacing")):
        spacing = pPr.find(qn("w:spacing"))
        if spacing is None:
            spacing = etree.SubElement(pPr, qn("w:spacing"))
        if "space_before" in fmt:
            spacing.set(qn("w:before"), str(int(fmt["space_before"] * _TWIPS_PER_PT)))
        if "space_after" in fmt:
            spacing.set(qn("w:after"), str(int(fmt["space_after"] * _TWIPS_PER_PT)))
        if "line_spacing" in fmt:
            ls = fmt["line_spacing"]
            if ls < 5:
                # Line spacing as multiple (e.g., 1.5 = 360 = 1.5 * 240)
                spacing.set(qn("w:line"), str(int(ls * 240)))
                spacing.set(qn("w:lineRule"), "auto")
            else:
                # Line spacing as points (exact)
                spacing.set(qn("w:line"), str(int(ls * _TWIPS_PER_PT)))
                spacing.set(qn("w:lineRule"), "exact")

    # Boolean paragraph properties
    if "keep_with_next" in fmt:
        keepNext = pPr.find(qn("w:keepNext"))
        if fmt["keep_with_next"]:
            if keepNext is None:
                etree.SubElement(pPr, qn("w:keepNext"))
        elif keepNext is not None:
            pPr.remove(keepNext)

    if "page_break_before" in fmt:
        pageBreakBefore = pPr.find(qn("w:pageBreakBefore"))
        if fmt["page_break_before"]:
            if pageBreakBefore is None:
                etree.SubElement(pPr, qn("w:pageBreakBefore"))
        elif pageBreakBefore is not None:
            pPr.remove(pageBreakBefore)

    # Apply run formatting to all runs
    for run_el in p_el.iter(qn("w:r")):
        for key, value in fmt.items():
            if key in _RUN_FORMAT_KEYS:
                _set_run_attr_ooxml(run_el, key, value)


def apply_paragraph_formatting(p_el, fmt: dict) -> None:
    """Apply direct formatting to paragraph (affects all runs).

    Args:
        p_el: lxml w:p element
        fmt: Dict of formatting properties to apply
    """
    _apply_paragraph_formatting_ooxml(p_el, fmt)


def _build_tab_stops_ooxml(p_el) -> list[TabStopInfo]:
    """Build tab stops from w:p element (pure OOXML)."""
    # OOXML alignment mapping (w:tab/@w:val)
    tab_align_ooxml = {
        "left": "left",
        "center": "center",
        "right": "right",
        "decimal": "decimal",
        "bar": "bar",
        "clear": "clear",  # Clears inherited tab
        "num": "left",  # Number tab (treated as left)
    }
    # OOXML leader mapping (w:tab/@w:leader)
    tab_leader_ooxml = {
        "none": "spaces",
        "dot": "dots",
        "hyphen": "heavy",
        "underscore": "heavy",
        "heavy": "heavy",
        "middleDot": "middle_dot",
    }

    result = []
    pPr = p_el.find(qn("w:pPr"))
    if pPr is not None:
        tabs = pPr.find(qn("w:tabs"))
        if tabs is not None:
            for tab in tabs.findall(qn("w:tab")):
                pos = tab.get(qn("w:pos"))
                val = tab.get(qn("w:val"))
                leader = tab.get(qn("w:leader"))

                if pos and val != "clear":
                    alignment = tab_align_ooxml.get(val, "left")
                    leader_str = tab_leader_ooxml.get(leader, "spaces")
                    result.append(
                        TabStopInfo(
                            position_inches=round(
                                int(pos) / 1440, 4
                            ),  # twips to inches
                            alignment=alignment,
                            leader=leader_str,
                        )
                    )
    return result


def _build_paragraph_format_ooxml(p_el) -> ParagraphFormatInfo:
    """Extract paragraph formatting from w:p element (pure OOXML)."""
    # OOXML alignment mapping (w:jc/@w:val)
    align_ooxml = {
        "left": "left",
        "center": "center",
        "right": "right",
        "both": "justify",
        "distribute": "justify",
    }

    alignment = None
    left_indent = None
    right_indent = None
    first_line_indent = None
    space_before = None
    space_after = None
    line_spacing = None
    keep_with_next = None
    page_break_before = None

    pPr = p_el.find(qn("w:pPr"))
    if pPr is not None:
        # Alignment (w:jc/@w:val)
        jc = pPr.find(qn("w:jc"))
        if jc is not None:
            alignment = align_ooxml.get(jc.get(qn("w:val")))

        # Indentation (w:ind)
        ind = pPr.find(qn("w:ind"))
        if ind is not None:
            left_val = ind.get(qn("w:left"))
            right_val = ind.get(qn("w:right"))
            first_line = ind.get(qn("w:firstLine"))
            hanging = ind.get(qn("w:hanging"))

            if left_val:
                left_indent = int(left_val) / 1440  # twips to inches
            if right_val:
                right_indent = int(right_val) / 1440
            if first_line:
                first_line_indent = int(first_line) / 1440
            elif hanging:
                first_line_indent = -int(hanging) / 1440  # Negative for hanging

        # Spacing (w:spacing)
        spacing = pPr.find(qn("w:spacing"))
        if spacing is not None:
            before = spacing.get(qn("w:before"))
            after = spacing.get(qn("w:after"))
            line = spacing.get(qn("w:line"))
            line_rule = spacing.get(qn("w:lineRule"))

            if before:
                space_before = int(before) / 20  # twips to points
            if after:
                space_after = int(after) / 20
            if line:
                if line_rule in ("exact", "atLeast"):
                    line_spacing = int(line) / 20  # twips to points
                else:
                    line_spacing = int(line) / 240  # 240ths to multiplier

        # Keep with next (w:keepNext)
        keep_next = pPr.find(qn("w:keepNext"))
        if keep_next is not None:
            val = keep_next.get(qn("w:val"))
            keep_with_next = val != "0" if val else True

        # Page break before (w:pageBreakBefore)
        pb_before = pPr.find(qn("w:pageBreakBefore"))
        if pb_before is not None:
            val = pb_before.get(qn("w:val"))
            page_break_before = val != "0" if val else True

    return ParagraphFormatInfo(
        alignment=alignment,
        left_indent=left_indent,
        right_indent=right_indent,
        first_line_indent=first_line_indent,
        space_before=space_before,
        space_after=space_after,
        line_spacing=line_spacing,
        keep_with_next=keep_with_next,
        page_break_before=page_break_before,
        tab_stops=_build_tab_stops_ooxml(p_el),
    )


def build_paragraph_format(p_el) -> ParagraphFormatInfo:
    """Extract paragraph formatting properties.

    Args:
        p_el: lxml w:p element
    """
    return _build_paragraph_format_ooxml(p_el)


# =============================================================================
# Tab Stops
# =============================================================================


def build_tab_stops(p_el) -> list[TabStopInfo]:
    """Build list of tab stops for a paragraph.

    Args:
        p_el: lxml w:p element
    """
    return _build_tab_stops_ooxml(p_el)


def add_tab_stop(
    p_el,
    position_inches: float,
    alignment: str = "left",
    leader: str = "spaces",
) -> None:
    """Add a tab stop to a paragraph.

    Args:
        p_el: lxml w:p element
        position_inches: Position from left margin (must be positive)
        alignment: Tab alignment - left, center, right, decimal
        leader: Tab leader character - spaces, dots, heavy, middle_dot
            Aliases: dot->dots, space->spaces, mid_dot->middle_dot
    """
    # Validate position
    if position_inches <= 0:
        raise ValueError(f"position_inches must be positive, got {position_inches}")

    # Alignment with validation
    valid_alignments = {"left", "center", "right", "decimal"}
    alignment_lower = alignment.lower()
    if alignment_lower not in valid_alignments:
        raise ValueError(
            f"Invalid alignment '{alignment}'. Valid: {list(valid_alignments)}"
        )

    # Leader with aliases and validation
    leader_aliases = {"dot": "dots", "space": "spaces", "mid_dot": "middle_dot"}
    leader_map_ooxml = {
        "spaces": "none",  # OOXML uses "none" for no leader
        "dots": "dot",
        "heavy": "heavy",
        "middle_dot": "middleDot",
    }
    leader_lower = leader_aliases.get(leader.lower(), leader.lower())
    if leader_lower not in leader_map_ooxml:
        raise ValueError(
            f"Invalid leader '{leader}'. Valid: {list(leader_map_ooxml.keys())}"
        )

    _add_tab_stop_ooxml(p_el, position_inches, alignment_lower, leader_lower)


def _add_tab_stop_ooxml(
    p_el: etree._Element,
    position_inches: float,
    alignment: str,
    leader: str,
) -> None:
    """Add a tab stop to a w:p element (pure OOXML).

    Creates w:tabs element in w:pPr if needed, adds w:tab child.
    """
    from mcp_handley_lab.microsoft.word.ops.core import get_or_create_pPr

    # OOXML leader mapping
    leader_map_ooxml = {
        "spaces": "none",
        "dots": "dot",
        "heavy": "heavy",
        "middle_dot": "middleDot",
    }

    pPr = get_or_create_pPr(p_el)

    # Get or create w:tabs
    tabs = pPr.find(qn("w:tabs"))
    if tabs is None:
        tabs = etree.SubElement(pPr, qn("w:tabs"))

    # Create w:tab element
    tab = etree.SubElement(tabs, qn("w:tab"))
    tab.set(qn("w:pos"), str(int(position_inches * 1440)))  # inches to twips
    tab.set(qn("w:val"), alignment)
    leader_val = leader_map_ooxml.get(leader, "none")
    if leader_val != "none":
        tab.set(qn("w:leader"), leader_val)


def clear_tab_stops(p_el) -> None:
    """Clear all tab stops from a paragraph.

    Args:
        p_el: lxml w:p element
    """
    pPr = p_el.find(qn("w:pPr"))
    if pPr is not None:
        tabs = pPr.find(qn("w:tabs"))
        if tabs is not None:
            pPr.remove(tabs)


# =============================================================================
# Run Formatting
# =============================================================================


def get_or_create_rPr(run_el: etree._Element) -> etree._Element:
    """Get or create w:rPr element for a run (pure OOXML)."""
    rPr = run_el.find(qn("w:rPr"))
    if rPr is None:
        rPr = etree.Element(qn("w:rPr"))
        run_el.insert(0, rPr)
    return rPr


# Mapping from API keys to OOXML elements (tag, value_attr)
# Boolean properties: just presence means True
_RUN_OOXML_BOOL = {
    "bold": "w:b",
    "italic": "w:i",
    "strike": "w:strike",
    "double_strike": "w:dstrike",
    "all_caps": "w:caps",
    "small_caps": "w:smallCaps",
    "hidden": "w:vanish",
    "emboss": "w:emboss",
    "imprint": "w:imprint",
    "outline": "w:outline",
    "shadow": "w:shadow",
}


def _set_run_attr_ooxml(run_el: etree._Element, key: str, value) -> None:
    """Set a run attribute on raw w:r element (pure OOXML)."""
    rPr = get_or_create_rPr(run_el)

    if key == "style":
        rStyle = rPr.find(qn("w:rStyle"))
        if rStyle is None:
            rStyle = etree.SubElement(rPr, qn("w:rStyle"))
        rStyle.set(qn("w:val"), str(value))

    elif key == "font_size":
        # w:sz/@w:val in half-points
        sz = rPr.find(qn("w:sz"))
        if sz is None:
            sz = etree.SubElement(rPr, qn("w:sz"))
        sz.set(qn("w:val"), str(int(float(value) * 2)))
        # Also set szCs for complex script
        szCs = rPr.find(qn("w:szCs"))
        if szCs is None:
            szCs = etree.SubElement(rPr, qn("w:szCs"))
        szCs.set(qn("w:val"), str(int(float(value) * 2)))

    elif key == "color":
        color_el = rPr.find(qn("w:color"))
        if color_el is None:
            color_el = etree.SubElement(rPr, qn("w:color"))
        color_el.set(qn("w:val"), str(value).lstrip("#").upper())

    elif key == "highlight_color":
        highlight = rPr.find(qn("w:highlight"))
        if highlight is None:
            highlight = etree.SubElement(rPr, qn("w:highlight"))
        highlight.set(qn("w:val"), str(value).lower())

    elif key == "underline":
        u = rPr.find(qn("w:u"))
        if value:
            if u is None:
                u = etree.SubElement(rPr, qn("w:u"))
            u.set(qn("w:val"), "single")
        elif u is not None:
            rPr.remove(u)

    elif key == "subscript":
        vertAlign = rPr.find(qn("w:vertAlign"))
        if value:
            if vertAlign is None:
                vertAlign = etree.SubElement(rPr, qn("w:vertAlign"))
            vertAlign.set(qn("w:val"), "subscript")
        elif vertAlign is not None and vertAlign.get(qn("w:val")) == "subscript":
            rPr.remove(vertAlign)

    elif key == "superscript":
        vertAlign = rPr.find(qn("w:vertAlign"))
        if value:
            if vertAlign is None:
                vertAlign = etree.SubElement(rPr, qn("w:vertAlign"))
            vertAlign.set(qn("w:val"), "superscript")
        elif vertAlign is not None and vertAlign.get(qn("w:val")) == "superscript":
            rPr.remove(vertAlign)

    elif key == "font_name":
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            rFonts = etree.SubElement(rPr, qn("w:rFonts"))
        rFonts.set(qn("w:ascii"), str(value))
        rFonts.set(qn("w:hAnsi"), str(value))

    elif key in _RUN_OOXML_BOOL:
        tag = qn(_RUN_OOXML_BOOL[key])
        el = rPr.find(tag)
        if value is None:
            # Clear/unset: remove the element to inherit
            if el is not None:
                rPr.remove(el)
        elif value:
            # Set to true (presence without val, or val="1")
            if el is None:
                el = etree.SubElement(rPr, tag)
            # Remove any explicit false value
            if el.get(qn("w:val")) == "0":
                del el.attrib[qn("w:val")]
        else:
            # Explicitly set to false with w:val="0"
            if el is None:
                el = etree.SubElement(rPr, tag)
            el.set(qn("w:val"), "0")


def _resolve_run_by_index_ooxml(p_el: etree._Element, run_index: int) -> etree._Element:
    """Resolve run by index in raw w:p element (pure OOXML).

    Iterates all w:r elements (including those inside w:hyperlink) in document order.
    """
    return list(p_el.iter(qn("w:r")))[run_index]


def _set_run_text_ooxml(run_el: etree._Element, text: str) -> None:
    """Set text of a run element (pure OOXML).

    Clears existing text elements and creates a single w:t with the new text.
    """
    # Remove existing text elements
    for t in list(run_el.findall(qn("w:t"))):
        run_el.remove(t)
    # Create new text element
    t = etree.SubElement(run_el, qn("w:t"))
    t.text = text
    if text.startswith(" ") or text.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def edit_run_text(p_el, run_index: int, text: str) -> None:
    """Edit run text.

    Args:
        p_el: lxml w:p element
        run_index: Index of the run to edit
        text: New text for the run
    """
    run_el = _resolve_run_by_index_ooxml(p_el, run_index)
    _set_run_text_ooxml(run_el, text)


def edit_run_formatting(p_el, run_index: int, fmt: dict) -> None:
    """Apply formatting to a specific run.

    Args:
        p_el: lxml w:p element
        run_index: Index of the run to format
        fmt: Dict of formatting properties to apply
    """
    run_el = _resolve_run_by_index_ooxml(p_el, run_index)
    for key, value in fmt.items():
        _set_run_attr_ooxml(run_el, key, value)
