"""Tests for shared chart XML builders and embedding utilities."""

from __future__ import annotations

import io

import pytest
from lxml import etree

from mcp_handley_lab.microsoft.common.charts import (
    CHART_NSMAP,
    _col_letter,
    compute_chart_refs,
    create_chart_xml,
    validate_chart_data,
)
from mcp_handley_lab.microsoft.common.embedding import create_embedded_excel
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestColLetter:
    """Tests for _col_letter column index conversion."""

    def test_single_letters(self):
        assert _col_letter(0) == "A"
        assert _col_letter(1) == "B"
        assert _col_letter(25) == "Z"

    def test_double_letters(self):
        assert _col_letter(26) == "AA"
        assert _col_letter(27) == "AB"
        assert _col_letter(51) == "AZ"
        assert _col_letter(52) == "BA"


class TestComputeChartRefs:
    """Tests for compute_chart_refs dimension-to-range conversion."""

    def test_single_series(self):
        cat_range, series = compute_chart_refs("Sheet1", n_rows=4, n_cols=2)
        assert cat_range == "'Sheet1'!$A$2:$A$4"
        assert len(series) == 1
        name_ref, name_text, val_range = series[0]
        assert name_ref == "'Sheet1'!$B$1"
        assert val_range == "'Sheet1'!$B$2:$B$4"

    def test_multi_series(self):
        cat_range, series = compute_chart_refs("Data", n_rows=5, n_cols=4)
        assert cat_range == "'Data'!$A$2:$A$5"
        assert len(series) == 3
        # Series B, C, D
        assert series[0][0] == "'Data'!$B$1"
        assert series[0][2] == "'Data'!$B$2:$B$5"
        assert series[1][0] == "'Data'!$C$1"
        assert series[2][0] == "'Data'!$D$1"

    def test_single_data_row(self):
        cat_range, series = compute_chart_refs("S", n_rows=2, n_cols=2)
        assert cat_range == "'S'!$A$2:$A$2"
        assert len(series) == 1
        assert series[0][2] == "'S'!$B$2:$B$2"


