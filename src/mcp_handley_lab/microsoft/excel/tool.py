"""Excel MCP tool - read and edit Excel workbooks.

Uses progressive disclosure with scopes for efficient reading.
Default representation is 'grid' with values + types arrays.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
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
    TableInfo,
    WorkbookMeta,
)
from mcp_handley_lab.microsoft.excel.ops.cells import (
    get_cells_in_range,
    set_cell_formula,
    set_cell_style,
    set_cell_value,
)
from mcp_handley_lab.microsoft.excel.ops.charts import (
    create_chart,
    delete_chart,
    list_charts,
    update_chart_data,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    index_to_column_letter,
    make_cell_id,
    make_sheet_id,
    make_table_id,
    parse_cell_ref,
    parse_range_ref,
)
from mcp_handley_lab.microsoft.excel.ops.formatting import (
    add_conditional_format,
    get_conditional_formats,
    list_styles,
)
from mcp_handley_lab.microsoft.excel.ops.pivots import (
    create_pivot,
    delete_pivot,
    list_pivots,
    refresh_pivot,
)
from mcp_handley_lab.microsoft.excel.ops.print_settings import (
    add_column_page_break,
    add_row_page_break,
    clear_page_breaks,
    clear_print_area,
    get_fit_to_page,
    get_page_margins,
    get_page_orientation,
    get_page_size,
    get_print_area,
    get_print_titles,
    get_scale,
    list_page_breaks,
    set_fit_to_page,
    set_page_margins,
    set_page_orientation,
    set_page_size,
    set_print_area,
    set_print_titles,
    set_scale,
)
from mcp_handley_lab.microsoft.excel.ops.protection import (
    get_sheet_protection,
    get_workbook_protection,
    is_sheet_protected,
    is_workbook_protected,
    lock_cells,
    protect_sheet,
    protect_workbook,
    unlock_cells,
    unprotect_sheet,
    unprotect_workbook,
)
from mcp_handley_lab.microsoft.excel.ops.ranges import (
    delete_columns,
    delete_rows,
    insert_columns,
    insert_rows,
    merge_cells,
    set_range_values,
    unmerge_cells,
)
from mcp_handley_lab.microsoft.excel.ops.sheets import (
    add_sheet,
    copy_sheet,
    delete_sheet,
    get_used_range,
    list_sheets,
    rename_sheet,
)
from mcp_handley_lab.microsoft.excel.ops.tables import (
    add_table_row,
    create_table,
    delete_table,
    delete_table_row,
    get_table_by_name,
    get_table_data,
    list_tables,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage

mcp = FastMCP(
    "Excel Tool",
    instructions="""Excel workbook (.xlsx) reading and editing tool.

