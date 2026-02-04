"""Comment operations.

Contains functions for:
- Building comment lists (simple and with threading)
- Adding comments to blocks
- Replying to comments
- Resolving/unresolving comments
- Threading and extended comment info
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from lxml import etree

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.models import CommentInfo

# =============================================================================
# Constants
# =============================================================================

# Word 2012 namespace for extended comment features
_W15_NS = "http://schemas.microsoft.com/office/word/2012/wordml"
_COMMENTS_EXT_NS = {"w15": _W15_NS}

# Content type for commentsExtended.xml
_COMMENTS_EXTENDED_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml"


# =============================================================================
# Pure OOXML Comment Parsing
# =============================================================================


def _build_comments_ooxml(pkg) -> dict[int, dict]:
    """Build comments dict from /word/comments.xml (pure OOXML).

    Returns: {comment_id: {id, author, initials, timestamp, text, para_id, ...}}
    """
    comments = {}

    if not pkg.has_part("/word/comments.xml"):
        return comments

    comments_xml = pkg.get_xml("/word/comments.xml")

    for comment in comments_xml.iter(qn("w:comment")):
        # Get basic attributes
        comment_id = comment.get(qn("w:id"))
        if comment_id is None:
            continue
        comment_id = int(comment_id)

        author = comment.get(qn("w:author")) or ""
        initials = comment.get(qn("w:initials")) or ""
        date_str = comment.get(qn("w:date"))

        # Parse date if present
        timestamp = None
        if date_str:
            # ISO 8601 format: 2024-01-15T10:30:00Z
            timestamp = date_str

        # Get w15:paraId for threading linkage
        para_id = comment.get(f"{{{_W15_NS}}}paraId")

        # Extract text from comment content (w:p/w:r/w:t)
        text_parts = []
        for t in comment.iter(qn("w:t")):
            if t.text:
                text_parts.append(t.text)
        text = "".join(text_parts)

        comments[comment_id] = {
            "id": comment_id,
            "author": author,
            "initials": initials,
            "timestamp": timestamp,
            "text": text,
            "para_id": para_id,
            "parent_id": None,
            "resolved": False,
            "replies": [],
        }

    return comments


def _parse_comment_threading_ooxml(pkg) -> dict[str, dict]:
    """Parse threading/resolution from /word/commentsExtended.xml (pure OOXML).

    Returns: {para_id: {'parent_para_id': str|None, 'done': bool}}
    """
    result = {}

    if not pkg.has_part("/word/commentsExtended.xml"):
        return result

    ext_xml = pkg.get_xml("/word/commentsExtended.xml")

    # w15:paraId, w15:done, w15:paraIdParent attributes
    para_id_attr = f"{{{_W15_NS}}}paraId"
    done_attr = f"{{{_W15_NS}}}done"
    parent_attr = f"{{{_W15_NS}}}paraIdParent"

    for comment_ex in ext_xml.iter(f"{{{_W15_NS}}}commentEx"):
        para_id = comment_ex.get(para_id_attr)
        if not para_id:
            continue

        done_str = comment_ex.get(done_attr)
        done = done_str == "1" if done_str else False

        parent_para_id = comment_ex.get(parent_attr)

        result[para_id] = {"parent_para_id": parent_para_id, "done": done}

    return result


def _build_comments_with_threading_ooxml(pkg) -> list[dict]:
    """Build comments list with threading from pure OOXML."""
    comments = _build_comments_ooxml(pkg)

    if not comments:
        return []

    # Build para_id -> comment_id map
    para_id_map = {}
    for comment_id, comment in comments.items():
        para_id = comment.get("para_id")
        if para_id:
            para_id_map[para_id] = comment_id

    # Parse threading info
    threading_info = _parse_comment_threading_ooxml(pkg)

    # Apply threading info
    for para_id, info in threading_info.items():
        comment_id = para_id_map.get(para_id)
        if comment_id is None or comment_id not in comments:
            continue

        comments[comment_id]["resolved"] = info["done"]

        parent_para_id = info.get("parent_para_id")
        if parent_para_id:
            parent_comment_id = para_id_map.get(parent_para_id)
            if parent_comment_id is not None:
                comments[comment_id]["parent_id"] = parent_comment_id

    # Build replies lists
    for comment_id, comment in comments.items():
        parent_id = comment["parent_id"]
        if parent_id is not None and parent_id in comments:
            comments[parent_id]["replies"].append(comment_id)

    # Remove internal para_id field before returning
    for comment in comments.values():
        comment.pop("para_id", None)

    return sorted(comments.values(), key=lambda c: c["id"])


# =============================================================================
# Basic Comment Functions
# =============================================================================

# Namespace for comments.xml
_NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_COMMENTS_NSMAP = {"w": _NS_W, "w15": _W15_NS}

# Content type for comments.xml
_COMMENTS_CT = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
)

# Relationship type for comments
_COMMENTS_RT = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
)

# Relationship type for commentsExtended
_COMMENTS_EXT_RT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentsExtended"


def _generate_para_id() -> str:
    """Generate an 8-character hex para_id (Word format)."""
    return secrets.token_hex(4).upper()


def _create_comment_element(
    parent: etree._Element,
    comment_id: int,
    para_id: str,
    text: str,
    author: str,
    initials: str,
) -> etree._Element:
    """Create w:comment element with content."""
    comment_el = etree.SubElement(parent, qn("w:comment"))
    comment_el.set(qn("w:id"), str(comment_id))
    if author:
        comment_el.set(qn("w:author"), author)
    if initials:
        comment_el.set(qn("w:initials"), initials)
    comment_el.set(qn("w:date"), datetime.now(timezone.utc).isoformat())
    comment_el.set(f"{{{_W15_NS}}}paraId", para_id)

    comment_p = etree.SubElement(comment_el, qn("w:p"))
    comment_r = etree.SubElement(comment_p, qn("w:r"))
    comment_t = etree.SubElement(comment_r, qn("w:t"))
    comment_t.text = text
    if text and (text[0].isspace() or text[-1].isspace()):
        comment_t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    return comment_el


def _get_next_comment_id(pkg) -> int:
    """Get next available comment ID from comments.xml."""
    if not pkg.has_part("/word/comments.xml"):
        return 0

    comments_xml = pkg.get_xml("/word/comments.xml")
    max_id = -1
    for comment in comments_xml.iter(qn("w:comment")):
        comment_id = comment.get(qn("w:id"))
        if comment_id is not None:
            max_id = max(max_id, int(comment_id))
    return max_id + 1


def _ensure_comments_part(pkg) -> etree._Element:
    """Ensure /word/comments.xml exists and return its root element."""
    if pkg.has_part("/word/comments.xml"):
        return pkg.get_xml("/word/comments.xml")

    # Create minimal comments.xml
    comments_root = etree.Element(
        qn("w:comments"),
        nsmap={"w": _NS_W, "w15": _W15_NS},
    )
    pkg.set_xml("/word/comments.xml", comments_root, _COMMENTS_CT)
    pkg.relate_to("/word/document.xml", "comments.xml", _COMMENTS_RT)
    return comments_root


def _ensure_comments_extended_part(pkg) -> etree._Element:
    """Ensure /word/commentsExtended.xml exists and return its root element."""
    if pkg.has_part("/word/commentsExtended.xml"):
        return pkg.get_xml("/word/commentsExtended.xml")

    # Create minimal commentsExtended.xml
    ext_root = etree.Element(
        f"{{{_W15_NS}}}commentsEx",
        nsmap={"w15": _W15_NS},
    )
    pkg.set_xml("/word/commentsExtended.xml", ext_root, _COMMENTS_EXTENDED_CT)
    pkg.relate_to("/word/document.xml", "commentsExtended.xml", _COMMENTS_EXT_RT)
    return ext_root


def build_comments(pkg) -> list[CommentInfo]:
    """Build list of CommentInfo from document comments.

    Args:
        pkg: WordPackage
    """
    comments_dict = _build_comments_ooxml(pkg)
    return [
        CommentInfo(
            id=c["id"],
            author=c["author"],
            initials=c["initials"],
            timestamp=c["timestamp"],
            text=c["text"],
        )
        for c in comments_dict.values()
    ]


def add_comment_to_block(
    pkg,
    p_el: etree._Element,
    text: str,
    author: str = "",
    initials: str = "",
) -> int:
    """Add a comment anchored to a paragraph. Returns comment_id.

    Args:
        pkg: WordPackage
        p_el: Target w:p element (lxml element)
        text: Comment text
        author: Author name
        initials: Author initials
    """
    comments_xml = _ensure_comments_part(pkg)
    comment_id = _get_next_comment_id(pkg)
    para_id = _generate_para_id()
    _create_comment_element(comments_xml, comment_id, para_id, text, author, initials)

    # Insert comment markers into the target paragraph
    # Insert commentRangeStart at beginning
    range_start = etree.Element(qn("w:commentRangeStart"))
    range_start.set(qn("w:id"), str(comment_id))

    # Insert commentRangeEnd at end
    range_end = etree.Element(qn("w:commentRangeEnd"))
    range_end.set(qn("w:id"), str(comment_id))

    # Insert commentReference run at end
    ref_run = etree.Element(qn("w:r"))
    ref_rPr = etree.SubElement(ref_run, qn("w:rPr"))
    etree.SubElement(ref_rPr, qn("w:rStyle")).set(qn("w:val"), "CommentReference")
    comment_ref = etree.SubElement(ref_run, qn("w:commentReference"))
    comment_ref.set(qn("w:id"), str(comment_id))

    # Find position to insert markers
    # Insert rangeStart at start of paragraph (after pPr if exists)
    pPr = p_el.find(qn("w:pPr"))
    if pPr is not None:
        pPr_idx = list(p_el).index(pPr)
        p_el.insert(pPr_idx + 1, range_start)
    else:
        p_el.insert(0, range_start)

    # Insert rangeEnd and reference at end
    p_el.append(range_end)
    p_el.append(ref_run)

    pkg.mark_xml_dirty("/word/comments.xml")
    pkg.mark_xml_dirty("/word/document.xml")

    return comment_id


# =============================================================================
# Extended Comments (Threading/Resolution)
# =============================================================================


def build_comments_with_threading(pkg) -> list[dict]:
    """Build comments list with threading info from extended part.

    Args:
        pkg: WordPackage

    Falls back to flat list if commentsExtended.xml not present.
    Returns list of dicts compatible with CommentInfo model.
    """
    return _build_comments_with_threading_ooxml(pkg)


def _get_comment_by_id(
    pkg, comment_id: int
) -> tuple[etree._Element | None, str | None]:
    """Find comment element and its para_id by comment ID.

    Returns: (comment_element, para_id) or (None, None) if not found.
    """
    if not pkg.has_part("/word/comments.xml"):
        return None, None

    comments_xml = pkg.get_xml("/word/comments.xml")
    for comment in comments_xml.iter(qn("w:comment")):
        cid = comment.get(qn("w:id"))
        if cid is not None and int(cid) == comment_id:
            para_id = comment.get(f"{{{_W15_NS}}}paraId")
            return comment, para_id
    return None, None


def _find_comment_paragraph(pkg, comment_id: int) -> etree._Element | None:
    """Find paragraph containing comment range for given comment ID."""
    body = pkg.body
    range_start = body.find(
        f".//{qn('w:commentRangeStart')}[@{qn('w:id')}='{comment_id}']"
    )
    if range_start is None:
        return None

    # Walk up to find containing paragraph
    parent = range_start.getparent()
    while parent is not None:
        if parent.tag == qn("w:p"):
            return parent
        parent = parent.getparent()
    return None


def reply_to_comment(
    pkg, parent_id: int, text: str, author: str = "", initials: str = ""
) -> int:
    """Add reply to existing comment. Returns new comment ID.

    Args:
        pkg: WordPackage
        parent_id: ID of parent comment to reply to
        text: Reply text
        author: Author name
        initials: Author initials
    """
    # Validate parent comment exists and get its para_id
    parent_comment, parent_para_id = _get_comment_by_id(pkg, parent_id)
    if parent_comment is None:
        raise ValueError(f"Parent comment not found: {parent_id}")

    # Find paragraph containing parent comment
    p_el = _find_comment_paragraph(pkg, parent_id)
    if p_el is None:
        raise ValueError(f"Parent comment {parent_id} not attached to any paragraph")

    # Add reply comment
    comments_xml = _ensure_comments_part(pkg)
    comment_id = _get_next_comment_id(pkg)
    para_id = _generate_para_id()
    _create_comment_element(comments_xml, comment_id, para_id, text, author, initials)

    # Insert markers in paragraph
    range_start = etree.Element(qn("w:commentRangeStart"))
    range_start.set(qn("w:id"), str(comment_id))
    range_end = etree.Element(qn("w:commentRangeEnd"))
    range_end.set(qn("w:id"), str(comment_id))
    ref_run = etree.Element(qn("w:r"))
    ref_rPr = etree.SubElement(ref_run, qn("w:rPr"))
    etree.SubElement(ref_rPr, qn("w:rStyle")).set(qn("w:val"), "CommentReference")
    comment_ref = etree.SubElement(ref_run, qn("w:commentReference"))
    comment_ref.set(qn("w:id"), str(comment_id))

    pPr = p_el.find(qn("w:pPr"))
    if pPr is not None:
        pPr_idx = list(p_el).index(pPr)
        p_el.insert(pPr_idx + 1, range_start)
    else:
        p_el.insert(0, range_start)
    p_el.append(range_end)
    p_el.append(ref_run)

    # Set up threading in commentsExtended.xml
    if parent_para_id:
        ext_xml = _ensure_comments_extended_part(pkg)
        comment_ex = etree.SubElement(ext_xml, f"{{{_W15_NS}}}commentEx")
        comment_ex.set(f"{{{_W15_NS}}}paraId", para_id)
        comment_ex.set(f"{{{_W15_NS}}}paraIdParent", parent_para_id)
        comment_ex.set(f"{{{_W15_NS}}}done", "0")
        pkg.mark_xml_dirty("/word/commentsExtended.xml")

    pkg.mark_xml_dirty("/word/comments.xml")
    pkg.mark_xml_dirty("/word/document.xml")

    return comment_id


def _find_or_create_comment_ex(pkg, para_id: str) -> etree._Element:
    """Find or create commentEx element for given para_id."""
    ext_xml = _ensure_comments_extended_part(pkg)

    # Look for existing commentEx
    for comment_ex in ext_xml.iter(f"{{{_W15_NS}}}commentEx"):
        if comment_ex.get(f"{{{_W15_NS}}}paraId") == para_id:
            return comment_ex

    # Create new commentEx
    comment_ex = etree.SubElement(ext_xml, f"{{{_W15_NS}}}commentEx")
    comment_ex.set(f"{{{_W15_NS}}}paraId", para_id)
    return comment_ex


def resolve_comment(pkg, comment_id: int) -> None:
    """Mark comment as resolved.

    Args:
        pkg: WordPackage
        comment_id: ID of comment to resolve
    """
    # Validate comment exists and get para_id
    comment_el, para_id = _get_comment_by_id(pkg, comment_id)
    if comment_el is None:
        raise ValueError(f"Comment not found: {comment_id}")

    if not para_id:
        # Generate para_id if missing (older docs)
        para_id = _generate_para_id()
        comment_el.set(f"{{{_W15_NS}}}paraId", para_id)
        pkg.mark_xml_dirty("/word/comments.xml")

    # Set done="1" in commentsExtended.xml
    comment_ex = _find_or_create_comment_ex(pkg, para_id)
    comment_ex.set(f"{{{_W15_NS}}}done", "1")
    pkg.mark_xml_dirty("/word/commentsExtended.xml")


def unresolve_comment(pkg, comment_id: int) -> None:
    """Mark comment as unresolved (clears 'done' state).

    Args:
        pkg: WordPackage
        comment_id: ID of comment to unresolve

    Raises:
        ValueError: If comment not found.
    """
    # Validate comment exists and get para_id
    comment_el, para_id = _get_comment_by_id(pkg, comment_id)
    if comment_el is None:
        raise ValueError(f"Comment not found: {comment_id}")

    if not para_id:
        # Generate para_id if missing (older docs)
        para_id = _generate_para_id()
        comment_el.set(f"{{{_W15_NS}}}paraId", para_id)
        pkg.mark_xml_dirty("/word/comments.xml")

    # Set done="0" in commentsExtended.xml (create if needed)
    comment_ex = _find_or_create_comment_ex(pkg, para_id)
    comment_ex.set(f"{{{_W15_NS}}}done", "0")
    pkg.mark_xml_dirty("/word/commentsExtended.xml")
