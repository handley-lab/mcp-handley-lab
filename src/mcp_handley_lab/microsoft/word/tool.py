"""Word document MCP tool - read and edit operations."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.microsoft.word import document as word_ops

if TYPE_CHECKING:
    pass
from mcp_handley_lab.microsoft.word.models import (
    BookmarkInfo,
    CaptionInfo,
    CommentInfo,
    ContentControlInfo,
    DocumentReadResult,
    EditResult,
    EquationInfo,
    FootnoteInfo,
    ListInfo,
    RevisionInfo,
    TextBoxInfo,
    TOCInfo,
)
from mcp_handley_lab.microsoft.word.package import WordPackage

mcp = FastMCP("Word Document Tool")


# Helper dispatch dicts for header/footer operations
_HF_SET_OPS = {
    "set_header": "header",
    "set_footer": "footer",
    "set_first_page_header": "first_page_header",
    "set_first_page_footer": "first_page_footer",
    "set_even_page_header": "even_page_header",
    "set_even_page_footer": "even_page_footer",
}
_HF_APPEND_OPS = {"append_header": "header", "append_footer": "footer"}
_HF_CLEAR_OPS = {"clear_header": "header", "clear_footer": "footer"}


def _recalc_table_id(doc, t) -> str:
    """Recalculate table element ID after modification. Requires base_kind == 'table'."""
    if t.base_kind != "table":
        raise ValueError("Expected base_kind=table for table ID recalculation")
    tbl_el = t.base_el  # Use element, not wrapper
    content = word_ops.table_content_for_hash(tbl_el)
    occurrence = word_ops.count_occurrence(doc, "table", content, tbl_el)
    return word_ops.make_block_id("table", content, occurrence)


def _recalc_block_id(doc, t) -> str:
    """Recalculate block element ID after modification. Pure OOXML-based."""
    # Get block type from element (handles headings correctly)
    block_kind, _ = word_ops.paragraph_kind_and_level(t.leaf_el)
    # Get text from element directly (pure OOXML)
    text = word_ops.get_paragraph_text_ooxml(t.leaf_el)
    occurrence = word_ops.count_occurrence(doc, block_kind, text, t.leaf_el)
    return word_ops.make_block_id(block_kind, text, occurrence)


@mcp.tool(
    description="Read Word document content. Scopes: 'meta' (doc info), 'outline' (headings only), 'blocks' (all content), 'search' (find text), 'table_cells' (cells of a table), 'table_layout' (table alignment/autofit/row heights), 'runs' (text runs in a paragraph), 'comments' (all comments), 'headers_footers' (headers/footers per section), 'page_setup' (margins, orientation per section), 'images' (embedded inline images), 'hyperlinks' (all hyperlinks with URLs), 'styles' (all document styles), 'style' (detailed formatting for a specific style by name in target_id), 'revisions' (tracked changes/revisions), 'list' (list properties for a paragraph by target_id), 'text_boxes' (all text boxes/floating content), 'text_box_content' (paragraphs inside a text box by target_id), 'bookmarks' (all bookmarks), 'captions' (all captions), 'toc' (table of contents info), 'footnotes' (all footnotes and endnotes), 'content_controls' (all content controls/SDTs), 'equations' (math equations with simplified text), 'bibliography' (bibliography sources). Block IDs are content-addressed (type_hash_occurrence) and CHANGE when content changes or after inserts/deletes shift occurrence index - use element_id from edit response for chaining."
)
def read(
    file_path: str = Field(..., description="Path to .docx file"),
    scope: str = Field(
        "outline",
        description="What to read: 'meta', 'outline', 'blocks', 'search', 'table_cells', 'table_layout', 'runs', 'comments', 'headers_footers', 'page_setup', 'images', 'hyperlinks', 'styles', 'style', 'revisions', 'list', 'text_boxes', 'text_box_content', 'bookmarks', 'captions', 'toc', 'footnotes', 'content_controls', 'equations', 'bibliography'",
    ),
    target_id: str = Field(
        "",
        description="Block ID for table_cells/runs/table_layout/list scopes, style name for 'style' scope, or text box ID for 'text_box_content' scope",
    ),
    search_query: str = Field("", description="Text to search for (scope='search')"),
    limit: int = Field(50, description="Max blocks to return"),
    offset: int = Field(0, description="Pagination offset"),
) -> DocumentReadResult:
    """Read Word document content."""
    # Scopes that need WordPackage (pure OOXML)
    _PKG_SCOPES = {
        "meta",
        "outline",
        "blocks",
        "search",
        "table_cells",
        "table_layout",
        "revisions",
        "list",
        "bookmarks",
        "captions",
        "toc",
        "content_controls",
        "equations",
        "footnotes",
        "hyperlinks",
        "text_boxes",
        "text_box_content",
        "page_setup",
        "styles",
        "style",
        "runs",
        "comments",
        "headers_footers",
        "images",
        "bibliography",
    }
    # Scopes that need python-docx Document (for now)
    _DOC_SCOPES: set[str] = set()

    # Load appropriate object(s)
    pkg = (
        WordPackage.open(file_path) if scope in _PKG_SCOPES or scope == "meta" else None
    )

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
        from mcp_handley_lab.microsoft.word.constants import qn

        t = word_ops.resolve_target(pkg, target_id)
        tbl_el = t.base_el if t.base_kind == "table" else t.leaf_el
        cells = word_ops.build_table_cells(tbl_el, t.base_id)
        # Count rows/cols from element
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
        tbl_el = t.base_el if t.base_kind == "table" else t.leaf_el
        table_layout = word_ops.build_table_layout(tbl_el, t.base_id)
        return DocumentReadResult(block_count=1, table_layout=table_layout)
    if scope == "runs":
        # Pure OOXML path - find paragraph element, get doc rels for hyperlink URLs
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
        # Return paragraphs as blocks for consistency
        from mcp_handley_lab.microsoft.word.models import Block

        blocks = [
            Block(
                id=p["id"],
                type="paragraph",
                text=p["text"],
                style="Normal",
            )
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
        from mcp_handley_lab.microsoft.word.models import BibAuthor, BibSourceInfo

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


@mcp.tool(
    description="Edit Word document. Operations: 'create', 'insert_before', 'insert_after', 'append', 'delete', 'replace', 'style', 'edit_cell', 'edit_run', 'edit_style', 'add_comment', 'reply_comment', 'resolve_comment', 'unresolve_comment', 'set_header', 'set_footer', 'set_first_page_header', 'set_first_page_footer', 'set_even_page_header', 'set_even_page_footer', 'append_header', 'append_footer', 'clear_header', 'clear_footer', 'set_margins', 'set_orientation', 'set_columns', 'set_line_numbering', 'set_page_borders', 'set_custom_property', 'delete_custom_property', 'create_style', 'delete_style', 'insert_image', 'insert_floating_image', 'delete_image', 'add_row', 'add_column', 'delete_row', 'delete_column', 'add_page_break', 'add_break', 'set_meta', 'add_section', 'merge_cells', 'set_table_alignment', 'set_table_autofit', 'set_table_fixed_layout', 'set_row_height', 'set_cell_width', 'set_cell_vertical_alignment', 'set_cell_borders', 'set_cell_shading', 'set_header_row', 'add_tab_stop', 'clear_tab_stops', 'insert_field', 'insert_page_x_of_y', 'accept_change', 'reject_change', 'accept_all_changes', 'reject_all_changes', 'set_list_level', 'promote_list', 'demote_list', 'restart_numbering', 'remove_list', 'add_to_list', 'edit_text_box', 'add_bookmark', 'add_hyperlink', 'insert_cross_ref', 'insert_caption', 'insert_toc', 'update_toc', 'add_footnote', 'delete_footnote', 'set_content_control', 'add_source', 'delete_source', 'insert_citation', 'insert_bibliography'. Block IDs are content-addressed and CHANGE when content changes or after inserts/deletes shift occurrence index. Always use element_id from response for chaining operations on modified content. Note: 'create' makes a doc with an initial empty paragraph (python-docx behavior). 'update_toc' sets dirty flag; Word updates content on open. 'add_to_list' adds a new paragraph to an existing list; content_data: {\"text\": \"...\", \"position\": \"before|after\", \"level\": 0-8 (optional)}."
)
def edit(
    file_path: str = Field(..., description="Path to .docx file"),
    operation: str = Field(
        ...,
        description="Operation: 'create', 'insert_before', 'insert_after', 'append', 'delete', 'replace', 'style', 'edit_cell', 'edit_run', 'edit_style', 'create_style', 'delete_style', 'add_comment', 'reply_comment', 'resolve_comment', 'unresolve_comment', 'set_header', 'set_footer', 'set_first_page_header', 'set_first_page_footer', 'set_even_page_header', 'set_even_page_footer', 'append_header', 'append_footer', 'clear_header', 'clear_footer', 'set_margins', 'set_orientation', 'set_columns', 'set_line_numbering', 'set_page_borders', 'set_custom_property', 'delete_custom_property', 'insert_image', 'delete_image', 'add_row', 'add_column', 'delete_row', 'delete_column', 'add_page_break', 'add_break', 'set_meta', 'add_section', 'merge_cells', 'set_table_alignment', 'set_table_autofit', 'set_table_fixed_layout', 'set_row_height', 'set_cell_width', 'set_cell_vertical_alignment', 'set_cell_borders', 'set_cell_shading', 'set_header_row', 'add_tab_stop', 'clear_tab_stops', 'insert_field', 'insert_page_x_of_y', 'accept_change', 'reject_change', 'accept_all_changes', 'reject_all_changes', 'set_list_level', 'promote_list', 'demote_list', 'restart_numbering', 'remove_list', 'add_to_list', 'edit_text_box', 'add_bookmark', 'add_hyperlink', 'insert_cross_ref', 'insert_caption', 'insert_toc', 'update_toc', 'add_footnote', 'delete_footnote', 'set_content_control', 'add_source', 'delete_source', 'insert_citation', 'insert_bibliography'",
    ),
    target_id: str = Field(
        "",
        description="Block ID from read() - required for insert/delete/replace/style/edit_cell/edit_run/add_comment/insert_image/list operations and table operations. For edit_style: style name. For delete_style: style name to delete. For delete_image: the image ID. For accept_change/reject_change: the revision ID from read(scope='revisions'). For edit_text_box: the text box ID from read(scope='text_boxes'). For add_bookmark/add_hyperlink/insert_cross_ref/insert_caption/insert_toc: the paragraph or block ID (or table cell ID). For reply_comment/resolve_comment/unresolve_comment: the comment ID. For add_footnote: the paragraph ID. For delete_footnote: the footnote ID (from read(scope='footnotes')). For set_content_control: the content control ID (from read(scope='content_controls')).",
    ),
    content_type: str = Field(
        "paragraph",
        description="Type: 'paragraph', 'heading', 'table'",
    ),
    content_data: str = Field(
        "",
        description="Content: text or JSON. For set_table_alignment: 'left'/'center'/'right'. For set_table_autofit: 'true'/'false'. For set_table_fixed_layout: JSON array of widths. For set_row_height: JSON {height, rule} where rule is 'auto', 'at_least', or 'exactly'. For set_cell_width: width in inches. For set_cell_vertical_alignment: 'top'/'center'/'bottom'. For set_cell_borders: JSON {top?, bottom?, left?, right?} with values as 'style:size:color' (e.g., 'single:24:000000'). For set_cell_shading: hex color (e.g., 'FF0000'). For set_header_row: 'true'/'false' (mark row as header). For set_columns: JSON {num_columns, spacing_inches?, separator?}. For set_line_numbering: JSON {enabled?, restart?, start?, count_by?, distance_inches?}. For set_custom_property: JSON {name, value, type?} where type is 'string'/'int'/'bool'/'datetime'/'float' (default 'string'). For delete_custom_property: property name. For create_style: JSON {name, style_type?, base_style?} where style_type is 'paragraph'/'character'/'table' (default 'paragraph'), base_style is style to inherit from (default 'Normal'). For add_tab_stop: JSON {position, alignment, leader} where alignment is 'left'/'center'/'right'/'decimal' and leader is 'spaces'/'dots'/'heavy'/'middle_dot'. For insert_field: field code (PAGE, NUMPAGES, DATE, TIME). For insert_page_x_of_y: 'header' or 'footer'. For set_list_level: level 0-8. For restart_numbering: start value (default 1). For insert_toc: JSON {position: 'before'/'after', heading_levels: '1-3'}. For add_footnote: JSON {text, note_type?, position?} where note_type is 'footnote'/'endnote' (default 'footnote'), position is 'after'/'before' (default 'after'). For delete_footnote: JSON {note_type?} where note_type is 'footnote'/'endnote' (default 'footnote'). For set_content_control: the new value - for dropdown must match one of the options, for checkbox use 'true'/'false', for date use ISO format. For add_hyperlink: JSON {text, address?, fragment?} where text is visible link text, address is URL (external link), fragment is bookmark name (internal link) or URL anchor.",
    ),
    style_name: str = Field(
        "", description="Apply Word style: 'Heading 1', 'Normal', etc."
    ),
    formatting: str = Field(
        "",
        description='Direct formatting JSON. Text/Run: {"bold": true, "color": "FF0000", "font_size": 14, "highlight_color": "yellow", "strike": true, "subscript": true, "superscript": true, "style": "Strong"}. Character styles: "Strong", "Emphasis", "Hyperlink", etc. Paragraph: {"left_indent": 0.5, "right_indent": 0.5, "first_line_indent": 0.5, "space_before": 12, "space_after": 12, "line_spacing": 1.5, "keep_with_next": true, "page_break_before": true} (indents in inches, spacing in points, line_spacing < 5 is multiplier). Margins: {"top": 1.0, "bottom": 1.0, "left": 1.25, "right": 1.25} in inches. Images: {"width": 4} or {"height": 3} in inches. Page borders: {"top": "style:size:space:color", ...} where style is border style (single, double, dotted, etc.), size is eighths of a point (4=0.5pt), space is points from text, color is hex RRGGBB or "auto". Optional offset_from: "text" or "page".',
    ),
    heading_level: int = Field(
        1, description="Heading level 1-9 (only for content_type='heading')"
    ),
    row: int = Field(0, description="Row number (0-based, for edit_cell operation)"),
    col: int = Field(0, description="Column number (0-based, for edit_cell operation)"),
    run_index: int = Field(
        -1,
        description="Run index (0-based, for edit_run operation). Use read() with scope='runs' to find indices.",
    ),
    author: str = Field("", description="Comment author name (for add_comment)"),
    initials: str = Field("", description="Comment author initials (for add_comment)"),
    section_index: int = Field(
        0,
        description="Section index (0-based, for set_header/set_footer/set_margins/set_orientation). Use read() with scope='page_setup' to see sections.",
    ),
) -> EditResult:
    """Edit Word document."""
    # WordPackage-based operations (pure OOXML, no python-docx)
    _PKG_OPERATIONS = {
        "edit_style",
        "delete",
        "replace",
        "edit_cell",
        # Content creation/insertion operations
        "create",
        "insert_before",
        "insert_after",
        "append",
        # Table structure operations
        "add_row",
        "add_column",
        "delete_row",
        "delete_column",
        "merge_cells",
        # Table formatting operations
        "set_table_alignment",
        "set_table_autofit",
        "set_table_fixed_layout",
        "set_row_height",
        "set_cell_width",
        "set_cell_vertical_alignment",
        "set_cell_borders",
        "set_cell_shading",
        "set_header_row",
        # Break operations
        "add_page_break",
        "add_break",
        # Revision operations
        "accept_change",
        "reject_change",
        "accept_all_changes",
        "reject_all_changes",
        # List operations
        "set_list_level",
        "promote_list",
        "demote_list",
        "restart_numbering",
        "remove_list",
        "add_to_list",
        # Properties operations (duck-typed)
        "set_custom_property",
        "delete_custom_property",
        "set_meta",
        # Run editing operations (duck-typed)
        "edit_run",
        # Style/formatting operations (duck-typed)
        "style",
        # Text box and content control operations (duck-typed)
        "edit_text_box",
        "set_content_control",
        # Section operations (duck-typed)
        "set_margins",
        "set_orientation",
        "set_columns",
        "set_line_numbering",
        "set_page_borders",
        # Bookmark and cross-reference operations (duck-typed)
        "add_bookmark",
        "insert_cross_ref",
        # Caption and TOC operations (duck-typed)
        "insert_caption",
        "insert_toc",
        "update_toc",
        # Footnote operations (file-based, already pure OOXML)
        "add_footnote",
        "delete_footnote",
        # Section structure operations (duck-typed)
        "add_section",
        # Comment operations (pure OOXML)
        "add_comment",
        "reply_comment",
        "resolve_comment",
        "unresolve_comment",
        # Hyperlink operations (pure OOXML)
        "add_hyperlink",
        # Header/footer operations (duck-typed)
        "set_header",
        "set_footer",
        "set_first_page_header",
        "set_first_page_footer",
        "set_even_page_header",
        "set_even_page_footer",
        "append_header",
        "append_footer",
        "clear_header",
        "clear_footer",
        "insert_page_x_of_y",
        # Style operations (duck-typed)
        "create_style",
        "delete_style",
        # Image operations (duck-typed)
        "insert_image",
        "delete_image",
        "insert_floating_image",
        # Tab stop operations (duck-typed)
        "add_tab_stop",
        "clear_tab_stops",
        # Field operations (pure OOXML)
        "insert_field",
        # Bibliography operations (pure OOXML)
        "add_source",
        "delete_source",
        "insert_citation",
        "insert_bibliography",
    }
    if operation in _PKG_OPERATIONS:
        # Create uses WordPackage.new(), others use WordPackage.open()
        if operation == "create":
            pkg = WordPackage.new()
        else:
            pkg = WordPackage.open(file_path)
        element_id = target_id
        message = f"Completed {operation}"

        if operation == "create":
            from mcp_handley_lab.microsoft.word.constants import qn

            # Create new document - if content_type provided, replace default paragraph
            if content_type:
                # Replace the empty placeholder paragraph with actual content
                body = pkg.body
                # Find and remove the empty placeholder paragraph
                for p in list(body.findall(qn("w:p"))):
                    body.remove(p)
                el = word_ops.append_content_ooxml(
                    pkg, content_type, content_data, style_name, heading_level
                )
                level = heading_level if content_type == "heading" else 0
                element_id = word_ops.get_element_id_ooxml(pkg, el, level)
            else:
                # Empty document - use the default empty paragraph
                el = pkg.body.find(qn("w:p"))
                element_id = word_ops.get_element_id_ooxml(pkg, el, 0)
            pkg.save(file_path)
            return EditResult(
                success=True, element_id=element_id, message=f"Created: {file_path}"
            )

        elif operation in ("insert_before", "insert_after"):
            t = word_ops.resolve_target(pkg, target_id)
            position = "before" if operation == "insert_before" else "after"
            el = word_ops.insert_content_ooxml(
                pkg,
                t.leaf_el,
                position,
                content_type,
                content_data,
                style_name,
                heading_level,
            )
            level = heading_level if content_type == "heading" else 0
            element_id = word_ops.get_element_id_ooxml(pkg, el, level)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Inserted {content_type} {position} {target_id}"

        elif operation == "append":
            el = word_ops.append_content_ooxml(
                pkg, content_type, content_data, style_name, heading_level
            )
            level = heading_level if content_type == "heading" else 0
            element_id = word_ops.get_element_id_ooxml(pkg, el, level)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Appended {content_type} to document"

        elif operation == "edit_style":
            fmt = json.loads(formatting)
            word_ops.edit_style(pkg, target_id, fmt)
            message = f"Modified style: {target_id}"

        elif operation == "delete":
            t = word_ops.resolve_target(pkg, target_id)
            t.base_el.getparent().remove(t.base_el)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Deleted block {target_id}"

        elif operation == "replace":
            t = word_ops.resolve_target(pkg, target_id)
            if t.leaf_kind.startswith("heading") or t.leaf_kind == "paragraph":
                word_ops.set_paragraph_text_ooxml(t.leaf_el, content_data)
                element_id = _recalc_block_id(pkg, t)
            elif t.leaf_kind == "table":
                table_data = json.loads(content_data)
                new_tbl_el = word_ops.replace_table(t.leaf_el, table_data)
                table_content = word_ops.table_content_for_hash(new_tbl_el)
                occurrence = word_ops.count_occurrence(
                    pkg, "table", table_content, new_tbl_el
                )
                element_id = word_ops.make_block_id("table", table_content, occurrence)
            else:
                raise ValueError(f"Unsupported leaf_kind: {t.leaf_kind}")
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Replaced content of {target_id}"

        elif operation == "edit_cell":
            t = word_ops.resolve_target(pkg, target_id)
            word_ops.replace_table_cell(t.base_el, row, col, content_data)
            pkg.mark_xml_dirty("/word/document.xml")
            element_id = _recalc_table_id(pkg, t)
            message = f"Updated cell r{row}c{col}"

        elif operation == "add_row":
            t = word_ops.resolve_target(pkg, target_id)
            data = json.loads(content_data) if content_data else None
            row_idx = word_ops.add_table_row(t.base_el, data)
            pkg.mark_xml_dirty("/word/document.xml")
            element_id = _recalc_table_id(pkg, t)
            message = f"Added row {row_idx}"

        elif operation == "add_column":
            t = word_ops.resolve_target(pkg, target_id)
            fmt = json.loads(formatting) if formatting else {}
            width_inches = float(fmt.get("width", 1.0))
            width_twips = int(width_inches * 1440)  # 1440 twips per inch
            data = json.loads(content_data) if content_data else None
            col_idx = word_ops.add_table_column(t.base_el, width_twips, data)
            pkg.mark_xml_dirty("/word/document.xml")
            element_id = _recalc_table_id(pkg, t)
            message = f"Added column {col_idx}"

        elif operation == "delete_row":
            t = word_ops.resolve_target(pkg, target_id)
            word_ops.delete_table_row(t.base_el, row)
            pkg.mark_xml_dirty("/word/document.xml")
            element_id = _recalc_table_id(pkg, t)
            message = f"Deleted row {row}"

        elif operation == "delete_column":
            t = word_ops.resolve_target(pkg, target_id)
            word_ops.delete_table_column(t.base_el, col)
            pkg.mark_xml_dirty("/word/document.xml")
            element_id = _recalc_table_id(pkg, t)
            message = f"Deleted column {col}"

        elif operation == "merge_cells":
            t = word_ops.resolve_target(pkg, target_id)
            if not content_data:
                raise ValueError(
                    "merge_cells requires content_data JSON with end_row, end_col"
                )
            try:
                merge_data = json.loads(content_data)
            except json.JSONDecodeError:
                raise ValueError(
                    "merge_cells content_data must be valid JSON with end_row, end_col"
                )
            start_row = merge_data.get("start_row", merge_data.get("row", row))
            start_col = merge_data.get("start_col", merge_data.get("col", col))
            end_row = merge_data.get("end_row")
            end_col = merge_data.get("end_col")
            if end_row is None or end_col is None:
                raise ValueError(
                    "merge_cells requires end_row and end_col in content_data"
                )
            word_ops.merge_cells(t.base_el, start_row, start_col, end_row, end_col)
            pkg.mark_xml_dirty("/word/document.xml")
            message = (
                f"Merged cells from ({start_row},{start_col}) to ({end_row},{end_col})"
            )

        elif operation == "set_table_alignment":
            t = word_ops.resolve_target(pkg, target_id)
            word_ops.set_table_alignment(t.base_el, content_data)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Set table alignment to {content_data}"

        elif operation == "set_table_autofit":
            t = word_ops.resolve_target(pkg, target_id)
            autofit_value = json.loads(content_data.lower())
            word_ops.set_table_autofit(t.base_el, autofit_value)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Set table autofit to {autofit_value}"

        elif operation == "set_table_fixed_layout":
            t = word_ops.resolve_target(pkg, target_id)
            widths = json.loads(content_data)
            word_ops.set_table_fixed_layout(t.base_el, widths)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Set table fixed layout with {len(widths)} columns"

        elif operation == "set_row_height":
            t = word_ops.resolve_target(pkg, target_id)
            height_data = json.loads(content_data)
            word_ops.set_row_height(
                t.base_el,
                row,
                height_data["height"],
                height_data.get("rule", "at_least"),
            )
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Set row {row} height to {height_data['height']} inches"

        elif operation == "set_cell_width":
            t = word_ops.resolve_target(pkg, target_id)
            word_ops.set_cell_width(t.base_el, row, col, float(content_data))
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Set cell ({row},{col}) width to {content_data} inches"

        elif operation == "set_cell_vertical_alignment":
            t = word_ops.resolve_target(pkg, target_id)
            word_ops.set_cell_vertical_alignment(t.base_el, row, col, content_data)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Set cell ({row},{col}) vertical alignment to {content_data}"

        elif operation == "set_cell_borders":
            t = word_ops.resolve_target(pkg, target_id)
            border_data = json.loads(content_data)
            word_ops.set_cell_borders(
                t.base_el,
                row,
                col,
                top=border_data.get("top"),
                bottom=border_data.get("bottom"),
                left=border_data.get("left"),
                right=border_data.get("right"),
            )
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Set borders on cell ({row},{col})"

        elif operation == "set_cell_shading":
            t = word_ops.resolve_target(pkg, target_id)
            word_ops.set_cell_shading(t.base_el, row, col, content_data)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Set shading on cell ({row},{col}) to {content_data}"

        elif operation == "set_header_row":
            t = word_ops.resolve_target(pkg, target_id)
            is_header = content_data.lower() in ("true", "1", "yes")
            word_ops.set_header_row(t.base_el, row, is_header)
            pkg.mark_xml_dirty("/word/document.xml")
            action = "marked as" if is_header else "unmarked as"
            message = f"Row {row} {action} header row"

        elif operation == "add_page_break":
            body = pkg.body
            p_el = word_ops.add_page_break_ooxml(body)
            pkg.mark_xml_dirty("/word/document.xml")
            text = word_ops.get_paragraph_text_ooxml(p_el)
            occurrence = word_ops.count_occurrence(pkg, "paragraph", text, p_el)
            element_id = word_ops.make_block_id("paragraph", text, occurrence)
            message = "Added page break"

        elif operation == "add_break":
            t = word_ops.resolve_target(pkg, target_id)
            break_type = content_data or "page"
            p_el = word_ops.add_break_after_ooxml(t.leaf_el, break_type)
            pkg.mark_xml_dirty("/word/document.xml")
            text = word_ops.get_paragraph_text_ooxml(p_el)
            occurrence = word_ops.count_occurrence(pkg, "paragraph", text, p_el)
            element_id = word_ops.make_block_id("paragraph", text, occurrence)
            message = f"Added {break_type} break after {target_id}"

        elif operation == "accept_change":
            word_ops.accept_change(pkg, target_id)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Accepted change {target_id}"

        elif operation == "reject_change":
            word_ops.reject_change(pkg, target_id)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Rejected change {target_id}"

        elif operation == "accept_all_changes":
            count = word_ops.accept_all_changes(pkg)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Accepted {count} changes"

        elif operation == "reject_all_changes":
            count = word_ops.reject_all_changes(pkg)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Rejected {count} changes"

        elif operation == "set_list_level":
            p_el = word_ops.find_paragraph_by_id(pkg, target_id)
            level = int(content_data) if content_data else 0
            if level < 0 or level > 8:
                raise ValueError("List level must be 0-8")
            word_ops.set_list_level(pkg, p_el, level)
            message = f"Set list level to {level}"

        elif operation == "promote_list":
            p_el = word_ops.find_paragraph_by_id(pkg, target_id)
            word_ops.promote_list_item(pkg, p_el)
            message = "Promoted list item"

        elif operation == "demote_list":
            p_el = word_ops.find_paragraph_by_id(pkg, target_id)
            word_ops.demote_list_item(pkg, p_el)
            message = "Demoted list item"

        elif operation == "restart_numbering":
            p_el = word_ops.find_paragraph_by_id(pkg, target_id)
            start_value = int(content_data) if content_data else 1
            word_ops.restart_numbering(pkg, p_el, start_value)
            message = f"Restarted numbering at {start_value}"

        elif operation == "remove_list":
            p_el = word_ops.find_paragraph_by_id(pkg, target_id)
            word_ops.remove_list_formatting(pkg, p_el)
            message = "Removed list formatting"

        elif operation == "add_to_list":
            t = word_ops.resolve_target(pkg, target_id)
            if t.base_kind not in (
                "paragraph",
                "heading1",
                "heading2",
                "heading3",
                "heading4",
                "heading5",
                "heading6",
                "heading7",
                "heading8",
                "heading9",
            ):
                raise ValueError("add_to_list requires a paragraph target")
            data = json.loads(content_data) if content_data else {}
            text = data.get("text", "")
            position = data.get("position", "after")
            level = data.get("level")  # None = inherit
            new_p = word_ops.add_to_list(pkg, t.leaf_el, text, position, level)
            # Compute block ID using get_element_id_ooxml - same function used by read()
            new_id = word_ops.get_element_id_ooxml(pkg, new_p)
            element_id = new_id
            message = f"Added list item {position} target"

        elif operation == "set_custom_property":
            prop_data = json.loads(content_data)
            word_ops.set_custom_property(
                pkg,
                name=prop_data["name"],
                value=prop_data["value"],
                prop_type=prop_data.get("type", "string"),
            )
            message = f"Set custom property '{prop_data['name']}'"

        elif operation == "delete_custom_property":
            prop_name = content_data
            deleted = word_ops.delete_custom_property(pkg, prop_name)
            if deleted:
                message = f"Deleted custom property '{prop_name}'"
            else:
                message = f"Custom property '{prop_name}' not found"

        elif operation == "set_meta":
            meta_data = json.loads(content_data) if content_data else {}
            word_ops.set_document_meta(
                pkg,
                title=meta_data.get("title"),
                author=meta_data.get("author"),
                subject=meta_data.get("subject"),
                keywords=meta_data.get("keywords"),
                category=meta_data.get("category"),
            )
            message = "Updated document metadata"

        elif operation == "edit_run":
            t = word_ops.resolve_target(pkg, target_id)
            # Ensure target is a paragraph, not a table
            if t.leaf_kind not in (
                "paragraph",
                "heading1",
                "heading2",
                "heading3",
                "heading4",
                "heading5",
                "heading6",
                "heading7",
                "heading8",
                "heading9",
            ):
                from mcp_handley_lab.microsoft.word.constants import qn

                if t.leaf_el.tag != qn("w:p"):
                    raise ValueError(
                        f"edit_run requires a paragraph target, got {t.leaf_kind}"
                    )
            if content_data:
                word_ops.edit_run_text(t.leaf_el, run_index, content_data)
            if formatting:
                fmt = json.loads(formatting)
                word_ops.edit_run_formatting(t.leaf_el, run_index, fmt)
            element_id = word_ops.get_element_id_ooxml(pkg, t.leaf_el, 0)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Updated run {run_index}"

        elif operation == "style":
            t = word_ops.resolve_target(pkg, target_id)
            if style_name:
                word_ops.set_paragraph_style_ooxml(t.leaf_el, style_name)
            if t.base_kind == "table":
                # Table formatting handled separately
                element_id = target_id
            else:
                if formatting:
                    fmt = json.loads(formatting)
                    word_ops.apply_paragraph_formatting(t.leaf_el, fmt)
                element_id = word_ops.get_element_id_ooxml(pkg, t.leaf_el, 0)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Applied style to {target_id}"

        elif operation == "edit_text_box":
            if not target_id:
                raise ValueError("target_id (text box ID) required for edit_text_box")
            word_ops.edit_text_box_text(pkg, target_id, row, content_data)
            message = f"Edited text box {target_id} paragraph {row}"

        elif operation == "set_content_control":
            if not target_id:
                raise ValueError(
                    "target_id (content control ID) required for set_content_control"
                )
            if not content_data:
                raise ValueError(
                    "content_data (new value) required for set_content_control"
                )
            sdt_id = int(target_id)
            word_ops.set_content_control_value(pkg, sdt_id, content_data)
            message = f"Set content control {sdt_id} to '{content_data}'"

        elif operation == "set_margins":
            margins = json.loads(formatting)
            word_ops.set_page_margins(
                pkg,
                section_index,
                top=margins.get("top"),
                bottom=margins.get("bottom"),
                left=margins.get("left"),
                right=margins.get("right"),
            )
            message = f"Set margins for section {section_index}"

        elif operation == "set_orientation":
            word_ops.set_page_orientation(pkg, section_index, content_data)
            message = f"Set orientation to {content_data} for section {section_index}"

        elif operation == "set_columns":
            col_data = json.loads(content_data)
            word_ops.set_section_columns(
                pkg,
                section_index,
                int(col_data["num_columns"]),
                float(col_data.get("spacing_inches", 0.5)),
                col_data.get("separator", False),
            )
            message = (
                f"Set {col_data['num_columns']} columns for section {section_index}"
            )

        elif operation == "set_line_numbering":
            ln_data = json.loads(content_data)
            word_ops.set_line_numbering(
                pkg,
                section_index,
                enabled=ln_data.get("enabled", True),
                restart=ln_data.get("restart", "newPage"),
                start=int(ln_data.get("start", 1)),
                count_by=int(ln_data.get("count_by", 1)),
                distance_inches=float(ln_data.get("distance_inches", 0.5)),
            )
            enabled = ln_data.get("enabled", True)
            action = "Enabled" if enabled else "Disabled"
            message = f"{action} line numbering for section {section_index}"

        elif operation == "set_page_borders":
            fmt = json.loads(formatting) if formatting else {}
            word_ops.set_page_borders(
                pkg,
                section_index,
                top=fmt.get("top"),
                bottom=fmt.get("bottom"),
                left=fmt.get("left"),
                right=fmt.get("right"),
                offset_from=fmt.get("offset_from", "text"),
            )
            sides = [s for s in ["top", "bottom", "left", "right"] if fmt.get(s)]
            message = f"Set page borders ({', '.join(sides) or 'none'}) for section {section_index}"

        elif operation == "add_bookmark":
            # target_id is the paragraph/heading ID, content_data is the bookmark name
            if not target_id:
                raise ValueError("target_id (paragraph ID) required for add_bookmark")
            if not content_data:
                raise ValueError(
                    "content_data (bookmark name) required for add_bookmark"
                )
            target = word_ops.resolve_target(pkg, target_id)
            # WordPackage uses leaf_el (lxml element)
            bm_id = word_ops.add_bookmark(pkg, content_data, target.leaf_el)
            message = f"Added bookmark '{content_data}' with ID {bm_id}"

        elif operation == "insert_cross_ref":
            # target_id is the paragraph/heading ID, content_data is bookmark name
            if not target_id:
                raise ValueError(
                    "target_id (paragraph ID) required for insert_cross_ref"
                )
            if not content_data:
                raise ValueError(
                    "content_data (bookmark name) required for insert_cross_ref"
                )
            target = word_ops.resolve_target(pkg, target_id)
            ref_type = style_name if style_name else "text"
            word_ops.insert_cross_reference(target.leaf_el, content_data, ref_type)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Inserted cross-reference to '{content_data}' ({ref_type})"

        elif operation == "insert_caption":
            # target_id is the block to caption
            if not target_id:
                raise ValueError("target_id (block ID) required for insert_caption")
            # Accept plain string OR JSON dict
            if content_data and content_data.strip().startswith("{"):
                # Looks like JSON - parse strictly
                caption_data = json.loads(content_data)
                if not isinstance(caption_data, dict):
                    raise ValueError("content_data must be a JSON object or plain text")
                label = caption_data.get("label", "Figure")
                caption_text = caption_data.get("text", "")
                position = caption_data.get("position", "below")
            else:
                # Plain string caption text
                label = "Figure"
                caption_text = content_data if content_data else ""
                position = "below"
            if position not in ("above", "below"):
                raise ValueError(
                    f"Invalid position '{position}'. Valid: ['above', 'below']"
                )
            element_id = word_ops.insert_caption(
                pkg, target_id, label, caption_text, position
            )
            message = f"Inserted {label} caption {position} {target_id}"

        elif operation == "insert_toc":
            # target_id is the block to insert before/after
            if not target_id:
                raise ValueError("target_id (block ID) required for insert_toc")
            toc_data = json.loads(content_data) if content_data else {}
            position = toc_data.get("position", "before")
            heading_levels = toc_data.get("heading_levels", "1-3")
            element_id = word_ops.insert_toc(pkg, target_id, position, heading_levels)
            message = f"Inserted TOC {position} {target_id}"

        elif operation == "update_toc":
            word_ops.update_toc_field(pkg)
            message = "Set TOC dirty flag for update on open"

        elif operation == "add_footnote":
            # Save first since footnotes use direct file manipulation
            pkg.save(file_path)
            if not target_id:
                raise ValueError("target_id (paragraph ID) required for add_footnote")
            if not content_data:
                raise ValueError(
                    "content_data (JSON with text) required for add_footnote"
                )
            fn_data = json.loads(content_data)
            fn_text = fn_data.get("text", "")
            note_type = fn_data.get("note_type", "footnote")
            position = fn_data.get("position", "after")
            fn_id = word_ops.add_footnote(
                file_path, target_id, fn_text, note_type, position
            )
            message = f"Added {note_type} {fn_id}"
            # Already saved, return early
            return EditResult(success=True, element_id=element_id, message=message)

        elif operation == "delete_footnote":
            # Save first since footnotes use direct file manipulation
            pkg.save(file_path)
            if not target_id:
                raise ValueError("target_id (note ID) required for delete_footnote")
            note_id = int(target_id)
            note_type = content_data.strip() if content_data else "footnote"
            word_ops.delete_footnote(file_path, note_id, note_type)
            message = f"Deleted {note_type} {note_id}"
            # Already saved, return early
            return EditResult(success=True, element_id=element_id, message=message)

        elif operation == "add_section":
            start_type = content_data.strip().lower() if content_data else "new_page"
            new_idx = word_ops.add_section(pkg, start_type)
            message = f"Added section {new_idx} ({start_type})"

        elif operation == "add_comment":
            if not target_id:
                raise ValueError("target_id (paragraph ID) required for add_comment")
            target = word_ops.resolve_target(pkg, target_id)
            # Comments can only be added to paragraphs, not tables
            from mcp_handley_lab.microsoft.word.constants import qn as _qn

            if target.leaf_el.tag != _qn("w:p"):
                raise ValueError(
                    f"Cannot add comment to {target.leaf_kind}. "
                    "Comments can only be added to paragraphs."
                )
            new_comment_id = word_ops.add_comment_to_block(
                pkg, target.leaf_el, content_data, author, initials
            )
            pkg.save(file_path)
            message = f"Added comment {new_comment_id} to {target_id}"
            return EditResult(
                success=True,
                element_id=element_id,
                message=message,
                comment_id=new_comment_id,
            )

        elif operation == "reply_comment":
            parent_id = int(target_id)
            new_comment_id = word_ops.reply_to_comment(
                pkg, parent_id, content_data, author, initials
            )
            pkg.save(file_path)
            message = f"Added reply {new_comment_id} to comment {parent_id}"
            return EditResult(
                success=True,
                element_id=element_id,
                message=message,
                comment_id=new_comment_id,
            )

        elif operation == "resolve_comment":
            cid = int(target_id)
            word_ops.resolve_comment(pkg, cid)
            message = f"Resolved comment {cid}"

        elif operation == "unresolve_comment":
            cid = int(target_id)
            word_ops.unresolve_comment(pkg, cid)
            message = f"Unresolved comment {cid}"

        elif operation == "add_hyperlink":
            if not target_id:
                raise ValueError("target_id required for add_hyperlink")
            if not content_data:
                raise ValueError(
                    "content_data (JSON with text, address/fragment) required"
                )
            try:
                link_data = json.loads(content_data)
            except json.JSONDecodeError:
                raise ValueError(
                    "content_data must be valid JSON: {text, address?, fragment?}"
                )
            text = link_data.get("text", "")
            address = link_data.get("address", "")
            fragment = link_data.get("fragment", "")
            target = word_ops.resolve_target(pkg, target_id)
            from mcp_handley_lab.microsoft.word.constants import qn as _qn

            # Get target paragraph - for cells, use first paragraph inside cell
            if target.leaf_kind == "cell":
                p_el = target.leaf_el.find(_qn("w:p"))
                if p_el is None:
                    raise ValueError("Cell has no paragraph to add hyperlink to")
            elif target.leaf_el.tag == _qn("w:p"):
                p_el = target.leaf_el
            else:
                raise ValueError(
                    f"Cannot add hyperlink to {target.leaf_kind}. "
                    "Hyperlinks can only be added to paragraphs or table cells."
                )
            word_ops.add_hyperlink(pkg, p_el, text, address, fragment)
            # Return table ID for cells, paragraph ID otherwise
            if target.leaf_kind == "cell":
                element_id = word_ops.get_element_id_ooxml(pkg, target.base_el)
            else:
                element_id = word_ops.get_element_id_ooxml(pkg, p_el)
            message = f"Added hyperlink '{text}' to {address or '#' + fragment}"

        elif operation in _HF_SET_OPS:
            location = _HF_SET_OPS[operation]
            word_ops.set_header_footer_text(pkg, section_index, content_data, location)
            message = f"Set {location.replace('_', ' ')} for section {section_index}"

        elif operation in _HF_APPEND_OPS:
            location = _HF_APPEND_OPS[operation]
            element_id = word_ops.append_to_header_footer(
                pkg, section_index, content_type, content_data, location
            )
            message = (
                f"Appended {content_type} to {location} for section {section_index}"
            )

        elif operation in _HF_CLEAR_OPS:
            location = _HF_CLEAR_OPS[operation]
            word_ops.clear_header_footer(pkg, section_index, location)
            message = f"Cleared {location} for section {section_index}"

        elif operation == "insert_page_x_of_y":
            location = content_data.strip().lower() or "footer"
            word_ops.insert_page_x_of_y(pkg, section_index, location)
            message = f"Inserted 'Page X of Y' in {location} of section {section_index}"

        elif operation == "create_style":
            style_data = json.loads(content_data)
            formatting_dict = json.loads(formatting) if formatting else None
            style_id = word_ops.create_style(
                pkg,
                name=style_data["name"],
                style_type=style_data.get("style_type", "paragraph"),
                base_style=style_data.get("base_style", "Normal"),
                formatting=formatting_dict,
            )
            element_id = style_id
            message = f"Created style '{style_data['name']}'"

        elif operation == "delete_style":
            deleted = word_ops.delete_style(pkg, target_id)
            if deleted:
                message = f"Deleted style '{target_id}'"
            else:
                message = f"Style '{target_id}' not found or is builtin"

        elif operation == "insert_image":
            fmt = json.loads(formatting) if formatting else {}
            element_id = word_ops.insert_image(
                pkg,
                content_data,
                target_id,
                "after",
                width_inches=float(fmt.get("width", 0)),
                height_inches=float(fmt.get("height", 0)),
            )
            message = "Inserted image"

        elif operation == "delete_image":
            word_ops.delete_image(pkg, target_id)
            message = f"Deleted {target_id}"

        elif operation == "insert_floating_image":
            fmt = json.loads(formatting) if formatting else {}
            element_id = word_ops.insert_floating_image(
                pkg,
                content_data,
                target_id,
                position_h=float(fmt.get("position_h", 0)),
                position_v=float(fmt.get("position_v", 0)),
                relative_h=fmt.get("relative_h", "column"),
                relative_v=fmt.get("relative_v", "paragraph"),
                wrap_type=fmt.get("wrap_type", "square"),
                width_inches=float(fmt.get("width", 0)),
                height_inches=float(fmt.get("height", 0)),
                behind_doc=bool(fmt.get("behind_doc", False)),
            )
            message = "Inserted floating image"

        elif operation == "add_tab_stop":
            t = word_ops.resolve_target(pkg, target_id)
            tab_data = json.loads(content_data)
            word_ops.add_tab_stop(
                t.leaf_el,
                float(tab_data["position"]),
                tab_data.get("alignment", "left"),
                tab_data.get("leader", "spaces"),
            )
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Added tab stop at {tab_data['position']} inches ({tab_data.get('alignment', 'left')}, {tab_data.get('leader', 'spaces')})"

        elif operation == "clear_tab_stops":
            t = word_ops.resolve_target(pkg, target_id)
            word_ops.clear_tab_stops(t.leaf_el)
            pkg.mark_xml_dirty("/word/document.xml")
            message = "Cleared all tab stops"

        elif operation == "insert_field":
            t = word_ops.resolve_target(pkg, target_id)
            field_code = content_data.strip().upper()
            word_ops.insert_field(t.leaf_el, field_code)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Inserted {field_code} field"

        # Bibliography operations
        elif operation == "add_source":
            data = json.loads(content_data)
            tag = word_ops.add_source(
                pkg,
                tag=data["tag"],
                source_type=data["source_type"],
                title=data["title"],
                authors=data.get("authors"),
                year=data.get("year"),
                publisher=data.get("publisher"),
                city=data.get("city"),
                journal_name=data.get("journal_name"),
                volume=data.get("volume"),
                issue=data.get("issue"),
                pages=data.get("pages"),
                url=data.get("url"),
            )
            message = f"Added bibliography source: {tag}"

        elif operation == "delete_source":
            tag = content_data.strip()
            if word_ops.delete_source(pkg, tag):
                message = f"Deleted bibliography source: {tag}"
            else:
                message = f"Source not found: {tag}"

        elif operation == "insert_citation":
            t = word_ops.resolve_target(pkg, target_id)
            data = json.loads(content_data) if content_data else {}
            tag = data.get("tag", "")
            display_text = data.get("display_text", "")
            locale = int(data.get("locale", 1033))
            word_ops.insert_citation(t.leaf_el, tag, display_text, locale)
            pkg.mark_xml_dirty("/word/document.xml")
            message = f"Inserted citation: {tag}"

        elif operation == "insert_bibliography":
            t = word_ops.resolve_target(pkg, target_id)
            word_ops.insert_bibliography(t.leaf_el)
            pkg.mark_xml_dirty("/word/document.xml")
            message = "Inserted bibliography field"

        pkg.save(file_path)
        return EditResult(success=True, element_id=element_id, message=message)

    raise ValueError(f"Unknown operation: {operation}")


if __name__ == "__main__":
    mcp.run()
