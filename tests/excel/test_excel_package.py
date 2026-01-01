"""Tests for ExcelPackage."""

from io import BytesIO

import pytest

from mcp_handley_lab.microsoft.excel.constants import CT, RT, qn
from mcp_handley_lab.microsoft.excel.package import ExcelPackage, SharedStrings


class TestSharedStrings:
    """Tests for SharedStrings class."""

    def test_empty_shared_strings(self):
        """Empty shared strings table."""
        sst = SharedStrings()
        assert len(sst) == 0
        assert not sst.is_dirty

    def test_add_string(self):
        """Adding a string returns index and marks dirty."""
        sst = SharedStrings()
        idx = sst.add("hello")
        assert idx == 0
        assert sst[0] == "hello"
        assert len(sst) == 1
        assert sst.is_dirty

    def test_get_or_add_deduplicates(self):
        """get_or_add returns existing index for duplicate strings."""
        sst = SharedStrings()
        idx1 = sst.get_or_add("hello")
        idx2 = sst.get_or_add("world")
        idx3 = sst.get_or_add("hello")  # Duplicate
        assert idx1 == 0
        assert idx2 == 1
        assert idx3 == 0  # Same as first
        assert len(sst) == 2  # Only 2 unique strings

    def test_round_trip_xml(self):
        """SharedStrings can be serialized and parsed."""
        sst = SharedStrings()
        sst.add("hello")
        sst.add("world")
        sst.add("test with spaces ")

        xml_bytes = sst.to_xml()
        parsed = SharedStrings.from_xml(xml_bytes)

        assert len(parsed) == 3
        assert parsed[0] == "hello"
        assert parsed[1] == "world"
        assert parsed[2] == "test with spaces "

    def test_whitespace_preservation(self):
        """Strings with leading/trailing whitespace are preserved."""
        sst = SharedStrings()
        sst.add(" leading")
        sst.add("trailing ")
        sst.add(" both ")

        xml_bytes = sst.to_xml()
        # Verify xml:space="preserve" is set
        assert b'xml:space="preserve"' in xml_bytes

        parsed = SharedStrings.from_xml(xml_bytes)
        assert parsed[0] == " leading"
        assert parsed[1] == "trailing "
        assert parsed[2] == " both "

    def test_from_xml_preserves_duplicate_index_stability(self):
        """Duplicates in SST preserve first occurrence index.

        Excel cells reference SST by index, so duplicates must maintain
        their original positions and get_or_add must return first index.
        """
        # Create SST with duplicates (simulating existing Excel file)
        sst = SharedStrings()
        sst._strings = ["hello", "world", "hello"]  # Duplicate at index 2
        sst._index = {"hello": 0, "world": 1}  # Only first occurrence in index

        xml_bytes = sst.to_xml()
        parsed = SharedStrings.from_xml(xml_bytes)

        # All strings preserved
        assert len(parsed) == 3
        assert parsed[0] == "hello"
        assert parsed[1] == "world"
        assert parsed[2] == "hello"

        # Index points to first occurrence, not last
        assert parsed.get_or_add("hello") == 0  # First occurrence
        assert parsed.get_or_add("world") == 1


class TestExcelPackageNew:
    """Tests for ExcelPackage.new() factory method."""

    def test_new_creates_valid_structure(self):
        """new() creates all required parts."""
        pkg = ExcelPackage.new()

        # Check package relationships
        pkg_rels = pkg.get_pkg_rels()
        assert pkg_rels.rId_for_reltype(RT.OFFICE_DOCUMENT) is not None
        assert pkg_rels.rId_for_reltype(RT.CORE_PROPERTIES) is not None

        # Check workbook exists
        assert pkg.has_part("/xl/workbook.xml")
        assert pkg.workbook_path == "/xl/workbook.xml"

        # Check sheet exists
        assert pkg.has_part("/xl/worksheets/sheet1.xml")

        # Check styles exists
        assert pkg.has_part("/xl/styles.xml")

    def test_new_has_one_sheet(self):
        """new() creates workbook with one sheet named 'Sheet1'."""
        pkg = ExcelPackage.new()
        sheets = pkg.get_sheet_paths()

        assert len(sheets) == 1
        name, rId, partname = sheets[0]
        assert name == "Sheet1"
        assert partname == "/xl/worksheets/sheet1.xml"

    def test_new_sheet_has_empty_sheet_data(self):
        """new() creates sheet with empty sheetData."""
        pkg = ExcelPackage.new()
        sheet = pkg.get_sheet_xml("Sheet1")
        sheet_data = sheet.find(qn("x:sheetData"))

        assert sheet_data is not None
        assert len(sheet_data) == 0  # No rows

    def test_new_content_types(self):
        """new() sets correct content types."""
        pkg = ExcelPackage.new()

        assert pkg.get_content_type("/xl/workbook.xml") == CT.SML_SHEET_MAIN
        assert pkg.get_content_type("/xl/worksheets/sheet1.xml") == CT.SML_WORKSHEET
        assert pkg.get_content_type("/xl/styles.xml") == CT.SML_STYLES


