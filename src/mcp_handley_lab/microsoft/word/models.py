"""Pydantic models for Word document MCP tool."""

from pydantic import BaseModel, Field


class Block(BaseModel):
    """A block-level element in a Word document (paragraph, heading, or table)."""

    id: str
    type: str  # "paragraph", "heading1".."heading9", or "table"
    text: str  # Content (for tables: markdown preview)
    style: str  # Word style name
    level: int = 0  # Heading level (1-9) or 0 for non-headings
    rows: int = 0  # Row count (tables only)
    cols: int = 0  # Column count (tables only)


class CustomPropertyInfo(BaseModel):
    """A custom document property."""

    name: str
    value: str  # String representation
    type: str  # "string", "datetime", "int", "bool", "float"


class DocumentMeta(BaseModel):
    """Document metadata from core properties."""

    title: str = ""
    author: str = ""
    created: str = ""
    modified: str = ""
    revision: int = 0
    sections: int = 0
    custom_properties: list[CustomPropertyInfo] = Field(default_factory=list)


class CellInfo(BaseModel):
    """A table cell with coordinates and hierarchical ID."""

    row: int  # 0-based row index
    col: int  # 0-based column index
    text: str  # Cell text content
    hierarchical_id: str = ""  # e.g., "table_abc_0#r0c0"
    grid_span: int = 1  # Horizontal span (columns merged)
    row_span: int = 1  # Vertical span (rows merged)
    is_merge_origin: bool = True  # False if this is a continuation cell
    width_inches: float | None = None  # Cell width
    vertical_alignment: str | None = None  # "top", "center", "bottom"
    # Border properties (format: "style:size:color", e.g., "single:24:000000")
    border_top: str | None = None
    border_bottom: str | None = None
    border_left: str | None = None
    border_right: str | None = None
    fill_color: str | None = None  # Hex background color (e.g., "FF0000")
    nested_tables: int = 0  # Count of all descendant tables (includes deeply nested)


class RowInfo(BaseModel):
    """Row properties for a table."""

    index: int  # 0-based row index
    height_inches: float | None = None
    height_rule: str | None = None  # "auto", "at_least", "exactly"
    is_header: bool = False  # True if marked with w:tblHeader (repeats on each page)


class TableLayoutInfo(BaseModel):
    """Table layout properties."""

    table_id: str
    alignment: str | None = None  # "left", "center", "right"
    autofit: bool = True
    rows: list[RowInfo] = Field(default_factory=list)


class RunInfo(BaseModel):
    """A run (text segment with uniform formatting) within a paragraph."""

    index: int  # 0-based position in paragraph
    text: str
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    font_name: str | None = None
    font_size: float | None = None  # in points
    color: str | None = None  # hex color (e.g., "FF0000")
    highlight_color: str | None = None  # e.g., "yellow", "cyan"
    strike: bool | None = None
    double_strike: bool | None = None
    subscript: bool | None = None
    superscript: bool | None = None
    style: str | None = None  # Character style name
    is_hyperlink: bool = False  # True if inside a hyperlink
    hyperlink_url: str | None = None  # URL if inside hyperlink
    # Additional font properties
    all_caps: bool | None = None  # Text appears in capital letters
    small_caps: bool | None = None  # Lowercase as smaller capitals
    hidden: bool | None = None  # Hidden text (not displayed unless settings allow)
    emboss: bool | None = None  # Raised emboss effect
    imprint: bool | None = None  # Pressed into page effect
    outline: bool | None = None  # One-pixel border around glyphs
    shadow: bool | None = None  # Shadow effect on characters


class HyperlinkInfo(BaseModel):
    """A hyperlink within a paragraph."""

    index: int  # Position in document's hyperlink list
    text: str  # Visible link text
    url: str  # Full URL (address + fragment)
    address: str  # Base URL
    fragment: str  # Anchor/bookmark (without #)
    is_external: bool  # True if external link (has rId)


class CommentInfo(BaseModel):
    """A comment in the document."""

    id: int  # python-docx comment_id
    author: str
    initials: str | None = None
    timestamp: str | None = None  # ISO format
    text: str
    # Threading fields (Word 2013+ via commentsExtended.xml)
    parent_id: int | None = None  # ID of parent comment (if reply)
    resolved: bool = False  # From commentsExtended.xml done state
    replies: list[int] = Field(default_factory=list)  # IDs of replies (computed)


class HeaderFooterInfo(BaseModel):
    """Header and footer info for a document section."""

    section_index: int  # 0-based section index
    header_text: str | None = None  # None if linked to previous
    footer_text: str | None = None  # None if linked to previous
    header_is_linked: bool = True  # True = inherits from previous section
    footer_is_linked: bool = True
    first_page_header_text: str | None = None  # Only if different_first_page
    first_page_footer_text: str | None = None
    has_different_first_page: bool = False
    even_page_header_text: str | None = None  # Only if different_odd_even
    even_page_footer_text: str | None = None
    has_different_odd_even: bool = False


