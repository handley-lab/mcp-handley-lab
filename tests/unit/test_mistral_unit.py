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
            ("mistral-medium-latest", 8192),
            ("mistral-small-latest", 8192),
            ("ministral-3b-latest", 8192),
            ("ministral-8b-latest", 8192),
            ("magistral-medium-latest", 40000),
            ("magistral-small-latest", 40000),
            ("codestral-latest", 8192),
            ("devstral-small-latest", 8192),
            ("pixtral-large-latest", 8192),
            ("pixtral-12b-2409", 8192),
            ("voxtral-small-latest", 8192),
            ("voxtral-mini-latest", 8192),
            ("mistral-ocr-latest", 0),
            ("mistral-moderation-latest", 0),
            ("mistral-embed", 0),
            ("codestral-embed", 0),
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
            # Frontier generalist
            "mistral-large-latest",
            "mistral-medium-latest",
            "mistral-small-latest",
            # Ministral edge
            "ministral-3b-latest",
            "ministral-8b-latest",
            # Reasoning (Magistral)
            "magistral-medium-latest",
            "magistral-small-latest",
            # Coding
            "codestral-latest",
            "devstral-small-latest",
            # Vision (Pixtral)
            "pixtral-large-latest",
            "pixtral-12b-2409",
            # Audio (Voxtral)
            "voxtral-small-latest",
            "voxtral-mini-latest",
            # Specialist
            "mistral-ocr-latest",
            "mistral-moderation-latest",
            # Embedding
            "mistral-embed",
            "codestral-embed",
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models

    @pytest.mark.parametrize(
        "model_name,expected_output_tokens",
        [
            ("mistral-large-latest", 8192),
            ("magistral-medium-latest", 40000),
            ("codestral-latest", 8192),
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
            # output_tokens should be an int
            assert isinstance(config["output_tokens"], int), (
                f"Model {model_id} output_tokens should be int"
            )

    def test_vision_models_have_supports_vision(self):
        """Test that vision-capable models have supports_vision flag."""
        vision_models = [
            "mistral-large-latest",
            "mistral-medium-latest",
            "mistral-small-latest",
            "ministral-3b-latest",
            "ministral-8b-latest",
            "pixtral-large-latest",
            "pixtral-12b-2409",
            "mistral-ocr-latest",
        ]
        for model_id in vision_models:
            config = MODEL_CONFIGS[model_id]
            assert config.get("supports_vision") is True, (
                f"Model {model_id} should support vision"
            )

    def test_reasoning_models_have_supports_reasoning(self):
        """Test that reasoning models have supports_reasoning flag."""
        reasoning_models = ["magistral-medium-latest", "magistral-small-latest"]
        for model_id in reasoning_models:
            config = MODEL_CONFIGS[model_id]
            assert config.get("supports_reasoning") is True, (
                f"Model {model_id} should support reasoning"
            )

    def test_audio_models_have_supports_audio(self):
        """Test that audio models have supports_audio flag."""
        audio_models = ["voxtral-small-latest", "voxtral-mini-latest"]
        for model_id in audio_models:
            config = MODEL_CONFIGS[model_id]
            assert config.get("supports_audio") is True, (
                f"Model {model_id} should support audio"
            )

    def test_fim_models_have_supports_fim(self):
        """Test that FIM-capable models have supports_fim flag."""
        fim_models = ["codestral-latest", "devstral-small-latest"]
        for model_id in fim_models:
            config = MODEL_CONFIGS[model_id]
            assert config.get("supports_fim") is True, (
                f"Model {model_id} should support FIM"
            )

    def test_embedding_models_have_dimensions(self):
        """Test that embedding models have embedding_dimensions configured."""
        embedding_models = ["mistral-embed", "codestral-embed"]
        for model_id in embedding_models:
            config = MODEL_CONFIGS[model_id]
            assert "embedding_dimensions" in config, (
                f"Model {model_id} missing embedding_dimensions"
            )
            assert isinstance(config["embedding_dimensions"], int), (
                f"Model {model_id} embedding_dimensions should be int"
            )


class TestMistralHelpers:
    """Test Mistral internal helper functions."""

    def test_resolve_files_processing_error(self):
        """Test file processing error in _resolve_files - should fail fast."""
        from mcp_handley_lab.llm.mistral.tool import _resolve_files

        # Use invalid path with unknown MIME type
        files = ["/invalid/nonexistent/path"]

        # Should raise ValueError for unsupported file type
        with pytest.raises(ValueError, match="Unsupported file type"):
            _resolve_files(files)
