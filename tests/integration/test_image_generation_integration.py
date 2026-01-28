"""Integration tests for image generation functionality via MCP protocol.

VCR cassettes enable these tests to run without real API keys.
The dummy API keys fixture in conftest.py allows the code to proceed
to HTTP calls, where VCR intercepts and replays recorded responses.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcp_handley_lab.llm.tool import mcp


def parse_image_result(result) -> tuple[dict, any]:
    """Parse generate_image result into metadata dict and image.

    FastMCP returns [TextContent(JSON metadata), Image(preview)] directly
    when a function returns content objects.

    Returns (metadata_dict, image_object).
    """
    assert isinstance(result, list), f"Expected list, got {type(result)}"
    assert len(result) == 2, f"Expected 2 elements, got {len(result)}"
    # First element is TextContent with JSON metadata
    metadata = json.loads(result[0].text)
    # Second element is Image
    image = result[1]
    return metadata, image


@pytest.fixture
def test_image_file():
    """Create a temporary file path for generated images."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


class TestOpenAIImageGeneration:
    """Test OpenAI image generation functionality via MCP protocol."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_dalle3_basic_generation(self, test_image_file):
        """Test DALL-E 3 basic image generation."""
        # FastMCP returns list directly when function returns content objects
        result = await mcp.call_tool(
            "generate_image",
            {
                "prompt": "A simple red circle",
                "model": "dall-e-3",
                "quality": "standard",
                "size": "1024x1024",
                "output_file": test_image_file,
            },
        )

        # Parse metadata from [TextContent, Image] result
        metadata, image = parse_image_result(result)

        # Verify core fields
        assert Path(metadata["file_path"]).exists()
        assert metadata["file_size_bytes"] > 0
        assert metadata["model"] == "dall-e-3"
        assert metadata["provider"] == "openai"
        assert metadata["original_prompt"] == "A simple red circle"
        assert metadata["cost"] > 0
        assert metadata["detected_format"] in ("png", "jpeg")

        # Verify Image content present (ImageContent has data and mimeType)
        assert hasattr(image, "data")
        assert hasattr(image, "mimeType") or hasattr(image, "format")

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_dalle3_enhanced_prompt(self, test_image_file):
        """Test DALL-E 3 prompt enhancement."""
        result = await mcp.call_tool(
            "generate_image",
            {
                "prompt": "A futuristic city",
                "model": "dall-e-3",
                "quality": "hd",
                "size": "1024x1024",
                "output_file": test_image_file,
            },
        )

        # Parse metadata from [TextContent, Image] result
        metadata, _ = parse_image_result(result)

        # Verify core fields
        assert Path(metadata["file_path"]).exists()
        assert metadata["file_size_bytes"] > 0
        assert metadata["original_prompt"] == "A futuristic city"

        # DALL-E 3 enhances prompts
        assert metadata["enhanced_prompt"] != ""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_dalle3_portrait_size(self, test_image_file):
        """Test DALL-E 3 with portrait orientation."""
        result = await mcp.call_tool(
            "generate_image",
            {
                "prompt": "A mountain landscape",
                "model": "dall-e-3",
                "size": "1024x1792",  # Portrait orientation
                "quality": "standard",
                "output_file": test_image_file,
            },
        )

        # Parse metadata from [TextContent, Image] result
        metadata, _ = parse_image_result(result)

        # Verify image was generated
        assert Path(metadata["file_path"]).exists()
        assert metadata["file_size_bytes"] > 0
        assert metadata["provider"] == "openai"


class TestGeminiImageGeneration:
    """Test Gemini image generation functionality via MCP protocol."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_imagen3_basic_generation(self, test_image_file):
        """Test Imagen 3 basic image generation."""
        result = await mcp.call_tool(
            "generate_image",
            {
                "prompt": "A peaceful garden",
                "model": "imagen-4.0-generate-001",
                "output_file": test_image_file,
            },
        )

        # Parse metadata from [TextContent, Image] result
        metadata, _ = parse_image_result(result)

        # Verify core fields
        assert Path(metadata["file_path"]).exists()
        assert metadata["file_size_bytes"] > 0
        assert metadata["model"] == "imagen-4.0-generate-001"
        assert metadata["provider"] == "gemini"
        assert metadata["original_prompt"] == "A peaceful garden"
        assert metadata["cost"] >= 0

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_imagen3_with_aspect_ratio(self, test_image_file):
        """Test Imagen 3 with custom aspect ratio."""
        result = await mcp.call_tool(
            "generate_image",
            {
                "prompt": "A safe, family-friendly cartoon character",
                "model": "imagen-4.0-generate-001",
                "aspect_ratio": "16:9",
                "output_file": test_image_file,
            },
        )

        # Parse metadata from [TextContent, Image] result
        metadata, _ = parse_image_result(result)

        # Verify image was generated
        assert Path(metadata["file_path"]).exists()
        assert metadata["file_size_bytes"] > 0
        assert metadata["provider"] == "gemini"

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_imagen_model_variants(self, test_image_file):
        """Test different Imagen model variants."""
        result = await mcp.call_tool(
            "generate_image",
            {
                "prompt": "A modern abstract art piece",
                "model": "imagen-4.0-generate-001",
                "output_file": test_image_file,
            },
        )

        # Parse metadata from [TextContent, Image] result
        metadata, _ = parse_image_result(result)

        # Verify model is correctly used
        assert metadata["model"] == "imagen-4.0-generate-001"
        assert metadata["original_prompt"] == "A modern abstract art piece"
        assert metadata["provider"] == "gemini"


