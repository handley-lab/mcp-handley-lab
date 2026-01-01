"""Tests for Excel filtering and sorting operations."""

import io

import pytest

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.ops.filtering import (
    apply_filter,
    clear_autofilter,
    clear_filter,
    get_autofilter,
    set_autofilter,
    sort_range,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestGetAutofilter:
    """Tests for get_autofilter."""

    def test_get_autofilter_none(self) -> None:
        """New sheet has no autofilter."""
        pkg = ExcelPackage.new()

        result = get_autofilter(pkg, "Sheet1")

        assert result is None

    def test_get_autofilter_exists(self) -> None:
        """Get existing autofilter."""
        pkg = ExcelPackage.new()
        set_autofilter(pkg, "Sheet1", "A1:D10")

        result = get_autofilter(pkg, "Sheet1")

        assert result is not None
        assert result.ref == "A1:D10"
        assert result.filters is None

    def test_get_autofilter_with_filters(self) -> None:
        """Get autofilter with applied filters."""
        pkg = ExcelPackage.new()
        set_autofilter(pkg, "Sheet1", "A1:D10")
        apply_filter(pkg, "Sheet1", 0, ["Value1", "Value2"])

        result = get_autofilter(pkg, "Sheet1")

        assert result is not None
        assert result.filters is not None
        assert 0 in result.filters
        assert result.filters[0] == ["Value1", "Value2"]


class TestSetAutofilter:
    """Tests for set_autofilter."""

    def test_set_autofilter_creates_element(self) -> None:
        """Setting autofilter creates XML element."""
        pkg = ExcelPackage.new()

        result = set_autofilter(pkg, "Sheet1", "A1:C5")

        assert result.ref == "A1:C5"

        # Verify in XML
        sheet_xml = pkg.get_sheet_xml("Sheet1")
        autofilter = sheet_xml.find(qn("x:autoFilter"))
        assert autofilter is not None
        assert autofilter.get("ref") == "A1:C5"

    def test_set_autofilter_replaces_existing(self) -> None:
        """Setting autofilter replaces existing one."""
        pkg = ExcelPackage.new()
        set_autofilter(pkg, "Sheet1", "A1:C5")

        set_autofilter(pkg, "Sheet1", "A1:D10")

        result = get_autofilter(pkg, "Sheet1")
        assert result.ref == "A1:D10"

        # Only one autoFilter element
        sheet_xml = pkg.get_sheet_xml("Sheet1")
        autofilters = sheet_xml.findall(qn("x:autoFilter"))
        assert len(autofilters) == 1

    def test_set_autofilter_persists(self) -> None:
        """AutoFilter persists through save/load."""
        pkg = ExcelPackage.new()
        set_autofilter(pkg, "Sheet1", "A1:E20")

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        result = get_autofilter(pkg2, "Sheet1")
        assert result is not None
        assert result.ref == "A1:E20"


class TestClearAutofilter:
    """Tests for clear_autofilter."""

    def test_clear_autofilter_removes_element(self) -> None:
        """Clearing autofilter removes XML element."""
        pkg = ExcelPackage.new()
        set_autofilter(pkg, "Sheet1", "A1:C5")

        clear_autofilter(pkg, "Sheet1")

        result = get_autofilter(pkg, "Sheet1")
        assert result is None

        # Verify element removed
        sheet_xml = pkg.get_sheet_xml("Sheet1")
        assert sheet_xml.find(qn("x:autoFilter")) is None

    def test_clear_autofilter_no_effect_when_none(self) -> None:
        """Clearing when no autofilter is safe no-op."""
        pkg = ExcelPackage.new()

        # Should not raise
        clear_autofilter(pkg, "Sheet1")

        assert get_autofilter(pkg, "Sheet1") is None


class TestApplyFilter:
    """Tests for apply_filter."""

    def test_apply_filter_single_column(self) -> None:
        """Apply filter to a single column."""
        pkg = ExcelPackage.new()
        set_autofilter(pkg, "Sheet1", "A1:D10")

        result = apply_filter(pkg, "Sheet1", 0, ["Apple", "Banana"])

        assert result.filters is not None
        assert result.filters[0] == ["Apple", "Banana"]

    def test_apply_filter_multiple_columns(self) -> None:
        """Apply filters to multiple columns."""
        pkg = ExcelPackage.new()
        set_autofilter(pkg, "Sheet1", "A1:D10")
        apply_filter(pkg, "Sheet1", 0, ["A", "B"])
        apply_filter(pkg, "Sheet1", 2, ["X", "Y", "Z"])

        result = get_autofilter(pkg, "Sheet1")

        assert result.filters is not None
        assert result.filters[0] == ["A", "B"]
        assert result.filters[2] == ["X", "Y", "Z"]

    def test_apply_filter_replaces_existing(self) -> None:
        """Applying filter to column replaces existing filter."""
        pkg = ExcelPackage.new()
        set_autofilter(pkg, "Sheet1", "A1:D10")
        apply_filter(pkg, "Sheet1", 0, ["Old1", "Old2"])

        apply_filter(pkg, "Sheet1", 0, ["New1"])

        result = get_autofilter(pkg, "Sheet1")
        assert result.filters[0] == ["New1"]

    def test_apply_filter_no_autofilter_raises(self) -> None:
        """Applying filter without autofilter raises error."""
        pkg = ExcelPackage.new()

        with pytest.raises(ValueError, match="No AutoFilter"):
            apply_filter(pkg, "Sheet1", 0, ["Value"])

    def test_apply_filter_persists(self) -> None:
        """Applied filters persist through save/load."""
        pkg = ExcelPackage.new()
        set_autofilter(pkg, "Sheet1", "A1:D10")
        apply_filter(pkg, "Sheet1", 1, ["Filter1", "Filter2"])

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        result = get_autofilter(pkg2, "Sheet1")
        assert result.filters is not None
        assert result.filters[1] == ["Filter1", "Filter2"]


class TestClearFilter:
    """Tests for clear_filter."""

    def test_clear_filter_single_column(self) -> None:
        """Clear filter on a single column."""
        pkg = ExcelPackage.new()
        set_autofilter(pkg, "Sheet1", "A1:D10")
        apply_filter(pkg, "Sheet1", 0, ["A"])
        apply_filter(pkg, "Sheet1", 1, ["B"])

        clear_filter(pkg, "Sheet1", 0)

        result = get_autofilter(pkg, "Sheet1")
        assert 0 not in (result.filters or {})
        assert result.filters is not None
        assert result.filters[1] == ["B"]

    def test_clear_filter_no_autofilter(self) -> None:
        """Clearing filter with no autofilter returns None."""
        pkg = ExcelPackage.new()

        result = clear_filter(pkg, "Sheet1", 0)

        assert result is None

    def test_clear_filter_no_effect_when_no_filter(self) -> None:
        """Clearing non-existent filter is safe."""
        pkg = ExcelPackage.new()
        set_autofilter(pkg, "Sheet1", "A1:D10")

        # Should not raise
        result = clear_filter(pkg, "Sheet1", 5)

        assert result is not None
        assert result.filters is None


class TestSortRange:
    """Tests for sort_range."""

    def test_sort_range_single_column(self) -> None:
        """Sort by single column."""
        pkg = ExcelPackage.new()

        sort_range(pkg, "Sheet1", "A2:D10", 0)

        # Verify sortState in XML
        sheet_xml = pkg.get_sheet_xml("Sheet1")
        autofilter = sheet_xml.find(qn("x:autoFilter"))
        assert autofilter is not None
        sort_state = autofilter.find(qn("x:sortState"))
        assert sort_state is not None
        assert sort_state.get("ref") == "A2:D10"

    def test_sort_range_descending(self) -> None:
        """Sort descending."""
        pkg = ExcelPackage.new()

        sort_range(pkg, "Sheet1", "A2:D10", 0, descending=True)

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        sort_state = sheet_xml.find(qn("x:autoFilter")).find(qn("x:sortState"))
        sort_cond = sort_state.find(qn("x:sortCondition"))
        assert sort_cond.get("descending") == "1"

    def test_sort_range_multiple_columns(self) -> None:
        """Sort by multiple columns."""
        pkg = ExcelPackage.new()

        sort_range(pkg, "Sheet1", "A2:D10", [0, 2], descending=[False, True])

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        sort_state = sheet_xml.find(qn("x:autoFilter")).find(qn("x:sortState"))
        conditions = sort_state.findall(qn("x:sortCondition"))
        assert len(conditions) == 2
        assert conditions[0].get("descending") is None  # ascending
        assert conditions[1].get("descending") == "1"  # descending

    def test_sort_range_creates_autofilter(self) -> None:
        """Sorting creates autofilter if not present."""
        pkg = ExcelPackage.new()
        assert get_autofilter(pkg, "Sheet1") is None

        sort_range(pkg, "Sheet1", "A2:D10", 0)

        result = get_autofilter(pkg, "Sheet1")
        assert result is not None

    def test_sort_range_replaces_existing_sort(self) -> None:
        """Sorting replaces existing sort state."""
        pkg = ExcelPackage.new()
        sort_range(pkg, "Sheet1", "A2:D10", 0)

        sort_range(pkg, "Sheet1", "A2:D10", 2, descending=True)

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        sort_state = sheet_xml.find(qn("x:autoFilter")).find(qn("x:sortState"))
        conditions = sort_state.findall(qn("x:sortCondition"))
        assert len(conditions) == 1  # Only one sort condition
        assert "C" in conditions[0].get("ref")  # Column C (index 2)

    def test_sort_range_persists(self) -> None:
        """Sort state persists through save/load."""
        pkg = ExcelPackage.new()
        sort_range(pkg, "Sheet1", "A2:C5", 1, descending=True)

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        sheet_xml = pkg2.get_sheet_xml("Sheet1")
        sort_state = sheet_xml.find(qn("x:autoFilter")).find(qn("x:sortState"))
        assert sort_state is not None


class TestAutoFilterInfo:
    """Tests for AutoFilterInfo model."""

    def test_autofilter_info_basic(self) -> None:
        """AutoFilterInfo has expected fields."""
        pkg = ExcelPackage.new()
        set_autofilter(pkg, "Sheet1", "A1:D10")

        result = get_autofilter(pkg, "Sheet1")

        assert result.ref == "A1:D10"
        assert result.filters is None

    def test_autofilter_info_with_filters(self) -> None:
        """AutoFilterInfo includes filters when set."""
        pkg = ExcelPackage.new()
        set_autofilter(pkg, "Sheet1", "A1:D10")
        apply_filter(pkg, "Sheet1", 0, ["Val"])
        apply_filter(pkg, "Sheet1", 3, ["Other"])

        result = get_autofilter(pkg, "Sheet1")

        assert result.filters is not None
        assert len(result.filters) == 2
        assert result.filters[0] == ["Val"]
        assert result.filters[3] == ["Other"]
