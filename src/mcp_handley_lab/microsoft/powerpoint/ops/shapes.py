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
            NSMAP,
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


def _get_shape_id(shape: etree._Element) -> int | None:
    """Get the shape ID from a shape element's cNvPr."""
    tag = etree.QName(shape).localname

    # Map shape type to non-visual properties element name
    nv_map = {
        "sp": "p:nvSpPr",
        "pic": "p:nvPicPr",
        "graphicFrame": "p:nvGraphicFramePr",
        "grpSp": "p:nvGrpSpPr",
        "cxnSp": "p:nvCxnSpPr",
    }

    nv_tag = nv_map.get(tag)
    if not nv_tag:
        return None

    nvPr = shape.find(qn(nv_tag), NSMAP)
    if nvPr is None:
        return None

    cNvPr = nvPr.find(qn("p:cNvPr"), NSMAP)
    if cNvPr is None:
        return None

    id_str = cNvPr.get("id")
    if id_str and id_str.isdigit():
        return int(id_str)
    return None


# Valid ECMA-376 preset geometry types (subset of commonly used shapes)
VALID_SHAPE_TYPES = {
    # Basic shapes
    "rect",
    "ellipse",
    "triangle",
    "rtTriangle",
    "diamond",
    "parallelogram",
    "trapezoid",
    "pentagon",
    "hexagon",
    "heptagon",
    "octagon",
    "decagon",
    "dodecagon",
    # Rounded shapes
    "roundRect",
    "snip1Rect",
    "snip2SameRect",
    "snip2DiagRect",
    "snipRoundRect",
    "round1Rect",
    "round2SameRect",
    "round2DiagRect",
    # Arrows
    "rightArrow",
    "leftArrow",
    "upArrow",
    "downArrow",
    "leftRightArrow",
    "upDownArrow",
    "quadArrow",
    "leftRightUpArrow",
    "bentArrow",
    "uturnArrow",
    "leftUpArrow",
    "bentUpArrow",
    "curvedRightArrow",
    "curvedLeftArrow",
    "curvedUpArrow",
    "curvedDownArrow",
    "stripedRightArrow",
    "notchedRightArrow",
    "homePlate",
    "chevron",
    "rightArrowCallout",
    "downArrowCallout",
    "leftArrowCallout",
    "upArrowCallout",
    "leftRightArrowCallout",
    "quadArrowCallout",
    "circularArrow",
    # Stars and banners
    "star4",
    "star5",
    "star6",
    "star7",
    "star8",
    "star10",
    "star12",
    "star16",
    "star24",
    "star32",
    "ribbon",
    "ribbon2",
    "ellipseRibbon",
    "ellipseRibbon2",
    "verticalScroll",
    "horizontalScroll",
    "wave",
    "doubleWave",
    # Callouts
    "wedgeRectCallout",
    "wedgeRoundRectCallout",
    "wedgeEllipseCallout",
    "cloudCallout",
    "borderCallout1",
    "borderCallout2",
    "borderCallout3",
    "accentCallout1",
    "accentCallout2",
    "accentCallout3",
    "callout1",
    "callout2",
    "callout3",
    "accentBorderCallout1",
    "accentBorderCallout2",
    "accentBorderCallout3",
    # Flowchart shapes
    "flowChartProcess",
    "flowChartDecision",
    "flowChartInputOutput",
    "flowChartPredefinedProcess",
    "flowChartInternalStorage",
    "flowChartDocument",
    "flowChartMultidocument",
    "flowChartTerminator",
    "flowChartPreparation",
    "flowChartManualInput",
    "flowChartManualOperation",
    "flowChartConnector",
    "flowChartOffpageConnector",
    "flowChartPunchedCard",
    "flowChartPunchedTape",
    "flowChartSummingJunction",
    "flowChartOr",
    "flowChartCollate",
    "flowChartSort",
    "flowChartExtract",
    "flowChartMerge",
    "flowChartOnlineStorage",
    "flowChartDelay",
    "flowChartMagneticTape",
    "flowChartMagneticDisk",
    "flowChartMagneticDrum",
    "flowChartDisplay",
    # Block arrows
    "actionButtonBlank",
    "actionButtonHome",
    "actionButtonHelp",
    "actionButtonInformation",
    "actionButtonBackPrevious",
    "actionButtonForwardNext",
    "actionButtonBeginning",
    "actionButtonEnd",
    "actionButtonReturn",
    "actionButtonDocument",
    "actionButtonSound",
    "actionButtonMovie",
    # Equation shapes
    "mathPlus",
    "mathMinus",
    "mathMultiply",
    "mathDivide",
    "mathEqual",
    "mathNotEqual",
    # Other common shapes
    "heart",
    "lightningBolt",
    "sun",
    "moon",
    "smileyFace",
    "irregularSeal1",
    "irregularSeal2",
    "foldedCorner",
    "bevel",
    "frame",
    "halfFrame",
    "corner",
    "diagStripe",
    "chord",
    "arc",
    "leftBracket",
    "rightBracket",
    "leftBrace",
    "rightBrace",
    "bracketPair",
    "bracePair",
    "straightConnector1",
    "bentConnector2",
    "bentConnector3",
    "bentConnector4",
    "bentConnector5",
    "curvedConnector2",
    "curvedConnector3",
    "curvedConnector4",
    "curvedConnector5",
    "line",
    "lineInv",
    "can",
    "cube",
    "donut",
    "noSmoking",
    "blockArc",
    "plaque",
    "gear6",
    "gear9",
    "funnel",
    "pieWedge",
    "pie",
    "teardrop",
}


