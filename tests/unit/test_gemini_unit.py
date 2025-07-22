"""Unit tests for Gemini LLM tool functionality."""
import pytest
from mcp_handley_lab.llm.gemini.tool import (
    MODEL_CONFIGS,
    _get_model_config,
)


class TestModelConfiguration:
    """Test model configuration and token limit functionality."""

    @pytest.mark.parametrize(
        "model_name,expected_output_tokens",
        [
            ("gemini-2.5-pro", 65536),
            ("gemini-2.5-flash", 65536),
            ("gemini-2.5-flash-lite", 64000),
            ("gemini-1.5-flash", 8192),
            ("gemini-1.5-flash-8b", 8192),
            ("gemini-1.5-pro", 8192),
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
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-1.5-pro",
            "imagen-4.0-generate-preview-06-06",
            "imagen-4.0-ultra-generate-preview-06-06",
            "imagen-3.0-generate-002",
            "veo-2",
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models

    @pytest.mark.parametrize(
        "model_name,expected_output_tokens",
        [
            ("gemini-2.5-flash", 65536),
            ("gemini-1.5-pro", 8192),
        ],
    )
    def test_get_model_config_parameterized(self, model_name, expected_output_tokens):
        """Test _get_model_config with various known models."""
        config = _get_model_config(model_name)
        assert config["output_tokens"] == expected_output_tokens

    def test_get_model_config_unknown_model(self):
        """Test _get_model_config falls back to default for unknown models."""
        config = _get_model_config("unknown-model")
        # Should default to gemini-2.5-flash
        assert config["output_tokens"] == 65536




class TestGeminiHelpers:
    """Test Gemini internal helper functions."""

    def test_resolve_files_processing_error(self):
        """Test file processing error in _resolve_files - should fail fast."""
        from mcp_handley_lab.llm.gemini.tool import _resolve_files

        # Use invalid path that will cause stat() to fail
        files = ["/invalid/nonexistent/path"]

        # Should raise FileNotFoundError instead of adding error text
        with pytest.raises(FileNotFoundError):
            _resolve_files(files)
