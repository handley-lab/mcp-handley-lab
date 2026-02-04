"""Tests for required parameter validation in Word edit operations."""

import json
import tempfile
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcp_handley_lab.microsoft.word.package import WordPackage
from mcp_handley_lab.microsoft.word.tool import mcp


def _ops(operations: list[dict]) -> str:
    return json.dumps(operations)


@pytest.fixture
async def sample_docx():
    """Create a sample Word document with one paragraph."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)
    WordPackage.new().save(str(path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": _ops([{"op": "append", "content_data": "Test paragraph"}]),
        },
    )
    yield str(path)


class TestOpRequired:
    """Validate that 'op' is required."""

    @pytest.mark.asyncio
    async def test_missing_op(self, sample_docx):
        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "edit",
                {"file_path": sample_docx, "ops": _ops([{"content_data": "text"}])},
            )
        # Missing op is caught at the shared.py level
        assert "op" in str(exc_info.value).lower()


class TestTargetIdRequired:
    """Validate target_id is required for operations that need it."""

    @pytest.mark.asyncio
    async def test_insert_before_missing_target(self, sample_docx):
        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "edit",
                {
                    "file_path": sample_docx,
                    "ops": _ops([{"op": "insert_before", "content_data": "text"}]),
                },
            )
        assert "target_id required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_delete_missing_target(self, sample_docx):
        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "edit",
                {"file_path": sample_docx, "ops": _ops([{"op": "delete"}])},
            )
        assert "target_id required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_replace_missing_target(self, sample_docx):
        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "edit",
                {
                    "file_path": sample_docx,
                    "ops": _ops([{"op": "replace", "content_data": "new"}]),
                },
            )
        assert "target_id required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_style_missing_target(self, sample_docx):
        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "edit",
                {
                    "file_path": sample_docx,
                    "ops": _ops([{"op": "style", "style_name": "Heading 1"}]),
                },
            )
        assert "target_id required" in str(exc_info.value).lower()


class TestContentDataRequired:
    """Validate content_data is required for operations that need it."""

    @pytest.mark.asyncio
    async def test_insert_before_missing_content(self, sample_docx):
        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "edit",
                {
                    "file_path": sample_docx,
                    "ops": _ops([{"op": "insert_before", "target_id": "p_abc_1"}]),
                },
            )
        assert "content_data required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_append_heading_missing_content(self, sample_docx):
        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "edit",
                {
                    "file_path": sample_docx,
                    "ops": _ops([{"op": "append", "content_type": "heading"}]),
                },
            )
        assert "content_data required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_append_paragraph_allows_empty(self, sample_docx):
        """Empty paragraph append should succeed (content_data not required)."""
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": sample_docx,
                "ops": _ops([{"op": "append", "content_data": ""}]),
            },
        )
        assert result["results"][0]["success"] is True

    @pytest.mark.asyncio
    async def test_set_property_missing_content(self, sample_docx):
        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "edit",
                {"file_path": sample_docx, "ops": _ops([{"op": "set_property"}])},
            )
        assert "content_data required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_content_alias_works(self, sample_docx):
        """Using 'content' alias instead of 'content_data' should work."""
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": sample_docx,
                "ops": _ops([{"op": "append", "content": "via alias"}]),
            },
        )
        assert result["results"][0]["success"] is True
