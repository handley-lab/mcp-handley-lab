"""Mistral LLM tool for AI interactions via MCP."""

import base64
import os
import threading
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mistralai import Mistral
from pydantic import Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    build_server_info,
    get_session_id,
    is_text_file,
    load_provider_models,
    resolve_image_data,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.model_loader import get_structured_model_listing
from mcp_handley_lab.llm.shared import process_llm_request
from mcp_handley_lab.shared.models import LLMResult, ModelListing, ServerInfo

mcp = FastMCP("Mistral Tool")

# Lazy initialization of Mistral client
_client: Mistral | None = None
_client_lock = threading.Lock()


def _get_client() -> Mistral:
    """Get or create the global Mistral client with thread safety."""
    global _client
    with _client_lock:
        if _client is None:
            try:
                _client = Mistral(api_key=settings.mistral_api_key)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Mistral client: {e}") from e
    return _client


# Generate session ID once at module load time
_SESSION_ID = f"_session_{os.getpid()}_{int(time.time())}"

# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL, _get_model_config_from_loader = load_provider_models(
    "mistral"
)


def _get_session_id() -> LLMResult:
    """Get the persistent session ID for this MCP server process."""
    return get_session_id(mcp)


def _get_model_config(model: str) -> dict[str, int]:
    """Get token limits for a specific model."""
    return _get_model_config_from_loader(model)


def _resolve_files(files: list[str]) -> list[dict[str, Any]]:
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
            # For images, encode as base64
            file_content = file_path.read_bytes()
            encoded_content = base64.b64encode(file_content).decode()
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{encoded_content}",
                }
            )

    return content_parts


def _mistral_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Mistral-specific text generation function for the shared processor."""
    # Extract Mistral-specific parameters
    temperature = kwargs.get("temperature", 1.0)
    files = kwargs.get("files", [])

    # Get model configuration for output tokens
    model_config = _get_model_config(model)
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
        file_parts = _resolve_files(files)
        user_content.extend(file_parts)

    messages.append(
        {"role": "user", "content": user_content if len(user_content) > 1 else prompt}
    )

    # Generate response
    try:
        response = _get_client().chat.complete(
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
        "text": message.content,
        "input_tokens": usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
        "finish_reason": choice.finish_reason or "",
        "model_version": model,
        "response_id": response.id or "",
    }


def _mistral_image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Mistral-specific image analysis function for the shared processor."""
    # Extract image analysis specific parameters
    images = kwargs.get("images", [])

    # Get model configuration for output tokens
    model_config = _get_model_config(model)
    output_tokens = model_config.get("output_tokens", 8192)

    # Build message content with images
    content = [{"type": "text", "text": prompt}]

    # Add images
    for image_item in images:
        image_bytes = resolve_image_data(image_item)
        encoded_image = base64.b64encode(image_bytes).decode()
        content.append(
            {
                "type": "image_url",
                "image_url": f"data:image/jpeg;base64,{encoded_image}",
            }
        )

    # Build messages
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    messages.append({"role": "user", "content": content})

    # Generate response
    try:
        response = _get_client().chat.complete(
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
        "text": message.content,
        "input_tokens": usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
    }


@mcp.tool(
    description="Delegates a user query to external Mistral AI service. Can take a prompt directly or load it from a template file with variables. Returns Mistral's verbatim response. Use `agent_name` for separate conversation thread."
)
def ask(
    prompt: str = Field(
        default=None,
        description="The user's question to delegate to external Mistral AI service.",
    ),
    prompt_file: str = Field(
        default=None,
        description="Path to a file containing the prompt. Cannot be used with 'prompt'.",
    ),
    prompt_vars: dict[str, str] = Field(
        default_factory=dict,
        description="A dictionary of variables for template substitution in the prompt using ${var} syntax (e.g., {'topic': 'API design'}).",
    ),
    output_file: str = Field(
        ...,
        description="File path to save Mistral's response.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with Mistral AI service (distinct from your conversation with the user).",
    ),
    model: str = Field(
        default=DEFAULT_MODEL,
        description="The Mistral model to use for the request. Default is 'mistral-large-latest' (recommended). Other options: 'mistral-small-latest', 'codestral-latest', 'ministral-8b-latest'. Only change if user explicitly requests a different model.",
    ),
    temperature: float = Field(
        default=1.0,
        description="Controls randomness in the response. Higher values (e.g., 1.0) are more creative, lower values are more deterministic. Only change if user explicitly requests.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of file paths to provide as context to the model.",
    ),
    system_prompt: str = Field(
        default=None,
        description="System instructions to send to external Mistral AI service. Remembered for this conversation thread.",
    ),
    system_prompt_file: str = Field(
        default=None,
        description="Path to a file containing system instructions. Cannot be used with 'system_prompt'.",
    ),
    system_prompt_vars: dict[str, str] = Field(
        default_factory=dict,
        description="A dictionary of variables for template substitution in the system prompt using ${var} syntax.",
    ),
) -> LLMResult:
    """Ask Mistral a question with optional persistent memory."""
    return process_llm_request(
        prompt=prompt,
        prompt_file=prompt_file,
        prompt_vars=prompt_vars,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="mistral",
        generation_func=_mistral_generation_adapter,
        mcp_instance=mcp,
        temperature=temperature,
        files=files,
        system_prompt=system_prompt,
        system_prompt_file=system_prompt_file,
        system_prompt_vars=system_prompt_vars,
    )


