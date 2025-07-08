"""Unit tests for common modules (config and pricing) with parametrized tests."""
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_handley_lab.common.config import Settings
from mcp_handley_lab.common.pricing import (
    PricingCalculator,
    calculate_cost,
    format_usage,
)


class TestConfig:
    """Test configuration functionality."""

    @patch.dict("os.environ", {}, clear=True)
    def test_settings_default_values(self):
        """Test Settings with default values (no env vars)."""
        settings = Settings()
        assert settings.gemini_api_key == "YOUR_API_KEY_HERE"
        assert settings.openai_api_key == "YOUR_API_KEY_HERE"
        assert settings.google_credentials_file == "~/.google_calendar_credentials.json"
        assert settings.google_token_file == "~/.google_calendar_token.json"

    def test_google_credentials_path_property(self):
        """Test google_credentials_path property expansion."""
        settings = Settings()
        path = settings.google_credentials_path
        assert isinstance(path, Path)
        # Should expand ~ to home directory
        assert "~" not in str(path)

    def test_google_token_path_property(self):
        """Test google_token_path property expansion."""
        settings = Settings()
        path = settings.google_token_path
        assert isinstance(path, Path)
        # Should expand ~ to home directory
        assert "~" not in str(path)

    @patch.dict(
        "os.environ",
        {"GEMINI_API_KEY": "test_gemini_key", "OPENAI_API_KEY": "test_openai_key"},
    )
    def test_settings_from_env_vars(self):
        """Test Settings loading from environment variables."""
        settings = Settings()
        assert settings.gemini_api_key == "test_gemini_key"
        assert settings.openai_api_key == "test_openai_key"


