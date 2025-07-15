"""Cost tracking and pricing utilities for LLM usage."""

from pathlib import Path
from typing import Any

import yaml


class PricingCalculator:
    """Calculates costs for various LLM models using YAML-based pricing configurations."""

    @classmethod
    def _load_pricing_config(cls, provider: str) -> dict[str, Any]:
        """Load pricing configuration from unified model YAML file."""
        current_dir = Path(__file__).parent
        models_file = current_dir.parent / "llm" / provider / "models.yaml"

        with open(models_file, encoding="utf-8") as f:
            return yaml.safe_load(f)

    @classmethod
    def calculate_cost(
        cls,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        provider: str = "gemini",
        input_modality: str = "text",
        output_quality: str = "medium",
        cached_input_tokens: int = 0,
        images_generated: int = 0,
        seconds_generated: int = 0,
    ) -> float:
        """Calculate cost using YAML-based pricing configurations."""
        config = cls._load_pricing_config(provider)

        models = config.get("models", {})
        if model not in models:
            raise ValueError(
                f"Model '{model}' not found in pricing config for provider '{provider}'"
            )

        model_config = models[model]
        total_cost = 0.0

        pricing_type = model_config.get("pricing_type")

        if pricing_type == "per_image":
            price_per_image = model_config.get("price_per_image", 0.0)
            return images_generated * price_per_image

        elif pricing_type == "per_second":
            price_per_second = model_config.get("price_per_second", 0.0)
            return seconds_generated * price_per_second

        elif "input_tiers" in model_config:
            for tier in model_config["input_tiers"]:
                threshold = (
                    float("inf") if tier["threshold"] == ".inf" else tier["threshold"]
                )
                if input_tokens <= threshold:
                    total_cost += (input_tokens / 1_000_000) * tier["price"]
                    break

            for tier in model_config.get("output_tiers", []):
                threshold = (
                    float("inf") if tier["threshold"] == ".inf" else tier["threshold"]
                )
                if output_tokens <= threshold:
                    total_cost += (output_tokens / 1_000_000) * tier["price"]
                    break

        elif "input_by_modality" in model_config:
            modality_price = model_config["input_by_modality"].get(input_modality, 0.30)
            total_cost += (input_tokens / 1_000_000) * modality_price
            total_cost += (output_tokens / 1_000_000) * model_config.get(
                "output_per_1m", 0.0
            )

        elif pricing_type == "complex":
            if model == "gpt-image-1":
                if input_modality == "text":
                    total_cost += (input_tokens / 1_000_000) * model_config[
                        "text_input_per_1m"
                    ]
                    total_cost += (cached_input_tokens / 1_000_000) * model_config[
                        "cached_text_input_per_1m"
                    ]
                elif input_modality == "image":
                    total_cost += (input_tokens / 1_000_000) * model_config[
                        "image_input_per_1m"
                    ]
                    total_cost += (cached_input_tokens / 1_000_000) * model_config[
                        "cached_image_input_per_1m"
                    ]

                if images_generated > 0:
                    image_pricing = model_config["image_output_pricing"]
                    per_image_cost = image_pricing.get(output_quality, 0.04)
                    total_cost += images_generated * per_image_cost

        else:
            input_price = model_config.get("input_per_1m", 0.0)
            output_price = model_config.get("output_per_1m", 0.0)

            total_cost += (input_tokens / 1_000_000) * input_price
            total_cost += (output_tokens / 1_000_000) * output_price

            if cached_input_tokens > 0 and "cached_input_per_1m" in model_config:
                cached_price = model_config["cached_input_per_1m"]
                total_cost += (cached_input_tokens / 1_000_000) * cached_price

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
def calculate_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    provider: str = "gemini",
    **kwargs,
) -> float:
    """Global function that delegates to PricingCalculator.calculate_cost."""
    return PricingCalculator.calculate_cost(
        model, input_tokens, output_tokens, provider, **kwargs
    )


def format_usage(input_tokens: int, output_tokens: int, cost: float) -> str:
    """Global function that delegates to PricingCalculator.format_usage."""
    return PricingCalculator.format_usage(input_tokens, output_tokens, cost)