def add_shape(
    pkg: PowerPointPackage,
    slide_num: int,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str = "",
    shape_type: str = "rect",
) -> str:
    """Add a new shape to a slide.

    Args:
        pkg: PowerPoint package
        slide_num: 1-based slide number
        x: X position in inches
        y: Y position in inches
        width: Width in inches
        height: Height in inches
        text: Initial text content
        shape_type: Preset geometry type (default "rect"). Common types:
            Basic: rect, ellipse, triangle, diamond, roundRect
            Arrows: rightArrow, leftArrow, upArrow, downArrow
            Flowchart: flowChartProcess, flowChartDecision, flowChartTerminator
            Stars: star5, star6, star10
            See VALID_SHAPE_TYPES for full list.

    Returns:
        shape_key for the new shape (slide_num:shape_id)

    Raises:
        ValueError: If shape_type is not a valid preset geometry.
    """
    if shape_type not in VALID_SHAPE_TYPES:
        raise ValueError(
            f"Invalid shape_type '{shape_type}'. "
            f"Common types: rect, ellipse, roundRect, rightArrow, flowChartProcess. "
            f"See VALID_SHAPE_TYPES for full list."
        )

    slide_xml = pkg.get_slide_xml(slide_num)
    slide_partname = pkg.get_slide_partname(slide_num)

    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        raise ValueError(f"Slide {slide_num} has no shape tree")

    # Get next shape ID
    shape_id = _get_next_shape_id(sp_tree)

    # Create shape element
    sp = etree.SubElement(sp_tree, qn("p:sp"))

    # Non-visual properties - use shape type for name if not a text box
    is_textbox = shape_type == "rect" and text
    nvSpPr = etree.SubElement(sp, qn("p:nvSpPr"))
    shape_name = f"TextBox {shape_id}" if is_textbox else f"Shape {shape_id}"
    etree.SubElement(nvSpPr, qn("p:cNvPr"), id=str(shape_id), name=shape_name)
    cNvSpPr = etree.SubElement(nvSpPr, qn("p:cNvSpPr"))
    if is_textbox:
        cNvSpPr.set("txBox", "1")
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

    # Preset geometry with specified shape type
    prstGeom = etree.SubElement(spPr, qn("a:prstGeom"), prst=shape_type)
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


# Shape element tags (drawable elements)
_SHAPE_TAGS = {"sp", "grpSp", "cxnSp", "pic", "graphicFrame", "contentPart"}


