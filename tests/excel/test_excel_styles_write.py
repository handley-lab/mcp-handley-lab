"""Tests for Excel style creation operations."""

import io

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.ops.formatting import (
    get_number_format,
    get_style_by_index,
    list_styles,
)
from mcp_handley_lab.microsoft.excel.ops.styles_write import (
    create_border,
    create_cell_style,
    create_fill,
    create_font,
    create_number_format,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestCreateFont:
    """Tests for create_font."""

    def test_create_font_default(self) -> None:
        """Create font with default settings."""
        pkg = ExcelPackage.new()
        initial_count = len(pkg.styles_xml.find(qn("x:fonts")).findall(qn("x:font")))

        font_id = create_font(pkg)

        fonts = pkg.styles_xml.find(qn("x:fonts"))
        assert int(fonts.get("count")) == initial_count + 1
        assert font_id == initial_count

    def test_create_font_custom_name_size(self) -> None:
        """Create font with custom name and size."""
        pkg = ExcelPackage.new()

        font_id = create_font(pkg, name="Arial", size=14)

        fonts = pkg.styles_xml.find(qn("x:fonts"))
        font = fonts.findall(qn("x:font"))[font_id]
        assert font.find(qn("x:name")).get("val") == "Arial"
        assert font.find(qn("x:sz")).get("val") == "14"

    def test_create_font_bold_italic(self) -> None:
        """Create bold italic font."""
        pkg = ExcelPackage.new()

        font_id = create_font(pkg, bold=True, italic=True)

        fonts = pkg.styles_xml.find(qn("x:fonts"))
        font = fonts.findall(qn("x:font"))[font_id]
        assert font.find(qn("x:b")) is not None
        assert font.find(qn("x:i")) is not None

    def test_create_font_underline(self) -> None:
        """Create underlined font."""
        pkg = ExcelPackage.new()

        font_id = create_font(pkg, underline=True)

        fonts = pkg.styles_xml.find(qn("x:fonts"))
        font = fonts.findall(qn("x:font"))[font_id]
        assert font.find(qn("x:u")) is not None

    def test_create_font_color(self) -> None:
        """Create font with color."""
        pkg = ExcelPackage.new()

        font_id = create_font(pkg, color="FF0000")

        fonts = pkg.styles_xml.find(qn("x:fonts"))
        font = fonts.findall(qn("x:font"))[font_id]
        color = font.find(qn("x:color"))
        assert color is not None
        assert color.get("rgb") == "FFFF0000"

    def test_create_font_color_with_hash(self) -> None:
        """Create font with color including # prefix."""
        pkg = ExcelPackage.new()

        font_id = create_font(pkg, color="#00FF00")

        fonts = pkg.styles_xml.find(qn("x:fonts"))
        font = fonts.findall(qn("x:font"))[font_id]
        color = font.find(qn("x:color"))
        assert color.get("rgb") == "FF00FF00"

    def test_create_font_persists_after_save(self) -> None:
        """Created font persists through save/load cycle."""
        pkg = ExcelPackage.new()
        create_font(pkg, name="Courier New", size=12, bold=True)

        # Save and reload
        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        fonts = pkg2.styles_xml.find(qn("x:fonts"))
        # Should have at least 2 fonts now (default + created)
        assert int(fonts.get("count")) >= 2


class TestCreateFill:
    """Tests for create_fill."""

    def test_create_fill_solid(self) -> None:
        """Create solid fill."""
        pkg = ExcelPackage.new()
        initial_count = len(pkg.styles_xml.find(qn("x:fills")).findall(qn("x:fill")))

        fill_id = create_fill(pkg, pattern="solid", fg_color="FFFF00")

        fills = pkg.styles_xml.find(qn("x:fills"))
        assert int(fills.get("count")) == initial_count + 1
        fill = fills.findall(qn("x:fill"))[fill_id]
        pattern = fill.find(qn("x:patternFill"))
        assert pattern.get("patternType") == "solid"
        assert pattern.find(qn("x:fgColor")).get("rgb") == "FFFFFF00"

    def test_create_fill_none(self) -> None:
        """Create no fill."""
        pkg = ExcelPackage.new()

        fill_id = create_fill(pkg, pattern="none")

        fills = pkg.styles_xml.find(qn("x:fills"))
        fill = fills.findall(qn("x:fill"))[fill_id]
        pattern = fill.find(qn("x:patternFill"))
        assert pattern.get("patternType") == "none"

    def test_create_fill_with_bg_color(self) -> None:
        """Create fill with both fg and bg colors."""
        pkg = ExcelPackage.new()

        fill_id = create_fill(
            pkg, pattern="gray125", fg_color="FF0000", bg_color="0000FF"
        )

        fills = pkg.styles_xml.find(qn("x:fills"))
        fill = fills.findall(qn("x:fill"))[fill_id]
        pattern = fill.find(qn("x:patternFill"))
        assert pattern.find(qn("x:fgColor")).get("rgb") == "FFFF0000"
        assert pattern.find(qn("x:bgColor")).get("rgb") == "FF0000FF"


class TestCreateBorder:
    """Tests for create_border."""

    def test_create_border_default(self) -> None:
        """Create border with no sides."""
        pkg = ExcelPackage.new()
        initial_count = len(
            pkg.styles_xml.find(qn("x:borders")).findall(qn("x:border"))
        )

        border_id = create_border(pkg)

        borders = pkg.styles_xml.find(qn("x:borders"))
        assert int(borders.get("count")) == initial_count + 1
        assert border_id == initial_count

    def test_create_border_thin_all_sides(self) -> None:
        """Create thin border on all sides."""
        pkg = ExcelPackage.new()

        border_id = create_border(
            pkg, left="thin", right="thin", top="thin", bottom="thin"
        )

        borders = pkg.styles_xml.find(qn("x:borders"))
        border = borders.findall(qn("x:border"))[border_id]
        assert border.find(qn("x:left")).get("style") == "thin"
        assert border.find(qn("x:right")).get("style") == "thin"
        assert border.find(qn("x:top")).get("style") == "thin"
        assert border.find(qn("x:bottom")).get("style") == "thin"

    def test_create_border_thick_with_color(self) -> None:
        """Create thick border with color."""
        pkg = ExcelPackage.new()

        border_id = create_border(pkg, left="thick", color="0000FF")

        borders = pkg.styles_xml.find(qn("x:borders"))
        border = borders.findall(qn("x:border"))[border_id]
        left = border.find(qn("x:left"))
        assert left.get("style") == "thick"
        assert left.find(qn("x:color")).get("rgb") == "FF0000FF"

    def test_create_border_mixed_styles(self) -> None:
        """Create border with different styles per side."""
        pkg = ExcelPackage.new()

        border_id = create_border(
            pkg, left="thin", right="medium", top="thick", bottom="dotted"
        )

        borders = pkg.styles_xml.find(qn("x:borders"))
        border = borders.findall(qn("x:border"))[border_id]
        assert border.find(qn("x:left")).get("style") == "thin"
        assert border.find(qn("x:right")).get("style") == "medium"
        assert border.find(qn("x:top")).get("style") == "thick"
        assert border.find(qn("x:bottom")).get("style") == "dotted"


class TestCreateNumberFormat:
    """Tests for create_number_format."""

    def test_create_number_format_starts_at_164(self) -> None:
        """Custom number formats start at ID 164."""
        pkg = ExcelPackage.new()

        fmt_id = create_number_format(pkg, "#,##0.00")

        # Custom formats start at 164
        assert fmt_id >= 164

    def test_create_number_format_currency(self) -> None:
        """Create currency format."""
        pkg = ExcelPackage.new()

        fmt_id = create_number_format(pkg, '"$"#,##0.00')

        # Verify it can be retrieved
        fmt = get_number_format(pkg, fmt_id)
        assert fmt == '"$"#,##0.00'

    def test_create_number_format_date(self) -> None:
        """Create custom date format."""
        pkg = ExcelPackage.new()

        fmt_id = create_number_format(pkg, "yyyy-mm-dd")

        fmt = get_number_format(pkg, fmt_id)
        assert fmt == "yyyy-mm-dd"

    def test_create_multiple_number_formats(self) -> None:
        """Create multiple number formats with sequential IDs."""
        pkg = ExcelPackage.new()

        fmt_id1 = create_number_format(pkg, "#,##0")
        fmt_id2 = create_number_format(pkg, "0.00%")
        fmt_id3 = create_number_format(pkg, "yyyy/mm/dd")

        # IDs should be sequential
        assert fmt_id2 == fmt_id1 + 1
        assert fmt_id3 == fmt_id2 + 1


class TestCreateCellStyle:
    """Tests for create_cell_style."""

    def test_create_cell_style_default(self) -> None:
        """Create cell style with defaults."""
        pkg = ExcelPackage.new()
        initial_count = len(pkg.styles_xml.find(qn("x:cellXfs")).findall(qn("x:xf")))

        style_id = create_cell_style(pkg)

        cell_xfs = pkg.styles_xml.find(qn("x:cellXfs"))
        assert int(cell_xfs.get("count")) == initial_count + 1
        assert style_id == initial_count

    def test_create_cell_style_with_font(self) -> None:
        """Create cell style with custom font."""
        pkg = ExcelPackage.new()

        font_id = create_font(pkg, bold=True, size=14)
        style_id = create_cell_style(pkg, font_id=font_id)

        cell_xfs = pkg.styles_xml.find(qn("x:cellXfs"))
        xf = cell_xfs.findall(qn("x:xf"))[style_id]
        assert xf.get("fontId") == str(font_id)
        assert xf.get("applyFont") == "1"

    def test_create_cell_style_with_fill(self) -> None:
        """Create cell style with custom fill."""
        pkg = ExcelPackage.new()

        fill_id = create_fill(pkg, pattern="solid", fg_color="FFFF00")
        style_id = create_cell_style(pkg, fill_id=fill_id)

        cell_xfs = pkg.styles_xml.find(qn("x:cellXfs"))
        xf = cell_xfs.findall(qn("x:xf"))[style_id]
        assert xf.get("fillId") == str(fill_id)
        assert xf.get("applyFill") == "1"

    def test_create_cell_style_with_border(self) -> None:
        """Create cell style with custom border."""
        pkg = ExcelPackage.new()

        border_id = create_border(pkg, left="thin", right="thin")
        style_id = create_cell_style(pkg, border_id=border_id)

        cell_xfs = pkg.styles_xml.find(qn("x:cellXfs"))
        xf = cell_xfs.findall(qn("x:xf"))[style_id]
        assert xf.get("borderId") == str(border_id)
        assert xf.get("applyBorder") == "1"

    def test_create_cell_style_with_number_format(self) -> None:
        """Create cell style with custom number format."""
        pkg = ExcelPackage.new()

        num_fmt_id = create_number_format(pkg, "#,##0.00")
        style_id = create_cell_style(pkg, num_fmt_id=num_fmt_id)

        cell_xfs = pkg.styles_xml.find(qn("x:cellXfs"))
        xf = cell_xfs.findall(qn("x:xf"))[style_id]
        assert xf.get("numFmtId") == str(num_fmt_id)
        assert xf.get("applyNumberFormat") == "1"

    def test_create_cell_style_combined(self) -> None:
        """Create cell style combining all elements."""
        pkg = ExcelPackage.new()

        font_id = create_font(pkg, name="Arial", bold=True, color="FF0000")
        fill_id = create_fill(pkg, pattern="solid", fg_color="FFFF00")
        border_id = create_border(
            pkg, left="thin", right="thin", top="thin", bottom="thin"
        )
        num_fmt_id = create_number_format(pkg, '"$"#,##0.00')

        style_id = create_cell_style(
            pkg,
            font_id=font_id,
            fill_id=fill_id,
            border_id=border_id,
            num_fmt_id=num_fmt_id,
        )

        cell_xfs = pkg.styles_xml.find(qn("x:cellXfs"))
        xf = cell_xfs.findall(qn("x:xf"))[style_id]
        assert xf.get("fontId") == str(font_id)
        assert xf.get("fillId") == str(fill_id)
        assert xf.get("borderId") == str(border_id)
        assert xf.get("numFmtId") == str(num_fmt_id)

    def test_create_cell_style_visible_in_list_styles(self) -> None:
        """Created style appears in list_styles."""
        pkg = ExcelPackage.new()

        font_id = create_font(pkg, bold=True)
        style_id = create_cell_style(pkg, font_id=font_id)

        styles = list_styles(pkg)
        assert len(styles) > style_id
        style = get_style_by_index(pkg, style_id)
        assert style.index == style_id
        # Font should show bold
        assert style.font is not None
        assert "bold" in style.font.lower()


class TestStaleCountAttribute:
    """Tests for handling stale/incorrect count attributes."""

    def test_create_font_with_stale_count(self) -> None:
        """Create font works even when count attribute is wrong."""
        pkg = ExcelPackage.new()

        # Corrupt the count attribute
        fonts = pkg.styles_xml.find(qn("x:fonts"))
        fonts.set("count", "999")  # Wrong count

        # Should still work correctly
        font_id = create_font(pkg, bold=True)

        # Index should be based on actual children, not the stale count
        fonts = pkg.styles_xml.find(qn("x:fonts"))
        actual_count = len(fonts.findall(qn("x:font")))
        assert font_id == actual_count - 1
        assert fonts.get("count") == str(actual_count)

    def test_create_fill_with_missing_count(self) -> None:
        """Create fill works when count attribute is missing."""
        pkg = ExcelPackage.new()

        # Remove the count attribute
        fills = pkg.styles_xml.find(qn("x:fills"))
        if "count" in fills.attrib:
            del fills.attrib["count"]

        # Should still work correctly
        fill_id = create_fill(pkg, pattern="solid", fg_color="FF0000")

        fills = pkg.styles_xml.find(qn("x:fills"))
        actual_count = len(fills.findall(qn("x:fill")))
        assert fill_id == actual_count - 1
        assert fills.get("count") == str(actual_count)

    def test_multiple_creations_correct_indices(self) -> None:
        """Multiple sequential creations return correct indices."""
        pkg = ExcelPackage.new()

        # Create multiple fonts
        id1 = create_font(pkg, name="Arial")
        id2 = create_font(pkg, name="Helvetica")
        id3 = create_font(pkg, name="Verdana")

        # Indices should be sequential from the initial count
        assert id2 == id1 + 1
        assert id3 == id2 + 1

        # Count should match actual children
        fonts = pkg.styles_xml.find(qn("x:fonts"))
        actual_count = len(fonts.findall(qn("x:font")))
        assert fonts.get("count") == str(actual_count)


class TestStylePersistence:
    """Tests for style persistence through save/load."""

    def test_full_style_round_trip(self) -> None:
        """Full style with all components persists through save/load."""
        pkg = ExcelPackage.new()

        font_id = create_font(
            pkg, name="Times New Roman", size=12, bold=True, italic=True
        )
        fill_id = create_fill(pkg, pattern="solid", fg_color="00FF00")
        border_id = create_border(pkg, left="medium", right="medium", color="000000")
        num_fmt_id = create_number_format(pkg, "0.000")
        style_id = create_cell_style(
            pkg,
            font_id=font_id,
            fill_id=fill_id,
            border_id=border_id,
            num_fmt_id=num_fmt_id,
        )

        # Save and reload
        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        # Verify style exists
        style = get_style_by_index(pkg2, style_id)
        assert style.index == style_id
        assert style.font is not None
        assert "Times New Roman" in style.font
        assert "bold" in style.font.lower()
        assert style.fill is not None
        assert "00FF00" in style.fill.upper()
        assert style.border is not None
        assert "medium" in style.border
        assert style.number_format == "0.000"
