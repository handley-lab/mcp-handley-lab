"""Tests for Excel edit operations (Phase 4)."""

import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.microsoft.excel.ops.cells import (
    get_cell_data,
    set_cell_formula,
    set_cell_value,
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


# =============================================================================
# Range Operations Tests
# =============================================================================


class TestGetRangeValues:
    """Tests for get_range_values."""

    def test_get_range_values(self):
        """Get values from a range."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", 1)
        set_cell_value(pkg, "Sheet1", "B1", 2)
        set_cell_value(pkg, "Sheet1", "A2", 3)
        set_cell_value(pkg, "Sheet1", "B2", 4)

        values = get_range_values(pkg, "Sheet1", "A1:B2")

        assert values == [[1, 2], [3, 4]]

    def test_get_range_with_empty_cells(self):
        """Get range with empty cells returns None."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", 1)
        set_cell_value(pkg, "Sheet1", "B2", 4)

        values = get_range_values(pkg, "Sheet1", "A1:B2")

        assert values == [[1, None], [None, 4]]

    def test_get_empty_range(self):
        """Get empty range returns grid of None."""
        pkg = ExcelPackage.new()
        values = get_range_values(pkg, "Sheet1", "A1:B2")

        assert values == [[None, None], [None, None]]


class TestSetRangeValues:
    """Tests for set_range_values."""

    def test_set_range_values(self):
        """Set values in a range."""
        pkg = ExcelPackage.new()
        count = set_range_values(pkg, "Sheet1", "A1", [[1, 2], [3, 4]])

        assert count == 4
        values = get_range_values(pkg, "Sheet1", "A1:B2")
        assert values == [[1, 2], [3, 4]]

    def test_set_range_mixed_types(self):
        """Set range with mixed types."""
        pkg = ExcelPackage.new()
        set_range_values(pkg, "Sheet1", "A1", [[1, "text"], [True, 3.14]])

        v1, _, _ = get_cell_data(pkg, "Sheet1", "A1")
        v2, _, _ = get_cell_data(pkg, "Sheet1", "B1")
        v3, _, _ = get_cell_data(pkg, "Sheet1", "A2")
        v4, _, _ = get_cell_data(pkg, "Sheet1", "B2")

        assert v1 == 1
        assert v2 == "text"
        assert v3 is True
        assert v4 == 3.14

    def test_set_range_empty_returns_zero(self):
        """Empty values returns 0."""
        pkg = ExcelPackage.new()
        count = set_range_values(pkg, "Sheet1", "A1", [])
        assert count == 0


class TestInsertRows:
    """Tests for insert_rows."""

    def test_insert_rows_shifts_data(self):
        """Insert rows shifts existing data down."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", "row1")
        set_cell_value(pkg, "Sheet1", "A2", "row2")

        insert_rows(pkg, "Sheet1", 2, 2)

        v1, _, _ = get_cell_data(pkg, "Sheet1", "A1")
        v2, _, _ = get_cell_data(pkg, "Sheet1", "A2")
        v3, _, _ = get_cell_data(pkg, "Sheet1", "A4")

        assert v1 == "row1"  # Row 1 unchanged
        assert v2 is None  # Inserted row
        assert v3 == "row2"  # Original row 2 shifted to row 4

    def test_insert_rows_zero_count(self):
        """Insert 0 rows does nothing."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", "test")

        insert_rows(pkg, "Sheet1", 1, 0)

        v1, _, _ = get_cell_data(pkg, "Sheet1", "A1")
        assert v1 == "test"


class TestDeleteRows:
    """Tests for delete_rows."""

    def test_delete_rows_removes_data(self):
        """Delete rows removes data and shifts up."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", "row1")
        set_cell_value(pkg, "Sheet1", "A2", "row2")
        set_cell_value(pkg, "Sheet1", "A3", "row3")

        delete_rows(pkg, "Sheet1", 2, 1)

        v1, _, _ = get_cell_data(pkg, "Sheet1", "A1")
        v2, _, _ = get_cell_data(pkg, "Sheet1", "A2")
        v3, _, _ = get_cell_data(pkg, "Sheet1", "A3")

        assert v1 == "row1"  # Row 1 unchanged
        assert v2 == "row3"  # Row 3 shifted up to row 2
        assert v3 is None  # No data in row 3 now

    def test_delete_multiple_rows(self):
        """Delete multiple rows."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", "row1")
        set_cell_value(pkg, "Sheet1", "A2", "row2")
        set_cell_value(pkg, "Sheet1", "A3", "row3")
        set_cell_value(pkg, "Sheet1", "A4", "row4")

        delete_rows(pkg, "Sheet1", 2, 2)

        v1, _, _ = get_cell_data(pkg, "Sheet1", "A1")
        v2, _, _ = get_cell_data(pkg, "Sheet1", "A2")

        assert v1 == "row1"
        assert v2 == "row4"  # Row 4 shifted up to row 2


class TestInsertColumns:
    """Tests for insert_columns."""

    def test_insert_columns_shifts_data(self):
        """Insert columns shifts existing data right."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", "colA")
        set_cell_value(pkg, "Sheet1", "B1", "colB")

        insert_columns(pkg, "Sheet1", "B", 2)

        vA, _, _ = get_cell_data(pkg, "Sheet1", "A1")
        vB, _, _ = get_cell_data(pkg, "Sheet1", "B1")
        vD, _, _ = get_cell_data(pkg, "Sheet1", "D1")

        assert vA == "colA"  # Column A unchanged
        assert vB is None  # Inserted column
        assert vD == "colB"  # Original column B shifted to D

    def test_insert_columns_with_index(self):
        """Insert columns using numeric index."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", "colA")
        set_cell_value(pkg, "Sheet1", "B1", "colB")

        insert_columns(pkg, "Sheet1", 2, 1)  # Column B (index 2)

        vA, _, _ = get_cell_data(pkg, "Sheet1", "A1")
        vC, _, _ = get_cell_data(pkg, "Sheet1", "C1")

        assert vA == "colA"
        assert vC == "colB"


