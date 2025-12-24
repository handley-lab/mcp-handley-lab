"""Grok provider adapter for unified LLM tools.

Contains provider-specific generation functions that implement the Grok API calls.
These adapters are used by the unified mcp-chat tool.
"""

import base64
import threading
from typing import Any

from xai_sdk import Client

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    load_provider_models,
    resolve_files_for_llm,
    resolve_images_for_multimodal_prompt,
)

# Lazy initialization of Grok client
_client: Client | None = None
_client_lock = threading.Lock()


def get_client() -> Client:
    """Get or create the global Grok client with thread safety."""
    global _client
    with _client_lock:
        if _client is None:
            try:
                _client = Client(api_key=settings.xai_api_key)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Grok client: {e}") from e
    return _client


# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL = load_provider_models("grok")


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
    """Grok-specific text generation function for the shared processor."""
    from xai_sdk import chat

    # Extract Grok-specific parameters
    temperature = kwargs.get("temperature", 1.0)
    files = kwargs.get("files", [])

    # Build messages using xai-sdk helpers
    messages = []

    # Add system instruction if provided
    if system_instruction:
        messages.append(chat.system(system_instruction))

    # Convert history to xai-sdk format
    for msg in history:
        if msg["role"] == "user":
            messages.append(chat.user(msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(chat.assistant(msg["content"]))

    # Resolve files
    inline_content = resolve_files_for_llm(files)

    # Add user message with any inline content
    user_content = prompt
    if inline_content:
        user_content += "\n\n" + "\n\n".join(inline_content)
    messages.append(chat.user(user_content))

    # Get model configuration
    model_config = get_model_config(model)
    default_tokens = model_config["output_tokens"]

    # Build request parameters
    request_params = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": default_tokens,
    }

    # Make API call using XAI SDK's two-step process
    chat_session = get_client().chat.create(**request_params)
    response = chat_session.sample()

    if not response or not response.content:
        raise RuntimeError("No response generated")

    # Extract logprobs if available
    avg_logprobs = None
    if response.logprobs and response.logprobs.content:
        logprobs = [
            item.logprob
            for item in response.logprobs.content
            if item.logprob > -1e30  # Filter out sentinel values
        ]
        if logprobs:
            avg_logprobs = sum(logprobs) / len(logprobs)

    # Get message content and reasoning content separately
    message_content = response.content or ""
    reasoning_text = getattr(response, "reasoning_content", "") or ""

    # Extract usage with fallbacks for optional fields
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
    total_tokens = getattr(usage, "total_tokens", 0) if usage else 0

    # Extract token details from usage
    completion_tokens_details = {}
    prompt_tokens_details = {}
    if usage:
        comp_details = getattr(usage, "completion_tokens_details", None)
        if comp_details:
            completion_tokens_details = {
                "reasoning_tokens": getattr(comp_details, "reasoning_tokens", 0) or 0,
                "accepted_prediction_tokens": getattr(
                    comp_details, "accepted_prediction_tokens", 0
                )
                or 0,
                "audio_tokens": getattr(comp_details, "audio_tokens", 0) or 0,
                "rejected_prediction_tokens": getattr(
                    comp_details, "rejected_prediction_tokens", 0
                )
                or 0,
            }
        prompt_details = getattr(usage, "prompt_tokens_details", None)
        if prompt_details:
            prompt_tokens_details = {
                "cached_tokens": getattr(prompt_details, "cached_tokens", 0) or 0,
                "text_tokens": getattr(prompt_details, "text_tokens", 0) or 0,
                "image_tokens": getattr(prompt_details, "image_tokens", 0) or 0,
                "audio_tokens": getattr(prompt_details, "audio_tokens", 0) or 0,
            }

    return {
        "text": message_content,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "finish_reason": str(getattr(response, "finish_reason", "") or ""),
        "avg_logprobs": avg_logprobs,
        "model_version": model,
        "response_id": getattr(response, "id", "") or "",
        "system_fingerprint": getattr(response, "system_fingerprint", "") or "",
        "service_tier": "",  # Grok doesn't have service tiers
        "completion_tokens_details": completion_tokens_details,
        "prompt_tokens_details": prompt_tokens_details,
        "reasoning_text": reasoning_text,
        "refusal": str(getattr(response, "refusal", ""))
        if getattr(response, "refusal", None)
        else None,
        "created_at": float(getattr(response, "created", 0))
        if getattr(response, "created", None)
        else None,
    }


def image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Grok-specific image analysis function for the shared processor."""
    from xai_sdk import chat

    # Extract image analysis specific parameters
    images = kwargs.get("images", [])
    focus = kwargs.get("focus", "general")

    # Enhance prompt based on focus
    if focus != "general":
        prompt = f"Focus on {focus} aspects. {prompt}"

    prompt_text, image_blocks = resolve_images_for_multimodal_prompt(prompt, images)

    # Build messages using xai-sdk helpers
    messages = []

    # Add system instruction if provided
    if system_instruction:
        messages.append(chat.system(system_instruction))

    # Convert history to xai-sdk format
    for msg in history:
        if msg["role"] == "user":
            messages.append(chat.user(msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(chat.assistant(msg["content"]))

    # Build message content with text and images
    content_parts = [chat.text(prompt_text)]
    for image_block in image_blocks:
        image_url = f"data:{image_block['mime_type']};base64,{image_block['data']}"
        content_parts.append(chat.image(image_url))

    # Add current message with images
    messages.append(chat.user(*content_parts))

    # Get model configuration
    model_config = get_model_config(model)
    default_tokens = model_config["output_tokens"]

    # Build request parameters
    request_params = {
        "model": model,
        "messages": messages,
        "temperature": 1.0,
        "max_tokens": default_tokens,
    }

    # Make API call using XAI SDK's two-step process
    chat_session = get_client().chat.create(**request_params)
    response = chat_session.sample()

    if not response or not response.content:
        raise RuntimeError("No response generated")

    # Get message content - check both content and reasoning_content
    message_content = response.content or ""
    if not message_content and getattr(response, "reasoning_content", None):
        message_content = response.reasoning_content

    # Extract usage with fallbacks for optional fields
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

    return {
        "text": message_content,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "finish_reason": str(getattr(response, "finish_reason", "") or ""),
        "avg_logprobs": None,
        "model_version": model,
        "response_id": getattr(response, "id", "") or "",
        "system_fingerprint": getattr(response, "system_fingerprint", "") or "",
        "service_tier": "",
        "completion_tokens_details": {},
        "prompt_tokens_details": {},
    }


def image_generation_adapter(prompt: str, model: str, **kwargs) -> dict:
    """Grok-specific image generation function with comprehensive metadata extraction."""
    # Use xai-sdk's image.sample method
    response = get_client().image.sample(
        prompt=prompt, model=model, image_format="base64"
    )

    if not response or not response.images:
        raise RuntimeError("No image generated")

    # Get the first (and typically only) image
    image = response.images[0]

    # Decode base64 image data
    image_bytes = base64.b64decode(image.image_data)

    # Extract metadata
    grok_metadata = {
        "model_used": model,
        "safety_rating": getattr(image, "safety_rating", None),
        "finish_reason": getattr(image, "finish_reason", None),
    }

    return {
        "image_bytes": image_bytes,
        "generation_timestamp": 0,  # Not provided by xai-sdk
        "enhanced_prompt": "",  # Not provided by xai-sdk
        "original_prompt": prompt,
        "requested_format": "png",  # xai-sdk returns PNG
        "mime_type": "image/png",
        "grok_metadata": grok_metadata,
    }


def list_api_models() -> set[str]:
    """List model names available from the Grok API."""
    language_models = get_client().models.list_language_models()
    api_model_ids = {m.name for m in language_models}

    # Also get image generation models
    image_models = get_client().models.list_image_generation_models()
    api_model_ids.update({m.name for m in image_models})

    return api_model_ids
