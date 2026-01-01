"""Tests for Excel table operations."""

import pytest

from mcp_handley_lab.microsoft.excel.ops.cells import set_cell_value
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


class TestListTables:
    """Tests for list_tables."""

    def test_list_tables_empty_workbook(self) -> None:
        """New workbook has no tables."""
        pkg = ExcelPackage.new()
        tables = list_tables(pkg)
        assert tables == []

    def test_list_tables_with_table(self) -> None:
        """List tables returns created table."""
        pkg = ExcelPackage.new()

        # Set up data for table
        set_cell_value(pkg, "Sheet1", "A1", "Name")
        set_cell_value(pkg, "Sheet1", "B1", "Age")
        set_cell_value(pkg, "Sheet1", "A2", "Alice")
        set_cell_value(pkg, "Sheet1", "B2", 30)

        create_table(pkg, "Sheet1", "A1:B2", "MyTable")

        tables = list_tables(pkg)
        assert len(tables) == 1
        assert tables[0].name == "MyTable"
        assert tables[0].sheet == "Sheet1"
        assert tables[0].ref == "A1:B2"


class TestCreateTable:
    """Tests for create_table."""

    def test_create_table_basic(self) -> None:
        """Create a basic table with headers."""
        pkg = ExcelPackage.new()

        # Set up data
        set_cell_value(pkg, "Sheet1", "A1", "Product")
        set_cell_value(pkg, "Sheet1", "B1", "Price")
        set_cell_value(pkg, "Sheet1", "A2", "Widget")
        set_cell_value(pkg, "Sheet1", "B2", 9.99)

        info = create_table(pkg, "Sheet1", "A1:B2", "Products")

        assert info.name == "Products"
        assert info.columns == ["Product", "Price"]
        assert info.row_count == 1  # Excludes header row

    def test_create_table_auto_column_names(self) -> None:
        """Table with empty headers gets auto-generated column names."""
        pkg = ExcelPackage.new()

        # Only data, no header values
        set_cell_value(pkg, "Sheet1", "A2", "Data1")
        set_cell_value(pkg, "Sheet1", "B2", "Data2")

        info = create_table(pkg, "Sheet1", "A1:B2", "AutoColumns")

        # When headers are None, they become "ColumnN" based on 1-based column index
        # Column A is index 1, Column B is index 2
        assert info.columns[0].startswith("Column")
        assert info.columns[1].startswith("Column")


class TestGetTableByName:
    """Tests for get_table_by_name."""

    def test_get_table_by_name_found(self) -> None:
        """Get existing table by name."""
        pkg = ExcelPackage.new()

        set_cell_value(pkg, "Sheet1", "A1", "Col")
        create_table(pkg, "Sheet1", "A1:A2", "TestTable")

        info = get_table_by_name(pkg, "TestTable")
        assert info.name == "TestTable"

    def test_get_table_by_name_not_found(self) -> None:
        """Getting non-existent table raises KeyError."""
        pkg = ExcelPackage.new()

        with pytest.raises(KeyError, match="not found"):
            get_table_by_name(pkg, "NonExistent")


class TestGetTableData:
    """Tests for get_table_data."""

    def test_get_table_data_excludes_headers(self) -> None:
        """Get table data excludes header row by default."""
        pkg = ExcelPackage.new()

        set_cell_value(pkg, "Sheet1", "A1", "Name")
        set_cell_value(pkg, "Sheet1", "B1", "Value")
        set_cell_value(pkg, "Sheet1", "A2", "Item1")
        set_cell_value(pkg, "Sheet1", "B2", 100)
        set_cell_value(pkg, "Sheet1", "A3", "Item2")
        set_cell_value(pkg, "Sheet1", "B3", 200)

        create_table(pkg, "Sheet1", "A1:B3", "DataTable")

        data = get_table_data(pkg, "DataTable")

        assert len(data) == 2
        assert data[0] == ["Item1", 100]
        assert data[1] == ["Item2", 200]

    def test_get_table_data_includes_headers(self) -> None:
        """Get table data with headers when requested."""
        pkg = ExcelPackage.new()

        set_cell_value(pkg, "Sheet1", "A1", "Header1")
        set_cell_value(pkg, "Sheet1", "A2", "Data1")

        create_table(pkg, "Sheet1", "A1:A2", "WithHeaders")

        data = get_table_data(pkg, "WithHeaders", include_headers=True)

        assert len(data) == 2
        assert data[0] == ["Header1"]
        assert data[1] == ["Data1"]