def set_z_order(
    pkg: PowerPointPackage,
    shape_key: str,
    action: str,
) -> bool:
    """Change the z-order (stacking order) of a shape.

    Z-order controls which shapes appear on top of others. Higher z-order shapes
    are drawn on top of lower z-order shapes.

    Note: Shapes inside groups cannot have their z-order changed independently.
    This is a v1 limitation. To change stacking order of grouped shapes, either
    use the group's shape_key (which changes the entire group's z-order), or
    ungroup the shapes first.

    Args:
        pkg: PowerPoint package
        shape_key: Shape identifier (slide_num:shape_id)
        action: Z-order action:
            - "bring_to_front": Move shape to top (highest z-order)
            - "send_to_back": Move shape to bottom (lowest z-order)
            - "bring_forward": Move shape one level up
            - "send_backward": Move shape one level down

    Returns:
        True if successful, False if shape not found

    Raises:
        ValueError: If action is invalid or shape is inside a group.
    """
    valid_actions = {"bring_to_front", "send_to_back", "bring_forward", "send_backward"}
    if action not in valid_actions:
        raise ValueError(
            f"Invalid action '{action}'. Valid: {', '.join(valid_actions)}"
        )

    slide_num, shape_id = parse_shape_key(shape_key)
    slide_xml = pkg.get_slide_xml(slide_num)
    slide_partname = pkg.get_slide_partname(slide_num)

    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        return False

    shape = _find_shape_by_id(sp_tree, shape_id)
    if shape is None:
        return False

    # Check if shape is inside a group
    parent = shape.getparent()
    if parent is None:
        return False

    parent_tag = etree.QName(parent).localname
    if parent_tag == "grpSp":
        raise ValueError(
            "Cannot change z-order of shape inside group. "
            "To reorder grouped shapes, either use the group's shape_key "
            "(changes entire group's z-order) or ungroup the shapes first."
        )

    # Build ordered list of shape-only children with their original indices
    shapes_with_idx = [
        (i, c) for i, c in enumerate(parent) if etree.QName(c).localname in _SHAPE_TAGS
    ]
    shapes = [c for _, c in shapes_with_idx]

    if not shapes:
        return False

    # Find shape in list
    try:
        shape_idx = shapes.index(shape)
    except ValueError:
        return False

    # Record first shape's parent index (to preserve non-shape nodes)
    first_shape_parent_idx = shapes_with_idx[0][0] if shapes_with_idx else len(parent)

    # Apply z-order action (swap semantics)
    if action == "bring_to_front":
        shapes.remove(shape)
        shapes.append(shape)
    elif action == "send_to_back":
        shapes.remove(shape)
        shapes.insert(0, shape)
    elif action == "bring_forward":
        if shape_idx < len(shapes) - 1:
            shapes[shape_idx], shapes[shape_idx + 1] = (
                shapes[shape_idx + 1],
                shapes[shape_idx],
            )
    elif action == "send_backward":
        if shape_idx > 0:
            shapes[shape_idx], shapes[shape_idx - 1] = (
                shapes[shape_idx - 1],
                shapes[shape_idx],
            )

    # Remove shapes from parent, reinsert at original first-shape position
    for _, c in shapes_with_idx:
        parent.remove(c)
    for i, s in enumerate(shapes):
        parent.insert(first_shape_parent_idx + i, s)

    pkg.mark_xml_dirty(slide_partname)
    return True


# Valid connector types
VALID_CONNECTOR_TYPES = {
    "line",  # Simple straight line
    "straightConnector1",  # Straight connector
    "bentConnector2",  # Bent connector with 1 segment
    "bentConnector3",  # Bent connector with 2 segments
    "bentConnector4",  # Bent connector with 3 segments
    "bentConnector5",  # Bent connector with 4 segments
    "curvedConnector2",  # Curved connector with 1 segment
    "curvedConnector3",  # Curved connector with 2 segments
    "curvedConnector4",  # Curved connector with 3 segments
    "curvedConnector5",  # Curved connector with 4 segments
}


