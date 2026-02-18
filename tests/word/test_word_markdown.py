"""Tests for lightweight markdown parsing and insertion in Word content operations."""

import json
import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.ops.core import expand_markdown_content
from mcp_handley_lab.microsoft.word.ops.lists import get_list_info
from mcp_handley_lab.microsoft.word.package import WordPackage
from mcp_handley_lab.microsoft.word.tool import mcp


class TestExpandMarkdownContent:
    """Tests for expand_markdown_content() parser."""

    def test_single_line(self):
        result = expand_markdown_content("Hello world")
        assert result == [("paragraph", "Hello world", 0)]

    def test_multi_line_paragraphs(self):
        result = expand_markdown_content("First\nSecond\nThird")
        assert result == [
            ("paragraph", "First", 0),
            ("paragraph", "Second", 0),
            ("paragraph", "Third", 0),
        ]

    def test_bullet_dash(self):
        result = expand_markdown_content("- Item one\n- Item two")
        assert result == [
            ("bullet", "Item one", 0),
            ("bullet", "Item two", 0),
        ]

    def test_bullet_asterisk(self):
        result = expand_markdown_content("* Item one\n* Item two")
        assert result == [
            ("bullet", "Item one", 0),
            ("bullet", "Item two", 0),
        ]

    def test_numbered_items(self):
        result = expand_markdown_content("1. First\n2. Second\n3. Third")
        assert result == [
            ("numbered", "First", 0),
            ("numbered", "Second", 0),
            ("numbered", "Third", 0),
        ]

    def test_numbered_multi_digit(self):
        result = expand_markdown_content("12. Twelfth item")
        assert result == [("numbered", "Twelfth item", 0)]

    def test_mixed_content(self):
        text = "Intro paragraph\n- Bullet one\n- Bullet two\n1. Num one\n2. Num two\nClosing"
        result = expand_markdown_content(text)
        assert result == [
            ("paragraph", "Intro paragraph", 0),
            ("bullet", "Bullet one", 0),
            ("bullet", "Bullet two", 0),
            ("numbered", "Num one", 0),
            ("numbered", "Num two", 0),
            ("paragraph", "Closing", 0),
        ]

    def test_indented_bullets_two_spaces(self):
        result = expand_markdown_content("- Top\n  - Level 1\n    - Level 2")
        assert result == [
            ("bullet", "Top", 0),
            ("bullet", "Level 1", 1),
            ("bullet", "Level 2", 2),
        ]

    def test_indented_numbered(self):
        result = expand_markdown_content("1. Top\n  1. Sub")
        assert result == [
            ("numbered", "Top", 0),
            ("numbered", "Sub", 1),
        ]

    def test_indent_cap_at_8(self):
        # 20 spaces = 10 indent levels, should be capped at 8
        result = expand_markdown_content("                    - Deep item")
        assert result == [("bullet", "Deep item", 8)]

    def test_empty_lines_produce_empty_paragraphs(self):
        result = expand_markdown_content("First\n\nSecond")
        assert result == [
            ("paragraph", "First", 0),
            ("paragraph", "", 0),
            ("paragraph", "Second", 0),
        ]

    def test_whitespace_only_line(self):
        result = expand_markdown_content("Before\n   \nAfter")
        assert result == [
            ("paragraph", "Before", 0),
            ("paragraph", "", 0),
            ("paragraph", "After", 0),
        ]

    def test_crlf_normalization(self):
        result = expand_markdown_content("Line one\r\nLine two\r\nLine three")
        assert result == [
            ("paragraph", "Line one", 0),
            ("paragraph", "Line two", 0),
            ("paragraph", "Line three", 0),
        ]

    def test_cr_normalization(self):
        result = expand_markdown_content("Line one\rLine two")
        assert result == [
            ("paragraph", "Line one", 0),
            ("paragraph", "Line two", 0),
        ]

    def test_leading_newline(self):
        result = expand_markdown_content("\nContent")
        assert result == [
            ("paragraph", "", 0),
            ("paragraph", "Content", 0),
        ]

    def test_trailing_newline(self):
        result = expand_markdown_content("Content\n")
        assert result == [
            ("paragraph", "Content", 0),
            ("paragraph", "", 0),
        ]

    def test_single_bullet_no_newline(self):
        """Single-line '- item' without newline: still parsed as bullet."""
        result = expand_markdown_content("- Single item")
        assert result == [("bullet", "Single item", 0)]

    def test_indented_paragraph_not_list(self):
        """Indented text without list marker is a paragraph with indent level."""
        result = expand_markdown_content("  Indented text")
        assert result == [("paragraph", "Indented text", 1)]

    def test_dash_without_space_not_bullet(self):
        """'-word' without space after dash is NOT a bullet."""
        result = expand_markdown_content("-not a bullet")
        assert result == [("paragraph", "-not a bullet", 0)]

    def test_asterisk_without_space_not_bullet(self):
        """'*word' without space is NOT a bullet."""
        result = expand_markdown_content("*not a bullet")
        assert result == [("paragraph", "*not a bullet", 0)]

    def test_number_without_dot_not_numbered(self):
        result = expand_markdown_content("1 Not numbered")
        assert result == [("paragraph", "1 Not numbered", 0)]

    def test_empty_string(self):
        result = expand_markdown_content("")
        assert result == [("paragraph", "", 0)]

    def test_only_newlines(self):
        result = expand_markdown_content("\n\n")
        assert result == [
            ("paragraph", "", 0),
            ("paragraph", "", 0),
            ("paragraph", "", 0),
        ]

    def test_mixed_bullet_types(self):
        """Both - and * work as bullets."""
        result = expand_markdown_content("- Dash\n* Star")
        assert result == [
            ("bullet", "Dash", 0),
            ("bullet", "Star", 0),
        ]

    def test_numbered_preserves_text_after_marker(self):
        """Text after '1. ' is preserved exactly."""
        result = expand_markdown_content("1.   Extra spaces")
        # The regex matches \d+\.\s+ so "1.   " is the marker
        assert result == [("numbered", "Extra spaces", 0)]


