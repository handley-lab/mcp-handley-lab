"""Integration tests for PowerPoint MCP tool entry points.

Tests read(), edit(), and render() via mcp.call_tool() to verify the full
dispatch pipeline: JSON parsing, $prev resolution, auto-create, and scopes.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.microsoft.powerpoint.tool import mcp


def _parse_result(result):
    """Extract dict from mcp.call_tool return (handles both tuple and list)."""
    if isinstance(result, tuple):
        return result[1]
    # List of TextContent — parse the JSON text
    return json.loads(result[0].text)


@pytest.fixture
def pptx_path():
    """Provide a temp path for a .pptx file (not yet created)."""
    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
        path = Path(f.name)
    path.unlink()  # remove so edit() auto-creates
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def pptx_with_slide(pptx_path):
    """Create a .pptx with one slide."""
    from mcp_handley_lab.microsoft.powerpoint.ops.slides import add_slide
    from mcp_handley_lab.microsoft.powerpoint.package import PowerPointPackage

    pkg = PowerPointPackage.new()
    add_slide(pkg, "Blank")
    pkg.save(str(pptx_path))
    return pptx_path


# =============================================================================
# Auto-create
# =============================================================================


@pytest.mark.asyncio
async def test_edit_auto_creates_new_file(pptx_path):
    """edit() on non-existent file creates it and applies ops."""
    assert not pptx_path.exists()

    result = _parse_result(
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(pptx_path),
                "ops": json.dumps([{"op": "add_slide", "layout_name": "Blank"}]),
            },
        )
    )

    assert result["success"] is True
    assert result["succeeded"] == 1
    assert result["saved"] is True
    assert pptx_path.exists()


# =============================================================================
# Read scopes
# =============================================================================


@pytest.mark.asyncio
async def test_read_meta(pptx_with_slide):
    """read(scope='meta') returns presentation metadata."""
    result = _parse_result(
        await mcp.call_tool(
            "read",
            {"file_path": str(pptx_with_slide), "scope": "meta"},
        )
    )

    assert result["scope"] == "meta"
    assert result["meta"]["slide_count"] == 1


@pytest.mark.asyncio
async def test_read_slides(pptx_with_slide):
    """read(scope='slides') lists slides."""
    result = _parse_result(
        await mcp.call_tool(
            "read",
            {"file_path": str(pptx_with_slide), "scope": "slides"},
        )
    )

    assert result["scope"] == "slides"
    assert len(result["slides"]) == 1


@pytest.mark.asyncio
async def test_read_shapes(pptx_with_slide):
    """read(scope='shapes') requires slide_num."""
    result = _parse_result(
        await mcp.call_tool(
            "read",
            {"file_path": str(pptx_with_slide), "scope": "shapes", "slide_num": 1},
        )
    )

    assert result["scope"] == "shapes"


@pytest.mark.asyncio
async def test_read_layouts(pptx_with_slide):
    """read(scope='layouts') lists available layouts."""
    result = _parse_result(
        await mcp.call_tool(
            "read",
            {"file_path": str(pptx_with_slide), "scope": "layouts"},
        )
    )

    assert result["scope"] == "layouts"
    layout_names = [layout["name"] for layout in result["layouts"]]
    assert "Blank" in layout_names
    assert "Title Slide" in layout_names


# =============================================================================
# Batch operations
# =============================================================================


@pytest.mark.asyncio
async def test_batch_add_slide_and_shape(pptx_path):
    """Batch: add slide then add shape on it."""
    result = _parse_result(
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(pptx_path),
                "ops": json.dumps(
                    [
                        {"op": "add_slide", "layout_name": "Blank"},
                        {
                            "op": "add_shape",
                            "slide_num": 1,
                            "x": 1.0,
                            "y": 1.0,
                            "width": 4.0,
                            "height": 1.0,
                            "text": "Hello World",
                        },
                    ]
                ),
            },
        )
    )

    assert result["success"] is True
    assert result["succeeded"] == 2
    assert result["saved"] is True

    # Verify text is readable
    text_result = _parse_result(
        await mcp.call_tool(
            "read",
            {"file_path": str(pptx_path), "scope": "text", "slide_num": 1},
        )
    )
    assert "Hello World" in text_result["text"]


@pytest.mark.asyncio
async def test_prev_ref_chaining(pptx_path):
    """$prev[N] references resolve correctly for shape_key."""
    result = _parse_result(
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(pptx_path),
                "ops": json.dumps(
                    [
                        {"op": "add_slide", "layout_name": "Blank"},
                        {
                            "op": "add_shape",
                            "slide_num": 1,
                            "x": 1.0,
                            "y": 1.0,
                            "width": 4.0,
                            "height": 1.0,
                            "text": "Styled text",
                        },
                        {
                            "op": "set_text_style",
                            "shape_key": "$prev[1]",
                            "bold": True,
                            "size": 24,
                        },
                    ]
                ),
            },
        )
    )

    assert result["success"] is True
    assert result["succeeded"] == 3


@pytest.mark.asyncio
async def test_atomic_mode_rollback(pptx_with_slide):
    """Atomic mode: failure rolls back (doesn't save)."""
    result = _parse_result(
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(pptx_with_slide),
                "ops": json.dumps(
                    [
                        {
                            "op": "add_shape",
                            "slide_num": 1,
                            "x": 1.0,
                            "y": 1.0,
                            "width": 4.0,
                            "height": 1.0,
                            "text": "OK",
                        },
                        {
                            "op": "delete_slide",
                            "slide_num": 999,
                        },
                    ]
                ),
                "mode": "atomic",
            },
        )
    )

    assert result["success"] is False
    assert result["saved"] is False