def _get_shape_center(shape: etree._Element) -> tuple[int, int] | None:
    """Get the center coordinates of a shape in EMUs.

    Returns (cx, cy) or None if shape has no valid xfrm.
    Rejects shapes with rotation or flip attributes.
    """
    tag = etree.QName(shape).localname

    xfrm = None
    if tag in ("sp", "pic", "cxnSp"):
        spPr = shape.find(qn("p:spPr"), NSMAP)
        if spPr is not None:
            xfrm = spPr.find(qn("a:xfrm"), NSMAP)
    elif tag == "graphicFrame":
        xfrm = shape.find(qn("p:xfrm"), NSMAP)
    elif tag == "grpSp":
        grpSpPr = shape.find(qn("p:grpSpPr"), NSMAP)
        if grpSpPr is not None:
            xfrm = grpSpPr.find(qn("a:xfrm"), NSMAP)

    if xfrm is None:
        return None

    # Reject rotated or flipped shapes (v1 constraint)
    if xfrm.get("rot") or xfrm.get("flipH") or xfrm.get("flipV"):
        return None

    off = xfrm.find(qn("a:off"), NSMAP)
    ext = xfrm.find(qn("a:ext"), NSMAP)

    if off is None or ext is None:
        return None

    x = int(off.get("x", "0"))
    y = int(off.get("y", "0"))
    cx = int(ext.get("cx", "0"))
    cy = int(ext.get("cy", "0"))

    # Calculate center
    center_x = x + cx // 2
    center_y = y + cy // 2

    return (center_x, center_y)


def add_connector(
    pkg: PowerPointPackage,
    slide_num: int,
    from_shape_key: str,
    to_shape_key: str,
    connector_type: str = "straightConnector1",
) -> str:
    """Add a connector between two shapes.

    V1 constraints:
    - Only connects shapes with simple a:xfrm (no rotation/flip)
    - Rejects grouped shapes as endpoints
    - Uses center-to-center coordinates

    Args:
        pkg: PowerPoint package
        slide_num: 1-based slide number
        from_shape_key: Source shape key (slide_num:shape_id)
        to_shape_key: Destination shape key (slide_num:shape_id)
        connector_type: Connector geometry type (default "straightConnector1")

    Returns:
        shape_key for the new connector (slide_num:shape_id)

    Raises:
        ValueError: If shapes not found, have rotation/flip, or invalid connector type.
    """
    if connector_type not in VALID_CONNECTOR_TYPES:
        raise ValueError(
            f"Invalid connector_type '{connector_type}'. "
            f"Valid: {sorted(VALID_CONNECTOR_TYPES)}"
        )

    # Parse shape keys
    from_slide, from_id = parse_shape_key(from_shape_key)
    to_slide, to_id = parse_shape_key(to_shape_key)

    # Both shapes must be on the same slide
    if from_slide != slide_num or to_slide != slide_num:
        raise ValueError(
            f"Both shapes must be on slide {slide_num}. "
            f"Got from={from_shape_key}, to={to_shape_key}"
        )

    slide_xml = pkg.get_slide_xml(slide_num)
    slide_partname = pkg.get_slide_partname(slide_num)

    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        raise ValueError(f"Slide {slide_num} has no shape tree")

    # Find source and destination shapes
    from_shape = _find_shape_by_id(sp_tree, from_id)
    to_shape = _find_shape_by_id(sp_tree, to_id)

    if from_shape is None:
        raise ValueError(f"Source shape {from_shape_key} not found")
    if to_shape is None:
        raise ValueError(f"Destination shape {to_shape_key} not found")

    # Check if shapes are inside groups
    from_parent = from_shape.getparent()
    to_parent = to_shape.getparent()

    if from_parent is not None and etree.QName(from_parent).localname == "grpSp":
        raise ValueError(
            f"Source shape {from_shape_key} is inside a group. "
            "Cannot connect to grouped shapes."
        )
    if to_parent is not None and etree.QName(to_parent).localname == "grpSp":
        raise ValueError(
            f"Destination shape {to_shape_key} is inside a group. "
            "Cannot connect to grouped shapes."
        )

    # Get center coordinates
    from_center = _get_shape_center(from_shape)
    to_center = _get_shape_center(to_shape)

    if from_center is None:
        raise ValueError(
            f"Source shape {from_shape_key} has no position, rotation, or flip. "
            "Cannot connect."
        )
    if to_center is None:
        raise ValueError(
            f"Destination shape {to_shape_key} has no position, rotation, or flip. "
            "Cannot connect."
        )

    from_x, from_y = from_center
    to_x, to_y = to_center

    # Calculate connector bounds (min corner and size)
    min_x = min(from_x, to_x)
    min_y = min(from_y, to_y)
    cx = abs(to_x - from_x)
    cy = abs(to_y - from_y)

    # Determine if we need to flip
    flip_h = from_x > to_x
    flip_v = from_y > to_y

    # Get next shape ID
    shape_id = _get_next_shape_id(sp_tree)

    # Create connector element
    cxnSp = etree.SubElement(sp_tree, qn("p:cxnSp"))

    # Non-visual properties
    nvCxnSpPr = etree.SubElement(cxnSp, qn("p:nvCxnSpPr"))
    etree.SubElement(
        nvCxnSpPr,
        qn("p:cNvPr"),
        id=str(shape_id),
        name=f"Connector {shape_id}",
    )
    # Connection shape properties (can add stCxn/endCxn for glue)
    etree.SubElement(nvCxnSpPr, qn("p:cNvCxnSpPr"))
    etree.SubElement(nvCxnSpPr, qn("p:nvPr"))

    # Shape properties
    spPr = etree.SubElement(cxnSp, qn("p:spPr"))

    # Transform with position/size
    xfrm_attrib = {}
    if flip_h:
        xfrm_attrib["flipH"] = "1"
    if flip_v:
        xfrm_attrib["flipV"] = "1"

    xfrm = etree.SubElement(spPr, qn("a:xfrm"), **xfrm_attrib)
    etree.SubElement(xfrm, qn("a:off"), x=str(min_x), y=str(min_y))
    etree.SubElement(
        xfrm, qn("a:ext"), cx=str(cx if cx > 0 else 1), cy=str(cy if cy > 0 else 1)
    )

    # Preset geometry for connector
    prstGeom = etree.SubElement(spPr, qn("a:prstGeom"), prst=connector_type)
    etree.SubElement(prstGeom, qn("a:avLst"))

    # Line properties (default black line)
    ln = etree.SubElement(spPr, qn("a:ln"), w="9525")
    solidFill = etree.SubElement(ln, qn("a:solidFill"))
    etree.SubElement(solidFill, qn("a:schemeClr"), val="tx1")

    pkg.mark_xml_dirty(slide_partname)
    return make_shape_key(slide_num, shape_id)


