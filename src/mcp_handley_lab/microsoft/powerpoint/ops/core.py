"""Core utilities for PowerPoint operations."""

from __future__ import annotations

import hashlib
from typing import Any

from lxml import etree

from mcp_handley_lab.microsoft.powerpoint.constants import EMU_PER_INCH, NSMAP, qn

# EMU conversion


def emu_to_inches(emu: int) -> float:
    """Convert EMUs to inches."""
    return emu / EMU_PER_INCH


def inches_to_emu(inches: float) -> int:
    """Convert inches to EMUs."""
    return int(inches * EMU_PER_INCH)


# Shape position extraction


def get_shape_position(
    shape: etree._Element, parent_transform: tuple[int, int, float, float] | None = None
) -> tuple[int, int, int, int] | None:
    """Get shape position (x, y, cx, cy) in EMUs with group transform composition.

    Args:
        shape: Shape element (p:sp, p:pic, p:graphicFrame, p:grpSp)
        parent_transform: Optional (off_x, off_y, scale_x, scale_y) from parent group

    Returns:
        (x, y, width, height) in EMUs, or None if no transform found
    """
    # Find the transform element
    xfrm = None

    # For shapes: p:spPr/a:xfrm
    spPr = shape.find(qn("p:spPr"), NSMAP)
    if spPr is not None:
        xfrm = spPr.find(qn("a:xfrm"), NSMAP)

    # For groups: p:grpSpPr/a:xfrm
    if xfrm is None:
        grpSpPr = shape.find(qn("p:grpSpPr"), NSMAP)
        if grpSpPr is not None:
            xfrm = grpSpPr.find(qn("a:xfrm"), NSMAP)

    # For graphic frames: p:xfrm (direct child)
    if xfrm is None:
        xfrm = shape.find(qn("p:xfrm"), NSMAP)

    if xfrm is None:
        return None

    off = xfrm.find(qn("a:off"), NSMAP)
    ext = xfrm.find(qn("a:ext"), NSMAP)

    if off is None or ext is None:
        return None

    x = int(off.get("x", "0"))
    y = int(off.get("y", "0"))
    cx = int(ext.get("cx", "0"))
    cy = int(ext.get("cy", "0"))

    # Apply parent transform if present (for group children)
    if parent_transform is not None:
        off_x, off_y, scale_x, scale_y = parent_transform
        x = off_x + int(x * scale_x)
        y = off_y + int(y * scale_y)
        cx = int(cx * scale_x)
        cy = int(cy * scale_y)

    return (x, y, cx, cy)


def get_group_transform(grpSp: etree._Element) -> tuple[int, int, float, float] | None:
    """Get group transform parameters for composing child positions.

    Returns (off_x, off_y, scale_x, scale_y) or None if not a valid group.
    """
    grpSpPr = grpSp.find(qn("p:grpSpPr"), NSMAP)
    if grpSpPr is None:
        return None

    xfrm = grpSpPr.find(qn("a:xfrm"), NSMAP)
    if xfrm is None:
        return None

    off = xfrm.find(qn("a:off"), NSMAP)
    ext = xfrm.find(qn("a:ext"), NSMAP)
    chOff = xfrm.find(qn("a:chOff"), NSMAP)
    chExt = xfrm.find(qn("a:chExt"), NSMAP)

    if off is None or ext is None:
        return None

    off_x = int(off.get("x", "0"))
    off_y = int(off.get("y", "0"))

    # Calculate scale factors if child extents differ from group extents
    if chOff is not None and chExt is not None:
        ch_off_x = int(chOff.get("x", "0"))
        ch_off_y = int(chOff.get("y", "0"))
        ch_ext_cx = int(chExt.get("cx", "1"))
        ch_ext_cy = int(chExt.get("cy", "1"))
        ext_cx = int(ext.get("cx", "1"))
        ext_cy = int(ext.get("cy", "1"))

        scale_x = ext_cx / ch_ext_cx if ch_ext_cx else 1.0
        scale_y = ext_cy / ch_ext_cy if ch_ext_cy else 1.0

        # Adjust offset for child coordinate system
        off_x -= int(ch_off_x * scale_x)
        off_y -= int(ch_off_y * scale_y)
    else:
        scale_x = 1.0
        scale_y = 1.0

    return (off_x, off_y, scale_x, scale_y)


# Shape identification


