"""Shape operations for PowerPoint."""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.powerpoint.constants import NSMAP, qn
from mcp_handley_lab.microsoft.powerpoint.models import ShapeInfo
from mcp_handley_lab.microsoft.powerpoint.ops.core import (
    emu_to_inches,
    find_shape_by_id,
    get_group_transform,
    get_placeholder_info,
    get_shape_id,
    get_shape_name,
    get_shape_position,
    inches_to_emu,
    make_shape_key,
    parse_shape_key,
    spatial_sort_shapes,
)
from mcp_handley_lab.microsoft.powerpoint.ops.text import (
    extract_text_from_shape,
    set_shape_text,
)
from mcp_handley_lab.microsoft.powerpoint.package import PowerPointPackage


def get_shape_type(shape: etree._Element) -> str:
    """Determine shape type from element tag."""
    tag = etree.QName(shape).localname

    if tag == "sp":
        return "shape"
    elif tag == "pic":
        return "picture"
    elif tag == "graphicFrame":
        # Could be table, chart, diagram, etc.
        # Check for specific content
        tbl = shape.find(".//" + qn("a:tbl"), NSMAP)
        if tbl is not None:
            return "table"
        chart = shape.find(
            ".//" + qn("c:chart"),
            {"c": "http://schemas.openxmlformats.org/drawingml/2006/chart"},
        )
        if chart is not None:
            return "chart"
        return "frame"
    elif tag == "grpSp":
        return "group"
    elif tag == "cxnSp":
        return "connector"

    return "unknown"


def _parse_shape(
    shape: etree._Element,
    slide_num: int,
    z_order: int,
    parent_transform: tuple[int, int, float, float] | None = None,
) -> ShapeInfo | None:
    """Parse a single shape into ShapeInfo."""
    shape_id = get_shape_id(shape)
    if shape_id is None:
        return None

    position = get_shape_position(shape, parent_transform)
    position_inherited = position is None

    # Shapes without local xfrm inherit position from layout/master
    # Use (0, 0, 0, 0) as default - actual position comes from layout
    if position_inherited:
        x, y, cx, cy = 0, 0, 0, 0
    else:
        x, y, cx, cy = position

    shape_type = get_shape_type(shape)
    shape_name = get_shape_name(shape)
    text = extract_text_from_shape(shape)
    ph_type, ph_idx = get_placeholder_info(shape)

    return ShapeInfo(
        shape_key=make_shape_key(slide_num, shape_id),
        shape_id=shape_id,
        type=shape_type,
        name=shape_name,
        x_inches=emu_to_inches(x),
        y_inches=emu_to_inches(y),
        width_inches=emu_to_inches(cx),
        height_inches=emu_to_inches(cy),
        position_inherited=position_inherited,
        z_order=z_order,
        text=text if text else None,
        placeholder_type=ph_type,
        placeholder_idx=ph_idx,
    )


def _collect_shapes_recursive(
    parent: etree._Element,
    slide_num: int,
    z_counter: list[int],
    parent_transform: tuple[int, int, float, float] | None = None,
) -> list[ShapeInfo]:
    """Recursively collect shapes, handling groups with transform composition."""
    shapes = []
    shape_tags = {"sp", "pic", "graphicFrame", "grpSp", "cxnSp"}

    for child in parent:
        tag = etree.QName(child).localname
        if tag not in shape_tags:
            continue

        z_order = z_counter[0]
        z_counter[0] += 1

        if tag == "grpSp":
            # Group: get transform and recurse
            group_transform = get_group_transform(child)

            # Compose with parent transform if present
            if parent_transform is not None and group_transform is not None:
                off_x, off_y, scale_x, scale_y = group_transform
                p_off_x, p_off_y, p_scale_x, p_scale_y = parent_transform
                composed = (
                    p_off_x + int(off_x * p_scale_x),
                    p_off_y + int(off_y * p_scale_y),
                    scale_x * p_scale_x,
                    scale_y * p_scale_y,
                )
            else:
                composed = group_transform or parent_transform

            # Add group shape itself
            shape_info = _parse_shape(child, slide_num, z_order, parent_transform)
            if shape_info:
                shapes.append(shape_info)

            # Recurse into group children
            child_shapes = _collect_shapes_recursive(
                child, slide_num, z_counter, composed
            )
            shapes.extend(child_shapes)
        else:
            # Regular shape
            shape_info = _parse_shape(child, slide_num, z_order, parent_transform)
            if shape_info:
                shapes.append(shape_info)

    return shapes


def list_shapes(pkg: PowerPointPackage, slide_num: int) -> list[ShapeInfo]:
    """List all shapes on a slide, spatially sorted.

    Shapes are sorted by (y, x, z_order, shape_id) for natural reading order.
    Group children are included with composed transforms for accurate positioning.
    """
    slide_xml = pkg.get_slide_xml(slide_num)

    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        return []

    # Collect all shapes with z-order
    z_counter = [0]
    shapes = _collect_shapes_recursive(sp_tree, slide_num, z_counter)

    # Convert to dict for sorting
    shape_dicts = [s.model_dump() for s in shapes]

    # Spatial sort
    sorted_dicts = spatial_sort_shapes(shape_dicts)

    # Assign reading order and convert back
    result = []
    for idx, d in enumerate(sorted_dicts):
        d["reading_order"] = idx
        result.append(ShapeInfo(**d))

    return result


