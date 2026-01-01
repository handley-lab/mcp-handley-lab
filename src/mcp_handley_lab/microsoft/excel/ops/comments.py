"""Comments operations for Excel.

Comments (notes) provide annotations on cells. In OOXML:
- /xl/comments{n}.xml contains comment text and author
- /xl/drawings/vmlDrawing{n}.vml contains positioning (legacy VML format)
- Sheet XML has <legacyDrawing r:id="..."/> reference
"""

from __future__ import annotations

import hashlib
import re

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import CT, NSMAP, RT, qn
from mcp_handley_lab.microsoft.excel.models import CommentInfo
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    insert_sheet_element,
    parse_cell_ref,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    get_sheet_path as _get_sheet_path,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def _make_comment_id(sheet_name: str, ref: str) -> str:
    """Generate content-addressed ID for a comment."""
    content = f"{sheet_name}:{ref}"
    hash_val = hashlib.sha1(content.encode()).hexdigest()[:8]
    safe_sheet = sheet_name.replace(" ", "_")
    return f"comment_{safe_sheet}_{ref}_{hash_val}"


def _find_comments_path(pkg: ExcelPackage, sheet_path: str) -> str | None:
    """Find comments part path for a sheet if it exists."""
    rels = pkg.get_rels(sheet_path)
    rId = rels.rId_for_reltype(RT.COMMENTS)
    if rId:
        return pkg.resolve_rel_target(sheet_path, rId)
    return None


def _find_vml_path(pkg: ExcelPackage, sheet_path: str) -> str | None:
    """Find VML drawing path for a sheet if it exists."""
    rels = pkg.get_rels(sheet_path)
    rId = rels.rId_for_reltype(RT.VML_DRAWING)
    if rId:
        return pkg.resolve_rel_target(sheet_path, rId)
    return None


def _next_part_number(pkg: ExcelPackage, pattern: str) -> int:
    """Find next available number for parts matching pattern."""
    regex = re.compile(pattern.replace("{n}", r"(\d+)"))
    max_n = 0
    for partname in pkg.iter_partnames():
        match = regex.search(partname)
        if match:
            max_n = max(max_n, int(match.group(1)))
    return max_n + 1


def _cell_ref_to_indices(ref: str) -> tuple[int, int]:
    """Parse cell reference to (col, row) 1-based indices."""
    col_letter, row, _, _ = parse_cell_ref(ref)
    return column_letter_to_index(col_letter), row


def _create_comments_xml(authors: list[str]) -> etree._Element:
    """Create empty comments.xml structure."""
    root = etree.Element(qn("x:comments"), nsmap={None: NSMAP["x"]})
    authors_el = etree.SubElement(root, qn("x:authors"))
    for author in authors:
        author_el = etree.SubElement(authors_el, qn("x:author"))
        author_el.text = author
    etree.SubElement(root, qn("x:commentList"))
    return root


# VML namespace
VML_NS = "urn:schemas-microsoft-com:vml"
VML_OFFICE_NS = "urn:schemas-microsoft-com:office:office"
VML_EXCEL_NS = "urn:schemas-microsoft-com:office:excel"


def _create_vml_xml() -> etree._Element:
    """Create empty VML drawing structure for comments.

    VML is legacy XML format but still required for Excel comment positioning.
    """
    # VML requires specific namespace handling
    # Root element is <xml> in no namespace (not <v:xml>)
    nsmap = {
        "v": VML_NS,
        "o": VML_OFFICE_NS,
        "x": VML_EXCEL_NS,
    }
    root = etree.Element("xml", nsmap=nsmap)

    # Add shapelayout element (required)
    shapelayout = etree.SubElement(root, f"{{{VML_OFFICE_NS}}}shapelayout")
    shapelayout.set(f"{{{VML_OFFICE_NS}}}ext", "edit")
    idmap = etree.SubElement(shapelayout, f"{{{VML_OFFICE_NS}}}idmap")
    idmap.set(f"{{{VML_OFFICE_NS}}}ext", "edit")
    idmap.set("data", "1")

    # Add shapetype definition (required for comment shapes)
    # This defines the text box shape type referenced by comment shapes
    shapetype = etree.SubElement(
        root,
        f"{{{VML_NS}}}shapetype",
        id="_x0000_t202",
        coordsize="21600,21600",
        path="m,l,21600r21600,l21600,xe",
    )
    shapetype.set(f"{{{VML_OFFICE_NS}}}spt", "202")
    etree.SubElement(shapetype, f"{{{VML_NS}}}stroke", joinstyle="miter")
    path = etree.SubElement(shapetype, f"{{{VML_NS}}}path", gradientshapeok="t")
    path.set(f"{{{VML_OFFICE_NS}}}connecttype", "rect")

    return root


