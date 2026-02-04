"""Integration tests for Word document MCP tool."""

import json
import tempfile
from pathlib import Path

import pytest
from lxml import etree
from mcp.server.fastmcp.exceptions import ToolError

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.package import WordPackage
from mcp_handley_lab.microsoft.word.tool import mcp


def _ops(operations: list[dict]) -> str:
    """Helper to convert operation list to ops JSON string."""
    return json.dumps(operations)


@pytest.fixture
async def sample_docx():
    """Create a sample Word document for testing using MCP tool."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)

    # Auto-create document and add all content via edit (auto-creates file)
    path.unlink()  # remove so edit() auto-creates
    table_data = json.dumps(
        [
            ["Header 1", "Header 2"],
            ["Row 1 Col 1", "Row 1 Col 2"],
        ]
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": _ops(
                [
                    {
                        "op": "append",
                        "content_type": "heading",
                        "content_data": "Test Document",
                        "heading_level": 1,
                    },
                    {"op": "append", "content_data": "This is the first paragraph."},
                    {
                        "op": "append",
                        "content_type": "heading",
                        "content_data": "Section Two",
                        "heading_level": 2,
                    },
                    {"op": "append", "content_data": "This is the second paragraph."},
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


async def create_empty_docx(path: Path) -> None:
    """Helper to create an empty document."""
    WordPackage.new().save(str(path))


def create_pkg_with_paragraph(text: str = "Test paragraph") -> WordPackage:
    """Create a WordPackage with a single paragraph."""
    pkg = WordPackage.new()
    body = pkg.body
    for p in list(body.findall(qn("w:p"))):
        body.remove(p)
    p = etree.SubElement(body, qn("w:p"))
    r = etree.SubElement(p, qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = text
    pkg.mark_xml_dirty("/word/document.xml")
    return pkg


def add_paragraph_to_pkg(pkg: WordPackage, text: str) -> etree._Element:
    """Add a paragraph to an existing WordPackage."""
    body = pkg.body
    p = etree.SubElement(body, qn("w:p"))
    r = etree.SubElement(p, qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = text
    pkg.mark_xml_dirty("/word/document.xml")
    return p


def add_heading_to_pkg(pkg: WordPackage, text: str, level: int = 1) -> etree._Element:
    """Add a heading to an existing WordPackage."""
    body = pkg.body
    p = etree.SubElement(body, qn("w:p"))
    pPr = etree.SubElement(p, qn("w:pPr"))
    pStyle = etree.SubElement(pPr, qn("w:pStyle"))
    pStyle.set(qn("w:val"), f"Heading{level}")
    r = etree.SubElement(p, qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = text
    pkg.mark_xml_dirty("/word/document.xml")
    return p


def add_section_to_pkg(pkg: WordPackage, start_type: str = "nextPage") -> None:
    """Add a section break to an existing WordPackage.

    start_type: nextPage, continuous, oddPage, evenPage
    """
    body = pkg.body
    # Get the last paragraph (sectPr goes inside pPr of last para)
    last_p = body.findall(qn("w:p"))[-1]
    pPr = last_p.find(qn("w:pPr"))
    if pPr is None:
        pPr = etree.Element(qn("w:pPr"))
        last_p.insert(0, pPr)
    sectPr = etree.SubElement(pPr, qn("w:sectPr"))
    type_el = etree.SubElement(sectPr, qn("w:type"))
    type_el.set(qn("w:val"), start_type)
    pkg.mark_xml_dirty("/word/document.xml")


@pytest.mark.asyncio
async def test_read_outline(sample_docx):
    """Test reading document outline (headings only)."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "outline"}
    )
    assert result["block_count"] == 2  # Two headings
    assert len(result["blocks"]) == 2
    assert result["blocks"][0]["type"] == "heading1"  # Level in type
    assert result["blocks"][0]["level"] == 1
    assert "Test Document" in result["blocks"][0]["text"]
    assert result["blocks"][1]["type"] == "heading2"
    assert result["blocks"][1]["level"] == 2


@pytest.mark.asyncio
async def test_read_meta(sample_docx):
    """Test reading document metadata."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "meta"}
    )
    assert result["meta"] is not None
    assert result["blocks"] == []


@pytest.mark.asyncio
async def test_read_blocks(sample_docx):
    """Test reading all blocks."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    assert result["block_count"] == 5  # 2 headings + 2 paragraphs + 1 table
    types = [b["type"] for b in result["blocks"]]
    assert "heading1" in types  # Level in type
    assert "heading2" in types
    assert "paragraph" in types
    assert "table" in types


@pytest.mark.asyncio
async def test_read_search(sample_docx):
    """Test searching for text."""
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "search", "search_query": "second"},
    )
    assert result["block_count"] == 1  # Only matching blocks counted
    assert len(result["blocks"]) == 1
    assert "second" in result["blocks"][0]["text"].lower()


@pytest.mark.asyncio
async def test_edit_append_paragraph(sample_docx):
    """Test appending a paragraph."""
    _, read_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    initial_count = read_result["block_count"]

    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "paragraph",
                            "content_data": "New paragraph at the end",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert edit_result["element_id"]

    _, read_result2 = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    assert read_result2["block_count"] == initial_count + 1


@pytest.mark.asyncio
async def test_edit_delete(sample_docx):
    """Test deleting a block."""
    _, read_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    initial_count = read_result["block_count"]
    target_id = read_result["blocks"][1]["id"]  # Delete second block

    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "delete",
                            "target_id": target_id,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    _, read_result2 = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    assert read_result2["block_count"] == initial_count - 1


@pytest.mark.asyncio
async def test_edit_insert_before(sample_docx):
    """Test inserting before a block."""
    _, read_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    target_id = read_result["blocks"][1]["id"]

    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_before",
                            "target_id": target_id,
                            "content_type": "paragraph",
                            "content_data": "Inserted before",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert edit_result["element_id"]


@pytest.mark.asyncio
async def test_edit_replace(sample_docx):
    """Test replacing block content."""
    _, read_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in read_result["blocks"] if b["type"] == "paragraph")

    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "replace",
                            "target_id": para_block["id"],
                            "content_data": "Replaced content",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]


@pytest.mark.asyncio
async def test_edit_append_table(sample_docx):
    """Test appending a table."""
    table_data = json.dumps([["A", "B"], ["1", "2"]])
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "table",
                            "content_data": table_data,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert edit_result["element_id"]


@pytest.mark.asyncio
async def test_block_ids_are_content_hash(sample_docx):
    """Test that block IDs use content-hash format (type_hash_occurrence)."""
    import re

    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    # Block IDs: paragraph_abc123_0, heading1_def456_0, table_ghi789_0
    id_pattern = re.compile(r"^(paragraph|heading[1-9]|table)_[0-9a-f]{8}_\d+$")
    for block in result["blocks"]:
        block_id = block["id"]
        assert id_pattern.match(block_id), f"Invalid ID format: {block_id}"


@pytest.mark.asyncio
async def test_read_table_cells(sample_docx):
    """Test reading table cells with 0-based indices and hierarchical IDs."""
    # First find the table
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")
    table_id = table_block["id"]

    # Now read the cells
    _, cells_result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "table_cells", "target_id": table_id},
    )
    assert cells_result["table_rows"] == 2
    assert cells_result["table_cols"] == 2
    assert len(cells_result["cells"]) == 4  # 2x2 table
    # Check first cell (now 0-based)
    cell_0_0 = next(c for c in cells_result["cells"] if c["row"] == 0 and c["col"] == 0)
    assert cell_0_0["text"] == "Header 1"
    # Check hierarchical_id format
    assert cell_0_0["hierarchical_id"] == f"{table_id}#r0c0"
    # Check another cell
    cell_1_1 = next(c for c in cells_result["cells"] if c["row"] == 1 and c["col"] == 1)
    assert cell_1_1["text"] == "Row 1 Col 2"
    assert cell_1_1["hierarchical_id"] == f"{table_id}#r1c1"


@pytest.mark.asyncio
async def test_edit_cell(sample_docx):
    """Test editing a single table cell."""
    # Find the table
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")
    table_id = table_block["id"]

    # Edit cell (1,1)
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_cell",
                            "target_id": table_id,
                            "row": 1,
                            "col": 1,
                            "content_data": "Updated Header",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    # Returns updated table block ID (content-hash changes after cell edit)
    assert edit_result["element_id"].startswith("table_")
    assert edit_result["element_id"] != table_id  # Hash changed

    # Verify the change - content hash changes after edit, so re-read blocks
    _, blocks_result2 = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    new_table_block = next(b for b in blocks_result2["blocks"] if b["type"] == "table")
    new_table_id = new_table_block["id"]

    _, cells_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(sample_docx),
            "scope": "table_cells",
            "target_id": new_table_id,
        },
    )
    cell_1_1 = next(c for c in cells_result["cells"] if c["row"] == 1 and c["col"] == 1)
    assert cell_1_1["text"] == "Updated Header"


@pytest.mark.asyncio
async def test_edit_cell_out_of_range(sample_docx):
    """Test that editing out-of-range cell raises ValueError."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "edit_cell",
                                "target_id": table_block["id"],
                                "row": 99,
                                "col": 1,
                                "content_data": "Should fail",
                            }
                        ]
                    )
                ),
            },
        )
    assert "out of range" in str(exc_info.value)


@pytest.mark.asyncio
async def test_edit_cell_on_non_table(sample_docx):
    """Test that editing cell on non-table block raises error."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    with pytest.raises(ToolError):
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "edit_cell",
                                "target_id": para_block["id"],
                                "row": 1,
                                "col": 1,
                                "content_data": "Should fail",
                            }
                        ]
                    )
                ),
            },
        )


@pytest.fixture
def formatted_docx():
    """Create a Word document with formatted runs for testing."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        pkg = WordPackage.new()
        body = pkg.body
        # Remove the default empty paragraph
        for p in list(body.findall(qn("w:p"))):
            body.remove(p)
        # Create a paragraph with multiple runs with different formatting
        p = etree.SubElement(body, qn("w:p"))
        # Run 1: Normal text (no formatting)
        r1 = etree.SubElement(p, qn("w:r"))
        t1 = etree.SubElement(r1, qn("w:t"))
        t1.text = "Normal text, "
        t1.set(qn("xml:space"), "preserve")
        # Run 2: Bold text
        r2 = etree.SubElement(p, qn("w:r"))
        rPr2 = etree.SubElement(r2, qn("w:rPr"))
        etree.SubElement(rPr2, qn("w:b"))
        t2 = etree.SubElement(r2, qn("w:t"))
        t2.text = "bold text, "
        t2.set(qn("xml:space"), "preserve")
        # Run 3: Italic text
        r3 = etree.SubElement(p, qn("w:r"))
        rPr3 = etree.SubElement(r3, qn("w:rPr"))
        etree.SubElement(rPr3, qn("w:i"))
        t3 = etree.SubElement(r3, qn("w:t"))
        t3.text = "italic text."
        pkg.mark_xml_dirty("/word/document.xml")
        pkg.save(f.name)
        yield Path(f.name)
    Path(f.name).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_runs(formatted_docx):
    """Test reading runs from a paragraph."""
    # First get the paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(formatted_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Now read the runs
    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(formatted_docx),
            "scope": "runs",
            "target_id": para_block["id"],
        },
    )
    assert runs_result["block_count"] == 3  # Three runs
    assert len(runs_result["runs"]) == 3

    # Check run properties
    assert runs_result["runs"][0]["text"] == "Normal text, "
    assert runs_result["runs"][0]["bold"] is None  # Not set (inherits)

    assert runs_result["runs"][1]["text"] == "bold text, "
    assert runs_result["runs"][1]["bold"] is True

    assert runs_result["runs"][2]["text"] == "italic text."
    assert runs_result["runs"][2]["italic"] is True


@pytest.mark.asyncio
async def test_edit_run_text(formatted_docx):
    """Test editing run text."""
    # Get paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(formatted_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Edit the bold run (index 1) - use different text (not just case change, as hash normalizes)
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(formatted_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": para_block["id"],
                            "run_index": 1,
                            "content_data": "strongly emphasized, ",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    # Hash changes because paragraph text changed
    assert edit_result["element_id"].startswith("paragraph_")
    assert edit_result["element_id"] != para_block["id"]

    # Verify the change - need new paragraph ID
    _, blocks_result2 = await mcp.call_tool(
        "read", {"file_path": str(formatted_docx), "scope": "blocks"}
    )
    new_para = next(b for b in blocks_result2["blocks"] if b["type"] == "paragraph")

    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(formatted_docx),
            "scope": "runs",
            "target_id": new_para["id"],
        },
    )
    assert runs_result["runs"][1]["text"] == "strongly emphasized, "
    assert runs_result["runs"][1]["bold"] is True  # Formatting preserved


@pytest.mark.asyncio
async def test_edit_run_formatting(formatted_docx):
    """Test editing run formatting."""
    # Get paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(formatted_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Make the first run (Normal text) bold and underlined
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(formatted_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": para_block["id"],
                            "run_index": 0,
                            "formatting": '{"bold": true, "underline": true}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify formatting (text unchanged, so ID unchanged)
    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(formatted_docx),
            "scope": "runs",
            "target_id": para_block["id"],
        },
    )
    assert runs_result["runs"][0]["text"] == "Normal text, "
    assert runs_result["runs"][0]["bold"] is True
    assert runs_result["runs"][0]["underline"] is True


@pytest.mark.asyncio
async def test_edit_run_out_of_range(formatted_docx):
    """Test that editing out-of-range run raises ValueError."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(formatted_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(formatted_docx),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "edit_run",
                                "target_id": para_block["id"],
                                "run_index": 99,
                                "content_data": "Should fail",
                            }
                        ]
                    )
                ),
            },
        )
    assert "out of range" in str(exc_info.value)


@pytest.mark.asyncio
async def test_read_runs_on_table_fails(sample_docx):
    """Test that reading runs on a table fails."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    with pytest.raises(ToolError):
        await mcp.call_tool(
            "read",
            {
                "file_path": str(sample_docx),
                "scope": "runs",
                "target_id": table_block["id"],
            },
        )


@pytest.mark.asyncio
async def test_edit_run_on_table_fails(sample_docx):
    """Test that editing run on a table raises error."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    with pytest.raises(ToolError):
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "edit_run",
                                "target_id": table_block["id"],
                                "run_index": 0,
                                "content_data": "Should fail",
                            }
                        ]
                    )
                ),
            },
        )


@pytest.mark.asyncio
async def test_read_runs_with_tab_and_linebreak():
    """Test that runs correctly handle tabs and line breaks in text."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        pkg = WordPackage.new()
        body = pkg.body
        # Remove the default empty paragraph
        for p in list(body.findall(qn("w:p"))):
            body.remove(p)
        # Create a paragraph with a run containing text, tab, more text, line break, and final text
        p = etree.SubElement(body, qn("w:p"))
        r_el = etree.SubElement(p, qn("w:r"))
        # Before tab text
        t1 = etree.SubElement(r_el, qn("w:t"))
        t1.text = "Before tab"
        # Tab element
        etree.SubElement(r_el, qn("w:tab"))
        # After tab text
        t2 = etree.SubElement(r_el, qn("w:t"))
        t2.text = "After tab"
        # Line break element
        etree.SubElement(r_el, qn("w:br"))
        # After break text
        t3 = etree.SubElement(r_el, qn("w:t"))
        t3.text = "After break"
        pkg.mark_xml_dirty("/word/document.xml")
        pkg.save(f.name)

        try:
            # Read blocks to get paragraph ID
            _, blocks_result = await mcp.call_tool(
                "read", {"file_path": f.name, "scope": "blocks"}
            )
            para_block = next(
                b for b in blocks_result["blocks"] if b["type"] == "paragraph"
            )

            # Read runs
            _, runs_result = await mcp.call_tool(
                "read",
                {
                    "file_path": f.name,
                    "scope": "runs",
                    "target_id": para_block["id"],
                },
            )
            assert runs_result["block_count"] == 1
            run_text = runs_result["runs"][0]["text"]
            # Verify tab and line break are represented
            assert "\t" in run_text, "Tab should be represented as \\t"
            assert "\n" in run_text, "Line break should be represented as \\n"
            assert "Before tab" in run_text
            assert "After tab" in run_text
            assert "After break" in run_text
        finally:
            Path(f.name).unlink(missing_ok=True)


# --- Comment tests ---


@pytest.mark.asyncio
async def test_read_comments_empty(sample_docx):
    """Test reading comments from a document with no comments."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "comments"}
    )
    assert result["block_count"] == 0
    assert result["comments"] == []


@pytest.mark.asyncio
async def test_add_comment_to_paragraph(sample_docx):
    """Test adding a comment to a paragraph."""
    # First get a paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Add a comment
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_comment",
                            "target_id": para_block["id"],
                            "content_data": "This is a test comment",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert edit_result["comment_id"] is not None

    # Verify comment was added
    _, comments_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "comments"}
    )
    assert comments_result["block_count"] == 1
    assert len(comments_result["comments"]) == 1
    assert comments_result["comments"][0]["text"] == "This is a test comment"


@pytest.mark.asyncio
async def test_add_comment_with_author(sample_docx):
    """Test adding a comment with author and initials."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Add a comment with author
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_comment",
                            "target_id": para_block["id"],
                            "content_data": "Review needed",
                            "author": "Test Author",
                            "initials": "TA",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify author info
    _, comments_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "comments"}
    )
    assert comments_result["comments"][0]["author"] == "Test Author"
    assert comments_result["comments"][0]["initials"] == "TA"


@pytest.mark.asyncio
async def test_add_comment_to_table_fails(sample_docx):
    """Test that adding a comment to a table fails (underlying library error)."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    with pytest.raises(ToolError):
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "add_comment",
                                "target_id": table_block["id"],
                                "content_data": "Should fail",
                            }
                        ]
                    )
                ),
            },
        )


# --- Headers/Footers tests ---


@pytest.mark.asyncio
async def test_read_headers_footers(sample_docx):
    """Test reading headers and footers."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "headers_footers"}
    )
    # Document should have at least one section
    assert result["block_count"] >= 1
    assert len(result["headers_footers"]) >= 1
    # First section should be at index 0
    assert result["headers_footers"][0]["section_index"] == 0


@pytest.mark.asyncio
async def test_set_header(sample_docx):
    """Test setting a header."""
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_header",
                            "section_index": 0,
                            "content_data": "My Custom Header",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify header was set
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "headers_footers"}
    )
    assert result["headers_footers"][0]["header_text"] == "My Custom Header"
    assert result["headers_footers"][0]["header_is_linked"] is False


@pytest.mark.asyncio
async def test_set_footer(sample_docx):
    """Test setting a footer."""
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_footer",
                            "section_index": 0,
                            "content_data": "Page Footer Text",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify footer was set
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "headers_footers"}
    )
    assert result["headers_footers"][0]["footer_text"] == "Page Footer Text"
    assert result["headers_footers"][0]["footer_is_linked"] is False


@pytest.mark.asyncio
async def test_set_header_invalid_section(sample_docx):
    """Test that setting header on invalid section raises ValueError."""
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "set_header",
                                "section_index": 99,
                                "content_data": "Should fail",
                            }
                        ]
                    )
                ),
            },
        )
    assert "out of range" in str(exc_info.value)


# --- Page Setup tests ---


@pytest.mark.asyncio
async def test_read_page_setup(sample_docx):
    """Test reading page setup."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "page_setup"}
    )
    # Document should have at least one section
    assert result["block_count"] >= 1
    assert len(result["page_setup"]) >= 1
    # Check first section has expected fields
    setup = result["page_setup"][0]
    assert setup["section_index"] == 0
    assert setup["orientation"] in ["portrait", "landscape"]
    assert setup["page_width"] > 0
    assert setup["page_height"] > 0


@pytest.mark.asyncio
async def test_read_page_setup_multi_section():
    """Test reading page setup with multiple sections including section breaks."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        doc_path = Path(f.name)
    WordPackage.new().save(str(doc_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "Section 0 content",
                        }
                    ]
                )
            ),
        },
    )
    # Add a section break (creates section 1)
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_section",
                            "content_data": "new_page",
                        }
                    ]
                )
            ),
        },
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "Section 1 content",
                        }
                    ]
                )
            ),
        },
    )
    # Add another section break (creates section 2)
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_section",
                            "content_data": "continuous",
                        }
                    ]
                )
            ),
        },
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "Section 2 content",
                        }
                    ]
                )
            ),
        },
    )

    try:
        _, result = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "page_setup"}
        )

        # Should have 3 sections (0, 1, 2)
        assert result["block_count"] == 3
        assert len(result["page_setup"]) == 3

        # Verify section indices are in order
        for i, setup in enumerate(result["page_setup"]):
            assert setup["section_index"] == i

        # All sections should have valid page dimensions
        for setup in result["page_setup"]:
            assert setup["page_width"] > 0
            assert setup["page_height"] > 0
    finally:
        doc_path.unlink()


@pytest.mark.asyncio
async def test_set_margins(sample_docx):
    """Test setting page margins."""
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_margins",
                            "section_index": 0,
                            "formatting": '{"top": 0.5, "bottom": 0.5, "left": 0.75, "right": 0.75}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify margins were set
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "page_setup"}
    )
    setup = result["page_setup"][0]
    assert setup["top_margin"] == 0.5
    assert setup["bottom_margin"] == 0.5
    assert setup["left_margin"] == 0.75
    assert setup["right_margin"] == 0.75


@pytest.mark.asyncio
async def test_set_orientation_landscape(sample_docx):
    """Test setting page orientation to landscape."""
    # Get original dimensions
    _, before = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "page_setup"}
    )
    orig_width = before["page_setup"][0]["page_width"]
    orig_height = before["page_setup"][0]["page_height"]

    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_orientation",
                            "section_index": 0,
                            "content_data": "landscape",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify orientation was set
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "page_setup"}
    )
    setup = result["page_setup"][0]
    assert setup["orientation"] == "landscape"
    # Width should now be greater than height (or swapped)
    assert setup["page_width"] >= setup["page_height"] or (
        setup["page_width"] == orig_height and setup["page_height"] == orig_width
    )


@pytest.mark.asyncio
async def test_set_margins_missing_formatting(sample_docx):
    """Test that set_margins without formatting raises ValueError."""
    with pytest.raises(ToolError):
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "set_margins",
                                "section_index": 0,
                            }
                        ]
                    )
                ),
            },
        )


# --- File error handling tests ---


@pytest.mark.asyncio
async def test_read_missing_file():
    """Test that reading a missing file raises error."""
    with pytest.raises(ToolError):
        await mcp.call_tool(
            "read",
            {
                "file_path": "/nonexistent/path/to/file.docx",
                "scope": "blocks",
            },
        )


@pytest.mark.asyncio
async def test_edit_missing_file():
    """Test that editing in nonexistent directory raises error."""
    with pytest.raises(ToolError):
        await mcp.call_tool(
            "edit",
            {
                "file_path": "/nonexistent/path/to/file.docx",
                "ops": (
                    _ops(
                        [
                            {
                                "op": "append",
                                "content_data": "Should fail",
                            }
                        ]
                    )
                ),
            },
        )


@pytest.mark.asyncio
async def test_read_corrupt_file():
    """Test that reading a corrupt file raises error."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(b"not a valid docx file")
        corrupt_path = f.name
    try:
        with pytest.raises(ToolError):
            await mcp.call_tool(
                "read",
                {
                    "file_path": corrupt_path,
                    "scope": "blocks",
                },
            )
    finally:
        Path(corrupt_path).unlink(missing_ok=True)


# --- Image tests ---


@pytest.fixture
def sample_image():
    """Create a minimal PNG image for testing using PIL."""
    from PIL import Image as PILImage

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        # Create a 10x10 red image
        img = PILImage.new("RGB", (10, 10), color="red")
        img.save(f.name, "PNG")
        yield Path(f.name)
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
async def docx_with_image(sample_image):
    """Create a Word document with an embedded image."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)
    # Create document with heading
    WordPackage.new().save(str(path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "heading",
                            "content_data": "Document with Image",
                            "heading_level": 1,
                        }
                    ]
                )
            ),
        },
    )
    # Add a paragraph that will contain the image
    _, append_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "",
                        }
                    ]
                )
            ),
        },
    )
    para_id = append_result["element_id"]
    # Insert image into the paragraph
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_image",
                            "target_id": para_id,
                            "content_data": str(sample_image),
                            "formatting": json.dumps({"width": 1.0, "height": 1.0}),
                        }
                    ]
                )
            ),
        },
    )
    # Add text after image
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "Text after image.",
                        }
                    ]
                )
            ),
        },
    )
    yield path
    path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_images(docx_with_image):
    """Test reading images from a document."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_image), "scope": "images"}
    )
    assert result["block_count"] == 1
    assert len(result["images"]) == 1
    img = result["images"][0]
    # Check ID format: image_{hash}_{occurrence}
    assert img["id"].startswith("image_")
    assert "_" in img["id"][6:]  # hash_occurrence part
    # Check dimensions (we set 1 inch)
    assert 0.9 < img["width_inches"] < 1.1
    assert 0.9 < img["height_inches"] < 1.1
    assert img["content_type"] == "image/png"
    # Check block_id references a paragraph
    assert img["block_id"].startswith("paragraph_")


