"""Tests for nested table cell editing (Issue #166).

Tests the hierarchical ID system for targeting nested tables:
- table_abc_0#r0c0/tbl0 - nested table inside cell (0,0)
- table_abc_0#r0c0/tbl0/r1c2 - cell (1,2) in nested table
"""

import tempfile
from pathlib import Path

import pytest
from lxml import etree
from mcp.server.fastmcp.exceptions import ToolError

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.package import WordPackage
from mcp_handley_lab.microsoft.word.tool import mcp


def _create_doc_with_nested_table() -> Path:
    """Create a document with a nested table structure.

    Outer table (2x2):
        (0,0): "Outer A" + nested table (2x2)
        (0,1): "Outer B"
        (1,0): "Outer C"
        (1,1): "Outer D"

    Nested table in (0,0):
        (0,0): "Inner A"
        (0,1): "Inner B"
        (1,0): "Inner C"
        (1,1): "Inner D"
    """
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)

    # Create document using WordPackage
    pkg = WordPackage.new()
    body = pkg.body

    # Remove default empty paragraph
    for p in list(body.findall(qn("w:p"))):
        body.remove(p)

    # Build outer table
    outer_tbl = etree.SubElement(body, qn("w:tbl"))

    # Table properties
    tblPr = etree.SubElement(outer_tbl, qn("w:tblPr"))
    tblBorders = etree.SubElement(tblPr, qn("w:tblBorders"))
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = etree.SubElement(tblBorders, qn(f"w:{side}"))
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), "4")
        border.set(qn("w:color"), "auto")

    # Grid
    tblGrid = etree.SubElement(outer_tbl, qn("w:tblGrid"))
    for _ in range(2):
        gridCol = etree.SubElement(tblGrid, qn("w:gridCol"))
        gridCol.set(qn("w:w"), "2160")

    # Row 0
    tr0 = etree.SubElement(outer_tbl, qn("w:tr"))

    # Cell (0,0) with nested table
    tc00 = etree.SubElement(tr0, qn("w:tc"))
    p00 = etree.SubElement(tc00, qn("w:p"))
    r00 = etree.SubElement(p00, qn("w:r"))
    t00 = etree.SubElement(r00, qn("w:t"))
    t00.text = "Outer A"

    # Nested table inside cell (0,0)
    inner_tbl = etree.SubElement(tc00, qn("w:tbl"))
    inner_tblPr = etree.SubElement(inner_tbl, qn("w:tblPr"))
    inner_tblBorders = etree.SubElement(inner_tblPr, qn("w:tblBorders"))
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = etree.SubElement(inner_tblBorders, qn(f"w:{side}"))
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), "4")
        border.set(qn("w:color"), "FF0000")  # Red to distinguish

    inner_tblGrid = etree.SubElement(inner_tbl, qn("w:tblGrid"))
    for _ in range(2):
        gridCol = etree.SubElement(inner_tblGrid, qn("w:gridCol"))
        gridCol.set(qn("w:w"), "1080")

    # Inner table rows
    for _row_idx, (text_a, text_b) in enumerate(
        [("Inner A", "Inner B"), ("Inner C", "Inner D")]
    ):
        inner_tr = etree.SubElement(inner_tbl, qn("w:tr"))
        for text in [text_a, text_b]:
            inner_tc = etree.SubElement(inner_tr, qn("w:tc"))
            inner_p = etree.SubElement(inner_tc, qn("w:p"))
            inner_r = etree.SubElement(inner_p, qn("w:r"))
            inner_t = etree.SubElement(inner_r, qn("w:t"))
            inner_t.text = text

    # Cell (0,1)
    tc01 = etree.SubElement(tr0, qn("w:tc"))
    p01 = etree.SubElement(tc01, qn("w:p"))
    r01 = etree.SubElement(p01, qn("w:r"))
    t01 = etree.SubElement(r01, qn("w:t"))
    t01.text = "Outer B"

    # Row 1
    tr1 = etree.SubElement(outer_tbl, qn("w:tr"))
    for text in ["Outer C", "Outer D"]:
        tc = etree.SubElement(tr1, qn("w:tc"))
        p = etree.SubElement(tc, qn("w:p"))
        r = etree.SubElement(p, qn("w:r"))
        t = etree.SubElement(r, qn("w:t"))
        t.text = text

    pkg.save(str(path))
    return path


