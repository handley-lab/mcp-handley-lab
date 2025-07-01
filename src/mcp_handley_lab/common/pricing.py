"""Cost tracking and pricing utilities for LLM usage."""
from typing import Dict, Tuple


class PricingCalculator:
    """Calculates costs for various LLM models."""
    
    PRICING_TABLES = {
        "claude": {
            # Claude 4 models (prices per 1M tokens - Input, Output)
            "claude-opus-4": (15.00, 75.00),
            "claude-sonnet-4": (3.00, 15.00),
            "claude-sonnet-3.7": (3.00, 15.00),
            
            # Claude 3.5 models 
            "claude-3-5-sonnet-20241022": (3.00, 15.00),
            "claude-3-5-sonnet-20240620": (3.00, 15.00),
            "claude-3-5-haiku-20241022": (0.80, 4.00),
            
            # Claude 3 models (legacy)
            "claude-3-opus-20240229": (15.00, 75.00),
            "claude-3-sonnet-20240229": (3.00, 15.00),
            "claude-3-haiku-20240307": (0.25, 1.25),
        },
        "gemini": {
            # Gemini 2.5 models (updated pricing - ≤200k tokens, paid tier)
            "gemini-2.5-pro": (1.25, 10.00),        # Input $1.25, Output $10 per 1M tokens
            "gemini-2.5-flash": (0.30, 2.50),       # Input $0.30, Output $2.50 per 1M tokens
            "gemini-2.5-flash-lite": (0.10, 0.40),  # Input $0.10, Output $0.40 per 1M tokens
            
            # Gemini 1.5 models (≤128k tokens, paid tier)
            "gemini-1.5-pro": (1.25, 5.00),         # Input $1.25, Output $5.00 per 1M tokens
            "gemini-1.5-flash": (0.075, 0.30),      # Input $0.075, Output $0.30 per 1M tokens
            "gemini-1.5-flash-8b": (0.0375, 0.15),  # Legacy pricing
            
            # Image generation (Imagen 4)
            "imagen-4": (0.040, 0.040),             # Standard image per image
            "imagen-4-ultra": (0.060, 0.060),       # Ultra image per image
            "imagen-3": (0.040, 0.040),             # Legacy Imagen 3
        },
        "openai": {
            # Official pricing from https://platform.openai.com/docs/pricing (2025)
            
            # GPT-4.1 Series (Latest models)
            "gpt-4.1": (2.00, 8.00),        # Smartest model for complex tasks
            "gpt-4.1-mini": (0.40, 1.60),   # Affordable model balancing speed and intelligence
            "gpt-4.1-nano": (0.10, 0.40),   # Fastest, most cost-effective model
            
            # Reasoning Models
            "o3": (2.00, 8.00),             # Most powerful reasoning model
            "o4-mini": (1.10, 4.40),        # Faster, cost-efficient reasoning model
            
            # GPT-4o models (current pricing)
            "gpt-4o": (5.00, 20.00),        # Updated pricing
            "gpt-4o-mini": (0.60, 2.40),    # Updated pricing
            "gpt-4o-2024-11-20": (5.00, 20.00),
            "gpt-4o-2024-08-06": (5.00, 20.00),
            "gpt-4o-mini-2024-07-18": (0.60, 2.40),
            
            # Legacy GPT-4 models
            "gpt-4-turbo": (10.00, 30.00),
            "gpt-4": (30.00, 60.00),
            "gpt-3.5-turbo": (0.50, 1.50),
            
            # Legacy reasoning models
            "o1": (15.00, 60.00),
            "o1-mini": (3.00, 12.00),
            "o1-preview": (15.00, 60.00),
            
            # Image generation models
            "gpt-image-1": (5.00, 40.00),   # New image generation model (text input, image output)
            "dall-e-3": (0.040, 0.040),     # per image (legacy)
            "dall-e-3-hd": (0.080, 0.080),  # per image (legacy)
            "dall-e-2": (0.020, 0.020),     # per image (legacy)
        }
    }
    
    MODEL_ALIASES = {
        "claude": {
            "opus": "claude-3-opus-20240229",
            "sonnet": "claude-3-5-sonnet-20240620",
            "haiku": "claude-3-5-haiku-20241022",
        },
        "gemini": {
            "flash": "gemini-2.5-flash",
            "gemini-flash": "gemini-2.5-flash",
            "pro": "gemini-2.5-pro",
            "gemini-pro": "gemini-2.5-pro",
            "image": "imagen-3",
        },
        "openai": {}
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
        # Fail fast if provider is unknown
        pricing_table = self.PRICING_TABLES[provider]
        aliases = self.MODEL_ALIASES.get(provider, {})
        
        # Resolve alias
        model = aliases.get(model, model)
        
        # Return zero cost for unknown models
        if model not in pricing_table:
            return 0.0
            
        input_price_per_1m, output_price_per_1m = pricing_table[model]
        
        # Image models (DALL-E, Imagen) use per-image pricing
        if model.startswith("dall-e") or model.startswith("imagen"):
            # For image models, input_tokens represents number of images
            # Price is per image, not per 1M tokens
            return input_tokens * input_price_per_1m
        
        # Text models use per-token pricing
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