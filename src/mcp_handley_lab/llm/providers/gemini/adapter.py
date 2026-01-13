"""Gemini provider adapter for unified LLM tools.

Contains provider-specific generation functions that implement the Gemini API calls.
These adapters are used by the unified mcp-chat tool.
"""

import base64
import io
import os
import threading
import time
from pathlib import Path
from typing import Any

from google import genai as google_genai
from google.genai.types import (
    Blob,
    FileData,
    GenerateContentConfig,
    GenerateImagesConfig,
    GoogleSearch,
    GoogleSearchRetrieval,
    ImageConfig,
    Part,
    ThinkingConfig,
    Tool,
    UploadFileConfig,
)
from PIL import Image

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    get_gemini_safe_mime_type,
    is_text_file,
    load_provider_models,
    resolve_image_data,
)

# Constants for configuration
GEMINI_INLINE_FILE_LIMIT_BYTES = 20 * 1024 * 1024  # 20MB

# Lazy initialization of Gemini client
_client: google_genai.Client | None = None
_client_lock = threading.Lock()


def get_client() -> google_genai.Client:
    """Get or create the global Gemini client with thread safety."""
    global _client
    with _client_lock:
        if _client is None:
            try:
                _client = google_genai.Client(api_key=settings.gemini_api_key)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Gemini client: {e}") from e
    return _client


def reset_client() -> None:
    """Reset the global client. Used by tests to ensure VCR can intercept requests."""
    global _client
    with _client_lock:
        _client = None


# Generate session ID once at module load time
_SESSION_ID = f"_session_{os.getpid()}_{int(time.time())}"


# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL = load_provider_models("gemini")


def get_model_config(model: str) -> dict[str, int]:
    """Get token limits for a specific model."""
    return MODEL_CONFIGS.get(model, MODEL_CONFIGS[DEFAULT_MODEL])


def resolve_files(files: list[str]) -> tuple[list[Part], bool]:
    """Resolve file inputs to structured content parts for google-genai API.

    Uses inlineData for files <20MB and Files API for larger files.
    Returns tuple of (Part objects list, Files API used flag).
    """
    parts = []
    used_files_api = False
    for file_item in files:
        # Handle unified format: strings or {"path": "..."} dicts
        if isinstance(file_item, str):
            file_path = Path(file_item)
        elif isinstance(file_item, dict) and "path" in file_item:
            file_path = Path(file_item["path"])
        else:
            raise ValueError(f"Invalid file item format: {file_item}")
        file_size = file_path.stat().st_size

        if file_size > GEMINI_INLINE_FILE_LIMIT_BYTES:
            # Large file - use Files API
            used_files_api = True
            config = UploadFileConfig(mimeType=get_gemini_safe_mime_type(file_path))
            uploaded_file = get_client().files.upload(
                file=str(file_path),
                config=config,
            )
            parts.append(Part(fileData=FileData(fileUri=uploaded_file.uri)))
        else:
            # Small file - use inlineData with base64 encoding
            if is_text_file(file_path):
                # For text files, read directly as text
                content = file_path.read_text(encoding="utf-8")
                parts.append(Part(text=f"[File: {file_path.name}]\n{content}"))
            else:
                # For binary files, use inlineData
                file_content = file_path.read_bytes()
                encoded_content = base64.b64encode(file_content).decode()
                parts.append(
                    Part(
                        inlineData=Blob(
                            mimeType=get_gemini_safe_mime_type(file_path),
                            data=encoded_content,
                        )
                    )
                )

    return parts, used_files_api


def resolve_images(images: list[str] | None = None) -> list[Image.Image]:
    """Resolve image inputs to PIL Image objects."""
    if images is None:
        images = []
    image_list = []

    # Handle images array
    for image_item in images:
        image_bytes = resolve_image_data(image_item)
        image_list.append(Image.open(io.BytesIO(image_bytes)))

    return image_list


def generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Gemini-specific text generation function for the shared processor."""
    # Extract Gemini-specific parameters from options dict
    options = kwargs.get("options", {})
    temperature = kwargs.get("temperature", 1.0)
    grounding = options.get("grounding", False)
    files = kwargs.get("files", [])
    include_thoughts = options.get("include_thoughts", False)
    thinking_level = options.get("thinking_level")
    thinking_budget = options.get("thinking_budget")

    # Configure tools for grounding if requested
    tools = []
    if grounding:
        if model.startswith("gemini-1.5"):
            tools.append(Tool(google_search_retrieval=GoogleSearchRetrieval()))
        else:
            tools.append(Tool(google_search=GoogleSearch()))

    # Resolve file contents
    file_parts, used_files_api = resolve_files(files)

    # Get model configuration and token limits
    model_config = get_model_config(model)
    output_tokens = model_config["output_tokens"]

    # Build thinking config if requested
    thinking_config = None
    if include_thoughts or thinking_level or thinking_budget is not None:
        thinking_params: dict[str, Any] = {"include_thoughts": include_thoughts}
        # Gemini 3 uses thinking_level (LOW/HIGH)
        if thinking_level:
            thinking_params["thinking_level"] = thinking_level.upper()
        # Gemini 2.5 uses thinking_budget (token count, -1=dynamic, 0=disable)
        if thinking_budget is not None:
            thinking_params["thinking_budget"] = thinking_budget
        thinking_config = ThinkingConfig(**thinking_params)

    # Prepare config
    config_params: dict[str, Any] = {
        "temperature": temperature,
        "max_output_tokens": output_tokens,
    }
    if system_instruction:
        config_params["system_instruction"] = system_instruction
    if tools:
        config_params["tools"] = tools
    if thinking_config:
        config_params["thinking_config"] = thinking_config

    config = GenerateContentConfig(**config_params)

    # Convert history to Gemini format
    gemini_history = [
        {
            "role": "model" if msg["role"] == "assistant" else msg["role"],
            "parts": [{"text": msg["content"]}],
        }
        for msg in history
    ]

    # Generate content
    try:
        if gemini_history:
            # Continue existing conversation
            user_parts = [Part(text=prompt)] + file_parts
            contents = gemini_history + [
                {"role": "user", "parts": [part.to_json_dict() for part in user_parts]}
            ]
            response = get_client().models.generate_content(
                model=model, contents=contents, config=config
            )
        else:
            # New conversation
            if file_parts:
                content_parts = [Part(text=prompt)] + file_parts
                response = get_client().models.generate_content(
                    model=model, contents=content_parts, config=config
                )
            else:
                response = get_client().models.generate_content(
                    model=model, contents=prompt, config=config
                )
    except Exception as e:
        # Convert all API errors to ValueError for consistent error handling
        raise ValueError(f"Gemini API error: {str(e)}") from e

    # Extract text, separating thinking from answer
    text_parts = []
    thinking_parts = []
    if response.candidates and response.candidates[0].content:
        for part in response.candidates[0].content.parts:
            if getattr(part, "thought", None):
                # Thought parts contain reasoning content - extract the text
                thought_text = getattr(part, "text", "") or str(part.thought)
                if thought_text:
                    thinking_parts.append(thought_text)
            elif getattr(part, "text", None):
                text_parts.append(part.text)

    # Build reasoning_text from thinking parts
    reasoning_text = "\n".join(thinking_parts) if thinking_parts else ""

    # Format output with thinking if present
    if thinking_parts and include_thoughts:
        answer_text = "\n".join(text_parts) if text_parts else ""
        text = f"<thinking>\n{reasoning_text}\n</thinking>\n\n{answer_text}"
    elif text_parts:
        text = "\n".join(text_parts)
    elif response.text:
        text = response.text
    else:
        raise RuntimeError("No response text generated")

    # Extract grounding metadata - SDK converts to snake_case
    grounding_metadata = None
    response_dict = response.to_json_dict()
    if "candidates" in response_dict and response_dict["candidates"]:
        candidate = response_dict["candidates"][0]
        if "grounding_metadata" in candidate:
            metadata = candidate["grounding_metadata"]
            # Skip if empty (happens with conversational history reusing previous grounding)
            if metadata:
                grounding_metadata = {
                    "web_search_queries": metadata["web_search_queries"],
                    "grounding_chunks": [
                        {"uri": chunk["web"]["uri"], "title": chunk["web"]["title"]}
                        for chunk in metadata["grounding_chunks"]
                        if "web" in chunk
                    ],
                    "grounding_supports": metadata["grounding_supports"],
                    "search_entry_point": metadata["search_entry_point"],
                }

    # Extract additional response metadata
    finish_reason = ""
    avg_logprobs = None
    if response.candidates and len(response.candidates) > 0:
        candidate = response.candidates[0]
        if candidate.finish_reason:
            finish_reason = str(candidate.finish_reason)
        if candidate.avg_logprobs is not None:
            avg_logprobs = float(candidate.avg_logprobs)

    # Extract generation time from server-timing header
    generation_time_ms = 0
    if not used_files_api and getattr(response, "sdk_http_response", None):
        http_dict = response.sdk_http_response.to_json_dict()
        headers = http_dict.get("headers", {})
        server_timing = headers.get("server-timing", "")
        if "dur=" in server_timing:
            dur_part = server_timing.split("dur=")[1].split(";")[0].split(",")[0]
            generation_time_ms = int(float(dur_part))

    # Extract thinking token count if available
    thoughts_token_count = (
        getattr(response.usage_metadata, "thoughts_token_count", 0) or 0
    )

    # Extract token modality breakdown (Gemini-specific)
    token_modalities = {}
    usage = response.usage_metadata
    if usage:
        prompt_details = getattr(usage, "prompt_tokens_details", None)
        if prompt_details:
            token_modalities["prompt"] = [
                {
                    "modality": getattr(d, "modality", ""),
                    "count": getattr(d, "token_count", 0),
                }
                for d in prompt_details
            ]
        candidates_details = getattr(usage, "candidates_tokens_details", None)
        if candidates_details:
            token_modalities["output"] = [
                {
                    "modality": getattr(d, "modality", ""),
                    "count": getattr(d, "token_count", 0),
                }
                for d in candidates_details
            ]

    return {
        "text": text,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count,
        "total_tokens": getattr(response.usage_metadata, "total_token_count", 0) or 0,
        "thoughts_token_count": thoughts_token_count,
        "grounding_metadata": grounding_metadata,
        "finish_reason": finish_reason,
        "avg_logprobs": avg_logprobs,
        "model_version": response.model_version,
        "generation_time_ms": generation_time_ms,
        "response_id": response.response_id or "",
        "token_modalities": token_modalities,
        "reasoning_text": reasoning_text,
    }


def image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Gemini-specific image analysis function for the shared processor."""
    # Extract image analysis specific parameters
    images = kwargs.get("images", [])

    # Load images
    image_list = resolve_images(images)

    # Get model configuration
    model_config = get_model_config(model)
    output_tokens = model_config["output_tokens"]

    # Prepare content with images
    content = [prompt] + image_list

    # Prepare the config
    config_params = {"max_output_tokens": output_tokens, "temperature": 1.0}
    if system_instruction:
        config_params["system_instruction"] = system_instruction

    config = GenerateContentConfig(**config_params)

    # Generate response - image analysis starts fresh conversation
    try:
        response = get_client().models.generate_content(
            model=model, contents=content, config=config
        )
    except Exception as e:
        raise ValueError(f"Gemini API error: {str(e)}") from e

    if not response.text:
        raise RuntimeError("No response text generated")

    return {
        "text": response.text,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count,
        "total_tokens": getattr(response.usage_metadata, "total_token_count", 0) or 0,
    }


