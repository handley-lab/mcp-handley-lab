"""Gemini LLM tool for AI interactions via MCP."""
import base64
import io
import os
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
    Part,
    Tool,
)
from mcp.server.fastmcp import FastMCP
from PIL import Image

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    get_gemini_safe_mime_type,
    get_session_id,
    is_text_file,
    resolve_image_data,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.model_loader import (
    build_model_configs_dict,
    get_structured_model_listing,
    load_model_config,
)
from mcp_handley_lab.llm.shared import process_image_generation, process_llm_request
from mcp_handley_lab.shared.models import (
    ImageGenerationResult,
    LLMResult,
    ModelListing,
    ServerInfo,
)

mcp = FastMCP("Gemini Tool")

# Configure Gemini client - fail fast if API key is invalid/missing
client = google_genai.Client(api_key=settings.gemini_api_key)

# Generate session ID once at module load time
_SESSION_ID = f"_session_{os.getpid()}_{int(time.time())}"


# Client initialization decorator is no longer needed with fail-fast approach
# If we reach this point, the client is guaranteed to be initialized
def require_client(func):
    """Identity decorator - no longer needed with fail-fast approach."""
    return func


# Load model configurations from YAML
MODEL_CONFIGS = build_model_configs_dict("gemini")

# Load default model from YAML
_config = load_model_config("gemini")
DEFAULT_MODEL = _config["default_model"]


def _get_session_id() -> LLMResult:
    """Get the persistent session ID for this MCP server process."""
    return get_session_id(mcp)


def _get_model_config(model: str) -> dict[str, int]:
    """Get token limits for a specific model."""
    return MODEL_CONFIGS.get(model, MODEL_CONFIGS[DEFAULT_MODEL])