def _add_vml_shape(vml_root: etree._Element, col: int, row: int, shape_id: int) -> None:
    """Add a VML shape for a comment at given cell position."""
    # VML uses 0-based coordinates
    col_0 = col - 1
    row_0 = row - 1

    # Create shape element
    shape = etree.SubElement(
        vml_root,
        f"{{{VML_NS}}}shape",
        id=f"_x0000_s{shape_id}",
        type="#_x0000_t202",
        style=(
            "position:absolute;margin-left:auto;margin-top:auto;"
            "width:108pt;height:59.25pt;z-index:1;visibility:hidden"
        ),
        fillcolor="#ffffe1",
        stroked="t",
    )
    shape.set(f"{{{VML_OFFICE_NS}}}insetmode", "auto")

    # Fill
    etree.SubElement(shape, f"{{{VML_NS}}}fill", color2="#ffffe1")
    # Stroke
    etree.SubElement(shape, f"{{{VML_NS}}}stroke", joinstyle="miter")
    # Shadow
    etree.SubElement(shape, f"{{{VML_NS}}}shadow", on="t", obscured="t")
    # Path
    etree.SubElement(shape, f"{{{VML_NS}}}path", connecttype="none").set(
        f"{{{VML_OFFICE_NS}}}connecttype", "none"
    )
    # Textbox
    etree.SubElement(shape, f"{{{VML_NS}}}textbox", style="mso-direction-alt:auto")
    # ClientData (Excel-specific positioning)
    client_data = etree.SubElement(shape, f"{{{VML_EXCEL_NS}}}ClientData")
    client_data.set("ObjectType", "Note")
    etree.SubElement(client_data, f"{{{VML_EXCEL_NS}}}MoveWithCells")
    etree.SubElement(client_data, f"{{{VML_EXCEL_NS}}}SizeWithCells")
    # Anchor: left-col, left-offset, top-row, top-offset, right-col, right-offset, bottom-row, bottom-offset
    anchor = etree.SubElement(client_data, f"{{{VML_EXCEL_NS}}}Anchor")
    anchor.text = f"{col_0 + 1}, 15, {row_0}, 10, {col_0 + 3}, 15, {row_0 + 4}, 4"
    etree.SubElement(client_data, f"{{{VML_EXCEL_NS}}}AutoFill").text = "False"
    etree.SubElement(client_data, f"{{{VML_EXCEL_NS}}}Row").text = str(row_0)
    etree.SubElement(client_data, f"{{{VML_EXCEL_NS}}}Column").text = str(col_0)


def list_comments(pkg: ExcelPackage, sheet_name: str) -> list[CommentInfo]:
    """List all comments on a sheet.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.

    Returns: List of CommentInfo for each comment.
    """
    sheet_path = _get_sheet_path(pkg, sheet_name)
    comments_path = _find_comments_path(pkg, sheet_path)
    if not comments_path:
        return []

    comments_xml = pkg.get_xml(comments_path)

    # Build author index
    authors: list[str] = []
    authors_el = comments_xml.find(qn("x:authors"))
    if authors_el is not None:
        for author_el in authors_el.findall(qn("x:author")):
            authors.append(author_el.text or "")

    # Parse comments
    result = []
    comment_list = comments_xml.find(qn("x:commentList"))
    if comment_list is not None:
        for comment_el in comment_list.findall(qn("x:comment")):
            ref = comment_el.get("ref", "")
            author_id = int(comment_el.get("authorId", "0"))
            author = authors[author_id] if author_id < len(authors) else None

            # Get text from <text><t>...</t></text> or <text><r><t>...</t></r></text>
            text_el = comment_el.find(qn("x:text"))
            text = ""
            if text_el is not None:
                # Simple text
                t_el = text_el.find(qn("x:t"))
                if t_el is not None and t_el.text:
                    text = t_el.text
                else:
                    # Rich text runs
                    parts = []
                    for r in text_el.findall(qn("x:r")):
                        t = r.find(qn("x:t"))
                        if t is not None and t.text:
                            parts.append(t.text)
                    text = "".join(parts)

            result.append(
                CommentInfo(
                    id=_make_comment_id(sheet_name, ref),
                    ref=ref,
                    text=text,
                    author=author,
                )
            )

    return result


def get_comment(
    pkg: ExcelPackage, sheet_name: str, cell_ref: str
) -> CommentInfo | None:
    """Get comment on a specific cell.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        cell_ref: Cell reference (e.g., "A1").

    Returns: CommentInfo if exists, None otherwise.
    """
    cell_ref = cell_ref.upper()
    for comment in list_comments(pkg, sheet_name):
        if comment.ref.upper() == cell_ref:
            return comment
    return None