Scopes:
- meta: Workbook metadata (sheet count, names)
- sheets: List of all sheets
- cells: Cell values in a range (default: grid representation)
- table: Single table data by name
- tables: List of all tables
- styles: List of cell styles
- conditional_formats: Conditional formatting rules for a sheet

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
        description="What to read: meta, sheets, cells, table, tables, styles, conditional_formats, protection, print_settings, charts",
    ),
    sheet: str = Field(
        default="",
        description="Sheet name (for cells scope, defaults to first sheet)",
    ),
    range_ref: str = Field(
        default="",
        description="Range like 'A1:C10' (for cells scope, defaults to used range)",
    ),
    table_name: str = Field(
        default="",
        description="Table name (for table scope)",
    ),
    representation: str = Field(
        default="grid",
        description="Output format: grid (2D arrays), sparse (cell list), cells (verbose)",
    ),
    include_types: bool = Field(
        default=False,
        description="Include type codes (n=number, s=string, b=bool, e=error, f=formula)",
    ),
    include_headers: bool = Field(
        default=False,
        description="Include header row in table data (for table scope)",
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
    - table: Single table data by name
    - tables: List of all tables
    - styles: List of cell styles
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
    elif scope == "table":
        result = _read_table(pkg, table_name, include_headers, limit)
    elif scope == "tables":
        result = _read_tables(pkg)
    elif scope == "styles":
        result = _read_styles(pkg)
    elif scope == "conditional_formats":
        result = _read_conditional_formats(pkg, sheet)
    elif scope == "protection":
        result = _read_protection(pkg, sheet)
    elif scope == "print_settings":
        result = _read_print_settings(pkg, sheet)
    elif scope == "charts":
        result = _read_charts(pkg, sheet)
    elif scope == "pivots":
        result = _read_pivots(pkg, sheet)
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
    # Convert to SheetInfo with content-addressed IDs
    sheet_infos = [
        SheetInfo(
            id=make_sheet_id(s.name, s.index),
            name=s.name,
            index=s.index,
        )
        for s in sheets
    ]
    return ExcelReadResult(
        scope="sheets",
        sheets=sheet_infos,
    )


def _read_table(
    pkg: ExcelPackage, table_name: str, include_headers: bool, limit: int
) -> ExcelReadResult:
    """Read a single table by name."""
    if not table_name:
        raise ValueError("table_name is required for table scope")

    info = get_table_by_name(pkg, table_name)
    data = get_table_data(pkg, table_name, include_headers=include_headers)

    # Apply limit to data rows
    if limit and len(data) > limit:
        data = data[:limit]

    # Add content-addressed ID
    info_with_id = TableInfo(
        id=make_table_id(info.name, info.ref),
        name=info.name,
        sheet=info.sheet,
        ref=info.ref,
        columns=info.columns,
        row_count=info.row_count,
    )

    return ExcelReadResult(
        scope="table",
        table=info_with_id,
        grid=GridData(values=data),
    )


def _read_tables(pkg: ExcelPackage) -> ExcelReadResult:
    """Read list of all tables."""
    tables = list_tables(pkg)
    # Add content-addressed IDs
    tables_with_ids = [
        TableInfo(
            id=make_table_id(t.name, t.ref),
            name=t.name,
            sheet=t.sheet,
            ref=t.ref,
            columns=t.columns,
            row_count=t.row_count,
        )
        for t in tables
    ]
    return ExcelReadResult(
        scope="tables",
        tables=tables_with_ids,
    )


def _read_styles(pkg: ExcelPackage) -> ExcelReadResult:
    """Read list of cell styles."""
    styles = list_styles(pkg)
    return ExcelReadResult(
        scope="styles",
        styles=styles,
    )


def _read_conditional_formats(pkg: ExcelPackage, sheet: str) -> ExcelReadResult:
    """Read conditional formatting rules for a sheet."""
    if not sheet:
        sheets = list_sheets(pkg)
        if not sheets:
            return ExcelReadResult(scope="conditional_formats", sheet=None)
        sheet = sheets[0].name

    rules = get_conditional_formats(pkg, sheet)
    return ExcelReadResult(
        scope="conditional_formats",
        sheet=sheet,
        conditional_formats=rules,
    )


def _read_protection(pkg: ExcelPackage, sheet: str) -> ExcelReadResult:
    """Read protection status for workbook and optionally a sheet."""
    workbook_protection = get_workbook_protection(pkg)
    sheet_protection = None

    if sheet:
        sheet_protection = get_sheet_protection(pkg, sheet)

    # Build protection info dict
    protection_info = {
        "workbook": {
            "protected": is_workbook_protected(pkg),
            **(workbook_protection or {}),
        }
    }

    if sheet:
        protection_info["sheet"] = {
            "name": sheet,
            "protected": is_sheet_protected(pkg, sheet),
            **(sheet_protection or {}),
        }

    return ExcelReadResult(
        scope="protection",
        sheet=sheet or None,
        protection=protection_info,
    )


def _read_print_settings(pkg: ExcelPackage, sheet: str) -> ExcelReadResult:
    """Read print settings for a sheet."""
    if not sheet:
        sheets = list_sheets(pkg)
        if not sheets:
            return ExcelReadResult(scope="print_settings", sheet=None)
        sheet = sheets[0].name

    settings: dict = {
        "print_area": get_print_area(pkg, sheet),
        "print_titles": get_print_titles(pkg, sheet),
        "page_margins": get_page_margins(pkg, sheet),
        "page_orientation": get_page_orientation(pkg, sheet),
        "page_size": get_page_size(pkg, sheet),
        "scale": get_scale(pkg, sheet),
        "fit_to_page": get_fit_to_page(pkg, sheet),
        "page_breaks": list_page_breaks(pkg, sheet),
    }

    return ExcelReadResult(
        scope="print_settings",
        sheet=sheet,
        print_settings=settings,
    )


def _read_charts(pkg: ExcelPackage, sheet: str) -> ExcelReadResult:
    """Read charts for a sheet."""
    if not sheet:
        sheets = list_sheets(pkg)
        if not sheets:
            return ExcelReadResult(scope="charts", sheet=None, charts=[])
        sheet = sheets[0].name

    chart_list = list_charts(pkg, sheet)
    return ExcelReadResult(
        scope="charts",
        sheet=sheet,
        charts=chart_list,
    )


def _read_pivots(pkg: ExcelPackage, sheet: str) -> ExcelReadResult:
    """Read pivot tables for a sheet."""
    if not sheet:
        sheets = list_sheets(pkg)
        if not sheets:
            return ExcelReadResult(scope="pivots", sheet=None, pivots=[])
        sheet = sheets[0].name

    pivot_list = list_pivots(pkg, sheet)
    return ExcelReadResult(
        scope="pivots",
        sheet=sheet,
        pivots=pivot_list,
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
        result.sparse = _build_sparse(raw_cells, include_types, sheet)
    elif representation == "cells":
        result.cells = _build_cells(raw_cells, include_types, sheet)
    else:
        raise ValueError(f"Unknown representation: {representation}")

    # Optionally add markdown view
    if include_view:
        result.view = _build_markdown_view(
            raw_cells, start_col_idx, start_row, num_rows, num_cols
        )

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
    sheet_name: str,
) -> list[SparseCell]:
    """Build sparse representation for non-empty cells only."""
    return [
        SparseCell(
            id=make_cell_id(sheet_name, cell_ref, value),
            ref=cell_ref,
            value=value,
            type=type_code if include_types else None,
        )
        for cell_ref, value, type_code, _formula in cells
    ]


def _build_cells(
    cells: list[tuple[str, Any, str | None, str | None]],
    include_types: bool,
    sheet_name: str,
) -> list[CellInfo]:
    """Build detailed cell representation."""
    return [
        CellInfo(
            id=make_cell_id(sheet_name, cell_ref, value),
            ref=cell_ref,
            value=value,
            type=type_code if include_types else None,
            formula=formula,
        )
        for cell_ref, value, type_code, formula in cells
    ]


def _build_markdown_view(
    cells: list[tuple[str, Any, str | None, str | None]],
    start_col_idx: int,
    start_row: int,
    num_rows: int,
    num_cols: int,
) -> str:
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

    return "\n".join([header_row, separator] + data_rows)


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
        description="Operation: create, set_cell, set_formula, set_range, set_style, "
        "insert_rows, delete_rows, insert_columns, delete_columns, "
        "merge_cells, unmerge_cells, add_sheet, rename_sheet, delete_sheet, copy_sheet, "
        "create_table, delete_table, add_table_row, delete_table_row, add_conditional_format, "
        "protect_sheet, unprotect_sheet, protect_workbook, unprotect_workbook, lock_cells, unlock_cells, "
        "set_print_area, clear_print_area, set_print_titles, set_page_margins, set_page_orientation, "
        "set_page_size, set_scale, set_fit_to_page, add_page_break, clear_page_breaks, "
        "create_chart, delete_chart, update_chart_data, "
        "create_pivot, delete_pivot, refresh_pivot, recalculate"
    ),
    sheet: str = Field(
        default="",
        description="Sheet name (required for cell/sheet operations)",
    ),
    cell_ref: str = Field(
        default="",
        description="Cell reference like 'A1' or range like 'A1:C3'",
    ),
    value: str = Field(
        default="",
        description="Value to set (string, number, or JSON array for add_table_row, JSON 2D array for set_range)",
    ),
    new_name: str = Field(
        default="",
        description="New name (for rename_sheet, copy_sheet, table_name for create_table)",
    ),
    table_name: str = Field(
        default="",
        description="Table name (for table operations)",
    ),
    row_index: int = Field(
        default=0,
        description="Row index for delete_table_row (0-based, relative to data rows)",
    ),
    count: int = Field(
        default=1,
        description="Count for insert/delete rows/columns",
    ),
    style_index: int = Field(
        default=-1,
        description="Style index for set_style or add_conditional_format (dxfId)",
    ),
    rule_type: str = Field(
        default="",
        description="For add_conditional_format: rule type (cellIs, colorScale, dataBar, etc.)",
    ),
    operator: str = Field(
        default="",
        description="For add_conditional_format: operator (lessThan, greaterThan, equal, between, etc.)",
    ),
    formula: str = Field(
        default="",
        description="For add_conditional_format: formula or value(s), semicolon-separated for between",
    ),
    priority: int = Field(
        default=1,
        description="For add_conditional_format: rule priority (lower = higher priority)",
    ),
    password: str = Field(
        default="",
        description="Password for protect_sheet/protect_workbook/unprotect operations",
    ),
    # Print settings parameters
    margin_left: float = Field(
        default=-1.0,
        description="Left margin in inches (for set_page_margins)",
    ),
    margin_right: float = Field(
        default=-1.0,
        description="Right margin in inches (for set_page_margins)",
    ),
    margin_top: float = Field(
        default=-1.0,
        description="Top margin in inches (for set_page_margins)",
    ),
    margin_bottom: float = Field(
        default=-1.0,
        description="Bottom margin in inches (for set_page_margins)",
    ),
    landscape: bool = Field(
        default=False,
        description="Landscape orientation (for set_page_orientation)",
    ),
    paper_size: int = Field(
        default=1,
        description="Paper size code: 1=Letter, 9=A4, 5=Legal (for set_page_size)",
    ),
    print_rows: str = Field(
        default="",
        description="Rows to repeat, e.g., '1:2' (for set_print_titles)",
    ),
    print_cols: str = Field(
        default="",
        description="Columns to repeat, e.g., 'A:B' (for set_print_titles)",
    ),
    break_type: str = Field(
        default="row",
        description="Page break type: 'row' or 'column' (for add_page_break)",
    ),
    break_position: int = Field(
        default=0,
        description="Row or column number for page break (for add_page_break)",
    ),
    scale: int = Field(
        default=100,
        description="Print scale percentage 10-400 (for set_scale)",
    ),
    fit_width: int = Field(
        default=-1,
        description="Fit to N pages wide, 0=auto (for set_fit_to_page)",
    ),
    fit_height: int = Field(
        default=-1,
        description="Fit to N pages tall, 0=auto (for set_fit_to_page)",
    ),
    # Chart parameters
    chart_type: str = Field(
        default="",
        description="Chart type: bar, column, line, pie, scatter, area (for create_chart)",
    ),
    data_range: str = Field(
        default="",
        description="Data range like 'A1:B10' (for create_chart, update_chart_data)",
    ),
    position: str = Field(
        default="",
        description="Chart position cell like 'E5' (for create_chart)",
    ),
    title: str = Field(
        default="",
        description="Chart title (for create_chart)",
    ),
    chart_id: str = Field(
        default="",
        description="Chart ID (for delete_chart, update_chart_data)",
    ),
    # Pivot table parameters
    row_fields: str = Field(
        default="",
        description="Comma-separated field names for row labels (for create_pivot)",
    ),
    col_fields: str = Field(
        default="",
        description="Comma-separated field names for column labels (for create_pivot)",
    ),
    value_fields: str = Field(
        default="",
        description="Comma-separated field names for values (for create_pivot)",
    ),
    pivot_name: str = Field(
        default="",
        description="Pivot table name (for create_pivot)",
    ),
    pivot_id: str = Field(
        default="",
        description="Pivot table ID (for delete_pivot, refresh_pivot)",
    ),
    agg_func: str = Field(
        default="sum",
        description="Aggregation function: sum, count, average, min, max (for create_pivot)",
    ),
) -> dict[str, Any]:
    """Edit an Excel workbook.

    Operations:
    - create: Create new empty workbook
    - set_cell: Set cell value (auto-detects type)
    - set_formula: Set cell formula (without leading =)
    - set_range: Set range values from JSON 2D array (cell_ref is start cell)
    - set_style: Apply style to cell or range (style_index from read scope=styles)
    - insert_rows: Insert rows at cell_ref row (count = number to insert)
    - delete_rows: Delete rows at cell_ref row (count = number to delete)
    - insert_columns: Insert columns at cell_ref column (count = number to insert)
    - delete_columns: Delete columns at cell_ref column (count = number to delete)
    - merge_cells: Merge cells in range (cell_ref = range like 'A1:C3')
    - unmerge_cells: Unmerge cells in range (cell_ref = range like 'A1:C3')
    - add_sheet: Add new sheet
    - rename_sheet: Rename existing sheet
    - delete_sheet: Delete sheet
    - copy_sheet: Copy sheet to new sheet
    - create_table: Create table from range (cell_ref = range, new_name = table name)
    - delete_table: Delete table by name (table_name)
    - add_table_row: Add row to table (table_name, value = JSON array)
    - delete_table_row: Delete row from table (table_name, row_index)
    - add_conditional_format: Add conditional formatting (sheet, cell_ref=range, rule_type, operator, formula, style_index)
    - protect_sheet: Protect sheet from modification (sheet, password=optional)
    - unprotect_sheet: Remove sheet protection (sheet, password=required if set)
    - protect_workbook: Protect workbook structure (password=optional)
    - unprotect_workbook: Remove workbook protection (password=required if set)
    - lock_cells: Lock cells in range (sheet, cell_ref=range)
    - unlock_cells: Unlock cells in range (sheet, cell_ref=range)
    - set_print_area: Set print area (sheet, cell_ref=range)
    - clear_print_area: Clear print area (sheet)
    - set_print_titles: Set repeating rows/columns (sheet, print_rows, print_cols)
    - set_page_margins: Set page margins (sheet, margin_left/right/top/bottom)
    - set_page_orientation: Set page orientation (sheet, landscape)
    - set_page_size: Set paper size (sheet, paper_size: 1=Letter, 9=A4)
    - set_scale: Set print scale percentage (sheet, scale: 10-400)
    - set_fit_to_page: Fit to pages (sheet, fit_width, fit_height; 0=auto)
    - add_page_break: Add page break (sheet, break_type='row'/'column', break_position)
    - clear_page_breaks: Clear all page breaks (sheet)
    - create_chart: Create chart (sheet, chart_type, data_range, position, title=optional)
    - delete_chart: Delete chart by ID (sheet, chart_id)
    - update_chart_data: Update chart data range (sheet, chart_id, data_range)
    - create_pivot: Create pivot table (sheet, data_range, position, row_fields, col_fields, value_fields, pivot_name=optional, agg_func=sum)
    - delete_pivot: Delete pivot table by ID (sheet, pivot_id)
    - refresh_pivot: Refresh pivot table cache (sheet, pivot_id)
    - recalculate: Recalculate all formulas using LibreOffice (populates cached values)
    """
    if operation == "create":
        return _edit_create(file_path)
    elif operation == "set_cell":
        return _edit_set_cell(file_path, sheet, cell_ref, value)
    elif operation == "set_formula":
        return _edit_set_formula(file_path, sheet, cell_ref, value)
    elif operation == "set_range":
        return _edit_set_range(file_path, sheet, cell_ref, value)
    elif operation == "set_style":
        return _edit_set_style(file_path, sheet, cell_ref, style_index)
    elif operation == "insert_rows":
        return _edit_insert_rows(file_path, sheet, cell_ref, count)
    elif operation == "delete_rows":
        return _edit_delete_rows(file_path, sheet, cell_ref, count)
    elif operation == "insert_columns":
        return _edit_insert_columns(file_path, sheet, cell_ref, count)
    elif operation == "delete_columns":
        return _edit_delete_columns(file_path, sheet, cell_ref, count)
    elif operation == "merge_cells":
        return _edit_merge_cells(file_path, sheet, cell_ref)
    elif operation == "unmerge_cells":
        return _edit_unmerge_cells(file_path, sheet, cell_ref)
    elif operation == "add_sheet":
        return _edit_add_sheet(file_path, value or new_name)
    elif operation == "rename_sheet":
        return _edit_rename_sheet(file_path, sheet, new_name)
    elif operation == "delete_sheet":
        return _edit_delete_sheet(file_path, sheet)
    elif operation == "copy_sheet":
        return _edit_copy_sheet(file_path, sheet, new_name)
    elif operation == "create_table":
        return _edit_create_table(file_path, sheet, cell_ref, new_name or table_name)
    elif operation == "delete_table":
        return _edit_delete_table(file_path, table_name)
    elif operation == "add_table_row":
        return _edit_add_table_row(file_path, table_name, value)
    elif operation == "delete_table_row":
        return _edit_delete_table_row(file_path, table_name, row_index)
    elif operation == "add_conditional_format":
        return _edit_add_conditional_format(
            file_path,
            sheet,
            cell_ref,
            rule_type,
            operator,
            formula,
            style_index,
            priority,
        )
    elif operation == "protect_sheet":
        return _edit_protect_sheet(file_path, sheet, password)
    elif operation == "unprotect_sheet":
        return _edit_unprotect_sheet(file_path, sheet, password)
    elif operation == "protect_workbook":
        return _edit_protect_workbook(file_path, password)
    elif operation == "unprotect_workbook":
        return _edit_unprotect_workbook(file_path, password)
    elif operation == "lock_cells":
        return _edit_lock_cells(file_path, sheet, cell_ref)
    elif operation == "unlock_cells":
        return _edit_unlock_cells(file_path, sheet, cell_ref)
    elif operation == "set_print_area":
        return _edit_set_print_area(file_path, sheet, cell_ref)
    elif operation == "clear_print_area":
        return _edit_clear_print_area(file_path, sheet)
    elif operation == "set_print_titles":
        return _edit_set_print_titles(file_path, sheet, print_rows, print_cols)
    elif operation == "set_page_margins":
        return _edit_set_page_margins(
            file_path, sheet, margin_left, margin_right, margin_top, margin_bottom
        )
    elif operation == "set_page_orientation":
        return _edit_set_page_orientation(file_path, sheet, landscape)
    elif operation == "set_page_size":
        return _edit_set_page_size(file_path, sheet, paper_size)
    elif operation == "set_scale":
        return _edit_set_scale(file_path, sheet, scale)
    elif operation == "set_fit_to_page":
        return _edit_set_fit_to_page(file_path, sheet, fit_width, fit_height)
    elif operation == "add_page_break":
        return _edit_add_page_break(file_path, sheet, break_type, break_position)
    elif operation == "clear_page_breaks":
        return _edit_clear_page_breaks(file_path, sheet)
    elif operation == "create_chart":
        return _edit_create_chart(
            file_path, sheet, chart_type, data_range, position, title
        )
    elif operation == "delete_chart":
        return _edit_delete_chart(file_path, sheet, chart_id)
    elif operation == "update_chart_data":
        return _edit_update_chart_data(file_path, sheet, chart_id, data_range)
    elif operation == "create_pivot":
        return _edit_create_pivot(
            file_path,
            sheet,
            data_range,
            position,
            row_fields,
            col_fields,
            value_fields,
            pivot_name,
            agg_func,
        )
    elif operation == "delete_pivot":
        return _edit_delete_pivot(file_path, sheet, pivot_id)
    elif operation == "refresh_pivot":
        return _edit_refresh_pivot(file_path, sheet, pivot_id)
    elif operation == "recalculate":
        return _edit_recalculate(file_path)
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
    pkg = ExcelPackage.open(file_path)
    set_cell_formula(pkg, sheet, cell_ref, formula)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Set {cell_ref} formula to ={formula}",
        affected_refs=[cell_ref],
    ).model_dump(exclude_none=True)


