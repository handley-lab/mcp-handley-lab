"""Unit tests for common modules (config and pricing)."""
import pytest
from pathlib import Path
from unittest.mock import patch

from mcp_handley_lab.common.config import Settings
from mcp_handley_lab.common.pricing import PricingCalculator, calculate_cost, format_usage


class TestConfig:
    """Test configuration functionality."""
    
    @patch.dict('os.environ', {}, clear=True)
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
    
    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test_gemini_key', 'OPENAI_API_KEY': 'test_openai_key'})
    def test_settings_from_env_vars(self):
        """Test Settings loading from environment variables."""
        settings = Settings()
        assert settings.gemini_api_key == 'test_gemini_key'
        assert settings.openai_api_key == 'test_openai_key'


class TestPricingCalculator:
    """Test pricing calculation functionality."""
    
    def test_gemini_cost_calculation(self):
        """Test Gemini cost calculation."""
        calc = PricingCalculator()
        
        # Test flash model
        cost = calc.calculate_cost("gemini-2.5-flash", 1000, 500, "gemini")
        expected = (1000 / 1_000_000) * 0.30 + (500 / 1_000_000) * 2.50
        assert cost == expected
        
        # Test pro model (under 200k tokens - lower tier)
        cost = calc.calculate_cost("gemini-2.5-pro", 2000, 1000, "gemini")
        expected = (2000 / 1_000_000) * 1.25 + (1000 / 1_000_000) * 10.00
        assert cost == expected
    
    def test_openai_cost_calculation(self):
        """Test OpenAI cost calculation."""
        calc = PricingCalculator()
        
        # Test gpt-4o
        cost = calc.calculate_cost("gpt-4o", 1000, 500, "openai")
        expected = (1000 / 1_000_000) * 2.50 + (500 / 1_000_000) * 10.00
        assert cost == expected
        
        # Test gpt-4o-mini
        cost = calc.calculate_cost("gpt-4o-mini", 2000, 1000, "openai")
        expected = (2000 / 1_000_000) * 0.150 + (1000 / 1_000_000) * 0.600
        assert cost == expected
    
    def test_image_model_pricing(self):
        """Test image model pricing (per image, not per token)."""
        calc = PricingCalculator()
        
        # Test DALL-E with images_generated parameter
        cost = calc.calculate_cost("dall-e-3", 0, 0, "openai", images_generated=2)  # 2 images
        assert cost == 2 * 0.040
        
        # Test Imagen with images_generated parameter
        cost = calc.calculate_cost("imagen-3", 0, 0, "gemini", images_generated=3)  # 3 images
        assert cost == 3 * 0.030
    
    def test_model_name_normalization(self):
        """Test that invalid model names return 0 cost."""
        calc = PricingCalculator()
        
        # Test invalid model names return 0
        cost = calc.calculate_cost("flash", 1000, 500, "gemini")
        assert cost == 0.0
        
        # Test invalid model names return 0
        cost = calc.calculate_cost("pro", 1000, 500, "gemini")
        assert cost == 0.0
        
        # Test valid model name works
        cost = calc.calculate_cost("gemini-2.5-flash", 1000, 500, "gemini")
        assert cost > 0
    
    def test_unknown_model_returns_zero(self):
        """Test unknown model returns zero cost."""
        calc = PricingCalculator()
        
        cost = calc.calculate_cost("unknown-model", 1000, 500, "gemini")
        assert cost == 0.0
        
        cost = calc.calculate_cost("unknown-model", 1000, 500, "openai")
        assert cost == 0.0
    
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
        assert "↑1,000" in summary        # input tokens
        assert "↓500" in summary          # output tokens
        assert "$0.01" in summary         # cost
    
    def test_convenience_functions(self):
        """Test convenience functions."""
        # Test calculate_cost function
        cost1 = calculate_cost("gemini-2.5-flash", 1000, 500, "gemini")
        cost2 = PricingCalculator.calculate_cost("gemini-2.5-flash", 1000, 500, "gemini")
        assert cost1 == cost2
        
        # Test format_usage function
        usage1 = format_usage(1000, 500, 0.01)
        usage2 = PricingCalculator.format_usage(1000, 500, 0.01)
        assert usage1 == usage2
    
    def test_o1_model_pricing(self):
        """Test o1 model pricing."""
        calc = PricingCalculator()
        
        # Test o1-preview
        cost = calc.calculate_cost("o1-preview", 1000, 500, "openai")
        expected = (1000 / 1_000_000) * 15.00 + (500 / 1_000_000) * 60.00
        assert cost == expected
        
        # Test o1-mini
        cost = calc.calculate_cost("o1-mini", 1000, 500, "openai")
        expected = (1000 / 1_000_000) * 3.00 + (500 / 1_000_000) * 12.00
        assert cost == expected
    
    def test_gpt41_model_pricing(self):
        """Test GPT-4.1 model pricing."""
        calc = PricingCalculator()
        
        # Test gpt-4.1
        cost = calc.calculate_cost("gpt-4.1", 1000, 500, "openai")
        expected = (1000 / 1_000_000) * 2.00 + (500 / 1_000_000) * 8.00
        assert cost == expected
        
        # Test gpt-4.1-mini
        cost = calc.calculate_cost("gpt-4.1-mini", 1000, 500, "openai")
        expected = (1000 / 1_000_000) * 0.40 + (500 / 1_000_000) * 1.60
        assert cost == expected