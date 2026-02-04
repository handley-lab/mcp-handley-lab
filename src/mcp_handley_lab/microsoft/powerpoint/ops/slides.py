"""Slide operations for PowerPoint."""

from __future__ import annotations

import copy

from lxml import etree

from mcp_handley_lab.microsoft.powerpoint.constants import CT, NSMAP, RT, qn
from mcp_handley_lab.microsoft.powerpoint.models import LayoutInfo, SlideInfo
from mcp_handley_lab.microsoft.powerpoint.ops.core import inches_to_emu
from mcp_handley_lab.microsoft.powerpoint.ops.text import extract_title_text
from mcp_handley_lab.microsoft.powerpoint.package import PowerPointPackage


def list_slides(pkg: PowerPointPackage) -> list[SlideInfo]:
    """List all slides with metadata."""
    slides = []

    for num, _rid, partname in pkg.get_slide_paths():
        slide_xml = pkg.get_xml(partname)

        # Count shapes in spTree
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        shape_count = 0
        if sp_tree is not None:
            # Count direct shape children (excluding nvGrpSpPr which is the tree itself)
            for child in sp_tree:
                tag = etree.QName(child).localname
                if tag in ("sp", "pic", "graphicFrame", "grpSp", "cxnSp"):
                    shape_count += 1

        # Check for notes
        has_notes = pkg.get_notes_xml(num) is not None

        # Get layout name
        layout_name = pkg.get_slide_layout_name(num)

        # Extract title from title placeholder
        title = extract_title_text(slide_xml)

        slides.append(
            SlideInfo(
                number=num,
                title=title,
                shape_count=shape_count,
                has_notes=has_notes,
                layout_name=layout_name,
            )
        )

    return slides


def get_slide_count(pkg: PowerPointPackage) -> int:
    """Get total number of slides."""
    return len(pkg.get_slide_paths())


def get_notes_count(pkg: PowerPointPackage) -> int:
    """Get number of slides with speaker notes."""
    count = 0
    for num, _rid, _partname in pkg.get_slide_paths():
        if pkg.get_notes_xml(num) is not None:
            count += 1
    return count


def list_layouts(pkg: PowerPointPackage) -> list[LayoutInfo]:
    """List all available slide layouts from all slide masters.

    Uses p:sldMasterIdLst for master ordering and p:sldLayoutIdLst for layout
    ordering within each master, as required by OOXML spec.
    """
    pres = pkg.presentation_xml
    layouts = []

    # Iterate over all masters in sldMasterIdLst (preserves ordering)
    sld_master_id_lst = pres.find(qn("p:sldMasterIdLst"), NSMAP)
    if sld_master_id_lst is None:
        return []

    for master_idx, master_id_el in enumerate(
        sld_master_id_lst.findall(qn("p:sldMasterId"), NSMAP)
    ):
        master_rid = master_id_el.get(qn("r:id"))
        if master_rid is None:
            continue

        master_path = pkg.resolve_rel_target(pkg.presentation_path, master_rid)
        master_xml = pkg.get_xml(master_path)

        # Get master name from cSld@name
        master_cSld = master_xml.find(qn("p:cSld"), NSMAP)
        master_name = (
            master_cSld.get("name", f"Master {master_idx + 1}")
            if master_cSld is not None
            else f"Master {master_idx + 1}"
        )

        master_rels = pkg.get_rels(master_path)

        # Use sldLayoutIdLst for proper ordering (not relationship iteration)
        sld_layout_id_lst = master_xml.find(qn("p:sldLayoutIdLst"), NSMAP)
        if sld_layout_id_lst is None:
            continue

        for layout_id_el in sld_layout_id_lst.findall(qn("p:sldLayoutId"), NSMAP):
            layout_rid = layout_id_el.get(qn("r:id"))
            if layout_rid is None or layout_rid not in master_rels:
                continue

            layout_path = pkg.resolve_rel_target(master_path, layout_rid)
            layout_xml = pkg.get_xml(layout_path)

            # Get layout name from cSld@name
            cSld = layout_xml.find(qn("p:cSld"), NSMAP)
            name = cSld.get("name", "Untitled") if cSld is not None else "Untitled"

            # Get layout type from root element attribute
            layout_type = layout_xml.get("type")

            # Collect placeholder info
            sp_tree = layout_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
            placeholder_count = 0
            placeholder_types = []
            if sp_tree is not None:
                for sp in sp_tree.findall(qn("p:sp"), NSMAP):
                    ph = sp.find(
                        qn("p:nvSpPr") + "/" + qn("p:nvPr") + "/" + qn("p:ph"), NSMAP
                    )
                    if ph is not None:
                        placeholder_count += 1
                        ph_type = ph.get("type", "body")
                        placeholder_types.append(ph_type)

            layouts.append(
                LayoutInfo(
                    name=name,
                    type=layout_type,
                    placeholder_count=placeholder_count,
                    placeholder_types=placeholder_types,
                    master_name=master_name,
                    master_index=master_idx,
                )
            )

    return layouts


