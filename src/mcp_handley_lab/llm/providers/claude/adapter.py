"""Claude provider adapter for unified LLM tools.

Contains provider-specific generation functions that implement the Anthropic API calls.
These adapters are used by the unified mcp-chat tool.
"""

import threading
from typing import Any

from anthropic import Anthropic

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    load_provider_models,
    resolve_files_for_llm,
    resolve_images_for_multimodal_prompt,
)

# Lazy initialization of Claude client
_client: Anthropic | None = None
_client_lock = threading.Lock()


def get_client() -> Anthropic:
    """Get or create the global Claude client with thread safety."""
    global _client
    with _client_lock:
        if _client is None:
            try:
                _client = Anthropic(api_key=settings.anthropic_api_key)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Claude client: {e}") from e
    return _client


# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL = load_provider_models("claude")


def get_model_config(model: str) -> dict:
    """Get model configuration."""
    return MODEL_CONFIGS.get(model, MODEL_CONFIGS[DEFAULT_MODEL])


def resolve_model_alias(model: str) -> str:
    """Resolve model aliases to full model names."""
    aliases = {
        "opus": "claude-opus-4-5-20251101",
        "sonnet": "claude-sonnet-4-5-20250929",
        "haiku": "claude-haiku-4-5-20251001",
    }
    return aliases.get(model, model)


def convert_history_to_claude_format(
    history: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Convert generic history to Claude's expected format.

    Claude requires alternating user/assistant messages. This function validates
    and fixes the sequence if needed.
    """
    if not history:
        return []

    claude_history = []
    last_role = None

    for message in history:
        role = message["role"]
        content = message["content"]

        # Skip system messages (handled separately in Claude)
        if role == "system":
            continue

        # If we have consecutive messages from the same role, merge them
        if role == last_role and claude_history:
            claude_history[-1]["content"] += "\n\n" + content
        else:
            claude_history.append({"role": role, "content": content})
            last_role = role

    # Ensure history starts with user message (Claude requirement)
    if claude_history and claude_history[0]["role"] != "user":
        claude_history.insert(
            0, {"role": "user", "content": "[Previous conversation context]"}
        )

    return claude_history


def resolve_files(files: list[str]) -> str:
    """Resolve file inputs to text content for Claude."""
    if not files:
        return ""

    file_contents = resolve_files_for_llm(files, max_file_size=20 * 1024 * 1024)
    return "\n\n".join(file_contents)


def resolve_images_to_content_blocks(
    images: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Resolve image inputs to Claude content blocks."""
    if images is None:
        images = []

    _, image_blocks = resolve_images_for_multimodal_prompt("", images)

    claude_image_blocks = []
    for image_block in image_blocks:
        claude_image_blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_block["mime_type"],
                    "data": image_block["data"],
                },
            }
        )

    return claude_image_blocks


def generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Claude-specific text generation function for the shared processor."""
    # Extract Claude-specific parameters from options dict
    options = kwargs.get("options", {})
    temperature = kwargs.get("temperature", 1.0)
    files = kwargs.get("files", [])
    enable_thinking = options.get("enable_thinking", False)
    thinking_budget = options.get("thinking_budget", 10000)

    # Get model configuration
    resolved_model = resolve_model_alias(model)
    model_config = get_model_config(resolved_model)
    output_tokens = model_config["output_tokens"]

    # Resolve file contents
    file_content = resolve_files(files)

    # Build user content
    user_content = prompt
    if file_content:
        user_content += "\n\n" + file_content

    # Convert history to Claude format
    claude_history = convert_history_to_claude_format(history)

    # Add current user message
    claude_history.append({"role": "user", "content": user_content})

    # Prepare request parameters
    request_params: dict[str, Any] = {
        "model": resolved_model,
        "messages": claude_history,
        "max_tokens": output_tokens,
        "timeout": 599,
    }

    # Add thinking configuration if enabled (temperature not allowed with thinking)
    if enable_thinking:
        request_params["thinking"] = {
            "type": "enabled",
            "budget_tokens": thinking_budget,
        }
    else:
        request_params["temperature"] = temperature

    # Add system instruction if provided
    if system_instruction:
        request_params["system"] = system_instruction

    # Make API call
    try:
        response = get_client().messages.create(**request_params)
    except Exception as e:
        raise ValueError(f"Claude API error: {str(e)}") from e

    # Extract text and thinking from response content blocks
    text_parts = []
    thinking_parts = []
    for block in response.content:
        if block.type == "thinking":
            thinking_parts.append(block.thinking)
        elif block.type == "text":
            text_parts.append(block.text)

    # Format output with thinking if present
    if thinking_parts and enable_thinking:
        thinking_text = "\n".join(thinking_parts)
        answer_text = "\n".join(text_parts) if text_parts else ""
        text = f"<thinking>\n{thinking_text}\n</thinking>\n\n{answer_text}"
    elif text_parts:
        text = "\n".join(text_parts)
    else:
        raise RuntimeError("No response text generated")

    # Extract citations from content blocks
    citations = []
    for block in response.content:
        if hasattr(block, "citations") and block.citations:
            citations.extend(
                [
                    c.model_dump() if hasattr(c, "model_dump") else c
                    for c in block.citations
                ]
            )

    # Extract cache creation details
    cache_creation_details = {}
    if hasattr(response.usage, "cache_creation") and response.usage.cache_creation:
        cache_creation_details = {
            "ephemeral_1h_input_tokens": getattr(
                response.usage.cache_creation, "ephemeral_1h_input_tokens", 0
            )
            or 0,
            "ephemeral_5m_input_tokens": getattr(
                response.usage.cache_creation, "ephemeral_5m_input_tokens", 0
            )
            or 0,
        }

    return {
        "text": text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
        "finish_reason": response.stop_reason,
        "model_version": response.model,
        "response_id": response.id,
        "stop_sequence": response.stop_sequence or "",
        "cache_creation_input_tokens": response.usage.cache_creation_input_tokens or 0,
        "cache_read_input_tokens": response.usage.cache_read_input_tokens or 0,
        "service_tier": response.usage.service_tier or "",
        "cache_creation_details": cache_creation_details,
        "citations": citations,
        "created_at": float(getattr(response, "created_at", 0))
        if getattr(response, "created_at", None)
        else None,
    }


def image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Claude-specific image analysis function for the shared processor."""
    images = kwargs.get("images", [])
    focus = kwargs.get("focus", "general")

    # Enhance prompt based on focus
    if focus != "general":
        prompt = f"Focus on {focus} aspects. {prompt}"

    # Get model configuration
    resolved_model = resolve_model_alias(model)
    model_config = get_model_config(resolved_model)
    output_tokens = model_config["output_tokens"]

    # Resolve images to content blocks
    image_blocks = resolve_images_to_content_blocks(images)

    # Build content with text and images
    content_blocks = [{"type": "text", "text": prompt}] + image_blocks

    # Convert history to Claude format
    claude_history = convert_history_to_claude_format(history)

    # Add current user message with images
    claude_history.append({"role": "user", "content": content_blocks})

    request_params = {
        "model": resolved_model,
        "messages": claude_history,
        "max_tokens": output_tokens,
        "temperature": 1.0,
        "timeout": 599,
    }

    # Add system instruction if provided
    if system_instruction:
        request_params["system"] = system_instruction

    try:
        response = get_client().messages.create(**request_params)
    except Exception as e:
        raise ValueError(f"Claude API error: {str(e)}") from e

    # Extract citations from content blocks
    citations = []
    for block in response.content:
        if hasattr(block, "citations") and block.citations:
            citations.extend(
                [
                    c.model_dump() if hasattr(c, "model_dump") else c
                    for c in block.citations
                ]
            )

    # Extract cache creation details
    cache_creation_details = {}
    if hasattr(response.usage, "cache_creation") and response.usage.cache_creation:
        cache_creation_details = {
            "ephemeral_1h_input_tokens": getattr(
                response.usage.cache_creation, "ephemeral_1h_input_tokens", 0
            )
            or 0,
            "ephemeral_5m_input_tokens": getattr(
                response.usage.cache_creation, "ephemeral_5m_input_tokens", 0
            )
            or 0,
        }

    return {
        "text": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
        "finish_reason": response.stop_reason,
        "model_version": response.model,
        "response_id": response.id,
        "stop_sequence": response.stop_sequence or "",
        "cache_creation_input_tokens": response.usage.cache_creation_input_tokens or 0,
        "cache_read_input_tokens": response.usage.cache_read_input_tokens or 0,
        "service_tier": response.usage.service_tier or "",
        "cache_creation_details": cache_creation_details,
        "citations": citations,
        "created_at": float(getattr(response, "created_at", 0))
        if getattr(response, "created_at", None)
        else None,
    }
