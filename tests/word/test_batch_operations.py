"""Tests for Word document batch operations (Issue #127).

Tests the ops array interface, $prev[N] chaining, fail-fast error handling,
and validation.
"""

import json
import tempfile
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcp_handley_lab.microsoft.word.package import WordPackage
from mcp_handley_lab.microsoft.word.tool import mcp


@pytest.fixture
async def sample_docx():
    """Create a sample Word document for batch testing."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)
    path.unlink()  # remove so edit() auto-creates

    # Create document with heading and table via edit (auto-creates file)
    table_data = json.dumps([["A", "B"], ["C", "D"]])
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": json.dumps(
                [
                    {
                        "op": "append",
                        "content_type": "heading",
                        "content_data": "Batch Test Document",
                        "heading_level": 1,
                    },
                    {
                        "op": "append",
                        "content_type": "table",
                        "content_data": table_data,
                    },
                ]
            ),
        },
    )

    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
async def empty_docx():
    """Create an empty Word document for testing."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)

    WordPackage.new().save(str(path))

    yield path
    path.unlink(missing_ok=True)


# =============================================================================
# Basic Batch Operations
# =============================================================================


@pytest.mark.asyncio
async def test_batch_single_operation(sample_docx):
    """Single operation in batch works."""
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "append",
                        "content_type": "paragraph",
                        "content_data": "New text",
                    }
                ]
            ),
        },
    )

    assert result["success"] is True
    assert result["total"] == 1
    assert result["succeeded"] == 1
    assert result["failed"] == 0
    assert result["saved"] is True
    assert len(result["results"]) == 1
    assert result["results"][0]["success"] is True
    assert result["results"][0]["index"] == 0
    assert result["results"][0]["op"] == "append"


@pytest.mark.asyncio
async def test_batch_multiple_table_cells(sample_docx):
    """Batch edit multiple table cells using $prev[N] chaining.

    Note: Table IDs are content-addressed and change after each edit.
    Use $prev[N] to reference the updated table ID from the previous operation.
    """
    # Get the initial table ID
    _, read_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in read_result["blocks"] if b["type"] == "table")
    table_id = table_block["id"]

    # Batch update 4 cells using $prev[N] chaining for subsequent cells
    # First cell uses original ID, others chain from previous
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "edit_cell",
                        "target_id": table_id,
                        "row": 0,
                        "col": 0,
                        "content_data": "A1",
                    },
                    {
                        "op": "edit_cell",
                        "target_id": "$prev[0]",
                        "row": 0,
                        "col": 1,
                        "content_data": "B1",
                    },
                    {
                        "op": "edit_cell",
                        "target_id": "$prev[1]",
                        "row": 1,
                        "col": 0,
                        "content_data": "A2",
                    },
                    {
                        "op": "edit_cell",
                        "target_id": "$prev[2]",
                        "row": 1,
                        "col": 1,
                        "content_data": "B2",
                    },
                ]
            ),
        },
    )

    assert result["success"] is True
    assert result["total"] == 4
    assert result["succeeded"] == 4
    assert result["failed"] == 0
    assert result["saved"] is True

    # Verify table content using the final table ID
    _, read_after = await mcp.call_tool(
        "read",
        {
            "file_path": str(sample_docx),
            "scope": "table_cells",
            "target_id": result["element_id"],
        },
    )
    cells = read_after["cells"]
    # Cells is a list of dicts with row, col, text keys
    cell_texts = {(c["row"], c["col"]): c["text"] for c in cells}
    assert cell_texts[(0, 0)] == "A1"
    assert cell_texts[(0, 1)] == "B1"
    assert cell_texts[(1, 0)] == "A2"
    assert cell_texts[(1, 1)] == "B2"


@pytest.mark.asyncio
async def test_batch_empty_ops_array(sample_docx):
    """Empty ops array returns success without modifying document."""
    original_bytes = sample_docx.read_bytes()

    _, result = await mcp.call_tool(
        "edit",
        {"file_path": str(sample_docx), "ops": json.dumps([])},
    )

    assert result["success"] is True
    assert result["total"] == 0
    assert result["succeeded"] == 0
    assert result["failed"] == 0
    assert result["saved"] is False
    assert "No operations" in result["message"]
    # File unchanged
    assert sample_docx.read_bytes() == original_bytes


# =============================================================================
# $prev[N] Chaining
# =============================================================================


@pytest.mark.asyncio
async def test_prev_chaining_append_then_style(empty_docx):
    """Create paragraph and style it using $prev[0] reference."""
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(empty_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "append",
                        "content_type": "paragraph",
                        "content_data": "Important note",
                    },
                    {"op": "style", "target_id": "$prev[0]", "style_name": "Heading 1"},
                ]
            ),
        },
    )

    assert result["success"] is True
    assert result["succeeded"] == 2
    assert result["results"][0]["element_id"] != ""
    # The style op receives the element_id from append
    assert result["results"][1]["success"] is True