def add_comment(
    pkg: ExcelPackage,
    sheet_name: str,
    cell_ref: str,
    text: str,
    author: str | None = None,
) -> CommentInfo:
    """Add a comment to a cell.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        cell_ref: Cell reference (e.g., "A1").
        text: Comment text.
        author: Optional author name (defaults to "Author").

    Returns: CommentInfo for the created comment.
    """
    cell_ref = cell_ref.upper()
    sheet_path = _get_sheet_path(pkg, sheet_name)
    author = author or "Author"

    # Get or create comments part
    comments_path = _find_comments_path(pkg, sheet_path)
    if comments_path and pkg.has_part(comments_path):
        comments_xml = pkg.get_xml(comments_path)
    else:
        # Create new comments part
        n = _next_part_number(pkg, r"/xl/comments(\d+)\.xml")
        comments_path = f"/xl/comments{n}.xml"
        comments_xml = _create_comments_xml([author])
        pkg.set_xml(comments_path, comments_xml, CT.SML_COMMENTS)
        # Add relationship from sheet to comments
        pkg.relate_to(sheet_path, f"../comments{n}.xml", RT.COMMENTS)

    # Get or create VML drawing
    vml_path = _find_vml_path(pkg, sheet_path)
    if vml_path and pkg.has_part(vml_path):
        vml_xml = pkg.get_xml(vml_path)
    else:
        # Create new VML drawing
        n = _next_part_number(pkg, r"/xl/drawings/vmlDrawing(\d+)\.vml")
        vml_path = f"/xl/drawings/vmlDrawing{n}.vml"
        vml_xml = _create_vml_xml()
        pkg.set_xml(
            vml_path,
            vml_xml,
            "application/vnd.openxmlformats-officedocument.vmlDrawing",
        )
        # Add relationship from sheet to VML
        vml_rId = pkg.relate_to(
            sheet_path, f"../drawings/vmlDrawing{n}.vml", RT.VML_DRAWING
        )
        # Add legacyDrawing element to sheet at correct position
        sheet_xml = pkg.get_sheet_xml(sheet_name)
        legacy_drawing = sheet_xml.find(qn("x:legacyDrawing"))
        if legacy_drawing is None:
            legacy_drawing = etree.Element(qn("x:legacyDrawing"))
            insert_sheet_element(sheet_xml, "legacyDrawing", legacy_drawing)
        legacy_drawing.set(qn("r:id"), vml_rId)
        pkg.mark_xml_dirty(sheet_path)

    # Find or add author
    authors_el = comments_xml.find(qn("x:authors"))
    author_id = None
    for i, author_el in enumerate(authors_el.findall(qn("x:author"))):
        if author_el.text == author:
            author_id = i
            break
    if author_id is None:
        author_id = len(authors_el.findall(qn("x:author")))
        new_author = etree.SubElement(authors_el, qn("x:author"))
        new_author.text = author

    # Add comment to commentList
    comment_list = comments_xml.find(qn("x:commentList"))
    comment_el = etree.SubElement(comment_list, qn("x:comment"))
    comment_el.set("ref", cell_ref)
    comment_el.set("authorId", str(author_id))
    text_el = etree.SubElement(comment_el, qn("x:text"))
    t_el = etree.SubElement(text_el, qn("x:t"))
    t_el.text = text
    # Preserve whitespace if needed
    if text and (text[0].isspace() or text[-1].isspace()):
        t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    pkg.mark_xml_dirty(comments_path)

    # Add VML shape for the comment
    col, row = _cell_ref_to_indices(cell_ref)
    # Count existing shapes to get unique ID
    shape_count = len(vml_xml.findall(f".//{{{VML_NS}}}shape"))
    _add_vml_shape(vml_xml, col, row, 1024 + shape_count)
    pkg.mark_xml_dirty(vml_path)

    return CommentInfo(
        id=_make_comment_id(sheet_name, cell_ref),
        ref=cell_ref,
        text=text,
        author=author,
    )


