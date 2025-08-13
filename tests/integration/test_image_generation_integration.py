"""Integration tests for image generation metadata extraction."""

import os
from pathlib import Path

import pytest

from mcp_handley_lab.llm.gemini.tool import generate_image as gemini_generate_image
from mcp_handley_lab.llm.gemini.tool import mcp as gemini_mcp
from mcp_handley_lab.llm.openai.tool import generate_image as openai_generate_image
from mcp_handley_lab.llm.openai.tool import mcp as openai_mcp
from mcp_handley_lab.shared.models import ImageGenerationResult


class TestOpenAIImageGeneration:
    """Test OpenAI image generation with comprehensive metadata extraction."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_dalle2_basic_metadata(self):
        """Test DALL-E 2 basic metadata extraction."""
        _, response = await openai_mcp.call_tool(
            "generate_image",
            {
                "prompt": "A simple red circle",
                "model": "dall-e-2",
                "size": "512x512",
                "agent_name": "test_dalle2",
            },
        )

        assert "error" not in response, response.get("error")
        result = response

        # Verify core fields
        assert result["message"] == "Image Generated Successfully"
        assert Path(result["file_path"]).exists()
        assert result["file_size_bytes"] > 0
        assert result["agent_name"] == "test_dalle2"

        # Verify usage statistics
        assert result["usage"]["input_tokens"] >= 0
        assert result["usage"]["output_tokens"] == 1  # Images count as 1 output token
        assert result["usage"]["cost"] > 0
        assert result["usage"]["model_used"] == "dall-e-2"

        # Verify OpenAI-specific metadata
        assert result["generation_timestamp"] > 0
        assert result["original_prompt"] == "A simple red circle"
        assert result["requested_size"] == "512x512"
        assert result["mime_type"] == "image/png"
        assert result["original_url"].startswith("https://")
        assert isinstance(result["openai_metadata"], dict)

        # DALL-E 2 doesn't enhance prompts
        assert result["enhanced_prompt"] == ""

    @pytest.mark.live
    def test_dalle3_enhanced_metadata(self):
        """Test DALL-E 3 enhanced metadata extraction including revised prompts."""
        result = openai_generate_image(
            prompt="A futuristic city",
            model="dall-e-3",
            size="1024x1024",
            quality="hd",
            agent_name="test_dalle3",
        )

        # Verify core fields
        assert isinstance(result, ImageGenerationResult)
        assert result.message == "Image Generated Successfully"
        assert Path(result.file_path).exists()
        assert result.file_size_bytes > 0

        # Verify enhanced OpenAI metadata
        assert result.generation_timestamp > 0
        assert result.enhanced_prompt != ""  # DALL-E 3 should enhance prompts
        assert result.original_prompt == "A futuristic city"
        assert result.requested_size == "1024x1024"
        assert result.requested_quality == "hd"
        assert result.requested_format == "png"
        assert result.mime_type == "image/png"
        assert result.original_url.startswith("https://")

        # Verify provider-specific metadata
        assert isinstance(result.openai_metadata, dict)
        assert "background" in result.openai_metadata
        assert "output_format" in result.openai_metadata
        assert "usage" in result.openai_metadata

    @pytest.mark.vcr
    def test_dalle3_standard_quality(self):
        """Test DALL-E 3 with standard quality settings."""
        result = openai_generate_image(
            prompt="A mountain landscape",
            model="dall-e-3",
            size="1024x1792",  # Portrait orientation
            quality="standard",
            agent_name="test_standard",
        )

        # Verify request parameters are correctly captured
        assert result.requested_size == "1024x1792"
        assert result.requested_quality == "standard"
        assert result.enhanced_prompt != result.original_prompt
        assert result.generation_timestamp > 0


class TestGeminiImageGeneration:
    """Test Gemini image generation with comprehensive metadata extraction."""

    @pytest.mark.vcr
    def test_imagen3_basic_metadata(self):
        """Test Imagen 3 basic metadata extraction."""
        result = gemini_generate_image(
            prompt="A peaceful garden",
            model="imagen-3.0-generate-002",
            agent_name="test_imagen3",
        )

        # Verify core fields
        assert isinstance(result, ImageGenerationResult)
        assert result.message == "Image Generated Successfully"
        assert Path(result.file_path).exists()
        assert result.file_size_bytes > 0
        assert result.agent_name == "test_imagen3"

        # Verify usage statistics
        assert result.usage.input_tokens > 0  # Gemini estimates tokens
        assert result.usage.output_tokens == 1
        assert result.usage.cost > 0
        assert result.usage.model_used == "imagen-3.0-generate-002"

        # Verify Gemini-specific metadata
        assert result.original_prompt == "A peaceful garden"
        assert result.aspect_ratio == "1:1"  # Default aspect ratio
        assert result.requested_format == "png"
        assert result.mime_type == "image/png"

        # Verify safety and filtering information
        assert isinstance(result.safety_attributes, dict)
        assert isinstance(result.gemini_metadata, dict)

        # Check provider-specific metadata
        assert "actual_model_used" in result.gemini_metadata
        assert "requested_model" in result.gemini_metadata
        assert result.gemini_metadata["requested_model"] == "imagen-3.0-generate-002"

    @pytest.mark.vcr
    def test_imagen3_safety_attributes(self):
        """Test Imagen 3 safety attributes extraction."""
        result = gemini_generate_image(
            prompt="A safe, family-friendly cartoon character",
            model="imagen-3.0-generate-002",
            agent_name="test_safety",
        )

        # Verify safety-related metadata
        assert isinstance(result.safety_attributes, dict)
        assert "categories" in result.safety_attributes
        assert "scores" in result.safety_attributes
        assert "content_type" in result.safety_attributes

        # Content should not be filtered for safe prompts
        assert result.content_filter_reason == ""

        # Check for positive safety attributes in metadata
        assert "positive_prompt_safety_attributes" in result.gemini_metadata

    @pytest.mark.vcr
    def test_imagen4_model_mapping(self):
        """Test Imagen 4 model mapping and metadata."""
        result = gemini_generate_image(
            prompt="A modern abstract art piece",
            model="imagen-4.0-generate-preview-06-06",
            agent_name="test_imagen4",
        )

        # Verify model mapping is working
        assert result.usage.model_used == "imagen-4.0-generate-preview-06-06"
        assert (
            result.gemini_metadata["requested_model"]
            == "imagen-4.0-generate-preview-06-06"
        )
        assert "imagen-4" in result.gemini_metadata["actual_model_used"]

        # Verify core metadata
        assert result.original_prompt == "A modern abstract art piece"
        assert result.mime_type == "image/png"


class TestImageGenerationComparison:
    """Test comparing metadata across providers."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_metadata_structure_consistency(self):
        """Test that both providers return consistent metadata structure."""
        prompt = "A simple test image"

        _, openai_response = await openai_mcp.call_tool(
            "generate_image",
            {
                "prompt": prompt,
                "model": "dall-e-2",
                "size": "512x512",
                "agent_name": "consistency_test",
            },
        )
        assert "error" not in openai_response, openai_response.get("error")
        openai_result = openai_response

        _, gemini_response = await gemini_mcp.call_tool(
            "generate_image",
            {
                "prompt": prompt,
                "model": "imagen-3.0-generate-002",
                "agent_name": "consistency_test",
            },
        )
        assert "error" not in gemini_response, gemini_response.get("error")
        gemini_result = gemini_response

        # Both should have the same core structure
        for result in [openai_result, gemini_result]:
            assert "message" in result
            assert "file_path" in result
            assert "file_size_bytes" in result
            assert "usage" in result
            assert "agent_name" in result
            assert "generation_timestamp" in result
            assert "enhanced_prompt" in result
            assert "original_prompt" in result
            assert "safety_attributes" in result
            assert "openai_metadata" in result
            assert "gemini_metadata" in result

        # Verify provider-specific metadata is in correct containers
        assert len(openai_result["openai_metadata"]) > 0
        assert len(openai_result["gemini_metadata"]) == 0
        assert len(gemini_result["gemini_metadata"]) > 0
        assert len(gemini_result["openai_metadata"]) == 0

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_prompt_enhancement_differences(self):
        """Test how different providers handle prompt enhancement."""
        prompt = "A cat wearing a hat"

        _, openai_response = await openai_mcp.call_tool(
            "generate_image",
            {
                "prompt": prompt,
                "model": "dall-e-3",  # DALL-E 3 enhances prompts
                "size": "1024x1024",
                "agent_name": "enhancement_test",
            },
        )
        assert "error" not in openai_response, openai_response.get("error")
        openai_result = openai_response

        _, gemini_response = await gemini_mcp.call_tool(
            "generate_image",
            {
                "prompt": prompt,
                "model": "imagen-3.0-generate-002",
                "agent_name": "enhancement_test",
            },
        )
        assert "error" not in gemini_response, gemini_response.get("error")
        gemini_result = gemini_response

        # Both should preserve original prompt
        assert openai_result["original_prompt"] == prompt
        assert gemini_result["original_prompt"] == prompt

        # DALL-E 3 should enhance prompts significantly
        assert openai_result["enhanced_prompt"] != ""
        assert len(openai_result["enhanced_prompt"]) > len(prompt)

        # Gemini may or may not enhance prompts
        assert isinstance(gemini_result["enhanced_prompt"], str)


