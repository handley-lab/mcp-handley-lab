"""Tests for Excel chart operations."""

import io

import pytest

from mcp_handley_lab.microsoft.excel.ops.cells import set_cell_value
from mcp_handley_lab.microsoft.excel.ops.charts import (
    create_chart,
    delete_chart,
    list_charts,
    update_chart_data,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestCreateChart:
    """Tests for chart creation."""

    def test_create_bar_chart(self) -> None:
        """Create a bar chart."""
        pkg = ExcelPackage.new()
        # Add some data
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i * 10)

        chart = create_chart(
            pkg,
            "Sheet1",
            "bar",
            "A1:A5",
            "C1",
            title="Sales",
        )

        assert chart.type == "bar"
        assert chart.title == "Sales"
        assert chart.position == "C1"
        assert "'Sheet1'!" in chart.data_range
        assert chart.id is not None

    def test_create_column_chart(self) -> None:
        """Create a column chart."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i * 10)

        chart = create_chart(pkg, "Sheet1", "column", "A1:A5", "D1")
        assert chart.type == "column"

    def test_create_line_chart(self) -> None:
        """Create a line chart."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i * 10)

        chart = create_chart(pkg, "Sheet1", "line", "A1:A5", "E1")
        assert chart.type == "line"

    def test_create_pie_chart(self) -> None:
        """Create a pie chart."""
        pkg = ExcelPackage.new()
        for i in range(1, 5):
            set_cell_value(pkg, "Sheet1", f"A{i}", i * 25)

        chart = create_chart(pkg, "Sheet1", "pie", "A1:A4", "F1")
        assert chart.type == "pie"

    def test_create_scatter_chart(self) -> None:
        """Create a scatter chart."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i)
            set_cell_value(pkg, "Sheet1", f"B{i}", i * i)

        chart = create_chart(pkg, "Sheet1", "scatter", "B1:B5", "G1")
        assert chart.type == "scatter"

    def test_create_area_chart(self) -> None:
        """Create an area chart."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i * 10)

        chart = create_chart(pkg, "Sheet1", "area", "A1:A5", "H1")
        assert chart.type == "area"

    def test_create_chart_without_title(self) -> None:
        """Create chart without title."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i)

        chart = create_chart(pkg, "Sheet1", "column", "A1:A5", "C1")
        assert chart.title is None

    def test_create_chart_invalid_type_raises(self) -> None:
        """Invalid chart type raises error."""
        pkg = ExcelPackage.new()
        with pytest.raises(ValueError, match="Unsupported chart type"):
            create_chart(pkg, "Sheet1", "invalid", "A1:A5", "C1")

    def test_create_multiple_charts(self) -> None:
        """Create multiple charts on same sheet."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i * 10)

        chart1 = create_chart(pkg, "Sheet1", "bar", "A1:A5", "C1")
        chart2 = create_chart(pkg, "Sheet1", "line", "A1:A5", "C15")

        charts = list_charts(pkg, "Sheet1")
        assert len(charts) == 2
        assert chart1.id != chart2.id


class TestListCharts:
    """Tests for listing charts."""

    def test_list_charts_empty(self) -> None:
        """List charts on sheet with no charts."""
        pkg = ExcelPackage.new()
        charts = list_charts(pkg, "Sheet1")
        assert charts == []

    def test_list_charts_after_create(self) -> None:
        """List charts after creating."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i)

        create_chart(pkg, "Sheet1", "column", "A1:A5", "C1", title="Test Chart")

        charts = list_charts(pkg, "Sheet1")
        assert len(charts) == 1
        assert charts[0].type == "column"
        assert charts[0].title == "Test Chart"

    def test_list_charts_multiple(self) -> None:
        """List multiple charts."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i)

        create_chart(pkg, "Sheet1", "bar", "A1:A5", "C1")
        create_chart(pkg, "Sheet1", "pie", "A1:A5", "C15")
        create_chart(pkg, "Sheet1", "line", "A1:A5", "K1")

        charts = list_charts(pkg, "Sheet1")
        assert len(charts) == 3
        types = {c.type for c in charts}
        assert types == {"bar", "pie", "line"}


