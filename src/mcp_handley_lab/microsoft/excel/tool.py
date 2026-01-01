"""Excel MCP tool - read and edit Excel workbooks.

Uses progressive disclosure with scopes for efficient reading.
Default representation is 'grid' with values + types arrays.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.microsoft.excel.models import (
    CellInfo,
    ExcelReadResult,
    GridData,
    RangeMeta,
    SheetInfo,
    SparseCell,
    WorkbookMeta,
)
from mcp_handley_lab.microsoft.excel.ops.cells import get_cells_in_range
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    index_to_column_letter,
    parse_cell_ref,
    parse_range_ref,
)
from mcp_handley_lab.microsoft.excel.ops.sheets import (
    get_used_range,
    list_sheets,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage

mcp = FastMCP(
    "Excel Tool",
    instructions="""Excel workbook (.xlsx) reading and editing tool.

Scopes:
- meta: Workbook metadata (sheet count, names)
- sheets: List of all sheets
- cells: Cell values in a range (default: grid representation)

Representation (for cells scope):
- grid: 2D arrays of values + types (default, most compact)
- sparse: List of non-empty cells (for large sparse ranges)
- cells: Detailed per-cell objects (verbose, for editing)

Add view=true to include a markdown table view for LLM readability.
""",
)


@mcp.tool()
def read(
    file_path: str = Field(description="Path to .xlsx file"),
    scope: str = Field(
        default="sheets",
        description="What to read: meta, sheets, cells",
    ),
    sheet: str = Field(
        default="",
        description="Sheet name (for cells scope, defaults to first sheet)",
    ),
    range_ref: str = Field(
        default="",
        description="Range like 'A1:C10' (for cells scope, defaults to used range)",
    ),
    representation: str = Field(
        default="grid",
        description="Output format: grid (2D arrays), sparse (cell list), cells (verbose)",
    ),
    include_types: bool = Field(
        default=False,
        description="Include type codes (n=number, s=string, b=bool, e=error, f=formula)",
    ),
    view: bool = Field(
        default=False,
        description="Include markdown table view for readability",
    ),
    limit: int = Field(
        default=1000,
        description="Maximum cells to return",
    ),
) -> dict[str, Any]:
    """Read data from an Excel workbook.

    Uses progressive disclosure with scopes:
    - meta: Quick workbook overview
    - sheets: List of sheets for subsequent queries
    - cells: Cell values with grid (default), sparse, or detailed representation
    """
    pkg = ExcelPackage.open(file_path)

    if scope == "meta":
        result = _read_meta(pkg)
    elif scope == "sheets":
        result = _read_sheets(pkg)
    elif scope == "cells":
        result = _read_cells(
            pkg, sheet, range_ref, representation, include_types, view, limit
        )
    elif scope in ("table", "tables", "styles"):
        raise NotImplementedError(f"Scope '{scope}' not yet implemented")
    else:
        raise ValueError(f"Unknown scope: {scope}")

    return result.model_dump(exclude_none=True)


def _read_meta(pkg: ExcelPackage) -> ExcelReadResult:
    """Read workbook metadata."""
    sheets = list_sheets(pkg)

    return ExcelReadResult(
        scope="meta",
        meta=WorkbookMeta(
            sheet_count=len(sheets),
            sheets=[s.name for s in sheets],
        ),
    )


def _read_sheets(pkg: ExcelPackage) -> ExcelReadResult:
    """Read list of sheets."""
    sheets = list_sheets(pkg)
    # Convert to SheetInfo without content-addressed IDs
    sheet_infos = [SheetInfo(name=s.name, index=s.index) for s in sheets]
    return ExcelReadResult(
        scope="sheets",
        sheets=sheet_infos,
    )


def _read_cells(
    pkg: ExcelPackage,
    sheet: str,
    range_ref: str,
    representation: str,
    include_types: bool,
    include_view: bool,
    limit: int,
) -> ExcelReadResult:
    """Read cells from a sheet."""
    if not sheet:
        sheets = list_sheets(pkg)
        if not sheets:
            return ExcelReadResult(scope="cells", sheet=None)
        sheet = sheets[0].name

    # Determine range
    if not range_ref:
        range_ref = get_used_range(pkg, sheet)
        if not range_ref:
            return ExcelReadResult(scope="cells", sheet=sheet)

    # Parse range
    start_ref, end_ref = parse_range_ref(range_ref)

    # Get cells (now returns: ref, value, type_code, formula)
    raw_cells = get_cells_in_range(pkg, sheet, start_ref, end_ref)

    # Apply limit
    raw_cells = raw_cells[:limit]

    # Calculate range metadata
    start_col, start_row, _, _ = parse_cell_ref(start_ref)
    end_col, end_row, _, _ = parse_cell_ref(end_ref)
    start_col_idx = column_letter_to_index(start_col)
    end_col_idx = column_letter_to_index(end_col)

    if start_col_idx > end_col_idx:
        start_col_idx, end_col_idx = end_col_idx, start_col_idx
        start_col, end_col = end_col, start_col
    if start_row > end_row:
        start_row, end_row = end_row, start_row

    num_rows = end_row - start_row + 1
    num_cols = end_col_idx - start_col_idx + 1

    range_meta = RangeMeta(
        ref=range_ref,
        rows=num_rows,
        cols=num_cols,
        filled=len(raw_cells),
    )

    # Build result based on representation
    result = ExcelReadResult(scope="cells", sheet=sheet, range=range_meta)

    if representation == "grid":
        result.grid = _build_grid(
            raw_cells, start_col_idx, start_row, num_rows, num_cols, include_types
        )
    elif representation == "sparse":
        result.sparse = _build_sparse(raw_cells, include_types)
    elif representation == "cells":
        result.cells = _build_cells(raw_cells, include_types)
    else:
        raise ValueError(f"Unknown representation: {representation}")

    # Optionally add markdown view
    if include_view:
        result.view = _build_markdown_view(
            raw_cells, start_col_idx, start_row, num_rows, num_cols
        ).content

    return result


def _build_grid(
    cells: list[tuple[str, Any, str | None, str | None]],
    start_col_idx: int,
    start_row: int,
    num_rows: int,
    num_cols: int,
    include_types: bool,
) -> GridData:
    """Build grid representation with values array and optional types."""
    values: list[list[Any]] = [[None] * num_cols for _ in range(num_rows)]
    types: list[list[str | None]] | None = (
        [[None] * num_cols for _ in range(num_rows)] if include_types else None
    )

    for cell_ref, value, type_code, _formula in cells:
        col, row, _, _ = parse_cell_ref(cell_ref)
        col_idx = column_letter_to_index(col)
        row_offset = row - start_row
        col_offset = col_idx - start_col_idx

        if 0 <= row_offset < num_rows and 0 <= col_offset < num_cols:
            values[row_offset][col_offset] = value
            if types is not None:
                types[row_offset][col_offset] = type_code

    return GridData(values=values, types=types)


def _build_sparse(
    cells: list[tuple[str, Any, str | None, str | None]],
    include_types: bool,
) -> list[SparseCell]:
    """Build sparse representation for non-empty cells only."""
    return [
        SparseCell(
            ref=cell_ref,
            value=value,
            type=type_code if include_types else None,
        )
        for cell_ref, value, type_code, _formula in cells
    ]


def _build_cells(
    cells: list[tuple[str, Any, str | None, str | None]],
    include_types: bool,
) -> list[CellInfo]:
    """Build detailed cell representation."""
    return [
        CellInfo(
            ref=cell_ref,
            value=value,
            type=type_code if include_types else None,
            formula=formula,
        )
        for cell_ref, value, type_code, formula in cells
    ]


class _MarkdownView:
    """Internal helper to build markdown table."""

    def __init__(self, content: str):
        self.content = content


def _build_markdown_view(
    cells: list[tuple[str, Any, str | None, str | None]],
    start_col_idx: int,
    start_row: int,
    num_rows: int,
    num_cols: int,
) -> _MarkdownView:
    """Build markdown table view for LLM readability."""
    # Build 2D array first
    grid: list[list[Any]] = [[None] * num_cols for _ in range(num_rows)]

    for cell_ref, value, _type_code, _formula in cells:
        col, row, _, _ = parse_cell_ref(cell_ref)
        col_idx = column_letter_to_index(col)
        row_offset = row - start_row
        col_offset = col_idx - start_col_idx

        if 0 <= row_offset < num_rows and 0 <= col_offset < num_cols:
            grid[row_offset][col_offset] = value

    # Build header with column letters
    col_headers = [index_to_column_letter(start_col_idx + i) for i in range(num_cols)]
    header_row = "|   | " + " | ".join(col_headers) + " |"
    separator = "|---" + "|---" * num_cols + "|"

    # Build data rows with row numbers
    data_rows = []
    for row_offset, row_data in enumerate(grid):
        row_num = start_row + row_offset
        formatted = [_format_cell_for_markdown(v) for v in row_data]
        data_rows.append(f"| {row_num} | " + " | ".join(formatted) + " |")

    content = "\n".join([header_row, separator] + data_rows)
    return _MarkdownView(content=content)


def _format_cell_for_markdown(value: Any) -> str:
    """Format a cell value for markdown table."""
    if value is None:
        return ""
    s = str(value)
    # Escape pipes and truncate long values
    s = s.replace("|", "\\|").replace("\n", " ")
    if len(s) > 50:
        s = s[:47] + "..."
    return s
