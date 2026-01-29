"""Tests for Word chart operations (create, list, delete, update)."""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.microsoft.word.ops.charts import (
    create_chart,
    delete_chart,
    list_charts,
    update_chart_data,
)
from mcp_handley_lab.microsoft.word.package import WordPackage
from mcp_handley_lab.microsoft.word.tool import mcp

SAMPLE_DATA = [["Category", "S1", "S2"], ["A", 10, 30], ["B", 20, 40], ["C", 15, 25]]


def _make_doc_with_paragraph() -> WordPackage:
    """Create a WordPackage with a single paragraph for testing."""
    pkg = WordPackage.new()
    from mcp_handley_lab.microsoft.word.ops.core import append_paragraph_ooxml

    append_paragraph_ooxml(pkg, "Test paragraph")
    return pkg


def _get_first_para_id(pkg: WordPackage) -> str:
    """Get block ID of first paragraph with text."""
    from mcp_handley_lab.microsoft.word.ops.core import build_blocks

    blocks, _total = build_blocks(pkg)
    # Find first paragraph with text (skip empty default paragraph)
    for b in blocks:
        if b.text:
            return b.id
    return blocks[0].id


class TestCreateChart:
    """Tests for Word chart creation."""

    def test_create_column_chart(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        chart_id = create_chart(pkg, target, "column", SAMPLE_DATA, title="Revenue")
        assert chart_id.startswith("chart_")

    def test_create_bar_chart(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        chart_id = create_chart(pkg, target, "bar", SAMPLE_DATA)
        assert chart_id.startswith("chart_")

    def test_create_line_chart(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        chart_id = create_chart(pkg, target, "line", SAMPLE_DATA)
        assert chart_id.startswith("chart_")

    def test_create_pie_chart(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        chart_id = create_chart(pkg, target, "pie", SAMPLE_DATA)
        assert chart_id.startswith("chart_")

    def test_create_scatter_chart(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        chart_id = create_chart(pkg, target, "scatter", SAMPLE_DATA)
        assert chart_id.startswith("chart_")

    def test_create_area_chart(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        chart_id = create_chart(pkg, target, "area", SAMPLE_DATA)
        assert chart_id.startswith("chart_")

    def test_create_chart_invalid_type(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        with pytest.raises(ValueError, match="Unsupported"):
            create_chart(pkg, target, "radar", SAMPLE_DATA)

    def test_create_multiple_charts(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        id1 = create_chart(pkg, target, "column", SAMPLE_DATA, title="Chart 1")
        id2 = create_chart(pkg, target, "bar", SAMPLE_DATA, title="Chart 2")
        assert id1 != id2

    def test_chart_has_embedded_workbook(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        create_chart(pkg, target, "column", SAMPLE_DATA)
        # Check that embedding part exists
        found = any(
            p.startswith("/word/embeddings/Microsoft_Excel_Worksheet")
            for p in pkg.iter_partnames()
        )
        assert found

    def test_chart_has_chart_part(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        create_chart(pkg, target, "column", SAMPLE_DATA)
        found = any(p.startswith("/word/charts/chart") for p in pkg.iter_partnames())
        assert found

    def test_chart_custom_size(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        chart_id = create_chart(
            pkg,
            target,
            "column",
            SAMPLE_DATA,
            width_inches=8.0,
            height_inches=4.0,
        )
        assert chart_id.startswith("chart_")


class TestListCharts:
    """Tests for listing Word charts."""

    def test_list_empty(self):
        pkg = _make_doc_with_paragraph()
        charts = list_charts(pkg)
        assert charts == []

    def test_list_after_create(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        create_chart(pkg, target, "column", SAMPLE_DATA, title="Revenue")
        charts = list_charts(pkg)
        assert len(charts) == 1
        assert charts[0].type == "column"
        assert charts[0].title == "Revenue"

    def test_list_multiple(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        create_chart(pkg, target, "bar", SAMPLE_DATA, title="Bar")
        create_chart(pkg, target, "line", SAMPLE_DATA, title="Line")
        charts = list_charts(pkg)
        assert len(charts) == 2
        types = {c.type for c in charts}
        assert types == {"bar", "line"}

    def test_list_chart_types(self):
        """Each chart type is correctly detected."""
        for ct in ("bar", "column", "line", "pie", "scatter", "area"):
            pkg = _make_doc_with_paragraph()
            target = _get_first_para_id(pkg)
            create_chart(pkg, target, ct, SAMPLE_DATA)
            charts = list_charts(pkg)
            assert charts[0].type == ct, f"Failed for {ct}"


class TestDeleteChart:
    """Tests for Word chart deletion."""

    def test_delete_chart(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        chart_id = create_chart(pkg, target, "column", SAMPLE_DATA)
        delete_chart(pkg, chart_id)
        charts = list_charts(pkg)
        assert len(charts) == 0

    def test_delete_nonexistent_raises(self):
        pkg = _make_doc_with_paragraph()
        with pytest.raises(KeyError):
            delete_chart(pkg, "chart_999")

    def test_delete_one_of_multiple(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        create_chart(pkg, target, "column", SAMPLE_DATA, title="Keep")
        id2 = create_chart(pkg, target, "bar", SAMPLE_DATA, title="Delete")
        delete_chart(pkg, id2)
        charts = list_charts(pkg)
        assert len(charts) == 1
        assert charts[0].title == "Keep"

    def test_delete_removes_parts(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        chart_id = create_chart(pkg, target, "column", SAMPLE_DATA)
        # Confirm parts exist before deletion
        chart_parts = [p for p in pkg.iter_partnames() if "/word/charts/" in p]
        embed_parts = [p for p in pkg.iter_partnames() if "/word/embeddings/" in p]
        assert len(chart_parts) >= 1
        assert len(embed_parts) >= 1

        delete_chart(pkg, chart_id)

        # Parts should be removed
        chart_parts_after = [p for p in pkg.iter_partnames() if "/word/charts/" in p]
        embed_parts_after = [
            p for p in pkg.iter_partnames() if "/word/embeddings/" in p
        ]
        assert len(chart_parts_after) == 0
        assert len(embed_parts_after) == 0


class TestUpdateChartData:
    """Tests for updating Word chart data."""

    def test_update_data(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        chart_id = create_chart(pkg, target, "column", SAMPLE_DATA, title="Original")

        new_data = [["Cat", "Sales"], ["X", 100], ["Y", 200]]
        update_chart_data(pkg, chart_id, new_data)

        charts = list_charts(pkg)
        assert len(charts) == 1
        # Title should be preserved
        assert charts[0].title == "Original"
        # Type should be preserved
        assert charts[0].type == "column"

    def test_update_nonexistent_raises(self):
        pkg = _make_doc_with_paragraph()
        with pytest.raises(KeyError):
            update_chart_data(pkg, "chart_999", SAMPLE_DATA)


class TestChartPersistence:
    """Tests for chart round-trip through save/load."""

    def test_chart_survives_save(self):
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)
        create_chart(pkg, target, "column", SAMPLE_DATA, title="Persist")

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)

        pkg2 = WordPackage.open(buf)
        charts = list_charts(pkg2)
        assert len(charts) == 1
        assert charts[0].type == "column"
        assert charts[0].title == "Persist"

    def test_full_crud_cycle(self):
        """Create, list, update, delete cycle."""
        pkg = _make_doc_with_paragraph()
        target = _get_first_para_id(pkg)

        # Create
        chart_id = create_chart(pkg, target, "bar", SAMPLE_DATA, title="Cycle")

        # List
        charts = list_charts(pkg)
        assert len(charts) == 1

        # Update
        new_data = [["Cat", "Revenue"], ["Q1", 500], ["Q2", 600]]
        update_chart_data(pkg, chart_id, new_data)
        charts = list_charts(pkg)
        assert charts[0].title == "Cycle"
        assert charts[0].type == "bar"

        # Delete
        delete_chart(pkg, chart_id)
        assert list_charts(pkg) == []


class TestWordChartMcpTool:
    """Tests for Word chart operations via MCP tool interface."""

    @pytest.mark.asyncio
    async def test_insert_chart_via_tool(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            path = Path(f.name)
        path.unlink()

        try:
            # Create document with a paragraph
            await mcp.call_tool(
                "edit",
                {
                    "file_path": str(path),
                    "ops": json.dumps(
                        [
                            {"op": "append", "content_data": "Before chart"},
                        ]
                    ),
                },
            )

            # Read to get block IDs
            content_list, _err = await mcp.call_tool(
                "read",
                {"file_path": str(path), "scope": "blocks"},
            )
            result_data = json.loads(content_list[0].text)
            blocks = result_data["blocks"]
            # Find a block with text
            target_id = blocks[0]["id"]
            for b in blocks:
                if b.get("text"):
                    target_id = b["id"]
                    break

            # Insert chart
            chart_data = {
                "chart_type": "column",
                "data": [["Cat", "Sales"], ["A", 10], ["B", 20]],
                "title": "Test Chart",
            }
            await mcp.call_tool(
                "edit",
                {
                    "file_path": str(path),
                    "ops": json.dumps(
                        [
                            {
                                "op": "insert_chart",
                                "target_id": target_id,
                                "content_data": json.dumps(chart_data),
                            },
                        ]
                    ),
                },
            )

            # Verify via read charts scope
            content_list, _err = await mcp.call_tool(
                "read",
                {"file_path": str(path), "scope": "charts"},
            )
            data = json.loads(content_list[0].text)
            assert len(data["charts"]) == 1
            assert data["charts"][0]["type"] == "column"
            assert data["charts"][0]["title"] == "Test Chart"
        finally:
            path.unlink(missing_ok=True)
