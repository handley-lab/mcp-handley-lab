"""Embedded Excel workbook creation for Word/PowerPoint charts.

Creates in-memory .xlsx files from 2D data arrays for use as chart data sources.
"""

from __future__ import annotations

from io import BytesIO

from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def create_embedded_excel(
    data: list[list], sheet_name: str = "Sheet1"
) -> tuple[bytes, str, int, int]:
    """Create an in-memory Excel workbook from a 2D data array.

    Args:
        data: 2D list, e.g. [["Category", "S1", "S2"], ["A", 10, 30], ["B", 20, 40]]
        sheet_name: Name for the worksheet

    Returns:
        (xlsx_bytes, sheet_name, n_rows, n_cols)
    """
    from mcp_handley_lab.microsoft.excel.ops.cells import set_cell_value
    from mcp_handley_lab.microsoft.excel.ops.core import index_to_column_letter

    pkg = ExcelPackage.new()

    for row_idx, row in enumerate(data):
        for col_idx, value in enumerate(row):
            col_letter = index_to_column_letter(col_idx + 1)
            cell_ref = f"{col_letter}{row_idx + 1}"
            set_cell_value(pkg, sheet_name, cell_ref, value)

    buf = BytesIO()
    pkg.save(buf)
    return buf.getvalue(), sheet_name, len(data), len(data[0]) if data else 0
