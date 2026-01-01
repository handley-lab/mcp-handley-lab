"""Tests for Excel formatting operations."""

import pytest

from mcp_handley_lab.microsoft.excel.ops.formatting import (
    get_number_format,
    get_style_by_index,
    list_styles,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestListStyles:
    """Tests for list_styles."""

    def test_list_styles_new_workbook(self) -> None:
        """New workbook has at least one default style."""
        pkg = ExcelPackage.new()
        styles = list_styles(pkg)

        # New workbook should have at least the default style
        assert len(styles) >= 1
        assert styles[0].index == 0

    def test_list_styles_has_font_info(self) -> None:
        """Style info includes font description."""
        pkg = ExcelPackage.new()
        styles = list_styles(pkg)

        # Default style should have font info
        assert styles[0].font is not None
        assert "Calibri" in styles[0].font or styles[0].font == "default"


class TestGetStyleByIndex:
    """Tests for get_style_by_index."""

    def test_get_style_by_index_valid(self) -> None:
        """Get style by valid index returns StyleInfo."""
        pkg = ExcelPackage.new()

        style = get_style_by_index(pkg, 0)
        assert style.index == 0

    def test_get_style_by_index_invalid(self) -> None:
        """Get style by invalid index raises IndexError."""
        pkg = ExcelPackage.new()

        with pytest.raises(IndexError, match="out of range"):
            get_style_by_index(pkg, 999)


class TestGetNumberFormat:
    """Tests for get_number_format."""

    def test_get_builtin_format_general(self) -> None:
        """Get built-in format 0 returns 'General'."""
        pkg = ExcelPackage.new()

        fmt = get_number_format(pkg, 0)
        assert fmt == "General"

    def test_get_builtin_format_number(self) -> None:
        """Get built-in number formats."""
        pkg = ExcelPackage.new()

        assert get_number_format(pkg, 1) == "0"
        assert get_number_format(pkg, 2) == "0.00"
        assert get_number_format(pkg, 3) == "#,##0"
        assert get_number_format(pkg, 4) == "#,##0.00"

    def test_get_builtin_format_percent(self) -> None:
        """Get built-in percent formats."""
        pkg = ExcelPackage.new()

        assert get_number_format(pkg, 9) == "0%"
        assert get_number_format(pkg, 10) == "0.00%"

    def test_get_builtin_format_date(self) -> None:
        """Get built-in date formats."""
        pkg = ExcelPackage.new()

        assert get_number_format(pkg, 14) == "mm-dd-yy"
        assert get_number_format(pkg, 22) == "m/d/yy h:mm"

    def test_get_builtin_format_text(self) -> None:
        """Get built-in text format."""
        pkg = ExcelPackage.new()

        assert get_number_format(pkg, 49) == "@"

    def test_get_unknown_format_returns_none(self) -> None:
        """Get unknown format ID returns None."""
        pkg = ExcelPackage.new()

        # ID 999 is not a built-in format and not in styles.xml
        result = get_number_format(pkg, 999)
        assert result is None


class TestStyleInfo:
    """Tests for StyleInfo structure."""

    def test_style_info_fields(self) -> None:
        """StyleInfo has expected fields."""
        pkg = ExcelPackage.new()
        styles = list_styles(pkg)

        if styles:
            style = styles[0]
            # These fields should exist (may be None)
            assert hasattr(style, "index")
            assert hasattr(style, "font")
            assert hasattr(style, "fill")
            assert hasattr(style, "border")
            assert hasattr(style, "number_format")