class TestImageGenerationComparison:
    """Test comparing functionality across providers via MCP protocol."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_response_structure_consistency(self):
        """Test that both providers return consistent response structure."""
        prompt = "A simple test image"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f1:
            openai_file = f1.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f2:
            gemini_file = f2.name

        try:
            openai_result = await mcp.call_tool(
                "generate_image",
                {
                    "prompt": prompt,
                    "model": "dall-e-3",
                    "size": "1024x1024",
                    "quality": "standard",
                    "output_file": openai_file,
                },
            )

            gemini_result = await mcp.call_tool(
                "generate_image",
                {
                    "prompt": prompt,
                    "model": "imagen-4.0-generate-001",
                    "output_file": gemini_file,
                },
            )

            # Parse metadata from [TextContent, Image] results
            openai_metadata, _ = parse_image_result(openai_result)
            gemini_metadata, _ = parse_image_result(gemini_result)

            # Both should have the same core structure
            for metadata in [openai_metadata, gemini_metadata]:
                assert "file_path" in metadata
                assert "file_size_bytes" in metadata
                assert "model" in metadata
                assert "provider" in metadata
                assert "cost" in metadata
                assert "original_prompt" in metadata
                assert "enhanced_prompt" in metadata
                assert "detected_format" in metadata

            # Verify correct providers
            assert openai_metadata["provider"] == "openai"
            assert gemini_metadata["provider"] == "gemini"
        finally:
            Path(openai_file).unlink(missing_ok=True)
            Path(gemini_file).unlink(missing_ok=True)

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_prompt_enhancement_differences(self):
        """Test how different providers handle prompt enhancement."""
        prompt = "A cat wearing a hat"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f1:
            openai_file = f1.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f2:
            gemini_file = f2.name

        try:
            openai_result = await mcp.call_tool(
                "generate_image",
                {
                    "prompt": prompt,
                    "model": "dall-e-3",
                    "size": "1024x1024",
                    "quality": "standard",
                    "output_file": openai_file,
                },
            )

            gemini_result = await mcp.call_tool(
                "generate_image",
                {
                    "prompt": prompt,
                    "model": "imagen-4.0-generate-001",
                    "output_file": gemini_file,
                },
            )

            # Parse metadata from [TextContent, Image] results
            openai_metadata, _ = parse_image_result(openai_result)
            gemini_metadata, _ = parse_image_result(gemini_result)

            # Both should preserve original prompt
            assert openai_metadata["original_prompt"] == prompt
            assert gemini_metadata["original_prompt"] == prompt

            # DALL-E 3 should enhance prompts significantly
            assert openai_metadata["enhanced_prompt"] != ""
            assert len(openai_metadata["enhanced_prompt"]) > len(prompt)

            # Gemini may or may not enhance prompts
            assert isinstance(gemini_metadata["enhanced_prompt"], str)
        finally:
            Path(openai_file).unlink(missing_ok=True)
            Path(gemini_file).unlink(missing_ok=True)


class TestImageGenerationErrorHandling:
    """Test error handling in image generation via MCP protocol."""

    @pytest.mark.asyncio
    async def test_empty_prompt(self, test_image_file):
        """Test image generation with empty prompt."""
        with pytest.raises(
            ToolError, match="Provide exactly one of 'prompt' or 'prompt_file'"
        ):
            await mcp.call_tool(
                "generate_image", {"prompt": "", "output_file": test_image_file}
            )

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_invalid_size_openai(self, test_image_file):
        """Test OpenAI with invalid size parameter."""
        with pytest.raises(ToolError):
            await mcp.call_tool(
                "generate_image",
                {
                    "prompt": "Test",
                    "model": "dall-e-3",
                    "size": "100x100",  # Invalid size
                    "quality": "standard",
                    "output_file": test_image_file,
                },
            )


if __name__ == "__main__":
    import asyncio

    async def main():
        # Run basic smoke test
        if os.getenv("OPENAI_API_KEY"):
            print("Testing OpenAI...")
            result = await mcp.call_tool(
                "generate_image",
                {
                    "prompt": "Test",
                    "model": "dall-e-3",
                    "size": "1024x1024",
                    "output_file": "/tmp/test_openai.png",
                },
            )
            metadata, _ = parse_image_result(result)
            print(f"Generated: {metadata['file_path']}")

        if os.getenv("GEMINI_API_KEY"):
            print("Testing Gemini...")
            result = await mcp.call_tool(
                "generate_image",
                {
                    "prompt": "Test",
                    "model": "imagen-4.0-generate-001",
                    "output_file": "/tmp/test_gemini.png",
                },
            )
            metadata, _ = parse_image_result(result)
            print(f"Generated: {metadata['file_path']}")

    asyncio.run(main())