class TestCreateChartXml:
    """Tests for the shared chart XML builder."""

    def _ns(self, tag: str) -> str:
        return f"{{{CHART_NSMAP['c']}}}{tag}"

    def test_bar_chart(self):
        xml = create_chart_xml(
            "bar",
            "Sheet1",
            "'S'!$A$2:$A$3",
            [("'S'!$B$1", "S1", "'S'!$B$2:$B$3")],
            title="Sales",
        )
        chart = xml.find(self._ns("chart"))
        assert chart is not None
        plot = chart.find(self._ns("plotArea"))
        bar = plot.find(self._ns("barChart"))
        assert bar is not None
        bar_dir = bar.find(self._ns("barDir"))
        assert bar_dir.get("val") == "bar"

    def test_column_chart(self):
        xml = create_chart_xml(
            "column",
            "Sheet1",
            "'S'!$A$2:$A$3",
            [("'S'!$B$1", "S1", "'S'!$B$2:$B$3")],
        )
        chart = xml.find(self._ns("chart"))
        plot = chart.find(self._ns("plotArea"))
        bar = plot.find(self._ns("barChart"))
        assert bar is not None
        bar_dir = bar.find(self._ns("barDir"))
        assert bar_dir.get("val") == "col"

    def test_line_chart(self):
        xml = create_chart_xml(
            "line",
            "Sheet1",
            "'S'!$A$2:$A$3",
            [("'S'!$B$1", "S1", "'S'!$B$2:$B$3")],
        )
        chart = xml.find(self._ns("chart"))
        plot = chart.find(self._ns("plotArea"))
        assert plot.find(self._ns("lineChart")) is not None

    def test_pie_chart(self):
        xml = create_chart_xml(
            "pie",
            "Sheet1",
            "'S'!$A$2:$A$3",
            [("'S'!$B$1", "S1", "'S'!$B$2:$B$3")],
        )
        chart = xml.find(self._ns("chart"))
        plot = chart.find(self._ns("plotArea"))
        assert plot.find(self._ns("pieChart")) is not None

    def test_scatter_chart_has_xval_yval(self):
        xml = create_chart_xml(
            "scatter",
            "Sheet1",
            "'S'!$A$2:$A$3",
            [("'S'!$B$1", "S1", "'S'!$B$2:$B$3")],
        )
        chart = xml.find(self._ns("chart"))
        plot = chart.find(self._ns("plotArea"))
        scatter = plot.find(self._ns("scatterChart"))
        assert scatter is not None
        ser = scatter.find(self._ns("ser"))
        assert ser.find(self._ns("xVal")) is not None
        assert ser.find(self._ns("yVal")) is not None

    def test_area_chart(self):
        xml = create_chart_xml(
            "area",
            "Sheet1",
            "'S'!$A$2:$A$3",
            [("'S'!$B$1", "S1", "'S'!$B$2:$B$3")],
        )
        chart = xml.find(self._ns("chart"))
        plot = chart.find(self._ns("plotArea"))
        assert plot.find(self._ns("areaChart")) is not None

    def test_invalid_chart_type(self):
        with pytest.raises(ValueError, match="Unsupported chart type"):
            create_chart_xml("radar", "S", "r", [("", "", "r")])

    def test_title_present(self):
        xml = create_chart_xml(
            "column",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
            title="Revenue",
        )
        chart = xml.find(self._ns("chart"))
        title_elem = chart.find(self._ns("title"))
        assert title_elem is not None
        # autoTitleDeleted should be 0
        atd = chart.find(self._ns("autoTitleDeleted"))
        assert atd.get("val") == "0"

    def test_no_title_sets_autotitledeleted(self):
        xml = create_chart_xml(
            "column",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
        )
        chart = xml.find(self._ns("chart"))
        title_elem = chart.find(self._ns("title"))
        assert title_elem is None
        atd = chart.find(self._ns("autoTitleDeleted"))
        assert atd.get("val") == "1"

    def test_external_data_rid(self):
        xml = create_chart_xml(
            "column",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
            external_data_rid="rId1",
        )
        ext_data = xml.find(self._ns("externalData"))
        assert ext_data is not None
        r_ns = CHART_NSMAP["r"]
        assert ext_data.get(f"{{{r_ns}}}id") == "rId1"
        auto = ext_data.find(self._ns("autoUpdate"))
        assert auto.get("val") == "0"

    def test_no_external_data_without_rid(self):
        xml = create_chart_xml(
            "column",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
        )
        assert xml.find(self._ns("externalData")) is None

    def test_multi_series(self):
        xml = create_chart_xml(
            "bar",
            "S",
            "'S'!$A$2:$A$3",
            [
                ("'S'!$B$1", "S1", "'S'!$B$2:$B$3"),
                ("'S'!$C$1", "S2", "'S'!$C$2:$C$3"),
            ],
        )
        chart = xml.find(self._ns("chart"))
        plot = chart.find(self._ns("plotArea"))
        bar = plot.find(self._ns("barChart"))
        sers = bar.findall(self._ns("ser"))
        assert len(sers) == 2
        # Check idx/order
        assert sers[0].find(self._ns("idx")).get("val") == "0"
        assert sers[1].find(self._ns("idx")).get("val") == "1"

    def test_categories_none_skips_cat(self):
        """Excel simple mode: no categories_range, no c:cat elements."""
        xml = create_chart_xml(
            "column",
            "S",
            categories_range=None,
            series=[("", "", "'S'!$A$1:$A$5")],
        )
        chart = xml.find(self._ns("chart"))
        plot = chart.find(self._ns("plotArea"))
        bar = plot.find(self._ns("barChart"))
        ser = bar.find(self._ns("ser"))
        # Should have val but NOT cat
        assert ser.find(self._ns("val")) is not None
        assert ser.find(self._ns("cat")) is None

    def test_scatter_no_categories_skips_xval(self):
        """Excel simple scatter: no xVal, only yVal."""
        xml = create_chart_xml(
            "scatter",
            "S",
            categories_range=None,
            series=[("", "", "'S'!$A$1:$A$5")],
        )
        chart = xml.find(self._ns("chart"))
        scatter = chart.find(self._ns("plotArea")).find(self._ns("scatterChart"))
        ser = scatter.find(self._ns("ser"))
        assert ser.find(self._ns("xVal")) is None
        assert ser.find(self._ns("yVal")) is not None

    def test_series_name_ref_creates_sertx(self):
        """When name_ref is provided, c:serTx is emitted."""
        xml = create_chart_xml(
            "line",
            "S",
            "'S'!$A$2:$A$3",
            [("'S'!$B$1", "Revenue", "'S'!$B$2:$B$3")],
        )
        chart = xml.find(self._ns("chart"))
        line = chart.find(self._ns("plotArea")).find(self._ns("lineChart"))
        ser = line.find(self._ns("ser"))
        tx = ser.find(self._ns("tx"))
        assert tx is not None

    def test_empty_name_ref_no_sertx(self):
        """When name_ref is empty string, c:serTx is NOT emitted."""
        xml = create_chart_xml(
            "line",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
        )
        chart = xml.find(self._ns("chart"))
        line = chart.find(self._ns("plotArea")).find(self._ns("lineChart"))
        ser = line.find(self._ns("ser"))
        tx = ser.find(self._ns("tx"))
        assert tx is None

    def test_pie_chart_no_axes(self):
        """Pie charts have no axes."""
        xml = create_chart_xml(
            "pie",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
        )
        chart = xml.find(self._ns("chart"))
        plot = chart.find(self._ns("plotArea"))
        assert plot.find(self._ns("catAx")) is None
        assert plot.find(self._ns("valAx")) is None

    def test_non_pie_chart_has_axes(self):
        """Non-pie charts have category and value axes."""
        xml = create_chart_xml(
            "column",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
        )
        chart = xml.find(self._ns("chart"))
        plot = chart.find(self._ns("plotArea"))
        assert plot.find(self._ns("catAx")) is not None
        assert plot.find(self._ns("valAx")) is not None

    def test_scatter_has_two_valax(self):
        """Scatter charts use valAx for both axes."""
        xml = create_chart_xml(
            "scatter",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
        )
        chart = xml.find(self._ns("chart"))
        plot = chart.find(self._ns("plotArea"))
        val_axes = plot.findall(self._ns("valAx"))
        assert len(val_axes) == 2
        assert plot.find(self._ns("catAx")) is None

    def test_print_settings_present(self):
        xml = create_chart_xml(
            "column",
            "S",
            None,
            [("", "", "'S'!$A$1:$A$5")],
        )
        assert xml.find(self._ns("printSettings")) is not None

    def test_legend_present(self):
        xml = create_chart_xml(
            "column",
            "S",
            None,
            [("", "", "'S'!$A$1:$A$5")],
        )
        chart = xml.find(self._ns("chart"))
        assert chart.find(self._ns("legend")) is not None


