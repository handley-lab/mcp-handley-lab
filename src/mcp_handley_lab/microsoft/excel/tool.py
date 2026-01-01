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
    ExcelEditResult,
    ExcelReadResult,
    GridData,
    RangeMeta,
    SheetInfo,
    SparseCell,
    WorkbookMeta,
)
from mcp_handley_lab.microsoft.excel.ops.cells import (
    get_cells_in_range,
    set_cell_formula,
    set_cell_value,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    index_to_column_letter,
    parse_cell_ref,
    parse_range_ref,
)
from mcp_handley_lab.microsoft.excel.ops.sheets import (
    add_sheet,
    copy_sheet,
    delete_sheet,
    get_used_range,
    list_sheets,
    rename_sheet,
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


# =============================================================================
# Edit Operations
# =============================================================================


@mcp.tool()
def edit(
    file_path: str = Field(description="Path to .xlsx file"),
    operation: str = Field(
        description="Operation: create, set_cell, set_formula, add_sheet, rename_sheet, delete_sheet, copy_sheet"
    ),
    sheet: str = Field(
        default="",
        description="Sheet name (required for cell/sheet operations)",
    ),
    cell_ref: str = Field(
        default="",
        description="Cell reference like 'A1' (for cell operations)",
    ),
    value: str = Field(
        default="",
        description="Value to set (string, number, or JSON for arrays)",
    ),
    new_name: str = Field(
        default="",
        description="New name (for rename_sheet, copy_sheet)",
    ),
) -> dict[str, Any]:
    """Edit an Excel workbook.

    Operations:
    - create: Create new empty workbook
    - set_cell: Set cell value (auto-detects type)
    - set_formula: Set cell formula (without leading =)
    - add_sheet: Add new sheet
    - rename_sheet: Rename existing sheet
    - delete_sheet: Delete sheet
    - copy_sheet: Copy sheet to new sheet
    """
    if operation == "create":
        return _edit_create(file_path)
    elif operation == "set_cell":
        return _edit_set_cell(file_path, sheet, cell_ref, value)
    elif operation == "set_formula":
        return _edit_set_formula(file_path, sheet, cell_ref, value)
    elif operation == "add_sheet":
        return _edit_add_sheet(file_path, value or new_name)
    elif operation == "rename_sheet":
        return _edit_rename_sheet(file_path, sheet, new_name)
    elif operation == "delete_sheet":
        return _edit_delete_sheet(file_path, sheet)
    elif operation == "copy_sheet":
        return _edit_copy_sheet(file_path, sheet, new_name)
    else:
        raise ValueError(f"Unknown operation: {operation}")


def _edit_create(file_path: str) -> dict[str, Any]:
    """Create a new empty workbook."""
    pkg = ExcelPackage.new()
    pkg.save(file_path)
    return ExcelEditResult(
        success=True,
        message=f"Created workbook: {file_path}",
        affected_refs=["Sheet1"],
    ).model_dump(exclude_none=True)


def _edit_set_cell(
    file_path: str, sheet: str, cell_ref: str, value: str
) -> dict[str, Any]:
    """Set a cell's value."""
    if not sheet:
        raise ValueError("sheet is required for set_cell")
    if not cell_ref:
        raise ValueError("cell_ref is required for set_cell")

    pkg = ExcelPackage.open(file_path)

    # Auto-detect type from value string
    parsed_value: Any = value
    if value == "":
        parsed_value = None
    elif value.lower() == "true":
        parsed_value = True
    elif value.lower() == "false":
        parsed_value = False
    else:
        try:
            parsed_value = float(value) if "." in value else int(value)
        except ValueError:
            parsed_value = value  # Keep as string

    set_cell_value(pkg, sheet, cell_ref, parsed_value)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Set {cell_ref} to {repr(parsed_value)}",
        affected_refs=[cell_ref],
    ).model_dump(exclude_none=True)


def _edit_set_formula(
    file_path: str, sheet: str, cell_ref: str, formula: str
) -> dict[str, Any]:
    """Set a cell's formula."""
    if not sheet:
        raise ValueError("sheet is required for set_formula")
    if not cell_ref:
        raise ValueError("cell_ref is required for set_formula")

    pkg = ExcelPackage.open(file_path)
    set_cell_formula(pkg, sheet, cell_ref, formula)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Set {cell_ref} formula to ={formula}",
        affected_refs=[cell_ref],
    ).model_dump(exclude_none=True)


def _edit_add_sheet(file_path: str, name: str) -> dict[str, Any]:
    """Add a new sheet."""
    if not name:
        raise ValueError("value or new_name is required for add_sheet")

    pkg = ExcelPackage.open(file_path)
    add_sheet(pkg, name)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Added sheet: {name}",
        affected_refs=[name],
    ).model_dump(exclude_none=True)


def _edit_rename_sheet(file_path: str, old_name: str, new_name: str) -> dict[str, Any]:
    """Rename a sheet."""
    if not old_name:
        raise ValueError("sheet is required for rename_sheet")
    if not new_name:
        raise ValueError("new_name is required for rename_sheet")

    pkg = ExcelPackage.open(file_path)
    rename_sheet(pkg, old_name, new_name)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Renamed sheet: {old_name} -> {new_name}",
        affected_refs=[new_name],
    ).model_dump(exclude_none=True)


def _edit_delete_sheet(file_path: str, name: str) -> dict[str, Any]:
    """Delete a sheet."""
    if not name:
        raise ValueError("sheet is required for delete_sheet")

    pkg = ExcelPackage.open(file_path)
    delete_sheet(pkg, name)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Deleted sheet: {name}",
        affected_refs=[name],
    ).model_dump(exclude_none=True)


def _edit_copy_sheet(file_path: str, source: str, new_name: str) -> dict[str, Any]:
    """Copy a sheet."""
    if not source:
        raise ValueError("sheet is required for copy_sheet")
    if not new_name:
        raise ValueError("new_name is required for copy_sheet")

    pkg = ExcelPackage.open(file_path)
    copy_sheet(pkg, source, new_name)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Copied sheet: {source} -> {new_name}",
        affected_refs=[new_name],
    ).model_dump(exclude_none=True)