# =============================================================================
# Group/Ungroup Helper Functions
# =============================================================================

# Tags that can be grouped (excludes connectors p:cxnSp and groups p:grpSp)
GROUPABLE_SHAPE_TAGS = {"sp", "pic", "graphicFrame"}

# All drawable shape tags for z-order operations
DRAWABLE_SHAPE_TAGS = {"sp", "grpSp", "cxnSp", "pic", "graphicFrame", "contentPart"}


def _get_shape_xfrm(shape: etree._Element) -> etree._Element | None:
    """Get xfrm element for any shape type (sp, pic, grpSp, graphicFrame).

    Returns None if no xfrm found or position is inherited.
    """
    localname = etree.QName(shape).localname

    if localname == "grpSp":
        # Group shapes have xfrm in grpSpPr
        grpSpPr = shape.find(qn("p:grpSpPr"))
        if grpSpPr is not None:
            return grpSpPr.find(qn("a:xfrm"))
    elif localname in ("sp", "cxnSp"):
        # Regular shapes and connectors have xfrm in spPr
        spPr = shape.find(qn("p:spPr"))
        if spPr is not None:
            return spPr.find(qn("a:xfrm"))
    elif localname == "pic":
        # Pictures have xfrm in blipFill's parent spPr
        spPr = shape.find(qn("p:spPr"))
        if spPr is not None:
            return spPr.find(qn("a:xfrm"))
    elif localname == "graphicFrame":
        # Graphic frames (tables, charts) have xfrm directly
        return shape.find(qn("p:xfrm"))

    return None