def _edit_set_style(
    file_path: str, sheet: str, cell_ref: str, style_index: int
) -> dict[str, Any]:
    """Apply a style to a cell or range."""
    pkg = ExcelPackage.open(file_path)

    # Support both single cell and range
    if ":" in cell_ref:
        # Range - apply style to all cells
        start_ref, end_ref = parse_range_ref(cell_ref)
        start_col, start_row, _, _ = parse_cell_ref(start_ref)
        end_col, end_row, _, _ = parse_cell_ref(end_ref)
        start_col_idx = column_letter_to_index(start_col)
        end_col_idx = column_letter_to_index(end_col)

        affected = []
        for row_num in range(start_row, end_row + 1):
            for col_idx in range(start_col_idx, end_col_idx + 1):
                col_letter = index_to_column_letter(col_idx)
                ref = f"{col_letter}{row_num}"
                set_cell_style(pkg, sheet, ref, style_index)
                affected.append(ref)

        pkg.save(file_path)
        return ExcelEditResult(
            success=True,
            message=f"Applied style {style_index} to {len(affected)} cells in {cell_ref}",
            affected_refs=affected,
        ).model_dump(exclude_none=True)
    else:
        # Single cell
        set_cell_style(pkg, sheet, cell_ref, style_index)
        pkg.save(file_path)
        return ExcelEditResult(
            success=True,
            message=f"Applied style {style_index} to {cell_ref}",
            affected_refs=[cell_ref],
        ).model_dump(exclude_none=True)