@mcp.tool(
    description="Delegates image analysis to external Mistral vision AI service (Pixtral) on behalf of the user. Returns Mistral's verbatim visual analysis to assist the user. Ideal for OCR and image understanding."
)
def analyze_image(
    prompt: str = Field(
        ...,
        description="The user's question about the images to delegate to external Mistral vision AI service.",
    ),
    output_file: str = Field(
        ...,
        description="File path to save Mistral's visual analysis.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of image file paths or base64 encoded strings to be analyzed.",
    ),
    focus: str = Field(
        default="general",
        description="The area of focus for the analysis (e.g., 'ocr', 'objects'). Note: This is a placeholder parameter in the current implementation.",
    ),
    model: str = Field(
        default="pixtral-large-latest",
        description="The Mistral vision model to use. Default is 'pixtral-large-latest' (recommended). Other option: 'pixtral-12b-2409'. Only change if user explicitly requests a different model.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with Mistral AI service (distinct from your conversation with the user).",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external Mistral AI service. Remembered for this conversation thread.",
    ),
) -> LLMResult:
    """Analyze images with Mistral vision model (Pixtral)."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="mistral",
        generation_func=_mistral_image_analysis_adapter,
        mcp_instance=mcp,
        images=files,
        focus=focus,
        system_prompt=system_prompt,
    )


@mcp.tool(
    description="Process documents with Mistral OCR for high-accuracy text extraction. Supports PDFs, images, PPTX, and DOCX. Returns structured markdown text with bounding boxes and metadata."
)
def process_ocr(
    document_path: str = Field(
        ...,
        description="Path to document file (PDF, image, PPTX, DOCX) or URL. Supports local files, HTTP(S) URLs, or base64 data URIs.",
    ),
    output_file: str = Field(
        ...,
        description="File path to save OCR results as JSON.",
    ),
    include_images: bool = Field(
        default=True,
        description="Whether to include base64-encoded images with bounding boxes in the response.",
    ),
) -> dict[str, Any]:
    """Process document with Mistral OCR for text extraction.

    Returns structured OCR results with:
    - pages: Array of extracted content per page
    - markdown: Formatted text extraction
    - images: Bounding box coordinates and base64 data (if include_images=True)
    - dimensions: DPI, height, width metadata
    - model: Version identifier
    - usage_info: Pages processed and document size
    """
    try:
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
            if not file_path.exists():
                raise FileNotFoundError(f"Document not found: {document_path}")

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
        response = _get_client().ocr.process(
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

        result = {
            "pages": to_dict(response.pages) if hasattr(response, "pages") else [],
            "model": response.model
            if hasattr(response, "model")
            else "mistral-ocr-latest",
            "usage_info": to_dict(response.usage_info)
            if hasattr(response, "usage_info")
            else {},
        }

        # Write output to file
        import json

        Path(output_file).write_text(json.dumps(result, indent=2))

        return result

    except Exception as e:
        raise ValueError(f"Mistral OCR error: {str(e)}") from e


@mcp.tool(
    description="Lists all available Mistral models with pricing, capabilities, and context windows. Helps compare models for cost, performance, and features to select the best model for specific tasks."
)
def list_models() -> ModelListing:
    """List available Mistral models with detailed information."""
    # Get models from API
    try:
        models_response = _get_client().models.list()
        api_model_names = {model.id for model in models_response.data}
    except Exception:
        # If API call fails, use models from YAML config
        api_model_names = set(MODEL_CONFIGS.keys())

    # Use structured model listing
    return get_structured_model_listing("mistral", api_model_names)


@mcp.tool(
    description="Checks Mistral Tool server status and API connectivity. Returns version info, model availability, and a list of available functions."
)
def server_info() -> ServerInfo:
    """Get server status and Mistral configuration without making a network call."""
    # Get model names from the local YAML config
    available_models = list(MODEL_CONFIGS.keys())

    # Build server info with vision support
    info = build_server_info(
        provider_name="Mistral",
        available_models=available_models,
        memory_manager=memory_manager,
        vision_support=True,
        image_generation=False,
    )

    return info


@mcp.tool(description="Tests the connection to the Mistral API by listing models.")
def test_connection() -> str:
    """Tests the connection to the Mistral API."""
    try:
        models_response = _get_client().models.list()
        model_count = len(models_response.data)
        return f"✅ Connection successful. Found {model_count} models."
    except Exception as e:
        return f"❌ Connection failed: {e}"