def _has_rotation_or_flip(xfrm: etree._Element) -> bool:
    """Check if xfrm has rotation or flip attributes."""
    if xfrm is None:
        return False
    rot = xfrm.get("rot")
    if rot and rot != "0":
        return True
    return bool(xfrm.get("flipH") == "1" or xfrm.get("flipV") == "1")


def _get_shape_bounds(shape: etree._Element) -> tuple[int, int, int, int] | None:
    """Get shape bounds (x, y, cx, cy) in EMUs.

    Returns None if position is inherited/missing (e.g., placeholders without
    explicit transforms).
    """
    xfrm = _get_shape_xfrm(shape)
    if xfrm is None:
        return None

    off = xfrm.find(qn("a:off"))
    ext = xfrm.find(qn("a:ext"))

    if off is None or ext is None:
        return None

    x = off.get("x")
    y = off.get("y")
    cx = ext.get("cx")
    cy = ext.get("cy")

    if x is None or y is None or cx is None or cy is None:
        return None

    return (int(x), int(y), int(cx), int(cy))


def _group_has_scaling(grp_xfrm: etree._Element) -> bool:
    """Check if group has scaling (chOff != (0,0) or chExt != ext).

    V1 constraint: We only support ungrouping groups with no scaling.
    """
    if grp_xfrm is None:
        return True  # Treat missing as scaled for safety

    chOff = grp_xfrm.find(qn("a:chOff"))
    chExt = grp_xfrm.find(qn("a:chExt"))
    ext = grp_xfrm.find(qn("a:ext"))

    if chOff is None or chExt is None or ext is None:
        return True  # Missing elements = assume scaled

    # Check chOff is (0, 0)
    if chOff.get("x", "0") != "0" or chOff.get("y", "0") != "0":
        return True

    # Check chExt matches ext
    return bool(chExt.get("cx") != ext.get("cx") or chExt.get("cy") != ext.get("cy"))


def _is_connector(shape: etree._Element) -> bool:
    """Check if shape is a connector (p:cxnSp)."""
    return etree.QName(shape).localname == "cxnSp"


def _is_nested_in_group(shape: etree._Element) -> bool:
    """Check if shape is already inside a group (i.e., parent is p:grpSp)."""
    parent = shape.getparent()
    if parent is None:
        return False
    return etree.QName(parent).localname == "grpSp"


# =============================================================================
# Group/Ungroup Operations
# =============================================================================


