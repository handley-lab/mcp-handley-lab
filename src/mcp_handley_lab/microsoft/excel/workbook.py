"""Workbook facade - re-exports all Excel operations.

This module provides a single import point for all Excel operations.
"""

from mcp_handley_lab.microsoft.excel.ops.cells import (
    get_cell_formula,
    get_cell_style_index,
    get_cell_value,
    get_cells_in_range,
)
from mcp_handley_lab.microsoft.excel.ops.charts import (
    create_chart,
    delete_chart,
    list_charts,
    update_chart_data,
)
from mcp_handley_lab.microsoft.excel.ops.comments import (
    add_comment,
    delete_comment,
    get_comment,
    list_comments,
    update_comment,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    index_to_column_letter,
    make_cell_id,
    make_cell_ref,
    make_chart_id,
    make_pivot_id,
    make_range_id,
    make_range_ref,
    make_sheet_id,
    make_table_id,
    parse_cell_ref,
    parse_range_ref,
)
from mcp_handley_lab.microsoft.excel.ops.dates import (
    datetime_to_excel,
    excel_to_date,
    excel_to_datetime,
    excel_to_time,
    is_date_format,
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
)
from mcp_handley_lab.microsoft.excel.ops.formula_refactor import (
    CellRef,
    parse_formula_references,
    shift_formula,
    shift_reference,
    update_formulas_after_delete,
    update_formulas_after_insert,
)
from mcp_handley_lab.microsoft.excel.ops.names import (
    create_name,
    delete_name,
    get_name,
    list_names,
    update_name,
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
    clear_print_titles,
    get_fit_to_page,
    get_page_margins,
    get_page_orientation,
    get_page_size,
    get_print_area,
    get_print_titles,
    get_scale,
    list_page_breaks,
    remove_column_page_break,
    remove_row_page_break,
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
    is_cell_locked,
    is_sheet_protected,
    is_workbook_protected,
    lock_cells,
    protect_sheet,
    protect_workbook,
    unlock_cells,
    unprotect_sheet,
    unprotect_workbook,
)
from mcp_handley_lab.microsoft.excel.ops.sheets import (
    get_column_width,
    get_dimension,
    get_row_height,
    get_sheet_by_index,
    get_sheet_by_name,
    get_used_range,
    list_sheets,
    set_column_width,
    set_row_height,
)
from mcp_handley_lab.microsoft.excel.ops.styles_write import (
    create_border,
    create_cell_style,
    create_fill,
    create_font,
    create_number_format,
)
from mcp_handley_lab.microsoft.excel.ops.validation import (
    add_validation,
    list_validations,
    remove_validation,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage

__all__ = [
    # Package
    "ExcelPackage",
    # Core utilities
    "column_letter_to_index",
    "index_to_column_letter",
    "make_cell_ref",
    "make_range_ref",
    "parse_cell_ref",
    "parse_range_ref",
    # ID generation
    "make_cell_id",
    "make_chart_id",
    "make_pivot_id",
    "make_range_id",
    "make_sheet_id",
    "make_table_id",
    # Date utilities
    "datetime_to_excel",
    "excel_to_datetime",
    "excel_to_date",
    "excel_to_time",
    "is_date_format",
    # Cell operations
    "get_cell_value",
    "get_cell_formula",
    "get_cell_style_index",
    "get_cells_in_range",
    # Sheet operations
    "list_sheets",
    "get_sheet_by_name",
    "get_sheet_by_index",
    "get_used_range",
    "get_dimension",
    # Conditional formatting
    "get_conditional_formats",
    "add_conditional_format",
    # Style creation
    "create_font",
    "create_fill",
    "create_border",
    "create_number_format",
    "create_cell_style",
    # Column/row sizing
    "get_column_width",
    "set_column_width",
    "get_row_height",
    "set_row_height",
    # Named ranges
    "list_names",
    "get_name",
    "create_name",
    "update_name",
    "delete_name",
    # Data validation
    "list_validations",
    "add_validation",
    "remove_validation",
    # Comments
    "list_comments",
    "get_comment",
    "add_comment",
    "update_comment",
    "delete_comment",
    # Filtering and sorting
    "get_autofilter",
    "set_autofilter",
    "clear_autofilter",
    "apply_filter",
    "clear_filter",
    "sort_range",
    # Formula refactoring
    "CellRef",
    "parse_formula_references",
    "shift_reference",
    "shift_formula",
    "update_formulas_after_insert",
    "update_formulas_after_delete",
    # Protection
    "protect_sheet",
    "unprotect_sheet",
    "is_sheet_protected",
    "get_sheet_protection",
    "protect_workbook",
    "unprotect_workbook",
    "is_workbook_protected",
    "get_workbook_protection",
    "lock_cells",
    "unlock_cells",
    "is_cell_locked",
    # Print settings
    "set_print_area",
    "get_print_area",
    "clear_print_area",
    "set_print_titles",
    "get_print_titles",
    "clear_print_titles",
    "set_page_margins",
    "get_page_margins",
    "set_page_orientation",
    "get_page_orientation",
    "set_page_size",
    "get_page_size",
    "set_scale",
    "get_scale",
    "set_fit_to_page",
    "get_fit_to_page",
    "add_row_page_break",
    "add_column_page_break",
    "remove_row_page_break",
    "remove_column_page_break",
    "list_page_breaks",
    "clear_page_breaks",
    # Charts
    "list_charts",
    "create_chart",
    "delete_chart",
    "update_chart_data",
    # Pivot Tables
    "list_pivots",
    "create_pivot",
    "delete_pivot",
    "refresh_pivot",
]
