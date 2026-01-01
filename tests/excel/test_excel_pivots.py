"""Tests for Excel pivot table operations."""

import io

import pytest

from mcp_handley_lab.microsoft.excel.ops.cells import set_cell_value
from mcp_handley_lab.microsoft.excel.ops.pivots import (
    create_pivot,
    delete_pivot,
    list_pivots,
    refresh_pivot,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def _setup_sample_data(pkg: ExcelPackage, sheet: str = "Sheet1") -> None:
    """Create sample data for pivot table tests.

    Creates a sales dataset:
    | Region | Product | Sales |
    | North  | Widget  | 100   |
    | South  | Widget  | 150   |
    | North  | Gadget  | 200   |
    | South  | Gadget  | 250   |
    """
    # Headers
    set_cell_value(pkg, sheet, "A1", "Region")
    set_cell_value(pkg, sheet, "B1", "Product")
    set_cell_value(pkg, sheet, "C1", "Sales")

    # Data rows
    set_cell_value(pkg, sheet, "A2", "North")
    set_cell_value(pkg, sheet, "B2", "Widget")
    set_cell_value(pkg, sheet, "C2", 100)

    set_cell_value(pkg, sheet, "A3", "South")
    set_cell_value(pkg, sheet, "B3", "Widget")
    set_cell_value(pkg, sheet, "C3", 150)

    set_cell_value(pkg, sheet, "A4", "North")
    set_cell_value(pkg, sheet, "B4", "Gadget")
    set_cell_value(pkg, sheet, "C4", 200)

    set_cell_value(pkg, sheet, "A5", "South")
    set_cell_value(pkg, sheet, "B5", "Gadget")
    set_cell_value(pkg, sheet, "C5", 250)


class TestCreatePivot:
    """Tests for pivot table creation."""

    def test_create_simple_pivot(self) -> None:
        """Create a simple pivot table."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        pivot = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
        )

        assert pivot.name == "PivotTable1"
        assert "Sales" in pivot.value_fields
        assert "Region" in pivot.row_fields
        assert pivot.location == "E1"
        assert pivot.id is not None

    def test_create_pivot_with_custom_name(self) -> None:
        """Create pivot table with custom name."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        pivot = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            name="SalesByRegion",
        )

        assert pivot.name == "SalesByRegion"

    def test_create_pivot_with_row_and_col(self) -> None:
        """Create pivot with both row and column fields."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        pivot = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=["Product"],
            values=["Sales"],
        )

        assert "Region" in pivot.row_fields
        assert "Product" in pivot.col_fields
        assert "Sales" in pivot.value_fields

    def test_create_pivot_count_aggregation(self) -> None:
        """Create pivot with count aggregation."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        pivot = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            agg_func="count",
        )

        assert pivot is not None

    def test_create_pivot_average_aggregation(self) -> None:
        """Create pivot with average aggregation."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        pivot = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            agg_func="average",
        )

        assert pivot is not None

    def test_create_pivot_sheet_not_found_raises(self) -> None:
        """Non-existent sheet raises error."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        with pytest.raises(KeyError, match="Sheet not found"):
            create_pivot(
                pkg,
                "NonExistent",
                "A1:C5",
                "E1",
                rows=["Region"],
                cols=[],
                values=["Sales"],
            )

    def test_create_pivot_with_sheet_prefix(self) -> None:
        """Create pivot with sheet-prefixed data range."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        pivot = create_pivot(
            pkg,
            "Sheet1",
            "'Sheet1'!A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
        )

        assert pivot is not None
        assert "Sheet1" in pivot.data_range

    def test_create_multiple_pivots(self) -> None:
        """Create multiple pivot tables."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        pivot1 = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            name="Pivot1",
        )

        pivot2 = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E10",
            rows=["Product"],
            cols=[],
            values=["Sales"],
            name="Pivot2",
        )

        pivots = list_pivots(pkg, "Sheet1")
        assert len(pivots) == 2
        assert pivot1.id != pivot2.id