class TestDeleteColumns:
    """Tests for delete_columns."""

    def test_delete_columns_removes_data(self):
        """Delete columns removes data and shifts left."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", "colA")
        set_cell_value(pkg, "Sheet1", "B1", "colB")
        set_cell_value(pkg, "Sheet1", "C1", "colC")

        delete_columns(pkg, "Sheet1", "B", 1)

        vA, _, _ = get_cell_data(pkg, "Sheet1", "A1")
        vB, _, _ = get_cell_data(pkg, "Sheet1", "B1")
        vC, _, _ = get_cell_data(pkg, "Sheet1", "C1")

        assert vA == "colA"
        assert vB == "colC"  # Column C shifted to B
        assert vC is None


class TestMergeCells:
    """Tests for merge_cells."""

    def test_merge_cells(self):
        """Merge cells clears non-top-left cells."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", "top-left")
        set_cell_value(pkg, "Sheet1", "B1", "to-clear")
        set_cell_value(pkg, "Sheet1", "A2", "to-clear")
        set_cell_value(pkg, "Sheet1", "B2", "to-clear")

        merge_cells(pkg, "Sheet1", "A1:B2")

        v1, _, _ = get_cell_data(pkg, "Sheet1", "A1")
        v2, _, _ = get_cell_data(pkg, "Sheet1", "B1")
        v3, _, _ = get_cell_data(pkg, "Sheet1", "A2")

        assert v1 == "top-left"  # Preserved
        assert v2 is None  # Cleared
        assert v3 is None  # Cleared

    def test_merge_overlapping_raises(self):
        """Merging overlapping range raises."""
        pkg = ExcelPackage.new()
        merge_cells(pkg, "Sheet1", "A1:B2")

        with pytest.raises(ValueError, match="overlaps"):
            merge_cells(pkg, "Sheet1", "B2:C3")


class TestUnmergeCells:
    """Tests for unmerge_cells."""

    def test_unmerge_cells(self):
        """Unmerge cells removes merge."""
        pkg = ExcelPackage.new()
        merge_cells(pkg, "Sheet1", "A1:B2")

        # Should not raise
        unmerge_cells(pkg, "Sheet1", "A1:B2")

        # Can merge again after unmerge
        merge_cells(pkg, "Sheet1", "A1:B2")

    def test_unmerge_not_found_raises(self):
        """Unmerging non-existent merge raises."""
        pkg = ExcelPackage.new()
        with pytest.raises(ValueError, match="(not found|No merged cells)"):
            unmerge_cells(pkg, "Sheet1", "A1:B2")


class TestRangeRoundTrip:
    """Round-trip tests for range operations."""

    def test_merge_round_trip(self):
        """Merge survives save/reload."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", "merged")
        merge_cells(pkg, "Sheet1", "A1:B2")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            pkg.save(f.name)
            pkg2 = ExcelPackage.open(f.name)

            # Value preserved
            v, _, _ = get_cell_data(pkg2, "Sheet1", "A1")
            assert v == "merged"

            # Can unmerge (proves merge was saved)
            unmerge_cells(pkg2, "Sheet1", "A1:B2")

            Path(f.name).unlink()

    def test_insert_delete_round_trip(self):
        """Insert/delete survives save/reload."""
        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", "row1")
        set_cell_value(pkg, "Sheet1", "A2", "row2")
        insert_rows(pkg, "Sheet1", 2, 1)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            pkg.save(f.name)
            pkg2 = ExcelPackage.open(f.name)

            v1, _, _ = get_cell_data(pkg2, "Sheet1", "A1")
            v3, _, _ = get_cell_data(pkg2, "Sheet1", "A3")

            assert v1 == "row1"
            assert v3 == "row2"

            Path(f.name).unlink()


class TestRecalculate:
    """Tests for recalculate operation."""

    def test_recalculate_populates_formula_values(self):
        """Recalculate should populate cached values for formulas."""
        import shutil

        from mcp_handley_lab.microsoft.excel.tool import _edit_recalculate

        if not shutil.which("libreoffice"):
            pytest.skip("LibreOffice not installed")

        pkg = ExcelPackage.new()
        set_cell_value(pkg, "Sheet1", "A1", 10)
        set_cell_value(pkg, "Sheet1", "A2", 20)
        set_cell_formula(pkg, "Sheet1", "A3", "SUM(A1:A2)")

        # Before recalculate: formula cell has no cached value
        value, type_code, formula = get_cell_data(pkg, "Sheet1", "A3")
        assert formula == "SUM(A1:A2)"
        assert value is None  # No cached value yet

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            pkg.save(f.name)

            # Recalculate using LibreOffice
            result = _edit_recalculate(f.name)
            assert result["success"] is True

            # Reload and check cached value
            pkg2 = ExcelPackage.open(f.name)
            value, type_code, formula = get_cell_data(pkg2, "Sheet1", "A3")
            assert formula == "SUM(A1:A2)"
            assert value == 30  # Now has cached value

            Path(f.name).unlink()