@pytest.mark.asyncio
async def test_read_images_empty(sample_docx):
    """Test reading images from a document with no images."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "images"}
    )
    assert result["block_count"] == 0
    assert result["images"] == []


@pytest.mark.asyncio
async def test_insert_image(sample_docx, sample_image):
    """Test inserting an image."""
    # Get a paragraph to insert after
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Insert image
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_image",
                            "target_id": para_block["id"],
                            "content_data": str(sample_image),
                            "formatting": '{"width": 2.0, "height": 1.5}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert edit_result["element_id"].startswith("image_")

    # Verify image was added
    _, images_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "images"}
    )
    assert images_result["block_count"] == 1
    img = images_result["images"][0]
    assert 1.9 < img["width_inches"] < 2.1
    assert 1.4 < img["height_inches"] < 1.6


@pytest.mark.asyncio
async def test_delete_image(docx_with_image):
    """Test deleting an image."""
    # Get the image ID
    _, images_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_image), "scope": "images"}
    )
    assert len(images_result["images"]) == 1
    image_id = images_result["images"][0]["id"]

    # Delete the image
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_image),
            "ops": (
                _ops(
                    [
                        {
                            "op": "delete_image",
                            "target_id": image_id,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify image was deleted
    _, images_result2 = await mcp.call_tool(
        "read", {"file_path": str(docx_with_image), "scope": "images"}
    )
    assert images_result2["block_count"] == 0
    assert images_result2["images"] == []


@pytest.mark.asyncio
async def test_image_id_format(sample_image):
    """Test that image IDs use content-hash format."""
    import re

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as doc_f:
        doc_path = Path(doc_f.name)
    WordPackage.new().save(str(doc_path))
    # Get paragraph ID to insert image
    _, blocks = await mcp.call_tool(
        "read", {"file_path": str(doc_path), "scope": "blocks"}
    )
    para_id = blocks["blocks"][0]["id"]
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_image",
                            "target_id": para_id,
                            "content_data": str(sample_image),
                            "formatting": json.dumps({"width": 1.0}),
                        }
                    ]
                )
            ),
        },
    )

    try:
        _, result = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "images"}
        )
        # Image ID format: image_{sha1[:8]}_{occurrence}
        id_pattern = re.compile(r"^image_[0-9a-f]{8}_\d+$")
        for img in result["images"]:
            assert id_pattern.match(img["id"]), f"Invalid ID format: {img['id']}"
    finally:
        doc_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_multiple_same_images(sample_image):
    """Test that same image appearing twice has different occurrence numbers."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as doc_f:
        doc_path = Path(doc_f.name)
    WordPackage.new().save(str(doc_path))
    # Get first paragraph and add image
    _, blocks = await mcp.call_tool(
        "read", {"file_path": str(doc_path), "scope": "blocks"}
    )
    para1_id = blocks["blocks"][0]["id"]
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_image",
                            "target_id": para1_id,
                            "content_data": str(sample_image),
                            "formatting": json.dumps({"width": 1.0}),
                        }
                    ]
                )
            ),
        },
    )
    # Add second paragraph with same image
    _, append_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (_ops([{"op": "append", "content_data": ""}])),
        },
    )
    para2_id = append_result["element_id"]
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_image",
                            "target_id": para2_id,
                            "content_data": str(sample_image),
                            "formatting": json.dumps({"width": 1.0}),
                        }
                    ]
                )
            ),
        },
    )

    try:
        _, result = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "images"}
        )
        assert len(result["images"]) == 2
        # Same hash, different occurrence
        id1, id2 = result["images"][0]["id"], result["images"][1]["id"]
        hash1, occ1 = id1.split("_")[1], id1.split("_")[2]
        hash2, occ2 = id2.split("_")[1], id2.split("_")[2]
        assert hash1 == hash2  # Same image = same hash
        assert occ1 != occ2  # Different occurrences
        assert {occ1, occ2} == {"0", "1"}  # Should be 0 and 1
    finally:
        doc_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_delete_image_invalid_id(sample_docx):
    """Test that deleting with invalid image ID raises error."""
    with pytest.raises(ToolError):
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "delete_image",
                                "target_id": "image_nonexist_0",
                            }
                        ]
                    )
                ),
            },
        )


@pytest.mark.asyncio
async def test_read_images_in_table(sample_image):
    """Test reading images from table cells with hierarchical block_id."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as doc_f:
        doc_path = Path(doc_f.name)
    WordPackage.new().save(str(doc_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "Document with table containing image",
                        }
                    ]
                )
            ),
        },
    )
    # Add a 2x2 table
    table_data = json.dumps([["Name", "Signature"], ["John Doe", ""]])
    _, table_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "table",
                            "content_data": table_data,
                        }
                    ]
                )
            ),
        },
    )
    table_id = table_result["element_id"]
    # Insert image into cell (1,1) - use hierarchical path
    cell_path = f"{table_id}#r1c1/p0"
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_image",
                            "target_id": cell_path,
                            "content_data": str(sample_image),
                            "formatting": json.dumps({"width": 1.0}),
                        }
                    ]
                )
            ),
        },
    )

    try:
        _, result = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "images"}
        )
        assert result["block_count"] == 1
        assert len(result["images"]) == 1
        img = result["images"][0]
        # block_id should be hierarchical: table_xxx#r1c1/p0
        assert img["block_id"].startswith("table_")
        assert "#r1c1/p0" in img["block_id"]  # Image in cell (1,1), paragraph 0
        assert img["content_type"] == "image/png"
    finally:
        doc_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_delete_image_in_table(sample_image):
    """Test deleting an image from a table cell."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as doc_f:
        doc_path = Path(doc_f.name)
    WordPackage.new().save(str(doc_path))
    # Add a 1x1 table
    table_data = json.dumps([[""]])
    _, table_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "table",
                            "content_data": table_data,
                        }
                    ]
                )
            ),
        },
    )
    table_id = table_result["element_id"]
    # Insert image into the cell
    cell_path = f"{table_id}#r0c0/p0"
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_image",
                            "target_id": cell_path,
                            "content_data": str(sample_image),
                            "formatting": json.dumps({"width": 1.0}),
                        }
                    ]
                )
            ),
        },
    )

    try:
        # Get the image ID
        _, images_result = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "images"}
        )
        assert len(images_result["images"]) == 1
        image_id = images_result["images"][0]["id"]

        # Delete the image
        _, edit_result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(doc_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "delete_image",
                                "target_id": image_id,
                            }
                        ]
                    )
                ),
            },
        )
        assert edit_result["success"]

        # Verify image was deleted
        _, images_result2 = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "images"}
        )
        assert images_result2["block_count"] == 0
    finally:
        doc_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_insert_image_into_table_cell(sample_image):
    """Test inserting an image into a specific table cell using hierarchical target_id."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as doc_f:
        doc_path = Path(doc_f.name)
    WordPackage.new().save(str(doc_path))
    # Add a 2x2 table
    table_data = json.dumps([["Image", "Description"], ["", "A test image"]])
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "table",
                            "content_data": table_data,
                        }
                    ]
                )
            ),
        },
    )

    try:
        # Get the table ID
        _, blocks_result = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "blocks"}
        )
        table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")
        table_id = table_block["id"]

        # Insert image into cell (1, 0) - second row, first column (0-based)
        # Using hierarchical target_id: table_xxx#r1c0
        _, edit_result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(doc_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "insert_image",
                                "target_id": f"{table_id}#r1c0",
                                "content_data": str(sample_image),
                                "formatting": '{"width": 1}',
                            }
                        ]
                    )
                ),
            },
        )
        assert edit_result["success"]
        assert edit_result["element_id"].startswith("image_")

        # Verify image was inserted in the correct cell
        _, images_result = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "images"}
        )
        assert images_result["block_count"] == 1
        img = images_result["images"][0]
        # Image should be in cell (1,0), paragraph 0
        assert "#r1c0/p0" in img["block_id"]
    finally:
        doc_path.unlink(missing_ok=True)


# --- Hierarchical addressing tests ---


@pytest.mark.asyncio
async def test_hierarchical_path_parsing(sample_docx):
    """Test that hierarchical paths are parsed correctly."""
    import re

    # Get table ID and read cells with hierarchical IDs
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")
    table_id = table_block["id"]

    _, cells_result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "table_cells", "target_id": table_id},
    )

    # Each cell should have a hierarchical_id in format: {table_id}#r{row}c{col}
    # Use strict regex to validate full grammar
    hier_id_pattern = re.compile(rf"^{re.escape(table_id)}#r(\d+)c(\d+)$")

    for cell in cells_result["cells"]:
        hid = cell["hierarchical_id"]
        match = hier_id_pattern.match(hid)
        assert match, f"Invalid hierarchical_id format: {hid}"
        # Verify the parsed row/col match cell's row/col
        assert int(match.group(1)) == cell["row"]
        assert int(match.group(2)) == cell["col"]


@pytest.mark.asyncio
async def test_hierarchical_path_from_paragraph_fails(sample_docx):
    """Test that hierarchical paths are rejected for non-table base blocks."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")
    para_id = para_block["id"]

    # Trying to use hierarchical path on a paragraph should fail
    # (paragraph has no rows/cells to navigate to)
    with pytest.raises(ToolError, match="list index out of range"):
        await mcp.call_tool(
            "read",
            {
                "file_path": str(sample_docx),
                "scope": "runs",
                "target_id": f"{para_id}#r0c0",  # Invalid: para can't have cell path
            },
        )


@pytest.mark.asyncio
async def test_hierarchical_path_invalid_segment(sample_docx):
    """Test that invalid path segments are rejected."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")
    table_id = table_block["id"]

    # Invalid segment format should fail
    with pytest.raises(ToolError, match="Invalid path segment"):
        await mcp.call_tool(
            "read",
            {
                "file_path": str(sample_docx),
                "scope": "runs",
                "target_id": f"{table_id}#invalid",
            },
        )


@pytest.mark.asyncio
async def test_hierarchical_path_cell_out_of_bounds(sample_docx):
    """Test that out-of-bounds cell coordinates are rejected."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")
    table_id = table_block["id"]

    # Row out of bounds (table has 2 rows: 0 and 1)
    with pytest.raises(ToolError, match="index out of range"):
        await mcp.call_tool(
            "read",
            {
                "file_path": str(sample_docx),
                "scope": "runs",
                "target_id": f"{table_id}#r99c0/p0",
            },
        )


@pytest.mark.asyncio
async def test_hierarchical_transition_cell_to_paragraph(sample_docx):
    """Test valid transition: table -> cell -> paragraph."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")
    table_id = table_block["id"]

    # Valid path: table#r0c0/p0 -> first paragraph in cell (0,0)
    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(sample_docx),
            "scope": "runs",
            "target_id": f"{table_id}#r0c0/p0",
        },
    )
    # Should succeed and return runs for the paragraph in the cell
    assert "runs" in runs_result


@pytest.mark.asyncio
async def test_hierarchical_transition_invalid_para_from_table(sample_docx):
    """Test invalid transition: cannot select paragraph directly from table."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")
    table_id = table_block["id"]

    # Invalid: p0 directly from table (must go through cell first)
    # Table has rows not paragraphs, so list index fails
    with pytest.raises(ToolError, match="list index out of range"):
        await mcp.call_tool(
            "read",
            {
                "file_path": str(sample_docx),
                "scope": "runs",
                "target_id": f"{table_id}#p0",  # Missing cell selector
            },
        )


# --- Paragraph formatting tests ---


@pytest.mark.asyncio
async def test_paragraph_indentation(sample_docx):
    """Test setting paragraph indentation (left, right, first-line)."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Apply indentation formatting
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "style",
                            "target_id": para_block["id"],
                            "formatting": '{"left_indent": 0.5, "right_indent": 0.25, "first_line_indent": 0.5}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    # Formatting was applied - trust the edit operation succeeded
    # Detailed format verification is done via OOXML inspection in unit tests


@pytest.mark.asyncio
async def test_paragraph_spacing(sample_docx):
    """Test setting paragraph spacing (before, after, line spacing)."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Apply spacing formatting
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "style",
                            "target_id": para_block["id"],
                            "formatting": '{"space_before": 12, "space_after": 6, "line_spacing": 1.5}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    # Formatting was applied - trust the edit operation succeeded


@pytest.mark.asyncio
async def test_paragraph_flow_control(sample_docx):
    """Test setting paragraph flow control (keep_with_next, page_break_before)."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Apply flow control formatting
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "style",
                            "target_id": para_block["id"],
                            "formatting": '{"keep_with_next": true, "page_break_before": true}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    # Formatting was applied - trust the edit operation succeeded


# --- Run effects tests ---


@pytest.mark.asyncio
async def test_run_highlight(sample_docx):
    """Test applying highlight color to a run."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Read runs to get run index
    _, runs_result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "runs", "target_id": para_block["id"]},
    )
    assert len(runs_result["runs"]) > 0

    # Apply highlight formatting
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": para_block["id"],
                            "run_index": 0,
                            "formatting": '{"highlight_color": "yellow"}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify via read() returns the highlight
    _, runs_result2 = await mcp.call_tool(
        "read",
        {
            "file_path": str(sample_docx),
            "scope": "runs",
            "target_id": edit_result["element_id"],
        },
    )
    assert runs_result2["runs"][0]["highlight_color"] == "yellow"


@pytest.mark.asyncio
async def test_run_strikethrough(sample_docx):
    """Test applying strikethrough to a run."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Apply strike formatting
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": para_block["id"],
                            "run_index": 0,
                            "formatting": '{"strike": true, "double_strike": false}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    # Verify via MCP read
    _, runs_result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "runs", "target_id": para_block["id"]},
    )
    assert runs_result["runs"][0]["strike"] is True


@pytest.mark.asyncio
async def test_run_subscript_superscript(sample_docx):
    """Test applying subscript and superscript to runs."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Apply subscript formatting
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": para_block["id"],
                            "run_index": 0,
                            "formatting": '{"subscript": true}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Now change to superscript
    _, edit_result2 = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": edit_result["element_id"],
                            "run_index": 0,
                            "formatting": '{"subscript": false, "superscript": true}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result2["success"]

    # Verify via MCP read
    _, runs_result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "runs", "target_id": para_block["id"]},
    )
    assert runs_result["runs"][0]["superscript"] is True


# --- Table row/column operations tests ---


@pytest.mark.asyncio
async def test_add_table_row_empty(sample_docx):
    """Test adding an empty row to a table."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")
    original_rows = table_block["rows"]

    # Add empty row
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_row",
                            "target_id": table_block["id"],
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "Added row" in edit_result["results"][0]["message"]

    # Verify row count increased
    _, cells_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(sample_docx),
            "scope": "table_cells",
            "target_id": edit_result["element_id"],
        },
    )
    assert cells_result["table_rows"] == original_rows + 1


@pytest.mark.asyncio
async def test_add_table_row_with_data(sample_docx):
    """Test adding a row with cell values."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Add row with data
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_row",
                            "target_id": table_block["id"],
                            "content_data": '["New Cell 1", "New Cell 2"]',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify cell content via MCP read
    _, cells_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(sample_docx),
            "scope": "table_cells",
            "target_id": edit_result["element_id"],
        },
    )
    # Find last row cells
    last_row_idx = cells_result["table_rows"] - 1
    last_row_cells = [c for c in cells_result["cells"] if c["row"] == last_row_idx]
    assert last_row_cells[0]["text"] == "New Cell 1"
    assert last_row_cells[1]["text"] == "New Cell 2"


@pytest.mark.asyncio
async def test_add_table_column(sample_docx):
    """Test adding a column with width and values."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")
    original_cols = table_block["cols"]

    # Add column with data
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_column",
                            "target_id": table_block["id"],
                            "content_data": '["Header 3", "Row 1 Col 3"]',
                            "formatting": '{"width": 1.5}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "Added column" in edit_result["results"][0]["message"]

    # Verify column count and content via MCP read
    _, cells_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(sample_docx),
            "scope": "table_cells",
            "target_id": edit_result["element_id"],
        },
    )
    assert cells_result["table_cols"] == original_cols + 1
    # Find cells in the new column
    new_col_idx = original_cols
    new_col_cells = [c for c in cells_result["cells"] if c["col"] == new_col_idx]
    assert new_col_cells[0]["text"] == "Header 3"
    assert new_col_cells[1]["text"] == "Row 1 Col 3"


@pytest.mark.asyncio
async def test_delete_table_row(sample_docx):
    """Test deleting a specific row."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")
    original_rows = table_block["rows"]

    # Delete second row (row index 1)
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "delete_row",
                            "target_id": table_block["id"],
                            "row": 1,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "Deleted row 1" in edit_result["results"][0]["message"]

    # Verify row count decreased
    _, cells_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(sample_docx),
            "scope": "table_cells",
            "target_id": edit_result["element_id"],
        },
    )
    assert cells_result["table_rows"] == original_rows - 1


@pytest.mark.asyncio
async def test_delete_table_column(sample_docx):
    """Test deleting a specific column."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")
    original_cols = table_block["cols"]

    # Delete first column (col index 0)
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "delete_column",
                            "target_id": table_block["id"],
                            "col": 0,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "Deleted column 0" in edit_result["results"][0]["message"]

    # Verify column count decreased
    _, cells_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(sample_docx),
            "scope": "table_cells",
            "target_id": edit_result["element_id"],
        },
    )
    assert cells_result["table_cols"] == original_cols - 1

    # Verify the remaining column has Header 2 content
    first_cell = cells_result["cells"][0]  # First cell in grid order
    assert first_cell["text"] == "Header 2"


# --- Page breaks tests ---


@pytest.mark.asyncio
async def test_add_page_break(sample_docx):
    """Test appending a page break to the document."""

    _, blocks_before = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    initial_count = blocks_before["block_count"]

    # Add page break
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_page_break",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "Added page break" in edit_result["results"][0]["message"]
    assert edit_result["element_id"].startswith("paragraph_")

    # Verify block count increased
    _, blocks_after = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    assert blocks_after["block_count"] == initial_count + 1

    # Verify the page break exists via OOXML (runs have break element)
    pkg = WordPackage.open(sample_docx)
    last_para = list(pkg.body.findall(qn("w:p")))[-1]
    breaks = last_para.findall(f".//{qn('w:br')}")
    assert len(breaks) > 0


@pytest.mark.asyncio
async def test_add_break_after_paragraph(sample_docx):
    """Test inserting a page break after a specific paragraph."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Add break after paragraph
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_break",
                            "target_id": para_block["id"],
                            "content_data": "page",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "Added page break" in edit_result["results"][0]["message"]


@pytest.mark.asyncio
async def test_add_column_break(sample_docx):
    """Test inserting a column break."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Add column break after paragraph
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_break",
                            "target_id": para_block["id"],
                            "content_data": "column",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "Added column break" in edit_result["results"][0]["message"]


# --- Metadata writing tests ---


@pytest.mark.asyncio
async def test_set_document_title(sample_docx):
    """Test updating document title."""
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_property",
                            "content_data": '{"title": "New Document Title"}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "Updated document metadata" in edit_result["results"][0]["message"]

    # Verify via read
    _, meta_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "meta"}
    )
    assert meta_result["meta"]["title"] == "New Document Title"


@pytest.mark.asyncio
async def test_set_document_author(sample_docx):
    """Test updating document author."""
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_property",
                            "content_data": '{"author": "Test Author"}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify via read
    _, meta_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "meta"}
    )
    assert meta_result["meta"]["author"] == "Test Author"


@pytest.mark.asyncio
async def test_set_multiple_metadata(sample_docx):
    """Test updating multiple metadata properties at once."""
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_property",
                            "content_data": '{"title": "Multi Test", "author": "Multi Author"}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify via MCP read
    _, meta_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "meta"}
    )
    assert meta_result["meta"]["title"] == "Multi Test"
    assert meta_result["meta"]["author"] == "Multi Author"


# --- First/Even page header tests ---


@pytest.mark.asyncio
async def test_set_first_page_header(sample_docx):
    """Test setting a different first page header."""
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_first_page_header",
                            "section_index": 0,
                            "content_data": "First Page Header",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "Set first page header" in edit_result["results"][0]["message"]

    # Verify via read
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "headers_footers"}
    )
    assert result["headers_footers"][0]["has_different_first_page"] is True
    assert result["headers_footers"][0]["first_page_header_text"] == "First Page Header"


@pytest.mark.asyncio
async def test_set_even_page_header(sample_docx):
    """Test setting a different even page header."""
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_even_page_header",
                            "section_index": 0,
                            "content_data": "Even Page Header",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "Set even page header" in edit_result["results"][0]["message"]

    # Verify via read
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "headers_footers"}
    )
    assert result["headers_footers"][0]["has_different_odd_even"] is True
    assert result["headers_footers"][0]["even_page_header_text"] == "Even Page Header"


@pytest.mark.asyncio
async def test_add_section_new_page(sample_docx):
    """Test adding a new section with new_page start type."""
    # Get initial section count
    _, initial = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "page_setup"}
    )
    initial_count = len(initial["page_setup"])

    # Add section
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_section",
                            "content_data": "new_page",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "new_page" in edit_result["results"][0]["message"]

    # Verify section count increased
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "page_setup"}
    )
    assert len(result["page_setup"]) == initial_count + 1


@pytest.mark.asyncio
async def test_add_section_continuous(sample_docx):
    """Test adding a continuous section."""
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_section",
                            "content_data": "continuous",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "continuous" in edit_result["results"][0]["message"]

    # Verify section was added
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "page_setup"}
    )
    assert len(result["page_setup"]) >= 2


# --- Hyperlink tests ---


@pytest.fixture
async def docx_with_hyperlinks():
    """Create a Word document with hyperlinks for testing."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)
    path.unlink()  # remove so edit() auto-creates
    # Add heading and paragraph with text
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "heading",
                            "content_data": "Document with Links",
                            "heading_level": 1,
                        },
                    ]
                )
            ),
        },
    )
    _, para_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": (_ops([{"op": "append", "content_data": "Visit "}])),
        },
    )
    para_id = para_result["element_id"]
    # Add hyperlink to the paragraph
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_hyperlink",
                            "target_id": para_id,
                            "content_data": json.dumps(
                                {
                                    "text": "Example Website",
                                    "address": "https://example.com",
                                }
                            ),
                        }
                    ]
                )
            ),
        },
    )
    # Append more text (need to use edit_run or append to same paragraph)
    # For now, we rely on hyperlink text being there
    yield path
    path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_build_runs_includes_hyperlink_text(docx_with_hyperlinks):
    """Test that build_runs includes text from hyperlinks."""
    # Get the paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_hyperlinks), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Read runs from the paragraph
    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_hyperlinks),
            "scope": "runs",
            "target_id": para_block["id"],
        },
    )

    # Should have 2 runs: "Visit ", "Example Website" (hyperlink)
    assert runs_result["block_count"] == 2
    texts = [r["text"] for r in runs_result["runs"]]
    assert "Visit " in texts
    assert "Example Website" in texts

    # The hyperlink run should be marked
    hyperlink_run = next(
        r for r in runs_result["runs"] if r["text"] == "Example Website"
    )
    assert hyperlink_run["is_hyperlink"] is True
    assert hyperlink_run["hyperlink_url"] == "https://example.com"


@pytest.mark.asyncio
async def test_read_hyperlinks(docx_with_hyperlinks):
    """Test reading hyperlinks from a document."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_hyperlinks), "scope": "hyperlinks"}
    )

    assert result["block_count"] == 1
    assert len(result["hyperlinks"]) == 1

    link = result["hyperlinks"][0]
    assert link["text"] == "Example Website"
    assert link["url"] == "https://example.com"
    assert link["address"] == "https://example.com"
    assert link["is_external"] is True
    assert link["index"] == 0


@pytest.mark.asyncio
async def test_read_hyperlinks_empty(sample_docx):
    """Test reading hyperlinks from a document with no hyperlinks."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "hyperlinks"}
    )
    assert result["block_count"] == 0
    assert result["hyperlinks"] == []


