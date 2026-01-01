"""Tests for Excel edit operations (Phase 4)."""

import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.microsoft.excel.ops.cells import (
    get_cell_data,
    set_cell_formula,
    set_cell_value,
)
from mcp_handley_lab.microsoft.excel.ops.sheets import (
    add_sheet,
    copy_sheet,
    delete_sheet,
    list_sheets,
    rename_sheet,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestSetCellValue:
    """Tests for set_cell_value."""

    def test_set_number(self):
        """Set numeric value."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", 42)

        value, type_code, formula = get_cell_data(pkg, "Sheet1", "A1")
        assert value == 42
        assert type_code == "n"
        assert formula is None

    def test_set_float(self):
        """Set float value."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "B2", 3.14159)

        value, type_code, formula = get_cell_data(pkg, "Sheet1", "B2")
        assert value == 3.14159
        assert type_code == "n"

    def test_set_string(self):
        """Set string value."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "C3", "Hello World")

        value, type_code, formula = get_cell_data(pkg, "Sheet1", "C3")
        assert value == "Hello World"
        assert type_code == "s"

    def test_set_boolean_true(self):
        """Set boolean True."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "D4", True)

        value, type_code, formula = get_cell_data(pkg, "Sheet1", "D4")
        assert value is True
        assert type_code == "b"

    def test_set_boolean_false(self):
        """Set boolean False."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "E5", False)

        value, type_code, formula = get_cell_data(pkg, "Sheet1", "E5")
        assert value is False
        assert type_code == "b"

    def test_set_none_clears_cell(self):
        """Setting None clears the cell."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", 42)
        set_cell_value(pkg, "Sheet1", "A1", None)

        value, type_code, formula = get_cell_data(pkg, "Sheet1", "A1")
        assert value is None
        assert type_code is None

    def test_overwrite_existing_value(self):
        """Overwrite existing cell value."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", 42)
        set_cell_value(pkg, "Sheet1", "A1", "Changed")

        value, type_code, formula = get_cell_data(pkg, "Sheet1", "A1")
        assert value == "Changed"
        assert type_code == "s"

    def test_round_trip_save(self):
        """Values survive save/reload."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", 42)
        set_cell_value(pkg, "Sheet1", "B1", "Hello")
        set_cell_value(pkg, "Sheet1", "C1", True)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            pkg.save(f.name)
            pkg2 = ExcelPackage.open(f.name)

            v1, _, _ = get_cell_data(pkg2, "Sheet1", "A1")
            v2, _, _ = get_cell_data(pkg2, "Sheet1", "B1")
            v3, _, _ = get_cell_data(pkg2, "Sheet1", "C1")

            assert v1 == 42
            assert v2 == "Hello"
            assert v3 is True

            Path(f.name).unlink()


class TestSetCellFormula:
    """Tests for set_cell_formula."""

    def test_set_formula(self):
        """Set a formula."""
        pkg = ExcelPackage.new()
        set_cell_formula(pkg, "Sheet1", "A1", "SUM(B1:B10)")

        value, type_code, formula = get_cell_data(pkg, "Sheet1", "A1")
        assert formula == "SUM(B1:B10)"
        # Value may be None until Excel calculates it

    def test_formula_round_trip(self):
        """Formula survives save/reload."""
        pkg = ExcelPackage.new()
        set_cell_formula(pkg, "Sheet1", "A1", "1+1")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            pkg.save(f.name)
            pkg2 = ExcelPackage.open(f.name)

            _, _, formula = get_cell_data(pkg2, "Sheet1", "A1")
            assert formula == "1+1"

            Path(f.name).unlink()