class TestImageGenerationErrorHandling:
    """Test error handling in image generation."""

    @pytest.mark.asyncio
    async def test_empty_prompt_openai(self):
        """Test OpenAI image generation with empty prompt."""
        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="Prompt is required and cannot be empty"):
            await openai_mcp.call_tool("generate_image", {"prompt": ""})

    @pytest.mark.asyncio
    async def test_empty_prompt_gemini(self):
        """Test Gemini image generation with empty prompt."""
        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="Prompt is required and cannot be empty"):
            await gemini_mcp.call_tool("generate_image", {"prompt": ""})

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_invalid_size_openai(self):
        """Test OpenAI with invalid size parameter."""
        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(ToolError):  # MCP wraps API errors in ToolError
            await openai_mcp.call_tool(
                "generate_image",
                {
                    "prompt": "Test",
                    "model": "dall-e-3",
                    "size": "100x100",  # Invalid size
                    "agent_name": "error_test",
                },
            )


if __name__ == "__main__":
    # Run basic smoke test
    if os.getenv("OPENAI_API_KEY"):
        print("Testing OpenAI...")
        result = openai_generate_image(
            "Test", model="dall-e-2", size="512x512", agent_name="smoke"
        )
        print(f"✅ Generated: {result.file_path}")

    if os.getenv("GEMINI_API_KEY"):
        print("Testing Gemini...")
        result = gemini_generate_image("Test", model="imagen-3", agent_name="smoke")
        print(f"✅ Generated: {result.file_path}")
