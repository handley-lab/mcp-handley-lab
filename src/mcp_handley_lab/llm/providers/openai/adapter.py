"""OpenAI provider adapter for unified LLM tools.

Contains provider-specific generation functions that implement the OpenAI API calls.
These adapters are used by the unified mcp-chat tool.
"""

import threading
from typing import Any

import httpx
import openai
from openai import OpenAI

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    load_provider_models,
    resolve_files_for_llm,
    resolve_images_for_multimodal_prompt,
)

# Lazy initialization of OpenAI client
_client: OpenAI | None = None
_client_lock = threading.Lock()


def get_client() -> OpenAI:
    """Get or create the global OpenAI client with thread safety."""
    global _client
    with _client_lock:
        if _client is None:
            try:
                _client = OpenAI(api_key=settings.openai_api_key)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize OpenAI client: {e}") from e
    return _client


# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL = load_provider_models("openai")


def get_model_config(model: str) -> dict:
    """Get model configuration."""
    return MODEL_CONFIGS.get(model, MODEL_CONFIGS[DEFAULT_MODEL])


def generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """OpenAI-specific text generation function using the Responses API."""
    # Get model configuration first for validation
    model_config = get_model_config(model)

    # Extract OpenAI-specific parameters from options dict
    options = kwargs.get("options", {})
    temperature = kwargs.get("temperature", 1.0)
    files = kwargs.get("files", [])
    reasoning_effort = options.get("reasoning_effort", "none")
    reasoning_summary = options.get("reasoning_summary", "auto")
    verbosity = options.get("verbosity")

    # Validate temperature parameter
    if not model_config.get("supports_temperature", True) and temperature != 1.0:
        raise ValueError(
            f"Model '{model}' does not support the 'temperature' parameter. "
            "Please remove it from your request."
        )

    # Resolve files and build user content
    inline_content = resolve_files_for_llm(files)
    user_content = prompt
    if inline_content:
        user_content += "\n\n" + "\n\n".join(inline_content)

    # Build input with conversation history (Responses API supports array format)
    if history:
        input_messages = []
        for msg in history:
            role = msg.get("role", "user")
            input_messages.append({"role": role, "content": msg.get("content", "")})
        input_messages.append({"role": "user", "content": user_content})
        input_value: str | list = input_messages
    else:
        input_value = user_content

    # Build request parameters for Responses API
    request_params: dict[str, Any] = {
        "model": model,
        "input": input_value,
    }

    if system_instruction:
        request_params["instructions"] = system_instruction

    if model_config.get("supports_temperature", True):
        request_params["temperature"] = temperature

    default_tokens = model_config["output_tokens"]
    request_params["max_output_tokens"] = default_tokens

    # Add reasoning configuration for models that support it
    if model_config.get("supports_reasoning", False):
        reasoning_effort = (reasoning_effort or "none").lower()
        reasoning_summary = (reasoning_summary or "auto").lower()

        if reasoning_effort != "none":
            request_params["reasoning"] = {
                "effort": reasoning_effort,
                "summary": reasoning_summary,
            }

    # Add verbosity configuration for models that support it (GPT-5.1+)
    if model_config.get("supports_verbosity", False) and verbosity:
        verbosity = verbosity.lower()
        if verbosity in ("low", "medium", "high"):
            request_params["text"] = {"verbosity": verbosity}

    # Make Responses API call
    response = get_client().responses.create(**request_params)

    # Extract primary output text via helper property
    text = getattr(response, "output_text", None)

    # Fallback if output_text is not present (older SDK versions)
    if text is None:
        parts = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) == "message":
                for block in getattr(item, "content", []) or []:
                    if isinstance(block, str):
                        parts.append(block)
                    elif hasattr(block, "text"):
                        parts.append(block.text)
        text = "\n".join(parts) if parts else ""

    # Extract finish reason
    status = getattr(response, "status", "completed")
    finish_reason = "stop" if status == "completed" else status

    # Usage mapping
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "output_tokens", 0) if usage else 0

    # Extract token details
    completion_tokens_details = {}
    prompt_tokens_details = {}

    if usage and hasattr(usage, "output_tokens_details"):
        details = usage.output_tokens_details
        if details:
            completion_tokens_details = {
                "reasoning_tokens": getattr(details, "reasoning_tokens", 0),
                "accepted_prediction_tokens": getattr(
                    details, "accepted_prediction_tokens", 0
                ),
                "rejected_prediction_tokens": getattr(
                    details, "rejected_prediction_tokens", 0
                ),
                "audio_tokens": getattr(details, "audio_tokens", 0),
            }

    if usage and hasattr(usage, "input_tokens_details"):
        details = usage.input_tokens_details
        if details:
            prompt_tokens_details = {
                "cached_tokens": getattr(details, "cached_tokens", 0),
                "audio_tokens": getattr(details, "audio_tokens", 0),
            }

    return {
        "text": text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": getattr(usage, "total_tokens", input_tokens + output_tokens)
        if usage
        else input_tokens + output_tokens,
        "finish_reason": finish_reason,
        "model_version": getattr(response, "model", model),
        "response_id": response.id,
        "system_fingerprint": getattr(response, "system_fingerprint", "") or "",
        "service_tier": getattr(response, "service_tier", "") or "",
        "completion_tokens_details": completion_tokens_details,
        "prompt_tokens_details": prompt_tokens_details,
        "created_at": float(getattr(response, "created_at", 0))
        if getattr(response, "created_at", None)
        else None,
        "completed_at": float(getattr(response, "completed_at", 0))
        if getattr(response, "completed_at", None)
        else None,
    }


