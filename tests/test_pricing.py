"""Unit tests for pricing calculation system."""
import pytest

from mcp_framework.common.pricing import PricingCalculator, calculate_cost, format_usage


class TestPricingCalculator:
    """Test cases for PricingCalculator class."""
    
    def test_gemini_flash_pricing(self):
        """Test Gemini Flash pricing calculation."""
        cost = PricingCalculator.calculate_cost(
            "flash", 
            input_tokens=1000, 
            output_tokens=500, 
            provider="gemini"
        )
        
        # Expected: (1000/1M * 0.075) + (500/1M * 0.30) = 0.000075 + 0.00015 = 0.000225
        expected = 0.000225
        assert abs(cost - expected) < 0.000001
    
    def test_gemini_pro_pricing(self):
        """Test Gemini Pro pricing calculation."""
        cost = PricingCalculator.calculate_cost(
            "pro", 
            input_tokens=2000, 
            output_tokens=1000, 
            provider="gemini"
        )
        
        # Expected: (2000/1M * 1.25) + (1000/1M * 5.00) = 0.0025 + 0.005 = 0.0075
        expected = 0.0075
        assert abs(cost - expected) < 0.000001
    
    def test_openai_gpt4o_pricing(self):
        """Test OpenAI GPT-4o pricing calculation."""
        cost = PricingCalculator.calculate_cost(
            "gpt-4o", 
            input_tokens=1000, 
            output_tokens=500, 
            provider="openai"
        )
        
        # Expected: (1000/1M * 2.50) + (500/1M * 10.00) = 0.0025 + 0.005 = 0.0075
        expected = 0.0075
        assert abs(cost - expected) < 0.000001
    
    def test_openai_gpt4o_mini_pricing(self):
        """Test OpenAI GPT-4o-mini pricing calculation."""
        cost = PricingCalculator.calculate_cost(
            "gpt-4o-mini", 
            input_tokens=10000, 
            output_tokens=5000, 
            provider="openai"
        )
        
        # Expected: (10000/1M * 0.150) + (5000/1M * 0.600) = 0.0015 + 0.003 = 0.0045
        expected = 0.0045
        assert abs(cost - expected) < 0.000001
    
    def test_unknown_model_pricing(self):
        """Test unknown model returns zero cost."""
        cost = PricingCalculator.calculate_cost(
            "unknown-model", 
            input_tokens=1000, 
            output_tokens=500, 
            provider="gemini"
        )
        
        assert cost == 0.0
    
    def test_zero_tokens_pricing(self):
        """Test zero tokens returns zero cost."""
        cost = PricingCalculator.calculate_cost(
            "flash", 
            input_tokens=0, 
            output_tokens=0, 
            provider="gemini"
        )
        
        assert cost == 0.0
    
    def test_gemini_model_normalization(self):
        """Test Gemini model name normalization."""
        # Test flash normalization
        cost1 = PricingCalculator.calculate_cost("flash", 1000, 500, "gemini")
        cost2 = PricingCalculator.calculate_cost("gemini-flash", 1000, 500, "gemini")
        cost3 = PricingCalculator.calculate_cost("gemini-1.5-flash", 1000, 500, "gemini")
        
        assert cost1 == cost2 == cost3
        
        # Test pro normalization
        cost4 = PricingCalculator.calculate_cost("pro", 1000, 500, "gemini")
        cost5 = PricingCalculator.calculate_cost("gemini-pro", 1000, 500, "gemini")
        cost6 = PricingCalculator.calculate_cost("gemini-1.5-pro", 1000, 500, "gemini")
        
        assert cost4 == cost5 == cost6
    
    def test_format_cost_very_small(self):
        """Test formatting very small costs."""
        formatted = PricingCalculator.format_cost(0.000123)
        assert formatted == "$0.000123"
    
    def test_format_cost_small(self):
        """Test formatting small costs."""
        formatted = PricingCalculator.format_cost(0.0045)
        assert formatted == "$0.0045"
    
    def test_format_cost_normal(self):
        """Test formatting normal costs."""
        formatted = PricingCalculator.format_cost(1.234)
        assert formatted == "$1.23"
    
    def test_format_cost_large(self):
        """Test formatting large costs."""
        formatted = PricingCalculator.format_cost(123.456)
        assert formatted == "$123.46"
    
    def test_format_usage_summary_gemini(self):
        """Test formatting usage summary for Gemini."""
        summary = PricingCalculator.format_usage_summary(
            "flash", 1500, 800, 0.0035, "gemini"
        )
        
        assert "2,300 tokens" in summary
        assert "↑1,500/↓800" in summary
        assert "$0.0035" in summary
        assert "💰 Usage:" in summary
    
    def test_format_usage_summary_openai(self):
        """Test formatting usage summary for OpenAI."""
        summary = PricingCalculator.format_usage_summary(
            "gpt-4o", 2000, 1000, 0.0075, "openai"
        )
        
        assert "3,000 tokens" in summary
        assert "↑2,000/↓1,000" in summary
        assert "$0.0075" in summary
        assert "💰 Usage:" in summary
    
    def test_large_token_counts(self):
        """Test formatting with large token counts."""
        summary = PricingCalculator.format_usage_summary(
            "pro", 1500000, 800000, 3.15, "gemini"
        )
        
        assert "2,300,000 tokens" in summary
        assert "↑1,500,000/↓800,000" in summary
        assert "$3.15" in summary


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_calculate_cost_function(self):
        """Test calculate_cost convenience function."""
        cost = calculate_cost("flash", 1000, 500, "gemini")
        expected = 0.000225
        assert abs(cost - expected) < 0.000001
    
    def test_format_usage_function(self):
        """Test format_usage convenience function."""
        summary = format_usage("gpt-4o", 1000, 500, 0.0075, "openai")
        
        assert "1,500 tokens" in summary
        assert "↑1,000/↓500" in summary
        assert "$0.0075" in summary
        assert "💰 Usage:" in summary
    
    def test_default_provider_gemini(self):
        """Test default provider is Gemini."""
        cost1 = calculate_cost("flash", 1000, 500)  # Default provider
        cost2 = calculate_cost("flash", 1000, 500, "gemini")  # Explicit provider
        
        assert cost1 == cost2
    
    def test_edge_case_pricing(self):
        """Test edge cases in pricing."""
        # Very large token counts
        cost = calculate_cost("flash", 10_000_000, 5_000_000, "gemini")
        assert cost > 0
        
        # Single token
        cost = calculate_cost("flash", 1, 1, "gemini")
        assert cost > 0
        assert cost < 0.001