class TestListPivots:
    """Tests for listing pivot tables."""

    def test_list_pivots_empty(self) -> None:
        """List pivots on sheet with no pivots."""
        pkg = ExcelPackage.new()
        pivots = list_pivots(pkg, "Sheet1")
        assert pivots == []

    def test_list_pivots_after_create(self) -> None:
        """List pivots after creating."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            name="TestPivot",
        )

        pivots = list_pivots(pkg, "Sheet1")
        assert len(pivots) == 1
        assert pivots[0].name == "TestPivot"

    def test_list_pivots_sheet_not_found_raises(self) -> None:
        """Non-existent sheet raises error."""
        pkg = ExcelPackage.new()

        with pytest.raises(KeyError, match="Sheet not found"):
            list_pivots(pkg, "NonExistent")


class TestDeletePivot:
    """Tests for deleting pivot tables."""

    def test_delete_pivot(self) -> None:
        """Delete a pivot table."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        pivot = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
        )

        assert len(list_pivots(pkg, "Sheet1")) == 1

        delete_pivot(pkg, "Sheet1", pivot.id)

        assert len(list_pivots(pkg, "Sheet1")) == 0

    def test_delete_pivot_not_found_raises(self) -> None:
        """Delete non-existent pivot raises error."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        with pytest.raises(KeyError, match="Pivot table not found"):
            delete_pivot(pkg, "Sheet1", "nonexistent_id")

    def test_delete_one_of_multiple(self) -> None:
        """Delete one pivot, others remain."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        pivot1 = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            name="Pivot1",
        )

        pivot2 = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E10",
            rows=["Product"],
            cols=[],
            values=["Sales"],
            name="Pivot2",
        )

        delete_pivot(pkg, "Sheet1", pivot1.id)

        pivots = list_pivots(pkg, "Sheet1")
        assert len(pivots) == 1
        assert pivots[0].id == pivot2.id


class TestRefreshPivot:
    """Tests for refreshing pivot tables."""

    def test_refresh_pivot(self) -> None:
        """Refresh a pivot table cache."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        pivot = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
        )

        # Modify source data
        set_cell_value(pkg, "Sheet1", "C2", 999)

        # Refresh should not raise
        refresh_pivot(pkg, "Sheet1", pivot.id)

    def test_refresh_pivot_not_found_raises(self) -> None:
        """Refresh non-existent pivot raises error."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        with pytest.raises(KeyError, match="Pivot table not found"):
            refresh_pivot(pkg, "Sheet1", "nonexistent_id")


class TestPivotPersistence:
    """Tests for pivot table save/load."""

    def test_pivot_persists(self) -> None:
        """Pivot table survives save/load."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            name="PersistedPivot",
        )

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        pivots = list_pivots(pkg2, "Sheet1")
        assert len(pivots) == 1
        assert pivots[0].name == "PersistedPivot"
        assert "Region" in pivots[0].row_fields
        assert "Sales" in pivots[0].value_fields

    def test_multiple_pivots_persist(self) -> None:
        """Multiple pivot tables survive save/load."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            name="Pivot1",
        )

        create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E10",
            rows=["Product"],
            cols=[],
            values=["Sales"],
            name="Pivot2",
        )

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        pivots = list_pivots(pkg2, "Sheet1")
        assert len(pivots) == 2
        names = {p.name for p in pivots}
        assert names == {"Pivot1", "Pivot2"}


class TestPivotAggregationFunctions:
    """Tests for different aggregation functions."""

    def test_min_aggregation(self) -> None:
        """Create pivot with min aggregation."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        pivot = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            agg_func="min",
        )

        assert pivot is not None

    def test_max_aggregation(self) -> None:
        """Create pivot with max aggregation."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)

        pivot = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "E1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            agg_func="max",
        )

        assert pivot is not None


