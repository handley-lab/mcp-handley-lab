"""Tests for Excel operations (Phase 3)."""

import pytest
from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.ops.cells import get_cell_value, get_cells_in_range
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    index_to_column_letter,
    make_cell_id,
    make_cell_ref,
    make_range_id,
    make_sheet_id,
    parse_cell_ref,
    parse_range_ref,
)
from mcp_handley_lab.microsoft.excel.ops.sheets import (
    get_used_range,
    list_sheets,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestCoreUtilities:
    """Tests for core cell addressing utilities."""

    def test_column_letter_to_index_single(self):
        """Single letters convert correctly."""
        assert column_letter_to_index("A") == 1
        assert column_letter_to_index("B") == 2
        assert column_letter_to_index("Z") == 26

    def test_column_letter_to_index_double(self):
        """Double letters convert correctly."""
        assert column_letter_to_index("AA") == 27
        assert column_letter_to_index("AB") == 28
        assert column_letter_to_index("AZ") == 52
        assert column_letter_to_index("BA") == 53

    def test_column_letter_to_index_case_insensitive(self):
        """Case insensitive conversion."""
        assert column_letter_to_index("a") == 1
        assert column_letter_to_index("aa") == 27

    def test_index_to_column_letter_single(self):
        """Single digit indices convert correctly."""
        assert index_to_column_letter(1) == "A"
        assert index_to_column_letter(2) == "B"
        assert index_to_column_letter(26) == "Z"

    def test_index_to_column_letter_double(self):
        """Double digit indices convert correctly."""
        assert index_to_column_letter(27) == "AA"
        assert index_to_column_letter(28) == "AB"
        assert index_to_column_letter(52) == "AZ"
        assert index_to_column_letter(53) == "BA"

    def test_roundtrip_column_conversion(self):
        """Column letter -> index -> letter roundtrip."""
        for i in range(1, 100):
            letter = index_to_column_letter(i)
            assert column_letter_to_index(letter) == i

    def test_parse_cell_ref_simple(self):
        """Simple cell references parse correctly."""
        col, row, col_abs, row_abs = parse_cell_ref("A1")
        assert col == "A"
        assert row == 1
        assert not col_abs
        assert not row_abs

    def test_parse_cell_ref_absolute(self):
        """Absolute references parse correctly."""
        col, row, col_abs, row_abs = parse_cell_ref("$B$2")
        assert col == "B"
        assert row == 2
        assert col_abs
        assert row_abs

    def test_parse_cell_ref_mixed(self):
        """Mixed absolute/relative references."""
        col, row, col_abs, row_abs = parse_cell_ref("$C3")
        assert col == "C"
        assert col_abs
        assert not row_abs

        col, row, col_abs, row_abs = parse_cell_ref("D$4")
        assert col == "D"
        assert not col_abs
        assert row_abs

    def test_parse_cell_ref_invalid(self):
        """Invalid references raise ValueError."""
        with pytest.raises(ValueError):
            parse_cell_ref("invalid")
        with pytest.raises(ValueError):
            parse_cell_ref("123")
        with pytest.raises(ValueError):
            parse_cell_ref("")

    def test_make_cell_ref_from_letter(self):
        """Create reference from column letter."""
        assert make_cell_ref("A", 1) == "A1"
        assert make_cell_ref("BC", 99) == "BC99"

    def test_make_cell_ref_from_index(self):
        """Create reference from column index."""
        assert make_cell_ref(1, 1) == "A1"
        assert make_cell_ref(27, 5) == "AA5"

    def test_make_cell_ref_absolute(self):
        """Create absolute references."""
        assert make_cell_ref("A", 1, col_abs=True) == "$A1"
        assert make_cell_ref("A", 1, row_abs=True) == "A$1"
        assert make_cell_ref("A", 1, col_abs=True, row_abs=True) == "$A$1"

    def test_parse_range_ref(self):
        """Range references parse correctly."""
        start, end = parse_range_ref("A1:C5")
        assert start == "A1"
        assert end == "C5"

    def test_parse_range_ref_invalid(self):
        """Invalid range references raise ValueError."""
        with pytest.raises(ValueError):
            parse_range_ref("A1")
        with pytest.raises(ValueError):
            parse_range_ref("invalid")


class TestContentAddressedIDs:
    """Tests for content-addressed ID generation."""

    def test_make_cell_id_basic(self):
        """Cell IDs contain sheet, ref, hash."""
        cell_id = make_cell_id("Sheet1", "A1", "hello")
        assert cell_id.startswith("cell_Sheet1_A1_")
        assert cell_id.endswith("_0")

    def test_make_cell_id_with_spaces(self):
        """Sheet names with spaces are handled."""
        cell_id = make_cell_id("My Sheet", "B2", "test")
        assert "My_Sheet" in cell_id

    def test_make_range_id_basic(self):
        """Range IDs contain sheet, ref, hash."""
        range_id = make_range_id("Sheet1", "A1:C5")
        assert range_id.startswith("range_Sheet1_A1C5_")

    def test_make_sheet_id_basic(self):
        """Sheet IDs contain name and hash."""
        sheet_id = make_sheet_id("Sheet1")
        assert sheet_id.startswith("sheet_Sheet1_")


class TestSheetOperations:
    """Tests for sheet operations."""

    def test_list_sheets_new_workbook(self):
        """New workbook has one sheet."""
        pkg = ExcelPackage.new()
        sheets = list_sheets(pkg)
        assert len(sheets) == 1
        assert sheets[0].name == "Sheet1"
        assert sheets[0].index == 0

    def test_list_sheets_ids_are_unique(self):
        """Sheet IDs are unique per sheet."""
        pkg = ExcelPackage.new()
        sheets = list_sheets(pkg)
        # Even with same name, different ordinals would be unique
        assert sheets[0].id.startswith("sheet_Sheet1_")

    def test_get_used_range_empty_sheet(self):
        """Empty sheet returns None for used range."""
        pkg = ExcelPackage.new()
        used = get_used_range(pkg, "Sheet1")
        assert used is None


class TestCellOperations:
    """Tests for cell operations."""

    def test_get_cell_value_empty(self):
        """Empty cell returns None, empty."""
        pkg = ExcelPackage.new()
        value, cell_type = get_cell_value(pkg, "Sheet1", "A1")
        assert value is None
        assert cell_type == "empty"

    def test_get_cells_in_range_empty(self):
        """Empty range returns empty list."""
        pkg = ExcelPackage.new()
        cells = get_cells_in_range(pkg, "Sheet1", "A1", "C3")
        assert cells == []


class TestCellWithData:
    """Tests for cells with actual data."""

    @pytest.fixture
    def pkg_with_cell(self):
        """Create package with a cell containing data."""
        pkg = ExcelPackage.new()
        sheet = pkg.get_sheet_xml("Sheet1")
        sheet_data = sheet.find(qn("x:sheetData"))

        # Add a row with a numeric cell
        row = etree.SubElement(sheet_data, qn("x:row"), r="1")
        cell = etree.SubElement(row, qn("x:c"), r="A1")
        v = etree.SubElement(cell, qn("x:v"))
        v.text = "42"

        pkg.mark_xml_dirty("/xl/worksheets/sheet1.xml")
        return pkg

    def test_get_cell_value_number(self, pkg_with_cell):
        """Numeric cell returns value and type."""
        value, cell_type = get_cell_value(pkg_with_cell, "Sheet1", "A1")
        assert value == "42"
        assert cell_type == "number"

    def test_get_cells_in_range_finds_cell(self, pkg_with_cell):
        """Range query finds cell with data."""
        cells = get_cells_in_range(pkg_with_cell, "Sheet1", "A1", "B2")
        assert len(cells) == 1
        assert cells[0][0] == "A1"
        assert cells[0][1] == "42"
        assert cells[0][2] == "number"

    def test_get_used_range_with_data(self, pkg_with_cell):
        """Used range detects cell."""
        used = get_used_range(pkg_with_cell, "Sheet1")
        assert used == "A1:A1"

    @pytest.fixture
    def pkg_with_string_cell(self):
        """Create package with a shared string cell."""
        pkg = ExcelPackage.new()

        # Add string to shared strings
        idx = pkg.shared_strings.add("Hello World")

        sheet = pkg.get_sheet_xml("Sheet1")
        sheet_data = sheet.find(qn("x:sheetData"))

        # Add a row with a string cell
        row = etree.SubElement(sheet_data, qn("x:row"), r="1")
        cell = etree.SubElement(row, qn("x:c"), r="A1", t="s")
        v = etree.SubElement(cell, qn("x:v"))
        v.text = str(idx)

        pkg.mark_xml_dirty("/xl/worksheets/sheet1.xml")
        return pkg

    def test_get_cell_value_shared_string(self, pkg_with_string_cell):
        """Shared string cell resolves correctly."""
        value, cell_type = get_cell_value(pkg_with_string_cell, "Sheet1", "A1")
        assert value == "Hello World"
        assert cell_type == "string"
