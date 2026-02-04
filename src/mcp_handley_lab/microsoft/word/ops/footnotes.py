"""Footnote and endnote operations.

Contains functions for:
- Reading footnotes/endnotes from documents
- Adding footnotes/endnotes to specific blocks
- Deleting footnotes/endnotes
"""

from __future__ import annotations

from lxml import etree
from lxml.etree import ElementBase as _LxmlElementBase

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.ops.core import (
    count_occurrence,
    get_paragraph_text,
    make_block_id,
    mark_dirty,
    paragraph_kind_and_level,
    resolve_target,
)
from mcp_handley_lab.microsoft.word.package import WordPackage

# =============================================================================
# Constants
# =============================================================================

# Namespaces for footnote operations
_FN_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_FN_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_FN_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_FN_XML_NS = "http://www.w3.org/XML/1998/namespace"

# Reserved footnote/endnote IDs (separators only, user notes use 1+)
_RESERVED_NOTE_IDS = {-1, 0}


# =============================================================================
# XPath Helper
# =============================================================================


def _fn_xpath(element: etree._Element, expr: str, ns: dict) -> list:
    """XPath using ElementBase.xpath for namespace compatibility."""
    return _LxmlElementBase.xpath(element, expr, namespaces=ns)


# =============================================================================
# Reading Footnotes/Endnotes
# =============================================================================


def build_footnotes(pkg) -> list[dict]:
    """List all footnotes and endnotes with their content.

    Reads from word/footnotes.xml and word/endnotes.xml, matching references
    in the document body. Returns list of dicts with id, type, text, block_id.

    Args:
        pkg: WordPackage
    """
    result = []
    ns = {"w": _FN_W_NS}
    doc_element = pkg.document_xml

    # Build map of reference locations in document (id -> block_id)
    ref_locations: dict[tuple[str, int], str] = {}  # (type, id) -> block_id

    # Find footnote references in document body
    for fn_ref in _fn_xpath(doc_element, ".//w:footnoteReference", ns):
        fn_id = fn_ref.get(qn("w:id"))
        if fn_id:
            # Find containing block
            parent = fn_ref.getparent()
            while parent is not None:
                if parent.tag == qn("w:p"):
                    kind, level = paragraph_kind_and_level(parent)
                    text = get_paragraph_text(parent)
                    occurrence = count_occurrence(pkg, kind, text, parent)
                    block_id = make_block_id(kind, text, occurrence)
                    ref_locations[("footnote", int(fn_id))] = block_id
                    break
                parent = parent.getparent()

    # Find endnote references
    for en_ref in _fn_xpath(doc_element, ".//w:endnoteReference", ns):
        en_id = en_ref.get(qn("w:id"))
        if en_id:
            parent = en_ref.getparent()
            while parent is not None:
                if parent.tag == qn("w:p"):
                    kind, level = paragraph_kind_and_level(parent)
                    text = get_paragraph_text(parent)
                    occurrence = count_occurrence(pkg, kind, text, parent)
                    block_id = make_block_id(kind, text, occurrence)
                    ref_locations[("endnote", int(en_id))] = block_id
                    break
                parent = parent.getparent()

    # Read footnotes from word/footnotes.xml
    fn_root = pkg.footnotes_xml
    if fn_root is not None:
        for fn in _fn_xpath(fn_root, "//w:footnote", ns):
            fn_id_str = fn.get(f"{{{_FN_W_NS}}}id")
            if fn_id_str:
                fn_id = int(fn_id_str)
                if fn_id in _RESERVED_NOTE_IDS:
                    continue  # Skip separators
                text_parts = _fn_xpath(fn, ".//w:t/text()", ns)
                text = "".join(text_parts).strip()
                block_id = ref_locations.get(("footnote", fn_id), "")
                result.append(
                    {
                        "id": fn_id,
                        "type": "footnote",
                        "text": text,
                        "block_id": block_id,
                    }
                )

    # Read endnotes from word/endnotes.xml
    en_root = pkg.endnotes_xml
    if en_root is not None:
        for en in _fn_xpath(en_root, "//w:endnote", ns):
            en_id_str = en.get(f"{{{_FN_W_NS}}}id")
            if en_id_str:
                en_id = int(en_id_str)
                if en_id in _RESERVED_NOTE_IDS:
                    continue  # Skip separators
                text_parts = _fn_xpath(en, ".//w:t/text()", ns)
                text = "".join(text_parts).strip()
                block_id = ref_locations.get(("endnote", en_id), "")
                result.append(
                    {
                        "id": en_id,
                        "type": "endnote",
                        "text": text,
                        "block_id": block_id,
                    }
                )

    return result


