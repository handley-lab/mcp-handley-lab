"""Excel MCP tool - read and edit Excel workbooks.

Uses progressive disclosure with scopes for efficient reading.
"""

from __future__ import annotations

from mcp import Field
from mcp.server.fastmcp import FastMCP

from mcp_handley_lab.microsoft.excel.models import (
    CellInfo,
    ExcelReadResult,
    RangeInfo,
    WorkbookMeta,
)
from mcp_handley_lab.microsoft.excel.ops.cells import (
    get_cells_in_range,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    make_cell_id,
    make_range_id,
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

Use scope parameter to control what data is returned:
- meta: Workbook metadata (sheet count, names)
- sheets: List of all sheets with IDs
- cells: Cell values in a range
- table: Table data by name (not yet implemented)
- tables: List of all tables (not yet implemented)
- styles: Style definitions (not yet implemented)

For cells scope, specify sheet and optionally range_ref.
""",
)


@mcp.tool()
def read(
    file_path: str = Field(description="Path to .xlsx file"),
    scope: str = Field(
        default="sheets",
        description="What to read: meta, sheets, cells, table, tables, styles",
    ),
    sheet: str = Field(
        default="",
        description="Sheet name (required for cells scope)",
    ),
    range_ref: str = Field(
        default="",
        description="Range like 'A1:C10' (optional, defaults to used range)",
    ),
    table_name: str = Field(
        default="",
        description="Table name (for table scope)",
    ),
    limit: int = Field(
        default=1000,
        description="Maximum cells to return (for cells scope)",
    ),
) -> ExcelReadResult:
    """Read data from an Excel workbook.

    Uses progressive disclosure with scopes:
    - meta: Quick workbook overview
    - sheets: List of sheets with IDs for subsequent queries
    - cells: Cell values (specify sheet, optionally range)
    """
    pkg = ExcelPackage.open(file_path)

    if scope == "meta":
        return _read_meta(pkg)
    elif scope == "sheets":
        return _read_sheets(pkg)
    elif scope == "cells":
        return _read_cells(pkg, sheet, range_ref, limit)
    elif scope in ("table", "tables", "styles"):
        return ExcelReadResult(
            scope=scope,
            meta=WorkbookMeta(
                sheet_count=0,
                sheets=[],
                has_shared_strings=False,
                shared_string_count=0,
            ),
        )
    else:
        raise ValueError(f"Unknown scope: {scope}")


def _read_meta(pkg: ExcelPackage) -> ExcelReadResult:
    """Read workbook metadata."""
    sheets = list_sheets(pkg)
    has_ss = len(pkg.shared_strings) > 0
    ss_count = len(pkg.shared_strings)

    return ExcelReadResult(
        scope="meta",
        meta=WorkbookMeta(
            sheet_count=len(sheets),
            sheets=[s.name for s in sheets],
            has_shared_strings=has_ss,
            shared_string_count=ss_count,
        ),
    )


def _read_sheets(pkg: ExcelPackage) -> ExcelReadResult:
    """Read list of sheets."""
    sheets = list_sheets(pkg)
    return ExcelReadResult(
        scope="sheets",
        sheets=sheets,
    )


def _read_cells(
    pkg: ExcelPackage, sheet: str, range_ref: str, limit: int
) -> ExcelReadResult:
    """Read cells from a sheet."""
    if not sheet:
        # Use first sheet
        sheets = list_sheets(pkg)
        if not sheets:
            return ExcelReadResult(scope="cells", cells=[])
        sheet = sheets[0].name

    # Determine range
    if not range_ref:
        range_ref = get_used_range(pkg, sheet)
        if not range_ref:
            return ExcelReadResult(scope="cells", cells=[])

    # Parse range
    start_ref, end_ref = parse_range_ref(range_ref)

    # Get cells
    raw_cells = get_cells_in_range(pkg, sheet, start_ref, end_ref)

    # Convert to CellInfo with limit
    cells = []
    for cell_ref, value, cell_type in raw_cells[:limit]:
        cell_id = make_cell_id(sheet, cell_ref, value or "")
        cells.append(
            CellInfo(
                id=cell_id,
                sheet=sheet,
                ref=cell_ref,
                value=value,
                type=cell_type,
            )
        )

    # Also return range info
    range_id = make_range_id(sheet, range_ref)
    values_2d = _cells_to_2d_array(raw_cells[:limit], start_ref, end_ref)
    range_info = RangeInfo(
        id=range_id,
        sheet=sheet,
        ref=range_ref,
        values=values_2d,
    )

    return ExcelReadResult(
        scope="cells",
        cells=cells,
        range=range_info,
    )


def _cells_to_2d_array(
    cells: list[tuple[str, str | None, str]], start_ref: str, end_ref: str
) -> list[list[str | None]]:
    """Convert cell list to 2D array for range output."""
    from mcp_handley_lab.microsoft.excel.ops.core import (
        column_letter_to_index,
        parse_cell_ref,
    )

    start_col, start_row, _, _ = parse_cell_ref(start_ref)
    end_col, end_row, _, _ = parse_cell_ref(end_ref)

    start_col_idx = column_letter_to_index(start_col)
    end_col_idx = column_letter_to_index(end_col)

    # Normalize
    if start_col_idx > end_col_idx:
        start_col_idx, end_col_idx = end_col_idx, start_col_idx
    if start_row > end_row:
        start_row, end_row = end_row, start_row

    num_rows = end_row - start_row + 1
    num_cols = end_col_idx - start_col_idx + 1

    # Initialize empty array
    result: list[list[str | None]] = [[None] * num_cols for _ in range(num_rows)]

    # Fill in values
    for cell_ref, value, _cell_type in cells:
        col, row, _, _ = parse_cell_ref(cell_ref)
        col_idx = column_letter_to_index(col)
        row_offset = row - start_row
        col_offset = col_idx - start_col_idx
        if 0 <= row_offset < num_rows and 0 <= col_offset < num_cols:
            result[row_offset][col_offset] = value

    return result