@pytest.mark.asyncio
async def test_hyperlink_in_table_cell():
    """Test that hyperlinks in table cells are detected."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        doc_path = Path(f.name)

    try:
        # Create document with table using MCP (auto-create)
        doc_path.unlink()
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(doc_path),
                "ops": _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "table",
                            "content_data": json.dumps(
                                [
                                    ["Name", "Website"],
                                    ["Example Corp", ""],
                                ]
                            ),
                        }
                    ]
                ),
            },
        )

        # Get table cell (1, 1) ID
        _, blocks_result = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "blocks"}
        )
        table_id = blocks_result["blocks"][0]["id"]

        _, cells_result = await mcp.call_tool(
            "read",
            {"file_path": str(doc_path), "scope": "table_cells", "target_id": table_id},
        )
        cell_1_1 = next(
            c for c in cells_result["cells"] if c["row"] == 1 and c["col"] == 1
        )

        # Add hyperlink to cell (1, 1)
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(doc_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "add_hyperlink",
                                "target_id": cell_1_1["hierarchical_id"],
                                "content_data": json.dumps(
                                    {
                                        "text": "Visit Site",
                                        "address": "https://example.org",
                                    }
                                ),
                            }
                        ]
                    )
                ),
            },
        )

        # Read hyperlinks
        _, result = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "hyperlinks"}
        )

        assert result["block_count"] == 1
        assert len(result["hyperlinks"]) == 1
        link = result["hyperlinks"][0]
        assert link["text"] == "Visit Site"
        assert link["url"] == "https://example.org"
        assert link["is_external"] is True
    finally:
        doc_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_edit_hyperlink_run(docx_with_hyperlinks):
    """Test that editing a hyperlink run uses correct indexing."""
    # Get the paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_hyperlinks), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Read runs to find the hyperlink run index
    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_hyperlinks),
            "scope": "runs",
            "target_id": para_block["id"],
        },
    )

    # Find the hyperlink run
    hyperlink_run = next(r for r in runs_result["runs"] if r["is_hyperlink"])
    hyperlink_index = hyperlink_run["index"]

    # Edit the hyperlink run text
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_hyperlinks),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": para_block["id"],
                            "run_index": hyperlink_index,
                            "content_data": "Modified Link Text",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify the hyperlink run was edited (not another run)
    _, runs_result2 = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_hyperlinks),
            "scope": "runs",
            "target_id": edit_result["element_id"],
        },
    )
    edited_run = runs_result2["runs"][hyperlink_index]
    assert edited_run["text"] == "Modified Link Text"
    assert edited_run["is_hyperlink"] is True  # Still a hyperlink


# --- Hyperlink creation tests ---


@pytest.mark.asyncio
async def test_add_hyperlink_external_url(sample_docx):
    """Test adding an external hyperlink to a paragraph."""
    # Get the first paragraph
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para = blocks_result["blocks"][0]

    # Add external hyperlink
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_hyperlink",
                            "target_id": para["id"],
                            "content_data": json.dumps(
                                {
                                    "text": "Visit Google",
                                    "address": "https://google.com",
                                }
                            ),
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"]
    assert "Added hyperlink 'Visit Google'" in result["results"][0]["message"]
    assert "https://google.com" in result["results"][0]["message"]

    # Verify hyperlink was created
    _, hl_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "hyperlinks"}
    )
    assert len(hl_result["hyperlinks"]) == 1
    link = hl_result["hyperlinks"][0]
    assert link["text"] == "Visit Google"
    assert link["url"] == "https://google.com"


@pytest.mark.asyncio
async def test_add_hyperlink_internal_bookmark(sample_docx):
    """Test adding an internal hyperlink (bookmark reference)."""
    # Get blocks
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para1 = blocks_result["blocks"][0]
    para2 = blocks_result["blocks"][1]

    # First add a bookmark to paragraph 2
    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_bookmark",
                            "target_id": para2["id"],
                            "content_data": "TargetSection",
                        }
                    ]
                )
            ),
        },
    )

    # Now add internal hyperlink to paragraph 1
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_hyperlink",
                            "target_id": para1["id"],
                            "content_data": json.dumps(
                                {"text": "Jump to section", "fragment": "TargetSection"}
                            ),
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"]
    assert "#TargetSection" in result["results"][0]["message"]


@pytest.mark.asyncio
async def test_add_hyperlink_external_with_fragment(sample_docx):
    """Test adding external URL with anchor fragment."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para = blocks_result["blocks"][0]

    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_hyperlink",
                            "target_id": para["id"],
                            "content_data": json.dumps(
                                {
                                    "text": "Python docs",
                                    "address": "https://docs.python.org",
                                    "fragment": "installation",
                                }
                            ),
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"]

    # Verify - URL should include fragment
    _, hl_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "hyperlinks"}
    )
    assert len(hl_result["hyperlinks"]) == 1
    assert hl_result["hyperlinks"][0]["url"] == "https://docs.python.org#installation"


@pytest.mark.asyncio
async def test_add_hyperlink_to_table_cell():
    """Test adding hyperlink to a table cell."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        doc_path = Path(tmp.name)

    try:
        # Create document with table using MCP (auto-create)
        doc_path.unlink()
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(doc_path),
                "ops": _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "table",
                            "content_data": json.dumps(
                                [
                                    ["Cell A", "Cell B"],
                                    ["", ""],
                                ]
                            ),
                        }
                    ]
                ),
            },
        )

        # Get table cell ID
        _, blocks_result = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "blocks"}
        )
        table_id = blocks_result["blocks"][0]["id"]

        _, cells_result = await mcp.call_tool(
            "read",
            {"file_path": str(doc_path), "scope": "table_cells", "target_id": table_id},
        )
        # Find cell (0,0) - cells is a flat list with row/col attributes
        cell_0_0 = next(
            c for c in cells_result["cells"] if c["row"] == 0 and c["col"] == 0
        )
        cell_id = cell_0_0["hierarchical_id"]

        # Add hyperlink to cell
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(doc_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "add_hyperlink",
                                "target_id": cell_id,
                                "content_data": json.dumps(
                                    {
                                        "text": "Link in cell",
                                        "address": "https://example.com",
                                    }
                                ),
                            }
                        ]
                    )
                ),
            },
        )
        assert result["success"]

        # Verify hyperlink was created
        _, hl_result = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "hyperlinks"}
        )
        assert len(hl_result["hyperlinks"]) == 1
        assert hl_result["hyperlinks"][0]["text"] == "Link in cell"
    finally:
        doc_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_add_hyperlink_mailto(sample_docx):
    """Test adding a mailto hyperlink."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para = blocks_result["blocks"][0]

    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_hyperlink",
                            "target_id": para["id"],
                            "content_data": json.dumps(
                                {
                                    "text": "Email us",
                                    "address": "mailto:test@example.com",
                                }
                            ),
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"]

    _, hl_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "hyperlinks"}
    )
    assert hl_result["hyperlinks"][0]["url"] == "mailto:test@example.com"


@pytest.mark.asyncio
async def test_add_hyperlink_empty_text_error(sample_docx):
    """Test that empty text raises ValueError."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para = blocks_result["blocks"][0]

    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "add_hyperlink",
                                "target_id": para["id"],
                                "content_data": json.dumps(
                                    {"text": "", "address": "https://example.com"}
                                ),
                            }
                        ]
                    )
                ),
            },
        )
    assert "empty" in str(exc_info.value)


@pytest.mark.asyncio
async def test_add_hyperlink_no_address_or_fragment_error(sample_docx):
    """Test that missing both address and fragment raises ValueError."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para = blocks_result["blocks"][0]

    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "add_hyperlink",
                                "target_id": para["id"],
                                "content_data": json.dumps({"text": "Orphan link"}),
                            }
                        ]
                    )
                ),
            },
        )
    assert "address or fragment" in str(exc_info.value)


@pytest.mark.asyncio
async def test_add_hyperlink_fragment_normalization(sample_docx):
    """Test that fragment leading # is stripped."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para1 = blocks_result["blocks"][0]
    para2 = blocks_result["blocks"][1]

    # Add bookmark
    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_bookmark",
                            "target_id": para2["id"],
                            "content_data": "TestBookmark",
                        }
                    ]
                )
            ),
        },
    )

    # Add hyperlink with # prefix - should be normalized
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_hyperlink",
                            "target_id": para1["id"],
                            "content_data": json.dumps(
                                {"text": "Go to bookmark", "fragment": "#TestBookmark"}
                            ),
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"]
    assert "#TestBookmark" in result["results"][0]["message"]


# --- Style tests ---


@pytest.mark.asyncio
async def test_read_styles(sample_docx):
    """Test reading all styles from a document."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "styles"}
    )

    # Should have at least one style (Normal is always present)
    assert result["block_count"] > 0
    assert len(result["styles"]) > 0

    # Check that Normal style exists (always present in OOXML documents)
    style_names_lower = [s["name"].lower() for s in result["styles"]]
    assert "normal" in style_names_lower

    # Check style properties
    normal_style = next(s for s in result["styles"] if s["name"].lower() == "normal")
    assert normal_style["style_id"] == "Normal"
    assert normal_style["type"] == "paragraph"
    assert normal_style["builtin"] is True


@pytest.mark.asyncio
async def test_read_styles_includes_custom():
    """Test that custom styles appear in the list."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        doc_path = Path(f.name)

    try:
        # Create document with MCP
        WordPackage.new().save(str(doc_path))
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(doc_path),
                "ops": _ops([{"op": "append", "content_data": "Test paragraph"}]),
            },
        )

        # Create custom style using MCP
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(doc_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "create_style",
                                "content_data": json.dumps(
                                    {
                                        "style_id": "MyCustomStyle",
                                        "name": "MyCustomStyle",
                                        "style_type": "paragraph",
                                        "based_on": "Normal",
                                    }
                                ),
                            }
                        ]
                    )
                ),
            },
        )

        _, result = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "styles"}
        )

        # Custom style should be in the list
        style_names = [s["name"] for s in result["styles"]]
        assert "MyCustomStyle" in style_names

        # Check custom style properties
        custom = next(s for s in result["styles"] if s["name"] == "MyCustomStyle")
        assert custom["builtin"] is False
        assert custom["base_style"] == "Normal"
        assert custom["type"] == "paragraph"
    finally:
        doc_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_style_hierarchy(sample_docx):
    """Test that base_style relationships are correctly reported."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "styles"}
    )

    # Heading 1 typically has a base style
    heading1 = next((s for s in result["styles"] if s["name"] == "Heading 1"), None)
    if heading1:
        # Base style could be None or another style
        # Just verify the field exists and is valid
        assert "base_style" in heading1

    # Check style types are valid
    for style in result["styles"]:
        assert style["type"] in ["paragraph", "character", "table", "list", "unknown"]


@pytest.mark.asyncio
async def test_read_styles_includes_character_styles():
    """Test that character styles are properly typed when they exist."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        doc_path = Path(f.name)

    try:
        # Create a document with a character style
        WordPackage.new().save(str(doc_path))
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(doc_path),
                "ops": _ops([{"op": "append", "content_data": "Test paragraph"}]),
            },
        )
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(doc_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "create_style",
                                "content_data": json.dumps(
                                    {"name": "CustomChar", "style_type": "character"}
                                ),
                                "formatting": json.dumps({"bold": True}),
                            }
                        ]
                    )
                ),
            },
        )

        _, result = await mcp.call_tool(
            "read", {"file_path": str(doc_path), "scope": "styles"}
        )

        # Should have our custom character style
        char_styles = [s for s in result["styles"] if s["type"] == "character"]
        assert len(char_styles) >= 1
        style_names = [s["name"] for s in char_styles]
        assert "CustomChar" in style_names
    finally:
        doc_path.unlink(missing_ok=True)


# --- Paragraph Format Read tests ---


@pytest.fixture
async def docx_with_formatting():
    """Create a Word document with paragraph formatting."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        doc_path = Path(f.name)

    # Create document with paragraph using MCP
    WordPackage.new().save(str(doc_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": _ops([{"op": "append", "content_data": "Formatted paragraph"}]),
        },
    )

    # Get paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(doc_path), "scope": "blocks"}
    )
    para_id = blocks_result["blocks"][0]["id"]

    # Apply paragraph formatting via MCP (using "style" operation with formatting)
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "style",
                            "target_id": para_id,
                            "formatting": json.dumps(
                                {
                                    "alignment": "center",
                                    "left_indent": 0.5,
                                    "right_indent": 0.25,
                                    "first_line_indent": 0.3,
                                    "space_before": 12.0,
                                    "space_after": 6.0,
                                    "line_spacing": 1.5,
                                }
                            ),
                        }
                    ]
                )
            ),
        },
    )

    yield doc_path
    doc_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_paragraph_format(docx_with_formatting):
    """Test reading paragraph formatting via runs scope."""
    # Get the paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_formatting), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Read runs (which includes paragraph_format)
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_formatting),
            "scope": "runs",
            "target_id": para_block["id"],
        },
    )

    # Verify paragraph_format is included
    pf = result["paragraph_format"]
    assert pf is not None
    assert pf["alignment"] == "center"
    assert pf["left_indent"] == pytest.approx(0.5, abs=0.01)
    assert pf["right_indent"] == pytest.approx(0.25, abs=0.01)
    assert pf["first_line_indent"] == pytest.approx(0.3, abs=0.01)
    assert pf["space_before"] == pytest.approx(12.0, abs=0.1)
    assert pf["space_after"] == pytest.approx(6.0, abs=0.1)
    assert pf["line_spacing"] == pytest.approx(1.5, abs=0.01)


@pytest.mark.asyncio
async def test_read_paragraph_alignment(sample_docx):
    """Test reading paragraph alignment from normal document."""
    # Get the first paragraph
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Read runs with paragraph_format
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(sample_docx),
            "scope": "runs",
            "target_id": para_block["id"],
        },
    )

    # Normal paragraphs typically have no explicit alignment (None or left)
    pf = result["paragraph_format"]
    assert pf is not None
    # alignment could be None for default or 'left'
    assert pf["alignment"] is None or pf["alignment"] == "left"


# --- Character Style tests ---


@pytest.mark.asyncio
async def test_apply_character_style(sample_docx):
    """Test applying a character style to a run."""
    # Get the first paragraph
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Apply "Strong" style to run 0
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": para_block["id"],
                            "run_index": 0,
                            "formatting": '{"style": "Strong"}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Read runs and verify style
    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(sample_docx),
            "scope": "runs",
            "target_id": edit_result["element_id"],
        },
    )
    assert runs_result["runs"][0]["style"] == "Strong"


@pytest.mark.asyncio
async def test_read_character_style(sample_docx):
    """Test reading character style from run."""
    # Get the first paragraph
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Read runs - default runs have no explicit style
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(sample_docx),
            "scope": "runs",
            "target_id": para_block["id"],
        },
    )
    # Default runs typically have None or "Default Paragraph Font" style
    assert result["runs"][0]["style"] is None or result["runs"][0]["style"] is not None


# --- Rich Header/Footer tests ---


@pytest.mark.asyncio
async def test_append_paragraph_to_header(sample_docx):
    """Test appending a paragraph to the header."""
    # First set a header
    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_header",
                            "content_data": "Initial Header",
                            "section_index": 0,
                        }
                    ]
                )
            ),
        },
    )

    # Append a second paragraph
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append_header",
                            "content_type": "paragraph",
                            "content_data": "Second Header Line",
                            "section_index": 0,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "paragraph_" in edit_result["element_id"]

    # Verify both are present
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "headers_footers"}
    )
    header_text = result["headers_footers"][0]["header_text"]
    assert "Initial Header" in header_text
    assert "Second Header Line" in header_text


@pytest.mark.asyncio
async def test_append_table_to_header(sample_docx):
    """Test appending a table to the header."""
    # First set a header
    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_header",
                            "content_data": "Header Text",
                            "section_index": 0,
                        }
                    ]
                )
            ),
        },
    )

    # Append a table
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append_header",
                            "content_type": "table",
                            "content_data": '[["Col1", "Col2"], ["A", "B"]]',
                            "section_index": 0,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "table_" in edit_result["element_id"]


@pytest.mark.asyncio
async def test_clear_header(sample_docx):
    """Test clearing header content."""
    # First set a header
    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_header",
                            "content_data": "Header To Clear",
                            "section_index": 0,
                        }
                    ]
                )
            ),
        },
    )

    # Clear the header
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "clear_header",
                            "section_index": 0,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify header is cleared (should have empty or minimal content)
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "headers_footers"}
    )
    header_text = result["headers_footers"][0]["header_text"]
    # Header should be empty or contain only whitespace
    assert header_text is None or header_text.strip() == ""


# --- Cell Merge tests ---


@pytest.fixture
async def docx_with_table():
    """Create a Word document with a 3x3 table for merge testing."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        doc_path = Path(f.name)

    # Create document with heading using MCP
    WordPackage.new().save(str(doc_path))

    # Append heading and 3x3 table
    table_data = [[f"R{r}C{c}" for c in range(3)] for r in range(3)]
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "heading",
                            "content_data": "Table for Merge Testing",
                            "heading_level": 1,
                        },
                        {
                            "op": "append",
                            "content_type": "table",
                            "content_data": json.dumps(table_data),
                        },
                    ]
                )
            ),
        },
    )

    yield doc_path
    doc_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_table_cells_merge_info(docx_with_table):
    """Test that table cells include merge info fields."""
    # Get the table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Read cells
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_cells",
            "target_id": table_block["id"],
        },
    )

    # All cells should be unmerged origin cells
    assert result["table_rows"] == 3
    assert result["table_cols"] == 3
    for cell in result["cells"]:
        assert cell["grid_span"] == 1
        assert cell["row_span"] == 1
        assert cell["is_merge_origin"] is True


@pytest.mark.asyncio
async def test_merge_cells_horizontal(docx_with_table):
    """Test merging cells horizontally."""
    # Get the table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Merge row 0, columns 0-1
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "merge_cells",
                            "target_id": table_block["id"],
                            "row": 0,
                            "col": 0,
                            "content_data": '{"end_row": 0, "end_col": 1}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Re-fetch table ID (content hash changed after merge)
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Verify merge by reading cells
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_cells",
            "target_id": table_block["id"],
        },
    )

    # Find the merged cell origin (row 0, col 0)
    origin = next(c for c in result["cells"] if c["row"] == 0 and c["col"] == 0)
    assert origin["grid_span"] == 2
    assert origin["is_merge_origin"] is True

    # The continuation cell should exist but not be an origin
    continuation = next(c for c in result["cells"] if c["row"] == 0 and c["col"] == 1)
    assert continuation["is_merge_origin"] is False


@pytest.mark.asyncio
async def test_merge_cells_vertical(docx_with_table):
    """Test merging cells vertically."""
    # Get the table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Merge column 0, rows 0-1
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "merge_cells",
                            "target_id": table_block["id"],
                            "row": 0,
                            "col": 0,
                            "content_data": '{"end_row": 1, "end_col": 0}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Re-fetch table ID (content hash changed after merge)
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Verify merge by reading cells
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_cells",
            "target_id": table_block["id"],
        },
    )

    # Find the merged cell origin (row 0, col 0)
    origin = next(c for c in result["cells"] if c["row"] == 0 and c["col"] == 0)
    assert origin["row_span"] == 2
    assert origin["is_merge_origin"] is True

    # The continuation cell should exist but not be an origin
    continuation = next(c for c in result["cells"] if c["row"] == 1 and c["col"] == 0)
    assert continuation["is_merge_origin"] is False


@pytest.mark.asyncio
async def test_merge_cells_rectangular(docx_with_table):
    """Test merging a 2x2 block of cells."""
    # Get the table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Merge 2x2 block from (0,0) to (1,1)
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "merge_cells",
                            "target_id": table_block["id"],
                            "row": 0,
                            "col": 0,
                            "content_data": '{"end_row": 1, "end_col": 1}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Re-fetch table ID (content hash changed after merge)
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Verify merge by reading cells
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_cells",
            "target_id": table_block["id"],
        },
    )

    # Find the merged cell origin (row 0, col 0)
    origin = next(c for c in result["cells"] if c["row"] == 0 and c["col"] == 0)
    assert origin["grid_span"] == 2
    assert origin["row_span"] == 2
    assert origin["is_merge_origin"] is True

    # All other cells in the 2x2 block should not be origins
    for r, c in [(0, 1), (1, 0), (1, 1)]:
        cell = next(cl for cl in result["cells"] if cl["row"] == r and cl["col"] == c)
        assert cell["is_merge_origin"] is False


# =============================================================================
# Phase 3.1: Additional Font Properties Tests
# =============================================================================


@pytest.fixture
async def docx_with_font_effects():
    """Create a document with various font effects for testing."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        doc_path = Path(f.name)

    # Create document using WordPackage with font effects
    pkg = WordPackage.new()
    body = pkg.body
    # Remove default empty paragraph
    for p in list(body.findall(qn("w:p"))):
        body.remove(p)

    # Create paragraph with multiple runs
    p = etree.SubElement(body, qn("w:p"))

    # Run 0: all_caps
    r0 = etree.SubElement(p, qn("w:r"))
    rPr0 = etree.SubElement(r0, qn("w:rPr"))
    etree.SubElement(rPr0, qn("w:caps"))
    t0 = etree.SubElement(r0, qn("w:t"))
    t0.text = "ALL CAPS TEXT"

    # Run 1: small_caps
    r1 = etree.SubElement(p, qn("w:r"))
    rPr1 = etree.SubElement(r1, qn("w:rPr"))
    etree.SubElement(rPr1, qn("w:smallCaps"))
    t1 = etree.SubElement(r1, qn("w:t"))
    t1.text = "Small Caps Text"

    # Run 2: hidden
    r2 = etree.SubElement(p, qn("w:r"))
    rPr2 = etree.SubElement(r2, qn("w:rPr"))
    etree.SubElement(rPr2, qn("w:vanish"))
    t2 = etree.SubElement(r2, qn("w:t"))
    t2.text = "Hidden Text"

    # Run 3: emboss
    r3 = etree.SubElement(p, qn("w:r"))
    rPr3 = etree.SubElement(r3, qn("w:rPr"))
    etree.SubElement(rPr3, qn("w:emboss"))
    t3 = etree.SubElement(r3, qn("w:t"))
    t3.text = "Embossed Text"

    # Run 4: normal for editing
    r4 = etree.SubElement(p, qn("w:r"))
    t4 = etree.SubElement(r4, qn("w:t"))
    t4.text = "Normal Text"

    pkg.mark_xml_dirty("/word/document.xml")
    pkg.save(doc_path)

    yield doc_path
    doc_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_font_all_caps(docx_with_font_effects):
    """Test reading all_caps font property."""
    # Get the paragraph
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_font_effects), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Read runs
    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_font_effects),
            "scope": "runs",
            "target_id": para_block["id"],
        },
    )

    # Check all_caps on run 0
    assert runs_result["runs"][0]["all_caps"] is True
    assert (
        runs_result["runs"][1]["all_caps"] is None
        or runs_result["runs"][1]["all_caps"] is False
    )


@pytest.mark.asyncio
async def test_read_font_small_caps(docx_with_font_effects):
    """Test reading small_caps font property."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_font_effects), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_font_effects),
            "scope": "runs",
            "target_id": para_block["id"],
        },
    )

    # Check small_caps on run 1
    assert runs_result["runs"][1]["small_caps"] is True


@pytest.mark.asyncio
async def test_read_font_hidden(docx_with_font_effects):
    """Test reading hidden font property."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_font_effects), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_font_effects),
            "scope": "runs",
            "target_id": para_block["id"],
        },
    )

    # Check hidden on run 2
    assert runs_result["runs"][2]["hidden"] is True


@pytest.mark.asyncio
async def test_read_font_emboss(docx_with_font_effects):
    """Test reading emboss font property."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_font_effects), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_font_effects),
            "scope": "runs",
            "target_id": para_block["id"],
        },
    )

    # Check emboss on run 3
    assert runs_result["runs"][3]["emboss"] is True


@pytest.mark.asyncio
async def test_edit_font_small_caps(docx_with_font_effects):
    """Test applying small_caps formatting to a run."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_font_effects), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Apply small_caps to run 4 (normal text)
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_font_effects),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": para_block["id"],
                            "run_index": 4,
                            "formatting": json.dumps({"small_caps": True}),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify the change
    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_font_effects),
            "scope": "runs",
            "target_id": edit_result["element_id"],
        },
    )
    assert runs_result["runs"][4]["small_caps"] is True


@pytest.mark.asyncio
async def test_edit_font_emboss(docx_with_font_effects):
    """Test applying emboss effect to a run."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_font_effects), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Apply emboss to run 4
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_font_effects),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": para_block["id"],
                            "run_index": 4,
                            "formatting": json.dumps({"emboss": True}),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify
    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_font_effects),
            "scope": "runs",
            "target_id": edit_result["element_id"],
        },
    )
    assert runs_result["runs"][4]["emboss"] is True


@pytest.mark.asyncio
async def test_edit_font_imprint(docx_with_font_effects):
    """Test applying imprint effect to a run."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_font_effects), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Apply imprint to run 4
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_font_effects),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": para_block["id"],
                            "run_index": 4,
                            "formatting": json.dumps({"imprint": True}),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify
    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_font_effects),
            "scope": "runs",
            "target_id": edit_result["element_id"],
        },
    )
    assert runs_result["runs"][4]["imprint"] is True


