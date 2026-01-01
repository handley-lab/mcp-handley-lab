"""Track changes (revisions) operations.

Contains functions for:
- Reading tracked changes (insertions, deletions, moves, formatting)
- Accepting/rejecting individual changes
- Accepting/rejecting all changes
- Move handling (source/destination pairing)

Pure OOXML implementation - works directly with lxml elements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree
from lxml.etree import ElementBase as _LxmlElementBase

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.ops.core import mark_dirty

if TYPE_CHECKING:
    pass


# =============================================================================
# Constants
# =============================================================================

# Namespace for revision XPath queries
_REV_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

# Content revision elements (accept/reject supported)
_CONTENT_REVISIONS = ("w:ins", "w:del")

# Move markers (for range-based pairing)
_MOVE_RANGE_MARKERS = (
    "w:moveFromRangeStart",
    "w:moveFromRangeEnd",
    "w:moveToRangeStart",
    "w:moveToRangeEnd",
)
_MOVE_WRAPPERS = ("w:moveFrom", "w:moveTo")

# Formatting/table revisions (report only, no accept/reject)
_FORMATTING_REVISIONS = (
    "w:pPrChange",
    "w:rPrChange",
    "w:sectPrChange",
    "w:numberingChange",
    "w:tcPrChange",
    "w:trPrChange",
    "w:tblPrChange",
    "w:tblPrExChange",
    "w:cellDel",
    "w:cellIns",
    "w:cellMerge",
    "w:tblGridChange",
)

# All revision tags for detection
_ALL_REVISION_TAGS = (
    _CONTENT_REVISIONS + _MOVE_RANGE_MARKERS + _MOVE_WRAPPERS + _FORMATTING_REVISIONS
)


# =============================================================================
# XPath Helper
# =============================================================================


def _get_document_xml(pkg) -> etree._Element:
    """Get document.xml root from WordPackage."""
    return pkg.document_xml


def _rev_xpath(element, expr: str) -> list:
    """Execute XPath with revision namespace."""
    return _LxmlElementBase.xpath(element, expr, namespaces=_REV_NS)


# =============================================================================
# Detection and Reading
# =============================================================================


def has_tracked_changes(pkg) -> bool:
    """Check if document body has any tracked changes.

    Args:
        pkg: WordPackage
    Searches only within w:body (not headers/footers/footnotes).
    """
    doc_xml = _get_document_xml(pkg)
    xpath_expr = " | ".join(f"//w:body//{tag}" for tag in _ALL_REVISION_TAGS)
    return bool(_rev_xpath(doc_xml, xpath_expr))


def _get_revision_text(element, tag: str) -> str:
    """Extract text from a revision element.

    For deletions (w:del), uses w:delText.
    For insertions (w:ins) and other elements, uses w:t.
    """
    parts = []
    if tag == "del":
        # Deletions use w:delText
        for dt in _rev_xpath(element, ".//w:delText"):
            if dt.text:
                parts.append(dt.text)
    else:
        # Insertions and other elements use w:t
        for t in _rev_xpath(element, ".//w:t"):
            if t.text:
                parts.append(t.text)
    return "".join(parts)


def _classify_revision(tag: str) -> tuple[str, bool]:
    """Classify a revision tag into type and whether accept/reject is supported.

    Returns: (type_name, is_supported)
    """
    if tag == "ins":
        return "insertion", True
    if tag == "del":
        return "deletion", True
    if tag in ("moveFrom", "moveTo"):
        return "move", True  # Move wrappers are supported
    if tag in (
        "moveFromRangeStart",
        "moveFromRangeEnd",
        "moveToRangeStart",
        "moveToRangeEnd",
    ):
        return "move", False  # Range markers are metadata, not actionable
    if tag in ("pPrChange", "rPrChange", "sectPrChange", "numberingChange"):
        return "formatting", False
    if tag in (
        "cellDel",
        "cellIns",
        "cellMerge",
        "tcPrChange",
        "trPrChange",
        "tblPrChange",
        "tblPrExChange",
        "tblGridChange",
    ):
        return "table", False
    return "unknown", False


def _has_field_deletion(element) -> bool:
    """Check if element contains w:delInstrText (field instruction deletion)."""
    return bool(_rev_xpath(element, ".//w:delInstrText"))


def read_tracked_changes(pkg) -> list[dict]:
    """List all tracked changes in document body.

    Args:
        pkg: WordPackage

    Searches only within w:body (consistent with has_tracked_changes).
    Returns list in document order (no deduplication - same w:id may appear
    multiple times for multi-element revisions like cross-paragraph changes).

    Each entry contains:
    - id: str (w:id attribute, treated as string; may repeat for grouped changes)
    - type: str (insertion, deletion, move, formatting, table)
    - author: str
    - date: str
    - text: str (affected text, empty for formatting/markers)
    - supported: bool (whether accept/reject is implemented)
    - tag: str (original tag name for disambiguation)
    """
    doc_xml = _get_document_xml(pkg)
    results = []

    # Include all revision elements (content, moves, formatting)
    # Move range markers included for completeness but typically have no text
    all_elements = (
        _CONTENT_REVISIONS
        + _MOVE_WRAPPERS
        + _MOVE_RANGE_MARKERS
        + _FORMATTING_REVISIONS
    )
    xpath_expr = " | ".join(f"//w:body//{tag}" for tag in all_elements)

    for el in _rev_xpath(doc_xml, xpath_expr):
        change_id = el.get(qn("w:id"))
        if not change_id:
            continue

        # Get tag name without namespace
        tag = el.tag.split("}")[-1]
        rev_type, supported = _classify_revision(tag)

        # Check for field deletions (unsupported for reject)
        if tag == "del" and _has_field_deletion(el):
            supported = False

        results.append(
            {
                "id": change_id,
                "type": rev_type,
                "author": el.get(qn("w:author"), ""),
                "date": el.get(qn("w:date"), ""),
                "text": _get_revision_text(el, tag),
                "supported": supported,
                "tag": tag,
            }
        )

    return results


# =============================================================================
# XML Manipulation Helpers
# =============================================================================


def _drop_tag_keep_content(element) -> None:
    """Remove element tag, promote children to parent at correct position.

    Handles lxml text/tail correctly:
    1. Find element's index in parent
    2. Preserve element.text by prepending to first child or attaching appropriately
    3. Remove children from element, insert at parent[index], incrementing
    4. Propagate element.tail to last child or previous sibling
    5. Remove the now-empty element

    Used for accepting insertions (unwrap w:ins) and rejecting deletions
    (unwrap w:del after converting delText to t).
    """
    parent = element.getparent()
    index = parent.index(element)
    children = list(element)  # Snapshot before mutation

    # Handle element.text (text before first child)
    if element.text:
        if children:
            # Prepend to first child's text
            first_child = children[0]
            first_child.text = element.text + (first_child.text or "")
        else:
            # No children - attach to previous sibling's tail or parent's text
            prev = element.getprevious()
            if prev is not None:
                prev.tail = (prev.tail or "") + element.text
            else:
                parent.text = (parent.text or "") + element.text

    # Move children to parent at correct position
    for child in children:
        element.remove(child)
        parent.insert(index, child)
        index += 1

    # Handle tail text (attach to last promoted child or previous sibling)
    if element.tail:
        if children:
            last_child = children[-1]
            last_child.tail = (last_child.tail or "") + element.tail
        else:
            # No children - attach to previous sibling or parent text
            prev = element.getprevious()
            if prev is not None:
                prev.tail = (prev.tail or "") + element.tail
            else:
                parent.text = (parent.text or "") + element.tail

    parent.remove(element)


def _convert_deltext_to_text(element: etree._Element) -> None:
    """Convert w:delText elements to w:t elements within element.

    Pure OOXML: Works with lxml elements.

    Used when rejecting a deletion - the deleted text must be restored
    as normal text (w:t) rather than deleted text (w:delText).
    """
    for dt in _rev_xpath(element, ".//w:delText"):
        # Create new w:t element
        new_t = etree.Element(qn("w:t"))
        new_t.text = dt.text
        # Preserve xml:space if present
        space_attr = dt.get("{http://www.w3.org/XML/1998/namespace}space")
        if space_attr:
            new_t.set("{http://www.w3.org/XML/1998/namespace}space", space_attr)
        # Replace in parent
        dt_parent = dt.getparent()
        dt_parent.replace(dt, new_t)


def _process_revisions_deepest_first(elements: list) -> list:
    """Sort revision elements by depth (ancestor count), deepest first.

    This ensures inner revisions are processed before outer ones,
    preventing parent removal from orphaning child operations.
    """
    return sorted(elements, key=lambda el: len(list(el.iterancestors())), reverse=True)


def _remove_element_preserve_tail(element) -> None:
    """Remove element from parent while preserving tail text.

    In lxml, each element's .tail contains text that follows the element.
    When removing an element, we must preserve its tail by attaching it
    to the previous sibling's tail or the parent's text.
    """
    parent = element.getparent()
    if element.tail:
        prev = element.getprevious()
        if prev is not None:
            prev.tail = (prev.tail or "") + element.tail
        else:
            parent.text = (parent.text or "") + element.tail

    parent.remove(element)


# =============================================================================
# Element Finding
# =============================================================================


def _find_elements_by_id(pkg, change_id: str, tags: tuple) -> list:
    """Find all elements with given w:id in document body.

    Args:
        pkg: WordPackage

    Uses Python filtering instead of XPath interpolation to avoid
    potential issues with special characters in change_id.
    """
    doc_xml = _get_document_xml(pkg)
    # Select all elements by tag, then filter by w:id in Python
    xpath_expr = " | ".join(f"//w:body//{tag}" for tag in tags)
    all_elements = _rev_xpath(doc_xml, xpath_expr)
    w_id_qn = qn("w:id")
    return [el for el in all_elements if el.get(w_id_qn) == change_id]


# =============================================================================
# Move Handling
# =============================================================================


def _find_move_range_markers(pkg, move_id: str) -> dict:
    """Find all range markers for a move operation.

    Args:
        pkg: WordPackage

    Returns dict with keys: from_start, from_end, to_start, to_end
    Each value is a list of matching elements (usually 0 or 1).
    """
    return {
        "from_start": _find_elements_by_id(pkg, move_id, ("w:moveFromRangeStart",)),
        "from_end": _find_elements_by_id(pkg, move_id, ("w:moveFromRangeEnd",)),
        "to_start": _find_elements_by_id(pkg, move_id, ("w:moveToRangeStart",)),
        "to_end": _find_elements_by_id(pkg, move_id, ("w:moveToRangeEnd",)),
    }


def _accept_move(pkg, move_id: str, move_from: list, move_to: list) -> None:
    """Accept a move: keep destination content, remove source."""
    markers = _find_move_range_markers(pkg, move_id)

    # Process deepest first
    all_from = _process_revisions_deepest_first(move_from)
    all_to = _process_revisions_deepest_first(move_to)

    # Remove source (moveFrom) - content is discarded, preserve tail
    for el in all_from:
        _remove_element_preserve_tail(el)

    # Keep destination (moveTo) - unwrap to keep content
    for el in all_to:
        _drop_tag_keep_content(el)

    # Clean up range markers
    for marker_list in markers.values():
        for marker in marker_list:
            _remove_element_preserve_tail(marker)


def _reject_move(pkg, move_id: str, move_from: list, move_to: list) -> None:
    """Reject a move: keep source content, remove destination."""
    markers = _find_move_range_markers(pkg, move_id)

    # Process deepest first
    all_from = _process_revisions_deepest_first(move_from)
    all_to = _process_revisions_deepest_first(move_to)

    # Remove destination (moveTo) - content is discarded, preserve tail
    for el in all_to:
        _remove_element_preserve_tail(el)

    # Keep source (moveFrom) - unwrap to keep content
    for el in all_from:
        _drop_tag_keep_content(el)

    # Clean up range markers
    for marker_list in markers.values():
        for marker in marker_list:
            _remove_element_preserve_tail(marker)


# =============================================================================
# Accept/Reject Functions
# =============================================================================


def accept_change(pkg, change_id: str) -> None:
    """Accept a specific tracked change by ID.

    Args:
        pkg: WordPackage

    - Insertions (w:ins): Unwrap content, remove tag
    - Deletions (w:del): Remove entirely
    - Moves: Remove source, unwrap destination
    - Formatting: Raises ValueError (not supported)
    """
    # Find all elements with this ID
    ins_elements = _find_elements_by_id(pkg, change_id, ("w:ins",))
    del_elements = _find_elements_by_id(pkg, change_id, ("w:del",))
    move_from = _find_elements_by_id(pkg, change_id, ("w:moveFrom",))
    move_to = _find_elements_by_id(pkg, change_id, ("w:moveTo",))
    formatting = _find_elements_by_id(pkg, change_id, _FORMATTING_REVISIONS)

    if formatting:
        raise ValueError(f"Cannot accept formatting change {change_id} (not supported)")

    # Handle moves
    if move_from or move_to:
        _accept_move(pkg, change_id, move_from, move_to)
        mark_dirty(pkg)
        return

    if not ins_elements and not del_elements:
        raise ValueError(f"Change not found: {change_id}")

    # Process deepest first to handle nested revisions
    all_elements = _process_revisions_deepest_first(ins_elements + del_elements)

    for el in all_elements:
        tag = el.tag.split("}")[-1]
        if tag == "ins":
            # Accept insertion: unwrap (keep content)
            _drop_tag_keep_content(el)
        elif tag == "del":
            # Accept deletion: remove entirely (content is deleted)
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)

    # Mark document.xml as modified for WordPackage
    mark_dirty(pkg)


def reject_change(pkg, change_id: str) -> None:
    """Reject a specific tracked change by ID.

    Args:
        pkg: WordPackage

    - Insertions (w:ins): Remove entirely
    - Deletions (w:del): Convert delText to t, unwrap
    - Moves: Remove destination, unwrap source
    - Formatting: Raises ValueError (not supported)
    """
    # Find all elements with this ID
    ins_elements = _find_elements_by_id(pkg, change_id, ("w:ins",))
    del_elements = _find_elements_by_id(pkg, change_id, ("w:del",))
    move_from = _find_elements_by_id(pkg, change_id, ("w:moveFrom",))
    move_to = _find_elements_by_id(pkg, change_id, ("w:moveTo",))
    formatting = _find_elements_by_id(pkg, change_id, _FORMATTING_REVISIONS)

    if formatting:
        raise ValueError(f"Cannot reject formatting change {change_id} (not supported)")

    # Handle moves
    if move_from or move_to:
        _reject_move(pkg, change_id, move_from, move_to)
        mark_dirty(pkg)
        return

    if not ins_elements and not del_elements:
        raise ValueError(f"Change not found: {change_id}")

    # Check for field deletions (unsupported for reject)
    for el in del_elements:
        if _has_field_deletion(el):
            raise ValueError(
                f"Cannot reject field deletion {change_id} (not supported)"
            )

    # Process deepest first to handle nested revisions
    all_elements = _process_revisions_deepest_first(ins_elements + del_elements)

    for el in all_elements:
        tag = el.tag.split("}")[-1]
        if tag == "ins":
            # Reject insertion: remove entirely (content was never there)
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)
        elif tag == "del":
            # Reject deletion: restore content (convert delText to t, unwrap)
            _convert_deltext_to_text(el)
            _drop_tag_keep_content(el)

    # Mark document.xml as modified for WordPackage
    mark_dirty(pkg)


def accept_all_changes(pkg) -> int:
    """Accept all supported tracked changes. Returns count.

    Args:
        pkg: WordPackage

    Gathers all change IDs first, then processes to avoid
    iteration invalidation during tree mutation.
    """
    changes = read_tracked_changes(pkg)
    # Filter to supported changes and get unique IDs (preserving order)
    seen = set()
    supported_ids = []
    for c in changes:
        if c["supported"] and c["id"] not in seen:
            seen.add(c["id"])
            supported_ids.append(c["id"])

    count = 0
    for change_id in supported_ids:
        accept_change(pkg, change_id)
        count += 1

    return count


def reject_all_changes(pkg) -> int:
    """Reject all supported tracked changes. Returns count.

    Args:
        pkg: WordPackage
    """
    changes = read_tracked_changes(pkg)
    # Filter to supported changes and get unique IDs (preserving order)
    seen = set()
    supported_ids = []
    for c in changes:
        if c["supported"] and c["id"] not in seen:
            seen.add(c["id"])
            supported_ids.append(c["id"])

    count = 0
    for change_id in supported_ids:
        reject_change(pkg, change_id)
        count += 1

    return count
