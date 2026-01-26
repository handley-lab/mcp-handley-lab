"""Core Excel functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

from typing import Any


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

    Args:
        file_path: Path to .xlsx file.
        scope: What to read: meta, sheets, cells, table, tables, styles,
            conditional_formats, protection, print_settings, charts, pivots.
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
    from mcp_handley_lab.microsoft.excel.package import ExcelPackage
    from mcp_handley_lab.microsoft.excel.tool import (
        _read_cells,
        _read_charts,
        _read_conditional_formats,
        _read_meta,
        _read_pivots,
        _read_print_settings,
        _read_protection,
        _read_sheets,
        _read_styles,
        _read_table,
        _read_tables,
    )

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


def edit(
    file_path: str,
    operation: str,
    sheet: str = "",
    cell_ref: str = "",
    value: str = "",
    new_name: str = "",
    table_name: str = "",
    row_index: int = 0,
    count: int = 1,
    style_index: int = -1,
    rule_type: str = "",
    operator: str = "",
    formula: str = "",
    priority: int = 1,
    password: str = "",
    margin_left: float = -1.0,
    margin_right: float = -1.0,
    margin_top: float = -1.0,
    margin_bottom: float = -1.0,
    landscape: bool = False,
    paper_size: int = 1,
    print_rows: str = "",
    print_cols: str = "",
    break_type: str = "row",
    break_position: int = 0,
    scale: int = 100,
    fit_width: int = -1,
    fit_height: int = -1,
    chart_type: str = "",
    data_range: str = "",
    position: str = "",
    title: str = "",
    chart_id: str = "",
    row_fields: str = "",
    col_fields: str = "",
    value_fields: str = "",
    pivot_name: str = "",
    pivot_id: str = "",
    agg_func: str = "sum",
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
    - add_conditional_format: Add conditional formatting
    - protect_sheet: Protect sheet from modification
    - unprotect_sheet: Remove sheet protection
    - protect_workbook: Protect workbook structure
    - unprotect_workbook: Remove workbook protection
    - lock_cells: Lock cells in range
    - unlock_cells: Unlock cells in range
    - set_print_area: Set print area
    - clear_print_area: Clear print area
    - set_print_titles: Set repeating rows/columns
    - set_page_margins: Set page margins
    - set_page_orientation: Set page orientation
    - set_page_size: Set paper size
    - set_scale: Set print scale percentage
    - set_fit_to_page: Fit to pages
    - add_page_break: Add page break
    - clear_page_breaks: Clear all page breaks
    - create_chart: Create chart
    - delete_chart: Delete chart by ID
    - update_chart_data: Update chart data range
    - create_pivot: Create pivot table
    - delete_pivot: Delete pivot table by ID
    - refresh_pivot: Refresh pivot table cache
    - recalculate: Recalculate all formulas using LibreOffice

    Args:
        file_path: Path to .xlsx file.
        operation: Operation to perform.
        sheet: Sheet name (required for cell/sheet operations).
        cell_ref: Cell reference like 'A1' or range like 'A1:C3'.
        value: Value to set (string, number, or JSON array for add_table_row,
            JSON 2D array for set_range).
        new_name: New name (for rename_sheet, copy_sheet, table_name for create_table).
        table_name: Table name (for table operations).
        row_index: Row index for delete_table_row (0-based, relative to data rows).
        count: Count for insert/delete rows/columns.
        style_index: Style index for set_style or add_conditional_format (dxfId).
        rule_type: For add_conditional_format: rule type (cellIs, colorScale, etc.).
        operator: For add_conditional_format: operator (lessThan, greaterThan, etc.).
        formula: For add_conditional_format: formula or value(s).
        priority: For add_conditional_format: rule priority.
        password: Password for protect/unprotect operations.
        margin_left: Left margin in inches (for set_page_margins).
        margin_right: Right margin in inches (for set_page_margins).
        margin_top: Top margin in inches (for set_page_margins).
        margin_bottom: Bottom margin in inches (for set_page_margins).
        landscape: Landscape orientation (for set_page_orientation).
        paper_size: Paper size code: 1=Letter, 9=A4, 5=Legal (for set_page_size).
        print_rows: Rows to repeat, e.g., '1:2' (for set_print_titles).
        print_cols: Columns to repeat, e.g., 'A:B' (for set_print_titles).
        break_type: Page break type: 'row' or 'column' (for add_page_break).
        break_position: Row or column number for page break (for add_page_break).
        scale: Print scale percentage 10-400 (for set_scale).
        fit_width: Fit to N pages wide, 0=auto (for set_fit_to_page).
        fit_height: Fit to N pages tall, 0=auto (for set_fit_to_page).
        chart_type: Chart type: bar, column, line, pie, scatter, area.
        data_range: Data range like 'A1:B10' (for create_chart, update_chart_data).
        position: Chart position cell like 'E5' (for create_chart).
        title: Chart title (for create_chart).
        chart_id: Chart ID (for delete_chart, update_chart_data).
        row_fields: Comma-separated field names for row labels (for create_pivot).
        col_fields: Comma-separated field names for column labels (for create_pivot).
        value_fields: Comma-separated field names for values (for create_pivot).
        pivot_name: Pivot table name (for create_pivot).
        pivot_id: Pivot table ID (for delete_pivot, refresh_pivot).
        agg_func: Aggregation function: sum, count, average, min, max.

    Returns:
        Dict with success status, message, and affected_refs.
    """
    from mcp_handley_lab.microsoft.excel.tool import (
        _edit_add_conditional_format,
        _edit_add_page_break,
        _edit_add_sheet,
        _edit_add_table_row,
        _edit_clear_page_breaks,
        _edit_clear_print_area,
        _edit_copy_sheet,
        _edit_create,
        _edit_create_chart,
        _edit_create_pivot,
        _edit_create_table,
        _edit_delete_chart,
        _edit_delete_columns,
        _edit_delete_pivot,
        _edit_delete_rows,
        _edit_delete_sheet,
        _edit_delete_table,
        _edit_delete_table_row,
        _edit_insert_columns,
        _edit_insert_rows,
        _edit_lock_cells,
        _edit_merge_cells,
        _edit_protect_sheet,
        _edit_protect_workbook,
        _edit_recalculate,
        _edit_refresh_pivot,
        _edit_rename_sheet,
        _edit_set_cell,
        _edit_set_fit_to_page,
        _edit_set_formula,
        _edit_set_page_margins,
        _edit_set_page_orientation,
        _edit_set_page_size,
        _edit_set_print_area,
        _edit_set_print_titles,
        _edit_set_range,
        _edit_set_scale,
        _edit_set_style,
        _edit_unlock_cells,
        _edit_unmerge_cells,
        _edit_unprotect_sheet,
        _edit_unprotect_workbook,
        _edit_update_chart_data,
    )

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
