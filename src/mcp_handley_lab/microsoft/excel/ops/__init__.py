"""Excel operation modules."""

from mcp_handley_lab.microsoft.excel.ops.cells import (
    get_cell_data,
    get_cell_style_index,
    get_cells_in_range,
    set_cell_formula,
    set_cell_style,
    set_cell_value,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    index_to_column_letter,
    make_cell_ref,
    make_range_ref,
    parse_cell_ref,
    parse_range_ref,
)
from mcp_handley_lab.microsoft.excel.ops.ranges import (
    delete_columns,
    delete_rows,
    get_range_values,
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
    get_dimension,
    get_sheet_by_index,
    get_sheet_by_name,
    get_used_range,
    list_sheets,
    rename_sheet,
)

__all__ = [
    # Core
    "column_letter_to_index",
    "index_to_column_letter",
    "make_cell_ref",
    "make_range_ref",
    "parse_cell_ref",
    "parse_range_ref",
    # Cells - Read
    "get_cell_data",
    "get_cell_style_index",
    "get_cells_in_range",
    # Cells - Write
    "set_cell_value",
    "set_cell_formula",
    "set_cell_style",
    # Ranges
    "get_range_values",
    "set_range_values",
    "insert_rows",
    "delete_rows",
    "insert_columns",
    "delete_columns",
    "merge_cells",
    "unmerge_cells",
    # Sheets - Read
    "list_sheets",
    "get_sheet_by_name",
    "get_sheet_by_index",
    "get_used_range",
    "get_dimension",
    # Sheets - Write
    "add_sheet",
    "rename_sheet",
    "delete_sheet",
    "copy_sheet",
]