class TestDeleteTable:
    """Tests for delete_table."""

    def test_delete_table_removes_from_list(self) -> None:
        """Deleted table is removed from list_tables."""
        pkg = ExcelPackage.new()

        set_cell_value(pkg, "Sheet1", "A1", "Col")
        create_table(pkg, "Sheet1", "A1:A2", "ToDelete")

        assert len(list_tables(pkg)) == 1

        delete_table(pkg, "ToDelete")

        assert len(list_tables(pkg)) == 0

    def test_delete_table_preserves_data(self) -> None:
        """Deleting table preserves cell data."""
        pkg = ExcelPackage.new()

        set_cell_value(pkg, "Sheet1", "A1", "Header")
        set_cell_value(pkg, "Sheet1", "A2", "Value")
        create_table(pkg, "Sheet1", "A1:A2", "Table")

        delete_table(pkg, "Table")

        # Data should still be there
        from mcp_handley_lab.microsoft.excel.ops.cells import get_cell_value

        assert get_cell_value(pkg, "Sheet1", "A1") == "Header"
        assert get_cell_value(pkg, "Sheet1", "A2") == "Value"

    def test_delete_table_not_found_raises(self) -> None:
        """Deleting non-existent table raises KeyError."""
        pkg = ExcelPackage.new()

        with pytest.raises(KeyError, match="not found"):
            delete_table(pkg, "NonExistent")


class TestAddTableRow:
    """Tests for add_table_row."""

    def test_add_table_row_extends_table(self) -> None:
        """Adding row extends table reference."""
        pkg = ExcelPackage.new()

        set_cell_value(pkg, "Sheet1", "A1", "Col")
        set_cell_value(pkg, "Sheet1", "A2", "Row1")
        create_table(pkg, "Sheet1", "A1:A2", "ExtendTable")

        first_ref = add_table_row(pkg, "ExtendTable", ["NewRow"])

        assert first_ref == "A3"

        # Table should now include new row
        info = get_table_by_name(pkg, "ExtendTable")
        assert info.ref == "A1:A3"

    def test_add_table_row_not_found_raises(self) -> None:
        """Adding row to non-existent table raises KeyError."""
        pkg = ExcelPackage.new()

        with pytest.raises(KeyError, match="not found"):
            add_table_row(pkg, "NonExistent", ["Value"])


class TestDeleteTableRow:
    """Tests for delete_table_row."""

    def test_delete_table_row_removes_data(self) -> None:
        """Deleting row removes data and contracts table."""
        pkg = ExcelPackage.new()

        set_cell_value(pkg, "Sheet1", "A1", "Header")
        set_cell_value(pkg, "Sheet1", "A2", "Row1")
        set_cell_value(pkg, "Sheet1", "A3", "Row2")
        create_table(pkg, "Sheet1", "A1:A3", "ContractTable")

        delete_table_row(pkg, "ContractTable", 0)  # Delete first data row

        info = get_table_by_name(pkg, "ContractTable")
        assert info.ref == "A1:A2"

        # Check remaining data was shifted
        data = get_table_data(pkg, "ContractTable")
        assert len(data) == 1
        assert data[0] == ["Row2"]

    def test_delete_table_row_single_row_keeps_empty_row(self) -> None:
        """Deleting only data row clears data but keeps table ref."""
        pkg = ExcelPackage.new()

        set_cell_value(pkg, "Sheet1", "A1", "Header")
        set_cell_value(pkg, "Sheet1", "A2", "OnlyRow")
        create_table(pkg, "Sheet1", "A1:A2", "SingleRow")

        delete_table_row(pkg, "SingleRow", 0)  # Delete the only data row

        # Table ref should stay A1:A2 (Excel requires at least header + 1 row)
        info = get_table_by_name(pkg, "SingleRow")
        assert info.ref == "A1:A2"

        # Data row should be cleared
        data = get_table_data(pkg, "SingleRow")
        assert len(data) == 1
        assert data[0] == [None]

    def test_delete_table_row_out_of_range_raises(self) -> None:
        """Deleting row with invalid index raises IndexError."""
        pkg = ExcelPackage.new()

        set_cell_value(pkg, "Sheet1", "A1", "Header")
        set_cell_value(pkg, "Sheet1", "A2", "Data")
        create_table(pkg, "Sheet1", "A1:A2", "OneRow")

        with pytest.raises(IndexError, match="out of range"):
            delete_table_row(pkg, "OneRow", 5)


class TestTableRoundTrip:
    """Tests for table persistence through save/load."""

    def test_table_survives_save_load(self, tmp_path) -> None:
        """Table persists after save and reload."""
        file_path = tmp_path / "table_test.xlsx"

        # Create and save
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", "Name")
        set_cell_value(pkg, "Sheet1", "A2", "Data")
        create_table(pkg, "Sheet1", "A1:A2", "PersistTable")
        pkg.save(str(file_path))

        # Load and verify
        pkg2 = ExcelPackage.open(str(file_path))
        tables = list_tables(pkg2)

        assert len(tables) == 1
        assert tables[0].name == "PersistTable"
