"""List and numbering operations.

Contains functions for:
- Reading list/numbering properties
- Modifying list levels (promote/demote)
- Restarting numbering
- Removing list formatting

Pure OOXML implementation - works directly with lxml elements.
"""

from __future__ import annotations

from lxml import etree
from lxml.etree import ElementBase as _LxmlElementBase

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.ops.core import mark_dirty

# Namespace for numbering XPath queries
_NUMBERING_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


# =============================================================================
# Helper Functions
# =============================================================================


def _get_numbering_xml(pkg) -> etree._Element | None:
    """Get numbering.xml root from WordPackage."""
    return pkg.numbering_xml


def _mark_numbering_dirty(pkg) -> None:
    """Mark numbering.xml as dirty."""
    pkg.mark_xml_dirty("/word/numbering.xml")


# =============================================================================
# Numbering Part Helpers
# =============================================================================


def _numbering_xpath(element: etree._Element, expr: str) -> list:
    """Execute XPath on element using Word namespace."""
    return _LxmlElementBase.xpath(element, expr, namespaces=_NUMBERING_NS)


def _resolve_abstract_num_id(pkg, num_id: int) -> int | None:
    """Resolve num_id to abstractNumId via numbering.xml.

    Args:
        pkg: WordPackage
        num_id: The numId to resolve

    Returns None if num_id not found.
    """
    numbering_xml = _get_numbering_xml(pkg)
    if numbering_xml is None:
        return None

    for num_el in _numbering_xpath(numbering_xml, ".//w:num"):
        if num_el.get(qn("w:numId")) == str(num_id):
            abstract_ref = num_el.find(qn("w:abstractNumId"))
            if abstract_ref is not None:
                return int(abstract_ref.get(qn("w:val")))
    return None


def _resolve_level_format(
    pkg, abstract_num_id: int, ilvl: int
) -> dict[str, str | int | None]:
    """Get level format info (numFmt, lvlText, start) from abstractNum.

    Args:
        pkg: WordPackage
        abstract_num_id: The abstractNumId
        ilvl: Indentation level (0-8)

    Returns dict with keys: format_type, level_text, start_value.
    """
    numbering_xml = _get_numbering_xml(pkg)
    if numbering_xml is None:
        return {"format_type": None, "level_text": None, "start_value": None}

    for abs_num in _numbering_xpath(numbering_xml, ".//w:abstractNum"):
        if abs_num.get(qn("w:abstractNumId")) == str(abstract_num_id):
            for lvl in _numbering_xpath(abs_num, ".//w:lvl"):
                if lvl.get(qn("w:ilvl")) == str(ilvl):
                    num_fmt = lvl.find(qn("w:numFmt"))
                    lvl_text = lvl.find(qn("w:lvlText"))
                    start = lvl.find(qn("w:start"))
                    return {
                        "format_type": num_fmt.get(qn("w:val"))
                        if num_fmt is not None
                        else None,
                        "level_text": lvl_text.get(qn("w:val"))
                        if lvl_text is not None
                        else None,
                        "start_value": int(start.get(qn("w:val")))
                        if start is not None
                        else None,
                    }
    return {"format_type": None, "level_text": None, "start_value": None}


# =============================================================================
# List Info Reading
# =============================================================================


def get_list_info(pkg, p_el: etree._Element) -> dict | None:
    """Get list properties for a paragraph element.

    Args:
        pkg: WordPackage
        p_el: w:p element

    Returns None if paragraph is not in a list.
    Returns dict with: num_id, abstract_num_id, level, format_type, start_value, level_text.
    """
    pPr = p_el.find(qn("w:pPr"))
    if pPr is None:
        return None

    num_pr_elem = pPr.find(qn("w:numPr"))
    if num_pr_elem is None:
        return None

    ilvl_el = num_pr_elem.find(qn("w:ilvl"))
    num_id_el = num_pr_elem.find(qn("w:numId"))

    if num_id_el is None:
        return None

    num_id = int(num_id_el.get(qn("w:val")))
    # numId of 0 means "no list"
    if num_id == 0:
        return None

    ilvl = int(ilvl_el.get(qn("w:val"))) if ilvl_el is not None else 0

    abstract_num_id = _resolve_abstract_num_id(pkg, num_id)
    level_info = (
        _resolve_level_format(pkg, abstract_num_id, ilvl)
        if abstract_num_id is not None
        else {}
    )

    return {
        "num_id": num_id,
        "abstract_num_id": abstract_num_id,
        "level": ilvl,
        "format_type": level_info.get("format_type"),
        "start_value": level_info.get("start_value"),
        "level_text": level_info.get("level_text"),
    }


