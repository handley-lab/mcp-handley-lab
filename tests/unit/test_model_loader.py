"""Unit tests for model_loader module."""
from unittest.mock import mock_open, patch

import pytest
import yaml
from mcp_handley_lab.llm.model_loader import (
    build_model_configs_dict,
    format_model_listing,
    get_models_by_tags,
    load_model_config,
)


class TestLoadModelConfig:
    """Test model configuration loading."""

    def test_load_model_config_gemini(self):
        """Test loading Gemini model configuration."""
        config = load_model_config("gemini")

        # Verify required sections exist
        assert "models" in config
        assert "display_categories" in config
        assert "default_model" in config
        assert "usage_notes" in config

        # Verify some expected models
        assert "gemini-2.5-pro" in config["models"]
        assert "gemini-2.5-flash" in config["models"]
        assert "imagen-3.0-generate-002" in config["models"]

        # Verify default model
        assert config["default_model"] == "gemini-2.5-pro"

    def test_load_model_config_openai(self):
        """Test loading OpenAI model configuration."""
        config = load_model_config("openai")

        # Verify required sections exist
        assert "models" in config
        assert "display_categories" in config
        assert "default_model" in config
        assert "usage_notes" in config

        # Verify some expected models
        assert "o4-mini" in config["models"]
        assert "gpt-4.1" in config["models"]
        assert "dall-e-3" in config["models"]

        # Verify default model
        assert config["default_model"] == "o4-mini"

    def test_load_model_config_claude(self):
        """Test loading Claude model configuration."""
        config = load_model_config("claude")

        # Verify required sections exist
        assert "models" in config
        assert "display_categories" in config
        assert "default_model" in config
        assert "usage_notes" in config

        # Verify some expected models
        assert "claude-sonnet-3.7" in config["models"]
        assert "claude-opus-4" in config["models"]

        # Verify default model
        assert config["default_model"] == "claude-sonnet-3.7"

    def test_load_model_config_nonexistent_provider(self):
        """Test loading configuration for non-existent provider."""
        with pytest.raises(FileNotFoundError):
            load_model_config("nonexistent")

    @patch("builtins.open", mock_open(read_data="invalid: yaml: content: ["))
    def test_load_model_config_invalid_yaml(self):
        """Test loading invalid YAML file."""
        with pytest.raises(yaml.YAMLError):
            load_model_config("gemini")

    @patch("builtins.open", mock_open(read_data="models: {}"))
    def test_load_model_config_missing_sections(self):
        """Test loading YAML with missing required sections."""
        with pytest.raises(ValueError, match="Missing required sections"):
            load_model_config("gemini")


class TestGetModelsByTags:
    """Test model filtering by tags."""

    @pytest.fixture
    def sample_config(self):
        """Sample configuration for testing."""
        return {
            "models": {
                "model-a": {"tags": ["reasoning", "latest"]},
                "model-b": {"tags": ["general", "cost-effective"]},
                "model-c": {"tags": ["reasoning", "legacy"]},
                "model-d": {"tags": ["image-generation"]},
                "model-e": {"tags": ["reasoning", "latest", "premium"]},
            }
        }

    def test_get_models_by_tags_single_required(self, sample_config):
        """Test filtering by single required tag."""
        result = get_models_by_tags(sample_config, ["reasoning"])

        expected = {"model-a", "model-c", "model-e"}
        assert set(result.keys()) == expected

    def test_get_models_by_tags_multiple_required(self, sample_config):
        """Test filtering by multiple required tags."""
        result = get_models_by_tags(sample_config, ["reasoning", "latest"])

        expected = {"model-a", "model-e"}
        assert set(result.keys()) == expected

    def test_get_models_by_tags_with_exclude(self, sample_config):
        """Test filtering with excluded tags."""
        result = get_models_by_tags(sample_config, ["reasoning"], ["legacy"])

        expected = {"model-a", "model-e"}
        assert set(result.keys()) == expected

    def test_get_models_by_tags_no_matches(self, sample_config):
        """Test filtering with no matching models."""
        result = get_models_by_tags(sample_config, ["nonexistent"])

        assert result == {}

    def test_get_models_by_tags_model_without_tags(self):
        """Test filtering when model has no tags."""
        config = {
            "models": {
                "model-a": {},  # No tags field
                "model-b": {"tags": ["test"]},
            }
        }

        result = get_models_by_tags(config, ["test"])
        assert set(result.keys()) == {"model-b"}


class TestBuildModelConfigsDict:
    """Test building model configs dictionary."""

    def test_build_model_configs_dict_openai(self):
        """Test building OpenAI model configs."""
        configs = build_model_configs_dict("openai")

        # Test reasoning model
        assert "o4-mini" in configs
        assert configs["o4-mini"]["output_tokens"] == 100000
        assert configs["o4-mini"]["param"] == "max_completion_tokens"

        # Test general model
        assert "gpt-4.1" in configs
        assert configs["gpt-4.1"]["output_tokens"] == 16384
        assert configs["gpt-4.1"]["param"] == "max_tokens"

        # Test image generation model
        assert "dall-e-3" in configs
        assert configs["dall-e-3"]["output_tokens"] is None
        assert configs["dall-e-3"]["param"] is None

    def test_build_model_configs_dict_claude(self):
        """Test building Claude model configs."""
        configs = build_model_configs_dict("claude")

        # Test Claude model
        assert "claude-sonnet-3.7" in configs
        assert configs["claude-sonnet-3.7"]["input_tokens"] == 200000
        assert configs["claude-sonnet-3.7"]["output_tokens"] == 64000

    def test_build_model_configs_dict_gemini(self):
        """Test building Gemini model configs."""
        configs = build_model_configs_dict("gemini")

        # Test text model
        assert "gemini-2.5-pro" in configs
        assert configs["gemini-2.5-pro"]["output_tokens"] == 65536

        # Test image generation model
        assert "imagen-3.0-generate-002" in configs
        assert configs["imagen-3.0-generate-002"]["output_tokens"] is None


