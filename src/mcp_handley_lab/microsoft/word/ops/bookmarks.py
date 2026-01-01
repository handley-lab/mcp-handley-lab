"""Bookmark and caption operations.

Contains functions for:
- Listing and adding bookmarks
- Inserting cross-references
- Creating and listing captions

Pure OOXML implementation - works directly with lxml elements.
"""

from __future__ import annotations

import re

from lxml import etree

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.ops.core import (
    count_occurrence,
    get_paragraph_style,
    get_paragraph_text,
    iter_body_blocks,
    make_block_id,
    mark_dirty,
    paragraph_kind_and_level,
    resolve_target,
)
from mcp_handley_lab.microsoft.word.ops.headers import insert_field
from mcp_handley_lab.microsoft.word.ops.revisions import _rev_xpath

# =============================================================================
# Constants
# =============================================================================

# Reserved bookmark prefixes (used internally by Word)
_RESERVED_BOOKMARK_PREFIXES = ("_Toc", "_Ref", "_Hlt", "_GoBack")


# =============================================================================
# Helper Functions
# =============================================================================


def _get_document_xml(pkg) -> etree._Element:
    """Get document.xml root from WordPackage."""
    return pkg.document_xml


def _get_next_bookmark_id(pkg) -> int:
    """Get next available bookmark ID.

    Args:
        pkg: WordPackage
    """
    doc_xml = _get_document_xml(pkg)
    max_id = 0
    for start in _rev_xpath(doc_xml, "//w:bookmarkStart"):
        bm_id = start.get(qn("w:id"))
        if bm_id:
            max_id = max(max_id, int(bm_id))
    return max_id + 1


def _is_reserved_bookmark(name: str) -> bool:
    """Check if bookmark name is a reserved Word internal bookmark."""
    return any(name.startswith(prefix) for prefix in _RESERVED_BOOKMARK_PREFIXES)


# =============================================================================
# Bookmark Operations
# =============================================================================


def build_bookmarks(pkg) -> list[dict]:
    """List all bookmarks in document.

    Args:
        pkg: WordPackage

    Skips reserved bookmarks (_Toc*, _Ref*, etc.) used internally by Word.
    Returns list of dicts with: id, name, block_id.
    """
    doc_xml = _get_document_xml(pkg)
    results = []
    seen_names = set()

    for start in _rev_xpath(doc_xml, "//w:body//w:bookmarkStart"):
        bm_id = start.get(qn("w:id"))
        bm_name = start.get(qn("w:name"))

        if not bm_id or not bm_name:
            continue

        # Skip reserved bookmarks
        if _is_reserved_bookmark(bm_name):
            continue

        # Skip duplicates
        if bm_name in seen_names:
            continue
        seen_names.add(bm_name)

        # Find containing paragraph for block_id
        block_id = ""
        parent = start.getparent()
        while parent is not None:
            if parent.tag == qn("w:p"):
                p_el = parent
                kind, _ = paragraph_kind_and_level(p_el)
                text = get_paragraph_text(p_el)
                occurrence = count_occurrence(pkg, kind, text, p_el)
                block_id = make_block_id(kind, text, occurrence)
                break
            parent = parent.getparent()

        results.append(
            {
                "id": int(bm_id),
                "name": bm_name,
                "block_id": block_id,
            }
        )

    return results


def add_bookmark(pkg, name: str, p_el: etree._Element) -> int:
    """Add bookmark at paragraph. Returns bookmark ID.

    Args:
        pkg: WordPackage
        name: Bookmark name
        p_el: w:p element

    """
    bm_id = _get_next_bookmark_id(pkg)

    # Insert bookmarkStart at beginning of paragraph
    bookmark_start = etree.Element(qn("w:bookmarkStart"))
    bookmark_start.set(qn("w:id"), str(bm_id))
    bookmark_start.set(qn("w:name"), name)
    p_el.insert(0, bookmark_start)

    # Insert bookmarkEnd at end of paragraph
    bookmark_end = etree.Element(qn("w:bookmarkEnd"))
    bookmark_end.set(qn("w:id"), str(bm_id))
    p_el.append(bookmark_end)

    # Mark document.xml as modified for WordPackage
    mark_dirty(pkg)

    return bm_id


# =============================================================================
# Cross-References
# =============================================================================