class TestCreateEmbeddedExcel:
    """Tests for the embedded Excel workbook creation utility."""

    def test_basic_creation(self):
        data = [["Cat", "S1", "S2"], ["A", 10, 30], ["B", 20, 40]]
        xlsx_bytes, sheet_name, n_rows, n_cols = create_embedded_excel(data)
        assert isinstance(xlsx_bytes, bytes)
        assert len(xlsx_bytes) > 0
        assert sheet_name == "Sheet1"
        assert n_rows == 3
        assert n_cols == 3

    def test_single_column(self):
        data = [["Value"], [100], [200], [300]]
        xlsx_bytes, sheet_name, n_rows, n_cols = create_embedded_excel(data)
        assert n_rows == 4
        assert n_cols == 1

    def test_default_sheet_name(self):
        data = [["X"], [1]]
        xlsx_bytes, sheet_name, n_rows, n_cols = create_embedded_excel(data)
        assert sheet_name == "Sheet1"

    def test_valid_xlsx(self):
        """The returned bytes can be opened as a valid Excel package."""
        data = [["Cat", "S1"], ["A", 10], ["B", 20]]
        xlsx_bytes, sheet_name, n_rows, n_cols = create_embedded_excel(data)

        pkg = ExcelPackage.open(io.BytesIO(xlsx_bytes))
        sheet_names = [name for name, _rId, _path in pkg.get_sheet_paths()]
        assert sheet_name in sheet_names

    def test_data_roundtrip(self):
        """Values written are readable from the resulting workbook."""
        data = [["Name", "Score"], ["Alice", 95], ["Bob", 87]]
        xlsx_bytes, sheet_name, n_rows, n_cols = create_embedded_excel(data)

        from mcp_handley_lab.microsoft.excel.ops.cells import get_cell_value

        pkg = ExcelPackage.open(io.BytesIO(xlsx_bytes))
        assert get_cell_value(pkg, sheet_name, "A1") == "Name"
        assert get_cell_value(pkg, sheet_name, "B1") == "Score"
        assert get_cell_value(pkg, sheet_name, "A2") == "Alice"
        assert get_cell_value(pkg, sheet_name, "B2") == 95


