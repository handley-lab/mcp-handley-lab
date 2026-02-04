"""Placeholder operations for PowerPoint."""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.powerpoint.constants import NSMAP, RT, qn
from mcp_handley_lab.microsoft.powerpoint.ops.text import set_shape_text
from mcp_handley_lab.microsoft.powerpoint.package import PowerPointPackage


def find_placeholder(
    pkg: PowerPointPackage,
    slide_num: int,
    placeholder_type: str | None = None,
    idx: int | None = None,
) -> etree._Element | None:
    """Find placeholder on slide by type or idx.

    Resolution chain: slide → layout → master.
    Returns the shape element if found, None otherwise.
    """
    slide_xml = pkg.get_slide_xml(slide_num)
    slide_partname = pkg.get_slide_partname(slide_num)

    # Try to find on slide first
    placeholder = _find_placeholder_in_part(slide_xml, placeholder_type, idx)
    if placeholder is not None:
        return placeholder

    # Try layout
    slide_rels = pkg.get_rels(slide_partname)
    layout_rid = slide_rels.rId_for_reltype(RT.SLIDE_LAYOUT)
    if layout_rid:
        layout_path = pkg.resolve_rel_target(slide_partname, layout_rid)
        layout_xml = pkg.get_xml(layout_path)
        placeholder = _find_placeholder_in_part(layout_xml, placeholder_type, idx)
        if placeholder is not None:
            # Return None - we found it in layout but need to materialize on slide
            return None

    # Try master
    if layout_rid:
        layout_rels = pkg.get_rels(layout_path)
        master_rid = layout_rels.rId_for_reltype(RT.SLIDE_MASTER)
        if master_rid:
            master_path = pkg.resolve_rel_target(layout_path, master_rid)
            master_xml = pkg.get_xml(master_path)
            placeholder = _find_placeholder_in_part(master_xml, placeholder_type, idx)
            # Return None - we found it in master but need to materialize on slide

    return None


def _find_placeholder_in_part(
    part_xml: etree._Element,
    placeholder_type: str | None = None,
    idx: int | None = None,
) -> etree._Element | None:
    """Find placeholder in a slide/layout/master part."""
    sp_tree = part_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        return None

    for sp in sp_tree.findall(qn("p:sp"), NSMAP):
        nvSpPr = sp.find(qn("p:nvSpPr"), NSMAP)
        if nvSpPr is None:
            continue

        nvPr = nvSpPr.find(qn("p:nvPr"), NSMAP)
        if nvPr is None:
            continue

        ph = nvPr.find(qn("p:ph"), NSMAP)
        if ph is None:
            continue

        ph_type = ph.get("type")
        ph_idx_str = ph.get("idx")
        ph_idx = int(ph_idx_str) if ph_idx_str else None

        # Match by type
        if placeholder_type is not None:
            if ph_type == placeholder_type:
                return sp
            # Handle common aliases
            if placeholder_type == "title" and ph_type in ("title", "ctrTitle"):
                return sp
            if placeholder_type == "subtitle" and ph_type == "subTitle":
                return sp
            if placeholder_type == "body" and ph_type in ("body", "obj"):
                return sp

        # Match by idx
        if idx is not None and ph_idx == idx:
            return sp

    return None