class LineNumberingInfo(BaseModel):
    """Line numbering settings for a section."""

    enabled: bool = False
    restart: str = "newPage"  # "newPage", "newSection", "continuous"
    start: int = 1
    count_by: int = 1  # Number every N lines
    distance_inches: float = 0.5  # From margin


class PageSetupInfo(BaseModel):
    """Page setup info for a document section."""

    section_index: int  # 0-based section index
    orientation: str  # "portrait" or "landscape"
    page_width: float  # inches
    page_height: float  # inches
    top_margin: float  # inches
    bottom_margin: float  # inches
    left_margin: float  # inches
    right_margin: float  # inches
    # Multi-column layout
    columns: int = 1  # Number of columns
    column_spacing: float = 0.5  # Inches between columns
    column_separator: bool = False  # Line between columns
    # Line numbering
    line_numbering: LineNumberingInfo | None = None


class ImageInfo(BaseModel):
    """Information about an embedded image (inline or floating)."""

    id: str  # image_{sha1[:8]}_{occurrence}
    width_inches: float
    height_inches: float
    content_type: str  # e.g., "image/png", "image/jpeg"
    block_id: (
        str  # Hierarchical ID of containing paragraph (e.g., "table_abc_0#r0c0/p0")
    )
    run_index: int  # 0-based index of run within paragraph
    image_index_in_run: int  # 0-based index among inline images in run
    filename: str  # Original filename if available
    # Floating image positioning (Phase 5)
    position_type: str = "inline"  # "inline" or "anchor"
    position_h: float | None = None  # Horizontal position (inches)
    position_v: float | None = None  # Vertical position (inches)
    relative_from_h: str | None = None  # "column", "page", "margin", "character"
    relative_from_v: str | None = None  # "paragraph", "page", "margin", "line"
    wrap_type: str | None = (
        None  # "square", "tight", "through", "top_and_bottom", "none"
    )
    behind_doc: bool = False  # True if behind text


class StyleInfo(BaseModel):
    """A style definition in the document."""

    name: str  # UI name (e.g., "Heading 1")
    style_id: str  # Internal ID
    type: str  # "paragraph", "character", "table", "list"
    builtin: bool  # True if built-in style
    base_style: str | None = None  # Parent style name
    next_style: str | None = None  # Auto-applied next paragraph style
    hidden: bool = False  # Hidden from UI
    quick_style: bool = False  # In Quick Styles gallery


class StyleFormatInfo(BaseModel):
    """Detailed style formatting (returned when reading a specific style)."""

    name: str
    style_id: str
    type: str
    # Font properties (from style.font)
    font_name: str | None = None
    font_size: float | None = None  # points
    bold: bool | None = None
    italic: bool | None = None
    color: str | None = None  # hex
    # Paragraph properties (paragraph styles only)
    alignment: str | None = None
    left_indent: float | None = None  # inches
    space_before: float | None = None  # points
    space_after: float | None = None  # points
    line_spacing: float | None = None


class TabStopInfo(BaseModel):
    """A tab stop definition."""

    position_inches: float
    alignment: str  # "left", "center", "right", "decimal"
    leader: str  # "spaces", "dots", "heavy", "middle_dot"


class ParagraphFormatInfo(BaseModel):
    """Paragraph formatting properties."""

    alignment: str | None = None  # "left", "center", "right", "justify"
    left_indent: float | None = None  # inches
    right_indent: float | None = None  # inches
    first_line_indent: float | None = None  # inches
    space_before: float | None = None  # points
    space_after: float | None = None  # points
    line_spacing: float | None = None  # multiplier or points
    keep_with_next: bool | None = None
    page_break_before: bool | None = None
    tab_stops: list[TabStopInfo] = Field(default_factory=list)


class RevisionInfo(BaseModel):
    """Information about a tracked change (revision) in the document."""

    id: str  # w:id attribute (string, not int - IDs can have leading zeros)
    type: str  # "insertion", "deletion", "move", "formatting", "table"
    author: str  # Change author
    date: str  # ISO date string
    text: str  # Affected text (empty for formatting/move markers)
    supported: bool = True  # Whether accept/reject is implemented for this change
    tag: str = ""  # Original OOXML tag name (e.g., "ins", "del", "moveFrom")


class ListInfo(BaseModel):
    """List properties for a paragraph."""

    num_id: int | None = None  # Numbering definition ID
    abstract_num_id: int | None = None  # Abstract numbering definition ID
    level: int | None = None  # Indentation level (0-8)
    format_type: str | None = None  # e.g., "decimal", "bullet", "lowerLetter"
    start_value: int | None = None  # Start value for this level
    level_text: str | None = None  # e.g., "%1." from w:lvlText