class TestValidateChartData:
    """Tests for validate_chart_data input validation."""

    def test_empty_data(self):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_chart_data([])

    def test_single_row(self):
        with pytest.raises(ValueError, match="at least 2 rows"):
            validate_chart_data([["Cat", "S1"]])

    def test_single_column(self):
        with pytest.raises(ValueError, match="at least 2 columns"):
            validate_chart_data([["Cat"], ["A"]])

    def test_jagged_rows(self):
        with pytest.raises(ValueError, match="rectangular"):
            validate_chart_data([["Cat", "S1"], ["A"]])

    def test_valid_data(self):
        # Should not raise
        validate_chart_data([["Cat", "S1"], ["A", 10]])

    def test_valid_multi_series(self):
        # Should not raise
        validate_chart_data([["Cat", "S1", "S2"], ["A", 10, 20], ["B", 30, 40]])


class TestCreateChartXmlValidation:
    """Tests for input validation in create_chart_xml."""

    def test_invalid_chart_type(self):
        with pytest.raises(ValueError, match="Unsupported chart type"):
            create_chart_xml("radar", "S", "r", [("", "", "r")])

    def test_empty_series(self):
        with pytest.raises(ValueError, match="At least one data series"):
            create_chart_xml("column", "S", "'S'!$A$2:$A$3", [])


class TestScatterAxes:
    """Tests for scatter chart axes (two valAx, no catAx properties)."""

    def _ns(self, tag: str) -> str:
        return f"{{{CHART_NSMAP['c']}}}{tag}"

    def test_scatter_no_catax(self):
        xml = create_chart_xml(
            "scatter",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
        )
        plot = xml.find(self._ns("chart")).find(self._ns("plotArea"))
        assert plot.find(self._ns("catAx")) is None

    def test_scatter_two_valax(self):
        xml = create_chart_xml(
            "scatter",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
        )
        plot = xml.find(self._ns("chart")).find(self._ns("plotArea"))
        val_axes = plot.findall(self._ns("valAx"))
        assert len(val_axes) == 2

    def test_scatter_x_axis_position_bottom(self):
        xml = create_chart_xml(
            "scatter",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
        )
        plot = xml.find(self._ns("chart")).find(self._ns("plotArea"))
        val_axes = plot.findall(self._ns("valAx"))
        # First valAx (X axis) should be at bottom
        ax_pos = val_axes[0].find(self._ns("axPos"))
        assert ax_pos.get("val") == "b"

    def test_scatter_y_axis_position_left(self):
        xml = create_chart_xml(
            "scatter",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
        )
        plot = xml.find(self._ns("chart")).find(self._ns("plotArea"))
        val_axes = plot.findall(self._ns("valAx"))
        # Second valAx (Y axis) should be at left
        ax_pos = val_axes[1].find(self._ns("axPos"))
        assert ax_pos.get("val") == "l"

    def test_scatter_axes_no_catax_properties(self):
        """Scatter valAx should NOT have catAx-only properties: auto, lblAlgn, lblOffset."""
        xml = create_chart_xml(
            "scatter",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
        )
        plot = xml.find(self._ns("chart")).find(self._ns("plotArea"))
        for val_ax in plot.findall(self._ns("valAx")):
            assert val_ax.find(self._ns("auto")) is None
            assert val_ax.find(self._ns("lblAlgn")) is None
            assert val_ax.find(self._ns("lblOffset")) is None

    def test_scatter_axes_have_numfmt(self):
        """Both scatter valAx should have numFmt (value axis property)."""
        xml = create_chart_xml(
            "scatter",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
        )
        plot = xml.find(self._ns("chart")).find(self._ns("plotArea"))
        for val_ax in plot.findall(self._ns("valAx")):
            assert val_ax.find(self._ns("numFmt")) is not None

    def test_non_scatter_catax_has_catax_properties(self):
        """Non-scatter catAx should have auto, lblAlgn, lblOffset."""
        xml = create_chart_xml(
            "column",
            "S",
            "'S'!$A$2:$A$3",
            [("", "", "'S'!$B$2:$B$3")],
        )
        plot = xml.find(self._ns("chart")).find(self._ns("plotArea"))
        cat_ax = plot.find(self._ns("catAx"))
        assert cat_ax.find(self._ns("auto")) is not None
        assert cat_ax.find(self._ns("lblAlgn")) is not None
        assert cat_ax.find(self._ns("lblOffset")) is not None


class TestChartSpaceNamespace:
    """Test that chartSpace uses prefixed 'c:' namespace."""

    def test_chartspace_uses_c_prefix(self):
        xml = create_chart_xml(
            "column",
            "S",
            None,
            [("", "", "'S'!$A$1:$A$5")],
        )
        serialized = etree.tostring(xml, encoding="unicode")
        # Should use c: prefix, not default namespace
        assert "c:chartSpace" in serialized
        assert "c:chart" in serialized