class TestFormatModelListing:
    """Test model listing formatting."""

    def test_format_model_listing_gemini(self):
        """Test formatting Gemini model listing."""
        listing = format_model_listing("gemini")

        # Check summary section
        assert "Gemini Model Summary" in listing
        assert "Total Models:" in listing
        assert "Default Model: gemini-2.5-pro" in listing

        # Check model categories
        assert "🚀 Gemini 2.5 Series" in listing
        assert "⚡ Gemini 1.5 Series" in listing
        assert "🎨 Image Generation" in listing

        # Check specific models
        assert "gemini-2.5-pro" in listing
        assert "imagen-3.0-generate-002" in listing

        # Check pricing information
        assert "$" in listing  # Should have pricing info
        assert "per" in listing  # Should have per-token or per-image pricing

    def test_format_model_listing_openai(self):
        """Test formatting OpenAI model listing."""
        listing = format_model_listing("openai")

        # Check summary section
        assert "Openai Model Summary" in listing
        assert "Default Model: o4-mini" in listing

        # Check model categories
        assert "🧠 Reasoning Models" in listing
        assert "💭 Latest Language Models" in listing
        assert "🎨 Image Generation" in listing

        # Check specific models
        assert "o4-mini" in listing
        assert "gpt-4.1" in listing
        assert "dall-e-3" in listing

    def test_format_model_listing_claude(self):
        """Test formatting Claude model listing."""
        listing = format_model_listing("claude")

        # Check summary section
        assert "Claude Model Summary" in listing
        assert "Default Model: claude-sonnet-3.7" in listing

        # Check model categories
        assert "🚀 Claude 4 Series" in listing
        assert "⚡ Claude 3.5 Series" in listing

        # Check specific models
        assert "claude-sonnet-3.7" in listing
        assert "claude-opus-4" in listing

    def test_format_model_listing_with_api_models(self):
        """Test formatting with API model availability."""
        api_models = {"o4-mini", "gpt-4.1", "dall-e-3"}
        listing = format_model_listing("openai", api_models)

        # Should show API availability
        assert "API Available Models: 3" in listing
        assert "✅ Available" in listing

    def test_format_model_listing_pricing_errors(self):
        """Test formatting handles pricing calculation errors gracefully."""
        # This should not raise exceptions even if pricing fails
        listing = format_model_listing("gemini")
        assert isinstance(listing, str)
        assert len(listing) > 0


class TestModelConfigErrorHandling:
    """Test error handling in model configuration."""

    def test_build_model_configs_missing_output_tokens_openai(self):
        """Test error when OpenAI model missing output_tokens."""
        with patch("mcp_handley_lab.llm.model_loader.load_model_config") as mock_load:
            mock_load.return_value = {
                "models": {
                    "test-model": {
                        "param": "max_tokens"
                        # Missing output_tokens
                    }
                },
                "display_categories": [],
                "default_model": "test-model",
                "usage_notes": [],
            }

            with pytest.raises(ValueError, match="Missing 'output_tokens'"):
                build_model_configs_dict("openai")

    def test_build_model_configs_missing_param_openai(self):
        """Test error when OpenAI model missing param."""
        with patch("mcp_handley_lab.llm.model_loader.load_model_config") as mock_load:
            mock_load.return_value = {
                "models": {
                    "test-model": {
                        "output_tokens": 1000
                        # Missing param
                    }
                },
                "display_categories": [],
                "default_model": "test-model",
                "usage_notes": [],
            }

            with pytest.raises(ValueError, match="Missing 'param'"):
                build_model_configs_dict("openai")

    def test_build_model_configs_missing_input_tokens_claude(self):
        """Test error when Claude model missing input_tokens."""
        with patch("mcp_handley_lab.llm.model_loader.load_model_config") as mock_load:
            mock_load.return_value = {
                "models": {
                    "test-model": {
                        "output_tokens": 1000
                        # Missing input_tokens
                    }
                },
                "display_categories": [],
                "default_model": "test-model",
                "usage_notes": [],
            }

            with pytest.raises(ValueError, match="Missing 'input_tokens'"):
                build_model_configs_dict("claude")

    def test_build_model_configs_missing_output_tokens_gemini(self):
        """Test error when Gemini text model missing output_tokens."""
        with patch("mcp_handley_lab.llm.model_loader.load_model_config") as mock_load:
            mock_load.return_value = {
                "models": {
                    "test-model": {
                        # Missing output_tokens for text model
                        # No pricing_type means it's a text model
                    }
                },
                "display_categories": [],
                "default_model": "test-model",
                "usage_notes": [],
            }

            with pytest.raises(ValueError, match="Missing 'output_tokens'"):
                build_model_configs_dict("gemini")