def _edit_add_sheet(file_path: str, name: str) -> dict[str, Any]:
    """Add a new sheet."""
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
    pkg = ExcelPackage.open(file_path)
    copy_sheet(pkg, source, new_name)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Copied sheet: {source} -> {new_name}",
        affected_refs=[new_name],
    ).model_dump(exclude_none=True)


# =============================================================================
# Range Operations
# =============================================================================


def _edit_set_range(
    file_path: str, sheet: str, start_ref: str, value: str
) -> dict[str, Any]:
    """Set range values from JSON 2D array."""
    values = json.loads(value)

    pkg = ExcelPackage.open(file_path)
    count = set_range_values(pkg, sheet, start_ref, values)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Set {count} cells starting at {start_ref}",
        affected_refs=[start_ref],
    ).model_dump(exclude_none=True)


def _edit_insert_rows(
    file_path: str, sheet: str, cell_ref: str, count: int
) -> dict[str, Any]:
    """Insert rows."""
    _, row_num, _, _ = parse_cell_ref(cell_ref)

    pkg = ExcelPackage.open(file_path)
    insert_rows(pkg, sheet, row_num, count)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Inserted {count} row(s) at row {row_num}",
        affected_refs=[f"row {row_num}"],
    ).model_dump(exclude_none=True)


