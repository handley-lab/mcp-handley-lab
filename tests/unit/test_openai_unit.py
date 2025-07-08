"""Unit tests for OpenAI LLM module."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_handley_lab.llm.common import determine_mime_type, is_text_file
from mcp_handley_lab.llm.openai.tool import (
    MODEL_CONFIGS,
    _get_model_config,
    analyze_image,
    ask,
    generate_image,
)


class TestOpenAIModelConfiguration:
    """Test OpenAI model configuration and token limit functionality."""

    def test_model_configs_all_present(self):
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

    def test_model_configs_token_limits(self):
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

    def test_model_configs_param_names(self):
        """Test that model configurations use correct parameter names."""
        # O1/O4 series use max_completion_tokens
        assert MODEL_CONFIGS["o4-mini"]["param"] == "max_completion_tokens"
        assert MODEL_CONFIGS["o1-preview"]["param"] == "max_completion_tokens"
        assert MODEL_CONFIGS["o1-mini"]["param"] == "max_completion_tokens"

        # GPT-4o series use max_tokens
        assert MODEL_CONFIGS["gpt-4o"]["param"] == "max_tokens"
        assert MODEL_CONFIGS["gpt-4o-mini"]["param"] == "max_tokens"
        assert MODEL_CONFIGS["gpt-4.1"]["param"] == "max_tokens"

    def test_get_model_config_known_models(self):
        """Test _get_model_config with known model names."""
        config = _get_model_config("o4-mini")
        assert config["output_tokens"] == 100000
        assert config["param"] == "max_completion_tokens"

        config = _get_model_config("gpt-4o")
        assert config["output_tokens"] == 16384
        assert config["param"] == "max_tokens"

    def test_get_model_config_unknown_model(self):
        """Test _get_model_config falls back to default for unknown models."""
        config = _get_model_config("unknown-model")
        # Should default to o4-mini
        assert config["output_tokens"] == 100000
        assert config["param"] == "max_completion_tokens"


class TestOpenAIHelperFunctions:
    """Test helper functions that don't require API calls."""

    def test_determine_mime_type_text(self):
        """Test MIME type detection for text files."""
        # Test common text file extensions
        assert determine_mime_type(Path("test.txt")) == "text/plain"
        assert determine_mime_type(Path("test.py")) == "text/x-python"
        assert determine_mime_type(Path("test.js")) == "text/javascript"
        assert determine_mime_type(Path("test.json")) == "application/json"

    def test_determine_mime_type_images(self):
        """Test MIME type detection for image files."""
        assert determine_mime_type(Path("test.jpg")) == "image/jpeg"
        assert determine_mime_type(Path("test.png")) == "image/png"
        assert determine_mime_type(Path("test.gif")) == "image/gif"
        assert determine_mime_type(Path("test.webp")) == "image/webp"

    def test_determine_mime_type_unknown(self):
        """Test MIME type detection for unknown extensions."""
        assert determine_mime_type(Path("test.unknown")) == "application/octet-stream"
        assert determine_mime_type(Path("no_extension")) == "application/octet-stream"

    def test_is_text_file_true(self):
        """Test text file detection for text files."""
        assert is_text_file(Path("test.txt")) is True
        assert is_text_file(Path("test.py")) is True
        assert is_text_file(Path("test.md")) is True
        assert is_text_file(Path("test.json")) is True

    def test_is_text_file_false(self):
        """Test text file detection for binary files."""
        assert is_text_file(Path("test.jpg")) is False
        assert is_text_file(Path("test.png")) is False
        assert is_text_file(Path("test.pdf")) is False
        assert is_text_file(Path("test.exe")) is False


class TestInputValidation:
    """Test input validation for main functions."""

    def test_ask_empty_prompt(self):
        """Test ask with empty prompt."""
        with pytest.raises(ValueError, match="Prompt is required and cannot be empty"):
            ask("", "/tmp/output.txt")

    def test_ask_empty_output_file(self):
        """Test ask with empty output file."""
        with pytest.raises(ValueError, match="Output file is required"):
            ask("Test prompt", "")

    def test_ask_empty_agent_name(self, mock_memory_manager):
        """Test ask with empty agent name disables memory."""
        # Mock the OpenAI API call to avoid real API requests in unit tests
        with patch(
            "mcp_handley_lab.llm.openai.tool.client.chat.completions.create"
        ) as mock_create:
            mock_response = type(
                "MockResponse",
                (),
                {
                    "choices": [
                        type(
                            "MockChoice",
                            (),
                            {
                                "message": type(
                                    "MockMessage", (), {"content": "Mocked response"}
                                )()
                            },
                        )()
                    ],
                    "usage": type(
                        "MockUsage", (), {"prompt_tokens": 10, "completion_tokens": 20}
                    )(),
                },
            )()
            mock_create.return_value = mock_response

            # Mock file writing
            with patch("pathlib.Path.write_text"):
                result = ask("Test prompt", "/tmp/output.txt", agent_name="")
                assert "Response saved to" in result
                # Verify memory manager is not called when agent_name is empty
                mock_memory_manager.get_response.assert_not_called()

    def test_analyze_image_empty_prompt(self):
        """Test analyze_image with empty prompt."""
        with pytest.raises(ValueError, match="Prompt is required and cannot be empty"):
            analyze_image("", "/tmp/output.txt")

    def test_analyze_image_empty_output_file(self):
        """Test analyze_image with empty output file."""
        with pytest.raises(ValueError, match="Output file is required"):
            analyze_image("Test prompt", "")

    def test_generate_image_empty_prompt(self):
        """Test generate_image with empty prompt."""
        with pytest.raises(ValueError, match="Prompt is required and cannot be empty"):
            generate_image("")


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