def get_shape_id(shape: etree._Element) -> int | None:
    """Get the intrinsic shape ID from cNvPr@id."""
    nvSpPr = shape.find(qn("p:nvSpPr"), NSMAP)
    if nvSpPr is None:
        nvSpPr = shape.find(qn("p:nvPicPr"), NSMAP)
    if nvSpPr is None:
        nvSpPr = shape.find(qn("p:nvGrpSpPr"), NSMAP)
    if nvSpPr is None:
        nvSpPr = shape.find(qn("p:nvGraphicFramePr"), NSMAP)
    if nvSpPr is None:
        nvSpPr = shape.find(qn("p:nvCxnSpPr"), NSMAP)

    if nvSpPr is None:
        return None

    cNvPr = nvSpPr.find(qn("p:cNvPr"), NSMAP)
    if cNvPr is None:
        return None

    id_attr = cNvPr.get("id")
    return int(id_attr) if id_attr else None


def get_shape_name(shape: etree._Element) -> str | None:
    """Get the shape name from cNvPr@name."""
    nvSpPr = shape.find(qn("p:nvSpPr"), NSMAP)
    if nvSpPr is None:
        nvSpPr = shape.find(qn("p:nvPicPr"), NSMAP)
    if nvSpPr is None:
        nvSpPr = shape.find(qn("p:nvGrpSpPr"), NSMAP)
    if nvSpPr is None:
        nvSpPr = shape.find(qn("p:nvGraphicFramePr"), NSMAP)
    if nvSpPr is None:
        nvSpPr = shape.find(qn("p:nvCxnSpPr"), NSMAP)

    if nvSpPr is None:
        return None

    cNvPr = nvSpPr.find(qn("p:cNvPr"), NSMAP)
    if cNvPr is None:
        return None

    return cNvPr.get("name")


def find_shape_by_id(slide_xml: etree._Element, shape_id: int) -> etree._Element | None:
    """Find a shape element by its ID in a slide (recursive, searches groups).

    Searches all shape types: p:sp, p:pic, p:graphicFrame, p:grpSp, p:cxnSp.

    Args:
        slide_xml: Slide XML element
        shape_id: Shape ID to find

    Returns:
        Shape element or None if not found
    """
    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        return None

    return find_shape_in_tree(sp_tree, shape_id)


def find_shape_in_tree(
    container: etree._Element, shape_id: int
) -> etree._Element | None:
    """Find a shape by ID within a shape tree or group (recursive).

    Args:
        container: Shape tree (p:spTree) or group element to search
        shape_id: Shape ID to find

    Returns:
        Shape element or None if not found
    """
    shape_tags = {"sp", "pic", "graphicFrame", "grpSp", "cxnSp"}

    for child in container:
        tag = etree.QName(child).localname
        if tag not in shape_tags:
            continue

        # Check this shape's id
        if get_shape_id(child) == shape_id:
            return child

        # Recursively search groups
        if tag == "grpSp":
            found = find_shape_in_tree(child, shape_id)
            if found is not None:
                return found

    return None


def make_shape_key(slide_num: int, shape_id: int) -> str:
    """Create stable shape key for edit targeting."""
    return f"{slide_num}:{shape_id}"


def parse_shape_key(shape_key: str) -> tuple[int, int]:
    """Parse shape key into (slide_num, shape_id)."""
    parts = shape_key.split(":")
    return (int(parts[0]), int(parts[1]))


# Content-addressed IDs (for reference, not edit targeting)


def make_content_id(content: str) -> str:
    """Create content-addressed ID from content hash."""
    return hashlib.md5(content.encode()).hexdigest()[:8]


# Placeholder detection


def get_placeholder_info(shape: etree._Element) -> tuple[str | None, int | None]:
    """Get placeholder (type, idx) from shape.

    Returns (None, None) if not a placeholder.
    """
    nvSpPr = shape.find(qn("p:nvSpPr"), NSMAP)
    if nvSpPr is None:
        return (None, None)

    nvPr = nvSpPr.find(qn("p:nvPr"), NSMAP)
    if nvPr is None:
        return (None, None)

    ph = nvPr.find(qn("p:ph"), NSMAP)
    if ph is None:
        return (None, None)

    ph_type = ph.get("type")
    idx_str = ph.get("idx")
    idx = int(idx_str) if idx_str else None

    return (ph_type, idx)


# Z-order (document order in spTree)


def get_z_order(shape: etree._Element, sp_tree: etree._Element) -> int:
    """Get z-order (document position) of shape within spTree."""
    shapes = list(sp_tree)
    try:
        return shapes.index(shape)
    except ValueError:
        return -1


# Spatial sorting


def spatial_sort_key(
    item: dict[str, Any],
) -> tuple[float, float, int, int]:
    """Sort key for spatial ordering: (y, x, z_order, shape_id)."""
    return (
        item.get("y_inches", 0.0),
        item.get("x_inches", 0.0),
        item.get("z_order", 0),
        item.get("shape_id", 0),
    )


def spatial_sort_shapes(shapes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort shapes by spatial position for natural reading order.

    Sort order: top-to-bottom (y), left-to-right (x), z-order, shape_id.
    """
    return sorted(shapes, key=spatial_sort_key)
