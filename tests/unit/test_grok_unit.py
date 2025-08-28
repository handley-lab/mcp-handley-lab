"""Unit tests for Grok LLM module."""

from mcp_handley_lab.llm.grok.tool import (
    MODEL_CONFIGS,
    _get_model_config,
)


class TestGrokModelConfiguration:
    """Test Grok model configuration and functionality."""

    def test_model_configs_all_present(self):
        """Test that all expected Grok models are in MODEL_CONFIGS."""
        expected_models = {
            "grok-4",
            "grok-3",
            "grok-3-mini",
            "grok-2-vision-1212",
            "grok-2-image-1212",
            "grok-2-1212",
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models

    def test_model_configs_token_limits(self):
        """Test that model configurations have correct token limits."""
        # Grok 4 series
        assert MODEL_CONFIGS["grok-4"]["output_tokens"] == 100000

        # Grok 3 series
        assert MODEL_CONFIGS["grok-3"]["output_tokens"] == 65536
        assert MODEL_CONFIGS["grok-3-mini"]["output_tokens"] == 65536

        # Grok 2 series (text models)
        assert MODEL_CONFIGS["grok-2-vision-1212"]["output_tokens"] == 16384
        assert MODEL_CONFIGS["grok-2-1212"]["output_tokens"] == 16384

        # Grok 2 image generation model has None (doesn't use token limits)
        assert MODEL_CONFIGS["grok-2-image-1212"]["output_tokens"] is None

    def test_model_configs_structure(self):
        """Test that model configurations have required structure."""
        # All Grok models should have output_tokens field
        # Note: Image generation models may have None values
        for model_config in MODEL_CONFIGS.values():
            assert "output_tokens" in model_config
            # Allow None for image generation models, require int for others
            output_tokens = model_config["output_tokens"]
            assert output_tokens is None or isinstance(output_tokens, int)

    def test_get_model_config_valid_model(self):
        """Test _get_model_config with valid model names."""
        config = _get_model_config("grok-4")
        assert config["output_tokens"] == 100000

    def test_get_model_config_fallback_to_default(self):
        """Test _get_model_config falls back to default for unknown models."""
        from mcp_handley_lab.llm.grok.tool import DEFAULT_MODEL

        config = _get_model_config("nonexistent-model")
        default_config = MODEL_CONFIGS[DEFAULT_MODEL]
        assert config == default_config


class TestGrokErrorHandling:
    """Test Grok error handling and edge cases."""

    def test_model_config_retrieval_robust(self):
        """Test model configuration retrieval is robust."""
        # Should not raise exceptions for any model name
        config = _get_model_config("completely-invalid-model")
        assert isinstance(config, dict)
        assert "output_tokens" in config

    def test_model_configs_basic_structure(self):
        """Test that all model configs have basic required fields."""
        for model_name, config in MODEL_CONFIGS.items():
            assert "output_tokens" in config, f"Missing output_tokens in {model_name}"
            # Allow None for image generation models (like grok-2-image-1212)
            output_tokens = config["output_tokens"]
            assert output_tokens is None or isinstance(output_tokens, int), (
                f"Invalid output_tokens type in {model_name}: {type(output_tokens)}"
            )

    def test_model_count_matches_expected(self):
        """Test that we have the expected number of models."""
        # Ensure we have all 6 expected Grok models
        assert len(MODEL_CONFIGS) == 6
