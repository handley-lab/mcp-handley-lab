"""Tests for Excel operations (Phase 3)."""

import pytest
from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.ops.cells import get_cell_data, get_cells_in_range
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    index_to_column_letter,
    make_cell_ref,
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


class TestSheetOperations:
    """Tests for sheet operations."""

    def test_list_sheets_new_workbook(self):
        """New workbook has one sheet."""
        pkg = ExcelPackage.new()
        sheets = list_sheets(pkg)
        assert len(sheets) == 1
        assert sheets[0].name == "Sheet1"
        assert sheets[0].index == 0

    def test_get_used_range_empty_sheet(self):
        """Empty sheet returns None for used range."""
        pkg = ExcelPackage.new()
        used = get_used_range(pkg, "Sheet1")
        assert used is None


class TestCellOperations:
    """Tests for cell operations."""

    def test_get_cell_data_empty(self):
        """Empty cell returns None with no type."""
        pkg = ExcelPackage.new()
        value, type_code, formula = get_cell_data(pkg, "Sheet1", "A1")
        assert value is None
        assert type_code is None
        assert formula is None

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

    def test_get_cell_data_number(self, pkg_with_cell):
        """Numeric cell returns integer value and 'n' type."""
        value, type_code, formula = get_cell_data(pkg_with_cell, "Sheet1", "A1")
        assert value == 42  # Now returns int, not string
        assert type_code == "n"
        assert formula is None

    def test_get_cells_in_range_finds_cell(self, pkg_with_cell):
        """Range query finds cell with data."""
        cells = get_cells_in_range(pkg_with_cell, "Sheet1", "A1", "B2")
        assert len(cells) == 1
        ref, value, type_code, formula = cells[0]
        assert ref == "A1"
        assert value == 42  # Now returns int
        assert type_code == "n"
        assert formula is None

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

    def test_get_cell_data_shared_string(self, pkg_with_string_cell):
        """Shared string cell resolves correctly."""
        value, type_code, formula = get_cell_data(pkg_with_string_cell, "Sheet1", "A1")
        assert value == "Hello World"
        assert type_code == "s"
        assert formula is None

    @pytest.fixture
    def pkg_with_float_cell(self):
        """Create package with a float cell."""
        pkg = ExcelPackage.new()
        sheet = pkg.get_sheet_xml("Sheet1")
        sheet_data = sheet.find(qn("x:sheetData"))

        row = etree.SubElement(sheet_data, qn("x:row"), r="1")
        cell = etree.SubElement(row, qn("x:c"), r="A1")
        v = etree.SubElement(cell, qn("x:v"))
        v.text = "3.14159"

        pkg.mark_xml_dirty("/xl/worksheets/sheet1.xml")
        return pkg

    def test_get_cell_data_float(self, pkg_with_float_cell):
        """Float cell returns float value."""
        value, type_code, formula = get_cell_data(pkg_with_float_cell, "Sheet1", "A1")
        assert value == 3.14159
        assert isinstance(value, float)
        assert type_code == "n"

    @pytest.fixture
    def pkg_with_boolean_cell(self):
        """Create package with a boolean cell."""
        pkg = ExcelPackage.new()
        sheet = pkg.get_sheet_xml("Sheet1")
        sheet_data = sheet.find(qn("x:sheetData"))

        row = etree.SubElement(sheet_data, qn("x:row"), r="1")
        cell = etree.SubElement(row, qn("x:c"), r="A1", t="b")
        v = etree.SubElement(cell, qn("x:v"))
        v.text = "1"

        pkg.mark_xml_dirty("/xl/worksheets/sheet1.xml")
        return pkg

    def test_get_cell_data_boolean(self, pkg_with_boolean_cell):
        """Boolean cell returns Python bool."""
        value, type_code, formula = get_cell_data(pkg_with_boolean_cell, "Sheet1", "A1")
        assert value is True
        assert isinstance(value, bool)
        assert type_code == "b"

    @pytest.fixture
    def pkg_with_formula_cell(self):
        """Create package with a formula cell."""
        pkg = ExcelPackage.new()
        sheet = pkg.get_sheet_xml("Sheet1")
        sheet_data = sheet.find(qn("x:sheetData"))

        row = etree.SubElement(sheet_data, qn("x:row"), r="1")
        cell = etree.SubElement(row, qn("x:c"), r="A1")
        f = etree.SubElement(cell, qn("x:f"))
        f.text = "SUM(B1:B10)"
        v = etree.SubElement(cell, qn("x:v"))
        v.text = "100"

        pkg.mark_xml_dirty("/xl/worksheets/sheet1.xml")
        return pkg

    def test_get_cell_data_formula(self, pkg_with_formula_cell):
        """Formula cell returns value, formula type, and formula string."""
        value, type_code, formula = get_cell_data(pkg_with_formula_cell, "Sheet1", "A1")
        assert value == 100
        assert type_code == "f"  # Formula type
        assert formula == "SUM(B1:B10)"
