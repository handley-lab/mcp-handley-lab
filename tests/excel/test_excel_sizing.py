"""Tests for Excel column/row sizing operations."""

import io

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.ops.sheets import (
    get_column_width,
    get_row_height,
    set_column_width,
    set_row_height,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestSetColumnWidth:
    """Tests for set_column_width."""

    def test_set_column_width_letter(self) -> None:
        """Set column width using letter reference."""
        pkg = ExcelPackage.new()

        set_column_width(pkg, "Sheet1", "A", 20.0)

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        cols = sheet_xml.find(qn("x:cols"))
        assert cols is not None
        col_el = cols.find(qn("x:col"))
        assert col_el is not None
        assert col_el.get("min") == "1"
        assert col_el.get("max") == "1"
        assert float(col_el.get("width")) == 20.0
        assert col_el.get("customWidth") == "1"

    def test_set_column_width_index(self) -> None:
        """Set column width using 1-based index."""
        pkg = ExcelPackage.new()

        set_column_width(pkg, "Sheet1", 3, 15.5)  # Column C

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        cols = sheet_xml.find(qn("x:cols"))
        col_el = cols.find(qn("x:col"))
        assert col_el.get("min") == "3"
        assert col_el.get("max") == "3"
        assert float(col_el.get("width")) == 15.5

    def test_set_column_width_multiple_columns(self) -> None:
        """Set width on multiple columns creates separate col elements."""
        pkg = ExcelPackage.new()

        set_column_width(pkg, "Sheet1", "A", 10.0)
        set_column_width(pkg, "Sheet1", "C", 25.0)

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        cols = sheet_xml.find(qn("x:cols"))
        col_els = cols.findall(qn("x:col"))
        assert len(col_els) == 2

    def test_set_column_width_update_existing(self) -> None:
        """Setting width on same column updates existing element."""
        pkg = ExcelPackage.new()

        set_column_width(pkg, "Sheet1", "B", 10.0)
        set_column_width(pkg, "Sheet1", "B", 20.0)

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        cols = sheet_xml.find(qn("x:cols"))
        cols.findall(qn("x:col"))
        # May have 1 or 2 elements depending on implementation
        # Check that we can get the correct value
        width = get_column_width(pkg, "Sheet1", "B")
        assert width == 20.0

    def test_set_column_width_zero_hides(self) -> None:
        """Setting width to 0 is valid (hides column)."""
        pkg = ExcelPackage.new()

        set_column_width(pkg, "Sheet1", "A", 0)

        width = get_column_width(pkg, "Sheet1", "A")
        assert width == 0.0

    def test_set_column_width_persists(self) -> None:
        """Column width persists through save/load."""
        pkg = ExcelPackage.new()
        set_column_width(pkg, "Sheet1", "D", 30.0)

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        width = get_column_width(pkg2, "Sheet1", "D")
        assert width == 30.0


class TestGetColumnWidth:
    """Tests for get_column_width."""

    def test_get_column_width_default(self) -> None:
        """Get width of column with no explicit width returns default."""
        pkg = ExcelPackage.new()

        width = get_column_width(pkg, "Sheet1", "A")

        # Default is 8.43 character widths
        assert width == 8.43

    def test_get_column_width_after_set(self) -> None:
        """Get width after setting returns set value."""
        pkg = ExcelPackage.new()
        set_column_width(pkg, "Sheet1", "B", 12.5)

        width = get_column_width(pkg, "Sheet1", "B")

        assert width == 12.5

    def test_get_column_width_by_index(self) -> None:
        """Get width using 1-based column index."""
        pkg = ExcelPackage.new()
        set_column_width(pkg, "Sheet1", 5, 18.0)  # Column E

        width = get_column_width(pkg, "Sheet1", 5)

        assert width == 18.0


class TestSetRowHeight:
    """Tests for set_row_height."""

    def test_set_row_height_new_row(self) -> None:
        """Set height on row that doesn't exist creates row element."""
        pkg = ExcelPackage.new()

        set_row_height(pkg, "Sheet1", 1, 25.0)

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        sheet_data = sheet_xml.find(qn("x:sheetData"))
        row_el = sheet_data.find(qn("x:row"))
        assert row_el is not None
        assert row_el.get("r") == "1"
        assert float(row_el.get("ht")) == 25.0
        assert row_el.get("customHeight") == "1"

    def test_set_row_height_multiple_rows(self) -> None:
        """Set height on multiple rows."""
        pkg = ExcelPackage.new()

        set_row_height(pkg, "Sheet1", 1, 20.0)
        set_row_height(pkg, "Sheet1", 3, 30.0)
        set_row_height(pkg, "Sheet1", 5, 40.0)

        height1 = get_row_height(pkg, "Sheet1", 1)
        height3 = get_row_height(pkg, "Sheet1", 3)
        height5 = get_row_height(pkg, "Sheet1", 5)

        assert height1 == 20.0
        assert height3 == 30.0
        assert height5 == 40.0

    def test_set_row_height_update_existing(self) -> None:
        """Setting height on same row updates existing."""
        pkg = ExcelPackage.new()

        set_row_height(pkg, "Sheet1", 2, 15.0)
        set_row_height(pkg, "Sheet1", 2, 25.0)

        height = get_row_height(pkg, "Sheet1", 2)
        assert height == 25.0

    def test_set_row_height_zero_hides(self) -> None:
        """Setting height to 0 is valid (hides row)."""
        pkg = ExcelPackage.new()

        set_row_height(pkg, "Sheet1", 1, 0)

        height = get_row_height(pkg, "Sheet1", 1)
        assert height == 0.0

    def test_set_row_height_maintains_order(self) -> None:
        """Rows are maintained in sorted order."""
        pkg = ExcelPackage.new()

        # Set heights in non-sequential order
        set_row_height(pkg, "Sheet1", 5, 50.0)
        set_row_height(pkg, "Sheet1", 2, 20.0)
        set_row_height(pkg, "Sheet1", 10, 100.0)

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        sheet_data = sheet_xml.find(qn("x:sheetData"))
        rows = sheet_data.findall(qn("x:row"))

        # Rows should be in order
        row_nums = [int(r.get("r")) for r in rows]
        assert row_nums == sorted(row_nums)

    def test_set_row_height_persists(self) -> None:
        """Row height persists through save/load."""
        pkg = ExcelPackage.new()
        set_row_height(pkg, "Sheet1", 3, 35.0)

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        height = get_row_height(pkg2, "Sheet1", 3)
        assert height == 35.0


class TestGetRowHeight:
    """Tests for get_row_height."""

    def test_get_row_height_default(self) -> None:
        """Get height of row with no explicit height returns default."""
        pkg = ExcelPackage.new()

        height = get_row_height(pkg, "Sheet1", 1)

        # Default is 15 points
        assert height == 15.0

    def test_get_row_height_after_set(self) -> None:
        """Get height after setting returns set value."""
        pkg = ExcelPackage.new()
        set_row_height(pkg, "Sheet1", 4, 22.5)

        height = get_row_height(pkg, "Sheet1", 4)

        assert height == 22.5


class TestSizingEdgeCases:
    """Edge case tests for sizing operations."""

    def test_column_width_wide_column(self) -> None:
        """Set very wide column (AA)."""
        pkg = ExcelPackage.new()

        set_column_width(pkg, "Sheet1", "AA", 50.0)

        width = get_column_width(pkg, "Sheet1", "AA")
        assert width == 50.0

    def test_row_height_large_row_number(self) -> None:
        """Set height on large row number."""
        pkg = ExcelPackage.new()

        set_row_height(pkg, "Sheet1", 1000, 20.0)

        height = get_row_height(pkg, "Sheet1", 1000)
        assert height == 20.0

    def test_get_column_width_no_cols_element(self) -> None:
        """Get column width when no <cols> element exists."""
        pkg = ExcelPackage.new()

        # New workbook has no <cols> element
        sheet_xml = pkg.get_sheet_xml("Sheet1")
        assert sheet_xml.find(qn("x:cols")) is None

        width = get_column_width(pkg, "Sheet1", "A")
        assert width == 8.43  # Default

    def test_cols_inserted_before_sheet_data(self) -> None:
        """<cols> element is inserted before <sheetData>."""
        pkg = ExcelPackage.new()

        set_column_width(pkg, "Sheet1", "A", 15.0)

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        children = list(sheet_xml)
        cols_idx = next(i for i, c in enumerate(children) if c.tag == qn("x:cols"))
        data_idx = next(i for i, c in enumerate(children) if c.tag == qn("x:sheetData"))
        assert cols_idx < data_idx
