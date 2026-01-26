"""Core Word document functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Image
from mcp.types import TextContent

from mcp_handley_lab.microsoft.word import document as word_ops
from mcp_handley_lab.microsoft.word.models import (
    BibAuthor,
    BibSourceInfo,
    Block,
    BookmarkInfo,
    CaptionInfo,
    CommentInfo,
    ContentControlInfo,
    DocumentReadResult,
    EditResult,
    EquationInfo,
    FootnoteInfo,
    ListInfo,
    OpResult,
    RevisionInfo,
    TextBoxInfo,
    TOCInfo,
)
from mcp_handley_lab.microsoft.word.package import WordPackage

if TYPE_CHECKING:
    pass


def read(
    file_path: str,
    scope: str = "outline",
    target_id: str = "",
    search_query: str = "",
    limit: int = 50,
    offset: int = 0,
) -> DocumentReadResult:
    """Read Word document content.

    Args:
        file_path: Path to .docx file.
        scope: What to read. Options:
            - 'meta': Document info
            - 'outline': Headings only
            - 'blocks': All content
            - 'search': Find text
            - 'table_cells': Cells of a table
            - 'table_layout': Table alignment/autofit/row heights
            - 'runs': Text runs in a paragraph
            - 'comments': All comments
            - 'headers_footers': Headers/footers per section
            - 'page_setup': Margins, orientation per section
            - 'images': Embedded inline images
            - 'hyperlinks': All hyperlinks with URLs
            - 'styles': All document styles
            - 'style': Detailed formatting for a specific style
            - 'revisions': Tracked changes/revisions
            - 'list': List properties for a paragraph
            - 'text_boxes': All text boxes/floating content
            - 'text_box_content': Paragraphs inside a text box
            - 'bookmarks': All bookmarks
            - 'captions': All captions
            - 'toc': Table of contents info
            - 'footnotes': All footnotes and endnotes
            - 'content_controls': All content controls/SDTs
            - 'equations': Math equations with simplified text
            - 'bibliography': Bibliography sources
        target_id: Block ID for table_cells/runs/table_layout/list scopes,
            style name for 'style' scope, or text box ID for 'text_box_content' scope.
        search_query: Text to search for (scope='search').
        limit: Max blocks to return.
        offset: Pagination offset.

    Returns:
        DocumentReadResult with requested content.
    """
    from mcp_handley_lab.microsoft.word.constants import qn

    pkg = WordPackage.open(file_path)

    if scope == "meta":
        meta = word_ops.get_document_meta(pkg)
        _, block_count = word_ops.build_blocks(pkg, offset=0, limit=0)
        return DocumentReadResult(block_count=block_count, meta=meta)
    if scope == "outline":
        blocks, block_count = word_ops.build_blocks(
            pkg, offset=offset, limit=limit, heading_only=True
        )
        return DocumentReadResult(block_count=block_count, blocks=blocks)
    if scope == "blocks":
        blocks, block_count = word_ops.build_blocks(pkg, offset=offset, limit=limit)
        return DocumentReadResult(block_count=block_count, blocks=blocks)
    if scope == "search":
        blocks, block_count = word_ops.build_blocks(
            pkg, offset=offset, limit=limit, search_query=search_query
        )
        return DocumentReadResult(block_count=block_count, blocks=blocks)
    if scope == "table_cells":
        t = word_ops.resolve_target(pkg, target_id)
        tbl_el = t.leaf_el
        cells = word_ops.build_table_cells(tbl_el, target_id)
        rows = tbl_el.findall(qn("w:tr"))
        max_cols = max((len(tr.findall(qn("w:tc"))) for tr in rows), default=0)
        return DocumentReadResult(
            block_count=len(cells),
            cells=cells,
            table_rows=len(rows),
            table_cols=max_cols,
        )
    if scope == "table_layout":
        t = word_ops.resolve_target(pkg, target_id)
        tbl_el = t.leaf_el
        table_layout = word_ops.build_table_layout(tbl_el, target_id)
        return DocumentReadResult(block_count=1, table_layout=table_layout)
    if scope == "runs":
        t = word_ops.resolve_target(pkg, target_id)
        if t.leaf_kind != "paragraph":
            raise ValueError(
                f"Target is not a paragraph: {target_id} (resolved to {t.leaf_kind})"
            )
        p_el = t.leaf_el
        doc_rels = pkg.get_rels("/word/document.xml")
        runs = word_ops.build_runs(p_el, doc_rels)
        paragraph_format = word_ops.build_paragraph_format(p_el)
        return DocumentReadResult(
            block_count=len(runs), runs=runs, paragraph_format=paragraph_format
        )
    if scope == "comments":
        comments_data = word_ops.build_comments_with_threading(pkg)
        comments = [CommentInfo(**c) for c in comments_data]
        return DocumentReadResult(block_count=len(comments), comments=comments)
    if scope == "headers_footers":
        headers_footers = word_ops.build_headers_footers(pkg)
        return DocumentReadResult(
            block_count=len(headers_footers), headers_footers=headers_footers
        )
    if scope == "page_setup":
        page_setup = word_ops.build_page_setup(pkg)
        return DocumentReadResult(block_count=len(page_setup), page_setup=page_setup)
    if scope == "images":
        images = word_ops.build_images(pkg)
        return DocumentReadResult(block_count=len(images), images=images)
    if scope == "hyperlinks":
        hyperlinks = word_ops.build_hyperlinks(pkg)
        return DocumentReadResult(block_count=len(hyperlinks), hyperlinks=hyperlinks)
    if scope == "styles":
        styles = word_ops.build_styles(pkg)
        return DocumentReadResult(block_count=len(styles), styles=styles)
    if scope == "style":
        style_format = word_ops.get_style_format(pkg, target_id)
        return DocumentReadResult(block_count=1, style_format=style_format)
    if scope == "revisions":
        has_changes = word_ops.has_tracked_changes(pkg)
        revisions = (
            [RevisionInfo(**r) for r in word_ops.read_tracked_changes(pkg)]
            if has_changes
            else []
        )
        return DocumentReadResult(
            block_count=len(revisions),
            has_tracked_changes=has_changes,
            revisions=revisions,
        )
    if scope == "list":
        if not target_id:
            raise ValueError("target_id required for list scope")
        p_el = word_ops.find_paragraph_by_id(pkg, target_id)
        list_info_dict = word_ops.get_list_info(pkg, p_el)
        list_info = ListInfo(**list_info_dict) if list_info_dict else None
        return DocumentReadResult(
            block_count=1 if list_info else 0, list_info=list_info
        )
    if scope == "text_boxes":
        text_boxes_data = word_ops.build_text_boxes(pkg)
        text_boxes = [TextBoxInfo(**tb) for tb in text_boxes_data]
        return DocumentReadResult(block_count=len(text_boxes), text_boxes=text_boxes)
    if scope == "text_box_content":
        if not target_id:
            raise ValueError("target_id required for text_box_content scope")
        paragraphs = word_ops.read_text_box_content(pkg, target_id)
        blocks = [
            Block(id=p["id"], type="paragraph", text=p["text"], style="Normal")
            for p in paragraphs
        ]
        return DocumentReadResult(block_count=len(blocks), blocks=blocks)
    if scope == "bookmarks":
        bookmarks_data = word_ops.build_bookmarks(pkg)
        bookmarks = [BookmarkInfo(**bm) for bm in bookmarks_data]
        return DocumentReadResult(block_count=len(bookmarks), bookmarks=bookmarks)
    if scope == "captions":
        captions_data = word_ops.build_captions(pkg)
        captions = [CaptionInfo(**c) for c in captions_data]
        return DocumentReadResult(block_count=len(captions), captions=captions)
    if scope == "toc":
        toc_data = word_ops.get_toc_info(pkg)
        toc_info = TOCInfo(**toc_data)
        return DocumentReadResult(
            block_count=1 if toc_info.exists else 0, toc_info=toc_info
        )
    if scope == "footnotes":
        footnotes_data = word_ops.build_footnotes(pkg)
        footnotes = [FootnoteInfo(**fn) for fn in footnotes_data]
        return DocumentReadResult(block_count=len(footnotes), footnotes=footnotes)
    if scope == "content_controls":
        cc_data = word_ops.build_content_controls(pkg)
        controls = [ContentControlInfo(**cc) for cc in cc_data]
        return DocumentReadResult(block_count=len(controls), content_controls=controls)
    if scope == "equations":
        eq_data = word_ops.build_equations(pkg)
        equations = [EquationInfo(**eq) for eq in eq_data]
        return DocumentReadResult(block_count=len(equations), equations=equations)
    if scope == "bibliography":
        sources = word_ops.build_sources(pkg)
        bib_sources = [
            BibSourceInfo(
                tag=s["tag"],
                source_type=s["source_type"],
                title=s["title"],
                authors=[BibAuthor(**a) for a in s.get("authors", [])],
                year=s.get("year"),
                publisher=s.get("publisher"),
                city=s.get("city"),
                journal_name=s.get("journal_name"),
                volume=s.get("volume"),
                issue=s.get("issue"),
                pages=s.get("pages"),
                url=s.get("url"),
            )
            for s in sources
        ]
        return DocumentReadResult(
            block_count=len(bib_sources), bibliography_sources=bib_sources
        )
    raise ValueError(f"Unknown scope: {scope}")


def render(
    file_path: str,
    pages: list[int] | None = None,
    dpi: int = 150,
    output: str = "png",
) -> list[Any]:
    """Render Word document for visual inspection or sharing.

    Args:
        file_path: Path to .docx file.
        pages: Page numbers to render (1-based). Required for PNG output. Max 5 pages.
        dpi: Resolution for PNG (default 150, max 300).
        output: Output format: 'png' (images) or 'pdf' (full document).

    Returns:
        List of TextContent and Image objects.
    """
    if output == "pdf":
        pdf_bytes = word_ops.render_to_pdf(file_path)
        return [
            TextContent(type="text", text=f"PDF ({len(pdf_bytes):,} bytes)"),
            Image(data=pdf_bytes, format="pdf"),
        ]
    # PNG output (default)
    if not pages:
        raise ValueError("pages is required for PNG output")
    result = []
    for page_num, png_bytes in word_ops.render_to_images(file_path, pages, dpi):
        result.append(TextContent(type="text", text=f"Page {page_num}:"))
        result.append(Image(data=png_bytes, format="png"))
    return result


# Pattern for $prev[N] references
_PREV_REF_PATTERN = re.compile(r"^\$prev\[(\d+)\]$")


def edit(
    file_path: str,
    ops: str,
    mode: str = "atomic",
) -> EditResult:
    """Edit Word document with batch operations.

    Args:
        file_path: Path to .docx file.
        ops: JSON array of operation objects. Each object must have an "op" field.
            Use $prev[N] in target_id to reference element_id from operation N (0-indexed).
        mode: Batch mode: 'atomic' (all-or-nothing, file unchanged on any failure)
            or 'partial' (save successful ops before failure).

    Returns:
        EditResult with batch fields (total, succeeded, failed, results, saved).
    """
    # Import _apply_operation from tool.py to avoid code duplication
    from mcp_handley_lab.microsoft.word.tool import _apply_operation

    # Parse ops JSON
    try:
        operations = json.loads(ops)
    except json.JSONDecodeError as e:
        return EditResult(
            success=False,
            message="Invalid JSON in ops parameter",
            error=f"JSON parse error: {e}",
            total=0,
            succeeded=0,
            failed=0,
            results=[],
            saved=False,
        )

    if not isinstance(operations, list):
        return EditResult(
            success=False,
            message="ops must be a JSON array",
            error="Expected array, got " + type(operations).__name__,
            total=0,
            succeeded=0,
            failed=0,
            results=[],
            saved=False,
        )

    for i, op_obj in enumerate(operations):
        if not isinstance(op_obj, dict):
            return EditResult(
                success=False,
                message=f"ops[{i}] is not an object",
                error=f"Expected object at index {i}, got {type(op_obj).__name__}",
                total=0,
                succeeded=0,
                failed=0,
                results=[],
                saved=False,
            )

    if len(operations) == 0:
        return EditResult(
            success=True,
            message="No operations to execute",
            total=0,
            succeeded=0,
            failed=0,
            results=[],
            saved=False,
        )

    if len(operations) > 500:
        return EditResult(
            success=False,
            message=f"Too many operations: {len(operations)} (max 500)",
            error="Operation count exceeds limit of 500",
            total=len(operations),
            succeeded=0,
            failed=0,
            results=[],
            saved=False,
        )

    _EXCLUDED_FROM_BATCH = {"create"}
    for i, op_obj in enumerate(operations):
        if "op" not in op_obj:
            return EditResult(
                success=False,
                message=f"ops[{i}] missing 'op' field",
                error=f"Operation at index {i} has no 'op' field",
                total=len(operations),
                succeeded=0,
                failed=0,
                results=[],
                saved=False,
            )
        op_name = op_obj["op"]
        if op_name in _EXCLUDED_FROM_BATCH:
            return EditResult(
                success=False,
                message=f"ops[{i}]: '{op_name}' cannot be used in batch",
                error=f"Operation '{op_name}' is excluded from batch mode (use separately)",
                total=len(operations),
                succeeded=0,
                failed=0,
                results=[],
                saved=False,
            )

    try:
        pkg = WordPackage.open(file_path)
    except Exception as e:
        return EditResult(
            success=False,
            message="Failed to open document",
            error=str(e),
            total=len(operations),
            succeeded=0,
            failed=0,
            results=[],
            saved=False,
        )

    results: list[OpResult] = []
    element_ids: list[str] = []
    succeeded = 0
    failed = 0
    last_element_id = ""
    last_comment_id = None

    for i, op_obj in enumerate(operations):
        op_name = op_obj.get("op", "")

        target_id = op_obj.get("target_id", "")
        if target_id:
            match = _PREV_REF_PATTERN.match(target_id)
            if match:
                ref_idx = int(match.group(1))
                if ref_idx >= i:
                    result = OpResult(
                        index=i,
                        op=op_name,
                        success=False,
                        element_id="",
                        error=f"Invalid $prev reference: $prev[{ref_idx}] references index >= current ({i})",
                    )
                    results.append(result)
                    element_ids.append("")
                    failed += 1
                    break
                resolved_id = element_ids[ref_idx]
                if not resolved_id:
                    result = OpResult(
                        index=i,
                        op=op_name,
                        success=False,
                        element_id="",
                        error=f"Invalid $prev reference: $prev[{ref_idx}] has empty element_id",
                    )
                    results.append(result)
                    element_ids.append("")
                    failed += 1
                    break
                op_obj = dict(op_obj)
                op_obj["target_id"] = resolved_id

        try:
            op_result = _apply_operation(pkg, file_path, op_obj)
            op_result.index = i
            op_result.op = op_name
            results.append(op_result)
            element_ids.append(op_result.element_id)

            if op_result.success:
                succeeded += 1
                last_element_id = op_result.element_id
                if op_result.comment_id is not None:
                    last_comment_id = op_result.comment_id
            else:
                failed += 1
                break

        except Exception as e:
            result = OpResult(
                index=i,
                op=op_name,
                success=False,
                element_id="",
                error=str(e),
            )
            results.append(result)
            element_ids.append("")
            failed += 1
            break

    saved = False
    if mode == "atomic":
        if failed == 0 and succeeded > 0:
            try:
                pkg.save(file_path)
                saved = True
            except Exception as e:
                return EditResult(
                    success=False,
                    element_id=last_element_id,
                    comment_id=last_comment_id,
                    message="All operations succeeded but save failed",
                    error=f"Save failed: {e}",
                    total=len(operations),
                    succeeded=succeeded,
                    failed=1,
                    results=results,
                    saved=False,
                )
    else:
        if succeeded > 0:
            try:
                pkg.save(file_path)
                saved = True
            except Exception as e:
                return EditResult(
                    success=False,
                    element_id=last_element_id,
                    comment_id=last_comment_id,
                    message=f"{succeeded} ops succeeded but save failed",
                    error=f"Save failed: {e}",
                    total=len(operations),
                    succeeded=succeeded,
                    failed=failed,
                    results=results,
                    saved=False,
                )

    all_success = failed == 0 and succeeded == len(operations)
    if all_success:
        message = f"Completed {succeeded} operation(s)"
    elif succeeded > 0 and failed > 0:
        message = f"{succeeded} succeeded, {failed} failed"
    elif failed > 0:
        message = f"Failed at operation {len(results) - 1}"
    else:
        message = "No operations executed"

    return EditResult(
        success=all_success,
        element_id=last_element_id,
        comment_id=last_comment_id,
        message=message,
        total=len(operations),
        succeeded=succeeded,
        failed=failed,
        results=results,
        saved=saved,
    )


def create(
    file_path: str,
    content_type: str = "paragraph",
    content_data: str = "",
    style_name: str = "",
    heading_level: int = 1,
) -> EditResult:
    """Create a new Word document.

    Args:
        file_path: Path for the new .docx file.
        content_type: Type of initial content: 'paragraph', 'heading', 'table'.
        content_data: Initial content text or JSON.
        style_name: Word style name to apply.
        heading_level: Heading level 1-9 (for content_type='heading').

    Returns:
        EditResult with the new document's element_id.
    """
    from mcp_handley_lab.microsoft.word.constants import qn

    pkg = WordPackage.new()
    element_id = ""

    if content_type:
        body = pkg.body
        for p in list(body.findall(qn("w:p"))):
            body.remove(p)
        el = word_ops.append_content_ooxml(
            pkg, content_type, content_data, style_name, heading_level
        )
        level = heading_level if content_type == "heading" else 0
        element_id = word_ops.get_element_id_ooxml(pkg, el, level)
    else:
        el = pkg.body.find(qn("w:p"))
        element_id = word_ops.get_element_id_ooxml(pkg, el, 0)

    pkg.save(file_path)
    return EditResult(
        success=True,
        element_id=element_id,
        message=f"Created: {file_path}",
        total=1,
        succeeded=1,
        failed=0,
        results=[
            OpResult(
                index=0,
                op="create",
                success=True,
                element_id=element_id,
                message=f"Created: {file_path}",
            )
        ],
        saved=True,
    )
