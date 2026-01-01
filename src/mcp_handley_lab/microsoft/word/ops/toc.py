"""Table of Contents operations.

Contains functions for:
- Checking if document has a TOC
- Getting TOC metadata
- Inserting TOC fields
- Marking TOC for update

Pure OOXML implementation - works directly with lxml elements.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from lxml import etree
from lxml.etree import ElementBase as _LxmlElementBase

from mcp_handley_lab.microsoft.word.constants import qn

if TYPE_CHECKING:
    pass

from mcp_handley_lab.microsoft.word.ops.core import (
    count_occurrence,
    get_paragraph_text,
    make_block_id,
    mark_dirty,
    paragraph_kind_and_level,
    resolve_target,
)

# =============================================================================
# Duck-Typed Helpers
# =============================================================================


_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _toc_xpath(element: etree._Element, expr: str) -> list:
    """XPath using ElementBase.xpath for namespace compatibility."""
    return _LxmlElementBase.xpath(element, expr, namespaces=_NS)


def _get_document_xml(pkg) -> etree._Element:
    """Get document.xml root from WordPackage."""
    return pkg.document_xml


# =============================================================================
# TOC Detection and Info
# =============================================================================


def has_toc(pkg) -> bool:
    """Check if document has a Table of Contents.

    Args:
        pkg: WordPackage

    Searches for:
    1. w:instrText containing "TOC" (complex field)
    2. w:fldSimple[@w:instr] starting with "TOC"
    """
    # Check for complex field with TOC
    for instr in _toc_xpath(_get_document_xml(pkg), ".//w:instrText"):
        if instr.text and "TOC" in instr.text.upper():
            return True

    # Check for simple field with TOC
    for fld in _toc_xpath(_get_document_xml(pkg), ".//w:fldSimple"):
        instr = fld.get(qn("w:instr")) or ""
        if instr.strip().upper().startswith("TOC"):
            return True

    return False


def get_toc_info(pkg) -> dict:
    """Get TOC metadata if exists.

    Args:
        pkg: WordPackage

    Parses heading levels from field switches (e.g., \\o "1-3").
    Returns dict compatible with TOCInfo model.
    """
    result = {
        "exists": False,
        "heading_levels": "1-3",
        "entry_count": 0,
        "block_id": None,
        "has_sdt_wrapper": False,
        "is_dirty": False,
    }

    # Find TOC field instruction
    toc_instr = None
    toc_para = None
    is_dirty = False

    # Check for complex field with TOC
    for instr_el in _toc_xpath(_get_document_xml(pkg), ".//w:instrText"):
        if instr_el.text and "TOC" in instr_el.text.upper():
            toc_instr = instr_el.text
            # Find containing paragraph
            parent = instr_el.getparent()
            while parent is not None:
                if parent.tag == qn("w:p"):
                    toc_para = parent
                    break
                parent = parent.getparent()

            # Check for dirty flag on fldChar begin
            if toc_para is not None:
                for fld_char in _toc_xpath(toc_para, ".//w:fldChar"):
                    if fld_char.get(qn("w:fldCharType")) == "begin":
                        dirty = fld_char.get(qn("w:dirty"))
                        is_dirty = dirty == "true" or dirty == "1"
                        break
            break

    # Check for simple field with TOC
    if not toc_instr:
        for fld in _toc_xpath(_get_document_xml(pkg), ".//w:fldSimple"):
            instr = fld.get(qn("w:instr")) or ""
            if instr.strip().upper().startswith("TOC"):
                toc_instr = instr
                # Find containing paragraph
                parent = fld.getparent()
                while parent is not None:
                    if parent.tag == qn("w:p"):
                        toc_para = parent
                        break
                    parent = parent.getparent()
                # Check dirty on simple field
                dirty = fld.get(qn("w:dirty"))
                is_dirty = dirty == "true" or dirty == "1"
                break

    if not toc_instr:
        return result

    result["exists"] = True
    result["is_dirty"] = is_dirty

    # Parse heading levels from \o switch
    levels_match = re.search(r'\\o\s*"(\d+-\d+)"', toc_instr)
    if levels_match:
        result["heading_levels"] = levels_match.group(1)

    # Get block ID for the TOC paragraph
    if toc_para is not None:
        kind, _ = paragraph_kind_and_level(toc_para)
        text = get_paragraph_text(toc_para)
        occurrence = count_occurrence(pkg, kind, text, toc_para)
        result["block_id"] = make_block_id(kind, text, occurrence)

        # Check for SDT wrapper
        parent = toc_para.getparent()
        if parent is not None and parent.tag == qn("w:sdt"):
            result["has_sdt_wrapper"] = True

    return result


# =============================================================================
# TOC Insertion
# =============================================================================


def _create_run_with_element(child: etree._Element) -> etree._Element:
    """Create w:r containing a single child element.

    Pure OOXML helper.
    """
    r = etree.Element(qn("w:r"))
    r.append(child)
    return r


def _create_text_run(text: str) -> etree._Element:
    """Create w:r containing text.

    Pure OOXML helper.
    """
    r = etree.Element(qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = text
    return r


def insert_toc(
    pkg,
    target_id: str,
    position: str = "before",
    heading_levels: str = "1-3",
) -> str:
    """Insert TOC field at position. Returns block ID.

    Args:
        pkg: WordPackage

    Field code: TOC \\o "1-3" \\h \\z \\u
    - \\o: heading levels
    - \\h: hyperlinks
    - \\z: hide tab leaders and page numbers in Web view
    - \\u: use applied paragraph outline level

    Sets w:dirty="true" so Word updates on open.
    """
    target = resolve_target(pkg, target_id)

    # Create paragraph element for TOC
    toc_el = etree.Element(qn("w:p"))

    # Build field instruction
    instr = f' TOC \\\\o "{heading_levels}" \\\\h \\\\z \\\\u '

    # Run 1: fldChar begin (with dirty flag)
    fld_char_begin = etree.Element(qn("w:fldChar"))
    fld_char_begin.set(qn("w:fldCharType"), "begin")
    fld_char_begin.set(qn("w:dirty"), "true")
    toc_el.append(_create_run_with_element(fld_char_begin))

    # Run 2: instrText
    instr_text = etree.Element(qn("w:instrText"))
    instr_text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instr_text.text = instr
    toc_el.append(_create_run_with_element(instr_text))

    # Run 3: fldChar separate
    fld_char_sep = etree.Element(qn("w:fldChar"))
    fld_char_sep.set(qn("w:fldCharType"), "separate")
    toc_el.append(_create_run_with_element(fld_char_sep))

    # Run 4: result text (placeholder - Word will replace)
    toc_el.append(_create_text_run("Update this field to generate Table of Contents"))

    # Run 5: fldChar end
    fld_char_end = etree.Element(qn("w:fldChar"))
    fld_char_end.set(qn("w:fldCharType"), "end")
    toc_el.append(_create_run_with_element(fld_char_end))

    # Move paragraph to correct position
    if target.base_kind == "table":
        target_el = target.base_el  # w:tbl element
    else:
        target_el = target.leaf_el

    if position == "before":
        target_el.addprevious(toc_el)
    else:
        target_el.addnext(toc_el)

    # Mark document.xml as modified for WordPackage
    mark_dirty(pkg)

    # Generate block ID
    text = get_paragraph_text(toc_el)
    occurrence = count_occurrence(pkg, "paragraph", text, toc_el)
    return make_block_id("paragraph", text, occurrence)


# =============================================================================
# TOC Update
# =============================================================================


def update_toc_field(pkg) -> bool:
    """Set dirty flag on TOC field begin marker.

    Args:
        pkg: WordPackage

    Sets w:dirty="true" on w:fldChar[@w:fldCharType="begin"] for complex fields,
    or w:dirty="true" on w:fldSimple for simple fields.
    Word recalculates field values when document opens.

    Returns True if TOC was found and updated, False otherwise.
    """
    # Find complex field with TOC
    for instr_el in _toc_xpath(_get_document_xml(pkg), ".//w:instrText"):
        if instr_el.text and "TOC" in instr_el.text.upper():
            # Find containing paragraph and fldChar begin
            parent = instr_el.getparent()
            while parent is not None:
                if parent.tag == qn("w:p"):
                    # Find fldChar begin in this paragraph
                    for fld_char in _toc_xpath(parent, ".//w:fldChar"):
                        if fld_char.get(qn("w:fldCharType")) == "begin":
                            fld_char.set(qn("w:dirty"), "true")
                            mark_dirty(pkg)
                            return True
                    break
                parent = parent.getparent()
            break

    # Find simple field with TOC
    for fld in _toc_xpath(_get_document_xml(pkg), ".//w:fldSimple"):
        instr = fld.get(qn("w:instr")) or ""
        if instr.strip().upper().startswith("TOC"):
            fld.set(qn("w:dirty"), "true")
            mark_dirty(pkg)
            return True

    return False
