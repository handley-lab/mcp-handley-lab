"""Tests for required parameter validation in Excel edit operations."""

import json

import pytest

from mcp_handley_lab.microsoft.excel.package import ExcelPackage
from mcp_handley_lab.microsoft.excel.shared import edit


@pytest.fixture
def workbook(tmp_path):
    """Create a temporary Excel workbook with a sheet."""
    file_path = tmp_path / "test.xlsx"
    pkg = ExcelPackage.new()
    pkg.save(str(file_path))
    return str(file_path)


class TestCellOpsRequiredParams:
    """Validate required params for cell operations."""

    def test_set_cell_missing_sheet(self, workbook):
        with pytest.raises(ValueError, match="(?i)sheet required"):
            edit(
                workbook,
                ops=json.dumps([{"op": "set_cell", "cell_ref": "A1", "value": "x"}]),
            )

    def test_set_cell_missing_cell_ref(self, workbook):
        with pytest.raises(ValueError, match="(?i)cell_ref required"):
            edit(
                workbook,
                ops=json.dumps([{"op": "set_cell", "sheet": "Sheet1", "value": "x"}]),
            )

    def test_set_cell_missing_value(self, workbook):
        with pytest.raises(ValueError, match="(?i)value required"):
            edit(
                workbook,
                ops=json.dumps(
                    [{"op": "set_cell", "sheet": "Sheet1", "cell_ref": "A1"}]
                ),
            )

    def test_set_formula_missing_formula(self, workbook):
        with pytest.raises(ValueError, match="(?i)formula required"):
            edit(
                workbook,
                ops=json.dumps(
                    [{"op": "set_formula", "sheet": "Sheet1", "cell_ref": "A1"}]
                ),
            )


class TestSheetOpsRequiredParams:
    """Validate required params for sheet operations."""

    def test_add_sheet_missing_name(self, workbook):
        with pytest.raises(ValueError, match="(?i)required for add_sheet"):
            edit(workbook, ops=json.dumps([{"op": "add_sheet"}]))

    def test_rename_sheet_missing_new_name(self, workbook):
        with pytest.raises(ValueError, match="(?i)new_name required"):
            edit(workbook, ops=json.dumps([{"op": "rename_sheet", "sheet": "Sheet1"}]))

    def test_delete_sheet_missing_sheet(self, workbook):
        with pytest.raises(ValueError, match="(?i)sheet required"):
            edit(workbook, ops=json.dumps([{"op": "delete_sheet"}]))


class TestTableOpsRequiredParams:
    """Validate required params for table operations."""

    def test_create_table_missing_table_name(self, workbook):
        with pytest.raises(ValueError, match="(?i)required for create_table"):
            edit(
                workbook,
                ops=json.dumps(
                    [{"op": "create_table", "sheet": "Sheet1", "cell_ref": "A1:B2"}]
                ),
            )

    def test_delete_table_missing_name(self, workbook):
        with pytest.raises(ValueError, match="(?i)table_name required"):
            edit(workbook, ops=json.dumps([{"op": "delete_table"}]))


class TestChartOpsRequiredParams:
    """Validate required params for chart operations."""

    def test_create_chart_missing_sheet(self, workbook):
        with pytest.raises(ValueError, match="(?i)sheet required"):
            edit(
                workbook,
                ops=json.dumps(
                    [{"op": "create_chart", "chart_type": "bar", "data_range": "A1:B3"}]
                ),
            )

    def test_create_chart_missing_chart_type(self, workbook):
        with pytest.raises(ValueError, match="(?i)chart_type required"):
            edit(
                workbook,
                ops=json.dumps(
                    [{"op": "create_chart", "sheet": "Sheet1", "data_range": "A1:B3"}]
                ),
            )

    def test_create_chart_missing_data_range(self, workbook):
        with pytest.raises(ValueError, match="(?i)data_range required"):
            edit(
                workbook,
                ops=json.dumps(
                    [{"op": "create_chart", "sheet": "Sheet1", "chart_type": "bar"}]
                ),
            )


class TestPropertyOpsRequiredParams:
    """Validate required params for property operations."""

    def test_set_property_missing_name(self, workbook):
        with pytest.raises(ValueError, match="(?i)property_name required"):
            edit(
                workbook,
                ops=json.dumps([{"op": "set_property", "property_value": "test"}]),
            )

    def test_set_property_missing_value(self, workbook):
        with pytest.raises(ValueError, match="(?i)property_value required"):
            edit(
                workbook,
                ops=json.dumps([{"op": "set_property", "property_name": "title"}]),
            )

    def test_delete_custom_property_missing_name(self, workbook):
        with pytest.raises(ValueError, match="(?i)property_name required"):
            edit(workbook, ops=json.dumps([{"op": "delete_custom_property"}]))
