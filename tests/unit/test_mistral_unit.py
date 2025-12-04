"""Unit tests for Mistral LLM tool functionality."""

import pytest

from mcp_handley_lab.llm.mistral.tool import (
    MODEL_CONFIGS,
    _get_model_config,
)


class TestModelConfiguration:
    """Test model configuration and token limit functionality."""

    @pytest.mark.parametrize(
        "model_name,expected_output_tokens",
        [
            ("mistral-large-latest", 8192),
            ("pixtral-large-latest", 8192),
            ("pixtral-12b-2409", 8192),
            ("mistral-small-latest", 8192),
            ("codestral-latest", 8192),
            ("ministral-8b-latest", 8192),
            ("mistral-ocr-latest", 0),
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
            "mistral-large-latest",
            "pixtral-large-latest",
            "pixtral-12b-2409",
            "mistral-small-latest",
            "codestral-latest",
            "ministral-8b-latest",
            "mistral-ocr-latest",
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models

    @pytest.mark.parametrize(
        "model_name,expected_output_tokens",
        [
            ("mistral-large-latest", 8192),
            ("pixtral-12b-2409", 8192),
        ],
    )
    def test_get_model_config_parameterized(self, model_name, expected_output_tokens):
        """Test _get_model_config with various known models."""
        config = _get_model_config(model_name)
        assert config["output_tokens"] == expected_output_tokens

    def test_get_model_config_unknown_model(self):
        """Test _get_model_config falls back to default for unknown models."""
        config = _get_model_config("unknown-model")
        # Should default to mistral-large-latest
        assert config["output_tokens"] == 8192

    def test_all_models_have_output_tokens(self):
        """Test that all models have output_tokens configured."""
        for model_id, config in MODEL_CONFIGS.items():
            assert "output_tokens" in config, f"Model {model_id} missing output_tokens"
            # output_tokens should be an int (0 for OCR model, 8192 for others)
            assert isinstance(
                config["output_tokens"], int
            ), f"Model {model_id} output_tokens should be int"


class TestMistralHelpers:
    """Test Mistral internal helper functions."""

    def test_resolve_files_processing_error(self):
        """Test file processing error in _resolve_files - should fail fast."""
        from mcp_handley_lab.llm.mistral.tool import _resolve_files

        # Use invalid path that will cause stat() to fail
        files = ["/invalid/nonexistent/path"]

        # Should raise FileNotFoundError instead of adding error text
        with pytest.raises(FileNotFoundError):
            _resolve_files(files)