def _edit_delete_rows(
    file_path: str, sheet: str, cell_ref: str, count: int
) -> dict[str, Any]:
    """Delete rows."""
    _, row_num, _, _ = parse_cell_ref(cell_ref)

    pkg = ExcelPackage.open(file_path)
    delete_rows(pkg, sheet, row_num, count)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Deleted {count} row(s) at row {row_num}",
        affected_refs=[f"row {row_num}"],
    ).model_dump(exclude_none=True)


def _edit_insert_columns(
    file_path: str, sheet: str, cell_ref: str, count: int
) -> dict[str, Any]:
    """Insert columns."""
    col, _, _, _ = parse_cell_ref(cell_ref)

    pkg = ExcelPackage.open(file_path)
    insert_columns(pkg, sheet, col, count)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Inserted {count} column(s) at column {col}",
        affected_refs=[f"column {col}"],
    ).model_dump(exclude_none=True)


def _edit_delete_columns(
    file_path: str, sheet: str, cell_ref: str, count: int
) -> dict[str, Any]:
    """Delete columns."""
    col, _, _, _ = parse_cell_ref(cell_ref)

    pkg = ExcelPackage.open(file_path)
    delete_columns(pkg, sheet, col, count)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Deleted {count} column(s) at column {col}",
        affected_refs=[f"column {col}"],
    ).model_dump(exclude_none=True)


