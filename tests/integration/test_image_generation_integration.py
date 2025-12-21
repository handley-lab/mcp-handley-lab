"""Integration tests for image generation functionality via MCP protocol.

VCR cassettes enable these tests to run without real API keys.
The dummy API keys fixture in conftest.py allows the code to proceed
to HTTP calls, where VCR intercepts and replays recorded responses.
"""

import os
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcp_handley_lab.llm.image.tool import mcp


class TestOpenAIImageGeneration:
    """Test OpenAI image generation functionality via MCP protocol."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_dalle3_basic_generation(self):
        """Test DALL-E 3 basic image generation."""
        _, result = await mcp.call_tool(
            "generate",
            {
                "prompt": "A simple red circle",
                "model": "dall-e-3",
                "quality": "standard",
                "size": "1024x1024",
            },
        )

        # Verify core fields
        assert Path(result["file_path"]).exists()
        assert result["file_size_bytes"] > 0
        assert result["model"] == "dall-e-3"
        assert result["provider"] == "openai"
        assert result["original_prompt"] == "A simple red circle"
        assert result["cost"] > 0

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_dalle3_enhanced_prompt(self):
        """Test DALL-E 3 prompt enhancement."""
        _, result = await mcp.call_tool(
            "generate",
            {
                "prompt": "A futuristic city",
                "model": "dall-e-3",
                "quality": "hd",
                "size": "1024x1024",
            },
        )

        # Verify core fields
        assert Path(result["file_path"]).exists()
        assert result["file_size_bytes"] > 0
        assert result["original_prompt"] == "A futuristic city"

        # DALL-E 3 enhances prompts
        assert result["enhanced_prompt"] != ""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_dalle3_portrait_size(self):
        """Test DALL-E 3 with portrait orientation."""
        _, result = await mcp.call_tool(
            "generate",
            {
                "prompt": "A mountain landscape",
                "model": "dall-e-3",
                "size": "1024x1792",  # Portrait orientation
                "quality": "standard",
            },
        )

        # Verify image was generated
        assert Path(result["file_path"]).exists()
        assert result["file_size_bytes"] > 0
        assert result["provider"] == "openai"


class TestGeminiImageGeneration:
    """Test Gemini image generation functionality via MCP protocol."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_imagen3_basic_generation(self):
        """Test Imagen 3 basic image generation."""
        _, result = await mcp.call_tool(
            "generate",
            {
                "prompt": "A peaceful garden",
                "model": "imagen-4.0-generate-001",
            },
        )

        # Verify core fields
        assert Path(result["file_path"]).exists()
        assert result["file_size_bytes"] > 0
        assert result["model"] == "imagen-4.0-generate-001"
        assert result["provider"] == "gemini"
        assert result["original_prompt"] == "A peaceful garden"
        assert result["cost"] >= 0

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_imagen3_with_aspect_ratio(self):
        """Test Imagen 3 with custom aspect ratio."""
        _, result = await mcp.call_tool(
            "generate",
            {
                "prompt": "A safe, family-friendly cartoon character",
                "model": "imagen-4.0-generate-001",
                "aspect_ratio": "16:9",
            },
        )

        # Verify image was generated
        assert Path(result["file_path"]).exists()
        assert result["file_size_bytes"] > 0
        assert result["provider"] == "gemini"

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_imagen_model_variants(self):
        """Test different Imagen model variants."""
        _, result = await mcp.call_tool(
            "generate",
            {
                "prompt": "A modern abstract art piece",
                "model": "imagen-4.0-generate-001",
            },
        )

        # Verify model is correctly used
        assert result["model"] == "imagen-4.0-generate-001"
        assert result["original_prompt"] == "A modern abstract art piece"
        assert result["provider"] == "gemini"


class TestImageGenerationComparison:
    """Test comparing functionality across providers via MCP protocol."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_response_structure_consistency(self):
        """Test that both providers return consistent response structure."""
        prompt = "A simple test image"

        _, openai_result = await mcp.call_tool(
            "generate",
            {
                "prompt": prompt,
                "model": "dall-e-3",
                "size": "1024x1024",
                "quality": "standard",
            },
        )

        _, gemini_result = await mcp.call_tool(
            "generate",
            {
                "prompt": prompt,
                "model": "imagen-4.0-generate-001",
            },
        )

        # Both should have the same core structure
        for result in [openai_result, gemini_result]:
            assert "file_path" in result
            assert "file_size_bytes" in result
            assert "model" in result
            assert "provider" in result
            assert "cost" in result
            assert "original_prompt" in result
            assert "enhanced_prompt" in result

        # Verify correct providers
        assert openai_result["provider"] == "openai"
        assert gemini_result["provider"] == "gemini"

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_prompt_enhancement_differences(self):
        """Test how different providers handle prompt enhancement."""
        prompt = "A cat wearing a hat"

        _, openai_result = await mcp.call_tool(
            "generate",
            {
                "prompt": prompt,
                "model": "dall-e-3",
                "size": "1024x1024",
                "quality": "standard",
            },
        )

        _, gemini_result = await mcp.call_tool(
            "generate",
            {
                "prompt": prompt,
                "model": "imagen-4.0-generate-001",
            },
        )

        # Both should preserve original prompt
        assert openai_result["original_prompt"] == prompt
        assert gemini_result["original_prompt"] == prompt

        # DALL-E 3 should enhance prompts significantly
        assert openai_result["enhanced_prompt"] != ""
        assert len(openai_result["enhanced_prompt"]) > len(prompt)

        # Gemini may or may not enhance prompts
        assert isinstance(gemini_result["enhanced_prompt"], str)


class TestImageGenerationErrorHandling:
    """Test error handling in image generation via MCP protocol."""

    @pytest.mark.asyncio
    async def test_empty_prompt(self):
        """Test image generation with empty prompt."""
        with pytest.raises(ToolError, match="Prompt is required and cannot be empty"):
            await mcp.call_tool("generate", {"prompt": ""})

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_invalid_size_openai(self):
        """Test OpenAI with invalid size parameter."""
        with pytest.raises(ToolError):
            await mcp.call_tool(
                "generate",
                {
                    "prompt": "Test",
                    "model": "dall-e-3",
                    "size": "100x100",  # Invalid size
                    "quality": "standard",
                },
            )


if __name__ == "__main__":
    import asyncio

    async def main():
        # Run basic smoke test
        if os.getenv("OPENAI_API_KEY"):
            print("Testing OpenAI...")
            _, result = await mcp.call_tool(
                "generate",
                {"prompt": "Test", "model": "dall-e-3", "size": "1024x1024"},
            )
            print(f"Generated: {result['file_path']}")

        if os.getenv("GEMINI_API_KEY"):
            print("Testing Gemini...")
            _, result = await mcp.call_tool(
                "generate",
                {"prompt": "Test", "model": "imagen-4.0-generate-001"},
            )
            print(f"Generated: {result['file_path']}")

    asyncio.run(main())