class TestPricingCalculator:
    """Test pricing calculation functionality."""

    # Basic cost calculation test parameters
    basic_cost_params = [
        # Gemini models
        pytest.param(
            "gemini-2.5-flash", 1000, 500, "gemini", 0.00155, id="gemini-flash"
        ),
        pytest.param(
            "gemini-2.5-pro", 2000, 1000, "gemini", 0.0125, id="gemini-pro-low"
        ),
        # OpenAI models
        pytest.param("gpt-4o", 1000, 500, "openai", 0.0075, id="openai-gpt4o"),
        pytest.param(
            "gpt-4o-mini", 2000, 1000, "openai", 0.0009, id="openai-gpt4o-mini"
        ),
        pytest.param("o1-preview", 1000, 500, "openai", 0.045, id="openai-o1-preview"),
        pytest.param("o1-mini", 1000, 500, "openai", 0.009, id="openai-o1-mini"),
        pytest.param("gpt-4.1", 1000, 500, "openai", 0.006, id="openai-gpt41"),
        pytest.param(
            "gpt-4.1-mini", 1000, 500, "openai", 0.0012, id="openai-gpt41-mini"
        ),
    ]

    # Image model test parameters
    image_model_params = [
        pytest.param("dall-e-3", "openai", 2, 0.080, id="dalle3"),
        pytest.param("imagen-3", "gemini", 3, 0.090, id="imagen3"),
    ]

    @pytest.mark.parametrize(
        "model, input_tokens, output_tokens, provider, expected_cost", basic_cost_params
    )
    def test_cost_calculation(
        self, model, input_tokens, output_tokens, provider, expected_cost
    ):
        """Test cost calculation for various models."""
        calc = PricingCalculator()
        cost = calc.calculate_cost(model, input_tokens, output_tokens, provider)
        assert cost == pytest.approx(expected_cost, rel=1e-6)

    @pytest.mark.parametrize(
        "model, provider, num_images, expected_cost", image_model_params
    )
    def test_image_model_pricing(self, model, provider, num_images, expected_cost):
        """Test image model pricing (per image, not per token)."""
        calc = PricingCalculator()
        cost = calc.calculate_cost(model, 0, 0, provider, images_generated=num_images)
        assert cost == expected_cost

    def test_gemini_tiered_pricing_high_usage(self):
        """Test Gemini 2.5 Pro tiered pricing for high token usage."""
        calc = PricingCalculator()

        # Test above 200k tokens (higher tier)
        cost = calc.calculate_cost("gemini-2.5-pro", 300000, 300000, "gemini")
        expected_input = (300000 / 1_000_000) * 2.50  # Above 200k threshold
        expected_output = (300000 / 1_000_000) * 15.00  # Above 200k threshold
        expected = expected_input + expected_output
        assert cost == expected

    def test_gemini_modality_pricing(self):
        """Test Gemini modality-based pricing."""
        calc = PricingCalculator()

        # Test audio input (higher cost)
        cost = calc.calculate_cost(
            "gemini-2.5-flash", 1000, 500, "gemini", input_modality="audio"
        )
        expected = (1000 / 1_000_000) * 1.00 + (
            500 / 1_000_000
        ) * 2.50  # Audio is $1.00 per 1M
        assert cost == expected

        # Test video input (standard cost)
        cost = calc.calculate_cost(
            "gemini-2.5-flash", 1000, 500, "gemini", input_modality="video"
        )
        expected = (1000 / 1_000_000) * 0.30 + (
            500 / 1_000_000
        ) * 2.50  # Video is $0.30 per 1M
        assert cost == expected

    def test_openai_cached_input_pricing(self):
        """Test OpenAI cached input pricing."""
        calc = PricingCalculator()

        # Test model with caching support
        cost = calc.calculate_cost(
            "gpt-4.1", 1000, 500, "openai", cached_input_tokens=200
        )
        expected_input = (1000 / 1_000_000) * 2.00  # Regular input
        expected_cached = (200 / 1_000_000) * 0.50  # Cached input
        expected_output = (500 / 1_000_000) * 8.00  # Output
        expected = expected_input + expected_cached + expected_output
        assert (
            abs(cost - expected) < 1e-10
        )  # Use approximate equality for floating point

    def test_openai_complex_pricing_gpt_image_1(self):
        """Test OpenAI GPT-image-1 complex pricing."""
        calc = PricingCalculator()

        # Test text input with image generation
        cost = calc.calculate_cost(
            "gpt-image-1",
            1000,
            0,
            "openai",
            input_modality="text",
            output_quality="medium",
            images_generated=2,
        )
        expected_text_input = (1000 / 1_000_000) * 5.00  # Text input per 1M
        expected_image_output = 2 * 0.04  # 2 images at medium quality
        expected = expected_text_input + expected_image_output
        assert cost == expected

        # Test image input with high quality output
        cost = calc.calculate_cost(
            "gpt-image-1",
            500,
            0,
            "openai",
            input_modality="image",
            output_quality="high",
            images_generated=1,
            cached_input_tokens=100,
        )
        expected_image_input = (500 / 1_000_000) * 10.00  # Image input per 1M
        expected_cached_image = (100 / 1_000_000) * 2.50  # Cached image input
        expected_image_output = 1 * 0.17  # 1 image at high quality
        expected = expected_image_input + expected_cached_image + expected_image_output
        assert cost == expected

    def test_gemini_video_generation_pricing(self):
        """Test Gemini video generation per-second pricing."""
        calc = PricingCalculator()

        # Test veo-2 video model
        cost = calc.calculate_cost("veo-2", 0, 0, "gemini", seconds_generated=10)
        expected = 10 * 0.35  # 10 seconds at $0.35 per second
        assert cost == expected

    def test_model_name_normalization(self):
        """Test that invalid model names now raise errors instead of returning 0."""
        calc = PricingCalculator()

        # Test invalid model names now raise ValueError
        with pytest.raises(
            ValueError, match="Model 'flash' not found in pricing config"
        ):
            calc.calculate_cost("flash", 1000, 500, "gemini")

        with pytest.raises(ValueError, match="Model 'pro' not found in pricing config"):
            calc.calculate_cost("pro", 1000, 500, "gemini")

        # Test valid model name works
        cost = calc.calculate_cost("gemini-2.5-flash", 1000, 500, "gemini")
        assert cost > 0

    def test_unknown_model_raises_error(self):
        """Test unknown model raises ValueError instead of returning zero."""
        calc = PricingCalculator()

        with pytest.raises(
            ValueError,
            match="Model 'unknown-model' not found in pricing config for provider 'gemini'",
        ):
            calc.calculate_cost("unknown-model", 1000, 500, "gemini")

        with pytest.raises(
            ValueError,
            match="Model 'unknown-model' not found in pricing config for provider 'openai'",
        ):
            calc.calculate_cost("unknown-model", 1000, 500, "openai")

    def test_format_cost_precision(self):
        """Test cost formatting with different precision levels."""
        calc = PricingCalculator()

        # Very small cost (< 0.01)
        formatted = calc.format_cost(0.0005)
        assert formatted == "$0.0005"

        # Small cost (< 0.01)
        formatted = calc.format_cost(0.005)
        assert formatted == "$0.0050"

        # Regular cost (>= 0.01)
        formatted = calc.format_cost(0.25)
        assert formatted == "$0.25"

        # Large cost
        formatted = calc.format_cost(15.789)
        assert formatted == "$15.79"

    def test_format_usage_summary(self):
        """Test usage summary formatting."""
        calc = PricingCalculator()

        # format_usage only takes tokens and cost, not model/provider
        summary = calc.format_usage(1000, 500, 0.01)

        assert "1,000 tokens" in summary  # input tokens
        assert "↑1,000" in summary  # input tokens
        assert "↓500" in summary  # output tokens

    def test_pricing_error_scenarios(self):
        """Test pricing calculation error scenarios now raise exceptions."""
        calc = PricingCalculator()

        # Test invalid provider (should raise FileNotFoundError)
        with pytest.raises(FileNotFoundError):
            calc.calculate_cost("gemini-2.5-flash", 1000, 500, "invalid_provider")

        # Test model not in config (should raise ValueError)
        with pytest.raises(
            ValueError, match="Model 'nonexistent-model' not found in pricing config"
        ):
            calc.calculate_cost("nonexistent-model", 1000, 500, "gemini")

    def test_global_functions(self):
        """Test global pricing functions for backward compatibility."""
        # Test global calculate_cost function
        cost = calculate_cost("gemini-2.5-flash", 1000, 500, "gemini")
        assert cost > 0

        # Test global format_usage function
        summary = format_usage(1000, 500, 0.01)
        assert "1,000 tokens" in summary
        assert "≈$0.01" in summary

    def test_zero_cost_formatting(self):
        """Test zero cost formatting."""
        calc = PricingCalculator()

        formatted = calc.format_cost(0.0)
        assert formatted == "$0.00"

    def test_edge_case_pricing_scenarios(self):
        """Test edge cases in pricing calculation."""
        calc = PricingCalculator()

        # Test zero tokens
        cost = calc.calculate_cost("gemini-2.5-flash", 0, 0, "gemini")
        assert cost == 0.0

        # Test only input tokens
        cost = calc.calculate_cost("gemini-2.5-flash", 1000, 0, "gemini")
        expected = (1000 / 1_000_000) * 0.30  # Only input cost
        assert cost == expected

        # Test only output tokens
        cost = calc.calculate_cost("gemini-2.5-flash", 0, 500, "gemini")
        expected = (500 / 1_000_000) * 2.50  # Only output cost
        assert cost == expected

    def test_convenience_functions(self):
        """Test convenience functions."""
        # Test calculate_cost function
        cost1 = calculate_cost("gemini-2.5-flash", 1000, 500, "gemini")
        cost2 = PricingCalculator.calculate_cost(
            "gemini-2.5-flash", 1000, 500, "gemini"
        )
        assert cost1 == cost2

        # Test format_usage function
        usage1 = format_usage(1000, 500, 0.01)
        usage2 = PricingCalculator.format_usage(1000, 500, 0.01)
        assert usage1 == usage2
