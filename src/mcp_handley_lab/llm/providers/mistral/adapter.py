"""Mistral provider adapter for unified LLM tools.

Contains provider-specific generation functions that implement the Mistral API calls.
These adapters are used by the unified mcp-chat tool.
"""

import base64
import threading
from pathlib import Path
from typing import Any

from mistralai import Mistral

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    determine_mime_type,
    is_text_file,
    load_provider_models,
    resolve_image_data,
)

# Lazy initialization of Mistral client
_client: Mistral | None = None
_client_lock = threading.Lock()


def get_client() -> Mistral:
    """Get or create the global Mistral client with thread safety."""
    global _client
    with _client_lock:
        if _client is None:
            try:
                _client = Mistral(api_key=settings.mistral_api_key)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Mistral client: {e}") from e
    return _client


# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL = load_provider_models("mistral")


def get_model_config(model: str) -> dict[str, int]:
    """Get token limits for a specific model."""
    return MODEL_CONFIGS.get(model, MODEL_CONFIGS[DEFAULT_MODEL])


def extract_text_content(content: str | list, include_thinking: bool = True) -> str:
    """Extract text from Mistral response content.

    Handles both simple string responses and structured content
    (ThinkChunk/TextChunk lists from reasoning models like Magistral).

    Args:
        content: Response content (string or list of chunks)
        include_thinking: If True, include thinking in <thinking> tags. If False, omit.
    """
    if isinstance(content, str):
        return content

    # Handle list of content chunks (reasoning models)
    text_parts = []
    for chunk in content:
        if hasattr(chunk, "text"):
            text_parts.append(chunk.text)
        elif hasattr(chunk, "thinking") and include_thinking:
            # ThinkChunk contains nested thinking content
            for think_part in chunk.thinking:
                if hasattr(think_part, "text"):
                    text_parts.append(f"<thinking>\n{think_part.text}\n</thinking>")
    return "\n\n".join(text_parts)


def resolve_files(files: list[str]) -> list[dict[str, Any]]:
    """Resolve file inputs to Mistral message content format.

    Returns list of content dictionaries for Mistral API.
    """
    content_parts = []

    for file_item in files:
        # Handle unified format: strings or {"path": "..."} dicts
        if isinstance(file_item, str):
            file_path = Path(file_item)
        elif isinstance(file_item, dict) and "path" in file_item:
            file_path = Path(file_item["path"])
        else:
            raise ValueError(f"Invalid file item format: {file_item}")

        if is_text_file(file_path):
            # For text files, read directly as text
            content = file_path.read_text(encoding="utf-8")
            content_parts.append(
                {"type": "text", "text": f"[File: {file_path.name}]\n{content}"}
            )
        else:
            # For images, encode as base64 with proper MIME type
            mime_type = determine_mime_type(file_path)
            if not mime_type.startswith("image/"):
                raise ValueError(
                    f"Unsupported file type for chat/vision: {file_path} "
                    f"({mime_type}). Only text and image files are supported."
                )
            file_content = file_path.read_bytes()
            encoded_content = base64.b64encode(file_content).decode()
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": f"data:{mime_type};base64,{encoded_content}",
                }
            )

    return content_parts


def generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Mistral-specific text generation function for the shared processor."""
    # Extract Mistral-specific parameters from options dict
    options = kwargs.get("options", {})
    temperature = kwargs.get("temperature", 1.0)
    files = kwargs.get("files", [])
    include_thinking = options.get("include_thinking", False)

    # Get model configuration for output tokens
    model_config = get_model_config(model)
    output_tokens = model_config.get("output_tokens", 8192)

    # Build messages array
    messages = []

    # Add system instruction if provided
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    # Add conversation history
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Build user message with prompt and files
    user_content = []
    user_content.append({"type": "text", "text": prompt})

    # Add file contents
    if files:
        file_parts = resolve_files(files)
        user_content.extend(file_parts)

    messages.append(
        {"role": "user", "content": user_content if len(user_content) > 1 else prompt}
    )

    # Generate response
    try:
        response = get_client().chat.complete(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=output_tokens,
        )
    except Exception as e:
        raise ValueError(f"Mistral API error: {str(e)}") from e

    if not response.choices or not response.choices[0].message.content:
        raise RuntimeError("No response text generated")

    # Extract response data
    choice = response.choices[0]
    message = choice.message
    usage = response.usage

    return {
        "text": extract_text_content(message.content, include_thinking),
        "input_tokens": usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
        "finish_reason": choice.finish_reason or "",
        "model_version": model,
        "response_id": response.id or "",
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
    """Mistral-specific image analysis function for the shared processor."""
    # Extract image analysis specific parameters
    images = kwargs.get("images", [])
    focus = kwargs.get("focus", "general")

    # Enhance prompt based on focus
    if focus != "general":
        prompt = f"Focus on {focus} aspects. {prompt}"

    # Get model configuration for output tokens
    model_config = get_model_config(model)
    output_tokens = model_config.get("output_tokens", 8192)

    # Build message content with images
    content = [{"type": "text", "text": prompt}]

    # Add images
    for image_item in images:
        image_bytes = resolve_image_data(image_item)
        encoded_image = base64.b64encode(image_bytes).decode()
        # Detect MIME type from path or default to jpeg
        mime_type = "image/jpeg"
        if isinstance(image_item, str) and not image_item.startswith("data:"):
            guessed_type = determine_mime_type(Path(image_item))
            if guessed_type.startswith("image/"):
                mime_type = guessed_type
        content.append(
            {
                "type": "image_url",
                "image_url": f"data:{mime_type};base64,{encoded_image}",
            }
        )

    # Build messages (including conversation history for context)
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    # Add conversation history for multi-turn context
    for entry in history:
        messages.append({"role": entry["role"], "content": entry["content"]})

    messages.append({"role": "user", "content": content})

    # Generate response
    try:
        response = get_client().chat.complete(
            model=model,
            messages=messages,
            max_tokens=output_tokens,
        )
    except Exception as e:
        raise ValueError(f"Mistral API error: {str(e)}") from e

    if not response.choices or not response.choices[0].message.content:
        raise RuntimeError("No response text generated")

    # Extract response data
    choice = response.choices[0]
    message = choice.message
    usage = response.usage

    return {
        "text": extract_text_content(message.content),
        "input_tokens": usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
        "created_at": float(getattr(response, "created", 0))
        if getattr(response, "created", None)
        else None,
    }


def ocr_adapter(document_path: str, include_images: bool = True) -> dict[str, Any]:
    """Mistral-specific OCR function for document processing."""
    # Determine input type and format
    document_input = {}

    if document_path.startswith(("http://", "https://")):
        # HTTP(S) URL
        document_input = {"type": "document_url", "document_url": document_path}
    elif document_path.startswith("data:"):
        # Base64 data URI
        document_input = {"type": "document_url", "document_url": document_path}
    else:
        # Local file - convert to base64 data URI
        file_path = Path(document_path)

        # Read file and encode
        file_content = file_path.read_bytes()
        encoded_content = base64.b64encode(file_content).decode()

        # Determine MIME type
        suffix = file_path.suffix.lower()
        mime_types = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        mime_type = mime_types.get(suffix, "application/octet-stream")

        # Images use image_url, documents use document_url
        if suffix in {".png", ".jpg", ".jpeg"}:
            document_input = {
                "type": "image_url",
                "image_url": f"data:{mime_type};base64,{encoded_content}",
            }
        else:
            document_input = {
                "type": "document_url",
                "document_url": f"data:{mime_type};base64,{encoded_content}",
            }

    # Call Mistral OCR API
    response = get_client().ocr.process(
        model="mistral-ocr-latest",
        document=document_input,
        include_image_base64=include_images,
    )

    # Convert response to dict (handle Pydantic models)
    def to_dict(obj):
        """Convert Pydantic models to dicts recursively."""
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        elif hasattr(obj, "dict"):
            return obj.dict()
        elif isinstance(obj, list):
            return [to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: to_dict(v) for k, v in obj.items()}
        else:
            return obj

    return {
        "pages": to_dict(response.pages) if hasattr(response, "pages") else [],
        "model": response.model if hasattr(response, "model") else "mistral-ocr-latest",
        "usage_info": to_dict(response.usage_info)
        if hasattr(response, "usage_info")
        else {},
    }


def audio_transcription_adapter(
    audio_path: str,
    language: str = "",
    include_timestamps: bool = False,
) -> dict[str, Any]:
    """Mistral-specific audio transcription function."""
    # Prepare transcription request
    transcription_params = {
        "model": "voxtral-mini-latest",
    }

    # Handle input source
    if audio_path.startswith(("http://", "https://")):
        transcription_params["file_url"] = audio_path
    else:
        # Local file
        file_path = Path(audio_path)
        with open(file_path, "rb") as f:
            transcription_params["file"] = {
                "content": f,
                "file_name": file_path.name,
            }

    # Add optional parameters
    if language:
        transcription_params["language"] = language

    if include_timestamps:
        transcription_params["timestamp_granularities"] = ["segment"]

    # Call Mistral transcription API
    response = get_client().audio.transcriptions.complete(**transcription_params)

    # Build result
    result = {
        "text": response.text if hasattr(response, "text") else str(response),
    }

    # Add segments if timestamps requested
    if include_timestamps and hasattr(response, "segments"):
        result["segments"] = [
            {
                "start": seg.start if hasattr(seg, "start") else 0,
                "end": seg.end if hasattr(seg, "end") else 0,
                "text": seg.text if hasattr(seg, "text") else "",
            }
            for seg in response.segments
        ]

    return result


def embeddings_adapter(texts: list[str], model: str) -> list[list[float]]:
    """Generate embeddings for a list of texts."""
    response = get_client().embeddings.create(model=model, inputs=texts)
    return [item.embedding for item in response.data]


def moderation_adapter(text: str) -> dict[str, Any]:
    """Mistral-specific content moderation function."""
    # Call Mistral moderation API
    response = get_client().classifiers.moderate_chat(
        model="mistral-moderation-latest",
        inputs=[{"role": "user", "content": text}],
    )

    # Extract moderation results
    if response.results and len(response.results) > 0:
        result_data = response.results[0]

        # Build category scores and flags
        categories = {}
        category_flags = {}

        if hasattr(result_data, "categories"):
            # Handle dict, Pydantic model, or other object types
            cats = result_data.categories
            if isinstance(cats, dict):
                cat_dict = cats
            elif hasattr(cats, "model_dump"):
                cat_dict = cats.model_dump(exclude_none=True)
            else:
                cat_dict = {
                    k: v for k, v in vars(cats).items() if not k.startswith("_")
                }
            for cat_name, cat_value in cat_dict.items():
                categories[cat_name] = cat_value
                category_flags[cat_name] = cat_value is True

        return {
            "flagged": any(category_flags.values()),
            "categories": categories,
            "category_flags": category_flags,
        }

    return {
        "flagged": False,
        "categories": {},
        "category_flags": {},
    }


def fill_in_middle_adapter(
    prefix: str,
    suffix: str = "",
    model: str = "codestral-latest",
    max_tokens: int = 256,
    temperature: float = 0.0,
    stop: list[str] | None = None,
) -> dict[str, Any]:
    """Mistral-specific fill-in-the-middle code completion."""
    # Build FIM request
    fim_params = {
        "model": model,
        "prompt": prefix,
        "suffix": suffix,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    if stop:
        fim_params["stop"] = stop

    # Call Mistral FIM API
    response = get_client().fim.complete(**fim_params)

    if not response.choices or not response.choices[0].message.content:
        raise RuntimeError("No completion generated")

    completion = extract_text_content(response.choices[0].message.content)
    usage = response.usage

    return {
        "completion": completion,
        "full_code": prefix + completion + suffix,
        "model": model,
        "usage": {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        },
    }


def list_api_models() -> set[str]:
    """List model IDs available from the Mistral API."""
    models_response = get_client().models.list()
    return {model.id for model in models_response.data}
