"""Unit tests for OpenAI LLM module."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp_handley_lab.llm.agent.tool import get_response
from mcp_handley_lab.llm.common import determine_mime_type, is_text_file
from mcp_handley_lab.llm.openai.tool import (
    MODEL_CONFIGS,
    _get_model_config,
    _resolve_files,
    _resolve_images,
    analyze_image,
    ask,
    generate_image,
)


class TestOpenAIModelConfiguration:
    """Test OpenAI model configuration and token limit functionality."""

    @pytest.mark.asyncio
    async def test_model_configs_all_present(self):
        """Test that all expected OpenAI models are in MODEL_CONFIGS."""
        expected_models = {
            "o3",
            "o4-mini",
            "o1",
            "o1-preview",
            "o1-mini",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4o-2024-11-20",
            "gpt-4o-2024-08-06",
            "gpt-4o-mini-2024-07-18",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
            "dall-e-3",
            "dall-e-2",
            "gpt-image-1",
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models

    @pytest.mark.asyncio
    async def test_model_configs_token_limits(self):
        """Test that model configurations have correct token limits."""
        # O3/O4 series
        assert MODEL_CONFIGS["o4-mini"]["output_tokens"] == 100000

        # O1 series
        assert MODEL_CONFIGS["o1-preview"]["output_tokens"] == 32768
        assert MODEL_CONFIGS["o1-mini"]["output_tokens"] == 65536

        # GPT-4o series
        assert MODEL_CONFIGS["gpt-4o"]["output_tokens"] == 16384
        assert MODEL_CONFIGS["gpt-4o-mini"]["output_tokens"] == 16384

        # GPT-4.1 series
        assert MODEL_CONFIGS["gpt-4.1"]["output_tokens"] == 16384
        assert MODEL_CONFIGS["gpt-4.1-mini"]["output_tokens"] == 16384

    @pytest.mark.asyncio
    async def test_model_configs_param_names(self):
        """Test that model configurations use correct parameter names."""
        # O1/O4 series use max_completion_tokens
        assert MODEL_CONFIGS["o4-mini"]["param"] == "max_completion_tokens"
        assert MODEL_CONFIGS["o1-preview"]["param"] == "max_completion_tokens"
        assert MODEL_CONFIGS["o1-mini"]["param"] == "max_completion_tokens"

        # GPT-4o series use max_tokens
        assert MODEL_CONFIGS["gpt-4o"]["param"] == "max_tokens"
        assert MODEL_CONFIGS["gpt-4o-mini"]["param"] == "max_tokens"
        assert MODEL_CONFIGS["gpt-4.1"]["param"] == "max_tokens"

    @pytest.mark.asyncio
    async def test_get_model_config_known_models(self):
        """Test _get_model_config with known model names."""
        config = _get_model_config("o4-mini")
        assert config["output_tokens"] == 100000
        assert config["param"] == "max_completion_tokens"

        config = _get_model_config("gpt-4o")
        assert config["output_tokens"] == 16384
        assert config["param"] == "max_tokens"

    @pytest.mark.asyncio
    async def test_get_model_config_unknown_model(self):
        """Test _get_model_config falls back to default for unknown models."""
        config = _get_model_config("unknown-model")
        # Should default to o4-mini
        assert config["output_tokens"] == 100000
        assert config["param"] == "max_completion_tokens"


class TestOpenAIHelperFunctions:
    """Test helper functions that don't require API calls."""

    @pytest.mark.asyncio
    async def test_determine_mime_type_text(self):
        """Test MIME type detection for text files."""
        # Test common text file extensions
        assert determine_mime_type(Path("test.txt")) == "text/plain"
        assert determine_mime_type(Path("test.py")) == "text/x-python"
        assert determine_mime_type(Path("test.js")) == "text/javascript"
        assert determine_mime_type(Path("test.json")) == "application/json"

    @pytest.mark.asyncio
    async def test_determine_mime_type_images(self):
        """Test MIME type detection for image files."""
        assert determine_mime_type(Path("test.jpg")) == "image/jpeg"
        assert determine_mime_type(Path("test.png")) == "image/png"
        assert determine_mime_type(Path("test.gif")) == "image/gif"
        assert determine_mime_type(Path("test.webp")) == "image/webp"

    @pytest.mark.asyncio
    async def test_determine_mime_type_unknown(self):
        """Test MIME type detection for unknown extensions."""
        assert determine_mime_type(Path("test.unknown")) == "application/octet-stream"
        assert determine_mime_type(Path("no_extension")) == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_is_text_file_true(self):
        """Test text file detection for text files."""
        assert is_text_file(Path("test.txt")) is True
        assert is_text_file(Path("test.py")) is True
        assert is_text_file(Path("test.md")) is True
        assert is_text_file(Path("test.json")) is True

    @pytest.mark.asyncio
    async def test_is_text_file_false(self):
        """Test text file detection for binary files."""
        assert is_text_file(Path("test.jpg")) is False
        assert is_text_file(Path("test.png")) is False
        assert is_text_file(Path("test.pdf")) is False
        assert is_text_file(Path("test.exe")) is False


