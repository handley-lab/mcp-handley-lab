"""Core Excel functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

from __future__ import annotations

import json
from typing import Any

from mcp_handley_lab.microsoft.common.batch import (
    convert_custom_property_value,
    require,
    require_any,
    run_batch_edit,
)
from mcp_handley_lab.microsoft.common.properties import (
    delete_custom_property,
    get_core_properties,
    get_custom_properties,
    set_core_properties,
    set_custom_property,
)
from mcp_handley_lab.microsoft.excel.models import (
    CellInfo,
    CustomPropertyInfo,
    DocumentProperties,
    ExcelEditResult,
    ExcelOpResult,
    ExcelReadResult,
    GridData,
    RangeMeta,
    SheetInfo,
    SparseCell,
    TableInfo,
    WorkbookMeta,
)
from mcp_handley_lab.microsoft.excel.ops.cells import (
    find_cells as find_cells_op,
)
from mcp_handley_lab.microsoft.excel.ops.cells import (
    find_replace as find_replace_cells,
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
from mcp_handley_lab.microsoft.excel.ops.comments import (
    list_comments,
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
from mcp_handley_lab.microsoft.excel.ops.filtering import (
    apply_filter,
    clear_autofilter,
    clear_filter,
    get_autofilter,
    set_autofilter,
    sort_range,
)
from mcp_handley_lab.microsoft.excel.ops.formatting import (
    add_conditional_format,
    get_conditional_formats,
    list_styles,
)
from mcp_handley_lab.microsoft.excel.ops.names import (
    create_name,
    delete_name,
    list_names,
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
from mcp_handley_lab.microsoft.excel.ops.validation import (
    add_validation,
    list_validations,
    remove_validation,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def read(
    file_path: str,
    scope: str = "sheets",
    sheet: str = "",
    range_ref: str = "",
    table_name: str = "",
    representation: str = "grid",
    include_types: bool = False,
    include_headers: bool = False,
    view: bool = False,
    limit: int = 1000,
) -> dict[str, Any]:
    """Read data from an Excel workbook.

    Uses progressive disclosure with scopes:
    - meta: Quick workbook overview
    - sheets: List of sheets for subsequent queries
    - cells: Cell values with grid (default), sparse, or detailed representation
    - table: Single table data by name
    - tables: List of all tables
    - styles: List of cell styles
    - conditional_formats: Conditional formatting rules
    - protection: Protection status
    - print_settings: Print configuration
    - charts: Chart list for a sheet
    - pivots: Pivot table list for a sheet
    - comments: Cell comments/notes for a sheet

    Args:
        file_path: Path to .xlsx file.
        scope: What to read: meta, sheets, cells, table, tables, styles,
            conditional_formats, protection, print_settings, charts, pivots, comments.
        sheet: Sheet name (for cells scope, defaults to first sheet).
        range_ref: Range like 'A1:C10' (for cells scope, defaults to used range).
        table_name: Table name (for table scope).
        representation: Output format: grid (2D arrays), sparse (cell list), cells (verbose).
        include_types: Include type codes (n=number, s=string, b=bool, e=error, f=formula).
        include_headers: Include header row in table data (for table scope).
        view: Include markdown table view for readability.
        limit: Maximum cells to return.

    Returns:
        Dict with scope-specific data.
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
    elif scope == "properties":
        result = _read_properties(pkg)
    elif scope == "names":
        result = _read_names(pkg)
    elif scope == "validations":
        result = _read_validations(pkg, sheet)
    elif scope == "autofilter":
        result = _read_autofilter(pkg, sheet)
    elif scope == "comments":
        result = _read_comments(pkg, sheet)
    else:
        raise ValueError(f"Unknown scope: {scope}")

    return result.model_dump(exclude_none=True)


def find_cells(
    file_path: str,
    query: str,
    sheet: str = "",
    match_case: bool = False,
    exact: bool = False,
) -> list[dict[str, Any]]:
    """Find cells containing specific text.

    Searches cell values (not formulas) across sheets.

    Args:
        file_path: Path to .xlsx file.
        query: Text to search for.
        sheet: Optional sheet to limit search. If empty, searches all sheets.
        match_case: Case-sensitive search (default False).
        exact: Exact match only (default False for substring matching).

    Returns:
        List of dicts with 'sheet', 'ref', and 'value' for each match.
    """
    pkg = ExcelPackage.open(file_path)
    return find_cells_op(pkg, query, sheet or None, match_case, exact)