def group_shapes(
    pkg: PowerPointPackage,
    slide_num: int,
    shape_keys: list[str],
) -> str:
    """Group multiple shapes into a new group.

    Args:
        pkg: PowerPoint package
        slide_num: Slide number (1-indexed)
        shape_keys: List of shape_key strings (e.g., ["1:5", "1:6"])

    Returns:
        shape_key of the new group

    Raises:
        ValueError: If shapes cannot be grouped (rotation, connectors, etc.)

    V1 Constraints:
        - Only unrotated, unflipped shapes supported
        - Connectors (p:cxnSp) excluded
        - Shapes with inherited/missing transforms rejected
        - Nested groups not supported (cannot group a group that's already in a group)
    """
    if len(shape_keys) < 2:
        raise ValueError("At least 2 shapes required to create a group")

    # Validate all shapes are on the same slide
    for key in shape_keys:
        parts = key.split(":")
        if len(parts) != 2 or int(parts[0]) != slide_num:
            raise ValueError(f"Shape key {key} is not on slide {slide_num}")

    # Get slide XML via relationship-based lookup
    slide_partname = pkg.get_slide_partname(slide_num)
    slide_xml = pkg.get_slide_xml(slide_num)

    spTree = slide_xml.find(f".//{qn('p:spTree')}")
    if spTree is None:
        raise ValueError("Slide has no shape tree")

    # Find all shapes to group
    shapes_to_group = []
    shape_ids = [int(key.split(":")[1]) for key in shape_keys]

    for shape in spTree:
        localname = etree.QName(shape).localname
        if localname not in DRAWABLE_SHAPE_TAGS:
            continue

        shape_id = _get_shape_id(shape)
        if shape_id in shape_ids:
            # Validate shape
            if _is_connector(shape):
                raise ValueError(
                    f"Cannot group connectors (shape {shape_id}). "
                    "Remove connectors from selection."
                )

            # V1: Cannot group an existing group (no nested groups)
            if localname == "grpSp":
                raise ValueError(
                    f"Cannot group a group (shape {shape_id}). "
                    "Nested groups not supported in V1."
                )

            xfrm = _get_shape_xfrm(shape)
            if xfrm is None:
                raise ValueError(
                    f"Shape {shape_id} has no explicit transform. "
                    "Cannot group shapes with inherited positions (e.g., placeholders)."
                )

            if _has_rotation_or_flip(xfrm):
                raise ValueError(
                    f"Shape {shape_id} has rotation or flip. "
                    "V1 only supports unrotated, unflipped shapes."
                )

            bounds = _get_shape_bounds(shape)
            if bounds is None:
                raise ValueError(
                    f"Shape {shape_id} has missing position/size. "
                    "Cannot group shapes without explicit bounds."
                )

            # Check if already in a group
            if _is_nested_in_group(shape):
                raise ValueError(
                    f"Shape {shape_id} is already in a group. "
                    "Nested groups not supported in V1."
                )

            shapes_to_group.append((shape, bounds))

    if len(shapes_to_group) != len(shape_keys):
        found_ids = {_get_shape_id(s) for s, _ in shapes_to_group}
        missing = set(shape_ids) - found_ids

        # Check if missing shapes are nested in existing groups
        nested_shapes = []
        for mid in missing:
            shape_el = _find_shape_by_id(spTree, mid)
            if shape_el is not None:
                nested_shapes.append(mid)

        if nested_shapes:
            raise ValueError(
                f"Shapes {nested_shapes} are nested inside groups. "
                "Nested groups not supported in V1. "
                "Ungroup the parent group first."
            )
        else:
            raise ValueError(f"Shapes not found: {missing}")

    # Calculate bounding box
    min_x = min(b[0] for _, b in shapes_to_group)
    min_y = min(b[1] for _, b in shapes_to_group)
    max_x = max(b[0] + b[2] for _, b in shapes_to_group)
    max_y = max(b[1] + b[3] for _, b in shapes_to_group)

    group_cx = max_x - min_x
    group_cy = max_y - min_y

    # Allocate new shape ID
    group_id = _get_next_shape_id(spTree)

    # Create group element
    grpSp = etree.Element(qn("p:grpSp"))

    # Non-visual properties
    nvGrpSpPr = etree.SubElement(grpSp, qn("p:nvGrpSpPr"))
    etree.SubElement(
        nvGrpSpPr, qn("p:cNvPr"), id=str(group_id), name=f"Group {group_id}"
    )
    etree.SubElement(nvGrpSpPr, qn("p:cNvGrpSpPr"))
    etree.SubElement(nvGrpSpPr, qn("p:nvPr"))

    # Group shape properties with transforms
    grpSpPr = etree.SubElement(grpSp, qn("p:grpSpPr"))
    xfrm = etree.SubElement(grpSpPr, qn("a:xfrm"))
    etree.SubElement(xfrm, qn("a:off"), x=str(min_x), y=str(min_y))
    etree.SubElement(xfrm, qn("a:ext"), cx=str(group_cx), cy=str(group_cy))
    # chOff = (0,0), chExt = group size (no scaling)
    etree.SubElement(xfrm, qn("a:chOff"), x="0", y="0")
    etree.SubElement(xfrm, qn("a:chExt"), cx=str(group_cx), cy=str(group_cy))

    # Track first shape's position for insertion
    first_shape_idx = None
    shapes_with_idx = []

    for idx, child in enumerate(spTree):
        if child in [s for s, _ in shapes_to_group]:
            if first_shape_idx is None:
                first_shape_idx = idx
            shapes_with_idx.append((idx, child))

    # Sort shapes by their original index to preserve z-order
    shapes_with_idx.sort(key=lambda x: x[0])

    # Transform child coordinates and move to group
    for _, shape in shapes_with_idx:
        bounds = _get_shape_bounds(shape)
        child_xfrm = _get_shape_xfrm(shape)

        # Transform to group-relative coordinates
        off = child_xfrm.find(qn("a:off"))
        off.set("x", str(bounds[0] - min_x))
        off.set("y", str(bounds[1] - min_y))

        # Remove from spTree and add to group
        spTree.remove(shape)
        grpSp.append(shape)

    # Insert group at first shape's original position
    spTree.insert(first_shape_idx, grpSp)

    pkg.mark_xml_dirty(slide_partname)
    return make_shape_key(slide_num, group_id)