def get_text_in_reading_order(pkg: PowerPointPackage, slide_num: int) -> str:
    """Get all text from a slide in spatial reading order."""
    shapes = list_shapes(pkg, slide_num)
    texts = []

    for shape in shapes:
        if shape.text:
            texts.append(shape.text)

    return "\n\n".join(texts)


def _find_shape_by_id(sp_tree: etree._Element, shape_id: int) -> etree._Element | None:
    """Find a shape element by its cNvPr id."""
    shape_tags = {"sp", "pic", "graphicFrame", "grpSp", "cxnSp"}

    for child in sp_tree:
        tag = etree.QName(child).localname
        if tag not in shape_tags:
            continue

        # Check this shape's id
        nvSpPr = child.find(qn("p:nvSpPr"), NSMAP)
        if nvSpPr is None:
            nvSpPr = child.find(qn("p:nvPicPr"), NSMAP)
        if nvSpPr is None:
            nvSpPr = child.find(qn("p:nvGraphicFramePr"), NSMAP)
        if nvSpPr is None:
            nvSpPr = child.find(qn("p:nvGrpSpPr"), NSMAP)
        if nvSpPr is None:
            nvSpPr = child.find(qn("p:nvCxnSpPr"), NSMAP)

        if nvSpPr is not None:
            cNvPr = nvSpPr.find(qn("p:cNvPr"), NSMAP)
            if cNvPr is not None:
                id_str = cNvPr.get("id")
                if id_str and id_str.isdigit() and int(id_str) == shape_id:
                    return child

        # Recurse into groups
        if tag == "grpSp":
            found = _find_shape_by_id(child, shape_id)
            if found is not None:
                return found

    return None


def _get_next_shape_id(sp_tree: etree._Element) -> int:
    """Get the next available shape ID."""
    max_id = 0
    for cNvPr in sp_tree.findall(".//" + qn("p:cNvPr"), NSMAP):
        id_str = cNvPr.get("id", "0")
        if id_str.isdigit():
            max_id = max(max_id, int(id_str))
    return max_id + 1


def add_shape(
    pkg: PowerPointPackage,
    slide_num: int,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str = "",
) -> str:
    """Add a new text box shape to a slide.

    Args:
        pkg: PowerPoint package
        slide_num: 1-based slide number
        x: X position in inches
        y: Y position in inches
        width: Width in inches
        height: Height in inches
        text: Initial text content

    Returns:
        shape_key for the new shape (slide_num:shape_id)
    """
    slide_xml = pkg.get_slide_xml(slide_num)
    slide_partname = pkg.get_slide_partname(slide_num)

    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        raise ValueError(f"Slide {slide_num} has no shape tree")

    # Get next shape ID
    shape_id = _get_next_shape_id(sp_tree)

    # Create shape element
    sp = etree.SubElement(sp_tree, qn("p:sp"))

    # Non-visual properties
    nvSpPr = etree.SubElement(sp, qn("p:nvSpPr"))
    etree.SubElement(
        nvSpPr, qn("p:cNvPr"), id=str(shape_id), name=f"TextBox {shape_id}"
    )
    etree.SubElement(nvSpPr, qn("p:cNvSpPr"), txBox="1")
    etree.SubElement(nvSpPr, qn("p:nvPr"))

    # Shape properties with position/size
    spPr = etree.SubElement(sp, qn("p:spPr"))
    xfrm = etree.SubElement(spPr, qn("a:xfrm"))
    etree.SubElement(
        xfrm,
        qn("a:off"),
        x=str(inches_to_emu(x)),
        y=str(inches_to_emu(y)),
    )
    etree.SubElement(
        xfrm,
        qn("a:ext"),
        cx=str(inches_to_emu(width)),
        cy=str(inches_to_emu(height)),
    )

    # Preset geometry (rectangle)
    prstGeom = etree.SubElement(spPr, qn("a:prstGeom"), prst="rect")
    etree.SubElement(prstGeom, qn("a:avLst"))

    # Text body
    txBody = etree.SubElement(sp, qn("p:txBody"))
    etree.SubElement(txBody, qn("a:bodyPr"), wrap="square", rtlCol="0")
    etree.SubElement(txBody, qn("a:lstStyle"))

    # Add text if provided
    if text:
        set_shape_text(sp, text)
    else:
        p = etree.SubElement(txBody, qn("a:p"))
        etree.SubElement(p, qn("a:endParaRPr"), lang="en-US")

    pkg.mark_xml_dirty(slide_partname)
    return make_shape_key(slide_num, shape_id)