@pytest.fixture
def nested_table_doc():
    """Fixture providing a document with nested table structure."""
    path = _create_doc_with_nested_table()
    yield path
    path.unlink(missing_ok=True)


# =============================================================================
# Read operation tests
# =============================================================================


@pytest.mark.asyncio
async def test_read_outer_table_shows_nested_count(nested_table_doc):
    """Verify outer table cells report nested_tables count."""
    # First get the table ID
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(nested_table_doc), "scope": "blocks"},
    )
    table_block = [b for b in result["blocks"] if b["type"] == "table"][0]
    table_id = table_block["id"]

    # Read table cells
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(nested_table_doc),
            "scope": "table_cells",
            "target_id": table_id,
        },
    )

    # Cell (0,0) should have nested_tables=1
    cell_00 = [c for c in result["cells"] if c["row"] == 0 and c["col"] == 0][0]
    assert cell_00["nested_tables"] == 1, (
        f"Expected 1 nested table, got {cell_00['nested_tables']}"
    )

    # Other cells should have nested_tables=0
    for cell in result["cells"]:
        if cell["row"] != 0 or cell["col"] != 0:
            assert cell["nested_tables"] == 0, (
                f"Cell ({cell['row']},{cell['col']}) should have no nested tables"
            )


@pytest.mark.asyncio
async def test_read_nested_table_cells(nested_table_doc):
    """Verify reading nested table cells via hierarchical ID."""
    # First get the outer table ID
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(nested_table_doc), "scope": "blocks"},
    )
    table_block = [b for b in result["blocks"] if b["type"] == "table"][0]
    outer_table_id = table_block["id"]

    # Read nested table cells using hierarchical ID
    nested_table_id = f"{outer_table_id}#r0c0/tbl0"
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(nested_table_doc),
            "scope": "table_cells",
            "target_id": nested_table_id,
        },
    )

    # Should have 4 cells (2x2)
    assert len(result["cells"]) == 4, f"Expected 4 cells, got {len(result['cells'])}"
    assert result["table_rows"] == 2
    assert result["table_cols"] == 2

    # Verify cell contents
    cell_texts = {(c["row"], c["col"]): c["text"] for c in result["cells"]}
    assert cell_texts[(0, 0)] == "Inner A"
    assert cell_texts[(0, 1)] == "Inner B"
    assert cell_texts[(1, 0)] == "Inner C"
    assert cell_texts[(1, 1)] == "Inner D"


@pytest.mark.asyncio
async def test_read_nested_table_layout(nested_table_doc):
    """Verify reading nested table layout via hierarchical ID."""
    # Get outer table ID
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(nested_table_doc), "scope": "blocks"},
    )
    table_block = [b for b in result["blocks"] if b["type"] == "table"][0]
    outer_table_id = table_block["id"]

    # Read nested table layout
    nested_table_id = f"{outer_table_id}#r0c0/tbl0"
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(nested_table_doc),
            "scope": "table_layout",
            "target_id": nested_table_id,
        },
    )

    # Should have layout for nested table
    assert result["table_layout"] is not None
    assert result["table_layout"]["table_id"] == nested_table_id
    assert len(result["table_layout"]["rows"]) == 2


# =============================================================================
# Edit operation tests
# =============================================================================


@pytest.mark.asyncio
async def test_edit_nested_table_cell(nested_table_doc):
    """Verify editing a cell in a nested table."""
    # Get outer table ID
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(nested_table_doc), "scope": "blocks"},
    )
    table_block = [b for b in result["blocks"] if b["type"] == "table"][0]
    outer_table_id = table_block["id"]

    # Edit cell (1,1) in nested table
    nested_table_id = f"{outer_table_id}#r0c0/tbl0"
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(nested_table_doc),
            "operation": "edit_cell",
            "target_id": nested_table_id,
            "row": 1,
            "col": 1,
            "content_data": "MODIFIED",
        },
    )

    # After edit, the outer table ID changes (content-addressed)
    # Re-read blocks to get the new table ID
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(nested_table_doc), "scope": "blocks"},
    )
    table_block = [b for b in result["blocks"] if b["type"] == "table"][0]
    new_outer_table_id = table_block["id"]
    new_nested_table_id = f"{new_outer_table_id}#r0c0/tbl0"

    # Verify the nested cell was modified
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(nested_table_doc),
            "scope": "table_cells",
            "target_id": new_nested_table_id,
        },
    )
    cell_11 = [c for c in result["cells"] if c["row"] == 1 and c["col"] == 1][0]
    assert cell_11["text"] == "MODIFIED"

    # Verify outer table cell (1,1) was NOT modified
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(nested_table_doc),
            "scope": "table_cells",
            "target_id": new_outer_table_id,
        },
    )
    outer_cell_11 = [c for c in result["cells"] if c["row"] == 1 and c["col"] == 1][0]
    assert outer_cell_11["text"] == "Outer D", "Outer table should be unchanged"