@pytest.mark.asyncio
async def test_prev_reference_invalid_future_index(empty_docx):
    """$prev[N] where N >= current index raises ValueError."""
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(empty_docx),
                "ops": json.dumps(
                    [
                        {
                            "op": "style",
                            "target_id": "$prev[0]",
                            "style_name": "Heading 1",
                        },
                    ]
                ),
            },
        )

    assert "Invalid $prev reference" in str(exc_info.value)
    assert "index >= current" in str(exc_info.value)


@pytest.mark.asyncio
async def test_prev_reference_empty_element_id(sample_docx):
    """$prev[N] referencing an op with empty element_id raises ValueError."""
    # set_property returns empty element_id, then try to reference it
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": json.dumps(
                    [
                        {
                            "op": "set_property",
                            "content_data": json.dumps({"title": "New Title"}),
                        },
                        {
                            "op": "style",
                            "target_id": "$prev[0]",
                            "style_name": "Heading 1",
                        },
                    ]
                ),
            },
        )

    assert "empty element_id" in str(exc_info.value)


@pytest.mark.asyncio
async def test_prev_literal_in_content_data_not_substituted(empty_docx):
    """$prev[N] in content_data is preserved literally, not substituted."""
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(empty_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "append",
                        "content_type": "paragraph",
                        "content_data": "See $prev[0] for details",
                    },
                ]
            ),
        },
    )

    assert result["success"] is True

    # Verify text contains literal $prev[0]
    _, read_result = await mcp.call_tool(
        "read", {"file_path": str(empty_docx), "scope": "blocks"}
    )
    blocks = read_result["blocks"]
    assert any("$prev[0]" in b.get("text", "") for b in blocks)


# =============================================================================
# Atomic Mode (all-or-nothing)
# =============================================================================


@pytest.mark.asyncio
async def test_failure_leaves_file_unchanged(sample_docx):
    """Failure raises exception and file is not modified."""
    original_bytes = sample_docx.read_bytes()

    # First op succeeds, second fails - raises immediately
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": json.dumps(
                    [
                        {
                            "op": "append",
                            "content_type": "paragraph",
                            "content_data": "This should not be saved",
                        },
                        {
                            "op": "style",
                            "target_id": "nonexistent_id_12345",
                            "style_name": "Heading 1",
                        },
                    ]
                ),
            },
        )

    assert (
        "nonexistent_id_12345" in str(exc_info.value)
        or "not found" in str(exc_info.value).lower()
    )

    # File must be unchanged
    assert sample_docx.read_bytes() == original_bytes


@pytest.mark.asyncio
async def test_success_saves_all(empty_docx):
    """All operations succeed, file is saved."""
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(empty_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "append",
                        "content_type": "paragraph",
                        "content_data": "First",
                    },
                    {
                        "op": "append",
                        "content_type": "paragraph",
                        "content_data": "Second",
                    },
                    {
                        "op": "append",
                        "content_type": "paragraph",
                        "content_data": "Third",
                    },
                ]
            ),
        },
    )

    assert result["success"] is True
    assert result["succeeded"] == 3
    assert result["failed"] == 0
    assert result["saved"] is True

    # Verify all three paragraphs exist
    _, read_result = await mcp.call_tool(
        "read", {"file_path": str(empty_docx), "scope": "blocks"}
    )
    texts = [b.get("text", "") for b in read_result["blocks"]]
    assert "First" in texts
    assert "Second" in texts
    assert "Third" in texts


# =============================================================================
# Fail-Fast Error Handling
# =============================================================================


@pytest.mark.asyncio
async def test_midway_failure_raises(sample_docx):
    """Failure raises exception immediately (fail-fast)."""
    original_bytes = sample_docx.read_bytes()

    # First op succeeds, second fails - raises immediately, no save
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": json.dumps(
                    [
                        {
                            "op": "append",
                            "content_type": "paragraph",
                            "content_data": "This should not be saved",
                        },
                        {
                            "op": "style",
                            "target_id": "nonexistent_id_12345",
                            "style_name": "Heading 1",
                        },
                    ]
                ),
            },
        )

    assert (
        "nonexistent_id_12345" in str(exc_info.value)
        or "not found" in str(exc_info.value).lower()
    )

    # File should be unchanged (fail-fast means no partial save)
    assert sample_docx.read_bytes() == original_bytes


@pytest.mark.asyncio
async def test_first_op_failure_no_save(sample_docx):
    """First op failure raises exception, nothing is saved."""
    original_bytes = sample_docx.read_bytes()

    with pytest.raises(ToolError):
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": json.dumps(
                    [
                        {
                            "op": "style",
                            "target_id": "nonexistent_id_12345",
                            "style_name": "Heading 1",
                        },
                    ]
                ),
            },
        )

    # File unchanged when nothing succeeded
    assert sample_docx.read_bytes() == original_bytes