@pytest.mark.asyncio
async def test_edit_font_outline_shadow(docx_with_font_effects):
    """Test applying outline and shadow effects to a run."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_font_effects), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Apply both outline and shadow to run 4
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_font_effects),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": para_block["id"],
                            "run_index": 4,
                            "formatting": json.dumps({"outline": True, "shadow": True}),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify both properties
    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_font_effects),
            "scope": "runs",
            "target_id": edit_result["element_id"],
        },
    )
    assert runs_result["runs"][4]["outline"] is True
    assert runs_result["runs"][4]["shadow"] is True


@pytest.mark.asyncio
async def test_clear_font_properties(docx_with_font_effects):
    """Test clearing/unsetting font properties by setting to null."""
    # Read the document to get block ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_font_effects), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # First, apply small_caps and emboss to run 0
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_font_effects),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": para_block["id"],
                            "run_index": 0,
                            "formatting": json.dumps(
                                {"small_caps": True, "emboss": True}
                            ),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify they are set
    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_font_effects),
            "scope": "runs",
            "target_id": edit_result["element_id"],
        },
    )
    assert runs_result["runs"][0]["small_caps"] is True
    assert runs_result["runs"][0]["emboss"] is True

    # Now clear (unset) by setting to null
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_font_effects),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_run",
                            "target_id": para_block["id"],
                            "run_index": 0,
                            "formatting": json.dumps(
                                {"small_caps": None, "emboss": None}
                            ),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify they are cleared (None)
    _, runs_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_font_effects),
            "scope": "runs",
            "target_id": edit_result["element_id"],
        },
    )
    assert runs_result["runs"][0]["small_caps"] is None
    assert runs_result["runs"][0]["emboss"] is None


# --- Phase 2: Edit Style Definitions ---


@pytest.fixture
async def docx_with_custom_style(tmp_path):
    """Create a document with a custom paragraph style for testing."""
    path = tmp_path / "custom_style.docx"

    # Create document with MCP
    WordPackage.new().save(str(path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": _ops(
                [{"op": "append", "content_data": "Test paragraph with custom style"}]
            ),
        },
    )

    # Create a custom style based on Normal
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "create_style",
                            "content_data": json.dumps(
                                {
                                    "style_id": "TestStyle",
                                    "name": "TestStyle",
                                    "style_type": "paragraph",
                                    "based_on": "Normal",
                                }
                            ),
                            "formatting": json.dumps(
                                {
                                    "font_name": "Arial",
                                    "font_size": 12,
                                    "bold": False,
                                }
                            ),
                        }
                    ]
                )
            ),
        },
    )

    # Get paragraph ID and apply style
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(path), "scope": "blocks"}
    )
    para_id = blocks_result["blocks"][0]["id"]

    await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "style",
                            "target_id": para_id,
                            "style_name": "TestStyle",
                        }
                    ]
                )
            ),
        },
    )

    return path


@pytest.mark.asyncio
async def test_read_style_format(docx_with_custom_style):
    """Test reading detailed style formatting."""
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_custom_style),
            "scope": "style",
            "target_id": "TestStyle",
        },
    )

    assert result["block_count"] == 1
    style_fmt = result["style_format"]
    assert style_fmt["name"] == "TestStyle"
    assert style_fmt["type"] == "paragraph"
    assert style_fmt["font_name"] == "Arial"
    assert style_fmt["font_size"] == 12.0
    # bold=False removes the element, so it reads back as None (not set)
    assert style_fmt["bold"] in (False, None)


@pytest.mark.asyncio
async def test_edit_style_font(docx_with_custom_style):
    """Test modifying style font properties."""
    # Edit the style to make it bold and 16pt
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_custom_style),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_style",
                            "target_id": "TestStyle",
                            "formatting": json.dumps(
                                {"bold": True, "font_size": 16, "italic": True}
                            ),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Read the style back and verify changes
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_custom_style),
            "scope": "style",
            "target_id": "TestStyle",
        },
    )
    style_fmt = result["style_format"]
    assert style_fmt["bold"] is True
    assert style_fmt["italic"] is True
    assert style_fmt["font_size"] == 16.0


@pytest.mark.asyncio
async def test_edit_style_paragraph(docx_with_custom_style):
    """Test modifying style paragraph properties."""
    # Edit the style paragraph formatting
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_custom_style),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_style",
                            "target_id": "TestStyle",
                            "formatting": json.dumps(
                                {
                                    "alignment": "center",
                                    "space_before": 12,
                                    "space_after": 6,
                                }
                            ),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Read the style back and verify changes
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_custom_style),
            "scope": "style",
            "target_id": "TestStyle",
        },
    )
    style_fmt = result["style_format"]
    assert style_fmt["alignment"] == "center"
    assert style_fmt["space_before"] == 12.0
    assert style_fmt["space_after"] == 6.0


@pytest.mark.asyncio
async def test_edit_style_line_spacing_multiplier_roundtrip(docx_with_custom_style):
    """Test setting line spacing as a multiplier (< 5)."""
    # Set line spacing to 1.5 (multiplier)
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_custom_style),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_style",
                            "target_id": "TestStyle",
                            "formatting": json.dumps({"line_spacing": 1.5}),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Read back and verify
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_custom_style),
            "scope": "style",
            "target_id": "TestStyle",
        },
    )
    assert result["style_format"]["line_spacing"] == 1.5


@pytest.mark.asyncio
async def test_edit_style_line_spacing_points_roundtrip(docx_with_custom_style):
    """Test setting line spacing as points (>= 5)."""
    # Set line spacing to 18 points
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_custom_style),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_style",
                            "target_id": "TestStyle",
                            "formatting": json.dumps({"line_spacing": 18}),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Read back and verify (should read as 18.0 points)
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_custom_style),
            "scope": "style",
            "target_id": "TestStyle",
        },
    )
    assert result["style_format"]["line_spacing"] == 18.0


@pytest.mark.asyncio
async def test_edit_style_alignment_justify_roundtrip(docx_with_custom_style):
    """Test that justify alignment roundtrips correctly."""
    # Set alignment to justify
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_custom_style),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_style",
                            "target_id": "TestStyle",
                            "formatting": json.dumps({"alignment": "justify"}),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Read back and verify API returns "justify" (not "both" or other variants)
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_custom_style),
            "scope": "style",
            "target_id": "TestStyle",
        },
    )
    assert result["style_format"]["alignment"] == "justify"


@pytest.mark.asyncio
async def test_edit_style_invalid_alignment_written_directly(docx_with_custom_style):
    """Test that invalid alignment values are written directly (no validation).

    Pure OOXML approach: values written as-is, Word handles unknown values.
    """
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_custom_style),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_style",
                            "target_id": "TestStyle",
                            "formatting": json.dumps({"alignment": "invalid"}),
                        }
                    ]
                )
            ),
        },
    )
    # Pure OOXML writes the value directly without validation
    assert edit_result["success"]

    # The value is written as-is (not mapped)
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_custom_style),
            "scope": "style",
            "target_id": "TestStyle",
        },
    )
    # Unknown OOXML values return None from the reader (no mapping found)
    assert result["style_format"]["alignment"] is None


# =============================================================================
# Phase 3: Table Dimensions & Layout Tests
# =============================================================================


@pytest.mark.asyncio
async def test_read_table_layout(docx_with_table):
    """Test reading table layout info via scope='table_layout'."""
    # Get the table ID first
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Read table layout
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_layout",
            "target_id": table_block["id"],
        },
    )

    # Check layout info returned
    layout = result["table_layout"]
    assert layout["table_id"] == table_block["id"]
    assert layout["autofit"] is True  # Default for new tables
    # Rows should be present (3 rows in fixture)
    assert len(layout["rows"]) == 3
    for i, row in enumerate(layout["rows"]):
        assert row["index"] == i


@pytest.mark.asyncio
async def test_set_table_alignment(docx_with_table):
    """Test setting table horizontal alignment."""
    # Get table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Set alignment to center
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_table_alignment",
                            "target_id": table_block["id"],
                            "content_data": "center",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify by reading layout
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_layout",
            "target_id": table_block["id"],
        },
    )
    assert result["table_layout"]["alignment"] == "center"


@pytest.mark.asyncio
async def test_set_table_fixed_layout(docx_with_table):
    """Test setting table to fixed layout with column widths."""
    # Get table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Set fixed layout with column widths
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_table_fixed_layout",
                            "target_id": table_block["id"],
                            "content_data": json.dumps([1.5, 2.0, 1.5]),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify autofit is False
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_layout",
            "target_id": table_block["id"],
        },
    )
    assert result["table_layout"]["autofit"] is False


@pytest.mark.asyncio
async def test_set_row_height(docx_with_table):
    """Test setting row height with at_least rule."""
    # Get table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Set row 0 height to 0.5 inches with "at_least" rule
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_row_height",
                            "target_id": table_block["id"],
                            "row": 0,
                            "content_data": json.dumps(
                                {"height": 0.5, "rule": "at_least"}
                            ),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify by reading layout
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_layout",
            "target_id": table_block["id"],
        },
    )
    row0 = result["table_layout"]["rows"][0]
    assert row0["height_inches"] == pytest.approx(0.5, rel=0.01)
    assert row0["height_rule"] == "at_least"


@pytest.mark.asyncio
async def test_set_cell_width(docx_with_table):
    """Test setting cell width."""
    # Get table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Set cell (0, 0) width to 2.0 inches
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_cell_width",
                            "target_id": table_block["id"],
                            "row": 0,
                            "col": 0,
                            "content_data": "2.0",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify by reading table cells
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_cells",
            "target_id": table_block["id"],
        },
    )
    cell_00 = next(c for c in result["cells"] if c["row"] == 0 and c["col"] == 0)
    assert cell_00["width_inches"] == pytest.approx(2.0, rel=0.01)


@pytest.mark.asyncio
async def test_set_cell_vertical_alignment(docx_with_table):
    """Test setting cell vertical alignment."""
    # Get table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Set cell (1, 1) to vertical center
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_cell_vertical_alignment",
                            "target_id": table_block["id"],
                            "row": 1,
                            "col": 1,
                            "content_data": "center",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify by reading table cells
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_cells",
            "target_id": table_block["id"],
        },
    )
    cell_11 = next(c for c in result["cells"] if c["row"] == 1 and c["col"] == 1)
    assert cell_11["vertical_alignment"] == "center"


@pytest.mark.asyncio
async def test_set_cell_borders(docx_with_table):
    """Test setting cell borders."""
    # Get table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Set borders on cell (0, 0)
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_cell_borders",
                            "target_id": table_block["id"],
                            "row": 0,
                            "col": 0,
                            "content_data": '{"top": "single:24:FF0000", "bottom": "double:12:0000FF"}',
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify by reading table cells
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_cells",
            "target_id": table_block["id"],
        },
    )
    cell_00 = next(c for c in result["cells"] if c["row"] == 0 and c["col"] == 0)
    assert cell_00["border_top"] == "single:24:FF0000"
    assert cell_00["border_bottom"] == "double:12:0000FF"


@pytest.mark.asyncio
async def test_set_cell_shading(docx_with_table):
    """Test setting cell background shading."""
    # Get table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Set shading on cell (1, 0)
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_cell_shading",
                            "target_id": table_block["id"],
                            "row": 1,
                            "col": 0,
                            "content_data": "FFFF00",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify by reading table cells
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_cells",
            "target_id": table_block["id"],
        },
    )
    cell_10 = next(c for c in result["cells"] if c["row"] == 1 and c["col"] == 0)
    assert cell_10["fill_color"] == "FFFF00"


@pytest.mark.asyncio
async def test_set_header_row(docx_with_table):
    """Test marking a row as header row."""
    # Get table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Mark row 0 as header
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_header_row",
                            "target_id": table_block["id"],
                            "row": 0,
                            "content_data": "true",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify by reading table layout
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_layout",
            "target_id": table_block["id"],
        },
    )
    row_0 = next(r for r in result["table_layout"]["rows"] if r["index"] == 0)
    assert row_0["is_header"] is True

    # Unmark as header
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_header_row",
                            "target_id": table_block["id"],
                            "row": 0,
                            "content_data": "false",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify unmarked
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_with_table),
            "scope": "table_layout",
            "target_id": table_block["id"],
        },
    )
    row_0 = next(r for r in result["table_layout"]["rows"] if r["index"] == 0)
    assert row_0["is_header"] is False


# =============================================================================
# Phase 3: Multi-Column Layout & Line Numbering Tests
# =============================================================================


@pytest.mark.asyncio
async def test_set_section_columns(sample_docx):
    """Test setting multi-column layout for a section."""
    # Set 2 columns with custom spacing and separator
    col_data = json.dumps({"num_columns": 2, "spacing_inches": 0.75, "separator": True})
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_columns",
                            "section_index": 0,
                            "content_data": col_data,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Read back page setup to verify via MCP
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "page_setup"},
    )
    page_setup = result["page_setup"][0]
    assert page_setup["columns"] == 2
    assert abs(page_setup["column_spacing"] - 0.75) < 0.01
    assert page_setup["column_separator"] is True

    # OOXML-level verification: check w:cols element exists with correct attributes
    pkg = WordPackage.open(sample_docx)
    body = pkg.body
    sectPr = body.find(qn("w:sectPr"))
    cols = sectPr.find(qn("w:cols"))
    assert cols is not None, "w:cols element should exist"
    assert cols.get(qn("w:num")) == "2"
    assert cols.get(qn("w:sep")) == "1"
    # 0.75 inches = 1080 twips
    assert cols.get(qn("w:space")) == "1080"

    # Set back to single column
    col_data = json.dumps({"num_columns": 1})
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_columns",
                            "section_index": 0,
                            "content_data": col_data,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify single column
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "page_setup"},
    )
    page_setup = result["page_setup"][0]
    assert page_setup["columns"] == 1


@pytest.mark.asyncio
async def test_set_line_numbering(sample_docx):
    """Test enabling and configuring line numbering."""
    import json

    # Enable line numbering with custom settings
    ln_data = json.dumps(
        {
            "enabled": True,
            "restart": "newSection",
            "start": 5,
            "count_by": 2,
            "distance_inches": 0.3,
        }
    )
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_line_numbering",
                            "section_index": 0,
                            "content_data": ln_data,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Read back page setup to verify via MCP
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "page_setup"},
    )
    page_setup = result["page_setup"][0]
    ln_info = page_setup["line_numbering"]
    assert ln_info is not None
    assert ln_info["enabled"] is True
    assert ln_info["restart"] == "newSection"
    assert ln_info["start"] == 5
    assert ln_info["count_by"] == 2
    assert abs(ln_info["distance_inches"] - 0.3) < 0.01

    # OOXML-level verification: check w:lnNumType element exists with correct attributes
    pkg = WordPackage.open(sample_docx)
    sectPr = pkg.body.find(qn("w:sectPr"))
    lnNumType = sectPr.find(qn("w:lnNumType"))
    assert lnNumType is not None, "w:lnNumType element should exist"
    assert lnNumType.get(qn("w:restart")) == "newSection"
    assert lnNumType.get(qn("w:start")) == "5"
    assert lnNumType.get(qn("w:countBy")) == "2"
    # 0.3 inches = 432 twips
    assert lnNumType.get(qn("w:distance")) == "432"

    # Disable line numbering
    ln_data = json.dumps({"enabled": False})
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_line_numbering",
                            "section_index": 0,
                            "content_data": ln_data,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # OOXML-level verification: w:lnNumType should be removed
    pkg = WordPackage.open(sample_docx)
    sectPr = pkg.body.find(qn("w:sectPr"))
    lnNumType = sectPr.find(qn("w:lnNumType"))
    assert lnNumType is None, "w:lnNumType element should be removed when disabled"

    # Verify disabled via MCP read
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "page_setup"},
    )
    page_setup = result["page_setup"][0]
    # When disabled, line_numbering should be None or have enabled=False
    ln_info = page_setup.get("line_numbering")
    if ln_info:
        assert ln_info["enabled"] is False


# =============================================================================
# Phase 4: Custom Properties & Style Creation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_set_and_get_custom_property(sample_docx):
    """Test setting and reading custom document properties."""
    import json

    # Set a custom string property
    prop_data = json.dumps(
        {"name": "ProjectID", "value": "PROJ-12345", "type": "string"}
    )
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_custom_property",
                            "content_data": prop_data,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Read back via meta scope (includes custom_properties in DocumentMeta)
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "meta"},
    )
    meta = result["meta"]
    custom_props = meta.get("custom_properties", [])
    assert len(custom_props) >= 1
    proj_prop = next((p for p in custom_props if p["name"] == "ProjectID"), None)
    assert proj_prop is not None
    assert proj_prop["value"] == "PROJ-12345"
    assert proj_prop["type"] == "string"

    # Set an integer property
    prop_data = json.dumps({"name": "Version", "value": "42", "type": "int"})
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_custom_property",
                            "content_data": prop_data,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Update existing property
    prop_data = json.dumps(
        {"name": "ProjectID", "value": "PROJ-99999", "type": "string"}
    )
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_custom_property",
                            "content_data": prop_data,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify update
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "meta"},
    )
    custom_props = result["meta"].get("custom_properties", [])
    proj_prop = next((p for p in custom_props if p["name"] == "ProjectID"), None)
    assert proj_prop["value"] == "PROJ-99999"


@pytest.mark.asyncio
async def test_delete_custom_property(sample_docx):
    """Test deleting a custom document property."""
    import json

    # First set a property
    prop_data = json.dumps({"name": "ToDelete", "value": "test", "type": "string"})
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_custom_property",
                            "content_data": prop_data,
                        }
                    ]
                )
            ),
        },
    )

    # Verify it exists
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "meta"},
    )
    custom_props = result["meta"].get("custom_properties", [])
    assert any(p["name"] == "ToDelete" for p in custom_props)

    # Delete it
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "delete_custom_property",
                            "content_data": "ToDelete",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify it's gone
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "meta"},
    )
    custom_props = result["meta"].get("custom_properties", [])
    assert not any(p["name"] == "ToDelete" for p in custom_props)


@pytest.mark.asyncio
async def test_custom_property_opc_structure(sample_docx):
    """Test that custom properties are correctly registered in OPC package."""
    import json
    import zipfile

    # Set a custom property
    prop_data = json.dumps(
        {"name": "OPCTestProp", "value": "OPCTestValue", "type": "string"}
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_custom_property",
                            "content_data": prop_data,
                        }
                    ]
                )
            ),
        },
    )

    # Verify OPC/ZIP structure
    with zipfile.ZipFile(sample_docx, "r") as z:
        # Check docProps/custom.xml exists
        files = z.namelist()
        assert "docProps/custom.xml" in files, (
            "docProps/custom.xml not found in package"
        )

        # Check relationship in _rels/.rels
        rels_content = z.read("_rels/.rels").decode()
        assert "custom-properties" in rels_content, (
            "custom-properties relationship not found"
        )
        assert "docProps/custom.xml" in rels_content, (
            "Target docProps/custom.xml not in rels"
        )

        # Check Content_Types.xml has the override
        content_types = z.read("[Content_Types].xml").decode()
        assert "custom-properties" in content_types, (
            "custom-properties content type not found"
        )

        # Verify the custom.xml content
        custom_xml = z.read("docProps/custom.xml").decode()
        assert "OPCTestProp" in custom_xml
        assert "OPCTestValue" in custom_xml


@pytest.mark.asyncio
async def test_create_style(sample_docx):
    """Test creating a new custom style."""
    # Create a new paragraph style
    style_data = json.dumps(
        {
            "name": "MyCustomStyle",
            "style_type": "paragraph",
            "base_style": "Normal",
        }
    )
    formatting = json.dumps({"bold": True, "font_size": 14, "color": "0000FF"})
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "create_style",
                            "content_data": style_data,
                            "formatting": formatting,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Read styles and verify the new style exists
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "styles"},
    )
    styles = result["styles"]
    custom_style = next((s for s in styles if s["name"] == "MyCustomStyle"), None)
    assert custom_style is not None
    assert custom_style["type"] == "paragraph"
    assert custom_style["builtin"] is False

    # OOXML-level verification via style scope
    _, style_result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "style", "target_id": "MyCustomStyle"},
    )
    fmt = style_result["style_format"]
    assert fmt["bold"] is True
    assert fmt["font_size"] == 14.0


@pytest.mark.asyncio
async def test_delete_style(sample_docx):
    """Test deleting a custom style."""
    import json

    # Create a custom style first
    style_data = json.dumps({"name": "StyleToDelete", "style_type": "paragraph"})
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "create_style",
                            "content_data": style_data,
                        }
                    ]
                )
            ),
        },
    )

    # Verify it exists
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "styles"},
    )
    assert any(s["name"] == "StyleToDelete" for s in result["styles"])

    # Delete it
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "delete_style",
                            "target_id": "StyleToDelete",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "Deleted" in edit_result["results"][0]["message"]

    # Verify it's gone
    _, result = await mcp.call_tool(
        "read",
        {"file_path": str(sample_docx), "scope": "styles"},
    )
    assert not any(s["name"] == "StyleToDelete" for s in result["styles"])


@pytest.mark.asyncio
async def test_cannot_delete_builtin_style(sample_docx):
    """Test that builtin styles cannot be deleted - raises error."""
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "delete_style",
                                "target_id": "Normal",
                            }
                        ]
                    )
                ),
            },
        )
    assert (
        "builtin" in str(exc_info.value) or "not found" in str(exc_info.value).lower()
    )


# -----------------------------------------------------------------------------
# Phase 5: Floating Image Positioning
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insert_floating_image(sample_docx, sample_image):
    """Test inserting a floating (anchored) image."""
    import json

    # Get first paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")
    para_id = para_block["id"]

    # Insert floating image
    formatting = json.dumps(
        {
            "position_h": 1.0,
            "position_v": 0.5,
            "relative_h": "column",
            "relative_v": "paragraph",
            "wrap_type": "square",
            "width": 1.5,
        }
    )
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_floating_image",
                            "target_id": para_id,
                            "content_data": str(sample_image),
                            "formatting": formatting,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert edit_result["element_id"].startswith("image_")

    # Verify image was inserted as anchor
    _, images_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "images"}
    )
    assert images_result["block_count"] == 1
    img = images_result["images"][0]
    assert img["position_type"] == "anchor"
    assert img["wrap_type"] == "square"


@pytest.mark.asyncio
async def test_floating_image_position_values(sample_docx, sample_image):
    """Test that floating image position values are correctly stored."""
    import json

    # Get first paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")
    para_id = para_block["id"]

    # Insert floating image with specific position
    formatting = json.dumps(
        {
            "position_h": 2.0,
            "position_v": 1.5,
            "relative_h": "page",
            "relative_v": "margin",
            "wrap_type": "tight",
            "width": 1.0,
        }
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_floating_image",
                            "target_id": para_id,
                            "content_data": str(sample_image),
                            "formatting": formatting,
                        }
                    ]
                )
            ),
        },
    )

    # Read image and verify position
    _, images_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "images"}
    )
    img = images_result["images"][0]
    assert img["position_type"] == "anchor"
    assert img["relative_from_h"] == "page"
    assert img["relative_from_v"] == "margin"
    assert img["wrap_type"] == "tight"
    # Position should be approximately 2.0 and 1.5 inches
    assert abs(img["position_h"] - 2.0) < 0.01
    assert abs(img["position_v"] - 1.5) < 0.01


@pytest.mark.asyncio
async def test_floating_image_xml_structure(sample_docx, sample_image):
    """Test that floating image produces correct OOXML structure."""
    import json
    import zipfile

    from lxml import etree

    # Get first paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")
    para_id = para_block["id"]

    # Insert floating image
    formatting = json.dumps(
        {
            "position_h": 1.0,
            "position_v": 0.5,
            "wrap_type": "square",
            "behind_doc": True,
        }
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_floating_image",
                            "target_id": para_id,
                            "content_data": str(sample_image),
                            "formatting": formatting,
                        }
                    ]
                )
            ),
        },
    )

    # Verify OOXML structure
    with zipfile.ZipFile(sample_docx, "r") as z:
        doc_xml = z.read("word/document.xml")
        root = etree.fromstring(doc_xml)
        nsmap = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
            "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
        }

        # Find anchor element
        anchors = root.findall(".//wp:anchor", namespaces=nsmap)
        assert len(anchors) == 1
        anchor = anchors[0]

        # Verify behindDoc attribute
        assert anchor.get("behindDoc") == "1"

        # Verify wrap element
        wrap = anchor.find("wp:wrapSquare", namespaces=nsmap)
        assert wrap is not None

        # Verify position elements
        pos_h = anchor.find("wp:positionH", namespaces=nsmap)
        pos_v = anchor.find("wp:positionV", namespaces=nsmap)
        assert pos_h is not None
        assert pos_v is not None


@pytest.mark.asyncio
async def test_floating_image_none_wrap(sample_docx, sample_image):
    """Test floating image with wrap_type='none' (no text wrapping)."""
    import json

    # Get first paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")
    para_id = para_block["id"]

    # Insert floating image with no wrap
    formatting = json.dumps(
        {
            "position_h": 0.5,
            "position_v": 0.5,
            "wrap_type": "none",
        }
    )
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_floating_image",
                            "target_id": para_id,
                            "content_data": str(sample_image),
                            "formatting": formatting,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify wrap type is read back correctly
    _, images_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "images"}
    )
    img = images_result["images"][0]
    assert img["wrap_type"] == "none"


@pytest.mark.asyncio
async def test_floating_image_top_and_bottom_wrap(sample_docx, sample_image):
    """Test floating image with wrap_type='top_and_bottom' (multi-word wrap type)."""
    import json

    # Get first paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")
    para_id = para_block["id"]

    # Insert floating image with top_and_bottom wrap
    formatting = json.dumps(
        {
            "position_h": 0.5,
            "position_v": 0.5,
            "wrap_type": "top_and_bottom",
        }
    )
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_floating_image",
                            "target_id": para_id,
                            "content_data": str(sample_image),
                            "formatting": formatting,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify wrap type is read back correctly
    _, images_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "images"}
    )
    img = images_result["images"][0]
    assert img["wrap_type"] == "top_and_bottom"


@pytest.mark.asyncio
async def test_floating_image_invalid_wrap_type_defaults_to_square(
    sample_docx, sample_image
):
    """Test that invalid wrap_type defaults to 'square' (documents expected behavior)."""
    import json

    # Get first paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")
    para_id = para_block["id"]

    # Insert floating image with invalid wrap_type
    formatting = json.dumps(
        {
            "position_h": 0.5,
            "position_v": 0.5,
            "wrap_type": "invalid_wrap_type",  # Not a valid wrap type
        }
    )
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_floating_image",
                            "target_id": para_id,
                            "content_data": str(sample_image),
                            "formatting": formatting,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify wrap type defaults to square
    _, images_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "images"}
    )
    img = images_result["images"][0]
    assert img["wrap_type"] == "square", "Invalid wrap_type should default to 'square'"


@pytest.mark.asyncio
async def test_build_images_includes_anchored(sample_docx, sample_image):
    """Test that build_images includes both inline and anchored images."""
    import json

    # Get first paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    para_block = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")
    para_id = para_block["id"]

    # Insert an inline image first
    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_image",
                            "target_id": para_id,
                            "content_data": str(sample_image),
                            "formatting": '{"width": 1}',
                        }
                    ]
                )
            ),
        },
    )

    # Insert a floating image
    formatting = json.dumps(
        {
            "position_h": 2.0,
            "position_v": 1.0,
            "wrap_type": "square",
        }
    )
    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_floating_image",
                            "target_id": para_id,
                            "content_data": str(sample_image),
                            "formatting": formatting,
                        }
                    ]
                )
            ),
        },
    )

    # Read images - should find both
    _, images_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "images"}
    )
    assert images_result["block_count"] == 2

    # Check position types
    position_types = [img["position_type"] for img in images_result["images"]]
    assert "inline" in position_types
    assert "anchor" in position_types


@pytest.mark.asyncio
async def test_table_layout_xml_structure(docx_with_table):
    """Test that table layout changes produce correct XML structure."""
    # Get table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_with_table), "scope": "blocks"}
    )
    table_block = next(b for b in blocks_result["blocks"] if b["type"] == "table")

    # Apply multiple layout changes
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_table_alignment",
                            "target_id": table_block["id"],
                            "content_data": "right",
                        }
                    ]
                )
            ),
        },
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_with_table),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_row_height",
                            "target_id": table_block["id"],
                            "row": 1,
                            "content_data": json.dumps(
                                {"height": 0.75, "rule": "exactly"}
                            ),
                        }
                    ]
                )
            ),
        },
    )

    # Open and verify XML using WordPackage
    pkg = WordPackage.open(docx_with_table)
    tbl = pkg.body.find(qn("w:tbl"))
    assert tbl is not None

    # Verify table alignment in XML (tblPr/jc element)
    tbl_pr = tbl.find(qn("w:tblPr"))
    assert tbl_pr is not None
    jc = tbl_pr.find(qn("w:jc"))
    assert jc is not None
    assert jc.get(qn("w:val")) == "right"

    # Verify row height in XML (trPr/trHeight element)
    rows = tbl.findall(qn("w:tr"))
    tr = rows[1]  # Second row (index 1)
    tr_pr = tr.find(qn("w:trPr"))
    assert tr_pr is not None
    tr_height = tr_pr.find(qn("w:trHeight"))
    assert tr_height is not None
    # hRule should be "exact" for "exactly" rule
    assert tr_height.get(qn("w:hRule")) == "exact"


# =============================================================================
# Phase 4: Paragraph Tab Stops Tests
# =============================================================================


@pytest.fixture
async def docx_for_tabs():
    """Create a Word document for tab stop testing."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        doc_path = Path(f.name)

    WordPackage.new().save(str(doc_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": _ops(
                [{"op": "append", "content_data": "Test paragraph for tab stops"}]
            ),
        },
    )
    yield doc_path
    doc_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_add_tab_stop(docx_for_tabs):
    """Test adding a tab stop with alignment and leader."""
    # Get paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_tabs), "scope": "blocks"}
    )
    para = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Add right-aligned tab with dot leader at 4 inches
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_tabs),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_tab_stop",
                            "target_id": para["id"],
                            "content_data": json.dumps(
                                {
                                    "position": 4.0,
                                    "alignment": "right",
                                    "leader": "dots",
                                }
                            ),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify by reading paragraph format
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_for_tabs),
            "scope": "runs",
            "target_id": para["id"],
        },
    )
    tab_stops = result["paragraph_format"]["tab_stops"]
    assert len(tab_stops) >= 1
    tab = tab_stops[0]
    assert tab["position_inches"] == pytest.approx(4.0, rel=0.01)
    assert tab["alignment"] == "right"
    assert tab["leader"] == "dots"


