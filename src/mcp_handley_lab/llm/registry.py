"""Model registry for unified LLM provider routing.

Provides model resolution (model name → provider) and option validation
for the unified mcp-chat tool.
"""

from typing import Any

# All supported providers
PROVIDERS = ["gemini", "openai", "claude", "mistral", "grok", "groq"]

# Prefix fallback rules (longest match wins)
# Order matters: longer prefixes should match before shorter ones
MODEL_PREFIXES = [
    # Gemini
    ("gemini-embedding", "gemini"),
    ("gemini-", "gemini"),
    ("imagen-", "gemini"),
    ("veo-", "gemini"),
    # OpenAI
    ("gpt-image", "openai"),
    ("gpt-", "openai"),
    ("dall-e", "openai"),
    ("text-embedding", "openai"),
    ("o3", "openai"),
    ("o4", "openai"),
    # Claude
    ("claude-", "claude"),
    # Mistral
    ("codestral", "mistral"),
    ("pixtral", "mistral"),
    ("ministral", "mistral"),
    ("mistral-", "mistral"),
    ("mistral-embed", "mistral"),
    # Grok
    ("grok-", "grok"),
    # Groq (often hosts llama/mixtral models)
    ("llama-", "groq"),
    ("mixtral-", "groq"),
]

# Model aliases (shorthand → full model ID)
MODEL_ALIASES = {
    # Claude shorthand aliases
    "opus": "claude-opus-4-5-20251101",
    "sonnet": "claude-sonnet-4-5-20250929",
    "haiku": "claude-haiku-4-5-20251001",
}

# Provider name aliases are added dynamically from YAML defaults

# Provider-specific options and their valid values
PROVIDER_OPTIONS = {
    "gemini": {
        "grounding": {"type": "bool", "description": "Enable Google Search grounding"},
        "thinking_level": {
            "type": "str",
            "values": ["low", "high"],
            "description": "Thinking effort level for Gemini 3 models",
        },
        "thinking_budget": {
            "type": "int",
            "description": "Token budget for thinking (128-32768, or -1 for dynamic)",
        },
        "include_thoughts": {
            "type": "bool",
            "description": "Include model's thinking in output",
        },
        "poll_interval": {
            "type": "int",
            "description": "Seconds between polls for deep research (default 10)",
        },
        "max_polls": {
            "type": "int",
            "description": "Maximum poll attempts for deep research (default 360)",
        },
    },
    "openai": {
        "reasoning_effort": {
            "type": "str",
            "values": ["none", "low", "medium", "high", "xhigh"],
            "description": "Reasoning effort for GPT-5.x and o-series models",
        },
        "reasoning_summary": {
            "type": "str",
            "values": ["auto", "concise", "detailed"],
            "description": "Reasoning summary format",
        },
        "verbosity": {
            "type": "str",
            "values": ["low", "medium", "high"],
            "description": "Output verbosity (GPT-5.1+ only)",
        },
    },
    "claude": {
        "enable_thinking": {
            "type": "bool",
            "description": "Enable extended thinking mode",
        },
        "thinking_budget": {
            "type": "int",
            "description": "Maximum tokens for thinking (min 1024)",
        },
    },
    "mistral": {
        "include_thinking": {
            "type": "bool",
            "description": "Include reasoning model thinking in output",
        },
    },
    "grok": {},
    "groq": {},
}


def build_model_registry() -> dict[str, tuple[str, dict[str, Any]]]:
    """Build unified model registry from all providers' models.yaml files.

    Returns:
        Dict mapping model_id → (provider, model_config)
    """
    from mcp_handley_lab.llm.model_loader import load_model_config

    registry: dict[str, tuple[str, dict[str, Any]]] = {}
    provider_defaults: dict[str, str] = {}

    for provider in PROVIDERS:
        config = load_model_config(provider)
        models = config.get("models", {})
        for model_id, model_config in models.items():
            registry[model_id] = (provider, model_config)

        # Track default model for provider alias
        if "default_model" in config:
            provider_defaults[provider] = config["default_model"]

    # Add model aliases (sonnet, opus, haiku, etc.)
    for alias, full_id in MODEL_ALIASES.items():
        if full_id in registry:
            registry[alias] = registry[full_id]

    # Add provider name aliases (gemini, openai, claude, etc.)
    for provider, default_model in provider_defaults.items():
        if default_model in registry:
            registry[provider] = registry[default_model]

    return registry


# Build registry at module load time
MODEL_REGISTRY = build_model_registry()


def get_default_model(provider: str) -> str:
    """Get the default model for a provider from its YAML config."""
    from mcp_handley_lab.llm.model_loader import load_model_config

    config = load_model_config(provider)
    return config.get("default_model", "")


