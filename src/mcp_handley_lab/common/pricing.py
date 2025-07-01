"""Cost tracking and pricing utilities for LLM usage."""
import yaml
from pathlib import Path
from typing import Dict, Tuple, Union, Optional, Any


class PricingCalculator:
    """Calculates costs for various LLM models using YAML-based pricing configurations."""
    
    @classmethod
    def _load_pricing_config(cls, provider: str) -> Dict[str, Any]:
        """Load pricing configuration from YAML file."""
        # Look for pricing files in the project root directory
        current_dir = Path(__file__).parent
        pricing_file = None
        
        # Search up the directory tree for the pricing file
        for path in [current_dir] + list(current_dir.parents):
            potential_file = path / f"pricing-{provider}.yaml"
            if potential_file.exists():
                pricing_file = potential_file
                break
        
        if not pricing_file:
            return {}
            
        try:
            with open(pricing_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Failed to load pricing for {provider}: {e}")
            return {}
    
    @classmethod  
    def calculate_cost(
        cls,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        provider: str = "gemini",
        # Extended parameters for complex pricing
        input_modality: str = "text",
        output_quality: str = "medium", 
        cached_input_tokens: int = 0,
        images_generated: int = 0,
        seconds_generated: int = 0
    ) -> float:
        """Calculate cost using YAML-based pricing configurations."""
        # Load pricing config for provider
        config = cls._load_pricing_config(provider)
        if not config:
            return 0.0
            
        models = config.get("models", {})
        if model not in models:
            return 0.0
            
        model_config = models[model]
        total_cost = 0.0
        
        # Handle different pricing types
        pricing_type = model_config.get("pricing_type")
        
        if pricing_type == "per_image":
            # Image generation models
            price_per_image = model_config.get("price_per_image", 0.0)
            return images_generated * price_per_image
            
        elif pricing_type == "per_second":
            # Video generation models
            price_per_second = model_config.get("price_per_second", 0.0)
            return seconds_generated * price_per_second
            
        elif "input_tiers" in model_config:
            # Tiered pricing (e.g., Gemini 2.5 Pro)
            for tier in model_config["input_tiers"]:
                threshold = float("inf") if tier["threshold"] == ".inf" else tier["threshold"]
                if input_tokens <= threshold:
                    total_cost += (input_tokens / 1_000_000) * tier["price"]
                    break
                    
            for tier in model_config.get("output_tiers", []):
                threshold = float("inf") if tier["threshold"] == ".inf" else tier["threshold"]
                if output_tokens <= threshold:
                    total_cost += (output_tokens / 1_000_000) * tier["price"]
                    break
                    
        elif "input_by_modality" in model_config:
            # Modality-specific pricing (e.g., Gemini Flash)
            modality_price = model_config["input_by_modality"].get(input_modality, 0.30)
            total_cost += (input_tokens / 1_000_000) * modality_price
            total_cost += (output_tokens / 1_000_000) * model_config.get("output_per_1m", 0.0)
            
        else:
            # Standard per-token pricing
            input_price = model_config.get("input_per_1m", 0.0)
            output_price = model_config.get("output_per_1m", 0.0)
            
            total_cost += (input_tokens / 1_000_000) * input_price
            total_cost += (output_tokens / 1_000_000) * output_price
            
            # Add cached input pricing if supported
            if cached_input_tokens > 0 and "cached_input_per_1m" in model_config:
                cached_price = model_config["cached_input_per_1m"]
                total_cost += (cached_input_tokens / 1_000_000) * cached_price
                
        # Handle complex models with special pricing (e.g., GPT-image-1)
        complex_models = config.get("complex_models", {})
        if model in complex_models:
            complex_config = complex_models[model]
            
            if model == "gpt-image-1":
                # Handle GPT-image-1 special pricing
                if input_modality == "text":
                    total_cost += (input_tokens / 1_000_000) * complex_config["text_input_per_1m"]
                    total_cost += (cached_input_tokens / 1_000_000) * complex_config["cached_text_input_per_1m"]
                elif input_modality == "image":
                    total_cost += (input_tokens / 1_000_000) * complex_config["image_input_per_1m"]
                    total_cost += (cached_input_tokens / 1_000_000) * complex_config["cached_image_input_per_1m"]
                
                # Add per-image output cost
                if images_generated > 0:
                    image_pricing = complex_config["image_output_pricing"]
                    per_image_cost = image_pricing.get(output_quality, 0.04)
                    total_cost += images_generated * per_image_cost
                    
        return total_cost
    
    @classmethod
    def format_cost(cls, cost: float) -> str:
        """Format cost for display."""
        if cost == 0:
            return "$0.00"
        elif cost < 0.01:
            return f"${cost:.4f}"
        else:
            return f"${cost:.2f}"
    
    @classmethod
    def format_usage(cls, input_tokens: int, output_tokens: int, cost: float) -> str:
        """Format usage summary for display."""
        return f"{input_tokens:,} tokens (↑{input_tokens:,}/↓{output_tokens:,}) ≈{cls.format_cost(cost)}"


# Global function for backward compatibility
def calculate_cost(model: str, input_tokens: int = 0, output_tokens: int = 0, provider: str = "gemini", **kwargs) -> float:
    """Global function that delegates to PricingCalculator.calculate_cost."""
    return PricingCalculator.calculate_cost(model, input_tokens, output_tokens, provider, **kwargs)


def format_usage(input_tokens: int, output_tokens: int, cost: float) -> str:
    """Global function that delegates to PricingCalculator.format_usage."""
    return PricingCalculator.format_usage(input_tokens, output_tokens, cost)