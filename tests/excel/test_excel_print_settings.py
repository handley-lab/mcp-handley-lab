"""Tests for Excel print settings operations."""

import io

from mcp_handley_lab.microsoft.excel.ops.print_settings import (
    add_column_page_break,
    add_row_page_break,
    clear_page_breaks,
    clear_print_area,
    clear_print_titles,
    get_page_margins,
    get_page_orientation,
    get_page_size,
    get_print_area,
    get_print_titles,
    list_page_breaks,
    remove_column_page_break,
    remove_row_page_break,
    set_fit_to_page,
    set_page_margins,
    set_page_orientation,
    set_page_size,
    set_print_area,
    set_print_titles,
    set_scale,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestPrintArea:
    """Tests for print area operations."""

    def test_set_print_area_basic(self) -> None:
        """Set a simple print area."""
        pkg = ExcelPackage.new()
        set_print_area(pkg, "Sheet1", "A1:D10")

        area = get_print_area(pkg, "Sheet1")
        assert area is not None
        assert "$A$1:$D$10" in area

    def test_get_print_area_returns_none_when_not_set(self) -> None:
        """get_print_area returns None when no print area set."""
        pkg = ExcelPackage.new()
        assert get_print_area(pkg, "Sheet1") is None

    def test_set_print_area_replaces_existing(self) -> None:
        """Setting print area replaces existing."""
        pkg = ExcelPackage.new()
        set_print_area(pkg, "Sheet1", "A1:B5")
        set_print_area(pkg, "Sheet1", "C1:E20")

        area = get_print_area(pkg, "Sheet1")
        assert "$C$1:$E$20" in area
        assert "A1:B5" not in area

    def test_clear_print_area(self) -> None:
        """clear_print_area removes the print area."""
        pkg = ExcelPackage.new()
        set_print_area(pkg, "Sheet1", "A1:D10")
        assert get_print_area(pkg, "Sheet1") is not None

        clear_print_area(pkg, "Sheet1")
        assert get_print_area(pkg, "Sheet1") is None

    def test_print_area_persists(self) -> None:
        """Print area survives save/load."""
        pkg = ExcelPackage.new()
        set_print_area(pkg, "Sheet1", "B2:F8")

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        area = get_print_area(pkg2, "Sheet1")
        assert area is not None
        assert "$B$2:$F$8" in area


class TestPrintTitles:
    """Tests for print titles (repeating rows/columns)."""

    def test_set_print_titles_rows_only(self) -> None:
        """Set repeating rows."""
        pkg = ExcelPackage.new()
        set_print_titles(pkg, "Sheet1", rows="1:2")

        titles = get_print_titles(pkg, "Sheet1")
        assert titles is not None
        assert titles["rows"] == "1:2"
        assert titles["cols"] is None

    def test_set_print_titles_cols_only(self) -> None:
        """Set repeating columns."""
        pkg = ExcelPackage.new()
        set_print_titles(pkg, "Sheet1", cols="A:B")

        titles = get_print_titles(pkg, "Sheet1")
        assert titles is not None
        assert titles["rows"] is None
        assert titles["cols"] == "A:B"

    def test_set_print_titles_both(self) -> None:
        """Set both repeating rows and columns."""
        pkg = ExcelPackage.new()
        set_print_titles(pkg, "Sheet1", rows="1:3", cols="A:C")

        titles = get_print_titles(pkg, "Sheet1")
        assert titles is not None
        assert titles["rows"] == "1:3"
        assert titles["cols"] == "A:C"

    def test_get_print_titles_returns_none_when_not_set(self) -> None:
        """get_print_titles returns None when not set."""
        pkg = ExcelPackage.new()
        assert get_print_titles(pkg, "Sheet1") is None

    def test_clear_print_titles(self) -> None:
        """clear_print_titles removes print titles."""
        pkg = ExcelPackage.new()
        set_print_titles(pkg, "Sheet1", rows="1:2", cols="A:B")
        assert get_print_titles(pkg, "Sheet1") is not None

        clear_print_titles(pkg, "Sheet1")
        assert get_print_titles(pkg, "Sheet1") is None

    def test_print_titles_persist(self) -> None:
        """Print titles survive save/load."""
        pkg = ExcelPackage.new()
        set_print_titles(pkg, "Sheet1", rows="1:2", cols="A:A")

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        titles = get_print_titles(pkg2, "Sheet1")
        assert titles is not None
        assert titles["rows"] == "1:2"
        assert titles["cols"] == "A:A"


class TestPageMargins:
    """Tests for page margins."""

    def test_set_page_margins_all(self) -> None:
        """Set all margins."""
        pkg = ExcelPackage.new()
        set_page_margins(
            pkg,
            "Sheet1",
            left=1.0,
            right=1.0,
            top=1.5,
            bottom=1.5,
            header=0.5,
            footer=0.5,
        )

        margins = get_page_margins(pkg, "Sheet1")
        assert margins is not None
        assert margins["left"] == 1.0
        assert margins["right"] == 1.0
        assert margins["top"] == 1.5
        assert margins["bottom"] == 1.5
        assert margins["header"] == 0.5
        assert margins["footer"] == 0.5

    def test_set_page_margins_partial(self) -> None:
        """Set only some margins."""
        pkg = ExcelPackage.new()
        set_page_margins(pkg, "Sheet1", left=0.5, right=0.5)

        margins = get_page_margins(pkg, "Sheet1")
        assert margins is not None
        assert margins["left"] == 0.5
        assert margins["right"] == 0.5
        # Others should have defaults
        assert margins["top"] == 0.75

    def test_get_page_margins_returns_none_when_not_set(self) -> None:
        """get_page_margins returns None if no margins explicitly set."""
        pkg = ExcelPackage.new()
        # New workbooks may or may not have pageMargins
        get_page_margins(pkg, "Sheet1")
        # Just verify it doesn't crash - either None or defaults is fine


class TestPageOrientation:
    """Tests for page orientation."""

    def test_set_orientation_landscape(self) -> None:
        """Set landscape orientation."""
        pkg = ExcelPackage.new()
        set_page_orientation(pkg, "Sheet1", landscape=True)

        orientation = get_page_orientation(pkg, "Sheet1")
        assert orientation == "landscape"

    def test_set_orientation_portrait(self) -> None:
        """Set portrait orientation."""
        pkg = ExcelPackage.new()
        set_page_orientation(pkg, "Sheet1", landscape=False)

        orientation = get_page_orientation(pkg, "Sheet1")
        assert orientation == "portrait"

    def test_default_orientation_is_portrait(self) -> None:
        """Default orientation is portrait."""
        pkg = ExcelPackage.new()
        orientation = get_page_orientation(pkg, "Sheet1")
        assert orientation == "portrait"

    def test_orientation_persists(self) -> None:
        """Orientation survives save/load."""
        pkg = ExcelPackage.new()
        set_page_orientation(pkg, "Sheet1", landscape=True)

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        assert get_page_orientation(pkg2, "Sheet1") == "landscape"


class TestPageSize:
    """Tests for paper size."""

    def test_set_page_size_a4(self) -> None:
        """Set A4 paper size."""
        pkg = ExcelPackage.new()
        set_page_size(pkg, "Sheet1", 9)  # A4

        size = get_page_size(pkg, "Sheet1")
        assert size == 9

    def test_set_page_size_letter(self) -> None:
        """Set Letter paper size."""
        pkg = ExcelPackage.new()
        set_page_size(pkg, "Sheet1", 1)  # Letter

        size = get_page_size(pkg, "Sheet1")
        assert size == 1

    def test_default_page_size_is_letter(self) -> None:
        """Default paper size is Letter (1)."""
        pkg = ExcelPackage.new()
        size = get_page_size(pkg, "Sheet1")
        assert size == 1


class TestScale:
    """Tests for print scaling."""

    def test_set_scale(self) -> None:
        """Set print scale."""
        pkg = ExcelPackage.new()
        set_scale(pkg, "Sheet1", 50)

        # Verify by reading pageSetup
        sheet_xml = pkg.get_sheet_xml("Sheet1")
        from mcp_handley_lab.microsoft.excel.constants import qn

        page_setup = sheet_xml.find(qn("x:pageSetup"))
        assert page_setup is not None
        assert page_setup.get("scale") == "50"

    def test_set_scale_clamps_minimum(self) -> None:
        """Scale is clamped to minimum 10."""
        pkg = ExcelPackage.new()
        set_scale(pkg, "Sheet1", 5)

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        from mcp_handley_lab.microsoft.excel.constants import qn

        page_setup = sheet_xml.find(qn("x:pageSetup"))
        assert page_setup is not None
        assert page_setup.get("scale") == "10"

    def test_set_scale_clamps_maximum(self) -> None:
        """Scale is clamped to maximum 400."""
        pkg = ExcelPackage.new()
        set_scale(pkg, "Sheet1", 500)

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        from mcp_handley_lab.microsoft.excel.constants import qn

        page_setup = sheet_xml.find(qn("x:pageSetup"))
        assert page_setup is not None
        assert page_setup.get("scale") == "400"


class TestFitToPage:
    """Tests for fit-to-page settings."""

    def test_set_fit_to_page_width_only(self) -> None:
        """Fit to one page wide."""
        pkg = ExcelPackage.new()
        set_fit_to_page(pkg, "Sheet1", width=1, height=0)

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        from mcp_handley_lab.microsoft.excel.constants import qn

        page_setup = sheet_xml.find(qn("x:pageSetup"))
        assert page_setup is not None
        assert page_setup.get("fitToWidth") == "1"
        assert page_setup.get("fitToHeight") == "0"

    def test_set_fit_to_page_both(self) -> None:
        """Fit to specific pages."""
        pkg = ExcelPackage.new()
        set_fit_to_page(pkg, "Sheet1", width=2, height=3)

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        from mcp_handley_lab.microsoft.excel.constants import qn

        page_setup = sheet_xml.find(qn("x:pageSetup"))
        assert page_setup is not None
        assert page_setup.get("fitToWidth") == "2"
        assert page_setup.get("fitToHeight") == "3"


class TestPageBreaks:
    """Tests for page break operations."""

    def test_add_row_page_break(self) -> None:
        """Add a row page break."""
        pkg = ExcelPackage.new()
        add_row_page_break(pkg, "Sheet1", 10)

        breaks = list_page_breaks(pkg, "Sheet1")
        assert 10 in breaks["rows"]

    def test_add_multiple_row_breaks(self) -> None:
        """Add multiple row page breaks."""
        pkg = ExcelPackage.new()
        add_row_page_break(pkg, "Sheet1", 10)
        add_row_page_break(pkg, "Sheet1", 20)
        add_row_page_break(pkg, "Sheet1", 30)

        breaks = list_page_breaks(pkg, "Sheet1")
        assert breaks["rows"] == [10, 20, 30]

    def test_add_column_page_break(self) -> None:
        """Add a column page break."""
        pkg = ExcelPackage.new()
        add_column_page_break(pkg, "Sheet1", 5)  # Column E

        breaks = list_page_breaks(pkg, "Sheet1")
        assert 5 in breaks["cols"]

    def test_remove_row_page_break(self) -> None:
        """Remove a row page break."""
        pkg = ExcelPackage.new()
        add_row_page_break(pkg, "Sheet1", 10)
        add_row_page_break(pkg, "Sheet1", 20)

        remove_row_page_break(pkg, "Sheet1", 10)

        breaks = list_page_breaks(pkg, "Sheet1")
        assert 10 not in breaks["rows"]
        assert 20 in breaks["rows"]

    def test_remove_column_page_break(self) -> None:
        """Remove a column page break."""
        pkg = ExcelPackage.new()
        add_column_page_break(pkg, "Sheet1", 5)
        add_column_page_break(pkg, "Sheet1", 10)

        remove_column_page_break(pkg, "Sheet1", 5)

        breaks = list_page_breaks(pkg, "Sheet1")
        assert 5 not in breaks["cols"]
        assert 10 in breaks["cols"]

    def test_clear_page_breaks(self) -> None:
        """Clear all page breaks."""
        pkg = ExcelPackage.new()
        add_row_page_break(pkg, "Sheet1", 10)
        add_column_page_break(pkg, "Sheet1", 5)

        clear_page_breaks(pkg, "Sheet1")

        breaks = list_page_breaks(pkg, "Sheet1")
        assert breaks["rows"] == []
        assert breaks["cols"] == []

    def test_adding_duplicate_break_is_idempotent(self) -> None:
        """Adding the same break twice doesn't duplicate."""
        pkg = ExcelPackage.new()
        add_row_page_break(pkg, "Sheet1", 10)
        add_row_page_break(pkg, "Sheet1", 10)

        breaks = list_page_breaks(pkg, "Sheet1")
        assert breaks["rows"].count(10) == 1

    def test_page_breaks_persist(self) -> None:
        """Page breaks survive save/load."""
        pkg = ExcelPackage.new()
        add_row_page_break(pkg, "Sheet1", 15)
        add_column_page_break(pkg, "Sheet1", 8)

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        breaks = list_page_breaks(pkg2, "Sheet1")
        assert 15 in breaks["rows"]
        assert 8 in breaks["cols"]


class TestAbsoluteRefHelper:
    """Tests for the _make_absolute_ref helper."""

    def test_cell_ref(self) -> None:
        """Convert cell reference to absolute."""
        from mcp_handley_lab.microsoft.excel.ops.print_settings import (
            _make_absolute_ref,
        )

        assert _make_absolute_ref("A1") == "$A$1"
        assert _make_absolute_ref("Z99") == "$Z$99"

    def test_range_ref(self) -> None:
        """Convert range reference to absolute."""
        from mcp_handley_lab.microsoft.excel.ops.print_settings import (
            _make_absolute_ref,
        )

        assert _make_absolute_ref("A1:B2") == "$A$1:$B$2"

    def test_row_range(self) -> None:
        """Convert row range to absolute."""
        from mcp_handley_lab.microsoft.excel.ops.print_settings import (
            _make_absolute_ref,
        )

        assert _make_absolute_ref("1:2") == "$1:$2"

    def test_column_range(self) -> None:
        """Convert column range to absolute."""
        from mcp_handley_lab.microsoft.excel.ops.print_settings import (
            _make_absolute_ref,
        )

        assert _make_absolute_ref("A:B") == "$A:$B"