def resolve_model(model: str) -> tuple[str, str, dict[str, Any]]:
    """Resolve a model name to its provider and configuration.

    Args:
        model: Model name, alias (e.g., "sonnet"), or provider name (e.g., "gemini")

    Returns:
        Tuple of (provider, canonical_model_id, model_config)

    Raises:
        ValueError: If model cannot be resolved to any provider
    """
    # 1. Exact match in registry (includes aliases and provider names)
    if model in MODEL_REGISTRY:
        provider, config = MODEL_REGISTRY[model]
        # Resolve alias to canonical ID if needed
        if model in MODEL_ALIASES:
            canonical_id = MODEL_ALIASES[model]
        elif model in PROVIDERS:
            # Provider name used as alias - get its default model
            canonical_id = get_default_model(model)
        else:
            canonical_id = model
        return provider, canonical_id, config

    # 2. Prefix match - fail-fast for unknown model variants
    for prefix, provider in sorted(MODEL_PREFIXES, key=lambda x: -len(x[0])):
        if model.startswith(prefix):
            raise ValueError(
                f"Unknown model '{model}' for provider '{provider}'. "
                f"Model matches prefix '{prefix}' but is not in the registry. "
                f"Check spelling or add to providers/{provider}/models.yaml"
            )

    # 3. Error with helpful message
    available_providers = ", ".join(PROVIDERS)
    raise ValueError(
        f"Unknown model: '{model}'. Cannot infer provider.\n"
        f"Use list_models() to see available models, or specify a model from: {available_providers}"
    )


def get_supported_options(provider: str, model_config: dict[str, Any]) -> set[str]:
    """Get the set of supported options for a provider/model combination.

    Args:
        provider: Provider name
        model_config: Model configuration from YAML

    Returns:
        Set of supported option names
    """
    # Start with provider-level options
    supported = set(PROVIDER_OPTIONS.get(provider, {}).keys())

    # Model-specific capability flags can restrict options
    # e.g., only models with supports_grounding=True can use grounding
    if provider == "gemini":
        if model_config.get("is_agent"):
            # Agent models only support polling options
            supported = {"poll_interval", "max_polls"}
        else:
            # Regular models don't support polling options
            supported.discard("poll_interval")
            supported.discard("max_polls")
            if not model_config.get("supports_grounding", False):
                supported.discard("grounding")
            if not model_config.get("supports_thinking_level", False):
                supported.discard("thinking_level")
                supported.discard("thinking_budget")
                supported.discard("include_thoughts")

    if provider == "openai":
        if not model_config.get("supports_reasoning", False):
            supported.discard("reasoning_effort")
            supported.discard("reasoning_summary")
        if not model_config.get("supports_verbosity", False):
            supported.discard("verbosity")

    if provider == "claude" and not model_config.get(
        "supports_extended_thinking", True
    ):
        supported.discard("enable_thinking")
        supported.discard("thinking_budget")

    if provider == "mistral" and not model_config.get("supports_reasoning", False):
        supported.discard("include_thinking")

    return supported


def validate_options(
    provider: str, model: str, model_config: dict[str, Any], options: dict[str, Any]
) -> None:
    """Validate that options are supported by the provider/model.

    Implements strict validation: raises error if user sets unsupported option.

    Args:
        provider: Provider name
        model: Model ID
        model_config: Model configuration from YAML
        options: User-provided options dict

    Raises:
        ValueError: If an unsupported option is explicitly set
    """
    supported = get_supported_options(provider, model_config)

    for key, value in options.items():
        # Skip if value is None, False, or empty string (not explicitly set)
        if value is None or value is False or value == "":
            continue

        # Skip if value equals the default "none" for reasoning_effort
        if key == "reasoning_effort" and value == "none":
            continue

        if key not in supported:
            supported_list = sorted(supported) if supported else ["none"]
            raise ValueError(
                f"'{key}' is not supported by {provider} models.\n"
                f"Inferred provider: {provider} (from model '{model}')\n"
                f"Supported options for this model: {', '.join(supported_list)}\n"
                f"Use capabilities('{model}') for full details."
            )


def get_model_capabilities(model: str) -> dict[str, Any]:
    """Get capabilities and supported options for a model.

    This is the data source for the capabilities() tool.

    Args:
        model: Model name

    Returns:
        Dict with provider, model info, and supported options
    """
    provider, canonical_id, config = resolve_model(model)
    supported = get_supported_options(provider, config)

    # Build option details
    option_details = {}
    for opt_name in supported:
        opt_info = PROVIDER_OPTIONS.get(provider, {}).get(opt_name, {})
        option_details[opt_name] = {
            "type": opt_info.get("type", "unknown"),
            "description": opt_info.get("description", ""),
        }
        if "values" in opt_info:
            option_details[opt_name]["values"] = opt_info["values"]

    return {
        "model": canonical_id,
        "provider": provider,
        "description": config.get("description", ""),
        "context_window": config.get("context_window", ""),
        "capabilities": {
            "vision": config.get("supports_vision", False),
            "grounding": config.get("supports_grounding", False),
            "reasoning": config.get("supports_reasoning", False),
            "extended_thinking": config.get("supports_extended_thinking", False),
            "image_generation": config.get("pricing_type") == "per_image",
        },
        "supported_options": option_details,
        "constraints": _get_model_constraints(provider, config),
    }


