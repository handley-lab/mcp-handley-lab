"""Comment operations for Visio.

Reads comments from /visio/comments.xml. Visio comments can be attached to:
- Pages (shape_id is null)
- Shapes on a page (shape_id is set)
"""

from __future__ import annotations

from mcp_handley_lab.microsoft.visio.constants import RT, findall_v
from mcp_handley_lab.microsoft.visio.models import CommentInfo
from mcp_handley_lab.microsoft.visio.package import VisioPackage


def _get_comment_authors(pkg: VisioPackage) -> dict[str, str]:
    """Build mapping of author ID -> name from comments.xml authors section."""
    comments_xml = _get_comments_xml(pkg)
    if comments_xml is None:
        return {}

    result = {}
    for author in findall_v(comments_xml, "AuthorEntry"):
        author_id = author.get("ID")
        name = author.get("Name")
        if author_id is not None and name:
            result[author_id] = name

    return result


def _get_comments_xml(pkg: VisioPackage):
    """Get comments.xml from the document if it exists."""
    # Visio comments are related from the document part
    document_path = pkg.document_path
    if document_path is None:
        return None

    rels = pkg.get_rels(document_path)
    comments_rid = rels.rId_for_reltype(RT.COMMENTS)
    if comments_rid is None:
        return None

    comments_path = pkg.resolve_rel_target(document_path, comments_rid)
    if not pkg.has_part(comments_path):
        return None

    return pkg.get_xml(comments_path)


def list_comments(pkg: VisioPackage, page_num: int | None = None) -> list[CommentInfo]:
    """List comments in a Visio document.

    Args:
        pkg: Visio package.
        page_num: Optional page number filter (1-based). If None, return all comments.

    Returns:
        List of CommentInfo for each comment.
    """
    comments_xml = _get_comments_xml(pkg)
    if comments_xml is None:
        return []

    authors = _get_comment_authors(pkg)
    results = []

    for comment in findall_v(comments_xml, "CommentEntry"):
        page_id_str = comment.get("PageID")
        if page_id_str is None:
            continue

        page_id = int(page_id_str)

        # Filter by page if specified
        if page_num is not None and page_id != page_num:
            continue

        # Get shape ID (optional - null for page-level comments)
        shape_id_str = comment.get("ShapeID")
        shape_id = int(shape_id_str) if shape_id_str else None

        # Get author info
        author_id = comment.get("AuthorID")
        author_name = authors.get(author_id) if author_id else None

        # Get date
        date_str = comment.get("Date")

        # Get comment text from child Text element
        text = ""
        text_el = comment.find("Text")
        if text_el is None:
            # Try with namespace
            for t in findall_v(comment, "Text"):
                if t.text:
                    text = t.text
                    break
        elif text_el.text:
            text = text_el.text

        results.append(
            CommentInfo(
                page_id=page_id,
                shape_id=shape_id,
                author=author_name,
                author_id=author_id,
                text=text,
                date=date_str,
            )
        )

    return results
