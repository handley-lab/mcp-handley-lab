"""Integration tests for Mistral LLM tools with real API calls."""

import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.llm.chat.tool import mcp
from mcp_handley_lab.llm.ocr.tool import mcp as ocr_mcp


@pytest.fixture
def skip_if_no_api_key(monkeypatch):
    """Skip test if MISTRAL_API_KEY is not set."""
    import os

    if not os.getenv("MISTRAL_API_KEY"):
        pytest.skip("MISTRAL_API_KEY not set")


@pytest.fixture
def test_output_file():
    """Create a temporary output file for test results."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_mistral_ask_simple(skip_if_no_api_key, test_output_file):
    """Test basic text generation with Mistral."""
    _, response = await mcp.call_tool(
        "ask",
        {
            "prompt": "What is 2+2? Answer with just the number.",
            "output_file": test_output_file,
            "agent_name": "",
            "model": "mistral-small-latest",
        },
    )

    assert "error" not in str(response).lower()
    assert response["content"]
    assert "usage" in response

    # Check output file was created
    output_content = Path(test_output_file).read_text()
    assert "4" in output_content


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_mistral_ask_with_files(skip_if_no_api_key, test_output_file):
    """Test text generation with file input."""
    # Create a temporary test file
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt"
    ) as test_file:
        test_file.write("Test document content: The answer is 42")
        test_file_path = test_file.name

    try:
        _, response = await mcp.call_tool(
            "ask",
            {
                "prompt": "What number is mentioned in the file?",
                "output_file": test_output_file,
                "agent_name": "",
                "model": "mistral-small-latest",
                "files": [test_file_path],
            },
        )

        assert "error" not in str(response).lower()
        assert response["content"]

        # Check response mentions the number
        output_content = Path(test_output_file).read_text()
        assert "42" in output_content

    finally:
        Path(test_file_path).unlink(missing_ok=True)


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_mistral_analyze_image(skip_if_no_api_key, test_output_file):
    """Test image analysis with Pixtral vision model."""
    # Create a simple test image
    from PIL import Image

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as image_file:
        # Create a simple red square image
        img = Image.new("RGB", (100, 100), color="red")
        img.save(image_file.name)
        image_path = image_file.name

    try:
        _, response = await mcp.call_tool(
            "analyze_image",
            {
                "prompt": "What color is this image?",
                "output_file": test_output_file,
                "images": [image_path],
                "model": "pixtral-12b-2409",
                "agent_name": "",
            },
        )

        assert "error" not in str(response).lower()
        assert response["content"]

        # Check response describes the image (any meaningful content)
        output_content = Path(test_output_file).read_text()
        assert len(output_content) > 10  # Got a meaningful response

    finally:
        Path(image_path).unlink(missing_ok=True)


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_mistral_process_ocr_image(skip_if_no_api_key, test_output_file):
    """Test OCR processing with image input."""
    # Create a simple test image with text
    from PIL import Image, ImageDraw

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as image_file:
        # Create image with text
        img = Image.new("RGB", (400, 100), color="white")
        draw = ImageDraw.Draw(img)
        # Use default font
        draw.text((10, 40), "Hello OCR Test 123", fill="black")
        img.save(image_file.name)
        image_path = image_file.name

    try:
        _, response = await ocr_mcp.call_tool(
            "process",
            {
                "document_path": image_path,
                "output_file": test_output_file,
                "include_images": False,
            },
        )

        assert "error" not in str(response).lower()
        assert "pages" in response
        assert response["status"] == "success"

    finally:
        Path(image_path).unlink(missing_ok=True)


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_mistral_ask_with_memory(skip_if_no_api_key, test_output_file):
    """Test conversation memory with agent_name."""
    # First message
    _, response1 = await mcp.call_tool(
        "ask",
        {
            "prompt": "Remember this number: 777. Just confirm you remember it.",
            "output_file": test_output_file,
            "agent_name": "test_memory_agent",
            "model": "mistral-small-latest",
        },
    )

    assert "error" not in str(response1).lower()

    # Second message - should remember
    _, response2 = await mcp.call_tool(
        "ask",
        {
            "prompt": "What number did I ask you to remember?",
            "output_file": test_output_file,
            "agent_name": "test_memory_agent",
            "model": "mistral-small-latest",
        },
    )

    assert "error" not in str(response2).lower()
    output_content = Path(test_output_file).read_text()
    assert "777" in output_content


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_mistral_ask_different_models(skip_if_no_api_key, test_output_file):
    """Test with different Mistral models."""
    models_to_test = [
        "mistral-small-latest",
        "mistral-large-latest",
        "pixtral-large-latest",
    ]

    for model in models_to_test:
        _, response = await mcp.call_tool(
            "ask",
            {
                "prompt": "Say 'hello' in one word.",
                "output_file": test_output_file,
                "agent_name": "",
                "model": model,
            },
        )

        assert "error" not in str(response).lower(), f"Failed for model: {model}"
        assert response["content"], f"No content for model: {model}"
