"""Pydantic models for Visio read results."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PageInfo(BaseModel):
    """Information about a Visio page."""

    model_config = ConfigDict(extra="forbid")

    number: int
    name: str | None = None
    width_inches: float | None = None
    height_inches: float | None = None
    shape_count: int = 0
    is_background: bool = False


class ShapeInfo(BaseModel):
    """Information about a shape on a page."""

    model_config = ConfigDict(extra="forbid")

    shape_id: int
    shape_key: str  # page_num:shape_id
    name: str | None = None
    name_u: str | None = None  # Universal name
    type: str  # "shape", "group", "connector", "foreign"
    text: str | None = None

    # Position in inches (native Visio coordinates, Y from bottom)
    x_inches: float | None = None
    y_inches: float | None = None
    width_inches: float | None = None
    height_inches: float | None = None

    # For connectors (1D shapes)
    begin_x: float | None = None
    begin_y: float | None = None
    end_x: float | None = None
    end_y: float | None = None

    # Master reference
    master_id: int | None = None
    master_name: str | None = None

    # Group membership
    parent_id: int | None = None

    # Reading order
    reading_order: int = 0


class ConnectionInfo(BaseModel):
    """A connector relationship between shapes."""

    model_config = ConfigDict(extra="forbid")

    connector_id: int
    connector_name: str | None = None
    connector_text: str | None = None
    from_shape_id: int | None = None
    from_shape_name: str | None = None
    to_shape_id: int | None = None
    to_shape_name: str | None = None


class MasterInfo(BaseModel):
    """Information about a master shape (stencil)."""

    model_config = ConfigDict(extra="forbid")

    master_id: int
    name: str | None = None
    name_u: str | None = None  # Universal name
    icon_size: str | None = None
    shape_count: int = 0


class CommentInfo(BaseModel):
    """Information about a comment in the document."""

    model_config = ConfigDict(extra="forbid")

    page_id: int
    shape_id: int | None = None  # None for page-level comments
    author: str | None = None
    author_id: str | None = None
    text: str
    date: str | None = None


class ShapeDataProperty(BaseModel):
    """A custom property from a shape's Property section."""

    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    value: str | None = None
    prompt: str | None = None
    type: str | None = None
    format: str | None = None
    sort_key: str | None = None
    row_name: str | None = None


class ShapeCellInfo(BaseModel):
    """A singleton cell from a shape's ShapeSheet."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    value: str | None = None
    formula: str | None = None
    unit: str | None = None


class DocumentProperties(BaseModel):
    """Document properties from docProps."""

    model_config = ConfigDict(extra="forbid")

    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""
    category: str = ""
    description: str = ""
    created: str = ""
    modified: str = ""
    last_modified_by: str = ""


class VisioMeta(BaseModel):
    """Visio document metadata."""

    model_config = ConfigDict(extra="forbid")

    page_count: int = 0
    master_count: int = 0
    properties: DocumentProperties | None = None


class VisioOpResult(BaseModel):
    """Result of a single edit operation."""

    model_config = ConfigDict(extra="forbid")

    index: int
    op: str
    success: bool
    element_id: str = ""
    message: str = ""
    error: str = ""


class VisioEditResult(BaseModel):
    """Result from edit() operation."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    message: str
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    results: list[VisioOpResult] = Field(default_factory=list)
    saved: bool = False


class VisioReadResult(BaseModel):
    """Result from read() operation."""

    model_config = ConfigDict(extra="forbid", exclude_none=True)

    scope: str
    meta: VisioMeta | None = None
    pages: list[PageInfo] | None = None
    shapes: list[ShapeInfo] | None = None
    text: str | None = None
    connections: list[ConnectionInfo] | None = None
    masters: list[MasterInfo] | None = None
    shape_data: list[ShapeDataProperty] | None = None
    shape_cells: list[ShapeCellInfo] | None = None
    properties: DocumentProperties | None = None
    comments: list[CommentInfo] | None = None