def edit(
    file_path: str,
    ops: str,
    mode: str = "atomic",
) -> dict[str, Any]:
    """Edit an Excel workbook using batch operations. Creates a new file if file_path doesn't exist.

    Batch operations allow multiple edits in a single call with $prev chaining.
    Use read() first to discover sheets, cells, and tables.

    Args:
        file_path: Path to .xlsx file (created if it doesn't exist).
        ops: JSON array of operation objects, e.g.:
            [{"op": "set_cell", "sheet": "Sheet1", "cell_ref": "A1", "value": "Hello"},
             {"op": "set_style", "sheet": "Sheet1", "cell_ref": "$prev[0]", "style_index": 1}]
        mode: 'atomic' (all-or-nothing) or 'partial' (save successful ops).

    Available operations:
        - set_cell, set_formula, set_range, set_style
        - insert_rows, delete_rows, insert_columns, delete_columns
        - merge_cells, unmerge_cells
        - add_sheet, rename_sheet, delete_sheet, copy_sheet
        - create_table, delete_table, add_table_row, delete_table_row
        - add_conditional_format
        - protect_sheet, unprotect_sheet, protect_workbook, unprotect_workbook
        - lock_cells, unlock_cells
        - set_print_area, clear_print_area, set_print_titles
        - set_page_margins, set_page_orientation, set_page_size
        - set_scale, set_fit_to_page, add_page_break, clear_page_breaks
        - create_chart, delete_chart, update_chart_data
        - create_pivot, delete_pivot, refresh_pivot
        - set_meta, set_custom_property, delete_custom_property
        - create_name, delete_name (named ranges)
        - add_validation, remove_validation (data validation)
        - set_autofilter, clear_autofilter, apply_filter, clear_filter, sort_range
        - find_replace (text search/replace in cell values, skips formula cells)

    $prev chaining:
        Reference results of previous operations using $prev[N] where N is the
        operation index (0-based). Works for: cell_ref, range_ref, sheet,
        table_name, chart_id, pivot_id.

    Returns:
        Dict with success status, counts, and per-operation results.
    """
    return run_batch_edit(
        file_path=file_path,
        ops=ops,
        mode=mode,
        open_pkg=ExcelPackage.open,
        new_pkg=ExcelPackage.new,
        apply_op=_apply_op,
        make_op_result=ExcelOpResult,
        make_edit_result=ExcelEditResult,
        prev_fields=_PREV_FIELDS,
        text_fields=_TEXT_FIELDS,
        excluded_ops=_EXCLUDED_OPS,
    )


# =============================================================================
# Read Helpers
# =============================================================================


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


def _get_document_properties(pkg: ExcelPackage) -> DocumentProperties:
    """Get document properties from core.xml and custom.xml."""
    core = get_core_properties(pkg)
    custom = get_custom_properties(pkg)

    return DocumentProperties(
        title=core["title"],
        author=core["author"],
        subject=core["subject"],
        keywords=core["keywords"],
        category=core["category"],
        comments=core["comments"],
        created=core["created"],
        modified=core["modified"],
        revision=core["revision"],
        last_modified_by=core["last_modified_by"],
        custom_properties=[
            CustomPropertyInfo(name=p["name"], value=p["value"], type=p["type"])
            for p in custom
        ],
    )


def _read_properties(pkg: ExcelPackage) -> ExcelReadResult:
    """Read document properties."""
    return ExcelReadResult(
        scope="properties",
        properties=_get_document_properties(pkg),
    )


def _read_names(pkg: ExcelPackage) -> ExcelReadResult:
    """Read all defined names (named ranges)."""
    names = list_names(pkg)
    return ExcelReadResult(
        scope="names",
        names=names,
    )


def _read_validations(pkg: ExcelPackage, sheet: str) -> ExcelReadResult:
    """Read data validation rules for a sheet."""
    if not sheet:
        sheets = list_sheets(pkg)
        if not sheets:
            return ExcelReadResult(scope="validations", sheet=None, validations=[])
        sheet = sheets[0].name

    validations = list_validations(pkg, sheet)
    return ExcelReadResult(
        scope="validations",
        sheet=sheet,
        validations=validations,
    )


def _read_autofilter(pkg: ExcelPackage, sheet: str) -> ExcelReadResult:
    """Read AutoFilter info for a sheet."""
    if not sheet:
        sheets = list_sheets(pkg)
        if not sheets:
            return ExcelReadResult(scope="autofilter", sheet=None, autofilter=None)
        sheet = sheets[0].name

    autofilter_info = get_autofilter(pkg, sheet)
    return ExcelReadResult(
        scope="autofilter",
        sheet=sheet,
        autofilter=autofilter_info,
    )


