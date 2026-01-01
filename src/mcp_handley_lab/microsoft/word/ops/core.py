"""Core utilities for Word document operations.

Contains shared helpers used across all ops modules:
- Content-addressed ID generation and resolution
- Block iteration and traversal
- Target resolution for hierarchical addressing
- Common XML element operations

Pure OOXML implementation working with WordPackage and lxml elements.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass

from lxml import etree

from mcp_handley_lab.microsoft.word.constants import NSMAP, qn
from mcp_handley_lab.microsoft.word.models import Block

# Element tag constants for pure OOXML
_W_P = qn("w:p")
_W_TBL = qn("w:tbl")
_W_TR = qn("w:tr")
_W_TC = qn("w:tc")
_W_R = qn("w:r")
_W_T = qn("w:t")
_W_PPR = qn("w:pPr")
_W_PSTYLE = qn("w:pStyle")
_W_VAL = qn("w:val")
_W_TYPE = qn("w:type")

# Regexes for parsing IDs and styles
_HEADING_RE = re.compile(
    r"^Heading ?([1-9])$"
)  # Matches both "Heading1" and "Heading 1"
_ID_RE = re.compile(r"^(paragraph|heading[1-9]|table)_([0-9a-f]{8})_(\d+)$")
_IMAGE_ID_RE = re.compile(r"^image_([0-9a-f]{8})_(\d+)$")

# Hierarchical path segment patterns (0-based indices)
_CELL_RE = re.compile(r"^r(\d+)c(\d+)$")
_PARA_RE = re.compile(r"^p(\d+)$")
_TABLE_RE = re.compile(r"^tbl(\d+)$")

# Unit conversions
_EMU_PER_INCH = 914400

# PathSegment: (kind, indices) where kind='cell'|'para'|'tbl'
PathSegment = tuple[str, tuple[int, ...]]


@dataclass
class ResolvedTarget:
    """Result of resolving a hierarchical target ID.

    Works with lxml elements directly.
    """

    base_id: str
    base_kind: str  # 'table' | 'paragraph' | 'heading1' etc
    base_el: etree._Element  # w:p or w:tbl element
    base_occurrence: int
    leaf_kind: str  # 'table' | 'cell' | 'paragraph'
    leaf_el: etree._Element  # w:p, w:tbl, or w:tc element


# =============================================================================
# Content Hashing and ID Generation
# =============================================================================


def content_hash(text: str) -> str:
    """8-char SHA256 of normalized text for content-addressable IDs."""
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()[:8]


def make_block_id(block_type: str, text: str, occurrence: int) -> str:
    """Generate content-addressable block ID. Single source of truth."""
    return f"{block_type}_{content_hash(text)}_{occurrence}"


def get_element_id_ooxml(pkg, el: etree._Element, heading_level: int = 0) -> str:
    """Calculate content-addressed ID for an element.

    Args:
        pkg: WordPackage
        el: w:p or w:tbl element
        heading_level: Override heading level (for newly created headings)
    """
    tag = el.tag
    if tag == qn("w:tbl"):
        block_type = "table"
        content = table_content_for_hash(el)
    else:
        block_type, _ = paragraph_kind_and_level(el)
        if heading_level:
            block_type = f"heading{heading_level}"
        content = get_paragraph_text_ooxml(el)

    occurrence = count_occurrence(pkg, block_type, content, el)
    return make_block_id(block_type, content, occurrence)


# =============================================================================
# Pure OOXML Element Helpers
# =============================================================================


def get_paragraph_text(p_el: etree._Element) -> str:
    """Extract text from w:p element.

    Note: This is an alias for get_paragraph_text_ooxml() for consistency.
    Preserves document order for tabs, breaks, and special characters.
    """
    return get_paragraph_text_ooxml(p_el)


def get_paragraph_style(p_el: etree._Element) -> str:
    """Get paragraph style name from w:p element."""
    pPr = p_el.find(_W_PPR)
    if pPr is not None:
        pStyle = pPr.find(_W_PSTYLE)
        if pStyle is not None:
            return pStyle.get(_W_VAL, "Normal")
    return "Normal"


def get_cell_text(tc_el: etree._Element) -> str:
    """Extract text from w:tc element."""
    texts = []
    for p_el in tc_el.iter(_W_P):
        texts.append(get_paragraph_text(p_el))
    return "\n".join(texts)


def table_content_for_hash(tbl_el: etree._Element) -> str:
    """Get full table content as canonical string for hashing.

    Pure OOXML: Takes w:tbl element.
    """
    rows_data = []
    for tr_el in tbl_el.findall(_W_TR):
        cells_data = []
        for tc_el in tr_el.findall(_W_TC):
            cells_data.append(get_cell_text(tc_el))
        rows_data.append(cells_data)
    return json.dumps(rows_data, ensure_ascii=False, separators=(",", ":"))


def paragraph_kind_and_level(p_el: etree._Element) -> tuple[str, int]:
    """Detect if paragraph is a heading and return (kind, level).

    Pure OOXML: Takes w:p element.
    For content-hash IDs, kind includes level: 'heading1', 'heading2', etc.
    """
    style_name = get_paragraph_style(p_el)
    m = _HEADING_RE.match(style_name)
    if m:
        level = int(m.group(1))
        return (f"heading{level}", level)
    return ("paragraph", 0)


# =============================================================================
# Package Helpers
# =============================================================================


def mark_dirty(pkg, partname: str = "/word/document.xml") -> None:
    """Mark an XML part as modified.

    Args:
        pkg: WordPackage

    Must call this after modifying cached XML so save() serializes it.
    """
    pkg.mark_xml_dirty(partname)


# =============================================================================
# Block Iteration
# =============================================================================


def iter_body_blocks(pkg) -> Iterator[tuple[str, etree._Element]]:
    """Yield (block_kind, element) in true document order.

    Args:
        pkg: WordPackage
    """
    body = pkg.body
    for child in body.iterchildren():
        if child.tag == _W_P:
            yield ("paragraph", child)
        elif child.tag == _W_TBL:
            yield ("table", child)


def _iter_all_paragraphs(pkg) -> Iterator[etree._Element]:
    """Iterate over all paragraphs in document body and tables.

    Args:
        pkg: WordPackage
    """
    for kind, el in iter_body_blocks(pkg):
        if kind == "paragraph":
            yield el
        elif kind == "table":
            yield from el.iter(_W_P)


def _iter_all_runs_in_paragraph(p_el: etree._Element) -> Iterator[etree._Element]:
    """Iterate all w:r elements in paragraph including those inside hyperlinks.

    Pure OOXML: Yields w:r elements.
    """
    yield from p_el.iter(_W_R)


# =============================================================================
# Target Resolution
# =============================================================================


def parse_target_id(target_id: str) -> tuple[str, list[PathSegment]]:
    """Parse target_id into (base_id, path_segments).

    Supports hierarchical IDs: table_abc12345_0#r0c1/p0
    Returns (base_id, []) for simple IDs without path.
    """
    base_id, *rest = target_id.split("#", 1)
    if not rest:
        return target_id, []

    segments: list[PathSegment] = []
    for part in rest[0].split("/"):
        if m := _CELL_RE.match(part):
            segments.append(("cell", (int(m[1]), int(m[2]))))
        elif m := _PARA_RE.match(part):
            segments.append(("para", (int(m[1]),)))
        elif m := _TABLE_RE.match(part):
            segments.append(("tbl", (int(m[1]),)))
        else:
            raise ValueError(f"Invalid path segment: {part}")
    return base_id, segments


def get_table_cell(tbl_el: etree._Element, row: int, col: int) -> etree._Element:
    """Get cell element at (row, col) from table element.

    Simple positional lookup. Does not account for grid spans or merges.
    """
    rows = tbl_el.findall(_W_TR)
    tr_el = rows[row]
    cells = tr_el.findall(_W_TC)
    return cells[col]


def get_cell_paragraphs(tc_el: etree._Element) -> list[etree._Element]:
    """Get all paragraph elements within a cell."""
    return tc_el.findall(_W_P)


def get_cell_tables(tc_el: etree._Element) -> list[etree._Element]:
    """Get all nested table elements within a cell."""
    return tc_el.findall(_W_TBL)


def resolve_path(
    container_el: etree._Element, segments: list[PathSegment]
) -> etree._Element:
    """Resolve path segments from container element. Returns leaf element.

    Pure OOXML: Works with lxml elements directly.
    Transition rules:
    - From Table -> cell (r,c) only
    - From Cell -> para (p) or tbl (tbl)
    - From nested Table -> cell (r,c)
    """
    current = container_el

    for kind, indices in segments:
        if kind == "cell":
            row, col = indices
            current = get_table_cell(current, row, col)
        elif kind == "para":
            current = get_cell_paragraphs(current)[indices[0]]
        elif kind == "tbl":
            current = get_cell_tables(current)[indices[0]]

    return current


def _resolve_base_block(pkg, base_id: str) -> tuple[str, etree._Element, int]:
    """Resolve base block ID to (block_type, element, occurrence).

    Args:
        pkg: WordPackage
        base_id: Block ID like table_abc12345_0

    Uses content-hash IDs: {type}_{hash}_{occurrence}
    Searches all blocks for matching type+hash, then skips to Nth occurrence.
    """
    match = _ID_RE.match(base_id)
    if not match:
        raise ValueError(f"Invalid block ID format: {base_id}")
    target_type, target_hash, occurrence_str = match.groups()
    target_occurrence = int(occurrence_str)

    occurrence_count = 0
    for kind, el in iter_body_blocks(pkg):
        if kind == "table":
            if target_type == "table":
                table_content = table_content_for_hash(el)
                if content_hash(table_content) == target_hash:
                    if occurrence_count == target_occurrence:
                        return "table", el, occurrence_count
                    occurrence_count += 1
        else:
            block_type, _ = paragraph_kind_and_level(el)
            if target_type == block_type:
                text = get_paragraph_text(el)
                if content_hash(text) == target_hash:
                    if occurrence_count == target_occurrence:
                        return block_type, el, occurrence_count
                    occurrence_count += 1
    raise ValueError(f"Block not found: {base_id}")


def resolve_target(pkg, target_id: str) -> ResolvedTarget:
    """Resolve target_id to ResolvedTarget with base and leaf info.

    Args:
        pkg: WordPackage
        target_id: Hierarchical ID like table_abc12345_0#r0c1/p0
    """
    base_id, path_segments = parse_target_id(target_id)

    # Resolve base block
    base_kind, base_el, base_occurrence = _resolve_base_block(pkg, base_id)

    if not path_segments:
        return ResolvedTarget(
            base_id=base_id,
            base_kind=base_kind,
            base_el=base_el,
            base_occurrence=base_occurrence,
            leaf_kind=base_kind,
            leaf_el=base_el,
        )

    # Resolve path within container
    leaf_el = resolve_path(base_el, path_segments)

    # Determine leaf kind based on element tag
    if leaf_el.tag == _W_TBL:
        leaf_kind = "table"
    elif leaf_el.tag == _W_TC:
        leaf_kind = "cell"
    else:
        leaf_kind = "paragraph"

    return ResolvedTarget(
        base_id=base_id,
        base_kind=base_kind,
        base_el=base_el,
        base_occurrence=base_occurrence,
        leaf_kind=leaf_kind,
        leaf_el=leaf_el,
    )


def find_paragraph_by_id(pkg, target_id: str) -> etree._Element:
    """Find a paragraph by its block ID.

    Args:
        pkg: WordPackage
        target_id: Block ID

    Returns:
        w:p element

    Raises:
        ValueError: If target not found or not a paragraph
    """
    target = resolve_target(pkg, target_id)
    if target.leaf_kind != "paragraph":
        raise ValueError(f"Target {target_id} is not a paragraph")
    return target.leaf_el


def count_occurrence(
    pkg,
    block_type: str,
    text: str,
    target_el: etree._Element,
) -> int:
    """Count how many blocks with same type+hash appear before target_el.

    Args:
        pkg: WordPackage
        block_type: Type like 'paragraph', 'heading1', 'table'
        text: Content text (for tables, use table_content_for_hash)
        target_el: Element to find occurrence index for

    Used after edits to compute the correct occurrence index for returned ID.
    """
    target_hash = content_hash(text)
    occurrence = 0
    for kind, el in iter_body_blocks(pkg):
        if kind == "table":
            if block_type == "table":
                table_content = table_content_for_hash(el)
                if content_hash(table_content) == target_hash:
                    if el is target_el:
                        return occurrence
                    occurrence += 1
        else:
            actual_type, _ = paragraph_kind_and_level(el)
            if block_type == actual_type:
                block_text = get_paragraph_text(el)
                if content_hash(block_text) == target_hash:
                    if el is target_el:
                        return occurrence
                    occurrence += 1
    raise ValueError("target_el not found in document")


# =============================================================================
# Block Building
# =============================================================================


def build_blocks(
    pkg,
    offset: int = 0,
    limit: int = 50,
    heading_only: bool = False,
    search_query: str = "",
) -> tuple[list[Block], int]:
    """Build list of Block objects from document body.

    Args:
        pkg: WordPackage
        offset: Number of blocks to skip
        limit: Maximum blocks to return
        heading_only: Only return headings
        search_query: Filter by text content

    Uses content-hash IDs: {type}_{hash}_{occurrence}
    """
    # Import here to avoid circular dependency (table_to_markdown is in tables.py)
    from mcp_handley_lab.microsoft.word.ops.tables import table_to_markdown

    blocks = []
    matched = 0
    query_lower = search_query.lower() if search_query else ""
    hash_counts: dict[str, int] = {}  # {type_hash: count} for occurrence tracking

    for kind, el in iter_body_blocks(pkg):
        if kind == "paragraph":
            block_type, level = paragraph_kind_and_level(el)
            text = get_paragraph_text(el)
            style = get_paragraph_style(el)

            # Track occurrence for this type+hash combination
            hash_key = f"{block_type}_{content_hash(text)}"
            occurrence = hash_counts.get(hash_key, 0)
            hash_counts[hash_key] = occurrence + 1

            if heading_only and not block_type.startswith("heading"):
                continue
            if query_lower and query_lower not in text.lower():
                continue

            if matched >= offset and len(blocks) < limit:
                blocks.append(
                    Block(
                        id=make_block_id(block_type, text, occurrence),
                        type=block_type,
                        text=text,
                        style=style,
                        level=level,
                    )
                )
            matched += 1

        elif kind == "table":
            md, rows, cols = table_to_markdown(el)
            # Use full content for hash (not truncated markdown)
            table_content = table_content_for_hash(el)

            # Track occurrence for this type+hash combination
            hash_key = f"table_{content_hash(table_content)}"
            occurrence = hash_counts.get(hash_key, 0)
            hash_counts[hash_key] = occurrence + 1

            if heading_only:
                continue
            # Search full table content, not truncated markdown preview
            if query_lower and query_lower not in table_content.lower():
                continue

            if matched >= offset and len(blocks) < limit:
                blocks.append(
                    Block(
                        id=make_block_id("table", table_content, occurrence),
                        type="table",
                        text=md,  # Keep markdown for display
                        style="",  # Table style not easily available in pure OOXML
                        rows=rows,
                        cols=cols,
                    )
                )
            matched += 1

    return blocks, matched


# =============================================================================
# Element Operations
# =============================================================================


def _make_run_with(*elements) -> etree._Element:
    """Create a w:r element containing the given child elements."""
    r = etree.Element(_W_R)
    for elem in elements:
        r.append(elem)
    return r


def _insert_at(
    target_el: etree._Element, new_el: etree._Element, position: str
) -> None:
    """Insert new_el before or after target_el."""
    (target_el.addprevious if position == "before" else target_el.addnext)(new_el)


# =============================================================================
# Pure OOXML Element Manipulation
# =============================================================================


def get_or_create_pPr(p_el: etree._Element) -> etree._Element:
    """Get or create w:pPr element for a paragraph."""
    pPr = p_el.find(_W_PPR)
    if pPr is None:
        pPr = etree.Element(_W_PPR)
        p_el.insert(0, pPr)
    return pPr


def set_paragraph_text_ooxml(p_el: etree._Element, text: str) -> None:
    """Set paragraph text by clearing runs and adding new text (pure OOXML).

    Preserves paragraph properties (w:pPr). Clears all runs and creates a new
    single run with the text.
    """
    # Remove all runs (w:r elements)
    for r in list(p_el.findall(_W_R)):
        p_el.remove(r)

    # Remove hyperlinks and other run containers
    for hl in list(p_el.findall(qn("w:hyperlink"))):
        p_el.remove(hl)

    # Add new run with text
    if text:
        r = etree.SubElement(p_el, _W_R)
        t = etree.SubElement(r, _W_T)
        t.text = text
        # Preserve spaces
        if text.startswith(" ") or text.endswith(" "):
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def set_paragraph_style_ooxml(p_el: etree._Element, style_name: str) -> None:
    """Set paragraph style (pure OOXML).

    Sets the w:pStyle element in w:pPr.
    """
    pPr = get_or_create_pPr(p_el)
    pStyle = pPr.find(_W_PSTYLE)
    if pStyle is None:
        pStyle = etree.Element(_W_PSTYLE)
        pPr.insert(0, pStyle)
    pStyle.set(_W_VAL, style_name)


def get_paragraph_text_ooxml(p_el: etree._Element) -> str:
    """Extract text from paragraph element (pure OOXML).

    Traverses in document order to preserve text/tab/break sequence.
    """
    parts = []
    # Process runs and hyperlinks in document order
    for child in p_el:
        tag = child.tag
        if tag == _W_R:
            # Process run content in order
            _extract_run_text(child, parts)
        elif tag == qn("w:hyperlink"):
            # Process hyperlink runs in order
            for run in child.findall(_W_R):
                _extract_run_text(run, parts)
    return "".join(parts)


def _extract_run_text(run_el: etree._Element, parts: list) -> None:
    """Extract text from a w:r element in document order."""
    for child in run_el:
        tag = child.tag
        if tag == _W_T:
            if child.text is not None:
                parts.append(child.text)
        elif tag == qn("w:tab"):
            parts.append("\t")
        elif tag in (qn("w:br"), qn("w:cr")):
            parts.append("\n")
        elif tag == qn("w:noBreakHyphen"):
            parts.append("\u2011")
        elif tag == qn("w:softHyphen"):
            parts.append("\u00ad")


# =============================================================================
# Re-exports for convenience
# =============================================================================

# Make NSMAP available for other ops modules (replaces docx.oxml.ns.nsmap)
nsmap = NSMAP


# =============================================================================
# Break Operations (Pure OOXML)
# =============================================================================


def add_page_break_ooxml(body: etree._Element) -> etree._Element:
    """Append a page break paragraph to body. Returns the w:p element.

    Pure OOXML: Takes w:body element.
    """
    p = etree.SubElement(body, _W_P)
    r = etree.SubElement(p, _W_R)
    br = etree.SubElement(r, qn("w:br"))
    br.set(_W_TYPE, "page")
    return p


def add_break_after_ooxml(target_el: etree._Element, break_type: str) -> etree._Element:
    """Insert break paragraph after target element. Returns the w:p element.

    Pure OOXML: Takes w:p or w:tbl element.
    break_type: 'page', 'column', 'line'
    """
    break_type_lower = break_type.lower()
    if break_type_lower not in ("page", "column", "line"):
        raise ValueError(
            f"Invalid break_type '{break_type}'. Valid: page, column, line"
        )

    # Create paragraph with break
    p = etree.Element(_W_P)
    r = etree.SubElement(p, _W_R)

    if break_type_lower == "line":
        # Line break: w:br with no type (or type="textWrapping")
        etree.SubElement(r, qn("w:br"))
    else:
        # Page/column break: w:br with w:type attribute
        br = etree.SubElement(r, qn("w:br"))
        br.set(_W_TYPE, break_type_lower)

    # Insert after target
    target_el.addnext(p)
    return p


# =============================================================================
# Block Creation (Pure OOXML)
# =============================================================================


def create_paragraph_ooxml(text: str, style_name: str = "") -> etree._Element:
    """Create a w:p element with text and optional style.

    Pure OOXML: Returns a standalone w:p element (not attached to document).

    Args:
        text: Paragraph text content
        style_name: Optional style name to apply
    """
    p = etree.Element(_W_P)

    if style_name:
        pPr = etree.SubElement(p, _W_PPR)
        pStyle = etree.SubElement(pPr, _W_PSTYLE)
        pStyle.set(_W_VAL, style_name)

    if text:
        r = etree.SubElement(p, _W_R)
        t = etree.SubElement(r, _W_T)
        t.text = text
        if text.startswith(" ") or text.endswith(" "):
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    return p


def create_heading_ooxml(text: str, level: int) -> etree._Element:
    """Create a heading w:p element.

    Pure OOXML: Returns a standalone w:p element with Heading{level} style.

    Args:
        text: Heading text content
        level: Heading level (0-9, where 0 is Title)
    """
    if level < 0 or level > 9:
        raise ValueError(f"Heading level must be 0-9, got {level}")

    style_name = "Title" if level == 0 else f"Heading {level}"
    return create_paragraph_ooxml(text, style_name)


def insert_paragraph_relative(
    target_el: etree._Element, text: str, style_name: str, position: str
) -> etree._Element:
    """Insert paragraph before or after target element.

    Pure OOXML: Takes w:p or w:tbl element, returns new w:p element.

    Args:
        target_el: Element to insert relative to
        text: Paragraph text content
        style_name: Style name to apply
        position: 'before' or 'after'
    """
    p = create_paragraph_ooxml(text, style_name)
    _insert_at(target_el, p, position)
    return p


def append_paragraph_ooxml(pkg, text: str, style_name: str = "") -> etree._Element:
    """Append paragraph to document body.

    Args:
        pkg: WordPackage
        text: Paragraph text
        style_name: Optional style name

    Returns the new w:p element.
    """
    p = create_paragraph_ooxml(text, style_name)
    body = pkg.body

    # Insert before final sectPr if present, else at end
    sectPr = body.find(qn("w:sectPr"))
    if sectPr is not None:
        sectPr.addprevious(p)
    else:
        body.append(p)

    mark_dirty(pkg)
    return p


def append_heading_ooxml(pkg, text: str, level: int) -> etree._Element:
    """Append heading to document body.

    Args:
        pkg: WordPackage
        text: Heading text
        level: Heading level (1-9)

    Returns the new w:p element.
    """
    p = create_heading_ooxml(text, level)
    body = pkg.body

    sectPr = body.find(qn("w:sectPr"))
    if sectPr is not None:
        sectPr.addprevious(p)
    else:
        body.append(p)

    mark_dirty(pkg)
    return p


def insert_content_ooxml(
    pkg,
    target_el: etree._Element,
    position: str,
    content_type: str,
    content_data: str,
    style_name: str = "",
    heading_level: int = 0,
) -> etree._Element:
    """Insert content relative to a target element.

    Args:
        pkg: WordPackage
        target_el: Element to insert relative to
        position: 'before' or 'after'
        content_type: 'paragraph', 'heading', or 'table'
        content_data: Text content or JSON for tables
        style_name: Style name to apply
        heading_level: Heading level (for headings)

    Returns the new element (w:p or w:tbl).
    """
    from mcp_handley_lab.microsoft.word.ops.tables import insert_table_relative

    if content_type == "paragraph":
        el = insert_paragraph_relative(target_el, content_data, style_name, position)
    elif content_type == "heading":
        p = create_heading_ooxml(content_data, heading_level)
        _insert_at(target_el, p, position)
        el = p
    elif content_type == "table":
        table_data = json.loads(content_data)
        el = insert_table_relative(target_el, table_data, position)
    else:
        raise ValueError(f"Unknown content_type: {content_type}")

    mark_dirty(pkg)
    return el


def append_content_ooxml(
    pkg,
    content_type: str,
    content_data: str,
    style_name: str = "",
    heading_level: int = 0,
) -> etree._Element:
    """Append content to document body.

    Args:
        pkg: WordPackage
        content_type: 'paragraph', 'heading', or 'table'
        content_data: Text content or JSON for tables
        style_name: Style name to apply (for paragraphs)
        heading_level: Heading level (for headings)

    Returns the new element (w:p or w:tbl).
    """
    from mcp_handley_lab.microsoft.word.ops.tables import (
        _create_table_element,
        populate_table,
    )

    if content_type == "paragraph":
        return append_paragraph_ooxml(pkg, content_data, style_name)
    elif content_type == "heading":
        return append_heading_ooxml(pkg, content_data, heading_level)
    elif content_type == "table":
        table_data = json.loads(content_data)
        rows = len(table_data)
        cols = max((len(r) for r in table_data), default=1)
        tbl = _create_table_element(rows, cols)
        populate_table(tbl, table_data)

        body = pkg.body
        sectPr = body.find(qn("w:sectPr"))
        if sectPr is not None:
            sectPr.addprevious(tbl)
        else:
            body.append(tbl)

        mark_dirty(pkg)
        return tbl
    else:
        raise ValueError(f"Unknown content_type: {content_type}")
