"""Utility for loading model configurations from YAML files."""

from pathlib import Path
from typing import Any

import yaml


def load_model_config(provider: str) -> dict[str, Any]:
    """Load model configuration from YAML file for a specific provider.

    Args:
        provider: Provider name ('openai', 'claude', 'gemini')

    Returns:
        Dictionary containing models, display_categories, default_model, and usage_notes

    Raises:
        FileNotFoundError: If YAML file doesn't exist
        yaml.YAMLError: If YAML file is invalid
        ValueError: If required sections are missing
    """
    yaml_path = Path(__file__).parent / "providers" / provider / "models.yaml"

    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    required_sections = ["models", "display_categories", "default_model", "usage_notes"]
    missing_sections = [
        section for section in required_sections if section not in config
    ]
    if missing_sections:
        raise ValueError(f"Missing required sections: {missing_sections}")

    return config


def get_models_by_tags(
    config: dict[str, Any],
    required_tags: list[str],
    exclude_tags: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Filter models by tags.

    Args:
        config: Model configuration dictionary
        required_tags: Models must have ALL of these tags
        exclude_tags: Models must have NONE of these tags

    Returns:
        Dictionary of model_id -> model_config for matching models
    """
    exclude_tags = exclude_tags or []
    matching_models = {}

    for model_id, model_config in config["models"].items():
        model_tags = set(model_config.get("tags", []))

        if not all(tag in model_tags for tag in required_tags):
            continue

        if any(tag in model_tags for tag in exclude_tags):
            continue

        matching_models[model_id] = model_config

    return matching_models


def build_model_configs_dict(provider: str) -> dict[str, dict[str, Any]]:
    """Build MODEL_CONFIGS dictionary from YAML configuration.

    Args:
        provider: Provider name ('openai', 'claude', 'gemini')

    Returns:
        Dictionary compatible with existing MODEL_CONFIGS format
    """
    config = load_model_config(provider)
    model_configs = {}

    for model_id, model_info in config["models"].items():
        if provider == "openai":
            if model_info.get("pricing_type") == "per_image":
                model_configs[model_id] = {
                    "output_tokens": None,
                    "param": None,
                }
            else:
                if "output_tokens" not in model_info:
                    raise ValueError(
                        f"Missing 'output_tokens' for OpenAI model {model_id}"
                    )
                if "param" not in model_info:
                    raise ValueError(f"Missing 'param' for OpenAI model {model_id}")
                model_configs[model_id] = {
                    "output_tokens": model_info["output_tokens"],
                    "param": model_info["param"],
                    "supports_temperature": model_info.get(
                        "supports_temperature", True
                    ),
                    "supports_reasoning": model_info.get("supports_reasoning", False),
                    "supports_verbosity": model_info.get("supports_verbosity", False),
                    "requires_web_search": model_info.get("requires_web_search", False),
                }
        elif provider == "claude":
            if "input_tokens" not in model_info:
                raise ValueError(f"Missing 'input_tokens' for Claude model {model_id}")
            model_configs[model_id] = {
                "input_tokens": model_info["input_tokens"],
                "output_tokens": model_info["output_tokens"],
            }
        elif provider == "gemini":
            if model_info.get("is_agent"):
                model_configs[model_id] = {
                    "output_tokens": model_info.get("output_tokens"),
                    "is_agent": True,
                }
            elif model_info.get("pricing_type") in ["per_image", "per_second"]:
                entry = {"output_tokens": None}
                if "default_duration_seconds" in model_info:
                    entry["default_duration_seconds"] = model_info[
                        "default_duration_seconds"
                    ]
                model_configs[model_id] = entry
            else:
                if "output_tokens" not in model_info:
                    raise ValueError(
                        f"Missing 'output_tokens' for Gemini model {model_id}"
                    )
                model_configs[model_id] = {"output_tokens": model_info["output_tokens"]}
        elif provider == "groq":
            if "output_tokens" not in model_info:
                raise ValueError(f"Missing 'output_tokens' for Groq model {model_id}")
            if "param" not in model_info:
                raise ValueError(f"Missing 'param' for Groq model {model_id}")
            model_configs[model_id] = {
                "output_tokens": model_info["output_tokens"],
                "param": model_info["param"],
                "supports_temperature": model_info.get("supports_temperature", True),
            }
        elif provider == "grok":
            if model_info.get("pricing_type") == "per_image":
                model_configs[model_id] = {"output_tokens": None}
            else:
                if "output_tokens" not in model_info:
                    raise ValueError(
                        f"Missing 'output_tokens' for Grok model {model_id}"
                    )
                model_configs[model_id] = {"output_tokens": model_info["output_tokens"]}
        elif provider == "mistral":
            if "output_tokens" not in model_info:
                raise ValueError(
                    f"Missing 'output_tokens' for Mistral model {model_id}"
                )
            config_entry = {"output_tokens": model_info["output_tokens"]}
            for flag in [
                "supports_vision",
                "supports_reasoning",
                "supports_audio",
                "supports_fim",
                "supports_transcription",
                "supports_grounding",
                "embedding_dimensions",
            ]:
                if flag in model_info:
                    config_entry[flag] = model_info[flag]
            model_configs[model_id] = config_entry

    return model_configs


def get_structured_model_listing(provider: str, api_model_ids: set | None = None):
    """Generate structured model listing from YAML configuration.

    Args:
        provider: Provider name ('openai', 'claude', 'gemini')
        api_model_ids: Set of model IDs available via API (for availability checking)

    Returns:
        ModelListing object with structured model information
    """
    from mcp_handley_lab.common.pricing import calculate_cost
    from mcp_handley_lab.shared.models import (
        ModelCategory,
        ModelInfo,
        ModelListing,
        ModelListingSummary,
        ModelPricing,
    )

    config = load_model_config(provider)

    summary = ModelListingSummary(
        provider=provider,
        total_models=len(config["models"]),
        total_categories=len(config["display_categories"]),
        default_model=config["default_model"],
        api_available_models=len(api_model_ids) if api_model_ids else 0,
    )

    categories = []
    all_models = []

    for category in config["display_categories"]:
        category_name = category["name"]
        required_tags = category["tags"]
        exclude_tags = category.get("exclude_tags", [])

        category_models = get_models_by_tags(config, required_tags, exclude_tags)

        category_model_objects = []

        for model_id, model_config in category_models.items():
            available = model_id in api_model_ids if api_model_ids else True

            pricing_type = model_config.get("pricing_type", "token")

            if pricing_type == "per_image":
                cost_per_image = calculate_cost(
                    model_id, 1, 0, provider, images_generated=1
                )
                pricing = ModelPricing(type="per_image", cost_per_image=cost_per_image)
            elif pricing_type == "per_second":
                cost_per_second = calculate_cost(
                    model_id, 1, 0, provider, seconds_generated=1
                )
                pricing = ModelPricing(
                    type="per_second", cost_per_second=cost_per_second
                )
            else:
                input_cost = calculate_cost(model_id, 1000000, 0, provider)
                output_cost = calculate_cost(model_id, 0, 1000000, provider)
                pricing = ModelPricing(
                    type="per_token",
                    input_cost_per_1m=input_cost,
                    output_cost_per_1m=output_cost,
                )

            capabilities = []
            if model_config.get("capabilities"):
                capabilities = [
                    cap.strip() for cap in model_config["capabilities"].split(",")
                ]

            best_for = []
            if model_config.get("best_for"):
                best_for = [
                    item.strip() for item in model_config["best_for"].split(",")
                ]

            model_info = ModelInfo(
                id=model_id,
                name=model_id,
                description=model_config.get("description", ""),
                available=available,
                context_window=str(model_config.get("context_window", "")),
                pricing=pricing,
                tags=model_config.get("tags", []),
                capabilities=capabilities,
                best_for=best_for,
            )

            category_model_objects.append(model_info)
            all_models.append(model_info)

        if category_model_objects:
            categories.append(
                ModelCategory(name=category_name, models=category_model_objects)
            )

    return ModelListing(
        summary=summary,
        categories=categories,
        models=all_models,
        usage_notes=config["usage_notes"],
    )


def format_model_listing(provider: str, api_model_ids: set | None = None) -> str:
    """Generate formatted model listing from YAML configuration.

    Args:
        provider: Provider name ('openai', 'claude', 'gemini')
        api_model_ids: Set of model IDs available via API (for availability checking)

    Returns:
        Formatted string with model information grouped by categories
    """
    from mcp_handley_lab.common.pricing import calculate_cost

    config = load_model_config(provider)
    model_info = []

    total_models = len(config["models"])
    total_categories = len(config["display_categories"])

    summary = f"""
📊 {provider.title()} Model Summary
{"=" * (len(provider) + 20)}
• Total Models: {total_models}
• Model Categories: {total_categories}
• Default Model: {config["default_model"]}
"""

    if provider == "openai":
        summary += f"• API Available Models: {len(api_model_ids) if api_model_ids else 'Unknown'}\n"

    for category in config["display_categories"]:
        category_name = category["name"]
        required_tags = category["tags"]
        exclude_tags = category.get("exclude_tags", [])

        model_info.append(f"\n{category_name}")
        model_info.append("=" * len(category_name))

        category_models = get_models_by_tags(config, required_tags, exclude_tags)

        for model_id, model_config in category_models.items():
            if api_model_ids:
                availability = (
                    "✅ Available"
                    if model_id in api_model_ids
                    else "❓ Not listed in API"
                )
            else:
                availability = "✅ Configured"

            pricing_type = model_config.get("pricing_type", "token")
            if pricing_type == "per_image":
                cost_per_image = calculate_cost(
                    model_id, 1, 0, provider, images_generated=1
                )
                pricing = f"${cost_per_image:.3f} per image"
            elif pricing_type == "per_second":
                cost_per_second = calculate_cost(
                    model_id, 1, 0, provider, seconds_generated=1
                )
                pricing = f"${cost_per_second:.3f} per second"
            else:
                input_cost = calculate_cost(model_id, 1000000, 0, provider)
                output_cost = calculate_cost(model_id, 0, 1000000, provider)
                pricing = f"${input_cost:.2f}/${output_cost:.2f} per 1M tokens"

            context_window = model_config.get("context_window", "Unknown")
            description = model_config.get("description", "No description")
            capabilities = model_config.get("capabilities", "No capabilities listed")

            model_info.append(
                f"""
📋 {model_id}
   Description: {description}
   Status: {availability}
   Context Window: {context_window}
   Pricing: {pricing}
   {capabilities}"""
            )

    usage_notes = "\n💡 Usage Notes:\n" + "\n".join(
        f"• {note}" for note in config["usage_notes"]
    )

    return summary + "\n".join(model_info) + usage_notes