def edit_shape(
    pkg: PowerPointPackage,
    shape_key: str,
    text: str,
    bullet_style: str | None = None,
) -> bool:
    """Edit text in an existing shape.

    Args:
        pkg: PowerPoint package
        shape_key: Shape identifier (slide_num:shape_id)
        text: New text content
        bullet_style: Optional bullet style ("bullet", "dash", "number", "none")

    Returns:
        True if successful, False if shape not found
    """
    slide_num, shape_id = parse_shape_key(shape_key)

    slide_xml = pkg.get_slide_xml(slide_num)
    slide_partname = pkg.get_slide_partname(slide_num)

    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        return False

    shape = _find_shape_by_id(sp_tree, shape_id)
    if shape is None:
        return False

    # Only allow editing text in sp (shape) elements
    tag = etree.QName(shape).localname
    if tag != "sp":
        return False

    set_shape_text(shape, text, bullet_style=bullet_style)
    pkg.mark_xml_dirty(slide_partname)
    return True


def delete_shape(
    pkg: PowerPointPackage,
    shape_key: str,
) -> bool:
    """Delete a shape from a slide.

    Args:
        pkg: PowerPoint package
        shape_key: Shape identifier (slide_num:shape_id)

    Returns:
        True if successful, False if shape not found
    """
    slide_num, shape_id = parse_shape_key(shape_key)

    slide_xml = pkg.get_slide_xml(slide_num)
    slide_partname = pkg.get_slide_partname(slide_num)

    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        return False

    shape = _find_shape_by_id(sp_tree, shape_id)
    if shape is None:
        return False

    # Remove from parent
    parent = shape.getparent()
    if parent is not None:
        parent.remove(shape)
        pkg.mark_xml_dirty(slide_partname)
        return True

    return False


def set_shape_transform(
    pkg: PowerPointPackage,
    shape_key: str,
    x: float | None = None,
    y: float | None = None,
    width: float | None = None,
    height: float | None = None,
) -> bool:
    """Set the position and/or size of a shape.

    Args:
        pkg: PowerPoint package
        shape_key: Shape identifier (slide_num:shape_id)
        x: X position in inches (None = keep current)
        y: Y position in inches (None = keep current)
        width: Width in inches (None = keep current)
        height: Height in inches (None = keep current)

    Returns:
        True if successful, False if shape not found

    Raises:
        ValueError: If shape is inside a group or has inherited position
    """
    slide_num, shape_id = parse_shape_key(shape_key)
    slide_xml = pkg.get_slide_xml(slide_num)
    slide_partname = pkg.get_slide_partname(slide_num)

    shape = find_shape_by_id(slide_xml, shape_id)
    if shape is None:
        return False

    # Check if shape is inside a group (parent is grpSp)
    parent = shape.getparent()
    if parent is not None:
        parent_tag = etree.QName(parent).localname
        if parent_tag == "grpSp":
            raise ValueError(
                "Cannot transform shape inside group. Use group's shape_key instead."
            )

    tag = etree.QName(shape).localname

    # Find the xfrm element based on shape type
    xfrm = None

    if tag in ("sp", "pic", "cxnSp"):
        # These use p:spPr/a:xfrm
        spPr = shape.find(qn("p:spPr"), NSMAP)
        if spPr is not None:
            xfrm = spPr.find(qn("a:xfrm"), NSMAP)
    elif tag == "graphicFrame":
        # GraphicFrame uses p:xfrm (direct child, not a:xfrm)
        xfrm = shape.find(qn("p:xfrm"), NSMAP)
    elif tag == "grpSp":
        # Group uses p:grpSpPr/a:xfrm
        grpSpPr = shape.find(qn("p:grpSpPr"), NSMAP)
        if grpSpPr is not None:
            xfrm = grpSpPr.find(qn("a:xfrm"), NSMAP)

    # Handle missing xfrm
    if xfrm is None:
        # For graphicFrame without xfrm, we can create it if ALL values provided
        if tag == "graphicFrame":
            if (
                x is not None
                and y is not None
                and width is not None
                and height is not None
            ):
                # Create p:xfrm for graphicFrame
                xfrm = etree.Element(qn("p:xfrm"))
                etree.SubElement(xfrm, qn("a:off"), x="0", y="0")
                etree.SubElement(xfrm, qn("a:ext"), cx="0", cy="0")
                # Insert at beginning (before a:graphic)
                shape.insert(0, xfrm)
            else:
                raise ValueError(
                    "Cannot transform graphicFrame without existing xfrm unless all "
                    "4 values (x, y, width, height) are provided"
                )
        else:
            # Shape has no transform - likely inherited position
            raise ValueError("Cannot transform shape with inherited position")

    # Get current values from xfrm
    off = xfrm.find(qn("a:off"), NSMAP)
    ext = xfrm.find(qn("a:ext"), NSMAP)

    if off is None or ext is None:
        raise ValueError("Shape transform is malformed (missing off or ext)")

    # Update position if provided
    if x is not None:
        off.set("x", str(inches_to_emu(x)))
    if y is not None:
        off.set("y", str(inches_to_emu(y)))

    # Update size if provided
    if width is not None:
        ext.set("cx", str(inches_to_emu(width)))
    if height is not None:
        ext.set("cy", str(inches_to_emu(height)))

    # Note: We preserve existing rot, flipH, flipV attributes on xfrm
    # (they are not touched since we only modify off and ext elements)

    pkg.mark_xml_dirty(slide_partname)
    return True
