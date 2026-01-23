"""Tests for Word document visual rendering."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.microsoft.word.ops.render import render_to_images, render_to_pdf
from mcp_handley_lab.microsoft.word.tool import mcp


def _ops(operations: list[dict]) -> str:
    """Helper to convert operation list to ops JSON string."""
    return json.dumps(operations)


# Check for required binaries
has_libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
has_pdftoppm = shutil.which("pdftoppm")

# Markers for different test types
requires_libreoffice = pytest.mark.skipif(
    not has_libreoffice, reason="libreoffice/soffice not installed"
)
requires_pdftoppm = pytest.mark.skipif(
    not has_pdftoppm, reason="pdftoppm not installed"
)


@pytest.fixture
async def sample_docx():
    """Create a simple Word document for testing using MCP tool."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)

    # Create document with initial empty paragraph
    await mcp.call_tool("create", {"file_path": str(path)})
    # Append content
    await mcp.call_tool(
        "edit",
        {
            "file_path": str(path),
            "ops": _ops(
                [
                    {
                        "op": "append",
                        "content_type": "paragraph",
                        "content_data": "Test content for rendering",
                    }
                ]
            ),
        },
    )
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
async def multi_page_docx():
    """Create a multi-page Word document for testing using MCP tool."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)

    # Create document with initial empty paragraph
    await mcp.call_tool("create", {"file_path": str(path)})

    # Add first heading and all page breaks with content in a single batch
    ops = [
        {
            "op": "append",
            "content_type": "heading",
            "content_data": "Page 1 Content",
            "heading_level": 1,
        }
    ]
    for i in range(2, 6):
        ops.append({"op": "add_page_break"})
        ops.append(
            {
                "op": "append",
                "content_type": "heading",
                "content_data": f"Page {i} Content",
                "heading_level": 1,
            }
        )

    await mcp.call_tool("edit", {"file_path": str(path), "ops": _ops(ops)})

    yield path
    path.unlink(missing_ok=True)


# PNG rendering tests - require both libreoffice and pdftoppm
@requires_libreoffice
@requires_pdftoppm
@pytest.mark.asyncio
async def test_render_single_page(sample_docx):
    """Test rendering a single page returns valid PNG."""
    result = render_to_images(str(sample_docx), pages=[1])
    assert len(result) == 1
    page_num, png_bytes = result[0]
    assert page_num == 1
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


@requires_libreoffice
@requires_pdftoppm
@pytest.mark.asyncio
async def test_render_returns_correct_page_numbers(multi_page_docx):
    """Verify page labels match actual pages for non-contiguous requests."""
    result = render_to_images(str(multi_page_docx), pages=[1, 3])
    assert len(result) == 2
    assert result[0][0] == 1
    assert result[1][0] == 3


@requires_libreoffice
@requires_pdftoppm
@pytest.mark.asyncio
async def test_render_empty_pages_error(sample_docx):
    """Test that empty pages list raises an error."""
    with pytest.raises(ValueError, match="required"):
        render_to_images(str(sample_docx), pages=[])


@requires_libreoffice
@requires_pdftoppm
@pytest.mark.asyncio
async def test_render_max_pages_error(multi_page_docx):
    """Test that >5 pages raises an error."""
    with pytest.raises(ValueError, match="max 5 pages"):
        render_to_images(str(multi_page_docx), pages=[1, 2, 3, 4, 5, 6])


@requires_libreoffice
@requires_pdftoppm
@pytest.mark.asyncio
async def test_render_dedup_and_sort(multi_page_docx):
    """Test that duplicate pages are deduped and sorted."""
    result = render_to_images(str(multi_page_docx), pages=[3, 1, 1, 2])
    page_nums = [r[0] for r in result]
    assert page_nums == [1, 2, 3]


@requires_libreoffice
@requires_pdftoppm
@pytest.mark.asyncio
async def test_render_page_images_differ(multi_page_docx):
    """Test that different pages produce different images."""
    result = render_to_images(str(multi_page_docx), pages=[1, 2])
    assert len(result) == 2
    page1_bytes = result[0][1]
    page2_bytes = result[1][1]
    # Pages have different content, so PNG bytes should differ
    assert page1_bytes != page2_bytes


@requires_libreoffice
@requires_pdftoppm
@pytest.mark.asyncio
async def test_render_missing_page_error(sample_docx):
    """Test that requesting a non-existent page raises CalledProcessError."""
    import subprocess

    # sample_docx has only 1 page - pdftoppm errors on out-of-range pages
    with pytest.raises(subprocess.CalledProcessError):
        render_to_images(str(sample_docx), pages=[999])


# PDF rendering tests - only require libreoffice
@requires_libreoffice
@pytest.mark.asyncio
async def test_render_to_pdf(sample_docx):
    """Test rendering to PDF returns valid PDF bytes."""
    pdf_bytes = render_to_pdf(str(sample_docx))
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 100


# MCP tool tests
@requires_libreoffice
@requires_pdftoppm
@pytest.mark.asyncio
async def test_mcp_render_png_output(sample_docx):
    """Test MCP render tool with PNG output."""
    import base64

    result = await mcp.call_tool(
        "render",
        {"file_path": str(sample_docx), "pages": [1], "output": "png"},
    )
    # Returns list of TextContent and Image objects
    assert len(result) == 2
    assert result[0].text == "Page 1:"
    # MCP Image returns base64-encoded data
    png_bytes = base64.b64decode(result[1].data)
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


@requires_libreoffice
@pytest.mark.asyncio
async def test_mcp_render_pdf_output(sample_docx):
    """Test MCP render tool with PDF output."""
    import base64

    result = await mcp.call_tool(
        "render",
        {"file_path": str(sample_docx), "output": "pdf"},
    )
    # Returns list with TextContent label and Image (PDF bytes)
    assert len(result) == 2
    assert "PDF" in result[0].text
    assert "bytes" in result[0].text
    # MCP Image returns base64-encoded data
    pdf_bytes = base64.b64decode(result[1].data)
    assert pdf_bytes[:4] == b"%PDF"