def add_slide(
    pkg: PowerPointPackage,
    layout_name: str | None = None,
    position: int | None = None,
) -> int:
    """Add a new slide to the presentation.

    Args:
        pkg: PowerPoint package
        layout_name: Layout name to use (default: first layout)
        position: 1-based position to insert (default: end)

    Returns:
        New slide number
    """
    pres = pkg.presentation_xml
    pres_path = pkg.presentation_path
    pres_rels = pkg.get_rels(pres_path)

    # Find layout
    layout_path = _find_layout_by_name(pkg, layout_name)

    # Determine new slide path (avoid collisions after deletions)
    new_slide_path = pkg.next_partname("/ppt/slides/slide", ".xml")

    # Create minimal slide XML
    slide = _create_minimal_slide()
    pkg.set_xml(new_slide_path, slide)

    # Add content type
    from mcp_handley_lab.microsoft.powerpoint.constants import CT

    pkg._content_types[new_slide_path] = CT.PML_SLIDE

    # Add relationship from presentation to slide
    new_rid = pres_rels.get_or_add(RT.SLIDE, new_slide_path)
    pkg._dirty_rels.add(pres_path)

    # Add slide to sldIdLst
    sld_id_lst = pres.find(qn("p:sldIdLst"), NSMAP)
    if sld_id_lst is None:
        sld_id_lst = etree.SubElement(pres, qn("p:sldIdLst"))

    # Generate new slide ID (must be unique, >= 256)
    existing_ids = [int(el.get("id", "0")) for el in sld_id_lst]
    new_id = max(existing_ids, default=255) + 1
    if new_id < 256:
        new_id = 256

    # Create the sldId element
    sld_id = etree.Element(
        qn("p:sldId"),
        id=str(new_id),
        nsmap={"r": NSMAP["r"]},
    )
    sld_id.set(qn("r:id"), new_rid)

    # Insert at position or append to end
    existing_count = len(list(sld_id_lst))
    if position is not None:
        # Clamp position to valid range (1 to existing_count + 1)
        insert_idx = max(0, min(position - 1, existing_count))
        sld_id_lst.insert(insert_idx, sld_id)
    else:
        # Append to end
        sld_id_lst.append(sld_id)

    # Add relationship from slide to layout
    slide_rels = pkg.get_rels(new_slide_path)
    slide_rels.get_or_add(RT.SLIDE_LAYOUT, layout_path)
    pkg._dirty_rels.add(new_slide_path)

    # Mark dirty and invalidate caches
    pkg.mark_xml_dirty(pres_path)
    pkg.invalidate_caches()

    # Determine actual slide number after insertion
    # The slide's position is its index in sldIdLst + 1
    for idx, el in enumerate(sld_id_lst):
        if el.get(qn("r:id")) == new_rid:
            return idx + 1

    # Fallback (should not reach here)
    return existing_count + 1


def delete_slide(pkg: PowerPointPackage, slide_num: int) -> None:
    """Delete a slide from the presentation."""
    pres = pkg.presentation_xml
    pres_path = pkg.presentation_path

    # Find slide info
    slide_paths = pkg.get_slide_paths()
    target = None
    for num, rid, partname in slide_paths:
        if num == slide_num:
            target = (rid, partname)
            break

    if target is None:
        raise KeyError(f"Slide {slide_num} not found")

    rid, partname = target

    # Remove from sldIdLst
    sld_id_lst = pres.find(qn("p:sldIdLst"), NSMAP)
    if sld_id_lst is not None:
        for sld_id in list(sld_id_lst):
            if sld_id.get(qn("r:id")) == rid:
                sld_id_lst.remove(sld_id)
                break

    # Remove relationship
    pres_rels = pkg.get_rels(pres_path)
    pres_rels.remove(rid)

    # Drop the slide part and its relationships
    pkg.drop_part(partname)

    # Mark dirty and invalidate caches
    pkg.mark_xml_dirty(pres_path)
    pkg.invalidate_caches()