def _resolve_files(
    files: list[str],
) -> list[Part]:
    """Resolve file inputs to structured content parts for google-genai API.

    Uses inlineData for files <20MB and Files API for larger files.
    Returns list of Part objects that can be included in contents.
    """
    if not files:
        return []

    parts = []
    for file_item in files:
        # Handle unified format: strings or {"path": "..."} dicts
        if isinstance(file_item, str):
            file_path = Path(file_item)
        elif isinstance(file_item, dict) and "path" in file_item:
            file_path = Path(file_item["path"])
        else:
            continue  # Skip invalid items
        file_size = file_path.stat().st_size

        if file_size > 20 * 1024 * 1024:  # 20MB threshold
            # Large file - use Files API
            uploaded_file = client.files.upload(
                file=str(file_path),
                mime_type=get_gemini_safe_mime_type(file_path),
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

    return parts


def _resolve_images(
    images: list[str] = [],
) -> list[Image.Image]:
    """Resolve image inputs to PIL Image objects."""
    image_list = []

    # Handle images array
    if images:
        for image_item in images:
            image_bytes = resolve_image_data(image_item)
            image_list.append(Image.open(io.BytesIO(image_bytes)))

    return image_list


def _gemini_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Gemini-specific text generation function for the shared processor."""
    # Extract Gemini-specific parameters
    temperature = kwargs.get("temperature", 0.7)
    grounding = kwargs.get("grounding", False)
    files = kwargs.get("files")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Configure tools for grounding if requested
    tools = []
    if grounding:
        if model.startswith("gemini-1.5"):
            tools.append(Tool(google_search_retrieval=GoogleSearchRetrieval()))
        else:
            tools.append(Tool(google_search=GoogleSearch()))

    # Resolve file contents
    file_parts = _resolve_files(files)

    # Get model configuration and token limits
    model_config = _get_model_config(model)
    max_output = model_config["output_tokens"]
    output_tokens = (
        min(max_output_tokens, max_output) if max_output_tokens > 0 else max_output
    )

    # Prepare config
    config_params = {
        "temperature": temperature,
        "max_output_tokens": output_tokens,
    }
    if system_instruction:
        config_params["system_instruction"] = system_instruction
    if tools:
        config_params["tools"] = tools

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
    if gemini_history:
        # Continue existing conversation
        user_parts = [Part(text=prompt)] + file_parts
        contents = gemini_history + [
            {"role": "user", "parts": [part.to_json_dict() for part in user_parts]}
        ]
        response = client.models.generate_content(
            model=model, contents=contents, config=config
        )
    else:
        # New conversation
        if file_parts:
            content_parts = [Part(text=prompt)] + file_parts
            response = client.models.generate_content(
                model=model, contents=content_parts, config=config
            )
        else:
            response = client.models.generate_content(
                model=model, contents=prompt, config=config
            )

    if not response.text:
        raise RuntimeError("No response text generated")

    # Extract grounding metadata if available
    grounding_metadata = None
    response_dict = response.to_json_dict()
    if "candidates" in response_dict and response_dict["candidates"]:
        candidate = response_dict["candidates"][0]
        if "grounding_metadata" in candidate:
            metadata = candidate["grounding_metadata"]
            grounding_metadata = {
                "web_search_queries": metadata.get("web_search_queries", []),
                "grounding_chunks": [
                    {"uri": chunk["web"]["uri"], "title": chunk["web"]["title"]}
                    for chunk in metadata.get("grounding_chunks", [])
                    if "web" in chunk
                ],
                "grounding_supports": metadata.get("grounding_supports", []),
                "retrieval_metadata": metadata.get("retrieval_metadata", {}),
                "search_entry_point": metadata.get("search_entry_point", {}),
            }

    # Extract additional response metadata
    finish_reason = ""
    avg_logprobs = 0.0
    if response.candidates and len(response.candidates) > 0:
        candidate = response.candidates[0]
        if hasattr(candidate, "finish_reason") and candidate.finish_reason:
            finish_reason = str(candidate.finish_reason)
        if hasattr(candidate, "avg_logprobs") and candidate.avg_logprobs is not None:
            avg_logprobs = float(candidate.avg_logprobs)

    # Extract generation time from server-timing header
    generation_time_ms = 0
    if hasattr(response, "sdk_http_response") and response.sdk_http_response:
        http_dict = response.sdk_http_response.to_json_dict()
        headers = http_dict.get("headers", {})
        server_timing = headers.get("server-timing", "")
        if "dur=" in server_timing:
            try:
                # Extract duration from "gfet4t7; dur=11255" format
                dur_part = server_timing.split("dur=")[1].split(";")[0].split(",")[0]
                generation_time_ms = int(float(dur_part))
            except (ValueError, IndexError):
                generation_time_ms = 0

    return {
        "text": response.text,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count,
        "grounding_metadata": grounding_metadata,
        "finish_reason": finish_reason,
        "avg_logprobs": avg_logprobs,
        "model_version": getattr(response, "model_version", ""),
        "generation_time_ms": generation_time_ms,
        "response_id": "",  # Gemini doesn't provide a response ID
    }


def _gemini_image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Gemini-specific image analysis function for the shared processor."""
    # Extract image analysis specific parameters
    images = kwargs.get("images", [])
    max_output_tokens = kwargs.get("max_output_tokens")

    # Load images
    image_list = _resolve_images(images)

    # Get model configuration
    model_config = _get_model_config(model)
    max_output = model_config["output_tokens"]
    output_tokens = (
        min(max_output_tokens, max_output) if max_output_tokens > 0 else max_output
    )

    # Prepare content with images
    content = [prompt] + image_list

    # Prepare the config
    config_params = {"max_output_tokens": output_tokens, "temperature": 0.7}
    if system_instruction:
        config_params["system_instruction"] = system_instruction

    config = GenerateContentConfig(**config_params)

    # Generate response - image analysis starts fresh conversation
    response = client.models.generate_content(
        model=model, contents=content, config=config
    )

    if not response.text:
        raise RuntimeError("No response text generated")

    return {
        "text": response.text,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count,
        "finish_reason": "stop",  # Gemini image analysis always stops naturally
        "avg_logprobs": 0.0,  # Gemini doesn't provide logprobs
        "model_version": "",  # Not available for image analysis
        "generation_time_ms": 0,  # Not extracted for image analysis
        "response_id": "",  # Gemini doesn't provide a response ID
    }


@mcp.tool(
    description="Sends a prompt to a Gemini model for a conversational response. Use `agent_name` for persistent memory and `files` to provide context. Response is saved to `output_file` ('-' for stdout)."
)
@require_client
def ask(
    prompt: str,
    output_file: str = "-",
    agent_name: str = "session",
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    grounding: bool = False,
    files: list[str] = [],
    max_output_tokens: int = 0,
) -> LLMResult:
    """Ask Gemini a question with optional persistent memory."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="gemini",
        generation_func=_gemini_generation_adapter,
        mcp_instance=mcp,
        temperature=temperature,
        grounding=grounding,
        files=files,
        max_output_tokens=max_output_tokens,
    )


@mcp.tool(
    description="Analyzes images using a Gemini vision model. Provide a prompt and a list of image file paths. Use `agent_name` for persistent memory. Response is saved to `output_file` ('-' for stdout)."
)
@require_client
def analyze_image(
    prompt: str,
    output_file: str = "-",
    files: list[str] = [],
    focus: str = "general",
    model: str = DEFAULT_MODEL,
    agent_name: str = "session",
    max_output_tokens: int = 0,
) -> LLMResult:
    """Analyze images with Gemini vision model."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="gemini",
        generation_func=_gemini_image_analysis_adapter,
        mcp_instance=mcp,
        images=files,
        focus=focus,
        max_output_tokens=max_output_tokens,
    )