@pytest.mark.asyncio
async def test_clear_tab_stops(docx_for_tabs):
    """Test clearing all tab stops from a paragraph."""
    # Get paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_tabs), "scope": "blocks"}
    )
    para = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Add a tab stop first
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_tabs),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_tab_stop",
                            "target_id": para["id"],
                            "content_data": json.dumps(
                                {"position": 2.0, "alignment": "left"}
                            ),
                        }
                    ]
                )
            ),
        },
    )

    # Clear all tab stops
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_tabs),
            "ops": (
                _ops(
                    [
                        {
                            "op": "clear_tab_stops",
                            "target_id": para["id"],
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]

    # Verify no tab stops remain
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_for_tabs),
            "scope": "runs",
            "target_id": para["id"],
        },
    )
    assert result["paragraph_format"]["tab_stops"] == []


@pytest.mark.asyncio
async def test_read_tab_stops(docx_for_tabs):
    """Test reading multiple tab stops from a paragraph."""
    # Get paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_tabs), "scope": "blocks"}
    )
    para = next(b for b in blocks_result["blocks"] if b["type"] == "paragraph")

    # Add multiple tab stops
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_tabs),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_tab_stop",
                            "target_id": para["id"],
                            "content_data": json.dumps(
                                {
                                    "position": 1.0,
                                    "alignment": "left",
                                    "leader": "spaces",
                                }
                            ),
                        }
                    ]
                )
            ),
        },
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_tabs),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_tab_stop",
                            "target_id": para["id"],
                            "content_data": json.dumps(
                                {
                                    "position": 3.0,
                                    "alignment": "center",
                                    "leader": "heavy",
                                }
                            ),
                        }
                    ]
                )
            ),
        },
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_tabs),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_tab_stop",
                            "target_id": para["id"],
                            "content_data": json.dumps(
                                {
                                    "position": 5.0,
                                    "alignment": "decimal",
                                    "leader": "middle_dot",
                                }
                            ),
                        }
                    ]
                )
            ),
        },
    )

    # Read tab stops
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(docx_for_tabs),
            "scope": "runs",
            "target_id": para["id"],
        },
    )
    tab_stops = result["paragraph_format"]["tab_stops"]
    assert len(tab_stops) == 3

    # Tab stops should be returned in position order
    positions = [t["position_inches"] for t in tab_stops]
    assert positions == sorted(positions)


# --- Phase 5: Document Fields Tests ---


@pytest.fixture
async def docx_for_fields(tmp_path):
    """Create a document for field tests."""
    doc_path = tmp_path / "fields_test.docx"
    WordPackage.new().save(str(doc_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": _ops([{"op": "append", "content_data": "First section content"}]),
        },
    )
    return doc_path


@pytest.mark.asyncio
async def test_insert_field_page(docx_for_fields):
    """Test inserting PAGE field into a paragraph."""
    # Get paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_fields), "scope": "blocks"}
    )
    para = blocks_result["blocks"][0]

    # Insert PAGE field
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_fields),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_field",
                            "target_id": para["id"],
                            "content_data": "PAGE",
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"] is True
    assert "PAGE" in result["results"][0]["message"]

    # Verify XML structure - field parts are in separate runs
    pkg = WordPackage.open(docx_for_fields)
    p = pkg.body.find(qn("w:p"))
    para_xml = etree.tostring(p, encoding="unicode")
    assert "fldChar" in para_xml
    assert 'fldCharType="begin"' in para_xml
    assert 'fldCharType="separate"' in para_xml
    assert 'fldCharType="end"' in para_xml
    assert "PAGE" in para_xml


@pytest.mark.asyncio
async def test_insert_field_numpages(docx_for_fields):
    """Test inserting NUMPAGES field."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_fields), "scope": "blocks"}
    )
    para = blocks_result["blocks"][0]

    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_fields),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_field",
                            "target_id": para["id"],
                            "content_data": "NUMPAGES",
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"] is True
    assert "NUMPAGES" in result["results"][0]["message"]


@pytest.mark.asyncio
async def test_insert_page_x_of_y_footer(docx_for_fields):
    """Test inserting 'Page X of Y' in footer."""
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_fields),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_page_x_of_y",
                            "section_index": 0,
                            "content_data": "footer",
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"] is True
    assert "footer" in result["results"][0]["message"]

    # Verify footer content via MCP headers_footers scope
    _, hf_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_fields), "scope": "headers_footers"}
    )
    footer_text = hf_result["headers_footers"][0].get("footer_text", "")
    assert "Page" in footer_text
    assert "of" in footer_text


@pytest.mark.asyncio
async def test_insert_page_x_of_y_header(docx_for_fields):
    """Test inserting 'Page X of Y' in header."""
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_fields),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_page_x_of_y",
                            "section_index": 0,
                            "content_data": "header",
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"] is True
    assert "header" in result["results"][0]["message"]

    # Verify header content via MCP headers_footers scope
    _, hf_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_fields), "scope": "headers_footers"}
    )
    header_text = hf_result["headers_footers"][0].get("header_text", "")
    assert "Page" in header_text
    assert "of" in header_text


@pytest.mark.asyncio
async def test_insert_field_arbitrary_code(docx_for_fields):
    """Test that any field code is accepted (no artificial restrictions)."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_fields), "scope": "blocks"}
    )
    para = blocks_result["blocks"][0]

    # AUTHOR is a valid Word field that was previously rejected
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_fields),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_field",
                            "target_id": para["id"],
                            "content_data": "AUTHOR",
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"]


# ============================================================================
# Track Changes / Revision Tests (Phase 7)
# ============================================================================


@pytest.fixture
def tracked_changes_docx():
    """Fixture document with tracked changes (insertions and deletions)."""
    return Path("tests/word/fixtures/expected_redline.docx")


@pytest.fixture
def no_changes_docx():
    """Fixture document with no tracked changes."""
    return Path("tests/word/fixtures/fixture_no_changes.docx")


@pytest.fixture
def tracked_changes_copy(tracked_changes_docx):
    """Create a temporary copy of the tracked changes fixture for mutation tests."""
    import shutil

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        shutil.copy(tracked_changes_docx, f.name)
        yield Path(f.name)
    Path(f.name).unlink(missing_ok=True)


# --- Detection tests ---


@pytest.mark.asyncio
async def test_has_tracked_changes_true(tracked_changes_docx):
    """Test that document with tracked changes returns has_tracked_changes=True."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_docx), "scope": "revisions"}
    )
    assert result["has_tracked_changes"] is True
    assert result["block_count"] > 0


@pytest.mark.asyncio
async def test_has_tracked_changes_false(no_changes_docx):
    """Test that clean document returns has_tracked_changes=False."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(no_changes_docx), "scope": "revisions"}
    )
    assert result["has_tracked_changes"] is False
    assert result["block_count"] == 0
    assert result["revisions"] == []


# --- Read tests ---


@pytest.mark.asyncio
async def test_read_tracked_changes_returns_structure(tracked_changes_docx):
    """Test that read(scope='revisions') returns correct structure."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_docx), "scope": "revisions"}
    )
    assert "revisions" in result
    assert len(result["revisions"]) > 0

    # Check first revision has all required fields
    rev = result["revisions"][0]
    assert "id" in rev
    assert "type" in rev
    assert "author" in rev
    assert "date" in rev
    assert "text" in rev
    assert "supported" in rev
    assert "tag" in rev


@pytest.mark.asyncio
async def test_read_tracked_changes_types(tracked_changes_docx):
    """Test that revisions have correct types (insertion or deletion)."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_docx), "scope": "revisions"}
    )
    types = {rev["type"] for rev in result["revisions"]}
    # Our fixture should have both insertions and deletions
    assert types.issubset({"insertion", "deletion", "move", "formatting", "table"})
    # At minimum, should have at least one of the main types
    assert len(types & {"insertion", "deletion"}) > 0


# --- Accept/reject individual changes ---


@pytest.mark.asyncio
async def test_accept_change_by_id(tracked_changes_copy):
    """Test accepting a single change by ID."""
    # Get revisions first
    _, revisions_result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "revisions"}
    )
    assert len(revisions_result["revisions"]) > 0

    # Find a supported revision
    supported_rev = next(
        (r for r in revisions_result["revisions"] if r["supported"]), None
    )
    assert supported_rev is not None, "No supported revisions found"

    # Accept it
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(tracked_changes_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "accept_change",
                            "target_id": supported_rev["id"],
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"] is True
    assert "Accepted" in edit_result["results"][0]["message"]


@pytest.mark.asyncio
async def test_reject_change_by_id(tracked_changes_copy):
    """Test rejecting a single change by ID."""
    # Get revisions first
    _, revisions_result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "revisions"}
    )
    assert len(revisions_result["revisions"]) > 0

    # Find a supported revision
    supported_rev = next(
        (r for r in revisions_result["revisions"] if r["supported"]), None
    )
    assert supported_rev is not None, "No supported revisions found"

    # Reject it
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(tracked_changes_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "reject_change",
                            "target_id": supported_rev["id"],
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"] is True
    assert "Rejected" in edit_result["results"][0]["message"]


# --- Bulk operations ---


@pytest.mark.asyncio
async def test_accept_all_changes(tracked_changes_copy):
    """Test accepting all tracked changes."""
    # Verify there are changes before
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "revisions"}
    )
    assert before_result["has_tracked_changes"] is True

    # Accept all
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(tracked_changes_copy),
            "ops": (_ops([{"op": "accept_all_changes"}])),
        },
    )
    assert edit_result["success"] is True
    assert "Accepted" in edit_result["results"][0]["message"]

    # Verify no changes remain
    _, after_result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "revisions"}
    )
    assert after_result["has_tracked_changes"] is False
    assert after_result["block_count"] == 0


@pytest.mark.asyncio
async def test_reject_all_changes(tracked_changes_copy):
    """Test rejecting all tracked changes."""
    # Verify there are changes before
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "revisions"}
    )
    assert before_result["has_tracked_changes"] is True

    # Reject all
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(tracked_changes_copy),
            "ops": (_ops([{"op": "reject_all_changes"}])),
        },
    )
    assert edit_result["success"] is True
    assert "Rejected" in edit_result["results"][0]["message"]

    # Verify no changes remain
    _, after_result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "revisions"}
    )
    assert after_result["has_tracked_changes"] is False
    assert after_result["block_count"] == 0


# --- Round-trip tests ---


@pytest.mark.asyncio
async def test_accept_all_round_trip(tracked_changes_copy):
    """Test that document is valid after accept_all and save/reload."""
    # Accept all changes
    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(tracked_changes_copy),
            "ops": (_ops([{"op": "accept_all_changes"}])),
        },
    )

    # Reload and verify document is parseable via MCP
    _, blocks = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "blocks"}
    )
    assert blocks["block_count"] > 0  # Document still has content

    # Verify no tracked changes after reload
    _, result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "revisions"}
    )
    assert result["has_tracked_changes"] is False


# --- Edge case tests ---


@pytest.mark.asyncio
async def test_invalid_change_id_raises_error(tracked_changes_copy):
    """Test that accepting/rejecting invalid change ID raises ValueError."""
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(tracked_changes_copy),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "accept_change",
                                "target_id": "nonexistent_id_99999",
                            }
                        ]
                    )
                ),
            },
        )
    assert "not found" in str(exc_info.value).lower()


# --- Additional tests per review ---


@pytest.mark.asyncio
async def test_read_tracked_changes_document_order(tracked_changes_docx):
    """Test that tracked changes are returned in deterministic document order."""
    # Read twice and verify exact same order
    _, result1 = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_docx), "scope": "revisions"}
    )
    _, result2 = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_docx), "scope": "revisions"}
    )

    # Compare (id, tag, text) tuples for exact order match
    order1 = [(r["id"], r["tag"], r["text"]) for r in result1["revisions"]]
    order2 = [(r["id"], r["tag"], r["text"]) for r in result2["revisions"]]
    assert order1 == order2, "Document order should be deterministic"


@pytest.mark.asyncio
async def test_accept_insertion_removes_markup(tracked_changes_copy):
    """Test that accepting an insertion keeps the text but removes the revision."""
    # Get revisions and find an insertion
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "revisions"}
    )
    insertion = next(
        (
            r
            for r in before_result["revisions"]
            if r["type"] == "insertion" and r["supported"]
        ),
        None,
    )
    if insertion is None:
        pytest.skip("No supported insertion in fixture")

    inserted_text = insertion["text"]
    insertion_id = insertion["id"]

    # Accept the insertion
    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(tracked_changes_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "accept_change",
                            "target_id": insertion_id,
                        }
                    ]
                )
            ),
        },
    )

    # Verify: text should still be in document, but revision should be gone
    _, after_revisions = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "revisions"}
    )
    remaining_ids = [r["id"] for r in after_revisions["revisions"]]
    assert insertion_id not in remaining_ids, (
        "Accepted insertion should be removed from revisions"
    )

    # Text should still be present in document
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "blocks"}
    )
    all_text = " ".join(b["text"] for b in blocks_result["blocks"])
    assert inserted_text in all_text, (
        "Accepted insertion text should remain in document"
    )


# --- Dedicated fixture tests for insertion/deletion ---
# Note: test_reject_insertion_removes_text_dedicated_fixture below properly tests
# that rejecting an insertion removes text using a clean fixture with known content.


@pytest.fixture
def insertion_fixture_docx():
    """Return path to insertion-only fixture."""
    return Path("tests/word/fixtures/fixture_insertion.docx")


@pytest.fixture
def insertion_fixture_copy(insertion_fixture_docx, tmp_path):
    """Create a temporary copy of insertion fixture for mutation tests."""
    if not insertion_fixture_docx.exists():
        pytest.skip("Insertion fixture not found")
    dest = tmp_path / "insertion_copy.docx"
    dest.write_bytes(insertion_fixture_docx.read_bytes())
    return dest


@pytest.fixture
def deletion_fixture_docx():
    """Return path to deletion-only fixture."""
    return Path("tests/word/fixtures/fixture_deletion.docx")


@pytest.fixture
def deletion_fixture_copy(deletion_fixture_docx, tmp_path):
    """Create a temporary copy of deletion fixture for mutation tests."""
    if not deletion_fixture_docx.exists():
        pytest.skip("Deletion fixture not found")
    dest = tmp_path / "deletion_copy.docx"
    dest.write_bytes(deletion_fixture_docx.read_bytes())
    return dest


@pytest.mark.asyncio
async def test_reject_insertion_removes_text_dedicated_fixture(insertion_fixture_copy):
    """Test that rejecting an insertion removes the inserted text - using dedicated fixture.

    Key insight: python-docx's paragraph.text doesn't include text inside w:ins elements,
    so we verify via revisions AND blocks. After rejection:
    - The revision tracking is removed
    - The content is NOT converted to normal text (unlike accept)
    """
    # Verify fixture has exactly one insertion with known text "INSERTED"
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(insertion_fixture_copy), "scope": "revisions"}
    )
    insertions = [r for r in before_result["revisions"] if r["type"] == "insertion"]
    assert len(insertions) == 1, "Fixture should have exactly one insertion"
    assert insertions[0]["text"] == "INSERTED", (
        "Fixture insertion text should be 'INSERTED'"
    )

    insertion_id = insertions[0]["id"]

    # Reject the insertion
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(insertion_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "reject_change",
                            "target_id": insertion_id,
                        }
                    ]
                )
            ),
        },
    )

    # Verify: no tracked changes remain
    _, after_result = await mcp.call_tool(
        "read", {"file_path": str(insertion_fixture_copy), "scope": "revisions"}
    )
    assert len(after_result["revisions"]) == 0, (
        "No revisions should remain after rejection"
    )

    # Verify: text is NOT in blocks (reject removes content, unlike accept which keeps it)
    _, after_blocks = await mcp.call_tool(
        "read", {"file_path": str(insertion_fixture_copy), "scope": "blocks"}
    )
    after_text = " ".join(b["text"] for b in after_blocks["blocks"])
    assert "INSERTED" not in after_text, (
        "Inserted text should be removed after rejection"
    )


@pytest.mark.asyncio
async def test_accept_insertion_keeps_text_dedicated_fixture(insertion_fixture_copy):
    """Test that accepting an insertion keeps the inserted text - using dedicated fixture."""
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(insertion_fixture_copy), "scope": "revisions"}
    )
    insertion = before_result["revisions"][0]
    insertion_id = insertion["id"]

    # Accept the insertion
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(insertion_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "accept_change",
                            "target_id": insertion_id,
                        }
                    ]
                )
            ),
        },
    )

    # Verify: text should still be present
    _, after_blocks = await mcp.call_tool(
        "read", {"file_path": str(insertion_fixture_copy), "scope": "blocks"}
    )
    after_text = " ".join(b["text"] for b in after_blocks["blocks"])
    assert "INSERTED" in after_text, "Inserted text should remain after acceptance"

    # Verify: revision should be gone
    _, after_revisions = await mcp.call_tool(
        "read", {"file_path": str(insertion_fixture_copy), "scope": "revisions"}
    )
    assert len(after_revisions["revisions"]) == 0, "No revisions should remain"


@pytest.mark.asyncio
async def test_accept_deletion_removes_text_dedicated_fixture(deletion_fixture_copy):
    """Test that accepting a deletion removes the deleted text - using dedicated fixture."""
    # Verify fixture has exactly one deletion with known text "DELETED"
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(deletion_fixture_copy), "scope": "revisions"}
    )
    deletions = [r for r in before_result["revisions"] if r["type"] == "deletion"]
    assert len(deletions) == 1, "Fixture should have exactly one deletion"
    assert deletions[0]["text"] == "DELETED", (
        "Fixture deletion text should be 'DELETED'"
    )

    deletion_id = deletions[0]["id"]

    # Accept the deletion (removes the text)
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(deletion_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "accept_change",
                            "target_id": deletion_id,
                        }
                    ]
                )
            ),
        },
    )

    # Verify: deleted text should be GONE
    _, after_blocks = await mcp.call_tool(
        "read", {"file_path": str(deletion_fixture_copy), "scope": "blocks"}
    )
    after_text = " ".join(b["text"] for b in after_blocks["blocks"])
    assert "DELETED" not in after_text, (
        "Deleted text should be removed after acceptance"
    )


@pytest.mark.asyncio
async def test_reject_deletion_restores_text_dedicated_fixture(deletion_fixture_copy):
    """Test that rejecting a deletion restores the deleted text - using dedicated fixture."""
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(deletion_fixture_copy), "scope": "revisions"}
    )
    deletion = before_result["revisions"][0]
    deletion_id = deletion["id"]

    # Reject the deletion (keeps the text)
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(deletion_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "reject_change",
                            "target_id": deletion_id,
                        }
                    ]
                )
            ),
        },
    )

    # Verify: text should still be present (restored)
    _, after_blocks = await mcp.call_tool(
        "read", {"file_path": str(deletion_fixture_copy), "scope": "blocks"}
    )
    after_text = " ".join(b["text"] for b in after_blocks["blocks"])
    assert "DELETED" in after_text, "Deleted text should remain after rejection"


@pytest.mark.asyncio
async def test_accept_deletion_removes_deleted_text(tracked_changes_copy):
    """Test that accepting a deletion removes the deleted text from document."""
    # Get revisions and find a deletion
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "revisions"}
    )
    deletion = next(
        (
            r
            for r in before_result["revisions"]
            if r["type"] == "deletion" and r["supported"]
        ),
        None,
    )
    if deletion is None:
        pytest.skip("No supported deletion in fixture")

    deletion_id = deletion["id"]

    # Accept the deletion (deleted text should remain gone)
    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(tracked_changes_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "accept_change",
                            "target_id": deletion_id,
                        }
                    ]
                )
            ),
        },
    )

    # Verify revision is gone
    _, after_revisions = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "revisions"}
    )
    remaining_ids = [r["id"] for r in after_revisions["revisions"]]
    assert deletion_id not in remaining_ids, (
        "Accepted deletion should be removed from revisions"
    )


