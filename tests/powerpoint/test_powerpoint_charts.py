"""Tests for PowerPoint chart operations (create, list, delete, update)."""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.microsoft.powerpoint.ops.charts import (
    create_chart,
    delete_chart,
    list_charts,
    update_chart_data,
)
from mcp_handley_lab.microsoft.powerpoint.ops.slides import add_slide
from mcp_handley_lab.microsoft.powerpoint.package import PowerPointPackage
from mcp_handley_lab.microsoft.powerpoint.tool import mcp


def _new_pptx_with_slide() -> PowerPointPackage:
    """Create a PowerPointPackage with one blank slide."""
    pkg = PowerPointPackage.new()
    add_slide(pkg)
    return pkg


SAMPLE_DATA = [["Category", "S1", "S2"], ["A", 10, 30], ["B", 20, 40], ["C", 15, 25]]


class TestCreateChart:
    """Tests for PowerPoint chart creation."""

    def test_create_column_chart(self):
        pkg = _new_pptx_with_slide()
        shape_key = create_chart(pkg, 1, "column", SAMPLE_DATA, title="Revenue")
        assert ":" in shape_key  # slide_num:shape_id format

    def test_create_bar_chart(self):
        pkg = _new_pptx_with_slide()
        shape_key = create_chart(pkg, 1, "bar", SAMPLE_DATA)
        assert shape_key.startswith("1:")

    def test_create_line_chart(self):
        pkg = _new_pptx_with_slide()
        shape_key = create_chart(pkg, 1, "line", SAMPLE_DATA)
        assert shape_key.startswith("1:")

    def test_create_pie_chart(self):
        pkg = _new_pptx_with_slide()
        shape_key = create_chart(pkg, 1, "pie", SAMPLE_DATA)
        assert shape_key.startswith("1:")

    def test_create_scatter_chart(self):
        pkg = _new_pptx_with_slide()
        shape_key = create_chart(pkg, 1, "scatter", SAMPLE_DATA)
        assert shape_key.startswith("1:")

    def test_create_area_chart(self):
        pkg = _new_pptx_with_slide()
        shape_key = create_chart(pkg, 1, "area", SAMPLE_DATA)
        assert shape_key.startswith("1:")

    def test_create_chart_invalid_type(self):
        pkg = _new_pptx_with_slide()
        with pytest.raises(ValueError, match="Unsupported"):
            create_chart(pkg, 1, "radar", SAMPLE_DATA)

    def test_create_multiple_charts(self):
        pkg = _new_pptx_with_slide()
        sk1 = create_chart(pkg, 1, "column", SAMPLE_DATA, title="Chart 1")
        sk2 = create_chart(pkg, 1, "bar", SAMPLE_DATA, title="Chart 2")
        assert sk1 != sk2

    def test_chart_custom_position(self):
        pkg = _new_pptx_with_slide()
        shape_key = create_chart(
            pkg,
            1,
            "column",
            SAMPLE_DATA,
            x=2.0,
            y=3.0,
            width=6.0,
            height=4.0,
        )
        assert shape_key.startswith("1:")

    def test_chart_has_embedded_workbook(self):
        pkg = _new_pptx_with_slide()
        create_chart(pkg, 1, "column", SAMPLE_DATA)
        found = any(
            p.startswith("/ppt/embeddings/Microsoft_Excel_Worksheet")
            for p in pkg.iter_partnames()
        )
        assert found

    def test_chart_has_chart_part(self):
        pkg = _new_pptx_with_slide()
        create_chart(pkg, 1, "column", SAMPLE_DATA)
        found = any(p.startswith("/ppt/charts/chart") for p in pkg.iter_partnames())
        assert found


class TestListCharts:
    """Tests for listing PowerPoint charts."""

    def test_list_empty(self):
        pkg = _new_pptx_with_slide()
        charts = list_charts(pkg, 1)
        assert charts == []

    def test_list_after_create(self):
        pkg = _new_pptx_with_slide()
        create_chart(pkg, 1, "column", SAMPLE_DATA, title="Revenue")
        charts = list_charts(pkg, 1)
        assert len(charts) == 1
        assert charts[0].type == "column"
        assert charts[0].title == "Revenue"

    def test_list_multiple(self):
        pkg = _new_pptx_with_slide()
        create_chart(pkg, 1, "bar", SAMPLE_DATA, title="Bar")
        create_chart(pkg, 1, "line", SAMPLE_DATA, title="Line")
        charts = list_charts(pkg, 1)
        assert len(charts) == 2
        types = {c.type for c in charts}
        assert types == {"bar", "line"}

    def test_list_chart_types(self):
        """Each chart type is correctly detected."""
        for ct in ("bar", "column", "line", "pie", "scatter", "area"):
            pkg = _new_pptx_with_slide()
            create_chart(pkg, 1, ct, SAMPLE_DATA)
            charts = list_charts(pkg, 1)
            assert charts[0].type == ct, f"Failed for {ct}"