class TestMultipleCaches:
    """Tests for multiple caches (different source ranges)."""

    def _setup_second_data(self, pkg: ExcelPackage, sheet: str = "Sheet1") -> None:
        """Create a second data set in columns F-H."""
        # Headers
        set_cell_value(pkg, sheet, "F1", "Category")
        set_cell_value(pkg, sheet, "G1", "Year")
        set_cell_value(pkg, sheet, "H1", "Revenue")

        # Data rows
        set_cell_value(pkg, sheet, "F2", "Electronics")
        set_cell_value(pkg, sheet, "G2", 2023)
        set_cell_value(pkg, sheet, "H2", 1000)

        set_cell_value(pkg, sheet, "F3", "Clothing")
        set_cell_value(pkg, sheet, "G3", 2023)
        set_cell_value(pkg, sheet, "H3", 800)

        set_cell_value(pkg, sheet, "F4", "Electronics")
        set_cell_value(pkg, sheet, "G4", 2024)
        set_cell_value(pkg, sheet, "H4", 1200)

        set_cell_value(pkg, sheet, "F5", "Clothing")
        set_cell_value(pkg, sheet, "G5", 2024)
        set_cell_value(pkg, sheet, "H5", 900)

    def test_list_pivots_different_caches_correct_data_range(self) -> None:
        """List pivots with different caches returns correct data_range for each."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)
        self._setup_second_data(pkg)

        # Create two pivots with DIFFERENT source ranges (different caches)
        create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",  # First data range
            "J1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            name="SalesPivot",
        )

        create_pivot(
            pkg,
            "Sheet1",
            "F1:H5",  # Different data range - creates a different cache
            "J10",
            rows=["Category"],
            cols=[],
            values=["Revenue"],
            name="RevenuePivot",
        )

        # Verify both pivots have correct data ranges
        pivots = list_pivots(pkg, "Sheet1")
        assert len(pivots) == 2

        sales_pivot = next((p for p in pivots if p.name == "SalesPivot"), None)
        revenue_pivot = next((p for p in pivots if p.name == "RevenuePivot"), None)

        assert sales_pivot is not None
        assert revenue_pivot is not None
        assert "A1:C5" in sales_pivot.data_range
        assert "F1:H5" in revenue_pivot.data_range

    def test_list_pivots_different_caches_correct_fields(self) -> None:
        """List pivots with different caches returns correct field mappings."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)
        self._setup_second_data(pkg)

        create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "J1",
            rows=["Region"],
            cols=["Product"],
            values=["Sales"],
            name="SalesPivot",
        )

        create_pivot(
            pkg,
            "Sheet1",
            "F1:H5",
            "J10",
            rows=["Category"],
            cols=["Year"],
            values=["Revenue"],
            name="RevenuePivot",
        )

        pivots = list_pivots(pkg, "Sheet1")
        sales_pivot = next((p for p in pivots if p.name == "SalesPivot"), None)
        revenue_pivot = next((p for p in pivots if p.name == "RevenuePivot"), None)

        assert sales_pivot is not None
        assert revenue_pivot is not None

        # Check SalesPivot fields
        assert "Region" in sales_pivot.row_fields
        assert "Product" in sales_pivot.col_fields
        assert "Sales" in sales_pivot.value_fields

        # Check RevenuePivot fields (different fields from different source)
        assert "Category" in revenue_pivot.row_fields
        assert "Year" in revenue_pivot.col_fields
        assert "Revenue" in revenue_pivot.value_fields

    def test_delete_one_pivot_other_still_works(self) -> None:
        """Delete one pivot, verify other pivot still lists correctly."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)
        self._setup_second_data(pkg)

        pivot1 = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "J1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            name="SalesPivot",
        )

        create_pivot(
            pkg,
            "Sheet1",
            "F1:H5",
            "J10",
            rows=["Category"],
            cols=[],
            values=["Revenue"],
            name="RevenuePivot",
        )

        # Delete first pivot
        delete_pivot(pkg, "Sheet1", pivot1.id)

        # Verify second pivot still works
        pivots = list_pivots(pkg, "Sheet1")
        assert len(pivots) == 1
        assert pivots[0].name == "RevenuePivot"
        assert "F1:H5" in pivots[0].data_range
        assert "Category" in pivots[0].row_fields

    def test_delete_second_pivot_first_still_works(self) -> None:
        """Delete second pivot, verify first pivot still lists correctly."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)
        self._setup_second_data(pkg)

        create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "J1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            name="SalesPivot",
        )

        pivot2 = create_pivot(
            pkg,
            "Sheet1",
            "F1:H5",
            "J10",
            rows=["Category"],
            cols=[],
            values=["Revenue"],
            name="RevenuePivot",
        )

        # Delete second pivot
        delete_pivot(pkg, "Sheet1", pivot2.id)

        # Verify first pivot still works
        pivots = list_pivots(pkg, "Sheet1")
        assert len(pivots) == 1
        assert pivots[0].name == "SalesPivot"
        assert "A1:C5" in pivots[0].data_range
        assert "Region" in pivots[0].row_fields

    def test_multiple_caches_persist_after_save(self) -> None:
        """Multiple caches survive save/load correctly."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)
        self._setup_second_data(pkg)

        create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "J1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
            name="SalesPivot",
        )

        create_pivot(
            pkg,
            "Sheet1",
            "F1:H5",
            "J10",
            rows=["Category"],
            cols=[],
            values=["Revenue"],
            name="RevenuePivot",
        )

        # Save and reload
        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        # Verify both pivots have correct data after reload
        pivots = list_pivots(pkg2, "Sheet1")
        assert len(pivots) == 2

        sales_pivot = next((p for p in pivots if p.name == "SalesPivot"), None)
        revenue_pivot = next((p for p in pivots if p.name == "RevenuePivot"), None)

        assert sales_pivot is not None
        assert revenue_pivot is not None
        assert "A1:C5" in sales_pivot.data_range
        assert "F1:H5" in revenue_pivot.data_range

    def test_delete_all_pivots_cleans_up_caches(self) -> None:
        """Deleting all pivots cleans up all caches."""
        pkg = ExcelPackage.new()
        _setup_sample_data(pkg)
        self._setup_second_data(pkg)

        pivot1 = create_pivot(
            pkg,
            "Sheet1",
            "A1:C5",
            "J1",
            rows=["Region"],
            cols=[],
            values=["Sales"],
        )

        pivot2 = create_pivot(
            pkg,
            "Sheet1",
            "F1:H5",
            "J10",
            rows=["Category"],
            cols=[],
            values=["Revenue"],
        )

        # Delete both
        delete_pivot(pkg, "Sheet1", pivot1.id)
        delete_pivot(pkg, "Sheet1", pivot2.id)

        # Verify no pivots remain
        assert list_pivots(pkg, "Sheet1") == []

        # Save and reload to verify workbook is still valid
        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)
        assert list_pivots(pkg2, "Sheet1") == []