def _edit_merge_cells(file_path: str, sheet: str, range_ref: str) -> dict[str, Any]:
    """Merge cells in a range."""
    pkg = ExcelPackage.open(file_path)
    merge_cells(pkg, sheet, range_ref)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Merged cells: {range_ref}",
        affected_refs=[range_ref],
    ).model_dump(exclude_none=True)


def _edit_unmerge_cells(file_path: str, sheet: str, range_ref: str) -> dict[str, Any]:
    """Unmerge cells in a range."""
    pkg = ExcelPackage.open(file_path)
    unmerge_cells(pkg, sheet, range_ref)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Unmerged cells: {range_ref}",
        affected_refs=[range_ref],
    ).model_dump(exclude_none=True)


# =============================================================================
# Table Operations
# =============================================================================


def _edit_create_table(
    file_path: str, sheet: str, range_ref: str, table_name: str
) -> dict[str, Any]:
    """Create a table from a range."""
    pkg = ExcelPackage.open(file_path)
    create_table(pkg, sheet, range_ref, table_name)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Created table: {table_name} in {range_ref}",
        affected_refs=[range_ref],
    ).model_dump(exclude_none=True)


def _edit_delete_table(file_path: str, table_name: str) -> dict[str, Any]:
    """Delete a table."""
    pkg = ExcelPackage.open(file_path)
    delete_table(pkg, table_name)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Deleted table: {table_name}",
        affected_refs=[table_name],
    ).model_dump(exclude_none=True)


def _edit_add_table_row(file_path: str, table_name: str, value: str) -> dict[str, Any]:
    """Add a row to a table."""
    values = json.loads(value)
    pkg = ExcelPackage.open(file_path)
    first_ref = add_table_row(pkg, table_name, values)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Added row to table {table_name} at {first_ref}",
        affected_refs=[first_ref],
    ).model_dump(exclude_none=True)


def _edit_delete_table_row(
    file_path: str, table_name: str, row_index: int
) -> dict[str, Any]:
    """Delete a row from a table."""
    pkg = ExcelPackage.open(file_path)
    delete_table_row(pkg, table_name, row_index)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Deleted row {row_index} from table {table_name}",
        affected_refs=[table_name],
    ).model_dump(exclude_none=True)


# =============================================================================
# Conditional Formatting Operations
# =============================================================================


def _edit_add_conditional_format(
    file_path: str,
    sheet: str,
    range_ref: str,
    rule_type: str,
    operator: str,
    formula: str,
    style_index: int,
    priority: int,
) -> dict[str, Any]:
    """Add a conditional formatting rule."""
    pkg = ExcelPackage.open(file_path)

    # Convert -1 style_index to None (optional)
    dxf_id = style_index if style_index >= 0 else None

    add_conditional_format(
        pkg,
        sheet,
        range_ref,
        rule_type,
        operator=operator or None,
        formula=formula or None,
        style_index=dxf_id,
        priority=priority,
    )
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Added {rule_type} conditional format to {range_ref}",
        affected_refs=[range_ref],
    ).model_dump(exclude_none=True)


# =============================================================================
# Protection Operations
# =============================================================================


def _edit_protect_sheet(file_path: str, sheet: str, password: str) -> dict[str, Any]:
    """Protect a sheet from modification."""
    pkg = ExcelPackage.open(file_path)
    protect_sheet(pkg, sheet, password=password or None)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Protected sheet: {sheet}",
        affected_refs=[sheet],
    ).model_dump(exclude_none=True)


def _edit_unprotect_sheet(file_path: str, sheet: str, password: str) -> dict[str, Any]:
    """Remove protection from a sheet."""
    pkg = ExcelPackage.open(file_path)
    unprotect_sheet(pkg, sheet, password=password or None)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Unprotected sheet: {sheet}",
        affected_refs=[sheet],
    ).model_dump(exclude_none=True)


def _edit_protect_workbook(file_path: str, password: str) -> dict[str, Any]:
    """Protect workbook structure."""
    pkg = ExcelPackage.open(file_path)
    protect_workbook(pkg, password=password or None)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message="Protected workbook structure",
        affected_refs=["workbook"],
    ).model_dump(exclude_none=True)


def _edit_unprotect_workbook(file_path: str, password: str) -> dict[str, Any]:
    """Remove workbook protection."""
    pkg = ExcelPackage.open(file_path)
    unprotect_workbook(pkg, password=password or None)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message="Unprotected workbook",
        affected_refs=["workbook"],
    ).model_dump(exclude_none=True)


