"""Shape extraction and text operations for Visio."""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.visio.constants import NS_VISIO_2012, findall_v, qn
from mcp_handley_lab.microsoft.visio.models import (
    ShapeCellInfo,
    ShapeDataProperty,
    ShapeInfo,
)
from mcp_handley_lab.microsoft.visio.ops.core import (
    extract_shape_text,
    get_all_cells,
    get_cell_float,
    get_cell_value,
    get_section_rows,
    make_shape_key,
)
from mcp_handley_lab.microsoft.visio.ops.masters import (
    list_masters,
    resolve_master_name,
)
from mcp_handley_lab.microsoft.visio.ops.pages import get_page_dimensions
from mcp_handley_lab.microsoft.visio.package import VisioPackage


def _get_shape_type(shape_el: etree._Element) -> str:
    """Determine shape type from Type attribute and cell presence."""
    type_attr = shape_el.get("Type")
    if type_attr == "Group":
        return "group"
    if type_attr == "Foreign":
        return "foreign"

    # Check for 1D shape (connector): has BeginX/EndX cells
    begin_x = get_cell_value(shape_el, "BeginX")
    end_x = get_cell_value(shape_el, "EndX")
    if begin_x is not None and end_x is not None:
        return "connector"

    return "shape"


def _parse_shape(
    shape_el: etree._Element,
    page_num: int,
    master_names: dict[int, str],
    parent_id: int | None = None,
) -> ShapeInfo | None:
    """Parse a single Shape element into ShapeInfo."""
    id_str = shape_el.get("ID")
    if id_str is None:
        return None
    shape_id = int(id_str)

    name = shape_el.get("Name")
    name_u = shape_el.get("NameU")
    shape_type = _get_shape_type(shape_el)

    text = extract_shape_text(shape_el)

    # Master reference
    master_id = None
    master_name = None
    master_attr = shape_el.get("Master")
    if master_attr is not None:
        master_id = int(master_attr)
        master_name = master_names.get(master_id)

    # Position: 2D shapes use PinX/PinY/Width/Height
    x = get_cell_float(shape_el, "PinX")
    y = get_cell_float(shape_el, "PinY")
    width = get_cell_float(shape_el, "Width")
    height = get_cell_float(shape_el, "Height")

    # Adjust position to top-left corner (PinX/PinY is center by default)
    loc_pin_x = get_cell_float(shape_el, "LocPinX")
    loc_pin_y = get_cell_float(shape_el, "LocPinY")
    if x is not None and loc_pin_x is not None:
        x = x - loc_pin_x
    elif x is not None and width is not None:
        x = x - width / 2
    if y is not None and loc_pin_y is not None:
        y = y - loc_pin_y
    elif y is not None and height is not None:
        y = y - height / 2

    # 1D shapes: connector endpoints
    begin_x = get_cell_float(shape_el, "BeginX")
    begin_y = get_cell_float(shape_el, "BeginY")
    end_x = get_cell_float(shape_el, "EndX")
    end_y = get_cell_float(shape_el, "EndY")

    return ShapeInfo(
        shape_id=shape_id,
        shape_key=make_shape_key(page_num, shape_id),
        name=name,
        name_u=name_u,
        type=shape_type,
        text=text,
        x_inches=x,
        y_inches=y,
        width_inches=width,
        height_inches=height,
        begin_x=begin_x,
        begin_y=begin_y,
        end_x=end_x,
        end_y=end_y,
        master_id=master_id,
        master_name=master_name,
        parent_id=parent_id,
    )


def _collect_shapes_recursive(
    parent: etree._Element,
    page_num: int,
    master_names: dict[int, str],
    parent_id: int | None = None,
) -> list[ShapeInfo]:
    """Recursively collect shapes, traversing into groups."""
    results = []

    for shape_el in findall_v(parent, "Shape"):
        info = _parse_shape(shape_el, page_num, master_names, parent_id)
        if info is None:
            continue
        results.append(info)

        # Recurse into group children
        if info.type == "group":
            shapes_container = findall_v(shape_el, "Shapes")
            for container in shapes_container:
                children = _collect_shapes_recursive(
                    container, page_num, master_names, info.shape_id
                )
                results.extend(children)

    return results


