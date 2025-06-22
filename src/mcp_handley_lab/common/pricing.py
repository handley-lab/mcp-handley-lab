"""Cost tracking and pricing utilities for LLM usage."""
from typing import Dict, Tuple


class PricingCalculator:
    """Calculates costs for various LLM models."""
    
    # Pricing per 1M tokens (input/output) as of January 2025
    GEMINI_PRICING = {
        "gemini-1.5-flash": (0.075, 0.30),      # flash model
        "gemini-1.5-pro": (1.25, 5.00),         # pro model
        "gemini-1.5-flash-8b": (0.0375, 0.15),  # flash-8b model
    }
    
    OPENAI_PRICING = {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.150, 0.600),
        "gpt-4-turbo": (10.00, 30.00),
        "gpt-4": (30.00, 60.00),
        "gpt-3.5-turbo": (0.50, 1.50),
        "o1": (15.00, 60.00),
        "o1-mini": (3.00, 12.00),
        "o1-preview": (15.00, 60.00),
        "chatgpt-4o": (5.00, 15.00),
        "dall-e-3": (0.040, 0.040),  # per image (1024x1024 standard)
        "dall-e-2": (0.020, 0.020),  # per image (1024x1024)
    }
    
    @classmethod
    def calculate_cost(
        self, 
        model: str, 
        input_tokens: int = 0, 
        output_tokens: int = 0,
        provider: str = "gemini"
    ) -> float:
        """Calculate cost for token usage."""
        pricing_table = self.GEMINI_PRICING if provider == "gemini" else self.OPENAI_PRICING
        
        # Normalize model names
        if provider == "gemini":
            if model in ["flash", "gemini-flash"]:
                model = "gemini-1.5-flash"
            elif model in ["pro", "gemini-pro"]:
                model = "gemini-1.5-pro"
        
        if model not in pricing_table:
            return 0.0
        
        input_price_per_1m, output_price_per_1m = pricing_table[model]
        
        input_cost = (input_tokens / 1_000_000) * input_price_per_1m
        output_cost = (output_tokens / 1_000_000) * output_price_per_1m
        
        return input_cost + output_cost
    
    @classmethod
    def format_cost(self, cost: float) -> str:
        """Format cost for display."""
        if cost < 0.001:
            return f"${cost:.6f}"
        elif cost < 0.01:
            return f"${cost:.4f}"
        else:
            return f"${cost:.2f}"
    
    @classmethod
    def format_usage_summary(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        provider: str = "gemini"
    ) -> str:
        """Format a usage and cost summary."""
        total_tokens = input_tokens + output_tokens
        cost_str = self.format_cost(cost)
        
        arrow_up = "↑"
        arrow_down = "↓"
        
        return f"💰 Usage: {total_tokens:,} tokens ({arrow_up}{input_tokens:,}/{arrow_down}{output_tokens:,}) ≈{cost_str}"


def calculate_cost(model: str, input_tokens: int = 0, output_tokens: int = 0, provider: str = "gemini") -> float:
    """Convenience function for calculating costs."""
    return PricingCalculator.calculate_cost(model, input_tokens, output_tokens, provider)


def format_usage(model: str, input_tokens: int, output_tokens: int, cost: float, provider: str = "gemini") -> str:
    """Convenience function for formatting usage summaries."""
    return PricingCalculator.format_usage_summary(model, input_tokens, output_tokens, cost, provider)