def _edit_lock_cells(file_path: str, sheet: str, cell_ref: str) -> dict[str, Any]:
    """Lock cells in a range."""
    pkg = ExcelPackage.open(file_path)
    lock_cells(pkg, sheet, cell_ref)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Locked cells: {cell_ref}",
        affected_refs=[cell_ref],
    ).model_dump(exclude_none=True)


def _edit_unlock_cells(file_path: str, sheet: str, cell_ref: str) -> dict[str, Any]:
    """Unlock cells in a range."""
    pkg = ExcelPackage.open(file_path)
    unlock_cells(pkg, sheet, cell_ref)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Unlocked cells: {cell_ref}",
        affected_refs=[cell_ref],
    ).model_dump(exclude_none=True)


# =============================================================================
# Print Settings Operations
# =============================================================================


def _edit_set_print_area(file_path: str, sheet: str, range_ref: str) -> dict[str, Any]:
    """Set the print area for a sheet."""
    pkg = ExcelPackage.open(file_path)
    set_print_area(pkg, sheet, range_ref)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Set print area to {range_ref}",
        affected_refs=[range_ref],
    ).model_dump(exclude_none=True)


def _edit_clear_print_area(file_path: str, sheet: str) -> dict[str, Any]:
    """Clear the print area for a sheet."""
    pkg = ExcelPackage.open(file_path)
    clear_print_area(pkg, sheet)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message="Cleared print area",
        affected_refs=[sheet],
    ).model_dump(exclude_none=True)


def _edit_set_print_titles(
    file_path: str, sheet: str, rows: str, cols: str
) -> dict[str, Any]:
    """Set print titles (repeating rows/columns)."""
    pkg = ExcelPackage.open(file_path)
    set_print_titles(pkg, sheet, rows=rows or None, cols=cols or None)
    pkg.save(file_path)

    parts = []
    if rows:
        parts.append(f"rows {rows}")
    if cols:
        parts.append(f"columns {cols}")

    return ExcelEditResult(
        success=True,
        message=f"Set print titles: {', '.join(parts) or 'cleared'}",
        affected_refs=[sheet],
    ).model_dump(exclude_none=True)


def _edit_set_page_margins(
    file_path: str,
    sheet: str,
    left: float,
    right: float,
    top: float,
    bottom: float,
) -> dict[str, Any]:
    """Set page margins for a sheet."""
    pkg = ExcelPackage.open(file_path)
    set_page_margins(
        pkg,
        sheet,
        left=left if left >= 0 else None,
        right=right if right >= 0 else None,
        top=top if top >= 0 else None,
        bottom=bottom if bottom >= 0 else None,
    )
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message="Updated page margins",
        affected_refs=[sheet],
    ).model_dump(exclude_none=True)


def _edit_set_page_orientation(
    file_path: str, sheet: str, landscape: bool
) -> dict[str, Any]:
    """Set page orientation for a sheet."""
    pkg = ExcelPackage.open(file_path)
    set_page_orientation(pkg, sheet, landscape=landscape)
    pkg.save(file_path)

    orientation = "landscape" if landscape else "portrait"
    return ExcelEditResult(
        success=True,
        message=f"Set page orientation to {orientation}",
        affected_refs=[sheet],
    ).model_dump(exclude_none=True)


def _edit_set_page_size(file_path: str, sheet: str, paper_size: int) -> dict[str, Any]:
    """Set paper size for a sheet."""
    pkg = ExcelPackage.open(file_path)
    set_page_size(pkg, sheet, paper_size)
    pkg.save(file_path)

    size_names = {1: "Letter", 5: "Legal", 9: "A4", 11: "A5"}
    size_name = size_names.get(paper_size, f"code {paper_size}")

    return ExcelEditResult(
        success=True,
        message=f"Set paper size to {size_name}",
        affected_refs=[sheet],
    ).model_dump(exclude_none=True)


def _edit_add_page_break(
    file_path: str, sheet: str, break_type: str, position: int
) -> dict[str, Any]:
    """Add a page break."""
    pkg = ExcelPackage.open(file_path)

    if break_type == "row":
        add_row_page_break(pkg, sheet, position)
        msg = f"Added row page break before row {position}"
    else:
        add_column_page_break(pkg, sheet, position)
        msg = f"Added column page break before column {position}"

    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=msg,
        affected_refs=[sheet],
    ).model_dump(exclude_none=True)


def _edit_clear_page_breaks(file_path: str, sheet: str) -> dict[str, Any]:
    """Clear all page breaks for a sheet."""
    pkg = ExcelPackage.open(file_path)
    clear_page_breaks(pkg, sheet)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message="Cleared all page breaks",
        affected_refs=[sheet],
    ).model_dump(exclude_none=True)


def _edit_set_scale(file_path: str, sheet: str, scale_value: int) -> dict[str, Any]:
    """Set print scale percentage."""
    pkg = ExcelPackage.open(file_path)
    set_scale(pkg, sheet, scale_value)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Set print scale to {scale_value}%",
        affected_refs=[sheet],
    ).model_dump(exclude_none=True)


