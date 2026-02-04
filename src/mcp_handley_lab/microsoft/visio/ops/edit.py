"""Edit operations for Visio shapes and pages.

Shape text, cell, and data modifications; shape deletion;
page add/delete/rename. All operations modify the XML in-place
and call mark_xml_dirty() on the affected part.
"""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.visio.constants import (
    CT,
    NS_REL,
    NS_VISIO_2012,
    RT,
    find_v,
    findall_v,
)
from mcp_handley_lab.microsoft.visio.ops.core import make_shape_key
from mcp_handley_lab.microsoft.visio.ops.shapes import find_shape_element
from mcp_handley_lab.microsoft.visio.package import VisioPackage

NS = NS_VISIO_2012


# =============================================================================
# Shape Operations
# =============================================================================


def set_shape_text(pkg: VisioPackage, page_num: int, shape_id: int, text: str) -> str:
    """Set the text content of a shape.

    Replaces all existing text content. Returns shape_key.
    """
    shape_el = find_shape_element(pkg, page_num, shape_id)
    if shape_el is None:
        raise ValueError(f"Shape {shape_id} not found on page {page_num}")

    # Remove existing Text element
    text_el = find_v(shape_el, "Text")
    if text_el is not None:
        shape_el.remove(text_el)

    # Create new Text element
    new_text = etree.SubElement(shape_el, f"{{{NS}}}Text")
    new_text.text = text

    pkg.mark_xml_dirty(pkg.get_page_partname(page_num))
    return make_shape_key(page_num, shape_id)


def set_shape_cell(
    pkg: VisioPackage,
    page_num: int,
    shape_id: int,
    cell_name: str,
    value: str,
    formula: str | None = None,
    unit: str | None = None,
) -> str:
    """Set a singleton Cell value on a shape.

    Creates the cell if it doesn't exist. Returns shape_key.
    """
    shape_el = find_shape_element(pkg, page_num, shape_id)
    if shape_el is None:
        raise ValueError(f"Shape {shape_id} not found on page {page_num}")

    # Find existing cell
    target_cell = None
    for cell in findall_v(shape_el, "Cell"):
        if cell.get("N") == cell_name:
            target_cell = cell
            break

    if target_cell is None:
        # Create new cell
        target_cell = etree.SubElement(shape_el, f"{{{NS}}}Cell", N=cell_name)

    target_cell.set("V", value)
    if formula is not None:
        target_cell.set("F", formula)
    elif "F" in target_cell.attrib:
        del target_cell.attrib["F"]
    if unit is not None:
        target_cell.set("U", unit)
    elif "U" in target_cell.attrib:
        del target_cell.attrib["U"]

    pkg.mark_xml_dirty(pkg.get_page_partname(page_num))
    return make_shape_key(page_num, shape_id)


def set_shape_data(
    pkg: VisioPackage,
    page_num: int,
    shape_id: int,
    row_name: str,
    value: str,
) -> str:
    """Set the Value cell in a Property section row.

    The row must already exist. Returns shape_key.
    """
    shape_el = find_shape_element(pkg, page_num, shape_id)
    if shape_el is None:
        raise ValueError(f"Shape {shape_id} not found on page {page_num}")

    # Find the Property section and row
    for section in findall_v(shape_el, "Section"):
        if section.get("N") != "Property":
            continue
        for row in findall_v(section, "Row"):
            if row.get("N") == row_name:
                # Find or create the Value cell
                value_cell = None
                for cell in findall_v(row, "Cell"):
                    if cell.get("N") == "Value":
                        value_cell = cell
                        break
                if value_cell is None:
                    value_cell = etree.SubElement(row, f"{{{NS}}}Cell", N="Value")
                value_cell.set("V", value)
                pkg.mark_xml_dirty(pkg.get_page_partname(page_num))
                return make_shape_key(page_num, shape_id)

    raise ValueError(
        f"Property row '{row_name}' not found on shape {shape_id}, page {page_num}"
    )


def delete_shape(pkg: VisioPackage, page_num: int, shape_id: int) -> None:
    """Delete a shape from a page by ID."""
    page_xml = pkg.get_page_xml(page_num)
    partname = pkg.get_page_partname(page_num)

    # Search recursively in all Shapes containers
    for container in findall_v(page_xml, "Shapes"):
        if _remove_shape_recursive(container, shape_id):
            pkg.mark_xml_dirty(partname)
            return

    raise ValueError(f"Shape {shape_id} not found on page {page_num}")


