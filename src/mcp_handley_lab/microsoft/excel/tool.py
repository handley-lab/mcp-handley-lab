"""Excel MCP tool - read and edit Excel workbooks.

Uses progressive disclosure with scopes for efficient reading.
Default representation is 'grid' with values + types arrays.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.microsoft.excel.models import ExcelEditResult

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
        description="What to read: meta, sheets, cells, table, tables, styles, conditional_formats, protection, print_settings, charts, properties",
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
    """Read data from an Excel workbook. Use edit to modify. Returns block IDs for targeting edits.

    Uses progressive disclosure with scopes:
    - meta: Quick workbook overview
    - sheets: List of sheets for subsequent queries
    - cells: Cell values with grid (default), sparse, or detailed representation
    - table: Single table data by name
    - tables: List of all tables
    - styles: List of cell styles
    """
    from mcp_handley_lab.microsoft.excel.shared import read as _read

    return _read(
        file_path=file_path,
        scope=scope,
        sheet=sheet,
        range_ref=range_ref,
        table_name=table_name,
        representation=representation,
        include_types=include_types,
        include_headers=include_headers,
        view=view,
        limit=limit,
    )


@mcp.tool()
def edit(
    file_path: str = Field(description="Path to .xlsx file"),
    ops: str = Field(
        description='JSON array of operation objects. Each object has "op" (operation name) '
        "plus operation-specific fields. Use $prev[N] to reference element_id from operation N."
    ),
) -> dict[str, Any]:
    """Edit an Excel workbook using batch operations. Creates a new file if file_path doesn't exist.

    Fail-fast semantics: raises on first operation error, file unchanged on any failure.
    Use read() first to discover sheets, cells, and tables.

    Args:
        file_path: Path to .xlsx file
        ops: JSON array of operation objects, e.g.:
            [{"op": "set_cell", "sheet": "Sheet1", "cell_ref": "A1", "value": "Hello"},
             {"op": "set_style", "sheet": "Sheet1", "cell_ref": "$prev[0]", "style_index": 1}]

    Available operations:
        - set_cell: Set cell value {sheet, cell_ref, value}
        - set_formula: Set formula {sheet, cell_ref, formula}
        - set_range: Set range values {sheet, cell_ref, value} (value is JSON 2D array)
        - set_style: Apply style {sheet, cell_ref, style_index}
        - insert_rows: Insert rows {sheet, cell_ref, count}
        - delete_rows: Delete rows {sheet, cell_ref, count}
        - insert_columns: Insert columns {sheet, cell_ref, count}
        - delete_columns: Delete columns {sheet, cell_ref, count}
        - merge_cells: Merge range {sheet, cell_ref}
        - unmerge_cells: Unmerge range {sheet, cell_ref}
        - add_sheet: Add sheet {new_name}
        - rename_sheet: Rename sheet {sheet, new_name}
        - delete_sheet: Delete sheet {sheet}
        - copy_sheet: Copy sheet {sheet, new_name}
        - create_table: Create table {sheet, cell_ref, table_name}
        - delete_table: Delete table {table_name}
        - add_table_row: Add row {table_name, value} (value is JSON array)
        - delete_table_row: Delete row {table_name, row}
        - add_conditional_format: Add conditional format {sheet, cell_ref, rule_type, operator, formula, style_index, priority}
        - protect_sheet/unprotect_sheet: {sheet, password}
        - protect_workbook/unprotect_workbook: {password}
        - lock_cells/unlock_cells: {sheet, cell_ref}
        - set_print_area/clear_print_area: {sheet, cell_ref}
        - set_print_titles: {sheet, print_rows, print_cols}
        - set_page_margins: {sheet, margin_left, margin_right, margin_top, margin_bottom}
        - set_page_orientation: {sheet, landscape}
        - set_page_size: {sheet, paper_size}
        - set_scale: {sheet, scale}
        - set_fit_to_page: {sheet, fit_width, fit_height}
        - add_page_break: {sheet, break_type, break_position}
        - clear_page_breaks: {sheet}
        - create_chart: {sheet, chart_type, data_range, position, title}
        - delete_chart: {sheet, chart_id}
        - update_chart_data: {sheet, chart_id, data_range}
        - create_pivot: {sheet, data_range, position, row_fields, col_fields, value_fields, pivot_name, agg_func}
        - delete_pivot: {sheet, pivot_id}
        - refresh_pivot: {sheet, pivot_id}
        - set_property: {property_name, property_value}
        - set_custom_property: {property_name, property_value, property_type}
        - delete_custom_property: {property_name}

    $prev chaining:
        Reference results of previous operations using $prev[N] where N is the
        operation index (0-based). Only works for: cell_ref, range_ref, sheet,
        table_name, chart_id, pivot_id.

    Returns:
        ExcelEditResult with success status, counts, and per-operation results
    """
    from mcp_handley_lab.microsoft.excel.shared import edit as _edit

    return _edit(file_path=file_path, ops=ops)


# =============================================================================
# Standalone Operations (not available in batch mode)
# =============================================================================


@mcp.tool()
def recalculate(
    file_path: str = Field(description="Path to .xlsx file"),
) -> dict[str, Any]:
    """Recalculate all formulas using LibreOffice headless.

    Opens the file in LibreOffice to trigger formula calculation,
    then saves it back. The cached values in <v> elements are then populated.
    """
    resolved_path = str(Path(file_path).resolve())
    file_name = Path(resolved_path).name

    with tempfile.TemporaryDirectory() as tmpdir:
        input_dir = Path(tmpdir) / "in"
        output_dir = Path(tmpdir) / "out"
        input_dir.mkdir()
        output_dir.mkdir()

        input_copy = input_dir / file_name
        shutil.copy2(resolved_path, input_copy)

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

        output_file = output_dir / file_name
        if not output_file.exists():
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

        shutil.move(str(output_file), resolved_path)

    return ExcelEditResult(
        success=True,
        message="Recalculated all formulas",
        total=1,
        succeeded=1,
        saved=True,
    ).model_dump(exclude_none=True)