def set_placeholder_text(
    pkg: PowerPointPackage,
    slide_num: int,
    text: str,
    placeholder_type: str | None = None,
    idx: int | None = None,
) -> None:
    """Set text in a placeholder.

    If placeholder exists on slide, updates it.
    If placeholder is inherited from layout/master, materializes it on slide.

    Raises:
        ValueError: If placeholder_type and idx are both None, or placeholder not found.
    """
    if placeholder_type is None and idx is None:
        raise ValueError("Must specify placeholder_type or idx")

    slide_xml = pkg.get_slide_xml(slide_num)
    slide_partname = pkg.get_slide_partname(slide_num)

    # Find placeholder on slide
    placeholder = _find_placeholder_in_part(slide_xml, placeholder_type, idx)

    if placeholder is not None:
        # Update existing placeholder
        set_shape_text(placeholder, text)
        pkg.mark_xml_dirty(slide_partname)
        return

    # Not on slide - try to get from layout and materialize
    slide_rels = pkg.get_rels(slide_partname)
    layout_rid = slide_rels.rId_for_reltype(RT.SLIDE_LAYOUT)
    if layout_rid is None:
        raise ValueError(f"Slide {slide_num} has no layout relationship")

    layout_path = pkg.resolve_rel_target(slide_partname, layout_rid)
    layout_xml = pkg.get_xml(layout_path)

    layout_placeholder = _find_placeholder_in_part(layout_xml, placeholder_type, idx)
    if layout_placeholder is None:
        # Try master
        layout_rels = pkg.get_rels(layout_path)
        master_rid = layout_rels.rId_for_reltype(RT.SLIDE_MASTER)
        if master_rid:
            master_path = pkg.resolve_rel_target(layout_path, master_rid)
            master_xml = pkg.get_xml(master_path)
            layout_placeholder = _find_placeholder_in_part(
                master_xml, placeholder_type, idx
            )

    if layout_placeholder is None:
        ph_desc = f"type={placeholder_type}" if placeholder_type else f"idx={idx}"
        raise ValueError(f"Placeholder {ph_desc} not found on slide {slide_num}")

    # Materialize placeholder on slide
    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        raise ValueError(f"Slide {slide_num} has no shape tree")

    new_sp = _materialize_placeholder(layout_placeholder, sp_tree)
    set_shape_text(new_sp, text)
    pkg.mark_xml_dirty(slide_partname)


def _materialize_placeholder(
    template: etree._Element,
    sp_tree: etree._Element,
) -> etree._Element:
    """Create a new placeholder shape on slide based on layout/master template."""
    sp = etree.SubElement(sp_tree, qn("p:sp"))

    # Copy nvSpPr (but generate new id)
    template_nvSpPr = template.find(qn("p:nvSpPr"), NSMAP)
    nvSpPr = etree.SubElement(sp, qn("p:nvSpPr"))

    # Get next available ID
    max_id = 0
    for existing in sp_tree.findall(".//" + qn("p:cNvPr"), NSMAP):
        id_str = existing.get("id", "0")
        if id_str.isdigit():
            max_id = max(max_id, int(id_str))
    new_id = str(max_id + 1)

    # Copy cNvPr with new id
    template_cNvPr = template_nvSpPr.find(qn("p:cNvPr"), NSMAP)
    cNvPr = etree.SubElement(nvSpPr, qn("p:cNvPr"))
    cNvPr.set("id", new_id)
    cNvPr.set("name", template_cNvPr.get("name", ""))

    # Copy cNvSpPr
    template_cNvSpPr = template_nvSpPr.find(qn("p:cNvSpPr"), NSMAP)
    if template_cNvSpPr is not None:
        nvSpPr.append(template_cNvSpPr.__copy__())
    else:
        etree.SubElement(nvSpPr, qn("p:cNvSpPr"))

    # Copy nvPr (with placeholder info)
    template_nvPr = template_nvSpPr.find(qn("p:nvPr"), NSMAP)
    if template_nvPr is not None:
        nvPr = template_nvPr.__copy__()
        nvSpPr.append(nvPr)
    else:
        etree.SubElement(nvSpPr, qn("p:nvPr"))

    # spPr - copy from template if it has geometry, otherwise empty (inherits from layout)
    template_spPr = template.find(qn("p:spPr"), NSMAP)
    if template_spPr is not None:
        # Deep copy to get all geometry including xfrm
        spPr = template_spPr.__copy__()
        sp.append(spPr)
    else:
        etree.SubElement(sp, qn("p:spPr"))

    # txBody with empty paragraph
    txBody = etree.SubElement(sp, qn("p:txBody"))
    etree.SubElement(txBody, qn("a:bodyPr"))
    etree.SubElement(txBody, qn("a:lstStyle"))
    p = etree.SubElement(txBody, qn("a:p"))
    etree.SubElement(p, qn("a:endParaRPr"), lang="en-US")

    return sp