# =============================================================================
# List Level Manipulation
# =============================================================================


def _ensure_pPr(p_el: etree._Element) -> etree._Element:
    """Ensure paragraph has pPr element, create if needed.

    Pure OOXML: Works with lxml elements.
    """
    pPr = p_el.find(qn("w:pPr"))
    if pPr is None:
        pPr = etree.Element(qn("w:pPr"))
        p_el.insert(0, pPr)
    return pPr


def _ensure_numPr(pPr: etree._Element) -> etree._Element:
    """Ensure pPr has numPr element, create if needed.

    Pure OOXML: Works with lxml elements.
    """
    numPr = pPr.find(qn("w:numPr"))
    if numPr is None:
        numPr = etree.Element(qn("w:numPr"))
        pPr.insert(0, numPr)
    return numPr


def _require_numPr(p_el: etree._Element) -> etree._Element:
    """Get numPr element from paragraph, raise if not in a list.

    Validates: has pPr, has numPr, has numId != "0".
    """
    pPr = p_el.find(qn("w:pPr"))
    numPr = pPr.find(qn("w:numPr")) if pPr is not None else None
    if numPr is None:
        raise ValueError("Paragraph is not in a list")
    num_id_el = numPr.find(qn("w:numId"))
    if num_id_el is None or num_id_el.get(qn("w:val")) == "0":
        raise ValueError("Paragraph is not in a list")
    return numPr


def _ensure_ilvl(numPr: etree._Element) -> etree._Element:
    """Get or create ilvl element in numPr."""
    ilvl_el = numPr.find(qn("w:ilvl"))
    if ilvl_el is None:
        ilvl_el = etree.Element(qn("w:ilvl"))
        numPr.insert(0, ilvl_el)
    return ilvl_el


def set_list_level(pkg, p_el: etree._Element, level: int) -> None:
    """Set list indentation level (0-8).

    Args:
        pkg: WordPackage
        p_el: w:p element
        level: List level (0-8)

    Only works on paragraphs already in a list.
    Raises ValueError if paragraph is not in a list.
    """
    numPr = _require_numPr(p_el)
    _ensure_ilvl(numPr).set(qn("w:val"), str(level))
    mark_dirty(pkg)


def promote_list_item(pkg, p_el: etree._Element) -> int:
    """Decrease level (move left). Min level is 0. Returns new level.

    Args:
        pkg: WordPackage
        p_el: w:p element
    """
    numPr = _require_numPr(p_el)
    ilvl_el = numPr.find(qn("w:ilvl"))
    current = int(ilvl_el.get(qn("w:val"))) if ilvl_el is not None else 0
    new_level = max(0, current - 1)
    _ensure_ilvl(numPr).set(qn("w:val"), str(new_level))
    mark_dirty(pkg)
    return new_level


def demote_list_item(pkg, p_el: etree._Element) -> int:
    """Increase level (move right). Max level is 8. Returns new level.

    Args:
        pkg: WordPackage
        p_el: w:p element
    """
    numPr = _require_numPr(p_el)
    ilvl_el = numPr.find(qn("w:ilvl"))
    current = int(ilvl_el.get(qn("w:val"))) if ilvl_el is not None else 0
    new_level = min(8, current + 1)
    _ensure_ilvl(numPr).set(qn("w:val"), str(new_level))
    mark_dirty(pkg)
    return new_level


# =============================================================================
# Numbering Restart
# =============================================================================


def _get_max_num_id(pkg) -> int:
    """Get the maximum numId currently in use.

    Args:
        pkg: WordPackage
    """
    numbering_xml = _get_numbering_xml(pkg)
    if numbering_xml is None:
        return 0

    max_id = 0
    for num_el in _numbering_xpath(numbering_xml, ".//w:num"):
        num_id = int(num_el.get(qn("w:numId"), "0"))
        max_id = max(max_id, num_id)
    return max_id