class TextBoxInfo(BaseModel):
    """Information about a text box (floating content)."""

    id: str  # From wp:docPr @id (stable) or fallback to content hash
    name: str | None = None  # From wp:docPr @name
    text: str  # Full text content
    paragraph_count: int  # Number of paragraphs inside
    width_inches: float = 0.0  # Width in inches
    height_inches: float = 0.0  # Height in inches
    position_type: str  # "anchor" (floating) or "inline"
    source_type: str  # "drawingml" or "vml"
    wrap_type: str | None = None  # "square", "tight", "none", etc.


class BookmarkInfo(BaseModel):
    """A named bookmark/anchor in the document."""

    id: int  # w:id attribute
    name: str  # w:name attribute (must be unique, no spaces, start with letter)
    block_id: str  # Containing block


class CaptionInfo(BaseModel):
    """A caption with sequence number."""

    id: str  # Content-addressed ID
    label: str  # e.g., "Figure", "Table"
    number: int  # Extracted from SEQ field result
    text: str  # Caption text after number
    block_id: str  # Block ID of caption paragraph
    style: str  # Should be "Caption" for proper Word integration


class TOCInfo(BaseModel):
    """Table of Contents metadata."""

    exists: bool
    heading_levels: str = "1-3"  # Extracted from field switches if present
    entry_count: int = 0  # Cached entries (may be stale - Word recalculates)
    block_id: str | None = None  # ID of paragraph containing TOC field
    has_sdt_wrapper: bool = False  # True if wrapped in SDT (optional)
    is_dirty: bool = False  # True if w:dirty="true" set


class ContentControlInfo(BaseModel):
    """A content control (SDT) in the document."""

    id: int  # w:id attribute
    tag: str | None = None  # w:tag for automation
    alias: str | None = None  # Display name
    type: str  # "text", "dropdown", "checkbox", "date", "richText", "color"
    value: str  # Current value/selection
    options: list[str] = Field(default_factory=list)  # For dropdown
    checked: bool | None = None  # For checkbox
    date_format: str | None = None  # For date picker
    block_id: str  # Containing block


class FootnoteInfo(BaseModel):
    """A footnote or endnote in the document."""

    id: int  # w:id attribute
    type: str  # "footnote" or "endnote"
    text: str  # Content text
    block_id: str  # Block containing reference


class EquationInfo(BaseModel):
    """A math equation (OMML) in the document."""

    id: str  # Content-addressed ID
    text: str  # Simplified text representation (a/b, x^2, etc.)
    block_id: str  # Containing block
    complexity: str  # "simple", "fraction", "matrix", "complex"


class BibAuthor(BaseModel):
    """An author in a bibliography source."""

    first: str = ""
    last: str = ""
    middle: str | None = None


class BibSourceInfo(BaseModel):
    """A bibliography source entry."""

    tag: str  # Unique identifier (e.g., "Smith2020")
    source_type: str  # Book, JournalArticle, etc.
    title: str
    authors: list[BibAuthor] = Field(default_factory=list)
    year: str | None = None
    publisher: str | None = None
    city: str | None = None
    journal_name: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    url: str | None = None


class DocumentReadResult(BaseModel):
    """Result from read() tool."""

    block_count: int
    blocks: list[Block] = Field(default_factory=list)
    meta: DocumentMeta | None = None
    cells: list[CellInfo] = Field(default_factory=list)
    table_rows: int = 0
    table_cols: int = 0
    runs: list[RunInfo] = Field(default_factory=list)
    comments: list[CommentInfo] = Field(default_factory=list)
    headers_footers: list[HeaderFooterInfo] = Field(default_factory=list)
    page_setup: list[PageSetupInfo] = Field(default_factory=list)
    images: list[ImageInfo] = Field(default_factory=list)
    hyperlinks: list[HyperlinkInfo] = Field(default_factory=list)
    styles: list[StyleInfo] = Field(default_factory=list)
    paragraph_format: ParagraphFormatInfo | None = None  # For runs scope
    style_format: "StyleFormatInfo | None" = None  # For style scope
    table_layout: "TableLayoutInfo | None" = None  # For table_layout scope
    revisions: list[RevisionInfo] = Field(default_factory=list)  # For revisions scope
    has_tracked_changes: bool = False  # True if document has any tracked changes
    list_info: "ListInfo | None" = None  # For list scope
    text_boxes: list["TextBoxInfo"] = Field(
        default_factory=list
    )  # For text_boxes scope
    bookmarks: list["BookmarkInfo"] = Field(default_factory=list)  # For bookmarks scope
    captions: list["CaptionInfo"] = Field(default_factory=list)  # For captions scope
    toc_info: "TOCInfo | None" = None  # For toc scope
    footnotes: list["FootnoteInfo"] = Field(default_factory=list)  # For footnotes scope
    content_controls: list["ContentControlInfo"] = Field(
        default_factory=list
    )  # For content_controls scope
    equations: list["EquationInfo"] = Field(default_factory=list)  # For equations scope
    bibliography_sources: list["BibSourceInfo"] = Field(
        default_factory=list
    )  # For bibliography scope


class EditResult(BaseModel):
    """Result from edit() tool."""

    success: bool
    element_id: str = ""
    comment_id: int | None = None
    message: str
