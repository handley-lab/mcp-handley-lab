"""Pydantic models for PowerPoint read/edit results."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CustomPropertyInfo(BaseModel):
    """A custom document property."""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: str  # String representation
    type: str  # "string", "datetime", "int", "bool", "float"


class DocumentProperties(BaseModel):
    """Document core and custom properties."""

    model_config = ConfigDict(extra="forbid")

    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""
    category: str = ""
    comments: str = ""
    created: str = ""
    modified: str = ""
    revision: int = 0
    last_modified_by: str = ""
    custom_properties: list[CustomPropertyInfo] = Field(default_factory=list)


class PresentationMeta(BaseModel):
    """Presentation metadata."""

    model_config = ConfigDict(extra="forbid")

    slide_count: int
    slide_width_inches: float
    slide_height_inches: float
    notes_count: int
    properties: DocumentProperties | None = None


class SlideInfo(BaseModel):
    """Information about a slide."""

    model_config = ConfigDict(extra="forbid")

    number: int
    title: str | None = None
    shape_count: int = 0
    has_notes: bool = False
    layout_name: str | None = None


class ShapeInfo(BaseModel):
    """Information about a shape on a slide."""

    model_config = ConfigDict(extra="forbid")

    shape_key: str  # slide_num:shape_id for edit targeting
    shape_id: int  # cNvPr@id
    type: str  # "shape", "picture", "table", "chart", "group", "connector"
    name: str | None = None

    # Position in inches
    x_inches: float
    y_inches: float
    width_inches: float
    height_inches: float

    # True if position is inherited from layout/master (no local xfrm)
    position_inherited: bool = False

    # Reading order position
    z_order: int = 0
    reading_order: int = 0

    # Text content (if any)
    text: str | None = None

    # Placeholder info (if placeholder)
    placeholder_type: str | None = None
    placeholder_idx: int | None = None


class NotesInfo(BaseModel):
    """Speaker notes information."""

    model_config = ConfigDict(extra="forbid")

    slide_number: int
    text: str
    paragraph_count: int = 1


class LayoutInfo(BaseModel):
    """Information about a slide layout."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: str | None = None  # e.g., "title", "obj", "twoObj"
    placeholder_count: int = 0
    placeholder_types: list[str] = Field(
        default_factory=list
    )  # e.g., ["title", "body", "dt"]
    master_name: str | None = None
    master_index: int = 0


class ImageInfo(BaseModel):
    """Information about an image on a slide."""

    model_config = ConfigDict(extra="forbid")

    shape_key: str  # slide_num:shape_id for edit targeting
    shape_id: int
    name: str | None = None
    content_type: str  # e.g., "image/png"

    # Position in inches
    x_inches: float
    y_inches: float
    width_inches: float
    height_inches: float


class TableCell(BaseModel):
    """Information about a table cell."""

    model_config = ConfigDict(extra="forbid")

    row: int
    col: int
    text: str


class TableInfo(BaseModel):
    """Information about a table on a slide."""

    model_config = ConfigDict(extra="forbid")

    shape_key: str  # slide_num:shape_id for edit targeting
    shape_id: int
    name: str | None = None

    # Position in inches
    x_inches: float
    y_inches: float
    width_inches: float
    height_inches: float

    # Table structure
    rows: int
    cols: int
    cells: list[TableCell] = Field(default_factory=list)


class ChartInfo(BaseModel):
    """Information about a chart on a slide."""

    model_config = ConfigDict(extra="forbid")

    shape_key: str  # slide_num:shape_id
    type: str  # bar, column, line, pie, scatter, area
    title: str | None = None


class PowerPointReadResult(BaseModel):
    """Result from read() operation."""

    model_config = ConfigDict(extra="forbid", exclude_none=True)

    scope: str
    meta: PresentationMeta | None = None
    slides: list[SlideInfo] | None = None
    shapes: list[ShapeInfo] | None = None
    text: str | None = None
    notes: NotesInfo | None = None
    layouts: list[LayoutInfo] | None = None
    images: list[ImageInfo] | None = None
    tables: list[TableInfo] | None = None
    charts: list[ChartInfo] | None = None
    properties: DocumentProperties | None = None


class PowerPointOpResult(BaseModel):
    """Result from a single PowerPoint batch operation."""

    model_config = ConfigDict(extra="forbid", exclude_none=True)

    index: int
    op: str
    success: bool
    element_id: str = ""  # For $prev chaining (shape_key, etc.)
    message: str = ""
    error: str = ""


class PowerPointEditResult(BaseModel):
    """Result from edit() operation (batch mode)."""

    model_config = ConfigDict(extra="forbid", exclude_none=True)

    success: bool
    message: str
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    results: list[PowerPointOpResult] = Field(default_factory=list)
    saved: bool = False