def image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """OpenAI-specific image analysis function using the Responses API."""
    model_config = get_model_config(model)

    images = kwargs.get("images", [])
    focus = kwargs.get("focus", "general")
    temperature = kwargs.get("temperature", 1.0)

    if not model_config.get("supports_temperature", True) and temperature != 1.0:
        raise ValueError(
            f"Model '{model}' does not support the 'temperature' parameter. "
            "Please remove it from your request."
        )

    # Enhance prompt based on focus
    if focus != "general":
        prompt = f"Focus on {focus} aspects. {prompt}"

    prompt_text, image_blocks = resolve_images_for_multimodal_prompt(prompt, images)

    # Build content blocks for Responses API multimodal input
    # Use "input_text" for user text, "input_image" for images (Responses API format)
    current_content: list[dict[str, Any]] = [
        {"type": "input_text", "text": prompt_text}
    ]
    for image_block in image_blocks:
        current_content.append(
            {
                "type": "input_image",
                "image_url": f"data:{image_block['mime_type']};base64,{image_block['data']}",
            }
        )

    # Build input with conversation history
    # Responses API format: {"role": "...", "content": [...]} without "type": "message" wrapper
    if history:
        input_messages: list[dict[str, Any]] = []
        for msg in history:
            role = msg.get("role", "user")
            # Use "output_text" for assistant messages, "input_text" for user messages
            content_type = "output_text" if role == "assistant" else "input_text"
            input_messages.append(
                {
                    "role": role,
                    "content": [{"type": content_type, "text": msg.get("content", "")}],
                }
            )
        input_messages.append({"role": "user", "content": current_content})
        input_value: Any = input_messages
    else:
        input_value = [{"role": "user", "content": current_content}]

    default_tokens = model_config["output_tokens"]

    request_params: dict[str, Any] = {
        "model": model,
        "input": input_value,
    }

    if system_instruction:
        request_params["instructions"] = system_instruction

    if model_config.get("supports_temperature", True):
        request_params["temperature"] = temperature

    request_params["max_output_tokens"] = default_tokens

    response = get_client().responses.create(**request_params)

    text = getattr(response, "output_text", None)
    if text is None:
        parts = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) == "message":
                for block in getattr(item, "content", []) or []:
                    if isinstance(block, str):
                        parts.append(block)
                    elif hasattr(block, "text"):
                        parts.append(block.text)
        text = "\n".join(parts) if parts else ""

    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "output_tokens", 0) if usage else 0

    status = getattr(response, "status", "completed")
    finish_reason = "stop" if status == "completed" else status

    return {
        "text": text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "finish_reason": finish_reason,
        "model_version": getattr(response, "model", model),
        "response_id": response.id,
        "system_fingerprint": getattr(response, "system_fingerprint", "") or "",
        "service_tier": getattr(response, "service_tier", "") or "",
        "completion_tokens_details": {},
        "prompt_tokens_details": {},
        "created_at": float(getattr(response, "created_at", 0))
        if getattr(response, "created_at", None)
        else None,
        "completed_at": float(getattr(response, "completed_at", 0))
        if getattr(response, "completed_at", None)
        else None,
    }


def image_generation_adapter(prompt: str, model: str, **kwargs) -> dict:
    """OpenAI-specific image generation function with comprehensive metadata extraction."""
    size = kwargs.get("size", "1024x1024")
    quality = kwargs.get("quality", "standard")

    params = {"model": model, "prompt": prompt, "size": size, "n": 1}
    if model == "dall-e-3":
        params["quality"] = quality

    try:
        response = get_client().images.generate(**params)
    except openai.BadRequestError as e:
        raise ValueError(f"OpenAI image generation error: {str(e)}") from e
    except Exception as e:
        raise ValueError(f"OpenAI image generation error: {str(e)}") from e

    image = response.data[0]

    # Download the image
    with httpx.Client() as http_client:
        image_response = http_client.get(image.url)
        image_response.raise_for_status()
        image_bytes = image_response.content

    openai_metadata = {
        "background": getattr(response, "background", None),
        "output_format": getattr(response, "output_format", None),
        "usage": getattr(response, "usage", None),
    }

    return {
        "image_bytes": image_bytes,
        "generation_timestamp": response.created,
        "enhanced_prompt": image.revised_prompt or "",
        "original_prompt": prompt,
        "requested_size": size,
        "requested_quality": quality,
        "requested_format": "png",
        "mime_type": "image/png",
        "original_url": image.url,
        "openai_metadata": openai_metadata,
    }


def list_api_models() -> set[str]:
    """List model IDs available from the OpenAI API."""
    api_models = get_client().models.list()
    return {m.id for m in api_models.data}


def embeddings_adapter(texts: list[str], model: str) -> list[list[float]]:
    """Generate embeddings for a list of texts."""
    response = get_client().embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]