def _edit_set_fit_to_page(
    file_path: str, sheet: str, width: int, height: int
) -> dict[str, Any]:
    """Set fit-to-page printing."""
    pkg = ExcelPackage.open(file_path)
    set_fit_to_page(
        pkg,
        sheet,
        width=width if width >= 0 else None,
        height=height if height >= 0 else None,
    )
    pkg.save(file_path)

    msg_parts = []
    if width >= 0:
        msg_parts.append(f"{width} page(s) wide" if width > 0 else "auto width")
    if height >= 0:
        msg_parts.append(f"{height} page(s) tall" if height > 0 else "auto height")

    return ExcelEditResult(
        success=True,
        message=f"Set fit-to-page: {', '.join(msg_parts) or 'default'}",
        affected_refs=[sheet],
    ).model_dump(exclude_none=True)


# =============================================================================
# Chart Operations
# =============================================================================


def _edit_create_chart(
    file_path: str,
    sheet: str,
    chart_type: str,
    data_range: str,
    position: str,
    title: str,
) -> dict[str, Any]:
    """Create a chart on the sheet."""
    pkg = ExcelPackage.open(file_path)
    chart_info = create_chart(
        pkg,
        sheet,
        chart_type,
        data_range,
        position,
        title=title if title else None,
    )
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Created {chart_type} chart at {position}",
        affected_refs=[chart_info.id or position],
    ).model_dump(exclude_none=True)


def _edit_delete_chart(file_path: str, sheet: str, chart_id: str) -> dict[str, Any]:
    """Delete a chart by ID."""
    pkg = ExcelPackage.open(file_path)
    delete_chart(pkg, sheet, chart_id)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Deleted chart: {chart_id}",
        affected_refs=[chart_id],
    ).model_dump(exclude_none=True)


def _edit_update_chart_data(
    file_path: str, sheet: str, chart_id: str, data_range: str
) -> dict[str, Any]:
    """Update a chart's data range."""
    pkg = ExcelPackage.open(file_path)
    update_chart_data(pkg, sheet, chart_id, data_range)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Updated chart {chart_id} data range to {data_range}",
        affected_refs=[chart_id],
    ).model_dump(exclude_none=True)


# =============================================================================
# Pivot Table Operations
# =============================================================================


def _edit_create_pivot(
    file_path: str,
    sheet: str,
    data_range: str,
    position: str,
    row_fields: str,
    col_fields: str,
    value_fields: str,
    pivot_name: str,
    agg_func: str,
) -> dict[str, Any]:
    """Create a pivot table."""
    # Parse comma-separated field names
    rows = [f.strip() for f in row_fields.split(",") if f.strip()] if row_fields else []
    cols = [f.strip() for f in col_fields.split(",") if f.strip()] if col_fields else []
    values = [f.strip() for f in value_fields.split(",") if f.strip()]

    pkg = ExcelPackage.open(file_path)
    pivot_info = create_pivot(
        pkg,
        sheet,
        data_range,
        position,
        rows,
        cols,
        values,
        name=pivot_name if pivot_name else None,
        agg_func=agg_func,
    )
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Created pivot table '{pivot_info.name}' at {position}",
        affected_refs=[pivot_info.id or position],
    ).model_dump(exclude_none=True)


def _edit_delete_pivot(file_path: str, sheet: str, pivot_id: str) -> dict[str, Any]:
    """Delete a pivot table by ID."""
    pkg = ExcelPackage.open(file_path)
    delete_pivot(pkg, sheet, pivot_id)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Deleted pivot table: {pivot_id}",
        affected_refs=[pivot_id],
    ).model_dump(exclude_none=True)


def _edit_refresh_pivot(file_path: str, sheet: str, pivot_id: str) -> dict[str, Any]:
    """Refresh a pivot table's cache."""
    pkg = ExcelPackage.open(file_path)
    refresh_pivot(pkg, sheet, pivot_id)
    pkg.save(file_path)

    return ExcelEditResult(
        success=True,
        message=f"Refreshed pivot table: {pivot_id}",
        affected_refs=[pivot_id],
    ).model_dump(exclude_none=True)


def _edit_recalculate(file_path: str) -> dict[str, Any]:
    """Recalculate all formulas using LibreOffice headless.

    This opens the file in LibreOffice, which triggers formula calculation,
    then saves it back. The cached values in <v> elements are then populated.
    """
    file_path = str(Path(file_path).resolve())
    file_name = Path(file_path).name

    with tempfile.TemporaryDirectory() as tmpdir:
        # LibreOffice can't overwrite input file, so use separate in/out dirs
        input_dir = Path(tmpdir) / "in"
        output_dir = Path(tmpdir) / "out"
        input_dir.mkdir()
        output_dir.mkdir()

        # Copy input to temp location
        input_copy = input_dir / file_name
        shutil.copy2(file_path, input_copy)

        # LibreOffice converts and outputs to a directory
        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--calc",
                "--convert-to",
                "xlsx",
                "--outdir",
                str(output_dir),
                str(input_copy),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise RuntimeError(f"LibreOffice failed: {result.stderr or result.stdout}")

        # Find output file (LO may change extension or name slightly)
        output_file = output_dir / file_name
        if not output_file.exists():
            # Fallback: find any .xlsx file in output dir
            xlsx_files = list(output_dir.glob("*.xlsx"))
            if len(xlsx_files) == 1:
                output_file = xlsx_files[0]
            elif not xlsx_files:
                raise RuntimeError(
                    f"LibreOffice did not produce any .xlsx file in {output_dir}"
                )
            else:
                raise RuntimeError(
                    f"LibreOffice produced multiple files: {[f.name for f in xlsx_files]}"
                )

        # Replace original with recalculated version
        shutil.move(str(output_file), file_path)

    return ExcelEditResult(
        success=True,
        message="Recalculated all formulas",
        affected_refs=["*"],
    ).model_dump(exclude_none=True)