class TestDeleteChart:
    """Tests for PowerPoint chart deletion."""

    def test_delete_chart(self):
        pkg = _new_pptx_with_slide()
        shape_key = create_chart(pkg, 1, "column", SAMPLE_DATA)
        delete_chart(pkg, 1, shape_key)
        charts = list_charts(pkg, 1)
        assert len(charts) == 0

    def test_delete_nonexistent_raises(self):
        pkg = _new_pptx_with_slide()
        with pytest.raises(KeyError):
            delete_chart(pkg, 1, "1:999")

    def test_delete_one_of_multiple(self):
        pkg = _new_pptx_with_slide()
        create_chart(pkg, 1, "column", SAMPLE_DATA, title="Keep")
        sk2 = create_chart(pkg, 1, "bar", SAMPLE_DATA, title="Delete")
        delete_chart(pkg, 1, sk2)
        charts = list_charts(pkg, 1)
        assert len(charts) == 1
        assert charts[0].title == "Keep"

    def test_delete_removes_parts(self):
        pkg = _new_pptx_with_slide()
        shape_key = create_chart(pkg, 1, "column", SAMPLE_DATA)
        chart_parts = [p for p in pkg.iter_partnames() if "/ppt/charts/" in p]
        embed_parts = [p for p in pkg.iter_partnames() if "/ppt/embeddings/" in p]
        assert len(chart_parts) >= 1
        assert len(embed_parts) >= 1

        delete_chart(pkg, 1, shape_key)

        chart_parts_after = [p for p in pkg.iter_partnames() if "/ppt/charts/" in p]
        embed_parts_after = [p for p in pkg.iter_partnames() if "/ppt/embeddings/" in p]
        assert len(chart_parts_after) == 0
        assert len(embed_parts_after) == 0

    def test_wrong_slide_raises(self):
        pkg = _new_pptx_with_slide()
        shape_key = create_chart(pkg, 1, "column", SAMPLE_DATA)
        # Shape key says slide 1, but we pass slide 2
        with pytest.raises(ValueError, match="not on slide"):
            delete_chart(pkg, 2, shape_key)


class TestUpdateChartData:
    """Tests for updating PowerPoint chart data."""

    def test_update_data(self):
        pkg = _new_pptx_with_slide()
        shape_key = create_chart(pkg, 1, "column", SAMPLE_DATA, title="Original")

        new_data = [["Cat", "Sales"], ["X", 100], ["Y", 200]]
        update_chart_data(pkg, 1, shape_key, new_data)

        charts = list_charts(pkg, 1)
        assert len(charts) == 1
        assert charts[0].title == "Original"
        assert charts[0].type == "column"

    def test_update_nonexistent_raises(self):
        pkg = _new_pptx_with_slide()
        with pytest.raises(KeyError):
            update_chart_data(pkg, 1, "1:999", SAMPLE_DATA)


class TestChartPersistence:
    """Tests for chart round-trip through save/load."""

    def test_chart_survives_save(self):
        pkg = _new_pptx_with_slide()
        create_chart(pkg, 1, "column", SAMPLE_DATA, title="Persist")

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)

        pkg2 = PowerPointPackage.open(buf)
        charts = list_charts(pkg2, 1)
        assert len(charts) == 1
        assert charts[0].type == "column"
        assert charts[0].title == "Persist"

    def test_full_crud_cycle(self):
        """Create, list, update, delete cycle."""
        pkg = _new_pptx_with_slide()

        # Create
        shape_key = create_chart(pkg, 1, "bar", SAMPLE_DATA, title="Cycle")

        # List
        charts = list_charts(pkg, 1)
        assert len(charts) == 1

        # Update
        new_data = [["Cat", "Revenue"], ["Q1", 500], ["Q2", 600]]
        update_chart_data(pkg, 1, shape_key, new_data)
        charts = list_charts(pkg, 1)
        assert charts[0].title == "Cycle"
        assert charts[0].type == "bar"

        # Delete
        delete_chart(pkg, 1, shape_key)
        assert list_charts(pkg, 1) == []


class TestPowerPointChartMcpTool:
    """Tests for PowerPoint chart operations via MCP tool interface."""

    @pytest.mark.asyncio
    async def test_add_chart_via_tool(self):
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
            path = Path(f.name)
        path.unlink()  # remove so edit() auto-creates

        try:
            # Create presentation with a slide
            await mcp.call_tool(
                "edit",
                {
                    "file_path": str(path),
                    "ops": json.dumps(
                        [
                            {"op": "add_slide"},
                        ]
                    ),
                },
            )

            # Add chart
            await mcp.call_tool(
                "edit",
                {
                    "file_path": str(path),
                    "ops": json.dumps(
                        [
                            {
                                "op": "add_chart",
                                "slide_num": 1,
                                "chart_type": "column",
                                "data": [["Cat", "Sales"], ["A", 10], ["B", 20]],
                                "title": "Test Chart",
                            },
                        ]
                    ),
                },
            )

            # Verify via read charts scope
            result = await mcp.call_tool(
                "read",
                {"file_path": str(path), "scope": "charts", "slide_num": 1},
            )
            # Handle both tuple (content_list, extra) and list returns
            content_list = result[0] if isinstance(result, tuple) else result
            data = json.loads(content_list[0].text)
            assert len(data["charts"]) == 1
            assert data["charts"][0]["type"] == "column"
            assert data["charts"][0]["title"] == "Test Chart"
        finally:
            path.unlink(missing_ok=True)