def _spatial_sort_key(shape: ShapeInfo, page_height: float) -> tuple[float, float, int]:
    """Sort key for spatial ordering: top-to-bottom, left-to-right.

    Flips Y coordinate since Visio Y is bottom-to-top.
    """
    if shape.type == "connector":
        # Use midpoint for connectors
        if shape.begin_x is not None and shape.end_x is not None:
            x = (shape.begin_x + shape.end_x) / 2
        else:
            x = 0.0
        if shape.begin_y is not None and shape.end_y is not None:
            y = page_height - (shape.begin_y + shape.end_y) / 2
        else:
            y = 0.0
    else:
        x = shape.x_inches or 0.0
        # Flip Y: page_height - y gives top-to-bottom order
        y = page_height - (shape.y_inches or 0.0)

    return (y, x, shape.shape_id)


def list_shapes(pkg: VisioPackage, page_num: int) -> list[ShapeInfo]:
    """List all shapes on a page, spatially sorted for reading order.

    Shapes are sorted top-to-bottom, left-to-right (Y-flipped for display order).
    Group children are included with parent_id set.
    """
    page_xml = pkg.get_page_xml(page_num)
    master_names = resolve_master_name(pkg)
    page_width, page_height = get_page_dimensions(pkg, page_num)

    # Find the top-level Shapes container in the page
    shapes_containers = findall_v(page_xml, "Shapes")
    if not shapes_containers:
        return []

    all_shapes = []
    for container in shapes_containers:
        all_shapes.extend(_collect_shapes_recursive(container, page_num, master_names))

    # Sort spatially
    all_shapes.sort(key=lambda s: _spatial_sort_key(s, page_height))

    # Assign reading order
    for idx, shape in enumerate(all_shapes):
        shape.reading_order = idx

    return all_shapes


def get_text_in_reading_order(pkg: VisioPackage, page_num: int) -> str:
    """Get all text from a page in spatial reading order."""
    shapes = list_shapes(pkg, page_num)
    texts = []
    for shape in shapes:
        if shape.text:
            texts.append(shape.text)
    return "\n\n".join(texts)


def find_shape_element(
    pkg: VisioPackage, page_num: int, shape_id: int
) -> etree._Element | None:
    """Find a shape element by ID on a page.

    Searches recursively into groups.
    """
    page_xml = pkg.get_page_xml(page_num)
    shapes_containers = findall_v(page_xml, "Shapes")

    for container in shapes_containers:
        found = _find_shape_recursive(container, shape_id)
        if found is not None:
            return found
    return None


def _find_shape_recursive(
    parent: etree._Element, shape_id: int
) -> etree._Element | None:
    """Recursively find shape element by ID."""
    for shape_el in findall_v(parent, "Shape"):
        id_str = shape_el.get("ID")
        if id_str and int(id_str) == shape_id:
            return shape_el
        # Recurse into groups
        for shapes_container in findall_v(shape_el, "Shapes"):
            found = _find_shape_recursive(shapes_container, shape_id)
            if found is not None:
                return found
    return None


def get_shape_data(
    pkg: VisioPackage, page_num: int, shape_id: int
) -> list[ShapeDataProperty]:
    """Get custom properties (Property section) for a shape.

    Returns list of ShapeDataProperty with label, value, prompt, type, format.
    """
    shape_el = find_shape_element(pkg, page_num, shape_id)
    if shape_el is None:
        raise ValueError(f"Shape {shape_id} not found on page {page_num}")

    rows = get_section_rows(shape_el, "Property")
    results = []
    for row in rows:
        cells = row["cells"]
        results.append(
            ShapeDataProperty(
                label=cells.get("Label", {}).get("value"),
                value=cells.get("Value", {}).get("value"),
                prompt=cells.get("Prompt", {}).get("value"),
                type=cells.get("Type", {}).get("value"),
                format=cells.get("Format", {}).get("value"),
                sort_key=cells.get("SortKey", {}).get("value"),
                row_name=row["name"],
            )
        )
    return results


