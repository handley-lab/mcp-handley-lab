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
    """
    yaml_path = Path(__file__).parent / provider / "models.yaml"

    if not yaml_path.exists():
        raise FileNotFoundError(f"Model config file not found: {yaml_path}")

    try:
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Validate required sections
        required_sections = [
            "models",
            "display_categories",
            "default_model",
            "usage_notes",
        ]
        missing_sections = [
            section for section in required_sections if section not in config
        ]
        if missing_sections:
            raise ValueError(
                f"Missing required sections in {yaml_path}: {missing_sections}"
            )

        return config

    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML in {yaml_path}: {e}") from e


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

        # Check if model has all required tags
        if not all(tag in model_tags for tag in required_tags):
            continue

        # Check if model has any excluded tags
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
            # OpenAI format - handle image generation models differently
            if model_info.get("pricing_type") == "per_image":
                # Image generation models don't need output_tokens/param
                model_configs[model_id] = {
                    "output_tokens": None,  # N/A for image generation
                    "param": None,
                }
            else:
                # Text generation models require explicit values in YAML
                if "output_tokens" not in model_info:
                    raise ValueError(
                        f"Missing 'output_tokens' for OpenAI model {model_id}"
                    )
                if "param" not in model_info:
                    raise ValueError(f"Missing 'param' for OpenAI model {model_id}")
                model_configs[model_id] = {
                    "output_tokens": model_info["output_tokens"],
                    "param": model_info["param"],
                }
        elif provider == "claude":
            # Claude format - require explicit values in YAML
            if "input_tokens" not in model_info:
                raise ValueError(f"Missing 'input_tokens' for Claude model {model_id}")
            if "output_tokens" not in model_info:
                raise ValueError(f"Missing 'output_tokens' for Claude model {model_id}")
            model_configs[model_id] = {
                "input_tokens": model_info["input_tokens"],
                "output_tokens": model_info["output_tokens"],
            }
        elif provider == "gemini":
            # Gemini format - skip image/video generation models or require explicit values
            if model_info.get("pricing_type") in ["per_image", "per_second"]:
                # Image/video generation models don't need output_tokens
                model_configs[model_id] = {
                    "output_tokens": None  # N/A for image/video generation
                }
            else:
                # Text generation models require explicit values in YAML
                if "output_tokens" not in model_info:
                    raise ValueError(
                        f"Missing 'output_tokens' for Gemini model {model_id}"
                    )
                model_configs[model_id] = {"output_tokens": model_info["output_tokens"]}
        # Other providers can be added here as needed

    return model_configs


def format_model_listing(provider: str, api_model_ids: set | None = None) -> str:
    """Generate formatted model listing from YAML configuration.

    Args:
        provider: Provider name ('openai', 'claude', 'gemini')
        api_model_ids: Set of model IDs available via API (for availability checking)

    Returns:
        Formatted string with model information grouped by categories
    """
    from ..common.pricing import calculate_cost

    config = load_model_config(provider)
    model_info = []

    # Build summary
    total_models = len(config["models"])
    total_categories = len(config["display_categories"])

    summary = f"""
📊 {provider.title()} Model Summary
{"=" * (len(provider) + 20)}
• Total Models: {total_models}
• Model Categories: {total_categories}
• Default Model: {config['default_model']}
"""

    # Add provider-specific info
    if provider == "openai":
        summary += f"• API Available Models: {len(api_model_ids) if api_model_ids else 'Unknown'}\n"

    # Process each display category
    for category in config["display_categories"]:
        category_name = category["name"]
        required_tags = category["tags"]
        exclude_tags = category.get("exclude_tags", [])

        model_info.append(f"\n{category_name}")
        model_info.append("=" * len(category_name))

        # Get models for this category
        category_models = get_models_by_tags(config, required_tags, exclude_tags)

        for model_id, model_config in category_models.items():
            # Check API availability
            if api_model_ids:
                availability = (
                    "✅ Available"
                    if model_id in api_model_ids
                    else "❓ Not listed in API"
                )
            else:
                availability = "✅ Configured"

            # Get pricing
            try:
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
            except Exception:
                pricing = "Pricing not available"

            # Format model entry
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

    # Add usage notes
    usage_notes = "\n💡 Usage Notes:\n" + "\n".join(
        f"• {note}" for note in config["usage_notes"]
    )

    return summary + "\n".join(model_info) + usage_notes