def insert_cross_reference(
    p_el: etree._Element, bookmark_name: str, ref_type: str = "text"
) -> None:
    """Insert cross-reference field.

    Pure OOXML: Takes w:p element.

    ref_type options:
    - 'text': REF <bookmark> field (bookmark text)
    - 'number': REF <bookmark> \\r field (paragraph number)
    - 'page': PAGEREF <bookmark> field (page number)

    Bookmark names are case-sensitive in field instructions.
    """
    if ref_type == "text":
        instr = f"REF {bookmark_name} \\h"
    elif ref_type == "number":
        instr = f"REF {bookmark_name} \\r \\h"
    elif ref_type == "page":
        instr = f"PAGEREF {bookmark_name} \\h"
    else:
        raise ValueError(
            f"Unknown ref_type: {ref_type}. Use 'text', 'number', or 'page'"
        )

    insert_field(p_el, instr, uppercase=False, placeholder="[ref]")


# =============================================================================
# Captions
# =============================================================================


def _create_run_with_text(text: str) -> etree._Element:
    """Create a w:r element containing text.

    Pure OOXML helper.
    """
    r = etree.Element(qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = text
    # Preserve spaces
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return r


def insert_caption(
    pkg,
    target_id: str,
    label: str,
    caption_text: str,
    position: str = "below",
) -> str:
    """Insert caption for table/image. Returns caption block ID.

    Args:
        pkg: WordPackage

    Creates paragraph with:
    1. Style "Caption"
    2. Label text (e.g., "Figure ")
    3. SEQ <label> field
    4. Separator (": ")
    5. Caption text

    Args:
        pkg: Package to modify
        target_id: Block ID of element to caption
        label: Caption label (e.g., "Figure", "Table")
        caption_text: Text after the number
        position: "below" or "above" the target element
    """
    target = resolve_target(pkg, target_id)

    # Create caption paragraph element
    caption_el = etree.Element(qn("w:p"))

    # Add paragraph properties with Caption style
    pPr = etree.SubElement(caption_el, qn("w:pPr"))
    pStyle = etree.SubElement(pPr, qn("w:pStyle"))
    pStyle.set(qn("w:val"), "Caption")

    # Add label text run
    caption_el.append(_create_run_with_text(f"{label} "))

    # Add SEQ field for auto-numbering
    insert_field(caption_el, f"SEQ {label}", uppercase=False)

    # Add separator and caption text run
    caption_el.append(_create_run_with_text(f": {caption_text}"))

    # Move paragraph to correct position
    # For tables, caption should be relative to the table itself
    if target.base_kind == "table":
        target_el = target.base_el  # w:tbl element
    else:
        target_el = target.leaf_el

    if position == "above":
        target_el.addprevious(caption_el)
    else:  # below
        target_el.addnext(caption_el)

    # Mark document.xml as modified for WordPackage
    mark_dirty(pkg)

    # Generate block ID for the caption
    text = get_paragraph_text(caption_el)
    occurrence = count_occurrence(pkg, "paragraph", text, caption_el)
    return make_block_id("paragraph", text, occurrence)


def build_captions(pkg) -> list[dict]:
    """List all captions (paragraphs with style "Caption" containing SEQ fields).

    Args:
        pkg: WordPackage

    Returns list of dicts with: id, label, number, text, block_id, style.
    """
    results = []

    for kind, p_el in iter_body_blocks(pkg):
        if kind != "paragraph":
            continue

        style_name = get_paragraph_style(p_el)

        if style_name != "Caption":
            continue

        # Extract text and look for SEQ field pattern
        full_text = get_paragraph_text(p_el)

        # Parse the caption: "Label N: text" or "Label N – text"
        # The SEQ field result is embedded in the text
        match = re.match(r"^(\w+)\s+(\d+)[:–\-]\s*(.*)$", full_text)
        if match:
            label, number, caption_text = match.groups()
            number = int(number)
        else:
            # Can't parse - use full text
            label = "Unknown"
            number = 0
            caption_text = full_text

        # Generate block ID
        occurrence = count_occurrence(pkg, kind, full_text, p_el)
        block_id = make_block_id(kind, full_text, occurrence)

        results.append(
            {
                "id": block_id,
                "label": label,
                "number": number,
                "text": caption_text,
                "block_id": block_id,
                "style": style_name,
            }
        )

    return results