class TestAddSheet:
    """Tests for add_sheet."""

    def test_add_sheet(self):
        """Add a new sheet."""
        pkg = ExcelPackage.new()
        info = add_sheet(pkg, "NewSheet")

        assert info.name == "NewSheet"
        sheets = list_sheets(pkg)
        assert len(sheets) == 2
        assert sheets[1].name == "NewSheet"

    def test_add_sheet_duplicate_raises(self):
        """Adding duplicate sheet name raises."""
        pkg = ExcelPackage.new()
        with pytest.raises(ValueError, match="already exists"):
            add_sheet(pkg, "Sheet1")

    def test_add_multiple_sheets(self):
        """Add multiple sheets."""
        pkg = ExcelPackage.new()
        add_sheet(pkg, "Sheet2")
        add_sheet(pkg, "Sheet3")

        sheets = list_sheets(pkg)
        assert len(sheets) == 3
        names = [s.name for s in sheets]
        assert "Sheet1" in names
        assert "Sheet2" in names
        assert "Sheet3" in names

    def test_add_sheet_round_trip(self):
        """Added sheet survives save/reload."""
        pkg = ExcelPackage.new()
        add_sheet(pkg, "NewSheet")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            pkg.save(f.name)
            pkg2 = ExcelPackage.open(f.name)

            sheets = list_sheets(pkg2)
            assert len(sheets) == 2

            Path(f.name).unlink()


class TestRenameSheet:
    """Tests for rename_sheet."""

    def test_rename_sheet(self):
        """Rename a sheet."""
        pkg = ExcelPackage.new()
        rename_sheet(pkg, "Sheet1", "Renamed")

        sheets = list_sheets(pkg)
        assert len(sheets) == 1
        assert sheets[0].name == "Renamed"

    def test_rename_sheet_not_found(self):
        """Renaming non-existent sheet raises."""
        pkg = ExcelPackage.new()
        with pytest.raises(KeyError, match="not found"):
            rename_sheet(pkg, "NonExistent", "New")

    def test_rename_to_existing_raises(self):
        """Renaming to existing name raises."""
        pkg = ExcelPackage.new()
        add_sheet(pkg, "Sheet2")
        with pytest.raises(ValueError, match="already exists"):
            rename_sheet(pkg, "Sheet1", "Sheet2")


class TestDeleteSheet:
    """Tests for delete_sheet."""

    def test_delete_sheet(self):
        """Delete a sheet."""
        pkg = ExcelPackage.new()
        add_sheet(pkg, "Sheet2")
        delete_sheet(pkg, "Sheet1")

        sheets = list_sheets(pkg)
        assert len(sheets) == 1
        assert sheets[0].name == "Sheet2"

    def test_delete_last_sheet_raises(self):
        """Cannot delete the last sheet."""
        pkg = ExcelPackage.new()
        with pytest.raises(ValueError, match="last sheet"):
            delete_sheet(pkg, "Sheet1")

    def test_delete_sheet_not_found(self):
        """Deleting non-existent sheet raises."""
        pkg = ExcelPackage.new()
        with pytest.raises(KeyError, match="not found"):
            delete_sheet(pkg, "NonExistent")


class TestCopySheet:
    """Tests for copy_sheet."""

    def test_copy_sheet(self):
        """Copy a sheet."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", 42)

        info = copy_sheet(pkg, "Sheet1", "Sheet1_Copy")

        assert info.name == "Sheet1_Copy"
        sheets = list_sheets(pkg)
        assert len(sheets) == 2

        # Check data was copied
        value, _, _ = get_cell_data(pkg, "Sheet1_Copy", "A1")
        assert value == 42

    def test_copy_to_existing_raises(self):
        """Copying to existing name raises."""
        pkg = ExcelPackage.new()
        with pytest.raises(ValueError, match="already exists"):
            copy_sheet(pkg, "Sheet1", "Sheet1")

    def test_copy_nonexistent_raises(self):
        """Copying non-existent sheet raises."""
        pkg = ExcelPackage.new()
        with pytest.raises(KeyError, match="not found"):
            copy_sheet(pkg, "NonExistent", "Copy")

    def test_copy_sheet_round_trip(self):
        """Copied sheet survives save/reload."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", 42)
        copy_sheet(pkg, "Sheet1", "Copy")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            pkg.save(f.name)
            pkg2 = ExcelPackage.open(f.name)

            sheets = list_sheets(pkg2)
            assert len(sheets) == 2

            value, _, _ = get_cell_data(pkg2, "Copy", "A1")
            assert value == 42

            Path(f.name).unlink()
