"""Pydantic models for Excel MCP tool."""

from typing import Any

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


class SheetInfo(BaseModel):
    """Information about a worksheet."""

    model_config = ConfigDict(exclude_none=True)

    id: str | None = None  # Content-addressed ID
    name: str
    index: int


class RangeMeta(BaseModel):
    """Metadata about a cell range."""

    model_config = ConfigDict(exclude_none=True)

    ref: str  # e.g., "A1:C5"
    rows: int
    cols: int
    filled: int  # Number of non-empty cells


class GridData(BaseModel):
    """Grid representation of cell data.

    Values are JSON primitives (int, float, str, bool, None).
    Types (when included) are single-char codes: n=number, s=string, b=boolean, e=error, f=formula.
    """

    model_config = ConfigDict(exclude_none=True)

    values: list[list[Any]]  # 2D array with JSON primitives
    types: list[list[str | None]] | None = None  # Optional 2D array of type codes


class SparseCell(BaseModel):
    """A single cell in sparse representation."""

    model_config = ConfigDict(exclude_none=True)

    id: str | None = None  # Content-addressed ID
    ref: str  # e.g., "A1"
    value: Any  # JSON primitive
    type: str | None = None  # Type code (optional)


class CellInfo(BaseModel):
    """Detailed cell information (verbose, opt-in)."""

    model_config = ConfigDict(exclude_none=True)

    id: str | None = None  # Content-addressed ID
    ref: str  # e.g., "A1", "B2"
    value: Any  # JSON primitive
    type: str | None = None  # Type code (optional)
    formula: str | None = None
    number_format: str | None = None


class TableInfo(BaseModel):
    """Information about an Excel table (ListObject)."""

    model_config = ConfigDict(exclude_none=True)

    id: str | None = None  # Content-addressed ID
    name: str
    sheet: str
    ref: str  # e.g., "A1:D10"
    columns: list[str]
    row_count: int


class StyleInfo(BaseModel):
    """Information about a cell style."""

    model_config = ConfigDict(exclude_none=True)

    index: int
    font: str | None = None
    fill: str | None = None
    border: str | None = None
    number_format: str | None = None


class ConditionalFormatInfo(BaseModel):
    """Information about a conditional formatting rule."""

    model_config = ConfigDict(exclude_none=True)

    id: str | None = None  # Content-addressed ID
    ref: str  # Range like "A1:C10"
    type: str  # Rule type (cellIs, colorScale, dataBar, etc.)
    priority: int
    operator: str | None = None  # For cellIs: lessThan, greaterThan, equal, etc.
    formula: str | None = None  # Formula or value for comparison
    style_index: int | None = None  # Style to apply (for cellIs rules)


class WorkbookMeta(BaseModel):
    """Workbook metadata."""

    model_config = ConfigDict(exclude_none=True)

    sheet_count: int
    sheets: list[str]


class ExcelReadResult(BaseModel):
    """Result from Excel read operation.

    Default representation is 'grid' with values array.
    Use include_types=true to add type codes.
    Use representation='sparse' for large ranges with few filled cells.
    Use representation='cells' for detailed per-cell metadata.
    """

    model_config = ConfigDict(exclude_none=True)

    scope: str
    sheet: str | None = None

    # Range metadata (for cells scope)
    range: RangeMeta | None = None

    # Grid representation (default)
    grid: GridData | None = None

    # Sparse representation (for <30% filled ranges)
    sparse: list[SparseCell] | None = None

    # Detailed cells (verbose, opt-in)
    cells: list[CellInfo] | None = None

    # Markdown view (optional, for LLM readability)
    view: str | None = None

    # Other scopes
    meta: WorkbookMeta | None = None
    sheets: list[SheetInfo] | None = None
    table: TableInfo | None = None
    tables: list[TableInfo] | None = None
    styles: list[StyleInfo] | None = None
    conditional_formats: list[ConditionalFormatInfo] | None = None
    protection: dict[str, Any] | None = None
    print_settings: dict[str, Any] | None = None
    charts: list["ChartInfo"] | None = None
    pivots: list["PivotInfo"] | None = None
    properties: DocumentProperties | None = None
    names: list["NameInfo"] | None = None
    validations: list["ValidationInfo"] | None = None
    autofilter: "AutoFilterInfo | None" = None
    comments: list["CommentInfo"] | None = None


class NameInfo(BaseModel):
    """Information about a defined name (named range)."""

    model_config = ConfigDict(exclude_none=True)

    id: str | None = None  # Content-addressed ID
    name: str
    refers_to: str  # Formula reference like "'Sheet1'!$A$1:$A$10"
    scope: str | None = None  # None = global, sheet name = local scope
    comment: str | None = None


class ValidationInfo(BaseModel):
    """Information about a data validation rule."""

    model_config = ConfigDict(exclude_none=True)

    id: str | None = None  # Content-addressed ID
    ref: str  # Range like "A1:A10"
    type: str  # list, whole, decimal, date, time, textLength, custom
    operator: str | None = None  # between, notBetween, equal, notEqual, etc.
    formula1: str | None = None  # First constraint value/formula
    formula2: str | None = None  # Second constraint (for between/notBetween)
    allow_blank: bool = True
    show_dropdown: bool = True  # For list type
    error_title: str | None = None
    error_message: str | None = None
    prompt_title: str | None = None
    prompt: str | None = None


class CommentInfo(BaseModel):
    """Information about a cell comment."""

    model_config = ConfigDict(exclude_none=True)

    id: str | None = None  # Content-addressed ID
    ref: str  # Cell reference like "A1"
    text: str
    author: str | None = None


class AutoFilterInfo(BaseModel):
    """Information about an AutoFilter on a sheet."""

    model_config = ConfigDict(exclude_none=True)

    ref: str  # Range like "A1:D10"
    filters: dict[int, list[str]] | None = None  # column index -> filter values


class ChartInfo(BaseModel):
    """Information about an Excel chart."""

    model_config = ConfigDict(exclude_none=True)

    id: str | None = None  # Content-addressed ID
    type: str  # bar, column, line, pie, scatter, area
    title: str | None = None
    data_range: str  # e.g., "'Sheet1'!A1:B10"
    position: str  # Anchor cell like "E5"


class PivotInfo(BaseModel):
    """Information about an Excel pivot table."""

    model_config = ConfigDict(exclude_none=True)

    id: str | None = None  # Content-addressed ID
    name: str
    data_range: str  # Source data range like "'Sheet1'!A1:D10"
    location: str  # Where pivot table renders
    row_fields: list[str]  # Fields used for row labels
    col_fields: list[str]  # Fields used for column labels
    value_fields: list[str]  # Fields used for values (aggregated)


class ExcelOpResult(BaseModel):
    """Result from a single Excel batch operation."""

    model_config = ConfigDict(exclude_none=True)

    index: int
    op: str
    success: bool
    element_id: str = ""  # For $prev chaining (cell_ref, range_ref, sheet_name, etc.)
    message: str = ""
    error: str = ""


class ExcelEditResult(BaseModel):
    """Result from Excel edit operation (batch mode)."""

    model_config = ConfigDict(exclude_none=True)

    success: bool
    message: str
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    results: list[ExcelOpResult] = Field(default_factory=list)
    saved: bool = False
