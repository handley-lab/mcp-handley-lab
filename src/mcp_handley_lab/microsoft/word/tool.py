"""Word document MCP tool - read and edit operations."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.microsoft.word.models import (
    DocumentReadResult,
    EditResult,
)

mcp = FastMCP("Word Document Tool")


@mcp.tool(
    description="Read Word document content. Scopes: 'meta' (doc info), 'outline' (headings only), 'blocks' (all content), 'search' (find text), 'table_cells' (cells of a table), 'table_layout' (table alignment/autofit/row heights), 'runs' (text runs in a paragraph), 'comments' (all comments), 'headers_footers' (headers/footers per section), 'page_setup' (margins, orientation per section), 'images' (embedded inline images), 'hyperlinks' (all hyperlinks with URLs), 'styles' (all document styles), 'style' (detailed formatting for a specific style by name in target_id), 'revisions' (tracked changes/revisions), 'list' (list properties for a paragraph by target_id), 'text_boxes' (all text boxes/floating content), 'text_box_content' (paragraphs inside a text box by target_id), 'bookmarks' (all bookmarks), 'captions' (all captions), 'toc' (table of contents info), 'footnotes' (all footnotes and endnotes), 'content_controls' (all content controls/SDTs), 'equations' (math equations with simplified text), 'bibliography' (bibliography sources), 'charts' (embedded charts). Block IDs are content-addressed (type_hash_occurrence) and CHANGE when content changes or after inserts/deletes shift occurrence index - use element_id from edit response for chaining."
)
def read(
    file_path: str = Field(..., description="Path to .docx file"),
    scope: str = Field(
        "outline",
        description="What to read: 'meta', 'outline', 'blocks', 'search', 'table_cells', 'table_layout', 'runs', 'comments', 'headers_footers', 'page_setup', 'images', 'hyperlinks', 'styles', 'style', 'revisions', 'list', 'text_boxes', 'text_box_content', 'bookmarks', 'captions', 'toc', 'footnotes', 'content_controls', 'equations', 'bibliography', 'charts'",
    ),
    target_id: str = Field(
        "",
        description="Block ID for table_cells/runs/table_layout/list scopes, style name for 'style' scope, or text box ID for 'text_box_content' scope. For nested tables use hierarchical paths: 'table_abc_0#r0c1/tbl0' (nested table 0 inside cell row=0,col=1). Path segments: #rXcY (cell), /tblN (Nth descendant table in document order), /pN (paragraph). Deep nesting: 'table_abc_0#r0c0/tbl0/r0c0/tbl0'. Note: /tblN indexes ALL descendant tables in the cell, not just direct children.",
    ),
    search_query: str = Field("", description="Text to search for (scope='search')"),
    limit: int = Field(50, description="Max blocks to return"),
    offset: int = Field(0, description="Pagination offset"),
) -> DocumentReadResult:
    """Read Word document content."""
    from mcp_handley_lab.microsoft.word.shared import read as _read

    return _read(
        file_path=file_path,
        scope=scope,
        target_id=target_id,
        search_query=search_query,
        limit=limit,
        offset=offset,
    )


@mcp.tool(
    description="Render Word document for visual inspection or sharing. Use read to get document structure, render to see it visually. output='png' (default) returns labeled images for Claude to see. output='pdf' saves PDF to disk alongside the source file. Requires libreoffice (and pdftoppm for PNG)."
)
def render(
    file_path: str = Field(..., description="Path to .docx file"),
    pages: list[int] = Field(
        default=[],
        description="Page numbers to render (1-based). Required for PNG output. Max 5 pages.",
    ),
    dpi: int = Field(150, description="Resolution for PNG (default 150, max 300)"),
    output: str = Field(
        "png", description="Output format: 'png' (images) or 'pdf' (full document)"
    ),
):  # No return type - allows mixed TextContent + Image content
    """Render Word document for visual inspection or sharing."""
    from mcp_handley_lab.microsoft.word.shared import render as _render

    return _render(file_path=file_path, pages=pages or None, dpi=dpi, output=output)


@mcp.tool(
    description="Edit Word document with batch operations. Supported ops: 'insert_before', 'insert_after', 'append', 'delete', 'replace', 'style', 'edit_cell', 'edit_run', 'edit_style', 'add_comment', 'reply_comment', 'resolve_comment', 'unresolve_comment', 'set_header', 'set_footer', 'set_first_page_header', 'set_first_page_footer', 'set_even_page_header', 'set_even_page_footer', 'append_header', 'append_footer', 'clear_header', 'clear_footer', 'set_margins', 'set_orientation', 'set_columns', 'set_line_numbering', 'set_page_borders', 'set_custom_property', 'delete_custom_property', 'create_style', 'delete_style', 'insert_image', 'insert_floating_image', 'delete_image', 'add_row', 'add_column', 'delete_row', 'delete_column', 'add_page_break', 'add_break', 'set_property', 'add_section', 'merge_cells', 'set_table_alignment', 'set_table_autofit', 'set_table_fixed_layout', 'set_row_height', 'set_cell_width', 'set_cell_vertical_alignment', 'set_cell_borders', 'set_cell_shading', 'set_header_row', 'add_tab_stop', 'clear_tab_stops', 'insert_field', 'insert_page_x_of_y', 'accept_change', 'reject_change', 'accept_all_changes', 'reject_all_changes', 'create_list', 'set_list_level', 'promote_list', 'demote_list', 'restart_numbering', 'remove_list', 'add_to_list', 'edit_text_box', 'add_bookmark', 'add_hyperlink', 'insert_cross_ref', 'insert_caption', 'insert_toc', 'update_toc', 'add_footnote', 'delete_footnote', 'set_content_control', 'create_content_control', 'add_source', 'delete_source', 'insert_citation', 'insert_bibliography', 'insert_chart', 'delete_chart', 'update_chart_data'. Block IDs are content-addressed and CHANGE when content changes or after inserts/deletes shift occurrence index. Always use element_id from response for chaining operations on modified content. Creates a new file if file_path doesn't exist. 'update_toc' sets dirty flag; Word updates content on open. 'add_to_list' adds a new paragraph to an existing list; content_data: {\"text\": \"...\", \"position\": \"before|after\", \"level\": 0-8 (optional)}. 'add_hyperlink' content_data: {\"text\": \"...\", \"address\"?: \"...\", \"fragment\"?: \"...\", \"replace\"?: true}. 'insert_chart' content_data: {\"chart_type\": \"bar|column|line|pie|scatter|area\", \"data\": [[\"Cat\",\"S1\"],[\"A\",10]], \"title\"?: \"...\"}, formatting: {\"width\"?: 5.0, \"height\"?: 3.0}. For 'replace', 'insert_before', 'insert_after', and 'append' with content_type='paragraph': when content_data contains newlines, lightweight markdown is supported — lines starting with '- ' or '* ' become bullet items, '1. ' becomes numbered items, and plain lines become paragraphs. Consecutive list items of the same type share a single list. Indent with 2 spaces per level (up to 8)."
)
def edit(
    file_path: str = Field(..., description="Path to .docx file"),
    ops: str = Field(
        ...,
        description='JSON array of operation objects. Each object must have an "op" field and operation-specific parameters. Example: [{"op": "edit_cell", "target_id": "table_abc_0", "row": 0, "col": 0, "content_data": "A1"}]. Use $prev[N] in target_id to reference element_id from operation N (0-indexed). Supported ops: insert_before, insert_after, append, delete, replace, style, edit_cell, edit_run, edit_style, add_comment, reply_comment, resolve_comment, unresolve_comment, set_header, set_footer, set_first_page_header, set_first_page_footer, set_even_page_header, set_even_page_footer, append_header, append_footer, clear_header, clear_footer, set_margins, set_orientation, set_columns, set_line_numbering, set_page_borders, set_custom_property, delete_custom_property, create_style, delete_style, insert_image, insert_floating_image, delete_image, add_row, add_column, delete_row, delete_column, add_page_break, add_break, set_property, add_section, merge_cells, set_table_alignment, set_table_autofit, set_table_fixed_layout, set_row_height, set_cell_width, set_cell_vertical_alignment, set_cell_borders, set_cell_shading, set_header_row, add_tab_stop, clear_tab_stops, insert_field, insert_page_x_of_y, accept_change, reject_change, accept_all_changes, reject_all_changes, create_list, set_list_level, promote_list, demote_list, restart_numbering, remove_list, add_to_list, edit_text_box, add_bookmark, add_hyperlink, insert_cross_ref, insert_caption, insert_toc, update_toc, add_footnote, delete_footnote, set_content_control, create_content_control, add_source, delete_source, insert_citation, insert_bibliography.',
    ),
) -> EditResult:
    """Edit Word document with batch operations. Creates a new file if file_path doesn't exist."""
    from mcp_handley_lab.microsoft.word.shared import edit as _edit

    return _edit(file_path=file_path, ops=ops)


if __name__ == "__main__":
    mcp.run()