def _is_nano_banana_model(model: str) -> bool:
    """Check if model is a Nano Banana model (uses generate_content API)."""
    return "gemini-" in model and "-image" in model


def _generate_with_nano_banana(prompt: str, model: str, **kwargs) -> dict:
    """Generate image using Nano Banana models via generate_content API."""
    # Build image config for aspect ratio and size
    image_config_params = {}
    if aspect_ratio := kwargs.get("aspect_ratio"):
        image_config_params["aspect_ratio"] = aspect_ratio
    if image_size := kwargs.get("size"):
        # Must be uppercase K (1K, 2K, 4K)
        image_config_params["image_size"] = image_size.upper()

    config_params = {"response_modalities": ["image", "text"]}
    if image_config_params:
        config_params["image_config"] = ImageConfig(**image_config_params)

    config = GenerateContentConfig(**config_params)

    # Build content parts: prompt text + any input images
    content_parts = [Part(text=prompt)]
    input_images = kwargs.get("input_images", [])
    if input_images:
        image_list = resolve_images(input_images)
        for img in image_list:
            # Convert PIL Image to bytes
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            img_bytes = buf.getvalue()
            content_parts.append(
                Part(
                    inlineData=Blob(
                        mimeType="image/png",
                        data=base64.b64encode(img_bytes).decode(),
                    )
                )
            )

    response = get_client().models.generate_content(
        model=model,
        contents=content_parts,
        config=config,
    )

    # Extract image from response parts
    image_bytes = None
    text_response = ""
    mime_type = "image/png"

    if response.candidates and response.candidates[0].content:
        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                # SDK returns data as bytes or base64 string depending on version
                raw_data = part.inline_data.data
                if isinstance(raw_data, str):
                    image_bytes = base64.b64decode(raw_data)
                else:
                    image_bytes = raw_data
                mime_type = part.inline_data.mime_type or "image/png"
            elif hasattr(part, "text") and part.text:
                text_response = part.text

    if not image_bytes:
        raise RuntimeError(
            f"No image generated. Model response: {text_response or 'empty'}"
        )

    # Extract token usage
    input_tokens = 0
    output_tokens = 1
    if response.usage_metadata:
        input_tokens = response.usage_metadata.prompt_token_count or 0
        output_tokens = response.usage_metadata.candidates_token_count or 0

    return {
        "image_bytes": image_bytes,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "enhanced_prompt": "",
        "original_prompt": prompt,
        "mime_type": mime_type,
        "text_response": text_response,
        "gemini_metadata": {
            "actual_model_used": model,
            "requested_model": model,
            "generation_type": "nano_banana",
        },
    }