def restart_numbering(pkg, p_el: etree._Element, start_value: int = 1) -> int:
    """Restart numbering from given value.

    Args:
        pkg: WordPackage
        p_el: w:p element
        start_value: Number to restart from (default 1)

    Creates a new w:num in numbering.xml referencing the same abstractNum,
    with lvlOverride/startOverride, then updates the paragraph's numId.

    Returns the new numId.
    Raises ValueError if paragraph is not in a list.
    """
    list_info = get_list_info(pkg, p_el)
    if list_info is None:
        raise ValueError("Paragraph is not in a list")

    abstract_num_id = list_info["abstract_num_id"]
    ilvl = list_info["level"]

    if abstract_num_id is None:
        raise ValueError("Cannot determine abstract numbering definition")

    numbering_xml = _get_numbering_xml(pkg)
    if numbering_xml is None:
        raise ValueError("Document has no numbering part")

    new_num_id = _get_max_num_id(pkg) + 1

    new_num = etree.Element(qn("w:num"))
    new_num.set(qn("w:numId"), str(new_num_id))

    abstract_num_id_el = etree.SubElement(new_num, qn("w:abstractNumId"))
    abstract_num_id_el.set(qn("w:val"), str(abstract_num_id))

    lvl_override = etree.SubElement(new_num, qn("w:lvlOverride"))
    lvl_override.set(qn("w:ilvl"), str(ilvl))

    start_override = etree.SubElement(lvl_override, qn("w:startOverride"))
    start_override.set(qn("w:val"), str(start_value))

    numbering_xml.append(new_num)
    _mark_numbering_dirty(pkg)

    pPr = p_el.find(qn("w:pPr"))
    numPr = pPr.find(qn("w:numPr"))
    num_id_el = numPr.find(qn("w:numId"))
    num_id_el.set(qn("w:val"), str(new_num_id))
    mark_dirty(pkg)  # Also mark document.xml dirty

    return new_num_id


# =============================================================================
# Remove List Formatting
# =============================================================================


def remove_list_formatting(pkg, p_el: etree._Element) -> None:
    """Remove list formatting from paragraph (removes w:numPr).

    Args:
        pkg: WordPackage
        p_el: w:p element
    """
    pPr = p_el.find(qn("w:pPr"))
    if pPr is None:
        return

    numPr = pPr.find(qn("w:numPr"))
    if numPr is not None:
        pPr.remove(numPr)
        mark_dirty(pkg)


# =============================================================================
# Add List Item
# =============================================================================


def add_to_list(
    pkg,
    reference_p_el: etree._Element,
    text: str,
    position: str = "after",
    level: int | None = None,
) -> etree._Element:
    """Add a new paragraph to an existing list.

    Args:
        pkg: WordPackage
        reference_p_el: w:p element that's already in a list
        text: Text for the new list item (plain text, no newlines)
        position: 'before' or 'after' the reference paragraph
        level: List level (0-8), defaults to same as reference

    Returns the new w:p element.
    Raises ValueError if reference paragraph is not in a list (no w:numPr).
    """
    # Get list info from reference
    list_info = get_list_info(pkg, reference_p_el)
    if list_info is None:
        raise ValueError(
            "Paragraph has no explicit w:numPr; style-based lists are not supported"
        )

    # Determine level
    if level is None:
        level = list_info["level"]

    # Create new paragraph using reference's tag for namespace context
    new_p = etree.Element(reference_p_el.tag)
    pPr = etree.SubElement(new_p, qn("w:pPr"))
    numPr = etree.SubElement(pPr, qn("w:numPr"))
    ilvl_el = etree.SubElement(numPr, qn("w:ilvl"))
    ilvl_el.set(qn("w:val"), str(level))
    num_id_el = etree.SubElement(numPr, qn("w:numId"))
    num_id_el.set(qn("w:val"), str(list_info["num_id"]))

    # Add text run
    r = etree.SubElement(new_p, qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = text
    # Preserve whitespace if needed
    if text and (text[0].isspace() or text[-1].isspace()):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    # Insert relative to reference
    if position == "before":
        reference_p_el.addprevious(new_p)
    else:
        reference_p_el.addnext(new_p)

    mark_dirty(pkg)
    return new_p