def _get_model_constraints(provider: str, config: dict[str, Any]) -> list[str]:
    """Get usage constraints for a model."""
    constraints = []

    if provider == "openai" and not config.get("supports_temperature", True):
        constraints.append("temperature only supported when reasoning_effort='none'")

    if provider == "claude" and config.get("supports_extended_thinking", False):
        constraints.append("temperature not allowed when enable_thinking=True")

    return constraints


def list_all_models() -> dict[str, list[dict[str, Any]]]:
    """List all available models grouped by provider with full details.

    Returns:
        Dict mapping provider → list of model info dicts with capabilities
    """
    result: dict[str, list[dict[str, Any]]] = {p: [] for p in PROVIDERS}

    for model_id, (provider, config) in MODEL_REGISTRY.items():
        # Skip aliases (they duplicate the canonical entry)
        if model_id in MODEL_ALIASES or model_id in PROVIDERS:
            continue

        # Get supported options for this model
        supported = get_supported_options(provider, config)
        option_details = {}
        for opt_name in supported:
            opt_info = PROVIDER_OPTIONS.get(provider, {}).get(opt_name, {})
            option_details[opt_name] = {
                "type": opt_info.get("type", "unknown"),
                "description": opt_info.get("description", ""),
            }
            if "values" in opt_info:
                option_details[opt_name]["values"] = opt_info["values"]

        result[provider].append(
            {
                "id": model_id,
                "description": config.get("description", ""),
                "context_window": config.get("context_window", ""),
                "tags": config.get("tags", []),
                "capabilities": {
                    "vision": config.get("supports_vision", False),
                    "grounding": config.get("supports_grounding", False),
                    "reasoning": config.get("supports_reasoning", False),
                    "extended_thinking": config.get(
                        "supports_extended_thinking", False
                    ),
                    "image_generation": config.get("pricing_type") == "per_image",
                },
                "supported_options": option_details,
                "constraints": _get_model_constraints(provider, config),
            }
        )

    return result


def get_adapter(provider: str, adapter_type: str):
    """Dynamically import and return the appropriate adapter function.

    This is the central routing function for all provider adapters.
    Supported adapter types depend on the provider's capabilities.

    Args:
        provider: Provider name (gemini, openai, claude, mistral, grok, groq)
        adapter_type: Type of adapter (generation, image_analysis, image_generation,
                      fill_in_middle, moderation)

    Returns:
        The adapter function for the specified provider and type

    Raises:
        ValueError: If provider is unknown or doesn't support the adapter type
    """
    if provider == "gemini":
        from mcp_handley_lab.llm.providers.gemini import adapter

        adapters = {
            "generation": adapter.generation_adapter,
            "image_analysis": adapter.image_analysis_adapter,
            "image_generation": adapter.image_generation_adapter,
            "embeddings": adapter.embeddings_adapter,
            "deep_research": adapter.deep_research_adapter,
        }
    elif provider == "openai":
        from mcp_handley_lab.llm.providers.openai import adapter

        adapters = {
            "generation": adapter.generation_adapter,
            "image_analysis": adapter.image_analysis_adapter,
            "image_generation": adapter.image_generation_adapter,
            "embeddings": adapter.embeddings_adapter,
        }
    elif provider == "claude":
        from mcp_handley_lab.llm.providers.claude import adapter

        adapters = {
            "generation": adapter.generation_adapter,
            "image_analysis": adapter.image_analysis_adapter,
        }
    elif provider == "mistral":
        from mcp_handley_lab.llm.providers.mistral import adapter

        adapters = {
            "generation": adapter.generation_adapter,
            "image_analysis": adapter.image_analysis_adapter,
            "fill_in_middle": adapter.fill_in_middle_adapter,
            "moderation": adapter.moderation_adapter,
            "embeddings": adapter.embeddings_adapter,
            "audio_transcription": adapter.audio_transcription_adapter,
            "ocr": adapter.ocr_adapter,
        }
    elif provider == "grok":
        from mcp_handley_lab.llm.providers.grok import adapter

        adapters = {
            "generation": adapter.generation_adapter,
            "image_analysis": adapter.image_analysis_adapter,
            "image_generation": adapter.image_generation_adapter,
        }
    elif provider == "groq":
        from mcp_handley_lab.llm.providers.groq import adapter

        adapters = {"generation": adapter.generation_adapter}
    else:
        raise ValueError(f"Unknown provider: {provider}")

    if adapter_type not in adapters:
        raise ValueError(f"Provider '{provider}' does not support '{adapter_type}'")

    return adapters[adapter_type]