# =============================================================================
# Helper Functions for Zipfile Operations
# =============================================================================


def _get_safe_note_id(notes_root, ns: dict) -> int:
    """Get a safe footnote/endnote ID avoiding reserved values.

    Raises:
        ValueError: If an existing note has a malformed (non-integer) ID.
    """
    used_ids: set[int] = set()
    for fn in _fn_xpath(notes_root, "//w:footnote | //w:endnote", ns):
        fn_id = fn.get(f"{{{_FN_W_NS}}}id")
        if fn_id:
            used_ids.add(int(fn_id))  # Let ValueError propagate for malformed IDs

    candidate_id = 1  # User notes start at 1, reserved are -1 and 0
    while candidate_id in used_ids or candidate_id in _RESERVED_NOTE_IDS:
        candidate_id += 1
    return candidate_id


def _ensure_note_content_types(ct_xml: bytes, note_type: str) -> bytes:
    """Ensure content types include footnotes/endnotes."""
    ct_root = etree.fromstring(ct_xml)
    ns = {"ct": _FN_CT_NS}

    part_name = f"/word/{note_type}s.xml"
    if note_type == "footnote":
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"
    else:
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"

    existing = _fn_xpath(ct_root, f"//ct:Override[@PartName='{part_name}']", ns)
    if existing:
        return ct_xml

    override = etree.Element(
        f"{{{_FN_CT_NS}}}Override",
        PartName=part_name,
        ContentType=content_type,
    )
    ct_root.append(override)
    return etree.tostring(
        ct_root, encoding="UTF-8", xml_declaration=True, standalone="yes"
    )


def _ensure_note_relationship(rels_xml: bytes, note_type: str) -> bytes:
    """Ensure document relationships include footnotes/endnotes."""
    rels_root = etree.fromstring(rels_xml)
    ns = {"r": _FN_REL_NS}

    rel_type = f"http://schemas.openxmlformats.org/officeDocument/2006/relationships/{note_type}s"
    existing = _fn_xpath(
        rels_root, f"//r:Relationship[contains(@Type, '{note_type}s')]", ns
    )
    if existing:
        return rels_xml

    # Generate unique rId
    all_rels = _fn_xpath(rels_root, "//r:Relationship", ns)
    existing_ids = {rel.get("Id") for rel in all_rels if rel.get("Id")}
    rid_num = 1
    while f"rId{rid_num}" in existing_ids:
        rid_num += 1

    rel = etree.Element(
        f"{{{_FN_REL_NS}}}Relationship",
        Id=f"rId{rid_num}",
        Type=rel_type,
        Target=f"{note_type}s.xml",
    )
    rels_root.append(rel)
    return etree.tostring(
        rels_root, encoding="UTF-8", xml_declaration=True, standalone="yes"
    )


def _create_minimal_notes_xml(note_type: str) -> bytes:
    """Create minimal footnotes.xml or endnotes.xml with separators."""
    tag = "footnotes" if note_type == "footnote" else "endnotes"
    item = "footnote" if note_type == "footnote" else "endnote"
    xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:{tag} xmlns:w="{_FN_W_NS}">
    <w:{item} w:type="separator" w:id="-1">
        <w:p>
            <w:pPr>
                <w:spacing w:after="0" w:line="240" w:lineRule="auto"/>
            </w:pPr>
            <w:r>
                <w:separator/>
            </w:r>
        </w:p>
    </w:{item}>
    <w:{item} w:type="continuationSeparator" w:id="0">
        <w:p>
            <w:pPr>
                <w:spacing w:after="0" w:line="240" w:lineRule="auto"/>
            </w:pPr>
            <w:r>
                <w:continuationSeparator/>
            </w:r>
        </w:p>
    </w:{item}>