def _read_comments(pkg: ExcelPackage, sheet: str) -> ExcelReadResult:
    """Read comments (notes) for a sheet."""
    if not sheet:
        sheets = list_sheets(pkg)
        if not sheets:
            return ExcelReadResult(scope="comments", sheet=None, comments=[])
        sheet = sheets[0].name

    comments = list_comments(pkg, sheet)
    return ExcelReadResult(
        scope="comments",
        sheet=sheet,
        comments=comments,
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
# Edit Operations - Batch API
# =============================================================================

_EXCLUDED_OPS = {"recalculate"}

_PREV_FIELDS = {
    "cell_ref",
    "range_ref",
    "sheet",
    "table_name",
    "chart_id",
    "pivot_id",
}

_TEXT_FIELDS: dict[str, set[str]] = {
    "set_cell": {"value"},
    "add_table_row": set(),
}


def _apply_op(pkg: ExcelPackage, op: str, params: dict[str, Any]) -> dict[str, Any]:
    """Apply a single operation to an open package.

    Returns dict with 'message' and optionally 'element_id' for $prev chaining.
    """
    if op == "set_cell":
        return _op_set_cell(pkg, params)
    elif op == "set_formula":
        return _op_set_formula(pkg, params)
    elif op == "set_range":
        return _op_set_range(pkg, params)
    elif op == "set_style":
        return _op_set_style(pkg, params)
    elif op == "insert_rows":
        return _op_insert_rows(pkg, params)
    elif op == "delete_rows":
        return _op_delete_rows(pkg, params)
    elif op == "insert_columns":
        return _op_insert_columns(pkg, params)
    elif op == "delete_columns":
        return _op_delete_columns(pkg, params)
    elif op == "merge_cells":
        return _op_merge_cells(pkg, params)
    elif op == "unmerge_cells":
        return _op_unmerge_cells(pkg, params)
    elif op == "add_sheet":
        return _op_add_sheet(pkg, params)
    elif op == "rename_sheet":
        return _op_rename_sheet(pkg, params)
    elif op == "delete_sheet":
        return _op_delete_sheet(pkg, params)
    elif op == "copy_sheet":
        return _op_copy_sheet(pkg, params)
    elif op == "create_table":
        return _op_create_table(pkg, params)
    elif op == "delete_table":
        return _op_delete_table(pkg, params)
    elif op == "add_table_row":
        return _op_add_table_row(pkg, params)
    elif op == "delete_table_row":
        return _op_delete_table_row(pkg, params)
    elif op == "add_conditional_format":
        return _op_add_conditional_format(pkg, params)
    elif op == "protect_sheet":
        return _op_protect_sheet(pkg, params)
    elif op == "unprotect_sheet":
        return _op_unprotect_sheet(pkg, params)
    elif op == "protect_workbook":
        return _op_protect_workbook(pkg, params)
    elif op == "unprotect_workbook":
        return _op_unprotect_workbook(pkg, params)
    elif op == "lock_cells":
        return _op_lock_cells(pkg, params)
    elif op == "unlock_cells":
        return _op_unlock_cells(pkg, params)
    elif op == "set_print_area":
        return _op_set_print_area(pkg, params)
    elif op == "clear_print_area":
        return _op_clear_print_area(pkg, params)
    elif op == "set_print_titles":
        return _op_set_print_titles(pkg, params)
    elif op == "set_page_margins":
        return _op_set_page_margins(pkg, params)
    elif op == "set_page_orientation":
        return _op_set_page_orientation(pkg, params)
    elif op == "set_page_size":
        return _op_set_page_size(pkg, params)
    elif op == "set_scale":
        return _op_set_scale(pkg, params)
    elif op == "set_fit_to_page":
        return _op_set_fit_to_page(pkg, params)
    elif op == "add_page_break":
        return _op_add_page_break(pkg, params)
    elif op == "clear_page_breaks":
        return _op_clear_page_breaks(pkg, params)
    elif op == "create_chart":
        return _op_create_chart(pkg, params)
    elif op == "delete_chart":
        return _op_delete_chart(pkg, params)
    elif op == "update_chart_data":
        return _op_update_chart_data(pkg, params)
    elif op == "create_pivot":
        return _op_create_pivot(pkg, params)
    elif op == "delete_pivot":
        return _op_delete_pivot(pkg, params)
    elif op == "refresh_pivot":
        return _op_refresh_pivot(pkg, params)
    elif op == "set_property":
        return _op_set_property(pkg, params)
    elif op == "set_custom_property":
        return _op_set_custom_property(pkg, params)
    elif op == "delete_custom_property":
        return _op_delete_custom_property(pkg, params)
    # Named ranges
    elif op == "create_name":
        return _op_create_name(pkg, params)
    elif op == "delete_name":
        return _op_delete_name(pkg, params)
    # Data validation
    elif op == "add_validation":
        return _op_add_validation(pkg, params)
    elif op == "remove_validation":
        return _op_remove_validation(pkg, params)
    # AutoFilter
    elif op == "set_autofilter":
        return _op_set_autofilter(pkg, params)
    elif op == "clear_autofilter":
        return _op_clear_autofilter(pkg, params)
    elif op == "apply_filter":
        return _op_apply_filter(pkg, params)
    elif op == "clear_filter":
        return _op_clear_filter(pkg, params)
    elif op == "sort_range":
        return _op_sort_range(pkg, params)
    elif op == "find_replace":
        return _op_find_replace(pkg, params)
    else:
        raise ValueError(f"Unknown operation: {op}")


# =============================================================================
# Individual Operation Handlers
# =============================================================================


def _op_set_cell(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Set a cell's value."""
    sheet = require(params, "sheet", "set_cell")
    cell_ref = require(params, "cell_ref", "set_cell")
    value = require_any(params, "value", "set_cell")

    # Auto-detect type from value string
    parsed_value: Any = value
    if value == "":
        parsed_value = None
    elif isinstance(value, str):
        if value.lower() == "true":
            parsed_value = True
        elif value.lower() == "false":
            parsed_value = False
        else:
            try:
                parsed_value = float(value) if "." in value else int(value)
            except ValueError:
                parsed_value = value

    set_cell_value(pkg, sheet, cell_ref, parsed_value)
    return {
        "message": f"Set {cell_ref} to {repr(parsed_value)}",
        "element_id": cell_ref,
    }


def _op_set_formula(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Set a cell's formula."""
    sheet = require(params, "sheet", "set_formula")
    cell_ref = require(params, "cell_ref", "set_formula")
    formula = require(params, "formula", "set_formula")

    set_cell_formula(pkg, sheet, cell_ref, formula)
    return {"message": f"Set {cell_ref} formula to ={formula}", "element_id": cell_ref}


def _op_set_range(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Set range values from JSON 2D array."""
    sheet = require(params, "sheet", "set_range")
    cell_ref = require(params, "cell_ref", "set_range")
    value = require(params, "value", "set_range")

    values = json.loads(value) if isinstance(value, str) else value
    set_range_values(pkg, sheet, cell_ref, values)
    return {"message": f"Set range starting at {cell_ref}", "element_id": cell_ref}


def _op_set_style(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Apply a style to a cell or range."""
    sheet = require(params, "sheet", "set_style")
    cell_ref = require(params, "cell_ref", "set_style")
    style_index = params.get("style_index", -1)

    if ":" in cell_ref:
        # Range - apply style to all cells
        start_ref, end_ref = parse_range_ref(cell_ref)
        start_col, start_row, _, _ = parse_cell_ref(start_ref)
        end_col, end_row, _, _ = parse_cell_ref(end_ref)
        start_col_idx = column_letter_to_index(start_col)
        end_col_idx = column_letter_to_index(end_col)

        for row_num in range(start_row, end_row + 1):
            for col_idx in range(start_col_idx, end_col_idx + 1):
                col_letter = index_to_column_letter(col_idx)
                ref = f"{col_letter}{row_num}"
                set_cell_style(pkg, sheet, ref, style_index)

        return {
            "message": f"Applied style {style_index} to range {cell_ref}",
            "element_id": cell_ref,
        }
    else:
        set_cell_style(pkg, sheet, cell_ref, style_index)
        return {
            "message": f"Applied style {style_index} to {cell_ref}",
            "element_id": cell_ref,
        }


def _op_insert_rows(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Insert rows."""
    sheet = require(params, "sheet", "insert_rows")
    cell_ref = require(params, "cell_ref", "insert_rows")
    count = params.get("count", 1)

    _, row, _, _ = parse_cell_ref(cell_ref)
    insert_rows(pkg, sheet, row, count)
    return {"message": f"Inserted {count} row(s) at row {row}", "element_id": ""}


def _op_delete_rows(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Delete rows."""
    sheet = require(params, "sheet", "delete_rows")
    cell_ref = require(params, "cell_ref", "delete_rows")
    count = params.get("count", 1)

    _, row, _, _ = parse_cell_ref(cell_ref)
    delete_rows(pkg, sheet, row, count)
    return {
        "message": f"Deleted {count} row(s) starting at row {row}",
        "element_id": "",
    }


def _op_insert_columns(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Insert columns."""
    sheet = require(params, "sheet", "insert_columns")
    cell_ref = require(params, "cell_ref", "insert_columns")
    count = params.get("count", 1)

    col, _, _, _ = parse_cell_ref(cell_ref)
    col_idx = column_letter_to_index(col)
    insert_columns(pkg, sheet, col_idx, count)
    return {"message": f"Inserted {count} column(s) at column {col}", "element_id": ""}


def _op_delete_columns(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Delete columns."""
    sheet = require(params, "sheet", "delete_columns")
    cell_ref = require(params, "cell_ref", "delete_columns")
    count = params.get("count", 1)

    col, _, _, _ = parse_cell_ref(cell_ref)
    col_idx = column_letter_to_index(col)
    delete_columns(pkg, sheet, col_idx, count)
    return {
        "message": f"Deleted {count} column(s) starting at column {col}",
        "element_id": "",
    }


def _op_merge_cells(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Merge cells in range."""
    sheet = require(params, "sheet", "merge_cells")
    cell_ref = require(params, "cell_ref", "merge_cells")

    merge_cells(pkg, sheet, cell_ref)
    return {"message": f"Merged cells {cell_ref}", "element_id": cell_ref}


def _op_unmerge_cells(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Unmerge cells in range."""
    sheet = require(params, "sheet", "unmerge_cells")
    cell_ref = require(params, "cell_ref", "unmerge_cells")

    unmerge_cells(pkg, sheet, cell_ref)
    return {"message": f"Unmerged cells {cell_ref}", "element_id": cell_ref}


def _op_add_sheet(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add new sheet."""
    name = params.get("new_name", "") or params.get("name", "")
    if not name:
        raise ValueError("new_name (or name) required for add_sheet")

    add_sheet(pkg, name)
    return {"message": f"Added sheet '{name}'", "element_id": name}


def _op_rename_sheet(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Rename existing sheet."""
    old_name = require(params, "sheet", "rename_sheet")
    new_name = require(params, "new_name", "rename_sheet")

    rename_sheet(pkg, old_name, new_name)
    return {
        "message": f"Renamed sheet '{old_name}' to '{new_name}'",
        "element_id": new_name,
    }


def _op_delete_sheet(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Delete sheet."""
    name = require(params, "sheet", "delete_sheet")

    delete_sheet(pkg, name)
    return {"message": f"Deleted sheet '{name}'", "element_id": ""}


def _op_copy_sheet(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Copy sheet to new sheet."""
    source = require(params, "sheet", "copy_sheet")
    new_name = require(params, "new_name", "copy_sheet")

    copy_sheet(pkg, source, new_name)
    return {
        "message": f"Copied sheet '{source}' to '{new_name}'",
        "element_id": new_name,
    }


def _op_create_table(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Create table from range."""
    sheet = require(params, "sheet", "create_table")
    cell_ref = require(params, "cell_ref", "create_table")
    table_name = params.get("table_name", "") or params.get("new_name", "")
    if not table_name:
        raise ValueError("table_name (or new_name) required for create_table")

    create_table(pkg, sheet, cell_ref, table_name)
    return {
        "message": f"Created table '{table_name}' from range {cell_ref}",
        "element_id": table_name,
    }


def _op_delete_table(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Delete table by name."""
    table_name = require(params, "table_name", "delete_table")

    delete_table(pkg, table_name)
    return {"message": f"Deleted table '{table_name}'", "element_id": ""}


def _op_add_table_row(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add row to table."""
    table_name = require(params, "table_name", "add_table_row")
    value = require_any(params, "value", "add_table_row")

    row_data = json.loads(value) if isinstance(value, str) else value
    add_table_row(pkg, table_name, row_data)
    return {"message": f"Added row to table '{table_name}'", "element_id": table_name}


def _op_delete_table_row(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Delete row from table."""
    table_name = require(params, "table_name", "delete_table_row")
    row_index = params.get("row", 0)

    delete_table_row(pkg, table_name, row_index)
    return {
        "message": f"Deleted row {row_index} from table '{table_name}'",
        "element_id": table_name,
    }


def _op_add_conditional_format(
    pkg: ExcelPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Add conditional formatting."""
    sheet = require(params, "sheet", "add_conditional_format")
    cell_ref = require(params, "cell_ref", "add_conditional_format")
    rule_type = require(params, "rule_type", "add_conditional_format")
    operator = params.get("operator", "")
    formula = params.get("formula", "")
    style_index = params.get("style_index", -1)
    priority = params.get("priority", 1)

    add_conditional_format(
        pkg, sheet, cell_ref, rule_type, operator, formula, style_index, priority
    )
    return {
        "message": f"Added conditional format to {cell_ref}",
        "element_id": cell_ref,
    }


def _op_protect_sheet(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Protect sheet."""
    sheet = require(params, "sheet", "protect_sheet")
    password = params.get("password", "")

    protect_sheet(pkg, sheet, password if password else None)
    return {"message": f"Protected sheet '{sheet}'", "element_id": ""}


def _op_unprotect_sheet(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Unprotect sheet."""
    sheet = require(params, "sheet", "unprotect_sheet")
    password = params.get("password", "")

    unprotect_sheet(pkg, sheet, password if password else None)
    return {"message": f"Unprotected sheet '{sheet}'", "element_id": ""}


def _op_protect_workbook(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Protect workbook."""
    password = params.get("password", "")

    protect_workbook(pkg, password if password else None)
    return {"message": "Protected workbook", "element_id": ""}


def _op_unprotect_workbook(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Unprotect workbook."""
    password = params.get("password", "")

    unprotect_workbook(pkg, password if password else None)
    return {"message": "Unprotected workbook", "element_id": ""}


def _op_lock_cells(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Lock cells in range."""
    sheet = require(params, "sheet", "lock_cells")
    cell_ref = require(params, "cell_ref", "lock_cells")

    lock_cells(pkg, sheet, cell_ref)
    return {"message": f"Locked cells {cell_ref}", "element_id": cell_ref}


def _op_unlock_cells(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Unlock cells in range."""
    sheet = require(params, "sheet", "unlock_cells")
    cell_ref = require(params, "cell_ref", "unlock_cells")

    unlock_cells(pkg, sheet, cell_ref)
    return {"message": f"Unlocked cells {cell_ref}", "element_id": cell_ref}


def _op_set_print_area(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Set print area."""
    sheet = require(params, "sheet", "set_print_area")
    cell_ref = require(params, "cell_ref", "set_print_area")

    set_print_area(pkg, sheet, cell_ref)
    return {"message": f"Set print area to {cell_ref}", "element_id": ""}


def _op_clear_print_area(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Clear print area."""
    sheet = require(params, "sheet", "clear_print_area")

    clear_print_area(pkg, sheet)
    return {"message": f"Cleared print area for sheet '{sheet}'", "element_id": ""}


def _op_set_print_titles(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Set print titles."""
    sheet = require(params, "sheet", "set_print_titles")
    print_rows = params.get("print_rows", "")
    print_cols = params.get("print_cols", "")

    set_print_titles(pkg, sheet, print_rows or None, print_cols or None)
    return {"message": f"Set print titles for sheet '{sheet}'", "element_id": ""}


def _op_set_page_margins(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Set page margins."""
    sheet = require(params, "sheet", "set_page_margins")
    left = params.get("margin_left", -1.0)
    right = params.get("margin_right", -1.0)
    top = params.get("margin_top", -1.0)
    bottom = params.get("margin_bottom", -1.0)

    set_page_margins(
        pkg,
        sheet,
        left if left >= 0 else None,
        right if right >= 0 else None,
        top if top >= 0 else None,
        bottom if bottom >= 0 else None,
    )
    return {"message": f"Set page margins for sheet '{sheet}'", "element_id": ""}


def _op_set_page_orientation(
    pkg: ExcelPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Set page orientation."""
    sheet = require(params, "sheet", "set_page_orientation")
    landscape = params.get("landscape", False)

    set_page_orientation(pkg, sheet, landscape)
    orientation = "landscape" if landscape else "portrait"
    return {"message": f"Set {sheet} to {orientation}", "element_id": ""}


def _op_set_page_size(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Set page size."""
    sheet = require(params, "sheet", "set_page_size")
    paper_size = params.get("paper_size", 1)

    set_page_size(pkg, sheet, paper_size)
    return {
        "message": f"Set paper size to {paper_size} for sheet '{sheet}'",
        "element_id": "",
    }


def _op_set_scale(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Set print scale."""
    sheet = require(params, "sheet", "set_scale")
    scale_value = params.get("scale", 100)

    set_scale(pkg, sheet, scale_value)
    return {
        "message": f"Set scale to {scale_value}% for sheet '{sheet}'",
        "element_id": "",
    }


def _op_set_fit_to_page(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Set fit to page."""
    sheet = require(params, "sheet", "set_fit_to_page")
    fit_width = params.get("fit_width", -1)
    fit_height = params.get("fit_height", -1)

    set_fit_to_page(
        pkg,
        sheet,
        fit_width if fit_width >= 0 else None,
        fit_height if fit_height >= 0 else None,
    )
    return {"message": f"Set fit to page for sheet '{sheet}'", "element_id": ""}


def _op_add_page_break(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add page break."""
    sheet = require(params, "sheet", "add_page_break")
    break_type = params.get("break_type", "row")
    break_position = params.get("break_position", 0)

    if break_type == "row":
        add_row_page_break(pkg, sheet, break_position)
        return {
            "message": f"Added row page break at row {break_position}",
            "element_id": "",
        }
    else:
        add_column_page_break(pkg, sheet, break_position)
        return {
            "message": f"Added column page break at column {break_position}",
            "element_id": "",
        }


def _op_clear_page_breaks(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Clear all page breaks."""
    sheet = require(params, "sheet", "clear_page_breaks")

    clear_page_breaks(pkg, sheet)
    return {"message": f"Cleared all page breaks for sheet '{sheet}'", "element_id": ""}


def _op_create_chart(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Create chart."""
    sheet = require(params, "sheet", "create_chart")
    chart_type = require(params, "chart_type", "create_chart")
    data_range = require(params, "data_range", "create_chart")
    position = params.get("position", "")
    title = params.get("title", "")

    chart_id = create_chart(pkg, sheet, chart_type, data_range, position, title or None)
    return {
        "message": f"Created {chart_type} chart at {position}",
        "element_id": chart_id,
    }


def _op_delete_chart(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Delete chart."""
    sheet = require(params, "sheet", "delete_chart")
    chart_id = require(params, "chart_id", "delete_chart")

    delete_chart(pkg, sheet, chart_id)
    return {"message": f"Deleted chart '{chart_id}'", "element_id": ""}


def _op_update_chart_data(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Update chart data range."""
    sheet = require(params, "sheet", "update_chart_data")
    chart_id = require(params, "chart_id", "update_chart_data")
    data_range = require(params, "data_range", "update_chart_data")

    update_chart_data(pkg, sheet, chart_id, data_range)
    return {
        "message": f"Updated chart '{chart_id}' data to {data_range}",
        "element_id": chart_id,
    }


def _op_create_pivot(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Create pivot table."""
    sheet = require(params, "sheet", "create_pivot")
    data_range = require(params, "data_range", "create_pivot")
    position = require(params, "position", "create_pivot")
    row_fields_str = params.get("row_fields", "")
    col_fields_str = params.get("col_fields", "")
    value_fields_str = params.get("value_fields", "")
    pivot_name = params.get("pivot_name", "")
    agg_func = params.get("agg_func", "sum")

    row_fields = [f.strip() for f in row_fields_str.split(",") if f.strip()]
    col_fields = [f.strip() for f in col_fields_str.split(",") if f.strip()]
    value_fields = [f.strip() for f in value_fields_str.split(",") if f.strip()]

    pivot_id = create_pivot(
        pkg,
        sheet,
        data_range,
        position,
        row_fields,
        col_fields,
        value_fields,
        pivot_name or None,
        agg_func,
    )
    return {"message": f"Created pivot table at {position}", "element_id": pivot_id}


def _op_delete_pivot(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Delete pivot table."""
    sheet = require(params, "sheet", "delete_pivot")
    pivot_id = require(params, "pivot_id", "delete_pivot")

    delete_pivot(pkg, sheet, pivot_id)
    return {"message": f"Deleted pivot table '{pivot_id}'", "element_id": ""}


def _op_refresh_pivot(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Refresh pivot table."""
    sheet = require(params, "sheet", "refresh_pivot")
    pivot_id = require(params, "pivot_id", "refresh_pivot")

    refresh_pivot(pkg, sheet, pivot_id)
    return {"message": f"Refreshed pivot table '{pivot_id}'", "element_id": pivot_id}


def _op_set_property(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Set core document property."""
    name = require(params, "property_name", "set_property")
    value = require_any(params, "property_value", "set_property")

    set_core_properties(pkg, **{name: value})
    return {"message": f"Set core property '{name}' = '{value}'", "element_id": ""}


def _op_set_custom_property(
    pkg: ExcelPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Set custom document property."""
    name = require(params, "property_name", "set_custom_property")
    value = require_any(params, "property_value", "set_custom_property")
    prop_type = params.get("property_type", "string")

    actual_value, prop_type = convert_custom_property_value(value, prop_type)
    set_custom_property(pkg, name, actual_value, prop_type)
    return {
        "message": f"Set custom property '{name}' = '{value}' ({prop_type})",
        "element_id": "",
    }


def _op_delete_custom_property(
    pkg: ExcelPackage, params: dict[str, Any]
) -> dict[str, Any]:
    """Delete custom document property."""
    name = require(params, "property_name", "delete_custom_property")

    deleted = delete_custom_property(pkg, name)
    if deleted:
        return {"message": f"Deleted custom property '{name}'", "element_id": ""}
    else:
        raise ValueError(f"Custom property '{name}' not found")


# =============================================================================
# Named Ranges Operations
# =============================================================================


def _op_create_name(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Create a defined name (named range)."""
    name = require(params, "name", "create_name")
    refers_to = require(params, "refers_to", "create_name")
    scope = params.get("scope")
    comment = params.get("comment")

    name_info = create_name(pkg, name, refers_to, scope, comment)
    return {
        "message": f"Created name '{name}' -> {refers_to}",
        "element_id": name_info.id or name,
    }


def _op_delete_name(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Delete a defined name."""
    name = require(params, "name", "delete_name")
    scope = params.get("scope")

    delete_name(pkg, name, scope)
    return {"message": f"Deleted name '{name}'", "element_id": ""}


# =============================================================================
# Data Validation Operations
# =============================================================================


def _op_add_validation(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Add data validation to cells."""
    sheet = require(params, "sheet", "add_validation")
    cell_ref = require(params, "cell_ref", "add_validation")
    val_type = require(params, "type", "add_validation")

    formula1 = params.get("formula1")
    formula2 = params.get("formula2")
    operator = params.get("operator")
    allow_blank = params.get("allow_blank", True)
    show_dropdown = params.get("show_dropdown", True)
    error_title = params.get("error_title")
    error_message = params.get("error_message")
    prompt_title = params.get("prompt_title")
    prompt = params.get("prompt")

    val_info = add_validation(
        pkg,
        sheet,
        cell_ref,
        val_type,
        formula1,
        formula2,
        operator,
        allow_blank,
        show_dropdown,
        error_title,
        error_message,
        prompt_title,
        prompt,
    )
    return {
        "message": f"Added {val_type} validation to {cell_ref}",
        "element_id": val_info.id or cell_ref,
    }


def _op_remove_validation(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Remove data validation from cells."""
    sheet = require(params, "sheet", "remove_validation")
    cell_ref = require(params, "cell_ref", "remove_validation")

    remove_validation(pkg, sheet, cell_ref)
    return {"message": f"Removed validation from {cell_ref}", "element_id": ""}


# =============================================================================
# AutoFilter Operations
# =============================================================================


def _op_set_autofilter(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Enable AutoFilter on a range."""
    sheet = require(params, "sheet", "set_autofilter")
    cell_ref = require(params, "cell_ref", "set_autofilter")

    filter_info = set_autofilter(pkg, sheet, cell_ref)
    return {
        "message": f"Set AutoFilter on {cell_ref}",
        "element_id": filter_info.ref,
    }


def _op_clear_autofilter(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Remove AutoFilter from a sheet."""
    sheet = require(params, "sheet", "clear_autofilter")

    clear_autofilter(pkg, sheet)
    return {"message": f"Cleared AutoFilter from sheet '{sheet}'", "element_id": ""}


def _op_apply_filter(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Apply filter criteria to a column."""
    sheet = require(params, "sheet", "apply_filter")
    column = params.get("column")
    values = params.get("values")

    if column is None:
        raise ValueError("column required for apply_filter")
    if values is None:
        raise ValueError("values required for apply_filter (list of strings)")

    filter_info = apply_filter(pkg, sheet, column, values)
    return {
        "message": f"Applied filter to column {column}",
        "element_id": filter_info.ref if filter_info else "",
    }


def _op_clear_filter(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Clear filter on a specific column."""
    sheet = require(params, "sheet", "clear_filter")
    column = params.get("column")

    if column is None:
        raise ValueError("column required for clear_filter")

    clear_filter(pkg, sheet, column)
    return {"message": f"Cleared filter on column {column}", "element_id": ""}


def _op_sort_range(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Sort a range by one or more columns."""
    sheet = require(params, "sheet", "sort_range")
    cell_ref = require(params, "cell_ref", "sort_range")
    sort_by = params.get("sort_by")
    descending = params.get("descending", False)

    if sort_by is None:
        raise ValueError("sort_by required for sort_range (column index or list)")

    sort_range(pkg, sheet, cell_ref, sort_by, descending)
    return {"message": f"Sorted range {cell_ref}", "element_id": ""}


def _op_find_replace(pkg: ExcelPackage, params: dict[str, Any]) -> dict[str, Any]:
    """Find and replace text in cell values."""
    search = require(params, "search", "find_replace")
    replace_text = params.get("replace", "")
    sheet = params.get("sheet")  # Optional - if not provided, searches all sheets
    match_case = params.get("match_case", True)  # Default to case-sensitive

    count = find_replace_cells(pkg, search, replace_text, sheet, match_case=match_case)
    if sheet:
        return {
            "message": f"Replaced {count} occurrences of '{search}' in sheet '{sheet}'",
            "element_id": "",
        }
    else:
        return {
            "message": f"Replaced {count} occurrences of '{search}' across all sheets",
            "element_id": "",
        }
