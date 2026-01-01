"""Pydantic models for Excel MCP tool."""

from pydantic import BaseModel


class SheetInfo(BaseModel):
    """Information about a worksheet."""

    name: str
    index: int
    id: str  # Content-addressed ID


class CellInfo(BaseModel):
    """Information about a cell."""

    id: str  # Content-addressed ID
    sheet: str
    ref: str  # e.g., "A1", "B2"
    value: str | None
    formula: str | None = None
    type: str  # "string", "number", "boolean", "error", "empty"


class RangeInfo(BaseModel):
    """Information about a range of cells."""

    id: str  # Content-addressed ID
    sheet: str
    ref: str  # e.g., "A1:C5"
    values: list[list[str | None]]  # 2D array of values


class TableInfo(BaseModel):
    """Information about an Excel table (ListObject)."""

    id: str  # Content-addressed ID
    name: str
    sheet: str
    ref: str  # e.g., "A1:D10"
    columns: list[str]
    row_count: int


class StyleInfo(BaseModel):
    """Information about a cell style."""

    id: str  # Style index
    font: str | None = None
    fill: str | None = None
    border: str | None = None
    number_format: str | None = None


class WorkbookMeta(BaseModel):
    """Workbook metadata."""

    sheet_count: int
    sheets: list[str]  # Sheet names
    has_shared_strings: bool
    shared_string_count: int


class ExcelReadResult(BaseModel):
    """Result from Excel read operation."""

    scope: str
    meta: WorkbookMeta | None = None
    sheets: list[SheetInfo] | None = None
    cells: list[CellInfo] | None = None
    range: RangeInfo | None = None
    table: TableInfo | None = None
    tables: list[TableInfo] | None = None
    styles: list[StyleInfo] | None = None


class ExcelEditResult(BaseModel):
    """Result from Excel edit operation."""

    success: bool
    message: str
    affected_ids: list[str] = []