</w:{tag}>'''
    return xml.encode("utf-8")


def _ensure_note_styles(styles_root, note_type: str) -> None:
    """Ensure footnote/endnote styles exist."""
    ns = {"w": _FN_W_NS}
    ref_style_id = f"{note_type.title()}Reference"
    text_style_id = f"{note_type.title()}Text"

    # Check for reference style
    ref_style = _fn_xpath(styles_root, f'//w:style[@w:styleId="{ref_style_id}"]', ns)
    if not ref_style:
        style = etree.Element(
            f"{{{_FN_W_NS}}}style",
            attrib={
                f"{{{_FN_W_NS}}}type": "character",
                f"{{{_FN_W_NS}}}styleId": ref_style_id,
            },
        )
        name = etree.SubElement(style, f"{{{_FN_W_NS}}}name")
        name.set(f"{{{_FN_W_NS}}}val", f"{note_type} reference")
        base = etree.SubElement(style, f"{{{_FN_W_NS}}}basedOn")
        base.set(f"{{{_FN_W_NS}}}val", "DefaultParagraphFont")
        rPr = etree.SubElement(style, f"{{{_FN_W_NS}}}rPr")
        vert_align = etree.SubElement(rPr, f"{{{_FN_W_NS}}}vertAlign")
        vert_align.set(f"{{{_FN_W_NS}}}val", "superscript")
        styles_root.append(style)

    # Check for text style
    text_style = _fn_xpath(styles_root, f'//w:style[@w:styleId="{text_style_id}"]', ns)
    if not text_style:
        style = etree.Element(
            f"{{{_FN_W_NS}}}style",
            attrib={
                f"{{{_FN_W_NS}}}type": "paragraph",
                f"{{{_FN_W_NS}}}styleId": text_style_id,
            },
        )
        name = etree.SubElement(style, f"{{{_FN_W_NS}}}name")
        name.set(f"{{{_FN_W_NS}}}val", f"{note_type} text")
        base = etree.SubElement(style, f"{{{_FN_W_NS}}}basedOn")
        base.set(f"{{{_FN_W_NS}}}val", "Normal")
        pPr = etree.SubElement(style, f"{{{_FN_W_NS}}}pPr")
        sz = etree.SubElement(pPr, f"{{{_FN_W_NS}}}sz")
        sz.set(f"{{{_FN_W_NS}}}val", "20")  # 10pt
        styles_root.append(style)


# =============================================================================
# Add/Delete Footnotes (Zipfile-based)
# =============================================================================


def add_footnote_ooxml(
    pkg: WordPackage,
    target_id: str,
    text: str,
    note_type: str = "footnote",
    position: str = "after",
) -> int:
    """Add a footnote or endnote to an open package (no save).

    Args:
        pkg: Open WordPackage
        target_id: Block ID where the reference should be placed
        text: Content of the footnote/endnote
        note_type: "footnote" or "endnote"
        position: "after" (end of paragraph) or "before" (start)

    Returns:
        The ID of the new footnote/endnote

    Raises:
        ValueError: If target not found or invalid location
    """
    ns = {"w": _FN_W_NS}
    notes_partname = f"/word/{note_type}s.xml"

    # Use resolve_target to get the target paragraph element directly
    try:
        target = resolve_target(pkg, target_id)
    except ValueError as e:
        raise ValueError(f"Target block not found: {target_id}") from e

    # Verify it's a paragraph-type element (headings are also w:p)
    if target.leaf_el.tag != qn("w:p"):
        raise ValueError(f"Target must be a paragraph: {target_id}")

    target_para = target.leaf_el

    # Validate location (not in header/footer)
    parent = target_para.getparent()
    while parent is not None:
        if parent.tag in [qn("w:hdr"), qn("w:ftr")]:
            raise ValueError("Cannot add footnote/endnote in header/footer")
        parent = parent.getparent()

    # Get or create notes XML part
    if note_type == "footnote":
        notes_root = pkg.footnotes_xml
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"
        rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes"
    else:
        notes_root = pkg.endnotes_xml
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"
        rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes"

    if notes_root is None:
        # Create minimal notes XML
        notes_bytes = _create_minimal_notes_xml(note_type)
        notes_root = etree.fromstring(notes_bytes)
        pkg.set_xml(notes_partname, notes_root, content_type)
        # Add relationship from document.xml
        pkg.relate_to("/word/document.xml", f"{note_type}s.xml", rel_type)

    # Get safe note ID
    note_id = _get_safe_note_id(notes_root, ns)

    # Find insertion position in paragraph
    runs = list(target_para.iter(qn("w:r")))
    if position == "after" and runs:
        last_run = runs[-1]
        insert_pos = list(target_para).index(last_run) + 1
    elif position == "before" and runs:
        first_run = runs[0]
        insert_pos = list(target_para).index(first_run)
    else:
        insert_pos = len(target_para)

    # Create footnote reference run in document
    ref_run = etree.Element(qn("w:r"))
    rPr = etree.SubElement(ref_run, qn("w:rPr"))
    rStyle = etree.SubElement(rPr, qn("w:rStyle"))
    rStyle.set(qn("w:val"), f"{note_type.title()}Reference")
    fn_ref = etree.SubElement(ref_run, qn(f"w:{note_type}Reference"))
    fn_ref.set(qn("w:id"), str(note_id))
    target_para.insert(insert_pos, ref_run)

    # Create footnote/endnote content in notes file
    new_note = etree.Element(qn(f"w:{note_type}"))
    new_note.set(qn("w:id"), str(note_id))

    # Add paragraph with content
    fn_para = etree.SubElement(new_note, qn("w:p"))
    pPr = etree.SubElement(fn_para, qn("w:pPr"))
    pStyle = etree.SubElement(pPr, qn("w:pStyle"))
    pStyle.set(qn("w:val"), f"{note_type.title()}Text")

    # Add footnote reference marker
    marker_run = etree.SubElement(fn_para, qn("w:r"))
    marker_rPr = etree.SubElement(marker_run, qn("w:rPr"))
    marker_rStyle = etree.SubElement(marker_rPr, qn("w:rStyle"))
    marker_rStyle.set(qn("w:val"), f"{note_type.title()}Reference")
    etree.SubElement(marker_run, qn(f"w:{note_type}Ref"))

    # Add space
    space_run = etree.SubElement(fn_para, qn("w:r"))
    space_text = etree.SubElement(space_run, qn("w:t"))
    space_text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    space_text.text = " "

    # Add content text
    text_run = etree.SubElement(fn_para, qn("w:r"))
    text_elem = etree.SubElement(text_run, qn("w:t"))
    text_elem.text = text

    notes_root.append(new_note)

    # Ensure styles exist
    styles_root = pkg.styles_xml
    if styles_root is not None:
        _ensure_note_styles(styles_root, note_type)
        pkg.mark_xml_dirty("/word/styles.xml")

    # Mark document and notes as dirty
    mark_dirty(pkg)
    pkg.mark_xml_dirty(notes_partname)
    return note_id


def add_footnote(
    doc_path: str,
    target_id: str,
    text: str,
    note_type: str = "footnote",
    position: str = "after",
) -> int:
    """Add a footnote or endnote to a document (opens, modifies, saves).

    Args:
        doc_path: Path to the Word document
        target_id: Block ID where the reference should be placed
        text: Content of the footnote/endnote
        note_type: "footnote" or "endnote"
        position: "after" (end of paragraph) or "before" (start)

    Returns:
        The ID of the new footnote/endnote

    Raises:
        ValueError: If target not found or invalid location
        FileNotFoundError: If document not found
    """
    pkg = WordPackage.open(doc_path)
    note_id = add_footnote_ooxml(pkg, target_id, text, note_type, position)
    pkg.save(doc_path)
    return note_id


def delete_footnote_ooxml(
    pkg: WordPackage, note_id: int, note_type: str = "footnote"
) -> None:
    """Delete a footnote or endnote from an open package (no save).

    Args:
        pkg: Open WordPackage
        note_id: ID of the footnote/endnote to delete
        note_type: "footnote" or "endnote"

    Raises:
        ValueError: If note not found
    """
    ns = {"w": _FN_W_NS}
    notes_partname = f"/word/{note_type}s.xml"

    # Get notes XML
    notes_root = pkg.footnotes_xml if note_type == "footnote" else pkg.endnotes_xml
    if notes_root is None:
        raise ValueError(f"No {note_type}s in document")

    # Remove reference from document body
    doc_root = pkg.document_xml
    refs_removed = 0
    for fn_ref in _fn_xpath(
        doc_root, f"//w:{note_type}Reference[@w:id='{note_id}']", ns
    ):
        run = fn_ref.getparent()
        if run is not None and run.tag == qn("w:r"):
            para = run.getparent()
            if para is not None:
                para.remove(run)
                refs_removed += 1

    if refs_removed == 0:
        raise ValueError(f"{note_type.title()} {note_id} not found")

    # Remove note content
    for fn in _fn_xpath(notes_root, f"//w:{note_type}[@w:id='{note_id}']", ns):
        notes_root.remove(fn)

    # Mark modified parts as dirty
    mark_dirty(pkg)
    pkg.mark_xml_dirty(notes_partname)


def delete_footnote(doc_path: str, note_id: int, note_type: str = "footnote") -> None:
    """Delete a footnote or endnote from a document (opens, modifies, saves).

    Args:
        doc_path: Path to the Word document
        note_id: ID of the footnote/endnote to delete
        note_type: "footnote" or "endnote"

    Raises:
        ValueError: If note not found
        FileNotFoundError: If document not found
    """
    pkg = WordPackage.open(doc_path)
    delete_footnote_ooxml(pkg, note_id, note_type)
    pkg.save(doc_path)
