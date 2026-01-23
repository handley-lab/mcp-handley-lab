"""Tests for Word document batch operations (Issue #127).

Tests the ops array interface, $prev[N] chaining, atomic/partial modes,
and batch-specific error handling.
"""

import json
import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.microsoft.word.tool import mcp


@pytest.fixture
async def sample_docx():
    """Create a sample Word document for batch testing."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)

    # Create document with heading and table
    await mcp.call_tool(
        "create",
        {
            "file_path": str(path),
            "content_type": "heading",
            "content_data": "Batch Test Document",
            "heading_level": 1,
        },
    )

    # Add a 2x2 table
    table_data = json.dumps([["A", "B"], ["C", "D"]])
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": json.dumps(
                [{"op": "append", "content_type": "table", "content_data": table_data}]
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

    await mcp.call_tool(
        "create",
        {
            "file_path": str(path),
            "content_type": "paragraph",
            "content_data": "",
        },
    )

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
    """$prev[N] where N >= current index fails."""
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(empty_docx),
            "ops": json.dumps(
                [
                    {"op": "style", "target_id": "$prev[0]", "style_name": "Heading 1"},
                ]
            ),
        },
    )

    assert result["success"] is False
    assert result["failed"] == 1
    assert "Invalid $prev reference" in result["results"][0]["error"]
    assert "index >= current" in result["results"][0]["error"]
    assert result["saved"] is False


@pytest.mark.asyncio
async def test_prev_reference_empty_element_id(sample_docx):
    """$prev[N] referencing an op with empty element_id fails."""
    # set_meta returns empty element_id, then try to reference it
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "set_meta",
                        "content_data": json.dumps({"title": "New Title"}),
                    },
                    {"op": "style", "target_id": "$prev[0]", "style_name": "Heading 1"},
                ]
            ),
        },
    )

    assert result["success"] is False
    # First op succeeds
    assert result["results"][0]["success"] is True
    assert result["results"][0]["element_id"] == ""
    # Second op fails due to empty element_id
    assert result["results"][1]["success"] is False
    assert "empty element_id" in result["results"][1]["error"]


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
async def test_atomic_mode_failure_leaves_file_unchanged(sample_docx):
    """Atomic mode: failure means file is not modified at all."""
    original_bytes = sample_docx.read_bytes()

    # First op succeeds, second fails
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "mode": "atomic",
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

    assert result["success"] is False
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert result["saved"] is False

    # File must be unchanged
    assert sample_docx.read_bytes() == original_bytes


@pytest.mark.asyncio
async def test_atomic_mode_success_saves_all(empty_docx):
    """Atomic mode: all operations succeed, file is saved."""
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(empty_docx),
            "mode": "atomic",
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
# Partial Mode (save successful ops before failure)
# =============================================================================


@pytest.mark.asyncio
async def test_partial_mode_saves_successful_ops(sample_docx):
    """Partial mode: successful ops are saved before failure."""
    original_bytes = sample_docx.read_bytes()

    # First op succeeds, second fails
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "mode": "partial",
            "ops": json.dumps(
                [
                    {
                        "op": "append",
                        "content_type": "paragraph",
                        "content_data": "This should be saved",
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

    assert result["success"] is False
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert result["saved"] is True  # Prior success was saved

    # File should be modified (unlike atomic)
    assert sample_docx.read_bytes() != original_bytes

    # Verify first operation was saved
    _, read_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    texts = [b.get("text", "") for b in read_result["blocks"]]
    assert "This should be saved" in texts


@pytest.mark.asyncio
async def test_partial_mode_all_fail_no_save(sample_docx):
    """Partial mode: if first op fails, nothing is saved."""
    original_bytes = sample_docx.read_bytes()

    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "mode": "partial",
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

    assert result["success"] is False
    assert result["succeeded"] == 0
    assert result["failed"] == 1
    assert result["saved"] is False

    # File unchanged when nothing succeeded
    assert sample_docx.read_bytes() == original_bytes


# =============================================================================
# Validation Errors (before opening document)
# =============================================================================


@pytest.mark.asyncio
async def test_invalid_json_ops(sample_docx):
    """Invalid JSON in ops returns error without opening document."""
    original_bytes = sample_docx.read_bytes()

    _, result = await mcp.call_tool(
        "edit",
        {"file_path": str(sample_docx), "ops": "not valid json {"},
    )

    assert result["success"] is False
    assert "JSON parse error" in result["error"]
    assert result["total"] == 0
    assert result["results"] == []
    assert result["saved"] is False
    assert sample_docx.read_bytes() == original_bytes


@pytest.mark.asyncio
async def test_ops_not_array(sample_docx):
    """ops must be a JSON array."""
    _, result = await mcp.call_tool(
        "edit",
        {"file_path": str(sample_docx), "ops": json.dumps({"op": "append"})},
    )

    assert result["success"] is False
    assert "must be a JSON array" in result["message"]
    assert result["results"] == []
    assert result["saved"] is False


@pytest.mark.asyncio
async def test_ops_item_not_dict(sample_docx):
    """Each item in ops must be an object."""
    _, result = await mcp.call_tool(
        "edit",
        {"file_path": str(sample_docx), "ops": json.dumps(["not a dict"])},
    )

    assert result["success"] is False
    assert "is not an object" in result["message"]
    assert result["results"] == []
    assert result["saved"] is False


@pytest.mark.asyncio
async def test_ops_missing_op_field(sample_docx):
    """Each operation must have an 'op' field."""
    _, result = await mcp.call_tool(
        "edit",
        {"file_path": str(sample_docx), "ops": json.dumps([{"content_data": "test"}])},
    )

    assert result["success"] is False
    assert "missing 'op'" in result["message"]
    assert result["saved"] is False


@pytest.mark.asyncio
async def test_excluded_operation_create(sample_docx):
    """'create' operation is excluded from batch mode."""
    _, result = await mcp.call_tool(
        "edit",
        {"file_path": str(sample_docx), "ops": json.dumps([{"op": "create"}])},
    )

    assert result["success"] is False
    assert "cannot be used in batch" in result["message"]
    assert result["saved"] is False


@pytest.mark.asyncio
async def test_ops_limit_500(sample_docx):
    """Maximum 500 operations per batch."""
    ops = [{"op": "append", "content_data": f"para {i}"} for i in range(501)]
    _, result = await mcp.call_tool(
        "edit",
        {"file_path": str(sample_docx), "ops": json.dumps(ops)},
    )

    assert result["success"] is False
    assert "500" in result["message"]
    assert result["saved"] is False


# =============================================================================
# Footnote Operations in Batch
# =============================================================================


@pytest.mark.asyncio
async def test_batch_footnote_atomic(empty_docx):
    """Footnotes work in batch mode without breaking atomicity."""
    # Add a paragraph then add footnote to it in one batch
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(empty_docx),
            "mode": "atomic",
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
    """Footnote op followed by failure leaves file unchanged in atomic mode."""
    original_bytes = empty_docx.read_bytes()

    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(empty_docx),
            "mode": "atomic",
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

    assert result["success"] is False
    assert result["succeeded"] == 2  # append and add_footnote succeeded
    assert result["failed"] == 1
    assert result["saved"] is False  # atomic mode: nothing saved

    # File must be unchanged
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
# Create Tool (Separate from Batch)
# =============================================================================


@pytest.mark.asyncio
async def test_create_tool_works():
    """Separate create() tool creates new document."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)

    try:
        _, result = await mcp.call_tool(
            "create",
            {
                "file_path": str(path),
                "content_type": "heading",
                "content_data": "New Document",
                "heading_level": 1,
            },
        )

        assert result["success"] is True
        assert result["element_id"] != ""
        assert path.exists()

        # Verify content
        _, read_result = await mcp.call_tool(
            "read", {"file_path": str(path), "scope": "outline"}
        )
        assert read_result["block_count"] == 1
        assert "New Document" in read_result["blocks"][0]["text"]
    finally:
        path.unlink(missing_ok=True)