def get_shape_cells(
    pkg: VisioPackage, page_num: int, shape_id: int
) -> list[ShapeCellInfo]:
    """Get all singleton cells for a shape (full ShapeSheet dump).

    Returns list of ShapeCellInfo with name, value, formula, unit.
    """
    shape_el = find_shape_element(pkg, page_num, shape_id)
    if shape_el is None:
        raise ValueError(f"Shape {shape_id} not found on page {page_num}")

    raw_cells = get_all_cells(shape_el)
    return [
        ShapeCellInfo(
            name=c["name"],
            value=c["value"],
            formula=c["formula"],
            unit=c["unit"],
        )
        for c in raw_cells
    ]


def set_z_order(
    pkg: VisioPackage,
    page_num: int,
    shape_id: int,
    action: str,
) -> bool:
    """Change the z-order (stacking order) of a shape.

    Z-order in Visio is determined by position in the Shapes container.
    Later shapes (higher index) are drawn on top.

    Args:
        pkg: Visio package
        page_num: 1-based page number
        shape_id: Shape ID
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

    page_xml = pkg.get_page_xml(page_num)

    # Find the top-level Shapes container(s)
    shapes_containers = findall_v(page_xml, "Shapes")
    if not shapes_containers:
        return False

    # Find the shape and its direct parent
    shape_el = None
    parent = None
    for container in shapes_containers:
        for shape in findall_v(container, "Shape"):
            id_str = shape.get("ID")
            if id_str and int(id_str) == shape_id:
                shape_el = shape
                parent = container
                break
        if shape_el is not None:
            break

    if shape_el is None:
        # Shape might be inside a group - check recursively but reject
        for container in shapes_containers:
            found = _find_shape_recursive(container, shape_id)
            if found is not None:
                # Walk up the ancestor chain to detect group membership
                # Chain: Shape (child) -> Shapes -> Shape (group) -> Shapes -> ...
                ancestor = found.getparent()
                while ancestor is not None:
                    # If we find a Shape element with Type="Group", we're inside a group
                    is_shape = (
                        ancestor.tag.endswith("}Shape") or ancestor.tag == "Shape"
                    )
                    if is_shape and ancestor.get("Type") == "Group":
                        raise ValueError(
                            "Cannot change z-order of shape inside group. "
                            "Use group's shape_id instead."
                        )
                    ancestor = ancestor.getparent()
        return False

    # Build list of Shape elements in order
    shapes = list(findall_v(parent, "Shape"))
    if not shapes:
        return False

    try:
        shape_idx = shapes.index(shape_el)
    except ValueError:
        return False

    # Apply z-order action (swap semantics)
    if action == "bring_to_front":
        shapes.remove(shape_el)
        shapes.append(shape_el)
    elif action == "send_to_back":
        shapes.remove(shape_el)
        shapes.insert(0, shape_el)
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

    # Remove all shapes and re-add in new order
    for s in list(findall_v(parent, "Shape")):
        parent.remove(s)
    for s in shapes:
        parent.append(s)

    pkg.mark_page_dirty(page_num)
    return True


def _get_max_shape_id(pkg: VisioPackage, page_num: int) -> int:
    """Get the maximum shape ID currently used on a page."""
    page_xml = pkg.get_page_xml(page_num)
    max_id = 0

    # Recursively find all shape IDs
    def scan_shapes(parent: etree._Element) -> None:
        nonlocal max_id
        for shape in findall_v(parent, "Shape"):
            id_str = shape.get("ID")
            if id_str:
                try:
                    shape_id = int(id_str)
                    if shape_id > max_id:
                        max_id = shape_id
                except ValueError:
                    pass
            # Recurse into nested Shapes containers (groups)
            for shapes_container in findall_v(shape, "Shapes"):
                scan_shapes(shapes_container)

    # Start from top-level Shapes containers
    for shapes_container in findall_v(page_xml, "Shapes"):
        scan_shapes(shapes_container)

    return max_id


def _make_cell(name: str, value: str, unit: str | None = None) -> etree._Element:
    """Create a Visio Cell element."""
    attrib = {"N": name, "V": value}
    if unit:
        attrib["U"] = unit
    return etree.Element(qn("v:Cell"), attrib, nsmap={"v": NS_VISIO_2012})


def add_shape_from_master(
    pkg: VisioPackage,
    page_num: int,
    master_name: str,
    x: float,
    y: float,
    width: float | None = None,
    height: float | None = None,
    text: str | None = None,
) -> int:
    """Add a new shape by dropping a master from the document stencil.

    Can only use masters already in the document. Master shapes inherit
    geometry and formatting from their master definition.

    Args:
        pkg: Visio package
        page_num: 1-based page number
        master_name: Name or NameU of the master to drop
        x: Pin X position in inches (center of shape)
        y: Pin Y position in inches (center of shape)
        width: Optional width in inches (overrides master default)
        height: Optional height in inches (overrides master default)
        text: Optional text to place in the shape

    Returns:
        The new shape's ID.

    Raises:
        ValueError: If master_name is not found in document stencil.
    """
    # Build name -> id mapping from masters
    masters = list_masters(pkg)
    name_to_id: dict[str, int] = {}
    for m in masters:
        if m.name_u:
            name_to_id[m.name_u] = m.master_id
        if m.name:
            name_to_id[m.name] = m.master_id

    if not name_to_id:
        raise ValueError(
            "No masters found in document stencil. "
            "Create the document from a template that includes stencils."
        )

    # Look up master by name
    master_id = name_to_id.get(master_name)
    if master_id is None:
        available = sorted(name_to_id.keys())
        raise ValueError(
            f"Master '{master_name}' not found. Available masters: {available}"
        )

    # Generate unique shape ID
    new_id = _get_max_shape_id(pkg, page_num) + 1

    # Get page XML and find/create Shapes container
    page_xml = pkg.get_page_xml(page_num)
    shapes_containers = findall_v(page_xml, "Shapes")
    if shapes_containers:
        shapes_container = shapes_containers[0]
    else:
        # Create Shapes container if missing
        shapes_container = etree.SubElement(
            page_xml, qn("v:Shapes"), nsmap={"v": NS_VISIO_2012}
        )

    # Create minimal Shape element
    shape_el = etree.SubElement(
        shapes_container,
        qn("v:Shape"),
        {"ID": str(new_id), "Master": str(master_id), "Type": "Shape"},
        nsmap={"v": NS_VISIO_2012},
    )

    # Add position cells (PinX, PinY)
    shape_el.append(_make_cell("PinX", str(x), "IN"))
    shape_el.append(_make_cell("PinY", str(y), "IN"))

    # Add optional size cells
    if width is not None:
        shape_el.append(_make_cell("Width", str(width), "IN"))
    if height is not None:
        shape_el.append(_make_cell("Height", str(height), "IN"))

    # Add text if provided
    if text:
        text_el = etree.SubElement(shape_el, qn("v:Text"), nsmap={"v": NS_VISIO_2012})
        text_el.text = text

    pkg.mark_page_dirty(page_num)
    return new_id


def _get_shape_center_visio(
    pkg: VisioPackage, page_num: int, shape_id: int
) -> tuple[float, float] | None:
    """Get the center coordinates of a Visio shape in inches.

    Returns (x, y) or None if shape not found or has no position.
    """
    shape_el = find_shape_element(pkg, page_num, shape_id)
    if shape_el is None:
        return None

    # Check if it's a 2D shape (PinX/PinY) or 1D (BeginX/EndX)
    pin_x = get_cell_float(shape_el, "PinX")
    pin_y = get_cell_float(shape_el, "PinY")

    if pin_x is not None and pin_y is not None:
        return (pin_x, pin_y)

    # For 1D shapes, use midpoint
    begin_x = get_cell_float(shape_el, "BeginX")
    begin_y = get_cell_float(shape_el, "BeginY")
    end_x = get_cell_float(shape_el, "EndX")
    end_y = get_cell_float(shape_el, "EndY")

    if all(v is not None for v in [begin_x, begin_y, end_x, end_y]):
        mid_x = (begin_x + end_x) / 2
        mid_y = (begin_y + end_y) / 2
        return (mid_x, mid_y)

    return None


def add_connector(
    pkg: VisioPackage,
    page_num: int,
    from_shape_id: int,
    to_shape_id: int,
    text: str = "",
) -> int:
    """Add a connector between two shapes.

    V1 constraints:
    - Static endpoints (center-to-center)
    - No dynamic glue (endpoints don't follow shape moves)

    Args:
        pkg: Visio package
        page_num: 1-based page number
        from_shape_id: Source shape ID
        to_shape_id: Destination shape ID
        text: Optional text to place on the connector

    Returns:
        The new connector's shape ID.

    Raises:
        ValueError: If shapes not found or have no position.
    """
    # Get center coordinates for both shapes
    from_center = _get_shape_center_visio(pkg, page_num, from_shape_id)
    to_center = _get_shape_center_visio(pkg, page_num, to_shape_id)

    if from_center is None:
        raise ValueError(f"Source shape {from_shape_id} not found or has no position")
    if to_center is None:
        raise ValueError(
            f"Destination shape {to_shape_id} not found or has no position"
        )

    from_x, from_y = from_center
    to_x, to_y = to_center

    # Generate unique shape ID
    new_id = _get_max_shape_id(pkg, page_num) + 1

    # Get page XML and find Shapes container
    page_xml = pkg.get_page_xml(page_num)
    shapes_containers = findall_v(page_xml, "Shapes")
    if not shapes_containers:
        raise ValueError(f"Page {page_num} has no Shapes container")

    shapes_container = shapes_containers[0]

    # Create 1D connector shape (no Master attribute for simple line)
    shape_el = etree.SubElement(
        shapes_container,
        qn("v:Shape"),
        {"ID": str(new_id), "Type": "Shape"},
        nsmap={"v": NS_VISIO_2012},
    )

    # Add 1D endpoint cells
    shape_el.append(_make_cell("BeginX", str(from_x), "IN"))
    shape_el.append(_make_cell("BeginY", str(from_y), "IN"))
    shape_el.append(_make_cell("EndX", str(to_x), "IN"))
    shape_el.append(_make_cell("EndY", str(to_y), "IN"))

    # Add text if provided
    if text:
        text_el = etree.SubElement(shape_el, qn("v:Text"), nsmap={"v": NS_VISIO_2012})
        text_el.text = text

    # Add Connect elements to link the connector to shapes
    # Connect elements are direct children of PageContents, not Shapes
    # FromSheet = connector ID, ToSheet = connected shape ID
    # FromCell = "BeginX" or "EndX" indicates which end

    etree.SubElement(
        page_xml,
        qn("v:Connect"),
        {
            "FromSheet": str(new_id),
            "FromCell": "BeginX",
            "ToSheet": str(from_shape_id),
        },
        nsmap={"v": NS_VISIO_2012},
    )

    etree.SubElement(
        page_xml,
        qn("v:Connect"),
        {
            "FromSheet": str(new_id),
            "FromCell": "EndX",
            "ToSheet": str(to_shape_id),
        },
        nsmap={"v": NS_VISIO_2012},
    )

    pkg.mark_page_dirty(page_num)
    return new_id


# =============================================================================
# Group/Ungroup Helper Functions
# =============================================================================


def _is_connector_visio(shape_el: etree._Element) -> bool:
    """Check if shape is a 1D connector (has BeginX/EndX cells)."""
    begin_x = get_cell_value(shape_el, "BeginX")
    end_x = get_cell_value(shape_el, "EndX")
    return begin_x is not None and end_x is not None


def _has_rotation_visio(shape_el: etree._Element) -> bool:
    """Check if Angle cell is non-zero."""
    angle = get_cell_float(shape_el, "Angle")
    return angle is not None and abs(angle) > 0.001


def _get_shape_bounds_visio(
    shape_el: etree._Element,
) -> tuple[float, float, float, float] | None:
    """Get shape bounds (left_x, bottom_y, width, height) in inches.

    Uses PinX/PinY/Width/Height/LocPinX/LocPinY to calculate bounding box.
    Returns None if required cells are missing.
    """
    pin_x = get_cell_float(shape_el, "PinX")
    pin_y = get_cell_float(shape_el, "PinY")
    width = get_cell_float(shape_el, "Width")
    height = get_cell_float(shape_el, "Height")

    if pin_x is None or pin_y is None or width is None or height is None:
        return None

    # Get local pin (defaults to center)
    loc_pin_x = get_cell_float(shape_el, "LocPinX")
    loc_pin_y = get_cell_float(shape_el, "LocPinY")

    if loc_pin_x is None:
        loc_pin_x = width / 2
    if loc_pin_y is None:
        loc_pin_y = height / 2

    # Calculate bottom-left corner
    left_x = pin_x - loc_pin_x
    bottom_y = pin_y - loc_pin_y

    return (left_x, bottom_y, width, height)


def _is_nested_in_group_visio(shape_el: etree._Element) -> bool:
    """Check if shape is already inside a group."""
    parent = shape_el.getparent()
    if parent is None:
        return False
    # Chain: Shape -> Shapes -> Shape (group)
    grandparent = parent.getparent()
    if grandparent is None:
        return False
    # Check if grandparent is a group
    return grandparent.get("Type") == "Group"


# =============================================================================
# Group/Ungroup Operations
# =============================================================================


def group_shapes(
    pkg: VisioPackage,
    page_num: int,
    shape_ids: list[int],
) -> int:
    """Group multiple shapes into a new group.

    Args:
        pkg: Visio package
        page_num: 1-based page number
        shape_ids: List of shape IDs to group

    Returns:
        The new group's shape ID.

    Raises:
        ValueError: If shapes cannot be grouped.

    V1 Constraints:
        - Only unrotated shapes supported
        - Connectors (1D shapes) excluded
        - Nested groups not supported
        - All shapes must be on same page at top level
    """
    if len(shape_ids) < 2:
        raise ValueError("At least 2 shapes required to create a group")

    page_xml = pkg.get_page_xml(page_num)

    # Find the top-level Shapes container
    shapes_containers = findall_v(page_xml, "Shapes")
    if not shapes_containers:
        raise ValueError(f"Page {page_num} has no Shapes container")
    shapes_container = shapes_containers[0]

    # Find all shapes to group at top level
    shapes_to_group = []
    for shape_el in findall_v(shapes_container, "Shape"):
        id_str = shape_el.get("ID")
        if id_str and int(id_str) in shape_ids:
            shape_id = int(id_str)

            # Validate constraints
            if _is_connector_visio(shape_el):
                raise ValueError(
                    f"Cannot group connectors (shape {shape_id}). "
                    "Remove connectors from selection."
                )

            if _has_rotation_visio(shape_el):
                raise ValueError(
                    f"Shape {shape_id} has rotation. V1 only supports unrotated shapes."
                )

            if shape_el.get("Type") == "Group":
                raise ValueError(
                    f"Shape {shape_id} is a group. Nested groups not supported in V1."
                )

            if _is_nested_in_group_visio(shape_el):
                raise ValueError(
                    f"Shape {shape_id} is already in a group. "
                    "Nested groups not supported in V1."
                )

            bounds = _get_shape_bounds_visio(shape_el)
            if bounds is None:
                raise ValueError(f"Shape {shape_id} has missing position/size cells.")

            shapes_to_group.append((shape_el, bounds))

    if len(shapes_to_group) != len(shape_ids):
        found_ids = {int(s.get("ID")) for s, _ in shapes_to_group if s.get("ID")}
        missing = set(shape_ids) - found_ids
        raise ValueError(
            f"Shapes not found at top level: {missing}. "
            "Shapes may be inside groups or on different pages."
        )

    # Calculate bounding box for group
    min_x = min(b[0] for _, b in shapes_to_group)
    min_y = min(b[1] for _, b in shapes_to_group)
    max_x = max(b[0] + b[2] for _, b in shapes_to_group)
    max_y = max(b[1] + b[3] for _, b in shapes_to_group)

    group_width = max_x - min_x
    group_height = max_y - min_y
    group_pin_x = min_x + group_width / 2
    group_pin_y = min_y + group_height / 2

    # Allocate new shape ID
    group_id = _get_max_shape_id(pkg, page_num) + 1

    # Track first shape's position for insertion
    first_shape_idx = None
    ordered_shapes = []
    for idx, child in enumerate(shapes_container):
        if child in [s for s, _ in shapes_to_group]:
            if first_shape_idx is None:
                first_shape_idx = idx
            ordered_shapes.append(child)

    # Create group element
    group_el = etree.Element(
        qn("v:Shape"),
        {"ID": str(group_id), "Type": "Group"},
        nsmap={"v": NS_VISIO_2012},
    )

    # Add group position cells
    group_el.append(_make_cell("PinX", str(group_pin_x), "IN"))
    group_el.append(_make_cell("PinY", str(group_pin_y), "IN"))
    group_el.append(_make_cell("Width", str(group_width), "IN"))
    group_el.append(_make_cell("Height", str(group_height), "IN"))
    group_el.append(_make_cell("LocPinX", str(group_width / 2), "IN"))
    group_el.append(_make_cell("LocPinY", str(group_height / 2), "IN"))

    # Create nested Shapes container
    nested_shapes = etree.SubElement(
        group_el, qn("v:Shapes"), nsmap={"v": NS_VISIO_2012}
    )

    # Move children to group (Visio children keep absolute coordinates!)
    for shape_el in ordered_shapes:
        shapes_container.remove(shape_el)
        nested_shapes.append(shape_el)

    # Insert group at first shape's position
    shapes_container.insert(first_shape_idx, group_el)

    pkg.mark_page_dirty(page_num)
    return group_id


def ungroup(
    pkg: VisioPackage,
    page_num: int,
    group_id: int,
) -> list[int]:
    """Ungroup a group, promoting children to page level.

    Args:
        pkg: Visio package
        page_num: 1-based page number
        group_id: Shape ID of the group to ungroup

    Returns:
        List of shape IDs of the ungrouped children.

    Raises:
        ValueError: If shape is not a group or has unsupported properties.

    V1 Constraints:
        - Only unrotated groups supported
        - Nested groups not supported
    """
    page_xml = pkg.get_page_xml(page_num)

    # Find the top-level Shapes container
    shapes_containers = findall_v(page_xml, "Shapes")
    if not shapes_containers:
        raise ValueError(f"Page {page_num} has no Shapes container")
    shapes_container = shapes_containers[0]

    # Find the group at top level
    group_el = None
    group_idx = None
    for idx, shape_el in enumerate(shapes_container):
        id_str = shape_el.get("ID")
        if id_str and int(id_str) == group_id:
            group_el = shape_el
            group_idx = idx
            break

    if group_el is None:
        raise ValueError(f"Group {group_id} not found at top level on page {page_num}")

    if group_el.get("Type") != "Group":
        raise ValueError(f"Shape {group_id} is not a group")

    if _has_rotation_visio(group_el):
        raise ValueError("Group has rotation. V1 only supports unrotated groups.")

    # Find nested Shapes container
    nested_shapes_list = list(findall_v(group_el, "Shapes"))
    if not nested_shapes_list:
        raise ValueError(f"Group {group_id} has no nested Shapes container")
    nested_shapes = nested_shapes_list[0]

    # Check for nested groups
    for child in findall_v(nested_shapes, "Shape"):
        if child.get("Type") == "Group":
            raise ValueError(
                "Group contains nested groups. V1 does not support ungrouping nested groups."
            )

    # Collect children
    children = list(findall_v(nested_shapes, "Shape"))
    if not children:
        raise ValueError(f"Group {group_id} has no child shapes")

    # Collect child IDs
    result_ids = []
    for child in children:
        id_str = child.get("ID")
        if id_str:
            result_ids.append(int(id_str))

    # Move children to page level (Visio children already have absolute coords!)
    for i, child in enumerate(children):
        nested_shapes.remove(child)
        shapes_container.insert(group_idx + i, child)

    # Remove the group element
    shapes_container.remove(group_el)

    pkg.mark_page_dirty(page_num)
    return result_ids
