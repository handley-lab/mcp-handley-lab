"""Unit tests for OpenAI LLM provider adapter."""

from pathlib import Path

from mcp_handley_lab.llm.common import determine_mime_type, is_text_file
from mcp_handley_lab.llm.providers.openai.adapter import (
    MODEL_CONFIGS,
    get_model_config,
)


class TestOpenAIModelConfiguration:
    """Test OpenAI model configuration and token limit functionality."""

    def test_model_configs_all_present(self):
        """Test that all expected OpenAI models are in MODEL_CONFIGS."""
        expected_models = {
            # GPT-5 series
            "gpt-5.2",
            "gpt-5.2-pro",
            "gpt-5.1",
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano",
            "gpt-5-pro",
            # O-series reasoning
            "o3",
            "o3-pro",
            "o3-mini",
            "o3-deep-research",
            "o4-mini",
            "o4-mini-deep-research",
            "o1",
            "o1-mini",
            # GPT-4 series
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            # Image generation
            "dall-e-3",
            "gpt-image-1.5",
            "gpt-image-1",
            "gpt-image-1-mini",
            # Audio models (ASR/TTS)
            "whisper-1",
            "tts-1",
            "tts-1-hd",
            # Realtime API
            "gpt-4o-realtime-preview",
            "gpt-4o-mini-realtime-preview",
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models

    def test_model_configs_token_limits(self):
        """Test that model configurations have correct token limits."""
        # GPT-5 series
        assert MODEL_CONFIGS["gpt-5.2"]["output_tokens"] == 128000
        assert MODEL_CONFIGS["gpt-5.2-pro"]["output_tokens"] == 128000
        assert MODEL_CONFIGS["gpt-5"]["output_tokens"] == 128000
        assert MODEL_CONFIGS["gpt-5-mini"]["output_tokens"] == 128000
        assert MODEL_CONFIGS["gpt-5-nano"]["output_tokens"] == 128000
        assert MODEL_CONFIGS["gpt-5.1"]["output_tokens"] == 128000
        assert MODEL_CONFIGS["gpt-5-pro"]["output_tokens"] == 128000

        # O3/O4 series
        assert MODEL_CONFIGS["o4-mini"]["output_tokens"] == 100000
        assert MODEL_CONFIGS["o3"]["output_tokens"] == 100000
        assert MODEL_CONFIGS["o3-mini"]["output_tokens"] == 100000

        # O1 series
        assert MODEL_CONFIGS["o1"]["output_tokens"] == 100000
        assert MODEL_CONFIGS["o1-mini"]["output_tokens"] == 65536

        # GPT-4o series
        assert MODEL_CONFIGS["gpt-4o"]["output_tokens"] == 16384
        assert MODEL_CONFIGS["gpt-4o-mini"]["output_tokens"] == 16384

        # GPT-4.1 series
        assert MODEL_CONFIGS["gpt-4.1"]["output_tokens"] == 16384
        assert MODEL_CONFIGS["gpt-4.1-mini"]["output_tokens"] == 16384

    def test_model_configs_param_names(self):
        """Test that model configurations use correct parameter names.

        Responses API uses max_output_tokens for all reasoning models (GPT-5, o-series).
        Legacy GPT-4.x models still use max_tokens.
        """
        # GPT-5 series use max_output_tokens (Responses API)
        assert MODEL_CONFIGS["gpt-5"]["param"] == "max_output_tokens"
        assert MODEL_CONFIGS["gpt-5.1"]["param"] == "max_output_tokens"
        assert MODEL_CONFIGS["gpt-5-mini"]["param"] == "max_output_tokens"
        assert MODEL_CONFIGS["gpt-5-nano"]["param"] == "max_output_tokens"
        assert MODEL_CONFIGS["gpt-5-pro"]["param"] == "max_output_tokens"

        # O1/O3/O4 series use max_output_tokens (Responses API)
        assert MODEL_CONFIGS["o4-mini"]["param"] == "max_output_tokens"
        assert MODEL_CONFIGS["o3"]["param"] == "max_output_tokens"
        assert MODEL_CONFIGS["o3-mini"]["param"] == "max_output_tokens"
        assert MODEL_CONFIGS["o1"]["param"] == "max_output_tokens"
        assert MODEL_CONFIGS["o1-mini"]["param"] == "max_output_tokens"

        # GPT-4o/4.1 series also use max_output_tokens (Responses API)
        assert MODEL_CONFIGS["gpt-4o"]["param"] == "max_output_tokens"
        assert MODEL_CONFIGS["gpt-4o-mini"]["param"] == "max_output_tokens"
        assert MODEL_CONFIGS["gpt-4.1"]["param"] == "max_output_tokens"

    def test_get_model_config_known_models(self):
        """Test get_model_config with known model names."""
        config = get_model_config("o4-mini")
        assert config["output_tokens"] == 100000
        assert config["param"] == "max_output_tokens"  # Responses API

        config = get_model_config("gpt-4o")
        assert config["output_tokens"] == 16384
        assert config["param"] == "max_output_tokens"  # Responses API

    def test_get_model_config_unknown_model(self):
        """Test get_model_config falls back to default for unknown models."""
        config = get_model_config("unknown-model")
        # Should default to gpt-5.2 (Responses API)
        assert config["output_tokens"] == 128000
        assert config["param"] == "max_output_tokens"


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
