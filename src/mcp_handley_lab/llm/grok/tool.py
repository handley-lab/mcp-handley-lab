"""Grok LLM tool for AI interactions via MCP."""
import base64
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from xai_sdk import Client

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    resolve_files_for_llm,
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

mcp = FastMCP("Grok Tool")

# Configure Grok client
client = Client(api_key=settings.xai_api_key)

# Load model configurations from YAML
MODEL_CONFIGS = build_model_configs_dict("grok")

# Load default model from YAML
_config = load_model_config("grok")
DEFAULT_MODEL = _config["default_model"]


def _get_model_config(model: str) -> dict[str, Any]:
    """Get token limits and parameter name for a specific model."""
    return MODEL_CONFIGS.get(model, MODEL_CONFIGS[DEFAULT_MODEL])


def _grok_generation_adapter(
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
    files = kwargs.get("files")
    max_output_tokens = kwargs.get("max_output_tokens")

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
    model_config = _get_model_config(model)
    default_tokens = model_config["output_tokens"]

    # Build request parameters
    request_params = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    # Add max tokens
    if max_output_tokens > 0:
        request_params["max_tokens"] = max_output_tokens
    else:
        request_params["max_tokens"] = default_tokens

    # Make API call using XAI SDK's two-step process
    chat_session = client.chat.create(**request_params)
    response = chat_session.sample()

    if not response or not response.proto or not response.proto.choices:
        raise RuntimeError("No response generated")

    # Extract response data from proto
    choice = response.proto.choices[0]
    finish_reason = choice.finish_reason

    # Extract logprobs if available
    avg_logprobs = 0.0
    if hasattr(choice, "logprobs") and choice.logprobs:
        logprobs = [token.logprob for token in choice.logprobs.content]
        avg_logprobs = sum(logprobs) / len(logprobs) if logprobs else 0.0

    # Get message content - Grok uses reasoning_content for its responses
    message_content = ""
    if hasattr(choice.message, "content") and choice.message.content:
        message_content = choice.message.content
    elif (
        hasattr(choice.message, "reasoning_content")
        and choice.message.reasoning_content
    ):
        message_content = choice.message.reasoning_content

    return {
        "text": message_content,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "finish_reason": str(finish_reason),
        "avg_logprobs": avg_logprobs,
        "model_version": response.proto.model,
        "response_id": getattr(response, "id", ""),
        "system_fingerprint": getattr(response, "system_fingerprint", "") or "",
        "service_tier": "",  # Grok doesn't have service tiers
        "completion_tokens_details": {},  # Not available for Grok
        "prompt_tokens_details": {},  # Not available for Grok
    }


def _grok_image_analysis_adapter(
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
    max_output_tokens = kwargs.get("max_output_tokens")

    # Load images
    from mcp_handley_lab.llm.common import resolve_image_data

    image_urls = []
    for image_path in images:
        image_bytes = resolve_image_data(image_path)
        encoded = base64.b64encode(image_bytes).decode()

        from mcp_handley_lab.llm.common import determine_mime_type

        if image_path.startswith("data:image"):
            image_urls.append(image_path)
        else:
            mime_type = determine_mime_type(Path(image_path))
            image_urls.append(f"data:{mime_type};base64,{encoded}")

    # Enhance prompt based on focus
    if focus != "general":
        prompt = f"Focus on {focus} aspects. {prompt}"

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
    content_parts = [chat.text(prompt)]
    for image_url in image_urls:
        content_parts.append(chat.image(image_url))

    # Add current message with images
    messages.append(chat.user(*content_parts))

    # Get model configuration
    model_config = _get_model_config(model)
    default_tokens = model_config["output_tokens"]

    # Build request parameters
    request_params = {
        "model": model,
        "messages": messages,
        "temperature": 1.0,
    }

    # Add max tokens
    if max_output_tokens > 0:
        request_params["max_tokens"] = max_output_tokens
    else:
        request_params["max_tokens"] = default_tokens

    # Make API call using XAI SDK's two-step process
    chat_session = client.chat.create(**request_params)
    response = chat_session.sample()

    if not response or not response.proto or not response.proto.choices:
        raise RuntimeError("No response generated")

    # Extract response data from proto
    choice = response.proto.choices[0]

    # Get message content - Grok uses reasoning_content for its responses
    message_content = ""
    if hasattr(choice.message, "content") and choice.message.content:
        message_content = choice.message.content
    elif (
        hasattr(choice.message, "reasoning_content")
        and choice.message.reasoning_content
    ):
        message_content = choice.message.reasoning_content

    return {
        "text": message_content,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "finish_reason": str(choice.finish_reason),
        "avg_logprobs": 0.0,  # Image analysis doesn't use logprobs
        "model_version": response.proto.model,
        "response_id": getattr(response, "id", ""),
        "system_fingerprint": getattr(response, "system_fingerprint", "") or "",
        "service_tier": "",  # Grok doesn't have service tiers
        "completion_tokens_details": {},  # Not available for vision models
        "prompt_tokens_details": {},  # Not available for vision models
    }


@mcp.tool(
    description="Sends a prompt to a Grok model for a conversational response. Use `agent_name` for persistent memory and `files` to provide context. Response is saved to the required `output_file` ('-' for stdout)."
)
def ask(
    prompt: str,
    output_file: str = "-",
    agent_name: str = "session",
    model: str = DEFAULT_MODEL,
    temperature: float = 1.0,
    max_output_tokens: int = 0,
    files: list[str] = [],
) -> LLMResult:
    """Ask Grok a question with optional persistent memory."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="grok",
        generation_func=_grok_generation_adapter,
        mcp_instance=mcp,
        temperature=temperature,
        files=files,
        max_output_tokens=max_output_tokens,
    )


@mcp.tool(
    description="Analyzes images using a Grok vision model (grok-2-vision-1212). Provide a prompt and a list of image file paths. Use `agent_name` for persistent memory. Response is saved to `output_file` ('-' for stdout)."
)
def analyze_image(
    prompt: str,
    output_file: str = "-",
    files: list[str] = [],
    focus: str = "general",
    model: str = "grok-2-vision-1212",
    agent_name: str = "session",
    max_output_tokens: int = 0,
) -> LLMResult:
    """Analyze images with Grok vision model."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="grok",
        generation_func=_grok_image_analysis_adapter,
        mcp_instance=mcp,
        images=files,
        focus=focus,
        max_output_tokens=max_output_tokens,
    )


def _grok_image_generation_adapter(prompt: str, model: str, **kwargs) -> dict:
    """Grok-specific image generation function with comprehensive metadata extraction."""
    # Use xai-sdk's image.sample method
    response = client.image.sample(prompt=prompt, model=model, image_format="base64")

    if not response or not response.images:
        raise RuntimeError("No image generated")

    # Get the first (and typically only) image
    image = response.images[0]

    # Decode base64 image data
    import base64

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


@mcp.tool(
    description="Generates an image using Grok's image generation model (grok-2-image-1212) from a text prompt. Returns the file path of the saved image."
)
def generate_image(
    prompt: str,
    model: str = "grok-2-image-1212",
    agent_name: str = "session",
) -> ImageGenerationResult:
    """Generate images with Grok."""
    return process_image_generation(
        prompt=prompt,
        agent_name=agent_name,
        model=model,
        provider="grok",
        generation_func=_grok_image_generation_adapter,
        mcp_instance=mcp,
    )


@mcp.tool(
    description="Retrieves a catalog of available Grok models with their capabilities, pricing, and context windows. Use this to select the best model for a task."
)
def list_models() -> ModelListing:
    """List available Grok models with detailed information."""
    # Get models from API for availability checking
    language_models = client.models.list_language_models()
    api_model_ids = {m.name for m in language_models}

    # Also get image generation models
    image_models = client.models.list_image_generation_models()
    api_model_ids.update({m.name for m in image_models})

    # Use structured model listing
    return get_structured_model_listing("grok", api_model_ids)


@mcp.tool(
    description="Checks Grok Tool server status and API connectivity. Returns version info, model availability, and a list of available functions."
)
def server_info() -> ServerInfo:
    """Get server status and Grok configuration."""
    # Test API key by listing models
    language_models = client.models.list_language_models()
    available_models = [m.name for m in language_models if "grok" in m.name.lower()]

    # Also count image models
    image_models = client.models.list_image_generation_models()
    available_models.extend([m.name for m in image_models if "grok" in m.name.lower()])

    # Get agent count
    agent_count = len(memory_manager.list_agents())

    return ServerInfo(
        name="Grok Tool",
        version="1.0.0",
        status="active",
        capabilities=[
            "ask - Chat with Grok models (persistent memory enabled by default)",
            "analyze_image - Image analysis with vision models (persistent memory enabled by default)",
            "generate_image - Generate images with Grok",
            "list_models - List available Grok models with detailed information",
            "server_info - Get server status",
        ],
        dependencies={
            "api_key": "configured",
            "available_models": f"{len(available_models)} models",
            "active_agents": str(agent_count),
            "memory_storage": str(memory_manager.storage_dir),
            "vision_support": "true",
            "image_generation": "true",
        },
    )