class TestDeleteChart:
    """Tests for deleting charts."""

    def test_delete_chart(self) -> None:
        """Delete a chart."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i)

        chart = create_chart(pkg, "Sheet1", "column", "A1:A5", "C1")
        chart_id = chart.id

        assert len(list_charts(pkg, "Sheet1")) == 1

        delete_chart(pkg, "Sheet1", chart_id)

        assert len(list_charts(pkg, "Sheet1")) == 0

    def test_delete_chart_not_found_raises(self) -> None:
        """Delete non-existent chart raises error."""
        pkg = ExcelPackage.new()
        with pytest.raises(KeyError, match="No charts on sheet|Chart not found"):
            delete_chart(pkg, "Sheet1", "nonexistent_chart_id")

    def test_delete_one_of_multiple(self) -> None:
        """Delete one chart, others remain."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i)

        chart1 = create_chart(pkg, "Sheet1", "bar", "A1:A5", "C1")
        chart2 = create_chart(pkg, "Sheet1", "line", "A1:A5", "C15")

        delete_chart(pkg, "Sheet1", chart1.id)

        charts = list_charts(pkg, "Sheet1")
        assert len(charts) == 1
        assert charts[0].id == chart2.id


class TestUpdateChartData:
    """Tests for updating chart data range."""

    def test_update_chart_data(self) -> None:
        """Update chart data range."""
        pkg = ExcelPackage.new()
        for i in range(1, 11):
            set_cell_value(pkg, "Sheet1", f"A{i}", i)

        chart = create_chart(pkg, "Sheet1", "column", "A1:A5", "C1")
        assert "A1:A5" in chart.data_range

        update_chart_data(pkg, "Sheet1", chart.id, "A1:A10")

        charts = list_charts(pkg, "Sheet1")
        assert len(charts) == 1
        assert "A1:A10" in charts[0].data_range

    def test_update_chart_not_found_raises(self) -> None:
        """Update non-existent chart raises error."""
        pkg = ExcelPackage.new()
        with pytest.raises(KeyError, match="No charts on sheet|Chart not found"):
            update_chart_data(pkg, "Sheet1", "nonexistent", "A1:A10")


class TestChartPersistence:
    """Tests for chart save/load."""

    def test_chart_persists(self) -> None:
        """Chart survives save/load."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i * 10)

        create_chart(pkg, "Sheet1", "bar", "A1:A5", "C1", title="Persisted Chart")

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        charts = list_charts(pkg2, "Sheet1")
        assert len(charts) == 1
        assert charts[0].type == "bar"
        assert charts[0].title == "Persisted Chart"

    def test_multiple_charts_persist(self) -> None:
        """Multiple charts survive save/load."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i)

        create_chart(pkg, "Sheet1", "bar", "A1:A5", "C1", title="Chart 1")
        create_chart(pkg, "Sheet1", "line", "A1:A5", "C15", title="Chart 2")

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        charts = list_charts(pkg2, "Sheet1")
        assert len(charts) == 2
        titles = {c.title for c in charts}
        assert titles == {"Chart 1", "Chart 2"}


class TestDrawingObjectIds:
    """Tests for unique drawing object IDs."""

    def test_multiple_charts_have_unique_ids(self) -> None:
        """Multiple charts should have unique cNvPr IDs."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i)

        # Create 3 charts
        create_chart(pkg, "Sheet1", "bar", "A1:A5", "C1")
        create_chart(pkg, "Sheet1", "line", "A1:A5", "C15")
        create_chart(pkg, "Sheet1", "pie", "A1:A5", "M1")

        # Get the drawing XML and check cNvPr IDs are unique
        from mcp_handley_lab.microsoft.excel.constants import RT

        for name, _rId, partname in pkg.get_sheet_paths():
            if name == "Sheet1":
                sheet_rels = pkg.get_rels(partname)
                drawing_rId = sheet_rels.rId_for_reltype(RT.DRAWING)
                if drawing_rId:
                    drawing_path = pkg.resolve_rel_target(partname, drawing_rId)
                    drawing_xml = pkg.get_xml(drawing_path)

                    # Find all cNvPr IDs
                    ids = []
                    for elem in drawing_xml.iter():
                        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        if tag == "cNvPr":
                            id_str = elem.get("id")
                            if id_str:
                                ids.append(int(id_str))

                    # All IDs should be unique
                    assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"
                    assert len(ids) == 3, f"Expected 3 chart IDs, got {len(ids)}"


class TestChartPositioning:
    """Tests for chart positioning."""

    def test_chart_position_extracted(self) -> None:
        """Chart position is correctly extracted."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i)

        create_chart(pkg, "Sheet1", "column", "A1:A5", "E5")

        charts = list_charts(pkg, "Sheet1")
        assert len(charts) == 1
        assert charts[0].position == "E5"

    def test_chart_position_various(self) -> None:
        """Test various chart positions."""
        pkg = ExcelPackage.new()
        for i in range(1, 6):
            set_cell_value(pkg, "Sheet1", f"A{i}", i)

        positions = ["A1", "Z10", "AA50"]
        for pos in positions:
            create_chart(pkg, "Sheet1", "bar", "A1:A5", pos)

        charts = list_charts(pkg, "Sheet1")
        assert len(charts) == 3
        found_positions = {c.position for c in charts}
        assert found_positions == set(positions)