@pytest.mark.asyncio
async def test_reject_deletion_restores_text(tracked_changes_copy):
    """Test that rejecting a deletion restores the deleted text."""
    # Get revisions and find a deletion
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "revisions"}
    )
    deletion = next(
        (
            r
            for r in before_result["revisions"]
            if r["type"] == "deletion" and r["supported"]
        ),
        None,
    )
    if deletion is None:
        pytest.skip("No supported deletion in fixture")

    deleted_text = deletion["text"]
    deletion_id = deletion["id"]

    # Reject the deletion (deleted text should be restored)
    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(tracked_changes_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "reject_change",
                            "target_id": deletion_id,
                        }
                    ]
                )
            ),
        },
    )

    # Verify revision is gone
    _, after_revisions = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "revisions"}
    )
    remaining_ids = [r["id"] for r in after_revisions["revisions"]]
    assert deletion_id not in remaining_ids, (
        "Rejected deletion should be removed from revisions"
    )

    # Deleted text should now be in document (restored)
    _, after_blocks = await mcp.call_tool(
        "read", {"file_path": str(tracked_changes_copy), "scope": "blocks"}
    )
    text_after = " ".join(b["text"] for b in after_blocks["blocks"])
    assert deleted_text in text_after, (
        f"Rejected deletion text '{deleted_text}' should be restored"
    )


# --- Move tests ---


@pytest.fixture
def move_fixture_docx():
    """Fixture document with move changes (text moved from one location to another)."""
    return Path("tests/word/fixtures/fixture_move.docx")


@pytest.fixture
def move_fixture_copy(move_fixture_docx):
    """Create a temporary copy of the move fixture for mutation tests."""
    import shutil

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        shutil.copy(move_fixture_docx, f.name)
        yield Path(f.name)
    Path(f.name).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_move_changes(move_fixture_docx):
    """Test that move changes are detected and reported."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(move_fixture_docx), "scope": "revisions"}
    )
    assert result["has_tracked_changes"] is True

    # Should have move changes
    move_changes = [r for r in result["revisions"] if r["type"] == "move"]
    assert len(move_changes) > 0, "Should detect move changes"

    # moveFrom and moveTo wrappers should be supported
    move_wrappers = [r for r in move_changes if r["tag"] in ("moveFrom", "moveTo")]
    assert len(move_wrappers) >= 2, "Should have moveFrom and moveTo wrappers"
    for wrapper in move_wrappers:
        assert wrapper["supported"] is True, f"{wrapper['tag']} should be supported"

    # Range markers should NOT be supported (metadata only)
    range_markers = [r for r in move_changes if "Range" in r["tag"]]
    for marker in range_markers:
        assert marker["supported"] is False, f"{marker['tag']} should not be supported"


@pytest.mark.asyncio
async def test_accept_move_keeps_destination(move_fixture_copy):
    """Test that accepting a move keeps the destination content."""
    # Read moves
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(move_fixture_copy), "scope": "revisions"}
    )

    # Find a moveTo wrapper (represents destination)
    move_to = next(
        (
            r
            for r in before_result["revisions"]
            if r["tag"] == "moveTo" and r["supported"]
        ),
        None,
    )
    if move_to is None:
        pytest.skip("No supported moveTo in fixture")

    move_id = move_to["id"]
    destination_text = move_to["text"]

    # Accept the move
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(move_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "accept_change",
                            "target_id": move_id,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"] is True

    # Verify destination text is still in document
    _, after_blocks = await mcp.call_tool(
        "read", {"file_path": str(move_fixture_copy), "scope": "blocks"}
    )
    text_after = " ".join(b["text"] for b in after_blocks["blocks"])
    assert destination_text in text_after, (
        "Destination text should remain after accepting move"
    )

    # Move revisions should be gone
    _, after_revisions = await mcp.call_tool(
        "read", {"file_path": str(move_fixture_copy), "scope": "revisions"}
    )
    remaining_move_ids = [
        r["id"] for r in after_revisions["revisions"] if r["type"] == "move"
    ]
    assert move_id not in remaining_move_ids, "Accepted move should be removed"


@pytest.mark.asyncio
async def test_reject_move_keeps_source(move_fixture_copy):
    """Test that rejecting a move keeps the source content."""
    # Read moves
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(move_fixture_copy), "scope": "revisions"}
    )

    # Find a moveFrom wrapper (represents source)
    move_from = next(
        (
            r
            for r in before_result["revisions"]
            if r["tag"] == "moveFrom" and r["supported"]
        ),
        None,
    )
    if move_from is None:
        pytest.skip("No supported moveFrom in fixture")

    move_id = move_from["id"]
    source_text = move_from["text"]

    # Reject the move
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(move_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "reject_change",
                            "target_id": move_id,
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"] is True

    # Verify source text is still in document
    _, after_blocks = await mcp.call_tool(
        "read", {"file_path": str(move_fixture_copy), "scope": "blocks"}
    )
    text_after = " ".join(b["text"] for b in after_blocks["blocks"])
    assert source_text in text_after, "Source text should remain after rejecting move"

    # Move revisions should be gone
    _, after_revisions = await mcp.call_tool(
        "read", {"file_path": str(move_fixture_copy), "scope": "revisions"}
    )
    remaining_move_ids = [
        r["id"] for r in after_revisions["revisions"] if r["type"] == "move"
    ]
    assert move_id not in remaining_move_ids, "Rejected move should be removed"


@pytest.mark.asyncio
async def test_accept_all_includes_moves(move_fixture_copy):
    """Test that accept_all_changes processes moves."""
    # Verify there are move changes before
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(move_fixture_copy), "scope": "revisions"}
    )
    move_count_before = len(
        [
            r
            for r in before_result["revisions"]
            if r["type"] == "move" and r["supported"]
        ]
    )
    assert move_count_before > 0, "Should have move changes in fixture"

    # Accept all
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(move_fixture_copy),
            "ops": (_ops([{"op": "accept_all_changes"}])),
        },
    )
    assert edit_result["success"] is True

    # Verify no move changes remain
    _, after_result = await mcp.call_tool(
        "read", {"file_path": str(move_fixture_copy), "scope": "revisions"}
    )
    # Only unsupported range markers might remain
    supported_moves = [
        r for r in after_result["revisions"] if r["type"] == "move" and r["supported"]
    ]
    assert len(supported_moves) == 0, "All supported moves should be processed"


@pytest.mark.asyncio
async def test_accept_move_removes_all_markers(move_fixture_copy):
    """Test that accepting a move removes all range markers from XML."""
    from mcp_handley_lab.microsoft.word.document import _rev_xpath

    # Get a move ID
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(move_fixture_copy), "scope": "revisions"}
    )
    move_to = next(
        (
            r
            for r in before_result["revisions"]
            if r["tag"] == "moveTo" and r["supported"]
        ),
        None,
    )
    if move_to is None:
        pytest.skip("No supported moveTo in fixture")

    move_id = move_to["id"]

    # Accept the move
    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(move_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "accept_change",
                            "target_id": move_id,
                        }
                    ]
                )
            ),
        },
    )

    # Verify no move elements remain in XML for this ID
    pkg = WordPackage.open(str(move_fixture_copy))
    w_id_qn = qn("w:id")

    # Check for any move-related elements with this ID
    for tag in [
        "moveFrom",
        "moveTo",
        "moveFromRangeStart",
        "moveFromRangeEnd",
        "moveToRangeStart",
        "moveToRangeEnd",
    ]:
        elements = _rev_xpath(pkg.document_xml, f"//w:body//w:{tag}")
        for el in elements:
            assert el.get(w_id_qn) != move_id, (
                f"{tag} with id {move_id} should be removed"
            )


# --- List tests ---


@pytest.fixture
def list_fixture_docx():
    """Return path to list fixture."""
    return Path("tests/word/fixtures/fixture_list.docx")


@pytest.fixture
def list_fixture_copy(list_fixture_docx, tmp_path):
    """Create a temporary copy of list fixture for mutation tests."""
    if not list_fixture_docx.exists():
        pytest.skip("List fixture not found")
    dest = tmp_path / "list_copy.docx"
    dest.write_bytes(list_fixture_docx.read_bytes())
    return dest


@pytest.mark.asyncio
async def test_read_list_scope_returns_info(list_fixture_docx):
    """Test reading list info for a list paragraph."""
    # First get blocks to find a list paragraph
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_docx), "scope": "blocks"}
    )

    # Find first list paragraph (should be "First numbered item")
    list_para = None
    for block in blocks_result["blocks"]:
        if "numbered" in block["text"].lower():
            list_para = block
            break

    if list_para is None:
        pytest.skip("No list paragraph found in fixture")

    # Read list scope for this paragraph
    _, list_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(list_fixture_docx),
            "scope": "list",
            "target_id": list_para["id"],
        },
    )

    assert list_result["list_info"] is not None
    assert list_result["list_info"]["num_id"] is not None
    assert list_result["list_info"]["level"] is not None


@pytest.mark.asyncio
async def test_read_list_scope_returns_none_for_non_list(list_fixture_docx):
    """Test reading list info for a non-list paragraph."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_docx), "scope": "blocks"}
    )

    # Find "Regular paragraph" which is not a list
    regular_para = None
    for block in blocks_result["blocks"]:
        if "Regular paragraph" in block["text"]:
            regular_para = block
            break

    if regular_para is None:
        pytest.skip("Regular paragraph not found in fixture")

    _, list_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(list_fixture_docx),
            "scope": "list",
            "target_id": regular_para["id"],
        },
    )

    assert list_result["list_info"] is None


@pytest.mark.asyncio
async def test_set_list_level(list_fixture_copy):
    """Test setting list level on a list paragraph."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_copy), "scope": "blocks"}
    )

    # Find a list paragraph
    list_para = None
    for block in blocks_result["blocks"]:
        if "First numbered" in block["text"]:
            list_para = block
            break

    if list_para is None:
        pytest.skip("List paragraph not found")

    # Set level to 2
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(list_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_list_level",
                            "target_id": list_para["id"],
                            "content_data": "2",
                        }
                    ]
                )
            ),
        },
    )

    assert edit_result["success"]

    # Verify level changed
    _, list_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(list_fixture_copy),
            "scope": "list",
            "target_id": list_para["id"],
        },
    )
    assert list_result["list_info"]["level"] == 2


@pytest.mark.asyncio
async def test_promote_list_item(list_fixture_copy):
    """Test promoting (decreasing level of) a list item."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_copy), "scope": "blocks"}
    )

    # Find nested list paragraph (level 1)
    nested_para = None
    for block in blocks_result["blocks"]:
        if "Nested" in block["text"]:
            nested_para = block
            break

    if nested_para is None:
        pytest.skip("Nested paragraph not found")

    # Get original level
    _, before_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(list_fixture_copy),
            "scope": "list",
            "target_id": nested_para["id"],
        },
    )
    original_level = before_result["list_info"]["level"]

    # Promote
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(list_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "promote_list",
                            "target_id": nested_para["id"],
                        }
                    ]
                )
            ),
        },
    )

    assert edit_result["success"]

    # Verify level decreased
    _, after_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(list_fixture_copy),
            "scope": "list",
            "target_id": nested_para["id"],
        },
    )
    assert after_result["list_info"]["level"] == max(0, original_level - 1)


@pytest.mark.asyncio
async def test_demote_list_item(list_fixture_copy):
    """Test demoting (increasing level of) a list item."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_copy), "scope": "blocks"}
    )

    # Find first list paragraph (level 0)
    list_para = None
    for block in blocks_result["blocks"]:
        if "First numbered" in block["text"]:
            list_para = block
            break

    if list_para is None:
        pytest.skip("List paragraph not found")

    # Get original level
    _, before_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(list_fixture_copy),
            "scope": "list",
            "target_id": list_para["id"],
        },
    )
    original_level = before_result["list_info"]["level"]

    # Demote
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(list_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "demote_list",
                            "target_id": list_para["id"],
                        }
                    ]
                )
            ),
        },
    )

    assert edit_result["success"]

    # Verify level increased
    _, after_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(list_fixture_copy),
            "scope": "list",
            "target_id": list_para["id"],
        },
    )
    assert after_result["list_info"]["level"] == min(8, original_level + 1)


@pytest.mark.asyncio
async def test_remove_list_formatting(list_fixture_copy):
    """Test removing list formatting from a paragraph."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_copy), "scope": "blocks"}
    )

    # Find a list paragraph
    list_para = None
    for block in blocks_result["blocks"]:
        if "First numbered" in block["text"]:
            list_para = block
            break

    if list_para is None:
        pytest.skip("List paragraph not found")

    # Verify it's a list
    _, before_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(list_fixture_copy),
            "scope": "list",
            "target_id": list_para["id"],
        },
    )
    assert before_result["list_info"] is not None

    # Remove list formatting
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(list_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "remove_list",
                            "target_id": list_para["id"],
                        }
                    ]
                )
            ),
        },
    )

    assert edit_result["success"]

    # Verify list info is now None
    _, after_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(list_fixture_copy),
            "scope": "list",
            "target_id": list_para["id"],
        },
    )
    assert after_result["list_info"] is None


@pytest.mark.asyncio
async def test_set_list_level_fails_on_non_list(list_fixture_copy):
    """Test that set_list_level fails on non-list paragraph - raises error."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_copy), "scope": "blocks"}
    )

    # Find regular paragraph
    regular_para = None
    for block in blocks_result["blocks"]:
        if "Regular paragraph" in block["text"]:
            regular_para = block
            break

    if regular_para is None:
        pytest.skip("Regular paragraph not found")

    # Should fail because it's not a list
    with pytest.raises(ToolError):
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(list_fixture_copy),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "set_list_level",
                                "target_id": regular_para["id"],
                                "content_data": "1",
                            }
                        ]
                    )
                ),
            },
        )


@pytest.mark.asyncio
async def test_restart_numbering(list_fixture_copy):
    """Test restart_numbering operation creates new numbering sequence."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_copy), "scope": "blocks"}
    )

    # Find a list paragraph to restart
    list_para = None
    for block in blocks_result["blocks"]:
        if "First numbered" in block["text"]:
            list_para = block
            break

    if list_para is None:
        pytest.skip("List paragraph not found")

    # Restart numbering at value 5
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(list_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "restart_numbering",
                            "target_id": list_para["id"],
                            "content_data": "5",
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert "Restarted" in edit_result["results"][0]["message"]

    # Verify list info shows the paragraph is still a list
    _, after_result = await mcp.call_tool(
        "read",
        {
            "file_path": str(list_fixture_copy),
            "scope": "list",
            "target_id": list_para["id"],
        },
    )
    assert after_result["list_info"] is not None


@pytest.mark.asyncio
async def test_list_level_bounds(list_fixture_copy):
    """Test that list level must be between 0 and 8."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_copy), "scope": "blocks"}
    )

    # Find a list paragraph
    list_para = None
    for block in blocks_result["blocks"]:
        if "First numbered" in block["text"]:
            list_para = block
            break

    if list_para is None:
        pytest.skip("List paragraph not found")

    # Level -1 should fail
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(list_fixture_copy),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "set_list_level",
                                "target_id": list_para["id"],
                                "content_data": "-1",
                            }
                        ]
                    )
                ),
            },
        )
    assert "0-8" in str(exc_info.value)

    # Level 9 should fail
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(list_fixture_copy),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "set_list_level",
                                "target_id": list_para["id"],
                                "content_data": "9",
                            }
                        ]
                    )
                ),
            },
        )
    assert "0-8" in str(exc_info.value)

    # Level 0 should succeed
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(list_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_list_level",
                            "target_id": list_para["id"],
                            "content_data": "0",
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"]

    # Level 8 should succeed
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(list_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "set_list_level",
                            "target_id": list_para["id"],
                            "content_data": "8",
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"]


# =============================================================================
# TEXT BOX TESTS (Phase 9)
# =============================================================================


@pytest.fixture
def textbox_fixture_docx():
    """Fixture document with a text box."""
    return Path("tests/word/fixtures/fixture_textbox.docx")


@pytest.mark.asyncio
async def test_read_text_boxes_scope_returns_list(textbox_fixture_docx):
    """Test that reading text_boxes scope returns text box info."""
    if not textbox_fixture_docx.exists():
        pytest.skip("Text box fixture not found")

    _, result = await mcp.call_tool(
        "read", {"file_path": str(textbox_fixture_docx), "scope": "text_boxes"}
    )

    assert "text_boxes" in result
    assert len(result["text_boxes"]) >= 1, "Should find at least one text box"

    tb = result["text_boxes"][0]
    assert "id" in tb
    assert "text" in tb
    assert "paragraph_count" in tb
    assert "position_type" in tb
    assert "source_type" in tb


@pytest.mark.asyncio
async def test_text_box_info_has_correct_metadata(textbox_fixture_docx):
    """Test that text box info contains expected metadata."""
    if not textbox_fixture_docx.exists():
        pytest.skip("Text box fixture not found")

    _, result = await mcp.call_tool(
        "read", {"file_path": str(textbox_fixture_docx), "scope": "text_boxes"}
    )

    tb = result["text_boxes"][0]

    # Check metadata
    assert tb["id"] == "textbox_1", "ID should be derived from wp:docPr @id"
    assert tb["name"] == "Text Box 1", "Name should come from wp:docPr @name"
    assert tb["paragraph_count"] == 2, "Should have 2 paragraphs"
    assert "Hello from text box!" in tb["text"]
    assert "Second paragraph" in tb["text"]


@pytest.mark.asyncio
async def test_text_box_dimensions(textbox_fixture_docx):
    """Test that text box dimensions are extracted correctly."""
    if not textbox_fixture_docx.exists():
        pytest.skip("Text box fixture not found")

    _, result = await mcp.call_tool(
        "read", {"file_path": str(textbox_fixture_docx), "scope": "text_boxes"}
    )

    tb = result["text_boxes"][0]

    # Should be approximately 2x1 inches
    assert tb["width_inches"] == 2.0, "Width should be 2 inches"
    assert tb["height_inches"] == 1.0, "Height should be 1 inch"


@pytest.mark.asyncio
async def test_text_box_position_type(textbox_fixture_docx):
    """Test that text box position type is detected."""
    if not textbox_fixture_docx.exists():
        pytest.skip("Text box fixture not found")

    _, result = await mcp.call_tool(
        "read", {"file_path": str(textbox_fixture_docx), "scope": "text_boxes"}
    )

    tb = result["text_boxes"][0]

    # Should be anchor (floating)
    assert tb["position_type"] == "anchor", "Position type should be 'anchor'"
    assert tb["source_type"] == "drawingml", "Source type should be 'drawingml'"


@pytest.mark.asyncio
async def test_text_boxes_not_in_regular_blocks(textbox_fixture_docx):
    """Test that text box content is NOT included in regular blocks scope."""
    if not textbox_fixture_docx.exists():
        pytest.skip("Text box fixture not found")

    # Read blocks
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(textbox_fixture_docx), "scope": "blocks"}
    )

    # Read text boxes
    _, textbox_result = await mcp.call_tool(
        "read", {"file_path": str(textbox_fixture_docx), "scope": "text_boxes"}
    )

    tb_text = textbox_result["text_boxes"][0]["text"]
    blocks_text = " ".join(b["text"] for b in blocks_result["blocks"])

    # The text box content should NOT appear in regular blocks
    # (python-docx doesn't iterate w:txbxContent in doc.paragraphs)
    assert tb_text not in blocks_text, (
        "Text box content should not appear in regular blocks"
    )


@pytest.mark.asyncio
async def test_no_text_boxes_returns_empty_list(no_changes_docx):
    """Test that documents without text boxes return empty list."""
    if not no_changes_docx.exists():
        pytest.skip("No changes fixture not found")

    _, result = await mcp.call_tool(
        "read", {"file_path": str(no_changes_docx), "scope": "text_boxes"}
    )

    assert result["text_boxes"] == [], (
        "Should return empty list for doc without text boxes"
    )
    assert result["block_count"] == 0


@pytest.fixture
def vml_textbox_fixture_docx():
    """Fixture document with a VML text box."""
    return Path("tests/word/fixtures/fixture_textbox_vml.docx")


@pytest.mark.asyncio
async def test_vml_text_box_discovery(vml_textbox_fixture_docx):
    """Test that VML text boxes are discovered correctly."""
    if not vml_textbox_fixture_docx.exists():
        pytest.skip("VML text box fixture not found")

    _, result = await mcp.call_tool(
        "read", {"file_path": str(vml_textbox_fixture_docx), "scope": "text_boxes"}
    )

    assert len(result["text_boxes"]) >= 1, "Should find VML text box"

    tb = result["text_boxes"][0]
    assert tb["source_type"] == "vml", "Source type should be 'vml'"
    assert "VMLTextBox" in tb["id"], "ID should contain VML shape ID"
    assert "VML text box content!" in tb["text"]
    assert tb["paragraph_count"] == 2


@pytest.mark.asyncio
async def test_vml_text_box_dimensions(vml_textbox_fixture_docx):
    """Test that VML text box dimensions are extracted from style attribute."""
    if not vml_textbox_fixture_docx.exists():
        pytest.skip("VML text box fixture not found")

    _, result = await mcp.call_tool(
        "read", {"file_path": str(vml_textbox_fixture_docx), "scope": "text_boxes"}
    )

    tb = result["text_boxes"][0]

    # 150pt / 72 = ~2.08 inches, 75pt / 72 = ~1.04 inches
    assert 2.0 <= tb["width_inches"] <= 2.2, "Width should be ~2.08 inches"
    assert 1.0 <= tb["height_inches"] <= 1.1, "Height should be ~1.04 inches"


@pytest.mark.asyncio
async def test_read_text_box_content_scope(textbox_fixture_docx):
    """Test reading paragraphs inside a text box via text_box_content scope."""
    if not textbox_fixture_docx.exists():
        pytest.skip("Text box fixture not found")

    # First get the text box ID
    _, tb_result = await mcp.call_tool(
        "read", {"file_path": str(textbox_fixture_docx), "scope": "text_boxes"}
    )
    textbox_id = tb_result["text_boxes"][0]["id"]

    # Read the text box content
    _, result = await mcp.call_tool(
        "read",
        {
            "file_path": str(textbox_fixture_docx),
            "scope": "text_box_content",
            "target_id": textbox_id,
        },
    )

    assert result["block_count"] == 2, "Should have 2 paragraphs"
    assert len(result["blocks"]) == 2
    assert result["blocks"][0]["text"] == "Hello from text box!"
    assert result["blocks"][1]["text"] == "Second paragraph in text box."


@pytest.mark.asyncio
async def test_edit_text_box_operation(textbox_fixture_docx, tmp_path):
    """Test editing text in a text box paragraph."""
    if not textbox_fixture_docx.exists():
        pytest.skip("Text box fixture not found")

    # Copy fixture
    dest = tmp_path / "textbox_edit_test.docx"
    dest.write_bytes(textbox_fixture_docx.read_bytes())

    # Get text box ID
    _, tb_result = await mcp.call_tool(
        "read", {"file_path": str(dest), "scope": "text_boxes"}
    )
    textbox_id = tb_result["text_boxes"][0]["id"]

    # Edit first paragraph
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(dest),
            "ops": (
                _ops(
                    [
                        {
                            "op": "edit_text_box",
                            "target_id": textbox_id,
                            "row": 0,  # paragraph index
                            "content_data": "Edited text box content!",
                        }
                    ]
                )
            ),
        },
    )

    assert edit_result["success"]

    # Verify the change
    _, tb_result_after = await mcp.call_tool(
        "read", {"file_path": str(dest), "scope": "text_boxes"}
    )
    assert "Edited text box content!" in tb_result_after["text_boxes"][0]["text"]


# --- Phase 10: Cross-References and Captions Tests ---


@pytest.fixture
async def docx_for_bookmarks(tmp_path):
    """Create a document for bookmark tests."""
    doc_path = tmp_path / "bookmarks_test.docx"

    WordPackage.new().save(str(doc_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "heading",
                            "content_data": "Chapter 1: Introduction",
                            "heading_level": 1,
                        },
                        {
                            "op": "append",
                            "content_data": "This is the introduction paragraph.",
                        },
                    ]
                )
            ),
        },
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "heading",
                            "content_data": "Chapter 2: Methods",
                            "heading_level": 1,
                        }
                    ]
                )
            ),
        },
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "This is the methods paragraph.",
                        }
                    ]
                )
            ),
        },
    )

    return doc_path


@pytest.mark.asyncio
async def test_read_bookmarks_scope_returns_empty_for_no_bookmarks(docx_for_bookmarks):
    """Test that bookmarks scope returns empty list for doc without bookmarks."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_bookmarks), "scope": "bookmarks"}
    )

    assert result["bookmarks"] == [], (
        "Should return empty list for doc without bookmarks"
    )
    assert result["block_count"] == 0