@pytest.mark.asyncio
async def test_partial_mode_saves_successes(pptx_with_slide):
    """Partial mode: saves successful ops even if some fail."""
    result = _parse_result(
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(pptx_with_slide),
                "ops": json.dumps(
                    [
                        {
                            "op": "add_shape",
                            "slide_num": 1,
                            "x": 1.0,
                            "y": 1.0,
                            "width": 4.0,
                            "height": 1.0,
                            "text": "Partial OK",
                        },
                        {
                            "op": "delete_slide",
                            "slide_num": 999,
                        },
                    ]
                ),
                "mode": "partial",
            },
        )
    )

    assert result["success"] is True
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert result["saved"] is True


# =============================================================================
# Table operations via MCP
# =============================================================================


@pytest.mark.asyncio
async def test_table_workflow(pptx_path):
    """Create table, set cells, read back."""
    result = _parse_result(
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(pptx_path),
                "ops": json.dumps(
                    [
                        {"op": "add_slide", "layout_name": "Blank"},
                        {
                            "op": "add_table",
                            "slide_num": 1,
                            "rows": 2,
                            "cols": 2,
                            "x": 1.0,
                            "y": 1.0,
                            "width": 6.0,
                            "height": 2.0,
                        },
                        {
                            "op": "set_table_cell",
                            "shape_key": "$prev[1]",
                            "row": 0,
                            "col": 0,
                            "text": "Header",
                        },
                    ]
                ),
            },
        )
    )

    assert result["success"] is True
    assert result["succeeded"] == 3

    # Read tables
    tables = _parse_result(
        await mcp.call_tool(
            "read",
            {"file_path": str(pptx_path), "scope": "tables", "slide_num": 1},
        )
    )

    assert len(tables["tables"]) == 1
    assert tables["tables"][0]["rows"] == 2
    assert tables["tables"][0]["cols"] == 2


# =============================================================================
# Error handling
# =============================================================================


@pytest.mark.asyncio
async def test_invalid_json_ops(pptx_with_slide):
    """Invalid JSON in ops returns error."""
    result = _parse_result(
        await mcp.call_tool(
            "edit",
            {"file_path": str(pptx_with_slide), "ops": "not json"},
        )
    )

    assert result["success"] is False
    assert "Invalid JSON" in result["message"]


@pytest.mark.asyncio
async def test_unknown_operation(pptx_with_slide):
    """Unknown op name returns error."""
    result = _parse_result(
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(pptx_with_slide),
                "ops": json.dumps([{"op": "nonexistent_op"}]),
            },
        )
    )

    assert result["success"] is False


@pytest.mark.asyncio
async def test_text_normalization(pptx_path):
    """Text fields normalize \\n to newlines."""
    result = _parse_result(
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(pptx_path),
                "ops": json.dumps(
                    [
                        {"op": "add_slide", "layout_name": "Blank"},
                        {
                            "op": "add_shape",
                            "slide_num": 1,
                            "x": 1.0,
                            "y": 1.0,
                            "width": 4.0,
                            "height": 2.0,
                            "text": "Line 1\\nLine 2",
                        },
                    ]
                ),
            },
        )
    )

    assert result["success"] is True

    text_result = _parse_result(
        await mcp.call_tool(
            "read",
            {"file_path": str(pptx_path), "scope": "text", "slide_num": 1},
        )
    )
    assert "Line 1" in text_result["text"]
    assert "Line 2" in text_result["text"]
