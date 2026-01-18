"""Unit tests for Gemini LLM provider adapter."""

import pytest

from mcp_handley_lab.llm.providers.gemini.adapter import (
    MODEL_CONFIGS,
    get_model_config,
    resolve_files,
)


class TestModelConfiguration:
    """Test model configuration and token limit functionality."""

    @pytest.mark.parametrize(
        "model_name,expected_output_tokens",
        [
            ("gemini-3-pro-preview", 64000),
            ("gemini-2.5-pro", 65536),
            ("gemini-2.5-flash", 65536),
            ("gemini-2.5-flash-lite", 64000),
        ],
    )
    def test_model_output_token_limits_parameterized(
        self, model_name, expected_output_tokens
    ):
        """Test model output token limits for all models."""
        assert MODEL_CONFIGS[model_name]["output_tokens"] == expected_output_tokens

    def test_model_configs_all_present(self):
        """Test that all expected models are in MODEL_CONFIGS."""
        expected_models = {
            "gemini-3-pro-preview",
            "gemini-3-flash-preview",
            "gemini-3-pro-image-preview",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-deep-research",
            "imagen-4.0-generate-001",
            "imagen-4.0-fast-generate-001",
            "imagen-4.0-ultra-generate-001",
            "imagen-4.0-generate-preview-06-06",
            "veo-2.0-generate-001",
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models

    @pytest.mark.parametrize(
        "model_name,expected_output_tokens",
        [
            ("gemini-3-pro-preview", 64000),
            ("gemini-2.5-flash", 65536),
        ],
    )
    def test_get_model_config_parameterized(self, model_name, expected_output_tokens):
        """Test get_model_config with various known models."""
        config = get_model_config(model_name)
        assert config["output_tokens"] == expected_output_tokens

    def test_get_model_config_unknown_model(self):
        """Test get_model_config falls back to default for unknown models."""
        config = get_model_config("unknown-model")
        # Should default to gemini-3-pro-preview
        assert config["output_tokens"] == 64000


class TestGeminiHelpers:
    """Test Gemini internal helper functions."""

    def test_resolve_files_processing_error(self):
        """Test file processing error in resolve_files - should fail fast."""
        # Use invalid path that will cause stat() to fail
        files = ["/invalid/nonexistent/path"]

        # Should raise FileNotFoundError instead of adding error text
        with pytest.raises(FileNotFoundError):
            resolve_files(files)
