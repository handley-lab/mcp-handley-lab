"""Comment operations for PowerPoint.

Reads legacy comments from presentation. PowerPoint stores comments:
- /ppt/commentAuthors.xml: List of comment authors (id, name)
- /ppt/comments/comment{n}.xml: Comments for each slide

Note: Modern "threaded comments" (p:cmtList in different namespace) are not supported.
"""

from __future__ import annotations

from mcp_handley_lab.microsoft.powerpoint.constants import NSMAP, RT, qn
from mcp_handley_lab.microsoft.powerpoint.models import CommentInfo
from mcp_handley_lab.microsoft.powerpoint.package import PowerPointPackage


def _get_comment_authors(pkg: PowerPointPackage) -> dict[int, str]:
    """Build mapping of author ID -> name from commentAuthors.xml."""
    pres_path = "/ppt/presentation.xml"
    pres_rels = pkg.get_rels(pres_path)

    rid = pres_rels.rId_for_reltype(RT.COMMENT_AUTHORS)
    if rid is None:
        return {}

    authors_path = pkg.resolve_rel_target(pres_path, rid)
    if not pkg.has_part(authors_path):
        return {}

    authors_xml = pkg.get_xml(authors_path)

    result = {}
    for author in authors_xml.iter(qn("p:cmAuthor")):
        author_id = author.get("id")
        name = author.get("name")
        if author_id is not None and name:
            result[int(author_id)] = name

    return result


def list_comments(
    pkg: PowerPointPackage, slide_num: int | None = None
) -> list[CommentInfo]:
    """List comments in a presentation.

    Args:
        pkg: PowerPoint package.
        slide_num: Optional slide number filter (1-based). If None, return all comments.

    Returns:
        List of CommentInfo for each comment.
    """
    authors = _get_comment_authors(pkg)
    results = []

    # Get slides to check
    slide_paths = pkg.get_slide_paths()

    for num, _rid, slide_partname in slide_paths:
        if slide_num is not None and num != slide_num:
            continue

        # Look for comments relationship on this slide
        slide_rels = pkg.get_rels(slide_partname)
        comments_rid = slide_rels.rId_for_reltype(RT.COMMENTS)
        if comments_rid is None:
            continue

        comments_path = pkg.resolve_rel_target(slide_partname, comments_rid)
        if not pkg.has_part(comments_path):
            continue

        comments_xml = pkg.get_xml(comments_path)

        # Parse comments
        for cm in comments_xml.iter(qn("p:cm")):
            author_id_str = cm.get("authorId")
            author_id = int(author_id_str) if author_id_str else None
            author_name = authors.get(author_id) if author_id is not None else None

            # Get timestamp
            date_str = cm.get("dt")

            # Get position (in EMUs)
            pos = cm.find(qn("p:pos"), NSMAP)
            x_pos = None
            y_pos = None
            if pos is not None:
                x_str = pos.get("x")
                y_str = pos.get("y")
                if x_str:
                    x_pos = float(x_str)
                if y_str:
                    y_pos = float(y_str)

            # Get text from p:text element
            text_el = cm.find(qn("p:text"), NSMAP)
            text = text_el.text if text_el is not None and text_el.text else ""

            results.append(
                CommentInfo(
                    slide_num=num,
                    author=author_name,
                    author_id=author_id,
                    text=text,
                    date=date_str,
                    x_pos=x_pos,
                    y_pos=y_pos,
                )
            )

    return results