def _gemini_image_generation_adapter(prompt: str, model: str, **kwargs) -> dict:
    """Gemini-specific image generation function with comprehensive metadata extraction."""
    model_mapping = {
        "imagen-3": "imagen-3.0-generate-002",
        "imagen-4": "imagen-4.0-generate-002",
        "imagen-4-ultra": "imagen-4.0-generate-002",
        "image": "imagen-3.0-generate-002",
        "image-flash": "imagen-3.0-generate-002",
    }
    actual_model = model_mapping.get(model, "imagen-3.0-generate-002")

    # Extract config parameters for metadata
    aspect_ratio = kwargs.get("aspect_ratio", "1:1")
    config = GenerateImagesConfig(number_of_images=1, aspect_ratio=aspect_ratio)

    response = client.models.generate_images(
        model=actual_model,
        prompt=prompt,
        config=config,
    )

    if not response.generated_images or not response.generated_images[0].image:
        raise RuntimeError("Generated image has no data")

    # Extract response data
    generated_image = response.generated_images[0]
    image = generated_image.image

    # Estimate tokens for cost calculation
    input_tokens = len(prompt.split()) * 2

    # Extract safety attributes
    safety_attributes = {}
    if generated_image.safety_attributes:
        safety_attributes = {
            "categories": generated_image.safety_attributes.categories,
            "scores": generated_image.safety_attributes.scores,
            "content_type": generated_image.safety_attributes.content_type,
        }

    # Extract provider-specific metadata
    gemini_metadata = {
        "positive_prompt_safety_attributes": response.positive_prompt_safety_attributes,
        "actual_model_used": actual_model,
        "requested_model": model,
    }

    return {
        "image_bytes": image.image_bytes,
        "input_tokens": input_tokens,
        "enhanced_prompt": generated_image.enhanced_prompt or "",
        "original_prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "requested_format": "png",  # Gemini always returns PNG
        "mime_type": image.mime_type or "image/png",
        "cloud_uri": image.gcs_uri or "",
        "content_filter_reason": generated_image.rai_filtered_reason or "",
        "safety_attributes": safety_attributes,
        "gemini_metadata": gemini_metadata,
    }


@mcp.tool(
    description="Generates high-quality images using Google's Imagen 3 model. Provide creative prompts and the AI generates visual content. Supports persistent memory via `agent_name` parameter. Generated images are saved as PNG files to temporary locations."
)
@require_client
def generate_image(
    prompt: str, model: str = "imagen-3", agent_name: str = "session"
) -> ImageGenerationResult:
    """Generate images with Google's Imagen 3 model."""
    return process_image_generation(
        prompt=prompt,
        agent_name=agent_name,
        model=model,
        provider="gemini",
        generation_func=_gemini_image_generation_adapter,
        mcp_instance=mcp,
    )


@mcp.tool(
    description="Lists all available Gemini models with pricing, capabilities, and context windows. Helps compare models for cost, performance, and features to select the best model for specific tasks."
)
@require_client
def list_models() -> ModelListing:
    """List available Gemini models with detailed information."""

    # Get models from API
    models_response = client.models.list()
    api_model_names = {model.name.split("/")[-1] for model in models_response}

    # Use structured model listing
    return get_structured_model_listing("gemini", api_model_names)


@mcp.tool(
    description="Checks Gemini Tool server status and API connectivity. Returns version info, model availability, and a list of available functions."
)
@require_client
def server_info() -> ServerInfo:
    """Get server status and Gemini configuration."""

    # Test API by listing models
    models_response = client.models.list()
    available_models = []
    for model in models_response:
        if "gemini" in model.name:
            available_models.append(model.name.split("/")[-1])

    # Get agent count
    agent_count = len(memory_manager.list_agents())

    return ServerInfo(
        name="Gemini Tool",
        version="1.0.0",
        status="active",
        capabilities=[
            "ask - Chat with Gemini models (persistent memory enabled by default)",
            "analyze_image - Image analysis with vision models (persistent memory enabled by default)",
            "generate_image - Generate images with Imagen 3 (persistent memory enabled by default)",
            "list_models - List available Gemini models with detailed information",
            "server_info - Get server status",
        ],
        dependencies={
            "api_key": "configured",
            "available_models": f"{len(available_models)} models",
            "active_agents": str(agent_count),
            "memory_storage": str(memory_manager.storage_dir),
        },
    )
