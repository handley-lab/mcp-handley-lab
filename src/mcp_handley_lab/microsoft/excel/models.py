"""Pydantic models for Excel MCP tool."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class SheetInfo(BaseModel):
    """Information about a worksheet."""

    model_config = ConfigDict(exclude_none=True)

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

    ref: str  # e.g., "A1"
    value: Any  # JSON primitive
    type: str | None = None  # Type code (optional)


class CellInfo(BaseModel):
    """Detailed cell information (verbose, opt-in)."""

    model_config = ConfigDict(exclude_none=True)

    ref: str  # e.g., "A1", "B2"
    value: Any  # JSON primitive
    type: str | None = None  # Type code (optional)
    formula: str | None = None
    number_format: str | None = None


class TableInfo(BaseModel):
    """Information about an Excel table (ListObject)."""

    model_config = ConfigDict(exclude_none=True)

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


class ExcelEditResult(BaseModel):
    """Result from Excel edit operation."""

    model_config = ConfigDict(exclude_none=True)

    success: bool
    message: str
    affected_refs: list[str] | None = None