def reorder_slide(pkg: PowerPointPackage, slide_num: int, new_position: int) -> None:
    """Move a slide to a new position."""
    pres = pkg.presentation_xml
    pres_path = pkg.presentation_path

    sld_id_lst = pres.find(qn("p:sldIdLst"), NSMAP)
    if sld_id_lst is None:
        raise ValueError("No slides in presentation")

    sld_ids = list(sld_id_lst)
    if slide_num < 1 or slide_num > len(sld_ids):
        raise KeyError(f"Slide {slide_num} not found")
    if new_position < 1 or new_position > len(sld_ids):
        raise ValueError(f"Invalid position {new_position}")

    # Remove from current position (0-indexed)
    element = sld_ids[slide_num - 1]
    sld_id_lst.remove(element)

    # Insert at new position
    sld_id_lst.insert(new_position - 1, element)

    pkg.mark_xml_dirty(pres_path)
    pkg.invalidate_caches()


def set_slide_dimensions(
    pkg: PowerPointPackage,
    preset: str | None = None,
    width: float | None = None,
    height: float | None = None,
) -> None:
    """Set slide dimensions (aspect ratio) for the presentation.

    Either provide a preset or custom width/height in inches. Changing dimensions
    does NOT scale existing content (shapes may go off-canvas).

    Args:
        pkg: PowerPoint package
        preset: Preset aspect ratio ("16:9", "16x9", "wide" or "4:3", "4x3", "standard")
        width: Custom width in inches (requires height)
        height: Custom height in inches (requires width)

    Raises:
        ValueError: If invalid preset, missing width/height, or invalid dimensions
    """
    pres = pkg.presentation_xml
    pres_path = pkg.presentation_path

    # Preset mappings: (cx EMU, cy EMU, type attribute or None for custom)
    PRESETS = {
        "16:9": (12192000, 6858000, "screen16x9"),
        "16x9": (12192000, 6858000, "screen16x9"),
        "wide": (12192000, 6858000, "screen16x9"),
        "4:3": (9144000, 6858000, "screen4x3"),
        "4x3": (9144000, 6858000, "screen4x3"),
        "standard": (9144000, 6858000, "screen4x3"),
    }

    # Determine dimensions
    if preset is not None:
        preset_lower = preset.lower()
        if preset_lower not in PRESETS:
            raise ValueError(
                f"Invalid preset '{preset}'. Use '16:9', '4:3', or custom width/height."
            )
        cx, cy, type_attr = PRESETS[preset_lower]
    elif width is not None and height is not None:
        # Validate custom dimensions
        if width <= 0.1:
            raise ValueError(f"Width must be > 0.1 inches, got {width}")
        if height <= 0.1:
            raise ValueError(f"Height must be > 0.1 inches, got {height}")
        cx = inches_to_emu(width)
        cy = inches_to_emu(height)
        type_attr = None  # Omit type for custom sizes
    else:
        raise ValueError(
            "Must provide either preset or both width and height in inches"
        )

    # Find or create p:sldSz
    sld_sz = pres.find(qn("p:sldSz"), NSMAP)
    if sld_sz is None:
        # Create p:sldSz - insert before p:notesSz if present, otherwise at end
        notes_sz = pres.find(qn("p:notesSz"), NSMAP)
        sld_sz = etree.Element(qn("p:sldSz"))
        if notes_sz is not None:
            notes_sz.addprevious(sld_sz)
        else:
            pres.append(sld_sz)

    # Update attributes
    sld_sz.set("cx", str(cx))
    sld_sz.set("cy", str(cy))

    # Set or remove type attribute
    if type_attr is not None:
        sld_sz.set("type", type_attr)
    elif "type" in sld_sz.attrib:
        del sld_sz.attrib["type"]

    pkg.mark_xml_dirty(pres_path)