def delete_comment(pkg: ExcelPackage, sheet_name: str, cell_ref: str) -> None:
    """Delete a comment from a cell.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        cell_ref: Cell reference (e.g., "A1").

    Raises: KeyError if no comment exists on cell.
    """
    cell_ref = cell_ref.upper()
    sheet_path = _get_sheet_path(pkg, sheet_name)
    comments_path = _find_comments_path(pkg, sheet_path)

    if not comments_path or not pkg.has_part(comments_path):
        raise KeyError(f"No comment on {cell_ref}")

    comments_xml = pkg.get_xml(comments_path)
    comment_list = comments_xml.find(qn("x:commentList"))
    if comment_list is None:
        raise KeyError(f"No comment on {cell_ref}")

    # Find and remove the comment
    found = False
    for _i, comment_el in enumerate(comment_list.findall(qn("x:comment"))):
        if comment_el.get("ref", "").upper() == cell_ref:
            comment_list.remove(comment_el)
            found = True
            break

    if not found:
        raise KeyError(f"No comment on {cell_ref}")

    pkg.mark_xml_dirty(comments_path)

    # Remove corresponding VML shape
    vml_path = _find_vml_path(pkg, sheet_path)
    if vml_path and pkg.has_part(vml_path):
        vml_xml = pkg.get_xml(vml_path)
        col, row = _cell_ref_to_indices(cell_ref)

        # Find shape by matching Row/Column in ClientData
        shapes = vml_xml.findall(f".//{{{VML_NS}}}shape")
        for shape in shapes:
            client_data = shape.find(f"{{{VML_EXCEL_NS}}}ClientData")
            if client_data is not None:
                row_el = client_data.find(f"{{{VML_EXCEL_NS}}}Row")
                col_el = client_data.find(f"{{{VML_EXCEL_NS}}}Column")
                if row_el is not None and col_el is not None:
                    vml_row = int(row_el.text or "0")
                    vml_col = int(col_el.text or "0")
                    # VML uses 0-based coords
                    if vml_row == row - 1 and vml_col == col - 1:
                        # Remove from actual parent (shape may not be direct child)
                        parent = shape.getparent()
                        if parent is not None:
                            parent.remove(shape)
                        pkg.mark_xml_dirty(vml_path)
                        break

    # If no comments left, clean up parts and relationships
    remaining = len(comment_list.findall(qn("x:comment")))
    if remaining == 0:
        # Remove comments relationship before dropping part
        rels = pkg.get_rels(sheet_path)
        comments_rId = rels.rId_for_reltype(RT.COMMENTS)
        if comments_rId:
            pkg.remove_rel(sheet_path, comments_rId)
        pkg.drop_part(comments_path)

        # Also drop VML if empty
        if vml_path and pkg.has_part(vml_path):
            vml_xml = pkg.get_xml(vml_path)
            if len(vml_xml.findall(f".//{{{VML_NS}}}shape")) == 0:
                # Remove VML relationship before dropping part
                vml_rId = rels.rId_for_reltype(RT.VML_DRAWING)
                if vml_rId:
                    pkg.remove_rel(sheet_path, vml_rId)
                pkg.drop_part(vml_path)
                # Remove legacyDrawing from sheet
                sheet_xml = pkg.get_sheet_xml(sheet_name)
                legacy_drawing = sheet_xml.find(qn("x:legacyDrawing"))
                if legacy_drawing is not None:
                    sheet_xml.remove(legacy_drawing)
                    pkg.mark_xml_dirty(sheet_path)


def update_comment(
    pkg: ExcelPackage, sheet_name: str, cell_ref: str, text: str
) -> CommentInfo:
    """Update the text of an existing comment.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        cell_ref: Cell reference (e.g., "A1").
        text: New comment text.

    Returns: Updated CommentInfo.

    Raises: KeyError if no comment exists on cell.
    """
    cell_ref = cell_ref.upper()
    sheet_path = _get_sheet_path(pkg, sheet_name)
    comments_path = _find_comments_path(pkg, sheet_path)

    if not comments_path or not pkg.has_part(comments_path):
        raise KeyError(f"No comment on {cell_ref}")

    comments_xml = pkg.get_xml(comments_path)
    comment_list = comments_xml.find(qn("x:commentList"))
    if comment_list is None:
        raise KeyError(f"No comment on {cell_ref}")

    # Find the comment
    for comment_el in comment_list.findall(qn("x:comment")):
        if comment_el.get("ref", "").upper() == cell_ref:
            # Update text
            text_el = comment_el.find(qn("x:text"))
            if text_el is None:
                text_el = etree.SubElement(comment_el, qn("x:text"))
            else:
                # Clear existing content
                for child in list(text_el):
                    text_el.remove(child)

            t_el = etree.SubElement(text_el, qn("x:t"))
            t_el.text = text
            if text and (text[0].isspace() or text[-1].isspace()):
                t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

            pkg.mark_xml_dirty(comments_path)

            # Get author
            author_id = int(comment_el.get("authorId", "0"))
            authors_el = comments_xml.find(qn("x:authors"))
            authors = [a.text or "" for a in authors_el.findall(qn("x:author"))]
            author = authors[author_id] if author_id < len(authors) else None

            return CommentInfo(
                id=_make_comment_id(sheet_name, cell_ref),
                ref=cell_ref,
                text=text,
                author=author,
            )

    raise KeyError(f"No comment on {cell_ref}")
