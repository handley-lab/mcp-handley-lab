"""Groq provider adapter for unified LLM tools.

Contains provider-specific generation functions that implement the Groq API calls.
These adapters are used by the unified mcp-chat tool.
"""

import os
import threading
from pathlib import Path
from typing import Any

from openai import BadRequestError, OpenAI

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    load_provider_models,
    resolve_files_for_llm,
)

# Lazy initialization of Groq client
_client: OpenAI | None = None
_client_lock = threading.Lock()


def get_client() -> OpenAI:
    """Get or create the global Groq client with thread safety."""
    global _client
    with _client_lock:
        if _client is None:
            # Check env var directly (for tests) or fall back to settings
            api_key = os.environ.get("GROQ_API_KEY") or settings.groq_api_key
            _client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
            )
    return _client


# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL = load_provider_models("groq")


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
    """Groq-specific text generation function for the shared processor."""
    model_config = get_model_config(model)

    # Extract Groq-specific parameters from options dict
    options = kwargs.get("options", {})
    temperature = kwargs.get("temperature", 1.0)
    files = kwargs.get("files", [])
    max_output_tokens = options.get("max_output_tokens")

    # Build messages
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.extend(history)

    # Resolve files and add to prompt
    inline_content = resolve_files_for_llm(files)
    user_content = prompt
    if inline_content:
        user_content += "\n\n" + "\n\n".join(inline_content)
    messages.append({"role": "user", "content": user_content})

    param_name = model_config.get("param", "max_tokens")
    default_tokens = model_config.get("output_tokens")

    request_params = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        param_name: max_output_tokens or default_tokens,
    }

    try:
        response = get_client().chat.completions.create(**request_params)
    except BadRequestError as e:
        raise ValueError(f"Groq API error: {str(e)}") from e
    except Exception as e:
        raise ValueError(f"Groq API error: {str(e)}") from e

    # Extract timing information from usage (Groq-specific latency breakdown)
    timing = {}
    if response.usage:
        timing = {
            "queue_time": getattr(response.usage, "queue_time", 0) or 0,
            "prompt_time": getattr(response.usage, "prompt_time", 0) or 0,
            "completion_time": getattr(response.usage, "completion_time", 0) or 0,
            "total_time": getattr(response.usage, "total_time", 0) or 0,
        }

    # Extract Groq-specific metadata
    groq_metadata = {}
    if hasattr(response, "x_groq") and response.x_groq:
        groq_metadata = {
            "request_id": getattr(response.x_groq, "id", "") or "",
            "seed": getattr(response.x_groq, "seed", None),
        }

    return {
        "text": response.choices[0].message.content or "",
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "total_tokens": getattr(response.usage, "total_tokens", 0) or 0,
        "finish_reason": response.choices[0].finish_reason,
        "model_version": response.model,
        "response_id": response.id,
        "system_fingerprint": response.system_fingerprint or "",
        "grounding_metadata": None,  # Groq doesn't support grounding
        "created_at": float(getattr(response, "created", 0))
        if getattr(response, "created", None)
        else None,
        "timing": timing,
        "groq_metadata": groq_metadata,
    }


def audio_transcription_adapter(
    audio_path: str,
    language: str = "",
    include_timestamps: bool = False,
) -> dict[str, Any]:
    """Groq Whisper audio transcription (whisper-large-v3-turbo)."""
    file_path = Path(audio_path).expanduser()
    with open(file_path, "rb") as f:
        params = {"model": "whisper-large-v3-turbo", "file": f}
        if language:
            params["language"] = language
        if include_timestamps:
            params["response_format"] = "verbose_json"
            params["timestamp_granularities"] = ["segment"]
        response = get_client().audio.transcriptions.create(**params)
    result = {"text": response.text}
    if include_timestamps and hasattr(response, "segments"):
        result["segments"] = [
            {"start": s.start, "end": s.end, "text": s.text} for s in response.segments
        ]
    return result


def list_api_models() -> set[str]:
    """List model IDs available from the Groq API."""
    api_models = get_client().models.list()
    return {m.id for m in api_models.data}