def duplicate_slide(
    pkg: PowerPointPackage,
    source_num: int,
    position: int | None = None,
) -> int:
    """Duplicate a slide.

    Creates a copy of the source slide with all its relationships (except notes
    and comments). Shared parts like layouts, masters, themes, and media are
    reused (not duplicated).

    Args:
        pkg: PowerPoint package
        source_num: Source slide number (1-based)
        position: Position to insert (1-based, None = end)

    Returns:
        New slide number

    Raises:
        KeyError: If source slide not found
    """
    pres = pkg.presentation_xml
    pres_path = pkg.presentation_path
    pres_rels = pkg.get_rels(pres_path)

    # Get source slide info
    source_path = pkg.get_slide_partname(source_num)
    source_xml = pkg.get_slide_xml(source_num)
    source_rels = pkg.get_rels(source_path)

    # Determine new slide path (avoid collisions)
    new_slide_path = pkg.next_partname("/ppt/slides/slide", ".xml")

    # Copy slide XML (deep copy)
    new_slide_xml = copy.deepcopy(source_xml)
    pkg.set_xml(new_slide_path, new_slide_xml)

    # Register content type
    pkg._content_types[new_slide_path] = CT.PML_SLIDE

    # Copy relationships (except notes and comments)
    new_slide_rels = pkg.get_rels(new_slide_path)
    excluded_reltypes = {RT.NOTES_SLIDE, RT.COMMENTS}

    for rel in source_rels.values():
        if rel.reltype in excluded_reltypes:
            continue
        # Preserve target and external flag
        new_slide_rels.add(rel.reltype, rel.target, rel.is_external)

    pkg._dirty_rels.add(new_slide_path)

    # Add relationship from presentation to new slide
    new_rid = pres_rels.add(RT.SLIDE, new_slide_path)
    pkg._dirty_rels.add(pres_path)

    # Add to sldIdLst
    sld_id_lst = pres.find(qn("p:sldIdLst"), NSMAP)
    if sld_id_lst is None:
        sld_id_lst = etree.SubElement(pres, qn("p:sldIdLst"))

    # Generate new slide ID (must be unique, >= 256)
    existing_ids = [int(el.get("id", "0")) for el in sld_id_lst]
    new_id = max(existing_ids, default=255) + 1
    if new_id < 256:
        new_id = 256

    # Create the sldId element
    sld_id = etree.Element(
        qn("p:sldId"),
        id=str(new_id),
        nsmap={"r": NSMAP["r"]},
    )
    sld_id.set(qn("r:id"), new_rid)

    # Insert at position or append to end
    existing_count = len(list(sld_id_lst))
    if position is not None:
        # Clamp position to valid range (1 to existing_count + 1)
        insert_idx = max(0, min(position - 1, existing_count))
        sld_id_lst.insert(insert_idx, sld_id)
    else:
        # Append to end
        sld_id_lst.append(sld_id)

    # Mark dirty and invalidate caches
    pkg.mark_xml_dirty(pres_path)
    pkg.invalidate_caches()

    # Determine actual slide number after insertion
    for idx, el in enumerate(sld_id_lst):
        if el.get(qn("r:id")) == new_rid:
            return idx + 1

    # Fallback (should not reach here)
    return existing_count + 1