class TestExcelPackageSaveLoad:
    """Tests for saving and loading Excel packages."""

    def test_round_trip_to_file(self, tmp_path):
        """Package can be saved to file and loaded back."""
        file_path = tmp_path / "test.xlsx"

        # Create and save
        pkg1 = ExcelPackage.new()
        pkg1.save(file_path)

        assert file_path.exists()

        # Load and verify
        pkg2 = ExcelPackage.open(file_path)
        assert pkg2.workbook_path == "/xl/workbook.xml"
        sheets = pkg2.get_sheet_paths()
        assert len(sheets) == 1
        assert sheets[0][0] == "Sheet1"

    def test_round_trip_to_stream(self):
        """Package can be saved to stream and loaded back."""
        stream = BytesIO()

        # Create and save
        pkg1 = ExcelPackage.new()
        pkg1.save(stream)

        # Load and verify
        stream.seek(0)
        pkg2 = ExcelPackage.open(stream)
        sheets = pkg2.get_sheet_paths()
        assert len(sheets) == 1
        assert sheets[0][0] == "Sheet1"

    def test_shared_strings_saved_when_dirty(self, tmp_path):
        """Shared strings are saved only when modified."""
        file_path = tmp_path / "test.xlsx"

        # Create, add shared strings, and save
        pkg1 = ExcelPackage.new()
        pkg1.shared_strings.add("hello")
        pkg1.shared_strings.add("world")
        pkg1.save(file_path)

        # Load and verify shared strings
        pkg2 = ExcelPackage.open(file_path)
        assert len(pkg2.shared_strings) == 2
        assert pkg2.shared_strings[0] == "hello"
        assert pkg2.shared_strings[1] == "world"


class TestExcelPackageSheetAccess:
    """Tests for sheet access methods."""

    def test_get_sheet_xml_by_name(self):
        """get_sheet_xml returns sheet by name."""
        pkg = ExcelPackage.new()
        sheet = pkg.get_sheet_xml("Sheet1")
        assert sheet.tag == qn("x:worksheet")

    def test_get_sheet_xml_by_name_not_found(self):
        """get_sheet_xml raises KeyError for unknown sheet."""
        pkg = ExcelPackage.new()
        with pytest.raises(KeyError, match="Sheet not found"):
            pkg.get_sheet_xml("NonExistent")

    def test_get_sheet_xml_by_index(self):
        """get_sheet_xml_by_index returns sheet by 0-based index."""
        pkg = ExcelPackage.new()
        sheet = pkg.get_sheet_xml_by_index(0)
        assert sheet.tag == qn("x:worksheet")

    def test_get_sheet_xml_by_index_out_of_range(self):
        """get_sheet_xml_by_index raises IndexError for invalid index."""
        pkg = ExcelPackage.new()
        with pytest.raises(IndexError):
            pkg.get_sheet_xml_by_index(5)


class TestExcelPackageStyles:
    """Tests for styles access."""

    def test_styles_xml_exists(self):
        """styles_xml returns parsed styles from new workbook."""
        pkg = ExcelPackage.new()
        styles = pkg.styles_xml
        assert styles is not None
        assert styles.tag == qn("x:styleSheet")


class TestExcelPackageCalcChain:
    """Tests for calculation chain handling."""

    def test_drop_calc_chain_no_error_when_missing(self):
        """drop_calc_chain doesn't error when calcChain doesn't exist."""
        pkg = ExcelPackage.new()
        # Should not raise
        pkg.drop_calc_chain()