# =============================================================================
# Validation Errors (before opening document)
# =============================================================================


@pytest.mark.asyncio
async def test_invalid_json_ops(sample_docx):
    """Invalid JSON in ops raises JSONDecodeError."""
    original_bytes = sample_docx.read_bytes()

    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {"file_path": str(sample_docx), "ops": "not valid json {"},
        )

    assert "JSON" in str(exc_info.value) or "Expecting" in str(exc_info.value)
    assert sample_docx.read_bytes() == original_bytes


@pytest.mark.asyncio
async def test_ops_not_array(sample_docx):
    """ops must be a JSON array - raises ValueError."""
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {"file_path": str(sample_docx), "ops": json.dumps({"op": "append"})},
        )

    assert "must be a JSON array" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ops_item_not_dict(sample_docx):
    """Each item in ops must be an object - raises ValueError."""
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {"file_path": str(sample_docx), "ops": json.dumps(["not a dict"])},
        )

    assert "must be an object" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ops_missing_op_field(sample_docx):
    """Each operation must have an 'op' field - raises ValueError."""
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": json.dumps([{"content_data": "test"}]),
            },
        )

    assert "missing 'op'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ops_limit_500(sample_docx):
    """Maximum 500 operations per batch - raises ValueError."""
    ops = [{"op": "append", "content_data": f"para {i}"} for i in range(501)]
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {"file_path": str(sample_docx), "ops": json.dumps(ops)},
        )

    assert "500" in str(exc_info.value)


# =============================================================================
# Footnote Operations in Batch
# =============================================================================


@pytest.mark.asyncio
async def test_batch_footnote_atomic(empty_docx):
    """Footnotes work in batch mode."""
    # Add a paragraph then add footnote to it in one batch
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(empty_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "append",
                        "content_type": "paragraph",
                        "content_data": "Main text",
                    },
                    {
                        "op": "add_footnote",
                        "target_id": "$prev[0]",
                        "content_data": json.dumps(
                            {"text": "This is a footnote", "note_type": "footnote"}
                        ),
                    },
                ]
            ),
        },
    )

    assert result["success"] is True
    assert result["succeeded"] == 2
    assert result["saved"] is True

    # Verify footnote exists
    _, read_result = await mcp.call_tool(
        "read", {"file_path": str(empty_docx), "scope": "footnotes"}
    )
    assert len(read_result["footnotes"]) == 1
    assert read_result["footnotes"][0]["text"] == "This is a footnote"


@pytest.mark.asyncio
async def test_batch_footnote_atomic_failure_no_save(empty_docx):
    """Failure raises exception and file is unchanged (fail-fast)."""
    original_bytes = empty_docx.read_bytes()

    with pytest.raises(ToolError):
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(empty_docx),
                "ops": json.dumps(
                    [
                        {
                            "op": "append",
                            "content_type": "paragraph",
                            "content_data": "Main text",
                        },
                        {
                            "op": "add_footnote",
                            "target_id": "$prev[0]",
                            "content_data": json.dumps({"text": "Footnote text"}),
                        },
                        {
                            "op": "style",
                            "target_id": "nonexistent",
                            "style_name": "Heading 1",
                        },
                    ]
                ),
            },
        )

    # File must be unchanged (fail-fast raises before save)
    assert empty_docx.read_bytes() == original_bytes


# =============================================================================
# Comment Operations in Batch
# =============================================================================


@pytest.mark.asyncio
async def test_batch_comment_returns_comment_id(empty_docx):
    """Comment operations return comment_id in OpResult."""
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(empty_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "append",
                        "content_type": "paragraph",
                        "content_data": "Text to comment on",
                    },
                    {
                        "op": "add_comment",
                        "target_id": "$prev[0]",
                        "content_data": "This is a comment",
                        "author": "Test Author",
                    },
                ]
            ),
        },
    )

    assert result["success"] is True
    assert result["results"][1]["success"] is True
    assert result["results"][1]["comment_id"] is not None
    assert isinstance(result["results"][1]["comment_id"], int)


# =============================================================================
# Auto-create (edit on non-existent file)
# =============================================================================


@pytest.mark.asyncio
async def test_edit_auto_creates_new_file():
    """edit() auto-creates a new .docx file if it doesn't exist."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)
    path.unlink()  # ensure file doesn't exist

    try:
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(path),
                "ops": json.dumps(
                    [
                        {
                            "op": "append",
                            "content_type": "heading",
                            "content_data": "New Document",
                            "heading_level": 1,
                        }
                    ]
                ),
            },
        )

        assert result["success"] is True
        assert path.exists()

        # Verify content
        _, read_result = await mcp.call_tool(
            "read", {"file_path": str(path), "scope": "outline"}
        )
        assert read_result["block_count"] >= 1
        texts = [b["text"] for b in read_result["blocks"]]
        assert any("New Document" in t for t in texts)
    finally:
        path.unlink(missing_ok=True)