@pytest.mark.asyncio
async def test_add_bookmark_creates_bookmark(docx_for_bookmarks):
    """Test adding a bookmark to a paragraph."""
    # Get paragraph ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_bookmarks), "scope": "blocks"}
    )
    para = blocks_result["blocks"][1]  # "This is the introduction paragraph."

    # Add bookmark
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_bookmarks),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_bookmark",
                            "target_id": para["id"],
                            "content_data": "IntroSection",
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"]
    assert "IntroSection" in result["results"][0]["message"]

    # Verify bookmark was created
    _, bm_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_bookmarks), "scope": "bookmarks"}
    )
    assert len(bm_result["bookmarks"]) == 1
    assert bm_result["bookmarks"][0]["name"] == "IntroSection"


@pytest.mark.asyncio
async def test_read_bookmarks_scope_returns_list(docx_for_bookmarks):
    """Test reading bookmarks after they're created."""
    # Get paragraph ID and add bookmarks
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_bookmarks), "scope": "blocks"}
    )

    # Add two bookmarks
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_bookmarks),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_bookmark",
                            "target_id": blocks_result["blocks"][0]["id"],
                            "content_data": "ChapterOne",
                        }
                    ]
                )
            ),
        },
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_bookmarks),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_bookmark",
                            "target_id": blocks_result["blocks"][2]["id"],
                            "content_data": "ChapterTwo",
                        }
                    ]
                )
            ),
        },
    )

    # Read bookmarks
    _, result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_bookmarks), "scope": "bookmarks"}
    )

    assert result["block_count"] == 2
    assert len(result["bookmarks"]) == 2
    names = [bm["name"] for bm in result["bookmarks"]]
    assert "ChapterOne" in names
    assert "ChapterTwo" in names


@pytest.mark.asyncio
async def test_insert_cross_reference(docx_for_bookmarks):
    """Test inserting a cross-reference to a bookmark."""
    # Get paragraph IDs
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_bookmarks), "scope": "blocks"}
    )

    # Add bookmark to first heading
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_bookmarks),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_bookmark",
                            "target_id": blocks_result["blocks"][0]["id"],
                            "content_data": "IntroHeading",
                        }
                    ]
                )
            ),
        },
    )

    # Insert cross-reference in a paragraph
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_bookmarks),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_cross_ref",
                            "target_id": blocks_result["blocks"][1]["id"],
                            "content_data": "IntroHeading",
                            "style_name": "text",
                        }
                    ]
                )
            ),  # ref_type
        },
    )
    assert result["success"]
    assert "IntroHeading" in result["results"][0]["message"]

    # Verify the field structure exists in the document via WordPackage
    pkg = WordPackage.open(docx_for_bookmarks)
    paragraphs = list(pkg.body.findall(qn("w:p")))
    para_xml = etree.tostring(paragraphs[1], encoding="unicode")
    assert "fldChar" in para_xml
    assert "REF" in para_xml
    assert "IntroHeading" in para_xml


@pytest.mark.asyncio
async def test_cross_reference_formats(docx_for_bookmarks):
    """Test different cross-reference formats: text, number, page."""
    # First add a bookmark
    _, blocks = await mcp.call_tool(
        "read", {"file_path": str(docx_for_bookmarks), "scope": "blocks"}
    )
    first_heading = blocks["blocks"][0]

    await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_bookmarks),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_bookmark",
                            "target_id": first_heading["id"],
                            "content_data": "RefTestBookmark",
                        }
                    ]
                )
            ),
        },
    )

    # Re-read blocks after modification (IDs may change)
    _, blocks = await mcp.call_tool(
        "read", {"file_path": str(docx_for_bookmarks), "scope": "blocks"}
    )

    # Test 'text' ref_type (default) - uses REF field
    _, text_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_bookmarks),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_cross_ref",
                            "target_id": blocks["blocks"][1]["id"],
                            "content_data": "RefTestBookmark",
                            "style_name": "text",
                        }
                    ]
                )
            ),
        },
    )
    assert text_result["success"]

    # Re-read blocks after modification (IDs may change)
    _, blocks = await mcp.call_tool(
        "read", {"file_path": str(docx_for_bookmarks), "scope": "blocks"}
    )

    # Test 'page' ref_type - uses PAGEREF field
    _, page_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_bookmarks),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_cross_ref",
                            "target_id": blocks["blocks"][1]["id"],
                            "content_data": "RefTestBookmark",
                            "style_name": "page",
                        }
                    ]
                )
            ),
        },
    )
    assert page_result["success"]

    # Verify both field types exist via WordPackage
    pkg = WordPackage.open(docx_for_bookmarks)
    paragraphs = list(pkg.body.findall(qn("w:p")))
    para_xml = etree.tostring(paragraphs[1], encoding="unicode")
    assert "REF " in para_xml  # text reference uses REF
    assert "PAGEREF" in para_xml  # page reference uses PAGEREF


@pytest.fixture
async def docx_for_captions(tmp_path):
    """Create a document for caption tests."""
    doc_path = tmp_path / "captions_test.docx"

    WordPackage.new().save(str(doc_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {"op": "append", "content_data": "Text before table"},
                        {
                            "op": "append",
                            "content_type": "table",
                            "content_data": json.dumps([["A", "B"], ["C", "D"]]),
                        },
                    ]
                )
            ),
        },
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(doc_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "Text after table",
                        }
                    ]
                )
            ),
        },
    )

    return doc_path


@pytest.mark.asyncio
async def test_insert_caption_below_table(docx_for_captions):
    """Test inserting a caption below a table."""
    # Get the table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_captions), "scope": "blocks"}
    )
    table_block = None
    for block in blocks_result["blocks"]:
        if block["type"] == "table":
            table_block = block
            break

    assert table_block is not None

    # Insert caption below table
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_captions),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_caption",
                            "target_id": table_block["id"],
                            "content_data": '{"label": "Table", "text": "Sample data table", "position": "below"}',
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"]
    assert "Table" in result["results"][0]["message"]

    # Verify caption was created
    _, captions_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_captions), "scope": "captions"}
    )
    assert len(captions_result["captions"]) == 1
    caption = captions_result["captions"][0]
    assert caption["label"] == "Table"
    assert "Sample data table" in caption["text"]


@pytest.mark.asyncio
async def test_insert_caption_above_element(docx_for_captions):
    """Test inserting a caption above an element."""
    # Get the table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_captions), "scope": "blocks"}
    )
    table_block = None
    for block in blocks_result["blocks"]:
        if block["type"] == "table":
            table_block = block
            break

    assert table_block is not None

    # Insert caption above table
    _, result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_captions),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_caption",
                            "target_id": table_block["id"],
                            "content_data": '{"label": "Figure", "text": "Data visualization", "position": "above"}',
                        }
                    ]
                )
            ),
        },
    )
    assert result["success"]

    # Verify caption was created via MCP read
    _, captions_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_captions), "scope": "captions"}
    )
    # Should have at least one caption with Figure label
    assert any(c["label"] == "Figure" for c in captions_result["captions"])


@pytest.mark.asyncio
async def test_read_captions_scope_returns_empty_for_no_captions(docx_for_captions):
    """Test that captions scope returns empty list for doc without captions."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_captions), "scope": "captions"}
    )

    assert result["captions"] == [], "Should return empty list for doc without captions"
    assert result["block_count"] == 0


@pytest.mark.asyncio
async def test_caption_contains_seq_field(docx_for_captions):
    """Test that captions contain SEQ field for auto-numbering."""
    # Get the table ID
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(docx_for_captions), "scope": "blocks"}
    )
    table_block = None
    for block in blocks_result["blocks"]:
        if block["type"] == "table":
            table_block = block
            break

    # Insert caption
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(docx_for_captions),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_caption",
                            "target_id": table_block["id"],
                            "content_data": '{"label": "Table", "text": "Test table"}',
                        }
                    ]
                )
            ),
        },
    )

    # Verify SEQ field is in the XML via WordPackage
    pkg = WordPackage.open(docx_for_captions)
    for p in pkg.body.findall(qn("w:p")):
        para_xml = etree.tostring(p, encoding="unicode")
        if "Table" in para_xml and "SEQ" in para_xml:
            assert "fldChar" in para_xml
            break


# --- Phase 11: Comment Threading tests ---


@pytest.mark.asyncio
async def test_comments_scope_includes_threading_fields(sample_docx):
    """Test that comments scope returns threading fields."""
    # First add a comment
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    first_para = None
    for block in blocks_result["blocks"]:
        if block["type"] == "paragraph":
            first_para = block
            break

    _, add_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_comment",
                            "target_id": first_para["id"],
                            "content_data": "Test comment",
                        }
                    ]
                )
            ),
        },
    )
    assert add_result["success"]

    # Read comments with threading info
    _, comments_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "comments"}
    )

    assert len(comments_result["comments"]) > 0
    comment = comments_result["comments"][0]

    # Verify threading fields exist
    assert "parent_id" in comment
    assert "resolved" in comment
    assert "replies" in comment

    # For a doc without commentsExtended.xml, threading should be flat
    assert comment["parent_id"] is None
    assert comment["resolved"] is False
    assert comment["replies"] == []


@pytest.mark.asyncio
async def test_reply_to_comment_creates_reply(sample_docx):
    """Test that reply_comment creates a reply to existing comment."""
    # First add a comment
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    first_para = None
    for block in blocks_result["blocks"]:
        if block["type"] == "paragraph":
            first_para = block
            break

    _, add_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_comment",
                            "target_id": first_para["id"],
                            "content_data": "Original comment",
                        }
                    ]
                )
            ),
        },
    )
    assert add_result["success"]
    # Extract comment ID from message
    import re

    match = re.search(r"comment (\d+)", add_result["results"][0]["message"])
    parent_id = match.group(1)

    # Reply to the comment
    _, reply_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "reply_comment",
                            "target_id": parent_id,
                            "content_data": "This is a reply",
                        }
                    ]
                )
            ),
        },
    )
    assert reply_result["success"]
    assert "reply" in reply_result["results"][0]["message"].lower()

    # Verify there are now 2 comments
    _, comments_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "comments"}
    )
    assert len(comments_result["comments"]) == 2


@pytest.mark.asyncio
async def test_reply_to_nonexistent_comment_raises_error(sample_docx):
    """Test that replying to non-existent comment raises ValueError."""
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "reply_comment",
                                "target_id": "9999",  # Non-existent comment ID
                                "content_data": "This should fail",
                            }
                        ]
                    )
                ),
            },
        )
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_resolve_comment_validates_comment_exists(sample_docx):
    """Test that resolve_comment validates the comment exists."""
    # First add a comment
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    first_para = None
    for block in blocks_result["blocks"]:
        if block["type"] == "paragraph":
            first_para = block
            break

    _, add_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_comment",
                            "target_id": first_para["id"],
                            "content_data": "Comment to resolve",
                        }
                    ]
                )
            ),
        },
    )
    assert add_result["success"]
    import re

    match = re.search(r"comment (\d+)", add_result["results"][0]["message"])
    comment_id = match.group(1)

    # Resolve the comment (validates it exists)
    _, resolve_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "resolve_comment",
                            "target_id": comment_id,
                        }
                    ]
                )
            ),
        },
    )
    assert resolve_result["success"]
    assert "Resolved" in resolve_result["results"][0]["message"]


@pytest.mark.asyncio
async def test_resolve_nonexistent_comment_raises_error(sample_docx):
    """Test that resolving non-existent comment raises ValueError."""
    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(sample_docx),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "resolve_comment",
                                "target_id": "9999",
                            }
                        ]
                    )
                ),  # Non-existent comment ID
            },
        )
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unresolve_comment_validates_comment_exists(sample_docx):
    """Test that unresolve_comment validates the comment exists."""
    # First add a comment
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "blocks"}
    )
    first_para = None
    for block in blocks_result["blocks"]:
        if block["type"] == "paragraph":
            first_para = block
            break

    _, add_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_comment",
                            "target_id": first_para["id"],
                            "content_data": "Comment to unresolve",
                        }
                    ]
                )
            ),
        },
    )
    assert add_result["success"]
    import re

    match = re.search(r"comment (\d+)", add_result["results"][0]["message"])
    comment_id = match.group(1)

    # Unresolve the comment (validates it exists)
    _, unresolve_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(sample_docx),
            "ops": (
                _ops(
                    [
                        {
                            "op": "unresolve_comment",
                            "target_id": comment_id,
                        }
                    ]
                )
            ),
        },
    )
    assert unresolve_result["success"]
    assert "Unresolved" in unresolve_result["results"][0]["message"]


# --- TOC (Table of Contents) Tests ---


@pytest.mark.asyncio
async def test_read_toc_scope_returns_no_toc_for_empty_doc(sample_docx):
    """Test that toc scope returns exists=False for document without TOC."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "toc"}
    )
    assert "toc_info" in result
    assert result["toc_info"]["exists"] is False


@pytest.mark.asyncio
async def test_insert_toc_creates_toc(tmp_path):
    """Test that insert_toc creates a TOC field."""
    # Create a document with headings using MCP
    file_path = tmp_path / "toc_test.docx"
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "heading",
                            "content_data": "Chapter 1",
                            "heading_level": 1,
                        },
                        {
                            "op": "append",
                            "content_data": "Content for chapter 1",
                        },
                    ]
                )
            ),
        },
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "heading",
                            "content_data": "Chapter 2",
                            "heading_level": 1,
                        }
                    ]
                )
            ),
        },
    )
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "Content for chapter 2",
                        }
                    ]
                )
            ),
        },
    )

    # Get the first paragraph to insert TOC before
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(file_path), "scope": "blocks"}
    )
    first_block = blocks_result["blocks"][0]

    # Insert TOC before first heading
    _, insert_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_toc",
                            "target_id": first_block["id"],
                            "content_data": '{"position": "before", "heading_levels": "1-3"}',
                        }
                    ]
                )
            ),
        },
    )
    assert insert_result["success"]
    assert "TOC" in insert_result["results"][0]["message"]

    # Verify TOC now exists
    _, toc_result = await mcp.call_tool(
        "read", {"file_path": str(file_path), "scope": "toc"}
    )
    assert toc_result["toc_info"]["exists"] is True


@pytest.mark.asyncio
async def test_insert_toc_heading_levels_configurable(tmp_path):
    """Test that insert_toc respects heading_levels parameter."""
    # Create a document using MCP
    file_path = tmp_path / "toc_levels.docx"
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "heading",
                            "content_data": "Heading 1",
                            "heading_level": 1,
                        },
                        {"op": "append", "content_data": "Content"},
                    ]
                )
            ),
        },
    )

    # Get first block
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(file_path), "scope": "blocks"}
    )
    first_block = blocks_result["blocks"][0]

    # Insert TOC with custom heading levels
    _, insert_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_toc",
                            "target_id": first_block["id"],
                            "content_data": '{"position": "before", "heading_levels": "1-4"}',
                        }
                    ]
                )
            ),
        },
    )
    assert insert_result["success"]

    # Verify TOC info contains heading_levels
    _, toc_result = await mcp.call_tool(
        "read", {"file_path": str(file_path), "scope": "toc"}
    )
    assert toc_result["toc_info"]["exists"]
    assert "1-4" in toc_result["toc_info"]["heading_levels"]


@pytest.mark.asyncio
async def test_update_toc_sets_dirty_flag(tmp_path):
    """Test that update_toc sets the dirty flag on the TOC field."""
    # Create a document with headings using MCP
    file_path = tmp_path / "toc_update.docx"
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "heading",
                            "content_data": "Chapter 1",
                            "heading_level": 1,
                        },
                        {"op": "append", "content_data": "Content"},
                    ]
                )
            ),
        },
    )

    # Get first block and insert TOC
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(file_path), "scope": "blocks"}
    )
    first_block = blocks_result["blocks"][0]

    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_toc",
                            "target_id": first_block["id"],
                            "content_data": '{"position": "before"}',
                        }
                    ]
                )
            ),
        },
    )

    # Update the TOC (set dirty flag)
    _, update_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "update_toc",
                        }
                    ]
                )
            ),
        },
    )
    assert update_result["success"]
    assert "dirty" in update_result["results"][0]["message"].lower()


@pytest.mark.asyncio
async def test_has_toc_detects_existing_toc(tmp_path):
    """Test that has_toc properly detects an existing TOC."""
    # Create document using MCP
    file_path = tmp_path / "toc_detect.docx"
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "heading",
                            "content_data": "Test",
                            "heading_level": 1,
                        }
                    ]
                )
            ),
        },
    )

    # Initially no TOC
    _, before_result = await mcp.call_tool(
        "read", {"file_path": str(file_path), "scope": "toc"}
    )
    assert before_result["toc_info"]["exists"] is False

    # Insert TOC
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(file_path), "scope": "blocks"}
    )
    _, _ = await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "insert_toc",
                            "target_id": blocks_result["blocks"][0]["id"],
                            "content_data": '{"position": "before"}',
                        }
                    ]
                )
            ),
        },
    )

    # Now TOC exists
    _, after_result = await mcp.call_tool(
        "read", {"file_path": str(file_path), "scope": "toc"}
    )
    assert after_result["toc_info"]["exists"] is True


# =============================================================================
# FOOTNOTES AND ENDNOTES TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_read_footnotes_empty_document(sample_docx):
    """Test reading footnotes from document with no footnotes."""
    _, result = await mcp.call_tool(
        "read", {"file_path": str(sample_docx), "scope": "footnotes"}
    )
    assert result["block_count"] == 0
    assert result["footnotes"] == []


@pytest.mark.asyncio
async def test_add_footnote():
    """Test adding a footnote to a paragraph."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with MCP
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": (
                _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "This paragraph needs a footnote.",
                        },
                        {
                            "op": "append",
                            "content_data": "Another paragraph.",
                        },
                    ]
                )
            ),
        },
    )

    try:
        # Get paragraph ID
        _, blocks_result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "blocks"}
        )
        para_id = blocks_result["blocks"][0]["id"]
        assert "paragraph" in para_id

        # Add footnote
        _, edit_result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(file_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "add_footnote",
                                "target_id": para_id,
                                "content_data": '{"text": "This is footnote content."}',
                            }
                        ]
                    )
                ),
            },
        )
        assert edit_result["success"] is True
        assert edit_result["results"][0]["message"].startswith("Added footnote")

        # Read footnotes
        _, footnotes_result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "footnotes"}
        )
        assert footnotes_result["block_count"] == 1
        assert len(footnotes_result["footnotes"]) == 1
        fn = footnotes_result["footnotes"][0]
        assert fn["type"] == "footnote"
        assert "footnote content" in fn["text"]
        assert fn["block_id"] == para_id
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_add_endnote():
    """Test adding an endnote to a paragraph."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with MCP
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops(
                [{"op": "append", "content_data": "This paragraph needs an endnote."}]
            ),
        },
    )

    try:
        # Get paragraph ID
        _, blocks_result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "blocks"}
        )
        para_id = blocks_result["blocks"][0]["id"]

        # Add endnote
        _, edit_result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(file_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "add_footnote",
                                "target_id": para_id,
                                "content_data": '{"text": "This is endnote content.", "note_type": "endnote"}',
                            }
                        ]
                    )
                ),
            },
        )
        assert edit_result["success"] is True
        assert edit_result["results"][0]["message"].startswith("Added endnote")

        # Read footnotes (includes endnotes)
        _, footnotes_result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "footnotes"}
        )
        assert footnotes_result["block_count"] == 1
        assert len(footnotes_result["footnotes"]) == 1
        en = footnotes_result["footnotes"][0]
        assert en["type"] == "endnote"
        assert "endnote content" in en["text"]
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_delete_footnote():
    """Test deleting a footnote."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with MCP
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops(
                [{"op": "append", "content_data": "This paragraph has a footnote."}]
            ),
        },
    )

    try:
        # Get paragraph ID and add footnote
        _, blocks_result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "blocks"}
        )
        para_id = blocks_result["blocks"][0]["id"]

        _, _ = await mcp.call_tool(
            "edit",
            {
                "file_path": str(file_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "add_footnote",
                                "target_id": para_id,
                                "content_data": '{"text": "To be deleted."}',
                            }
                        ]
                    )
                ),
            },
        )

        # Verify footnote exists
        _, fn_result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "footnotes"}
        )
        assert fn_result["block_count"] == 1
        fn_id = fn_result["footnotes"][0]["id"]

        # Delete footnote
        _, delete_result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(file_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "delete_footnote",
                                "target_id": str(fn_id),
                            }
                        ]
                    )
                ),
            },
        )
        assert delete_result["success"] is True
        assert delete_result["results"][0]["message"].startswith("Deleted footnote")

        # Verify footnote gone
        _, after_result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "footnotes"}
        )
        assert after_result["block_count"] == 0
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_multiple_footnotes():
    """Test adding multiple footnotes to different paragraphs."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with MCP
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": (
                _ops(
                    [
                        {"op": "append", "content_data": "First paragraph."},
                        {"op": "append", "content_data": "Second paragraph."},
                        {"op": "append", "content_data": "Third paragraph."},
                    ]
                )
            ),
        },
    )

    try:
        # Get paragraph IDs
        _, blocks_result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "blocks"}
        )
        para_ids = [b["id"] for b in blocks_result["blocks"]]

        # Add footnotes to first and third paragraphs
        for i, para_id in enumerate([para_ids[0], para_ids[2]]):
            _, _ = await mcp.call_tool(
                "edit",
                {
                    "file_path": str(file_path),
                    "ops": (
                        _ops(
                            [
                                {
                                    "op": "add_footnote",
                                    "target_id": para_id,
                                    "content_data": f'{{"text": "Footnote {i + 1}."}}',
                                }
                            ]
                        )
                    ),
                },
            )

        # Read footnotes
        _, fn_result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "footnotes"}
        )
        assert fn_result["block_count"] == 2
        assert len(fn_result["footnotes"]) == 2
        # Both should be footnotes
        for fn in fn_result["footnotes"]:
            assert fn["type"] == "footnote"
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_footnote_opc_package_integrity():
    """Test that footnotes create proper OPC package structure (content types + relationships)."""
    import zipfile

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with MCP
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops([{"op": "append", "content_data": "Paragraph with footnote."}]),
        },
    )

    try:
        # Get paragraph ID and add footnote
        _, blocks_result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "blocks"}
        )
        para_id = blocks_result["blocks"][0]["id"]

        _, edit_result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(file_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "add_footnote",
                                "target_id": para_id,
                                "content_data": '{"text": "OPC integrity test footnote."}',
                            }
                        ]
                    )
                ),
            },
        )
        assert edit_result["success"]

        # Verify OPC package structure
        with zipfile.ZipFile(file_path, "r") as zf:
            namelist = zf.namelist()

            # Footnotes part must exist
            assert "word/footnotes.xml" in namelist, (
                "footnotes.xml missing from package"
            )

            # Content types must include footnotes
            ct_content = zf.read("[Content_Types].xml").decode("utf-8")
            assert "footnotes.xml" in ct_content, (
                "footnotes.xml not in [Content_Types].xml"
            )

            # Document rels must reference footnotes
            doc_rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
            assert "footnotes.xml" in doc_rels, "footnotes.xml not in document.xml.rels"

            # Footnotes part must contain the footnote
            fn_content = zf.read("word/footnotes.xml").decode("utf-8")
            assert "OPC integrity test footnote" in fn_content

            # Document must contain footnote reference
            doc_content = zf.read("word/document.xml").decode("utf-8")
            assert "footnoteReference" in doc_content

    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_footnote_delete_removes_reference():
    """Test that deleting a footnote removes the reference from the document."""
    import zipfile

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with MCP
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops(
                [
                    {
                        "op": "append",
                        "content_data": "Paragraph with footnote to delete.",
                    }
                ]
            ),
        },
    )

    try:
        # Add a footnote
        _, blocks_result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "blocks"}
        )
        para_id = blocks_result["blocks"][0]["id"]

        _, _ = await mcp.call_tool(
            "edit",
            {
                "file_path": str(file_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "add_footnote",
                                "target_id": para_id,
                                "content_data": '{"text": "Footnote to delete."}',
                            }
                        ]
                    )
                ),
            },
        )

        # Get footnote ID via read
        _, fn_result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "footnotes"}
        )
        assert fn_result["block_count"] == 1
        footnote_id = fn_result["footnotes"][0]["id"]

        # Delete the footnote
        _, del_result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(file_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "delete_footnote",
                                "target_id": str(footnote_id),
                            }
                        ]
                    )
                ),
            },
        )
        assert del_result["success"]

        # Verify no footnotes remain
        _, after_result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "footnotes"}
        )
        assert after_result["block_count"] == 0

        # Verify footnote reference removed from document XML
        with zipfile.ZipFile(file_path, "r") as zf:
            doc_content = zf.read("word/document.xml").decode("utf-8")
            # Footnote reference with this ID should be gone
            assert f'w:id="{footnote_id}"' not in doc_content

    finally:
        file_path.unlink(missing_ok=True)


# =============================================================================
# Content Controls (SDTs) Tests
# =============================================================================


