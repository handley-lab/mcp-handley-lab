"""Unit tests for image generation metadata extraction."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_handley_lab.llm.shared import process_image_generation
from mcp_handley_lab.shared.models import ImageGenerationResult, UsageStats


class TestImageGenerationMetadata:
    """Test image generation metadata handling."""

    def test_image_generation_result_model(self):
        """Test ImageGenerationResult model with all fields."""
        usage = UsageStats(
            input_tokens=10, output_tokens=1, cost=0.04, model_used="test-model"
        )

        result = ImageGenerationResult(
            message="Test Image Generated",
            file_path="/tmp/test.png",
            file_size_bytes=1024,
            usage=usage,
            agent_name="test_agent",
            generation_timestamp=1234567890,
            enhanced_prompt="Enhanced test prompt with details",
            original_prompt="Test prompt",
            requested_size="1024x1024",
            requested_quality="hd",
            requested_format="png",
            aspect_ratio="1:1",
            safety_attributes={"safe": True},
            content_filter_reason="",
            openai_metadata={"provider": "openai"},
            gemini_metadata={},
            mime_type="image/png",
            cloud_uri="gs://bucket/image.png",
            original_url="https://example.com/image.png",
        )

        # Verify all fields are properly set
        assert result.message == "Test Image Generated"
        assert result.file_path == "/tmp/test.png"
        assert result.file_size_bytes == 1024
        assert result.usage == usage
        assert result.agent_name == "test_agent"
        assert result.generation_timestamp == 1234567890
        assert result.enhanced_prompt == "Enhanced test prompt with details"
        assert result.original_prompt == "Test prompt"
        assert result.requested_size == "1024x1024"
        assert result.requested_quality == "hd"
        assert result.requested_format == "png"
        assert result.aspect_ratio == "1:1"
        assert result.safety_attributes == {"safe": True}
        assert result.content_filter_reason == ""
        assert result.openai_metadata == {"provider": "openai"}
        assert result.gemini_metadata == {}
        assert result.mime_type == "image/png"
        assert result.cloud_uri == "gs://bucket/image.png"
        assert result.original_url == "https://example.com/image.png"

    def test_image_generation_result_defaults(self):
        """Test ImageGenerationResult with only required fields."""
        usage = UsageStats(
            input_tokens=10, output_tokens=1, cost=0.04, model_used="test-model"
        )

        result = ImageGenerationResult(
            message="Test", file_path="/tmp/test.png", file_size_bytes=1024, usage=usage
        )

        # Verify defaults are set correctly
        assert result.agent_name == ""
        assert result.generation_timestamp == 0
        assert result.enhanced_prompt == ""
        assert result.original_prompt == ""
        assert result.requested_size == ""
        assert result.requested_quality == ""
        assert result.requested_format == ""
        assert result.aspect_ratio == ""
        assert result.safety_attributes == {}
        assert result.content_filter_reason == ""
        assert result.openai_metadata == {}
        assert result.gemini_metadata == {}
        assert result.mime_type == ""
        assert result.cloud_uri == ""
        assert result.original_url == ""

    @patch("mcp_handley_lab.llm.shared.calculate_cost")
    @patch("mcp_handley_lab.llm.shared.handle_agent_memory")
    def test_process_image_generation_metadata_passthrough(
        self, mock_memory, mock_cost
    ):
        """Test that process_image_generation passes through metadata correctly."""
        mock_cost.return_value = 0.04

        # Mock generation function that returns comprehensive metadata
        def mock_generation_func(prompt, model, **kwargs):
            return {
                "image_bytes": b"fake_image_data",
                "input_tokens": 10,
                "generation_timestamp": 1234567890,
                "enhanced_prompt": "Enhanced: " + prompt,
                "original_prompt": prompt,
                "requested_size": "1024x1024",
                "requested_quality": "hd",
                "requested_format": "png",
                "aspect_ratio": "1:1",
                "safety_attributes": {"safe": True, "score": 0.9},
                "content_filter_reason": "",
                "openai_metadata": {"revised": True},
                "gemini_metadata": {},
                "mime_type": "image/png",
                "cloud_uri": "",
                "original_url": "https://api.example.com/image.png",
            }

        mock_mcp = MagicMock()

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch(
                "mcp_handley_lab.llm.shared.tempfile.gettempdir", return_value=temp_dir
            ),
        ):
            result = process_image_generation(
                prompt="Test prompt",
                agent_name="test_agent",
                model="test-model",
                provider="test",
                generation_func=mock_generation_func,
                mcp_instance=mock_mcp,
            )

            # Verify file was created with correct content (within temp dir scope)
            assert Path(result.file_path).exists()
            assert Path(result.file_path).read_bytes() == b"fake_image_data"
            assert result.file_path.startswith(temp_dir)
            assert result.file_path.endswith(".png")

        # Verify all metadata was passed through correctly
        assert isinstance(result, ImageGenerationResult)
        assert result.message == "Image Generated Successfully"
        assert result.file_size_bytes == len(b"fake_image_data")
        assert result.agent_name == "test_agent"
        assert result.generation_timestamp == 1234567890
        assert result.enhanced_prompt == "Enhanced: Test prompt"
        assert result.original_prompt == "Test prompt"
        assert result.requested_size == "1024x1024"
        assert result.requested_quality == "hd"
        assert result.requested_format == "png"
        assert result.aspect_ratio == "1:1"
        assert result.safety_attributes == {"safe": True, "score": 0.9}
        assert result.content_filter_reason == ""
        assert result.openai_metadata == {"revised": True}
        assert result.gemini_metadata == {}
        assert result.mime_type == "image/png"
        assert result.cloud_uri == ""
        assert result.original_url == "https://api.example.com/image.png"

    @patch("mcp_handley_lab.llm.shared.calculate_cost")
    @patch("mcp_handley_lab.llm.shared.handle_agent_memory")
    def test_process_image_generation_minimal_metadata(self, mock_memory, mock_cost):
        """Test process_image_generation with minimal metadata from provider."""
        mock_cost.return_value = 0.03

        # Mock generation function with minimal metadata
        def mock_minimal_func(prompt, model, **kwargs):
            return {
                "image_bytes": b"minimal_image",
                "input_tokens": 5,
            }

        mock_mcp = MagicMock()

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch(
                "mcp_handley_lab.llm.shared.tempfile.gettempdir", return_value=temp_dir
            ),
        ):
            result = process_image_generation(
                prompt="Minimal test",
                agent_name="minimal_agent",
                model="minimal-model",
                provider="minimal",
                generation_func=mock_minimal_func,
                mcp_instance=mock_mcp,
            )

        # Verify core fields are set
        assert result.message == "Image Generated Successfully"
        assert result.agent_name == "minimal_agent"
        assert result.usage.model_used == "minimal-model"
        assert result.usage.cost == 0.03

        # Verify missing metadata gets defaults
        assert result.generation_timestamp == 0
        assert result.enhanced_prompt == ""
        assert result.original_prompt == "Minimal test"  # Falls back to prompt
        assert result.safety_attributes == {}
        assert result.openai_metadata == {}
        assert result.gemini_metadata == {}

    def test_process_image_generation_empty_prompt(self):
        """Test that empty prompt raises ValueError."""
        mock_func = MagicMock()
        mock_mcp = MagicMock()

        with pytest.raises(ValueError, match="Prompt is required and cannot be empty"):
            process_image_generation(
                prompt="",
                agent_name="test",
                model="test",
                provider="test",
                generation_func=mock_func,
                mcp_instance=mock_mcp,
            )

        # Ensure generation function was not called
        mock_func.assert_not_called()

    def test_process_image_generation_whitespace_prompt(self):
        """Test that whitespace-only prompt raises ValueError."""
        mock_func = MagicMock()
        mock_mcp = MagicMock()

        with pytest.raises(ValueError, match="Prompt is required and cannot be empty"):
            process_image_generation(
                prompt="   \n\t  ",
                agent_name="test",
                model="test",
                provider="test",
                generation_func=mock_func,
                mcp_instance=mock_mcp,
            )


class TestProviderSpecificMetadata:
    """Test provider-specific metadata handling."""

    def test_openai_specific_metadata_structure(self):
        """Test OpenAI-specific metadata structure."""
        result = ImageGenerationResult(
            message="Test",
            file_path="/tmp/test.png",
            file_size_bytes=1024,
            usage=UsageStats(
                input_tokens=10, output_tokens=1, cost=0.04, model_used="dall-e-3"
            ),
            openai_metadata={
                "background": None,
                "output_format": None,
                "usage": None,
                "model_version": "dall-e-3-v1",
            },
        )

        assert result.openai_metadata["background"] is None
        assert result.openai_metadata["output_format"] is None
        assert result.openai_metadata["usage"] is None
        assert result.openai_metadata["model_version"] == "dall-e-3-v1"

    def test_gemini_specific_metadata_structure(self):
        """Test Gemini-specific metadata structure."""
        result = ImageGenerationResult(
            message="Test",
            file_path="/tmp/test.png",
            file_size_bytes=1024,
            usage=UsageStats(
                input_tokens=10, output_tokens=1, cost=0.03, model_used="imagen-3"
            ),
            gemini_metadata={
                "positive_prompt_safety_attributes": None,
                "actual_model_used": "imagen-3.0-generate-002",
                "requested_model": "imagen-3",
            },
            safety_attributes={
                "categories": None,
                "scores": None,
                "content_type": None,
            },
        )

        assert result.gemini_metadata["actual_model_used"] == "imagen-3.0-generate-002"
        assert result.gemini_metadata["requested_model"] == "imagen-3"
        assert result.safety_attributes["categories"] is None

    def test_cross_provider_metadata_isolation(self):
        """Test that provider metadata doesn't interfere."""
        result = ImageGenerationResult(
            message="Test",
            file_path="/tmp/test.png",
            file_size_bytes=1024,
            usage=UsageStats(
                input_tokens=10, output_tokens=1, cost=0.04, model_used="test"
            ),
            openai_metadata={"provider": "openai"},
            gemini_metadata={"provider": "gemini"},
        )

        # Both should coexist without interference
        assert result.openai_metadata["provider"] == "openai"
        assert result.gemini_metadata["provider"] == "gemini"
        assert len(result.openai_metadata) == 1
        assert len(result.gemini_metadata) == 1