def _remove_shape_recursive(parent: etree._Element, shape_id: int) -> bool:
    """Recursively find and remove a shape by ID. Returns True if found."""
    for shape_el in findall_v(parent, "Shape"):
        if shape_el.get("ID") == str(shape_id):
            parent.remove(shape_el)
            return True
        # Recurse into group children
        for shapes_container in findall_v(shape_el, "Shapes"):
            if _remove_shape_recursive(shapes_container, shape_id):
                return True
    return False


# =============================================================================
# Page Operations
# =============================================================================


def add_page(pkg: VisioPackage, name: str | None = None) -> int:
    """Add a new blank page. Returns 1-based page number."""
    pages_xml = pkg.get_pages_xml()
    if pages_xml is None:
        raise ValueError("No pages.xml found in document")

    pages_path = pkg.pages_path
    if pages_path is None:
        raise ValueError("No pages path found")

    # Determine new page number and ID
    existing_pages = findall_v(pages_xml, "Page")
    new_num = len(existing_pages) + 1
    if name:
        page_name = name
    else:
        existing_names = {p.get("Name") for p in existing_pages}
        n = new_num
        while f"Page-{n}" in existing_names:
            n += 1
        page_name = f"Page-{n}"

    # Find next available page file number
    existing_partnames = {pn for _, _, pn in pkg.get_page_paths()}
    file_num = 1
    while f"/visio/pages/page{file_num}.xml" in existing_partnames:
        file_num += 1
    new_partname = f"/visio/pages/page{file_num}.xml"

    # Add relationship first to get the canonical rId
    target = f"page{file_num}.xml"
    new_rid = pkg.relate_to(pages_path, target, RT.PAGE)

    # Add Page element to pages.xml
    new_id = max((int(p.get("ID", "0")) for p in existing_pages), default=0) + 1

    page_el = etree.SubElement(
        pages_xml,
        f"{{{NS}}}Page",
        ID=str(new_id),
        Name=page_name,
        NameU=page_name,
        attrib={f"{{{NS_REL}}}id": new_rid},
    )
    page_sheet = etree.SubElement(page_el, f"{{{NS}}}PageSheet")
    etree.SubElement(page_sheet, f"{{{NS}}}Cell", N="PageWidth", V="8.5", U="IN")
    etree.SubElement(page_sheet, f"{{{NS}}}Cell", N="PageHeight", V="11", U="IN")

    pkg.mark_xml_dirty(pages_path)

    # Create empty page XML
    page_contents = etree.Element(f"{{{NS}}}PageContents")
    etree.SubElement(page_contents, f"{{{NS}}}Shapes")
    pkg.set_xml(new_partname, page_contents, CT.VSD_PAGE)

    # Invalidate caches
    pkg.invalidate_caches()

    return new_num


def delete_page(pkg: VisioPackage, page_num: int) -> None:
    """Delete a page by 1-based page number."""
    pages_xml = pkg.get_pages_xml()
    if pages_xml is None:
        raise ValueError("No pages.xml found")

    pages_path = pkg.pages_path
    if pages_path is None:
        raise ValueError("No pages path found")

    page_els = findall_v(pages_xml, "Page")
    if page_num < 1 or page_num > len(page_els):
        raise ValueError(f"Page {page_num} out of range (1-{len(page_els)})")

    if len(page_els) <= 1:
        raise ValueError("Cannot delete the only page")

    page_el = page_els[page_num - 1]

    # Get the rId and partname for this page
    rid = page_el.get(f"{{{NS_REL}}}id")

    # Remove the page XML part
    page_paths = pkg.get_page_paths()
    part_dropped = False
    for num, _rid, partname in page_paths:
        if num == page_num:
            pkg.drop_part(partname)
            part_dropped = True
            break
    if not part_dropped:
        raise ValueError(f"No page part found for page {page_num}")

    # Remove from pages.xml
    pages_xml.remove(page_el)
    pkg.mark_xml_dirty(pages_path)

    # Remove the relationship
    if rid:
        pkg.remove_rel(pages_path, rid)

    pkg.invalidate_caches()


def rename_page(pkg: VisioPackage, page_num: int, name: str) -> None:
    """Rename a page by 1-based page number."""
    pages_xml = pkg.get_pages_xml()
    if pages_xml is None:
        raise ValueError("No pages.xml found")

    pages_path = pkg.pages_path
    if pages_path is None:
        raise ValueError("No pages path found")

    page_els = findall_v(pages_xml, "Page")
    if page_num < 1 or page_num > len(page_els):
        raise ValueError(f"Page {page_num} out of range (1-{len(page_els)})")

    page_el = page_els[page_num - 1]
    page_el.set("Name", name)
    page_el.set("NameU", name)

    pkg.mark_xml_dirty(pages_path)