@pytest.mark.asyncio
async def test_edit_nested_table_add_row(nested_table_doc):
    """Verify adding a row to a nested table."""
    # Get outer table ID
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(nested_table_doc), "scope": "blocks"},
    )
    table_block = [b for b in result["blocks"] if b["type"] == "table"][0]
    outer_table_id = table_block["id"]

    # Add row to nested table
    nested_table_id = f"{outer_table_id}#r0c0/tbl0"
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(nested_table_doc),
            "operation": "add_row",
            "target_id": nested_table_id,
            "content_data": '["New A", "New B"]',
        },
    )

    # After edit, re-read to get updated table IDs (content-addressed)
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(nested_table_doc), "scope": "blocks"},
    )
    table_block = [b for b in result["blocks"] if b["type"] == "table"][0]
    new_outer_table_id = table_block["id"]
    new_nested_table_id = f"{new_outer_table_id}#r0c0/tbl0"

    # Verify nested table now has 3 rows
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(nested_table_doc),
            "scope": "table_cells",
            "target_id": new_nested_table_id,
        },
    )
    assert result["table_rows"] == 3

    # Verify outer table still has 2 rows
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(nested_table_doc),
            "scope": "table_cells",
            "target_id": new_outer_table_id,
        },
    )
    assert result["table_rows"] == 2


@pytest.mark.asyncio
async def test_edit_nested_table_set_alignment(nested_table_doc):
    """Verify setting alignment on a nested table."""
    # Get outer table ID
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(nested_table_doc), "scope": "blocks"},
    )
    table_block = [b for b in result["blocks"] if b["type"] == "table"][0]
    outer_table_id = table_block["id"]

    # Set alignment on nested table
    nested_table_id = f"{outer_table_id}#r0c0/tbl0"
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(nested_table_doc),
            "operation": "set_table_alignment",
            "target_id": nested_table_id,
            "content_data": "center",
        },
    )

    # Verify nested table has center alignment
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(nested_table_doc),
            "scope": "table_layout",
            "target_id": nested_table_id,
        },
    )
    assert result["table_layout"]["alignment"] == "center"


# =============================================================================
# Edge case tests
# =============================================================================