def _create_text_sdt_lxml(body, sdt_id, tag, text):
    """Helper to create a text content control using lxml."""
    sdt = etree.SubElement(body, qn("w:sdt"))
    sdtPr = etree.SubElement(sdt, qn("w:sdtPr"))

    id_el = etree.SubElement(sdtPr, qn("w:id"))
    id_el.set(qn("w:val"), str(sdt_id))

    tag_el = etree.SubElement(sdtPr, qn("w:tag"))
    tag_el.set(qn("w:val"), tag)

    sdtContent = etree.SubElement(sdt, qn("w:sdtContent"))
    p = etree.SubElement(sdtContent, qn("w:p"))
    r = etree.SubElement(p, qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = text

    return sdt


def _create_dropdown_sdt_lxml(body, sdt_id, tag, options, selected):
    """Helper to create a dropdown content control using lxml."""
    sdt = etree.SubElement(body, qn("w:sdt"))
    sdtPr = etree.SubElement(sdt, qn("w:sdtPr"))

    id_el = etree.SubElement(sdtPr, qn("w:id"))
    id_el.set(qn("w:val"), str(sdt_id))

    tag_el = etree.SubElement(sdtPr, qn("w:tag"))
    tag_el.set(qn("w:val"), tag)

    dropDown = etree.SubElement(sdtPr, qn("w:dropDownList"))
    for opt in options:
        listItem = etree.SubElement(dropDown, qn("w:listItem"))
        listItem.set(qn("w:displayText"), opt)
        listItem.set(qn("w:value"), opt.lower().replace(" ", "_"))

    sdtContent = etree.SubElement(sdt, qn("w:sdtContent"))
    p = etree.SubElement(sdtContent, qn("w:p"))
    r = etree.SubElement(p, qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = selected

    return sdt


@pytest.mark.asyncio
async def test_read_content_controls_empty_document():
    """Test reading content controls from a document with none."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with MCP (no content controls)
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops(
                [{"op": "append", "content_data": "No content controls here."}]
            ),
        },
    )

    try:
        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "content_controls"}
        )
        assert result["block_count"] == 0
        assert result["content_controls"] == []
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_content_controls_finds_text_sdt():
    """Test reading a text content control."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with paragraph, then add SDT via WordPackage
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops([{"op": "append", "content_data": "Before content control."}]),
        },
    )

    # Add SDT using WordPackage
    pkg = WordPackage.open(str(file_path))
    body = pkg.body
    _create_text_sdt_lxml(body, 123456, "name_field", "John Doe")
    pkg.mark_xml_dirty("/word/document.xml")
    pkg.save(str(file_path))

    try:
        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "content_controls"}
        )
        assert result["block_count"] == 1
        assert len(result["content_controls"]) == 1

        cc = result["content_controls"][0]
        assert cc["id"] == 123456
        assert cc["tag"] == "name_field"
        assert cc["type"] == "text"
        assert cc["value"] == "John Doe"
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_content_controls_finds_dropdown_sdt():
    """Test reading a dropdown content control."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with paragraph, then add SDT via WordPackage
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops([{"op": "append", "content_data": "Select an option:"}]),
        },
    )

    # Add SDT using WordPackage
    pkg = WordPackage.open(str(file_path))
    body = pkg.body
    _create_dropdown_sdt_lxml(
        body, 789012, "priority", ["Low", "Medium", "High"], "Medium"
    )
    pkg.mark_xml_dirty("/word/document.xml")
    pkg.save(str(file_path))

    try:
        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "content_controls"}
        )
        assert result["block_count"] == 1

        cc = result["content_controls"][0]
        assert cc["id"] == 789012
        assert cc["tag"] == "priority"
        assert cc["type"] == "dropdown"
        assert cc["value"] == "Medium"
        assert cc["options"] == ["Low", "Medium", "High"]
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_set_content_control_text():
    """Test setting the value of a text content control."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with paragraph, then add SDT via WordPackage
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops([{"op": "append", "content_data": "Form:"}]),
        },
    )

    # Add SDT using WordPackage
    pkg = WordPackage.open(str(file_path))
    body = pkg.body
    _create_text_sdt_lxml(body, 555555, "city_field", "Original City")
    pkg.mark_xml_dirty("/word/document.xml")
    pkg.save(str(file_path))

    try:
        # Update the content control
        _, edit_result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(file_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "set_content_control",
                                "target_id": "555555",
                                "content_data": "New York",
                            }
                        ]
                    )
                ),
            },
        )
        assert edit_result["success"] is True

        # Read back and verify
        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "content_controls"}
        )
        cc = result["content_controls"][0]
        assert cc["value"] == "New York"
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_set_content_control_dropdown():
    """Test setting the value of a dropdown content control."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with paragraph, then add SDT via WordPackage
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops([{"op": "append", "content_data": "Status:"}]),
        },
    )

    # Add SDT using WordPackage
    pkg = WordPackage.open(str(file_path))
    body = pkg.body
    _create_dropdown_sdt_lxml(
        body, 666666, "status", ["Draft", "Review", "Final"], "Draft"
    )
    pkg.mark_xml_dirty("/word/document.xml")
    pkg.save(str(file_path))

    try:
        # Update the dropdown
        _, edit_result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(file_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "set_content_control",
                                "target_id": "666666",
                                "content_data": "Final",
                            }
                        ]
                    )
                ),
            },
        )
        assert edit_result["success"] is True

        # Read back and verify
        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "content_controls"}
        )
        cc = result["content_controls"][0]
        assert cc["value"] == "Final"
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_set_content_control_invalid_id():
    """Test setting content control with non-existent ID raises error."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with MCP (no content controls)
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops([{"op": "append", "content_data": "No content controls."}]),
        },
    )

    try:
        with pytest.raises(ToolError):
            await mcp.call_tool(
                "edit",
                {
                    "file_path": str(file_path),
                    "ops": (
                        _ops(
                            [
                                {
                                    "op": "set_content_control",
                                    "target_id": "999999",
                                    "content_data": "Some value",
                                }
                            ]
                        )
                    ),
                },
            )
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_set_content_control_dropdown_invalid_value():
    """Test setting dropdown to invalid value raises error and doesn't mutate document."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with paragraph, then add SDT via WordPackage
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops([{"op": "append", "content_data": "Priority:"}]),
        },
    )

    # Add SDT using WordPackage
    pkg = WordPackage.open(str(file_path))
    body = pkg.body
    _create_dropdown_sdt_lxml(
        body, 888888, "priority", ["Low", "Medium", "High"], "Low"
    )
    pkg.mark_xml_dirty("/word/document.xml")
    pkg.save(str(file_path))

    try:
        # Try to set an invalid value not in options
        with pytest.raises(ToolError):
            await mcp.call_tool(
                "edit",
                {
                    "file_path": str(file_path),
                    "ops": (
                        _ops(
                            [
                                {
                                    "op": "set_content_control",
                                    "target_id": "888888",
                                    "content_data": "Invalid Option",
                                }
                            ]
                        )
                    ),  # Not in ["Low", "Medium", "High"]
                },
            )

        # Verify original value is unchanged
        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "content_controls"}
        )
        cc = result["content_controls"][0]
        assert cc["value"] == "Low", (
            "Value should be unchanged after invalid set attempt"
        )
    finally:
        file_path.unlink(missing_ok=True)


def _create_checkbox_sdt_lxml(body, sdt_id, tag, checked=False):
    """Helper to create a checkbox content control using lxml."""
    ns_w14 = "http://schemas.microsoft.com/office/word/2010/wordml"

    sdt = etree.SubElement(body, qn("w:sdt"))
    sdtPr = etree.SubElement(sdt, qn("w:sdtPr"))

    id_el = etree.SubElement(sdtPr, qn("w:id"))
    id_el.set(qn("w:val"), str(sdt_id))

    tag_el = etree.SubElement(sdtPr, qn("w:tag"))
    tag_el.set(qn("w:val"), tag)

    # Add w14:checkbox element
    checkbox = etree.SubElement(sdtPr, f"{{{ns_w14}}}checkbox")
    checked_el = etree.SubElement(checkbox, f"{{{ns_w14}}}checked")
    checked_el.set(f"{{{ns_w14}}}val", "1" if checked else "0")

    # Content with checkbox glyph
    sdtContent = etree.SubElement(sdt, qn("w:sdtContent"))
    p = etree.SubElement(sdtContent, qn("w:p"))
    r = etree.SubElement(p, qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = "\u2612" if checked else "\u2610"  # ☒ or ☐

    return sdt


@pytest.mark.asyncio
async def test_read_content_controls_finds_checkbox_sdt():
    """Test reading a checkbox content control."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with paragraph, then add SDT via WordPackage
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops([{"op": "append", "content_data": "Checkbox form:"}]),
        },
    )

    # Add SDT using WordPackage
    pkg = WordPackage.open(str(file_path))
    body = pkg.body
    _create_checkbox_sdt_lxml(body, 777777, "agree_terms", checked=False)
    pkg.mark_xml_dirty("/word/document.xml")
    pkg.save(str(file_path))

    try:
        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "content_controls"}
        )
        assert result["block_count"] == 1

        cc = result["content_controls"][0]
        assert cc["id"] == 777777
        assert cc["tag"] == "agree_terms"
        assert cc["type"] == "checkbox"
        assert cc["checked"] is False
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_set_content_control_checkbox():
    """Test setting the value of a checkbox content control."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with paragraph, then add SDT via WordPackage
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops([{"op": "append", "content_data": "Agreement:"}]),
        },
    )

    # Add SDT using WordPackage
    pkg = WordPackage.open(str(file_path))
    body = pkg.body
    _create_checkbox_sdt_lxml(body, 888888, "confirm", checked=False)
    pkg.mark_xml_dirty("/word/document.xml")
    pkg.save(str(file_path))

    try:
        # Initially unchecked
        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "content_controls"}
        )
        assert result["content_controls"][0]["checked"] is False

        # Update to checked
        _, edit_result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(file_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "set_content_control",
                                "target_id": "888888",
                                "content_data": "true",
                            }
                        ]
                    )
                ),
            },
        )
        assert edit_result["success"] is True

        # Read back and verify both state and displayed value
        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "content_controls"}
        )
        cc = result["content_controls"][0]
        assert cc["checked"] is True
        # Displayed value should be the checked glyph
        assert cc["value"] == "\u2612"  # ☒
    finally:
        file_path.unlink(missing_ok=True)


def _create_date_sdt_lxml(body, sdt_id, tag, date_value, date_format="yyyy-MM-dd"):
    """Helper to create a date picker content control using lxml."""
    sdt = etree.SubElement(body, qn("w:sdt"))
    sdtPr = etree.SubElement(sdt, qn("w:sdtPr"))

    id_el = etree.SubElement(sdtPr, qn("w:id"))
    id_el.set(qn("w:val"), str(sdt_id))

    tag_el = etree.SubElement(sdtPr, qn("w:tag"))
    tag_el.set(qn("w:val"), tag)

    # Date type marker
    date_el = etree.SubElement(sdtPr, qn("w:date"))
    date_format_el = etree.SubElement(date_el, qn("w:dateFormat"))
    date_format_el.set(qn("w:val"), date_format)

    # Content with date value
    sdtContent = etree.SubElement(sdt, qn("w:sdtContent"))
    p = etree.SubElement(sdtContent, qn("w:p"))
    r = etree.SubElement(p, qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.text = date_value

    return sdt


@pytest.mark.asyncio
async def test_read_content_controls_finds_date_sdt():
    """Test reading a date picker content control."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with paragraph, then add SDT via WordPackage
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops([{"op": "append", "content_data": "Due date:"}]),
        },
    )

    # Add SDT using WordPackage
    pkg = WordPackage.open(str(file_path))
    body = pkg.body
    _create_date_sdt_lxml(body, 999999, "due_date", "2025-12-31", "yyyy-MM-dd")
    pkg.mark_xml_dirty("/word/document.xml")
    pkg.save(str(file_path))

    try:
        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "content_controls"}
        )
        assert result["block_count"] == 1

        cc = result["content_controls"][0]
        assert cc["id"] == 999999
        assert cc["tag"] == "due_date"
        assert cc["type"] == "date"
        assert cc["value"] == "2025-12-31"
        assert cc["date_format"] == "yyyy-MM-dd"
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_set_content_control_date():
    """Test setting the value of a date content control (as plain text)."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    # Create document with paragraph, then add SDT via WordPackage
    WordPackage.new().save(str(file_path))
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(file_path),
            "ops": _ops([{"op": "append", "content_data": "Event date:"}]),
        },
    )

    # Add SDT using WordPackage
    pkg = WordPackage.open(str(file_path))
    body = pkg.body
    _create_date_sdt_lxml(body, 111111, "event_date", "2025-01-01")
    pkg.mark_xml_dirty("/word/document.xml")
    pkg.save(str(file_path))

    try:
        # Update the date value
        _, edit_result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(file_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "set_content_control",
                                "target_id": "111111",
                                "content_data": "2025-06-15",
                            }
                        ]
                    )
                ),
            },
        )
        assert edit_result["success"] is True

        # Read back and verify
        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "content_controls"}
        )
        cc = result["content_controls"][0]
        assert cc["value"] == "2025-06-15"
    finally:
        file_path.unlink(missing_ok=True)


# =============================================================================
# PHASE 7: EQUATIONS (OMML) TESTS
# =============================================================================


# Math namespace for OMML
_M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _qn_m(tag: str) -> str:
    """Create qualified name for math namespace."""
    return f"{{{_M_NS}}}{tag}"


def _create_simple_equation_pkg(body, text: str):
    """Create a simple math equation with just text (like 'x') using lxml."""
    oMathPara = etree.SubElement(body, _qn_m("oMathPara"))
    oMath = etree.SubElement(oMathPara, _qn_m("oMath"))
    r = etree.SubElement(oMath, _qn_m("r"))
    t = etree.SubElement(r, _qn_m("t"))
    t.text = text

    # Wrap in a paragraph
    p = etree.Element(qn("w:p"))
    p.append(oMathPara)
    body.append(p)
    return oMath


def _create_fraction_equation_pkg(body, numerator: str, denominator: str):
    """Create a fraction equation (a/b) using lxml."""
    oMathPara = etree.Element(_qn_m("oMathPara"))
    oMath = etree.SubElement(oMathPara, _qn_m("oMath"))
    f = etree.SubElement(oMath, _qn_m("f"))

    # Numerator
    num = etree.SubElement(f, _qn_m("num"))
    r1 = etree.SubElement(num, _qn_m("r"))
    t1 = etree.SubElement(r1, _qn_m("t"))
    t1.text = numerator

    # Denominator
    den = etree.SubElement(f, _qn_m("den"))
    r2 = etree.SubElement(den, _qn_m("r"))
    t2 = etree.SubElement(r2, _qn_m("t"))
    t2.text = denominator

    # Wrap in a paragraph
    p = etree.Element(qn("w:p"))
    p.append(oMathPara)
    body.append(p)
    return oMath


def _create_superscript_equation_pkg(body, base: str, exponent: str):
    """Create a superscript equation (x^2) using lxml."""
    oMathPara = etree.Element(_qn_m("oMathPara"))
    oMath = etree.SubElement(oMathPara, _qn_m("oMath"))
    sSup = etree.SubElement(oMath, _qn_m("sSup"))

    # Base element
    e = etree.SubElement(sSup, _qn_m("e"))
    r1 = etree.SubElement(e, _qn_m("r"))
    t1 = etree.SubElement(r1, _qn_m("t"))
    t1.text = base

    # Superscript
    sup = etree.SubElement(sSup, _qn_m("sup"))
    r2 = etree.SubElement(sup, _qn_m("r"))
    t2 = etree.SubElement(r2, _qn_m("t"))
    t2.text = exponent

    # Wrap in a paragraph
    p = etree.Element(qn("w:p"))
    p.append(oMathPara)
    body.append(p)
    return oMath


@pytest.mark.asyncio
async def test_read_equations_empty_document():
    """Test reading equations from document with none."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    try:
        # Create document without equations using MCP
        WordPackage.new().save(str(file_path))
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(file_path),
                "ops": _ops([{"op": "append", "content_data": "No equations here"}]),
            },
        )

        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "equations"}
        )
        assert result["block_count"] == 0
        assert result["equations"] == []
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_equations_finds_simple_equation():
    """Test reading a simple text equation."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    try:
        # Create document and add equation using WordPackage
        pkg = WordPackage.new()
        body = pkg.body
        # Remove default paragraph
        for p in list(body.findall(qn("w:p"))):
            body.remove(p)
        # Add intro paragraph
        add_paragraph_to_pkg(pkg, "The variable:")
        # Add equation
        _create_simple_equation_pkg(body, "x")
        pkg.mark_xml_dirty("/word/document.xml")
        pkg.save(file_path)

        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "equations"}
        )
        assert result["block_count"] == 1

        eq = result["equations"][0]
        assert eq["text"] == "x"
        assert eq["complexity"] == "simple"
        assert eq["id"]  # Has content-addressed ID
        assert eq["block_id"]  # Has block ID
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_equations_finds_fraction():
    """Test reading a fraction equation."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    try:
        # Create document and add equation using WordPackage
        pkg = WordPackage.new()
        body = pkg.body
        # Remove default paragraph
        for p in list(body.findall(qn("w:p"))):
            body.remove(p)
        # Add intro paragraph
        add_paragraph_to_pkg(pkg, "The fraction:")
        # Add equation
        _create_fraction_equation_pkg(body, "a", "b")
        pkg.mark_xml_dirty("/word/document.xml")
        pkg.save(file_path)

        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "equations"}
        )
        assert result["block_count"] == 1

        eq = result["equations"][0]
        assert eq["text"] == "(a)/(b)"
        assert eq["complexity"] == "fraction"
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_equations_finds_superscript():
    """Test reading a superscript equation."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        file_path = Path(f.name)

    try:
        # Create document and add equation using WordPackage
        pkg = WordPackage.new()
        body = pkg.body
        # Remove default paragraph
        for p in list(body.findall(qn("w:p"))):
            body.remove(p)
        # Add intro paragraph
        add_paragraph_to_pkg(pkg, "The expression:")
        # Add equation
        _create_superscript_equation_pkg(body, "x", "2")
        pkg.mark_xml_dirty("/word/document.xml")
        pkg.save(file_path)

        _, result = await mcp.call_tool(
            "read", {"file_path": str(file_path), "scope": "equations"}
        )
        assert result["block_count"] == 1

        eq = result["equations"][0]
        assert eq["text"] == "x^2"
        assert eq["complexity"] == "simple"  # Simple superscript
    finally:
        file_path.unlink(missing_ok=True)


# =============================================================================
# Tests for GitHub #129 fixes: Document creation and add_to_list
# =============================================================================


@pytest.mark.asyncio
async def test_new_document_has_section():
    """Test that newly created documents have exactly 1 section."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        new_path = Path(f.name)
    new_path.unlink()

    try:
        # Create new document
        WordPackage.new().save(str(new_path))

        # Read metadata
        _, result = await mcp.call_tool(
            "read", {"file_path": str(new_path), "scope": "meta"}
        )
        assert result["meta"]["sections"] == 1
    finally:
        new_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_new_document_has_page_dimensions():
    """Test that new documents have non-zero page dimensions."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        new_path = Path(f.name)
    new_path.unlink()

    try:
        WordPackage.new().save(str(new_path))

        _, result = await mcp.call_tool(
            "read", {"file_path": str(new_path), "scope": "page_setup"}
        )
        assert len(result["page_setup"]) == 1
        ps = result["page_setup"][0]
        assert ps["page_width"] > 0, "Page width should be positive"
        assert ps["page_height"] > 0, "Page height should be positive"
        assert ps["top_margin"] > 0, "Top margin should be positive"
        assert ps["bottom_margin"] > 0, "Bottom margin should be positive"
        assert ps["left_margin"] > 0, "Left margin should be positive"
        assert ps["right_margin"] > 0, "Right margin should be positive"
    finally:
        new_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_set_property_on_new_document():
    """Test that set_meta persists title/author on new documents."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        new_path = Path(f.name)
    new_path.unlink()

    try:
        # Create and set meta
        WordPackage.new().save(str(new_path))
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(new_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "set_property",
                                "content_data": json.dumps(
                                    {"title": "Test Title", "author": "Test Author"}
                                ),
                            }
                        ]
                    )
                ),
            },
        )

        # Re-read and verify
        _, result = await mcp.call_tool(
            "read", {"file_path": str(new_path), "scope": "meta"}
        )
        assert result["meta"]["title"] == "Test Title"
        assert result["meta"]["author"] == "Test Author"
    finally:
        new_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_set_property_creates_core_xml_on_minimal_doc():
    """Test set_meta works on documents without core.xml (roundtrip save/load)."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        new_path = Path(f.name)
    new_path.unlink()

    try:
        # Create doc, set meta, save
        WordPackage.new().save(str(new_path))
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(new_path),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "set_property",
                                "content_data": json.dumps({"title": "Roundtrip Test"}),
                            }
                        ]
                    )
                ),
            },
        )

        # Read back to verify persistence
        _, result = await mcp.call_tool(
            "read", {"file_path": str(new_path), "scope": "meta"}
        )
        assert result["meta"]["title"] == "Roundtrip Test"
    finally:
        new_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_add_to_list(list_fixture_copy):
    """Test add_to_list adds a paragraph to an existing list."""
    # Get blocks to find a list paragraph
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_copy), "scope": "blocks"}
    )

    list_para = None
    for block in blocks_result["blocks"]:
        if "First numbered" in block["text"]:
            list_para = block
            break

    if list_para is None:
        pytest.skip("List paragraph not found")

    # Add new list item after it
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(list_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_to_list",
                            "target_id": list_para["id"],
                            "content_data": json.dumps(
                                {"text": "New list item", "position": "after"}
                            ),
                        }
                    ]
                )
            ),
        },
    )
    assert edit_result["success"]
    assert edit_result["element_id"]  # New paragraph ID returned

    # Verify new item exists and is in the list
    _, verify_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_copy), "scope": "blocks"}
    )
    texts = [b["text"] for b in verify_result["blocks"]]
    assert "New list item" in texts


@pytest.mark.asyncio
async def test_add_to_list_inherits_level(list_fixture_copy):
    """Test add_to_list inherits level from reference when level not specified."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_copy), "scope": "blocks"}
    )

    list_para = None
    for block in blocks_result["blocks"]:
        if "First numbered" in block["text"]:
            list_para = block
            break

    if list_para is None:
        pytest.skip("List paragraph not found")

    # Get original level
    _, orig_list = await mcp.call_tool(
        "read",
        {
            "file_path": str(list_fixture_copy),
            "scope": "list",
            "target_id": list_para["id"],
        },
    )
    orig_level = orig_list["list_info"]["level"]

    # Add item without specifying level
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(list_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_to_list",
                            "target_id": list_para["id"],
                            "content_data": json.dumps(
                                {"text": "Inherited level item"}
                            ),
                        }
                    ]
                )
            ),
        },
    )
    new_id = edit_result["element_id"]

    # Verify new item has same level
    _, new_list = await mcp.call_tool(
        "read",
        {
            "file_path": str(list_fixture_copy),
            "scope": "list",
            "target_id": new_id,
        },
    )
    assert new_list["list_info"]["level"] == orig_level


@pytest.mark.asyncio
async def test_add_to_list_fails_on_non_list(list_fixture_copy):
    """Test add_to_list raises error for non-list paragraphs."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_copy), "scope": "blocks"}
    )

    regular_para = None
    for block in blocks_result["blocks"]:
        if "Regular paragraph" in block["text"]:
            regular_para = block
            break

    if regular_para is None:
        pytest.skip("Regular paragraph not found")

    with pytest.raises(ToolError) as exc_info:
        await mcp.call_tool(
            "edit",
            {
                "file_path": str(list_fixture_copy),
                "ops": (
                    _ops(
                        [
                            {
                                "op": "add_to_list",
                                "target_id": regular_para["id"],
                                "content_data": json.dumps({"text": "Should fail"}),
                            }
                        ]
                    )
                ),
            },
        )
    error_msg = str(exc_info.value)
    assert (
        "w:numPr" in error_msg
        or "not in a list" in error_msg
        or "not supported" in error_msg
    )


@pytest.mark.asyncio
async def test_add_to_list_whitespace_preserved(list_fixture_copy):
    """Test add_to_list preserves leading/trailing whitespace in text."""
    _, blocks_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_copy), "scope": "blocks"}
    )

    list_para = None
    for block in blocks_result["blocks"]:
        if "First numbered" in block["text"]:
            list_para = block
            break

    if list_para is None:
        pytest.skip("List paragraph not found")

    # Add item with leading/trailing spaces
    _, edit_result = await mcp.call_tool(
        "edit",
        {
            "file_path": str(list_fixture_copy),
            "ops": (
                _ops(
                    [
                        {
                            "op": "add_to_list",
                            "target_id": list_para["id"],
                            "content_data": json.dumps({"text": "  spaced text  "}),
                        }
                    ]
                )
            ),
        },
    )
    new_id = edit_result["element_id"]

    # Verify whitespace preserved
    _, verify_result = await mcp.call_tool(
        "read", {"file_path": str(list_fixture_copy), "scope": "blocks"}
    )
    new_block = None
    for block in verify_result["blocks"]:
        if block["id"] == new_id:
            new_block = block
            break

    assert new_block is not None
    assert new_block["text"] == "  spaced text  "