def _find_layout_by_name(pkg: PowerPointPackage, layout_name: str | None) -> str:
    """Find layout path by name, or return first layout if name is None.

    Uses sldMasterIdLst and sldLayoutIdLst for proper OOXML spec ordering,
    supporting multi-master presentations.
    """
    pres = pkg.presentation_xml

    # Iterate over all masters in sldMasterIdLst (preserves ordering)
    sld_master_id_lst = pres.find(qn("p:sldMasterIdLst"), NSMAP)
    if sld_master_id_lst is None:
        raise ValueError("No slide masters found in presentation")

    first_layout_path = None

    for master_id_el in sld_master_id_lst.findall(qn("p:sldMasterId"), NSMAP):
        master_rid = master_id_el.get(qn("r:id"))
        if master_rid is None:
            continue

        master_path = pkg.resolve_rel_target(pkg.presentation_path, master_rid)
        master_xml = pkg.get_xml(master_path)
        master_rels = pkg.get_rels(master_path)

        # Use sldLayoutIdLst for proper ordering (not relationship iteration)
        sld_layout_id_lst = master_xml.find(qn("p:sldLayoutIdLst"), NSMAP)
        if sld_layout_id_lst is None:
            continue

        for layout_id_el in sld_layout_id_lst.findall(qn("p:sldLayoutId"), NSMAP):
            layout_rid = layout_id_el.get(qn("r:id"))
            if layout_rid is None or layout_rid not in master_rels:
                continue

            layout_path = pkg.resolve_rel_target(master_path, layout_rid)

            # Track the first layout found (for None case)
            if first_layout_path is None:
                first_layout_path = layout_path

            # If no name specified, return first layout
            if layout_name is None:
                return layout_path

            # Check if this layout matches the requested name
            layout_xml = pkg.get_xml(layout_path)
            cSld = layout_xml.find(qn("p:cSld"), NSMAP)
            if cSld is not None and cSld.get("name") == layout_name:
                return layout_path

    if layout_name is None:
        if first_layout_path is not None:
            return first_layout_path
        raise ValueError("No layouts found in any slide master")

    raise KeyError(f"Layout '{layout_name}' not found")


def _create_minimal_slide() -> etree._Element:
    """Create minimal valid slide XML."""
    slide = etree.Element(
        qn("p:sld"),
        nsmap={
            "p": NSMAP["p"],
            "a": NSMAP["a"],
            "r": NSMAP["r"],
        },
    )

    cSld = etree.SubElement(slide, qn("p:cSld"))
    spTree = etree.SubElement(cSld, qn("p:spTree"))

    # Group shape properties (required)
    nvGrpSpPr = etree.SubElement(spTree, qn("p:nvGrpSpPr"))
    etree.SubElement(nvGrpSpPr, qn("p:cNvPr"), id="1", name="")
    etree.SubElement(nvGrpSpPr, qn("p:cNvGrpSpPr"))
    etree.SubElement(nvGrpSpPr, qn("p:nvPr"))

    etree.SubElement(spTree, qn("p:grpSpPr"))

    return slide


def hide_slide(pkg: PowerPointPackage, slide_num: int, hidden: bool = True) -> None:
    """Hide or show a slide.

    Hidden slides are skipped during slideshow playback but remain visible
    in editing mode (typically shown grayed out).

    Args:
        pkg: PowerPoint package
        slide_num: Slide number (1-based)
        hidden: True to hide, False to show

    Raises:
        ValueError: If slide not found
    """
    pres = pkg.presentation_xml
    pres_path = pkg.presentation_path

    sld_id_lst = pres.find(qn("p:sldIdLst"), NSMAP)
    if sld_id_lst is None:
        raise ValueError("Presentation has no slide list")

    # Find the sldId element at the given position
    sld_ids = list(sld_id_lst.findall(qn("p:sldId"), NSMAP))
    if slide_num < 1 or slide_num > len(sld_ids):
        raise ValueError(
            f"Slide {slide_num} not found (presentation has {len(sld_ids)} slides)"
        )

    sld_id = sld_ids[slide_num - 1]

    # Set or remove the show attribute
    if hidden:
        sld_id.set("show", "0")
    else:
        # Remove show attribute to show slide (show="1" is default)
        sld_id.attrib.pop("show", None)

    pkg.mark_xml_dirty(pres_path)


def is_slide_hidden(pkg: PowerPointPackage, slide_num: int) -> bool:
    """Check if a slide is hidden.

    Args:
        pkg: PowerPoint package
        slide_num: Slide number (1-based)

    Returns:
        True if hidden, False if visible

    Raises:
        ValueError: If slide not found
    """
    pres = pkg.presentation_xml

    sld_id_lst = pres.find(qn("p:sldIdLst"), NSMAP)
    if sld_id_lst is None:
        raise ValueError("Presentation has no slide list")

    sld_ids = list(sld_id_lst.findall(qn("p:sldId"), NSMAP))
    if slide_num < 1 or slide_num > len(sld_ids):
        raise ValueError(
            f"Slide {slide_num} not found (presentation has {len(sld_ids)} slides)"
        )

    sld_id = sld_ids[slide_num - 1]
    return sld_id.get("show") == "0"