@pytest.mark.asyncio
async def test_multiple_nested_tables_in_same_cell():
    """Verify handling multiple nested tables in the same cell."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)

    try:
        # Create document with 2 nested tables in cell (0,0)
        pkg = WordPackage.new()
        body = pkg.body

        # Remove default empty paragraph
        for p in list(body.findall(qn("w:p"))):
            body.remove(p)

        outer_tbl = etree.SubElement(body, qn("w:tbl"))
        etree.SubElement(outer_tbl, qn("w:tblPr"))  # Required for valid structure
        tblGrid = etree.SubElement(outer_tbl, qn("w:tblGrid"))
        etree.SubElement(tblGrid, qn("w:gridCol")).set(qn("w:w"), "4320")

        tr = etree.SubElement(outer_tbl, qn("w:tr"))
        tc = etree.SubElement(tr, qn("w:tc"))

        # Two nested tables
        for table_name in ["First", "Second"]:
            inner_tbl = etree.SubElement(tc, qn("w:tbl"))
            etree.SubElement(inner_tbl, qn("w:tblPr"))  # Required for valid structure
            inner_tblGrid = etree.SubElement(inner_tbl, qn("w:tblGrid"))
            etree.SubElement(inner_tblGrid, qn("w:gridCol")).set(qn("w:w"), "2160")

            inner_tr = etree.SubElement(inner_tbl, qn("w:tr"))
            inner_tc = etree.SubElement(inner_tr, qn("w:tc"))
            inner_p = etree.SubElement(inner_tc, qn("w:p"))
            inner_r = etree.SubElement(inner_p, qn("w:r"))
            inner_t = etree.SubElement(inner_r, qn("w:t"))
            inner_t.text = f"{table_name} Table"

        pkg.save(str(path))

        # Get outer table ID
        _, result = await mcp.call_tool(
            "read",
            {"file_path": str(path), "scope": "blocks"},
        )
        table_block = [b for b in result["blocks"] if b["type"] == "table"][0]
        outer_table_id = table_block["id"]

        # Read outer table cells - should show nested_tables=2
        _, result = await mcp.call_tool(
            "read",
            {
                "file_path": str(path),
                "scope": "table_cells",
                "target_id": outer_table_id,
            },
        )
        cell_00 = [c for c in result["cells"] if c["row"] == 0 and c["col"] == 0][0]
        assert cell_00["nested_tables"] == 2

        # Access first nested table (tbl0)
        _, result = await mcp.call_tool(
            "read",
            {
                "file_path": str(path),
                "scope": "table_cells",
                "target_id": f"{outer_table_id}#r0c0/tbl0",
            },
        )
        assert result["cells"][0]["text"] == "First Table"

        # Access second nested table (tbl1)
        _, result = await mcp.call_tool(
            "read",
            {
                "file_path": str(path),
                "scope": "table_cells",
                "target_id": f"{outer_table_id}#r0c0/tbl1",
            },
        )
        assert result["cells"][0]["text"] == "Second Table"

    finally:
        path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_backward_compatibility_non_nested_tables(nested_table_doc):
    """Verify non-nested table operations still work correctly."""
    # Get outer table ID
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(nested_table_doc), "scope": "blocks"},
    )
    table_block = [b for b in result["blocks"] if b["type"] == "table"][0]
    outer_table_id = table_block["id"]

    # Edit outer table cell (1,1) - should work as before
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(nested_table_doc),
            "operation": "edit_cell",
            "target_id": outer_table_id,
            "row": 1,
            "col": 1,
            "content_data": "Modified Outer D",
        },
    )

    # After edit, ID changes (content-addressed) - use element_id from result
    new_outer_table_id = edit_result["element_id"]

    # Verify outer table was modified
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(nested_table_doc),
            "scope": "table_cells",
            "target_id": new_outer_table_id,
        },
    )
    cell_11 = [c for c in result["cells"] if c["row"] == 1 and c["col"] == 1][0]
    assert cell_11["text"] == "Modified Outer D"


@pytest.mark.asyncio
async def test_invalid_nested_table_index(nested_table_doc):
    """Verify error handling for invalid nested table index."""
    # Get outer table ID
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(nested_table_doc), "scope": "blocks"},
    )
    table_block = [b for b in result["blocks"] if b["type"] == "table"][0]
    outer_table_id = table_block["id"]

    # Try to access non-existent tbl1 (only tbl0 exists in cell 0,0)
    with pytest.raises(ToolError, match=r"index.*out of range"):
        await mcp.call_tool(
            "read",
            {
                "file_path": str(nested_table_doc),
                "scope": "table_cells",
                "target_id": f"{outer_table_id}#r0c0/tbl1",
            },
        )


@pytest.mark.asyncio
async def test_deep_nesting_two_levels():
    """Verify 2+ levels of nested tables work via hierarchical paths.

    Structure:
        Outer table (1x1):
            (0,0): "Outer" + nested table L1 (1x1)
                L1 (0,0): "Level 1" + nested table L2 (1x1)
                    L2 (0,0): "Level 2"

    This tests the descendant XPath in get_cell_tables() which finds
    ALL nested tables in a cell subtree, enabling paths like:
    table_X#r0c0/tbl0/r0c0/tbl0
    """
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)

    try:
        pkg = WordPackage.new()
        body = pkg.body

        # Remove default empty paragraph
        for p in list(body.findall(qn("w:p"))):
            body.remove(p)

        # Build outer table (level 0)
        outer_tbl = etree.SubElement(body, qn("w:tbl"))
        etree.SubElement(outer_tbl, qn("w:tblPr"))  # Required for valid structure
        outer_tblGrid = etree.SubElement(outer_tbl, qn("w:tblGrid"))
        etree.SubElement(outer_tblGrid, qn("w:gridCol")).set(qn("w:w"), "4320")

        outer_tr = etree.SubElement(outer_tbl, qn("w:tr"))
        outer_tc = etree.SubElement(outer_tr, qn("w:tc"))
        outer_p = etree.SubElement(outer_tc, qn("w:p"))
        outer_r = etree.SubElement(outer_p, qn("w:r"))
        outer_t = etree.SubElement(outer_r, qn("w:t"))
        outer_t.text = "Outer"

        # Build level 1 nested table
        l1_tbl = etree.SubElement(outer_tc, qn("w:tbl"))
        etree.SubElement(l1_tbl, qn("w:tblPr"))  # Required for valid structure
        l1_tblGrid = etree.SubElement(l1_tbl, qn("w:tblGrid"))
        etree.SubElement(l1_tblGrid, qn("w:gridCol")).set(qn("w:w"), "3240")

        l1_tr = etree.SubElement(l1_tbl, qn("w:tr"))
        l1_tc = etree.SubElement(l1_tr, qn("w:tc"))
        l1_p = etree.SubElement(l1_tc, qn("w:p"))
        l1_r = etree.SubElement(l1_p, qn("w:r"))
        l1_t = etree.SubElement(l1_r, qn("w:t"))
        l1_t.text = "Level 1"

        # Build level 2 nested table (inside level 1)
        l2_tbl = etree.SubElement(l1_tc, qn("w:tbl"))
        etree.SubElement(l2_tbl, qn("w:tblPr"))  # Required for valid structure
        l2_tblGrid = etree.SubElement(l2_tbl, qn("w:tblGrid"))
        etree.SubElement(l2_tblGrid, qn("w:gridCol")).set(qn("w:w"), "2160")

        l2_tr = etree.SubElement(l2_tbl, qn("w:tr"))
        l2_tc = etree.SubElement(l2_tr, qn("w:tc"))
        l2_p = etree.SubElement(l2_tc, qn("w:p"))
        l2_r = etree.SubElement(l2_p, qn("w:r"))
        l2_t = etree.SubElement(l2_r, qn("w:t"))
        l2_t.text = "Level 2"

        pkg.save(str(path))

        # Get outer table ID
        _, result = await mcp.call_tool(
            "read",
            {"file_path": str(path), "scope": "blocks"},
        )
        table_block = [b for b in result["blocks"] if b["type"] == "table"][0]
        outer_table_id = table_block["id"]

        # Read outer table cells - nested_tables=2 (descendant search finds L1 and L2)
        _, result = await mcp.call_tool(
            "read",
            {
                "file_path": str(path),
                "scope": "table_cells",
                "target_id": outer_table_id,
            },
        )
        # Note: get_cell_tables() uses descendant XPath so it finds ALL tables
        # in the subtree - both L1 AND L2 (even though L2 is inside L1)
        assert result["cells"][0]["nested_tables"] == 2

        # Read level 1 nested table
        l1_table_id = f"{outer_table_id}#r0c0/tbl0"
        _, result = await mcp.call_tool(
            "read",
            {"file_path": str(path), "scope": "table_cells", "target_id": l1_table_id},
        )
        # Cell text includes nested content, so check it starts with expected text
        assert result["cells"][0]["text"].startswith("Level 1")
        # L1 cell should show it has a nested table too
        assert result["cells"][0]["nested_tables"] == 1

        # Read level 2 nested table (2 levels deep!)
        l2_table_id = f"{outer_table_id}#r0c0/tbl0/r0c0/tbl0"
        _, result = await mcp.call_tool(
            "read",
            {"file_path": str(path), "scope": "table_cells", "target_id": l2_table_id},
        )
        # L2 has no nested tables, so text should be exact
        assert result["cells"][0]["text"] == "Level 2"
        assert result["cells"][0]["nested_tables"] == 0  # No deeper nesting

        # Edit the deepest nested cell
        _, edit_result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(path),
                "operation": "edit_cell",
                "target_id": l2_table_id,
                "row": 0,
                "col": 0,
                "content_data": "DEEP EDIT",
            },
        )

        # Re-read blocks to get updated IDs
        _, result = await mcp.call_tool(
            "read",
            {"file_path": str(path), "scope": "blocks"},
        )
        table_block = [b for b in result["blocks"] if b["type"] == "table"][0]
        new_outer_table_id = table_block["id"]
        new_l2_table_id = f"{new_outer_table_id}#r0c0/tbl0/r0c0/tbl0"

        # Verify the deep edit worked
        _, result = await mcp.call_tool(
            "read",
            {
                "file_path": str(path),
                "scope": "table_cells",
                "target_id": new_l2_table_id,
            },
        )
        assert result["cells"][0]["text"] == "DEEP EDIT"

    finally:
        path.unlink(missing_ok=True)