class TestResolveFiles:
    """Test file resolution logic."""

    @pytest.mark.asyncio
    async def test_resolve_files_none(self):
        """Test resolve_files with None input."""
        inline_content = await _resolve_files(None)
        assert inline_content == []

    @pytest.mark.asyncio
    async def test_resolve_files_empty_list(self):
        """Test resolve_files with empty list."""
        inline_content = await _resolve_files([])
        assert inline_content == []

    @pytest.mark.asyncio
    async def test_resolve_files_direct_string(self):
        """Test resolve_files with direct string content."""
        files = ["This is direct content", "More content"]
        inline_content = await _resolve_files(files)
        assert inline_content == ["This is direct content", "More content"]

    @pytest.mark.asyncio
    async def test_resolve_files_dict_content(self):
        """Test resolve_files with dict content."""
        files = [{"content": "Dict content"}, {"content": "More dict content"}]
        inline_content = await _resolve_files(files)
        assert inline_content == ["Dict content", "More dict content"]

    @pytest.mark.asyncio
    async def test_resolve_files_small_text_file(self):
        """Test resolve_files with small text file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Small text file content")
            temp_path = f.name

        try:
            files = [{"path": temp_path}]
            inline_content = await _resolve_files(files)

            assert len(inline_content) == 1
            assert "Small text file content" in inline_content[0]
            assert (
                Path(temp_path).name in inline_content[0]
            )  # Should include filename header
        finally:
            Path(temp_path).unlink()


class TestResolveImages:
    """Test image resolution for vision models."""

    @pytest.mark.asyncio
    async def test_resolve_images_none(self):
        """Test resolve_images with None input."""
        images = _resolve_images()
        assert images == []

    @pytest.mark.asyncio
    async def test_resolve_images_direct_data_url(self):
        """Test resolve_images with data URL."""
        data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        resolved_images = _resolve_images(image_data=data_url)

        assert len(resolved_images) == 1
        assert resolved_images[0] == data_url

    @pytest.mark.asyncio
    async def test_resolve_images_dict_data(self):
        """Test resolve_images with dict containing base64 data."""
        base64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        images = [{"data": base64_data}]
        resolved_images = _resolve_images(images=images)

        assert len(resolved_images) == 1
        assert (
            "data:image/jpeg;base64," in resolved_images[0]
        )  # Function defaults to JPEG for dict data


class TestInputValidation:
    """Test input validation for main functions."""

    @pytest.mark.asyncio
    async def test_ask_empty_prompt(self):
        """Test ask with empty prompt."""
        with pytest.raises(ValueError, match="Prompt is required and cannot be empty"):
            await ask("", "/tmp/output.txt")

    @pytest.mark.asyncio
    async def test_ask_empty_output_file(self):
        """Test ask with empty output file."""
        with pytest.raises(ValueError, match="Output file is required"):
            await ask("Test prompt", "")

    @pytest.mark.asyncio
    async def test_ask_empty_agent_name(self):
        """Test ask with empty agent name."""
        with pytest.raises(ValueError, match="Agent name cannot be empty"):
            await ask("Test prompt", "/tmp/output.txt", agent_name="")

    @pytest.mark.asyncio
    async def test_analyze_image_empty_prompt(self):
        """Test analyze_image with empty prompt."""
        with pytest.raises(ValueError, match="Prompt is required and cannot be empty"):
            await analyze_image("", "/tmp/output.txt")

    @pytest.mark.asyncio
    async def test_analyze_image_empty_output_file(self):
        """Test analyze_image with empty output file."""
        with pytest.raises(ValueError, match="Output file is required"):
            await analyze_image("Test prompt", "")

    @pytest.mark.asyncio
    async def test_generate_image_empty_prompt(self):
        """Test generate_image with empty prompt."""
        with pytest.raises(ValueError, match="Prompt is required and cannot be empty"):
            await generate_image("")

    @pytest.mark.asyncio
    async def test_get_response_nonexistent_agent(self, mock_memory_manager):
        """Test get_response with nonexistent agent."""
        mock_memory_manager.get_response.return_value = None
        mock_memory_manager.get_agent.return_value = None

        with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
            await get_response("nonexistent")


@pytest.fixture
def temp_storage_dir():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_memory_manager():
    """Mock memory manager for testing."""
    with patch("mcp_handley_lab.llm.openai.tool.memory_manager") as mock_manager:
        yield mock_manager