def _generate_with_imagen(prompt: str, model: str, **kwargs) -> dict:
    """Generate image using Imagen models via generate_images API."""
    aspect_ratio = kwargs.get("aspect_ratio", "1:1")
    config = GenerateImagesConfig(number_of_images=1, aspect_ratio=aspect_ratio)

    response = get_client().models.generate_images(
        model=model,
        prompt=prompt,
        config=config,
    )

    if not response.generated_images or not response.generated_images[0].image:
        raise RuntimeError("Generated image has no data")

    generated_image = response.generated_images[0]
    image = generated_image.image

    # Extract safety attributes
    safety_attributes = {}
    if generated_image.safety_attributes:
        safety_attributes = {
            "categories": generated_image.safety_attributes.categories,
            "scores": generated_image.safety_attributes.scores,
            "content_type": generated_image.safety_attributes.content_type,
        }

    return {
        "image_bytes": image.image_bytes,
        "input_tokens": 0,
        "output_tokens": 1,
        "enhanced_prompt": generated_image.enhanced_prompt or "",
        "original_prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "requested_format": "png",
        "mime_type": image.mime_type or "image/png",
        "cloud_uri": image.gcs_uri or "",
        "content_filter_reason": generated_image.rai_filtered_reason or "",
        "safety_attributes": safety_attributes,
        "gemini_metadata": {
            "positive_prompt_safety_attributes": response.positive_prompt_safety_attributes,
            "actual_model_used": model,
            "requested_model": model,
            "generation_type": "imagen",
        },
    }


def image_generation_adapter(prompt: str, model: str, **kwargs) -> dict:
    """Gemini-specific image generation function.

    Routes to appropriate API based on model type:
    - Nano Banana models (gemini-*-image*): uses generate_content API
    - Imagen models: uses generate_images API
    """
    if _is_nano_banana_model(model):
        return _generate_with_nano_banana(prompt, model, **kwargs)
    else:
        return _generate_with_imagen(prompt, model, **kwargs)


def list_api_models() -> set[str]:
    """List model names available from the Gemini API."""
    models_response = get_client().models.list()
    return {model.name.split("/")[-1] for model in models_response}


def embeddings_adapter(texts: list[str], model: str) -> list[list[float]]:
    """Generate embeddings for a list of texts."""
    result = []
    for text in texts:
        response = get_client().models.embed_content(model=model, contents=text)
        # response.embeddings is a list of ContentEmbedding, each has .values
        result.append(response.embeddings[0].values)
    return result