class TestPricingAccuracy:
    """Test pricing accuracy against known values."""
    
    def test_gemini_flash_1m_tokens(self):
        """Test Gemini Flash with exactly 1M tokens."""
        cost = calculate_cost("flash", 1_000_000, 1_000_000, "gemini")
        expected = 0.075 + 0.30  # $0.375
        assert abs(cost - expected) < 0.000001
    
    def test_gemini_pro_1m_tokens(self):
        """Test Gemini Pro with exactly 1M tokens."""
        cost = calculate_cost("pro", 1_000_000, 1_000_000, "gemini")
        expected = 1.25 + 5.00  # $6.25
        assert abs(cost - expected) < 0.000001
    
    def test_openai_gpt4o_1m_tokens(self):
        """Test OpenAI GPT-4o with exactly 1M tokens."""
        cost = calculate_cost("gpt-4o", 1_000_000, 1_000_000, "openai")
        expected = 2.50 + 10.00  # $12.50
        assert abs(cost - expected) < 0.000001
    
    def test_realistic_conversation_cost(self):
        """Test realistic conversation token usage."""
        # Typical conversation: ~500 input tokens, ~300 output tokens
        cost_flash = calculate_cost("flash", 500, 300, "gemini")
        cost_pro = calculate_cost("pro", 500, 300, "gemini")
        cost_gpt4o = calculate_cost("gpt-4o", 500, 300, "openai")
        
        # Flash should be cheapest, Pro middle, GPT-4o most expensive
        assert cost_flash < cost_pro < cost_gpt4o
        assert cost_flash < 0.001  # Should be very cheap
        assert cost_gpt4o > 0.003  # Should be more expensive