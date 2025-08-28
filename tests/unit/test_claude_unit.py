"""Unit tests for Claude LLM module."""

from mcp_handley_lab.llm.claude.tool import (
    MODEL_CONFIGS,
    _get_model_config,
    _resolve_model_alias,
)


class TestClaudeModelConfiguration:
    """Test Claude model configuration and functionality."""

    def test_model_configs_all_present(self):
        """Test that all expected Claude models are in MODEL_CONFIGS."""
        expected_models = {
            "claude-opus-4",
            "claude-sonnet-4",
            "claude-3-7-sonnet-20250219",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-sonnet-20240620",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        }
        assert set(MODEL_CONFIGS.keys()) == expected_models

    def test_model_configs_token_limits(self):
        """Test that model configurations have correct token limits."""
        # Claude 4 series
        assert MODEL_CONFIGS["claude-opus-4"]["output_tokens"] == 32000
        assert MODEL_CONFIGS["claude-sonnet-4"]["output_tokens"] == 64000

        # Claude 3.5 series
        assert MODEL_CONFIGS["claude-3-5-sonnet-20241022"]["output_tokens"] == 8192
        assert MODEL_CONFIGS["claude-3-5-haiku-20241022"]["output_tokens"] == 8192

        # Claude 3 series
        assert MODEL_CONFIGS["claude-3-opus-20240229"]["output_tokens"] == 4096
        assert MODEL_CONFIGS["claude-3-sonnet-20240229"]["output_tokens"] == 4096
        assert MODEL_CONFIGS["claude-3-haiku-20240307"]["output_tokens"] == 4096

    def test_model_configs_context_windows(self):
        """Test that model configurations have correct context windows."""
        # All Claude models have 200K token context windows
        for model_config in MODEL_CONFIGS.values():
            assert model_config["input_tokens"] == 200000

    def test_model_configs_structure(self):
        """Test that model configurations have required structure."""
        # All Claude models should have basic token fields
        for model_config in MODEL_CONFIGS.values():
            assert "input_tokens" in model_config
            assert "output_tokens" in model_config
            assert isinstance(model_config["input_tokens"], int)
            assert isinstance(model_config["output_tokens"], int)

    def test_get_model_config_valid_model(self):
        """Test _get_model_config with valid model names."""
        config = _get_model_config("claude-3-5-sonnet-20241022")
        assert config["output_tokens"] == 8192
        assert config["input_tokens"] == 200000

    def test_get_model_config_fallback_to_default(self):
        """Test _get_model_config falls back to default for unknown models."""
        from mcp_handley_lab.llm.claude.tool import DEFAULT_MODEL

        config = _get_model_config("nonexistent-model")
        default_config = MODEL_CONFIGS[DEFAULT_MODEL]
        assert config == default_config

    def test_resolve_model_alias(self):
        """Test model alias resolution."""
        assert _resolve_model_alias("sonnet") == "claude-3-5-sonnet-20241022"
        assert _resolve_model_alias("opus") == "claude-3-opus-20240229"
        assert _resolve_model_alias("haiku") == "claude-3-5-haiku-20241022"

        # Test that non-alias models pass through unchanged
        assert (
            _resolve_model_alias("claude-3-5-sonnet-20241022")
            == "claude-3-5-sonnet-20241022"
        )


class TestClaudeErrorHandling:
    """Test Claude error handling and edge cases."""

    def test_model_alias_unknown(self):
        """Test that unknown aliases pass through unchanged."""
        unknown_alias = "unknown-model"
        result = _resolve_model_alias(unknown_alias)
        assert result == unknown_alias

    def test_model_config_retrieval_robust(self):
        """Test model configuration retrieval is robust."""
        # Should not raise exceptions for any model name
        config = _get_model_config("completely-invalid-model")
        assert isinstance(config, dict)
        assert "output_tokens" in config
        assert "input_tokens" in config