def ungroup(
    pkg: PowerPointPackage,
    shape_key: str,
) -> list[str]:
    """Ungroup a group, promoting children to parent level.

    Args:
        pkg: PowerPoint package
        shape_key: shape_key of the group (e.g., "1:10")

    Returns:
        List of shape_keys of the ungrouped children

    Raises:
        ValueError: If shape is not a group or has unsupported properties

    V1 Constraints:
        - Only unrotated, unflipped groups supported
        - Groups with scaling (chOff != 0 or chExt != ext) rejected
        - Nested groups not supported
    """
    slide_num, shape_id = parse_shape_key(shape_key)

    # Get slide XML via relationship-based lookup
    slide_partname = pkg.get_slide_partname(slide_num)
    slide_xml = pkg.get_slide_xml(slide_num)

    spTree = slide_xml.find(f".//{qn('p:spTree')}")
    if spTree is None:
        raise ValueError("Slide has no shape tree")

    # Find the group
    group = None
    group_idx = None
    for idx, shape in enumerate(spTree):
        if etree.QName(shape).localname == "grpSp" and _get_shape_id(shape) == shape_id:
            group = shape
            group_idx = idx
            break

    if group is None:
        raise ValueError(f"Group {shape_key} not found")

    # Validate group properties
    grp_xfrm = _get_shape_xfrm(group)
    if grp_xfrm is None:
        raise ValueError("Group has no transform")

    if _has_rotation_or_flip(grp_xfrm):
        raise ValueError(
            "Group has rotation or flip. V1 only supports unrotated, unflipped groups."
        )

    if _group_has_scaling(grp_xfrm):
        raise ValueError(
            "Group has scaling (chOff != 0 or chExt != ext). "
            "V1 only supports groups with no scaling."
        )

    # Get group offset
    off = grp_xfrm.find(qn("a:off"))
    group_off_x = int(off.get("x", "0"))
    group_off_y = int(off.get("y", "0"))

    # Collect children (skip non-shape elements like nvGrpSpPr, grpSpPr)
    children = []
    for child in group:
        localname = etree.QName(child).localname
        if localname in DRAWABLE_SHAPE_TAGS:
            children.append(child)

    if not children:
        raise ValueError("Group has no child shapes")

    # Check for nested groups (among drawable children only)
    for child in children:
        if etree.QName(child).localname == "grpSp":
            raise ValueError(
                "Group contains nested groups. V1 does not support ungrouping nested groups."
            )

    # Transform children to absolute coordinates
    result_keys = []
    for child in children:
        child_xfrm = _get_shape_xfrm(child)
        if child_xfrm is not None:
            child_off = child_xfrm.find(qn("a:off"))
            if child_off is not None:
                old_x = int(child_off.get("x", "0"))
                old_y = int(child_off.get("y", "0"))
                child_off.set("x", str(old_x + group_off_x))
                child_off.set("y", str(old_y + group_off_y))

        child_id = _get_shape_id(child)
        result_keys.append(make_shape_key(slide_num, child_id))

    # Move children to spTree at group's position, preserving order
    for i, child in enumerate(children):
        group.remove(child)
        spTree.insert(group_idx + i, child)

    # Remove the group element
    spTree.remove(group)

    pkg.mark_xml_dirty(slide_partname)
    return result_keys