# =============================================================================
# Integration tests — real document operations via MCP
# =============================================================================


def _get_paragraphs(path: Path) -> list:
    """Open doc and return list of (text, list_info) for each paragraph."""
    pkg = WordPackage.open(str(path))
    body = pkg.body
    result = []
    for p in body.findall(qn("w:p")):
        text_parts = []
        for r in p.findall(f".//{qn('w:t')}"):
            if r.text:
                text_parts.append(r.text)
        text = "".join(text_parts)
        info = get_list_info(pkg, p)
        result.append((text, info))
    return result


@pytest.fixture
def tmp_docx():
    """Provide a temp file path and clean up after."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)
    path.unlink()
    yield path
    path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_replace_with_multi_paragraph(tmp_docx):
    """Replace a paragraph with multi-line content creates multiple paragraphs."""
    # Create doc with one paragraph
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps([{"op": "append", "content_data": "Original text"}]),
        },
    )

    # Read to get block ID
    _, result = await mcp.call_tool(
        "read", {"file_path": str(tmp_docx), "scope": "blocks"}
    )
    blocks = result["blocks"]
    target_id = blocks[0]["id"]

    # Replace with multi-line content
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "replace",
                        "target_id": target_id,
                        "content_data": "First paragraph\nSecond paragraph\nThird paragraph",
                    }
                ]
            ),
        },
    )

    paras = _get_paragraphs(tmp_docx)
    texts = [t for t, _ in paras]
    assert "First paragraph" in texts
    assert "Second paragraph" in texts
    assert "Third paragraph" in texts


@pytest.mark.asyncio
async def test_replace_with_bullet_list(tmp_docx):
    """Replace a paragraph with bullet list content creates list items."""
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps([{"op": "append", "content_data": "To be replaced"}]),
        },
    )

    _, result = await mcp.call_tool(
        "read", {"file_path": str(tmp_docx), "scope": "blocks"}
    )
    blocks = result["blocks"]
    target_id = blocks[0]["id"]

    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "replace",
                        "target_id": target_id,
                        "content_data": "- Apple\n- Banana\n- Cherry",
                    }
                ]
            ),
        },
    )

    paras = _get_paragraphs(tmp_docx)
    # All three should be list items
    for text, info in paras:
        if text in ("Apple", "Banana", "Cherry"):
            assert info is not None, f"'{text}' should be a list item"
            assert info["format_type"] == "bullet"

    # All bullet items should share the same num_id
    num_ids = {info["num_id"] for _, info in paras if info}
    assert len(num_ids) == 1


@pytest.mark.asyncio
async def test_replace_with_mixed_content(tmp_docx):
    """Replace with mixed paragraph + bullet + numbered content."""
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps([{"op": "append", "content_data": "Placeholder"}]),
        },
    )

    _, result = await mcp.call_tool(
        "read", {"file_path": str(tmp_docx), "scope": "blocks"}
    )
    blocks = result["blocks"]
    target_id = blocks[0]["id"]

    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "replace",
                        "target_id": target_id,
                        "content_data": "Intro\n- Bullet A\n- Bullet B\n1. Num one\n2. Num two\nClosing",
                    }
                ]
            ),
        },
    )

    paras = _get_paragraphs(tmp_docx)
    texts = [t for t, _ in paras]
    assert "Intro" in texts
    assert "Bullet A" in texts
    assert "Bullet B" in texts
    assert "Num one" in texts
    assert "Num two" in texts
    assert "Closing" in texts

    # Check list types
    for text, info in paras:
        if text in ("Bullet A", "Bullet B"):
            assert info is not None
            assert info["format_type"] == "bullet"
        elif text in ("Num one", "Num two"):
            assert info is not None
            assert info["format_type"] in ("decimal", "numbered")
        elif text in ("Intro", "Closing"):
            assert info is None  # plain paragraphs

    # Bullets and numbers should have different num_ids
    bullet_ids = {
        info["num_id"] for t, info in paras if info and t in ("Bullet A", "Bullet B")
    }
    num_ids = {
        info["num_id"] for t, info in paras if info and t in ("Num one", "Num two")
    }
    assert bullet_ids.isdisjoint(num_ids)


@pytest.mark.asyncio
async def test_insert_after_with_markdown(tmp_docx):
    """insert_after with markdown content inserts blocks after target."""
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps([{"op": "append", "content_data": "Anchor paragraph"}]),
        },
    )

    _, result = await mcp.call_tool(
        "read", {"file_path": str(tmp_docx), "scope": "blocks"}
    )
    blocks = result["blocks"]
    target_id = blocks[0]["id"]

    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "insert_after",
                        "target_id": target_id,
                        "content_data": "Line A\n- Item 1\n- Item 2",
                    }
                ]
            ),
        },
    )

    paras = _get_paragraphs(tmp_docx)
    texts = [t for t, _ in paras]
    # Anchor should still be first
    assert texts[0] == "Anchor paragraph"
    assert "Line A" in texts
    assert "Item 1" in texts
    assert "Item 2" in texts


@pytest.mark.asyncio
async def test_insert_before_with_markdown(tmp_docx):
    """insert_before with markdown content inserts blocks before target."""
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps([{"op": "append", "content_data": "Anchor paragraph"}]),
        },
    )

    _, result = await mcp.call_tool(
        "read", {"file_path": str(tmp_docx), "scope": "blocks"}
    )
    blocks = result["blocks"]
    target_id = blocks[0]["id"]

    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "insert_before",
                        "target_id": target_id,
                        "content_data": "Before line\n- Bullet before",
                    }
                ]
            ),
        },
    )

    paras = _get_paragraphs(tmp_docx)
    texts = [t for t, _ in paras]
    # Inserted content should come before anchor
    anchor_idx = texts.index("Anchor paragraph")
    before_idx = texts.index("Before line")
    assert before_idx < anchor_idx


@pytest.mark.asyncio
async def test_append_with_markdown(tmp_docx):
    """append with markdown content creates multiple blocks at end."""
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps([{"op": "append", "content_data": "Existing paragraph"}]),
        },
    )

    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "append",
                        "content_data": "Appended first\n- Appended bullet",
                    }
                ]
            ),
        },
    )

    paras = _get_paragraphs(tmp_docx)
    texts = [t for t, _ in paras]
    assert "Existing paragraph" in texts
    assert "Appended first" in texts
    assert "Appended bullet" in texts

    # Bullet should be after appended first
    first_idx = texts.index("Appended first")
    bullet_idx = texts.index("Appended bullet")
    assert bullet_idx > first_idx


@pytest.mark.asyncio
async def test_single_line_replace_unchanged(tmp_docx):
    """Single-line replace (no newline) behaves exactly as before."""
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps([{"op": "append", "content_data": "Original"}]),
        },
    )

    _, result = await mcp.call_tool(
        "read", {"file_path": str(tmp_docx), "scope": "blocks"}
    )
    blocks = result["blocks"]
    target_id = blocks[0]["id"]

    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "replace",
                        "target_id": target_id,
                        "content_data": "Replaced single line",
                    }
                ]
            ),
        },
    )

    paras = _get_paragraphs(tmp_docx)
    texts = [t for t, _ in paras]
    assert "Replaced single line" in texts
    assert len(paras) == 1


@pytest.mark.asyncio
async def test_list_items_share_num_id_within_run(tmp_docx):
    """Consecutive list items of the same type share a single num_id."""
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "append",
                        "content_data": "- Alpha\n- Beta\n- Gamma",
                    }
                ]
            ),
        },
    )

    paras = _get_paragraphs(tmp_docx)
    list_paras = [(t, info) for t, info in paras if info]
    assert len(list_paras) == 3
    num_ids = {info["num_id"] for _, info in list_paras}
    assert len(num_ids) == 1  # all same list


@pytest.mark.asyncio
async def test_separate_list_runs_different_num_ids(tmp_docx):
    """List runs separated by a paragraph get different num_ids."""
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(tmp_docx),
            "ops": json.dumps(
                [
                    {
                        "op": "append",
                        "content_data": "- First list\nBreak paragraph\n- Second list",
                    }
                ]
            ),
        },
    )

    paras = _get_paragraphs(tmp_docx)
    list_paras = [(t, info) for t, info in paras if info]
    assert len(list_paras) == 2
    num_ids = [info["num_id"] for _, info in list_paras]
    assert num_ids[0] != num_ids[1]  # different lists
