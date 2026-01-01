"""Workbook facade - re-exports all Excel operations.

This module provides a single import point for all Excel operations.
"""

from mcp_handley_lab.microsoft.excel.ops.cells import (
    get_cell_formula,
    get_cell_style_index,
    get_cell_value,
    get_cells_in_range,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    index_to_column_letter,
    make_cell_id,
    make_cell_ref,
    make_range_id,
    make_range_ref,
    make_sheet_id,
    make_table_id,
    parse_cell_ref,
    parse_range_ref,
)
from mcp_handley_lab.microsoft.excel.ops.sheets import (
    get_dimension,
    get_sheet_by_index,
    get_sheet_by_name,
    get_used_range,
    list_sheets,
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
    "make_range_id",
    "make_sheet_id",
    "make_table_id",
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
]
