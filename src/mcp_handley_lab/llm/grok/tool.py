"""Grok LLM tool for AI interactions via MCP."""

import threading
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from xai_sdk import Client

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    build_server_info,
    load_provider_models,
    resolve_files_for_llm,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.model_loader import (
    get_structured_model_listing,
)
from mcp_handley_lab.llm.shared import process_image_generation, process_llm_request
from mcp_handley_lab.shared.models import (
    ImageGenerationResult,
    LLMResult,
    ModelListing,
    ServerInfo,
)

mcp = FastMCP("Grok Tool")

# Lazy initialization of Grok client
_client: Client | None = None
_client_lock = threading.Lock()


def _get_client() -> Client:
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
MODEL_CONFIGS, DEFAULT_MODEL, _get_model_config = load_provider_models("grok")


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
    chat_session = _get_client().chat.create(**request_params)
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

    # Use standardized image processing
    from mcp_handley_lab.llm.common import resolve_images_for_multimodal_prompt

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
    chat_session = _get_client().chat.create(**request_params)
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
    description="Delegates a user query to external xAI Grok service on behalf of the human user. Returns Grok's verbatim response to assist the user. Use `agent_name` for separate conversation thread with Grok. For code reviews, use code2prompt first."
)
def ask(
    prompt: str = Field(
        ..., description="The user's question to delegate to external Grok AI service."
    ),
    output_file: str = Field(
        default="-",
        description="File path to save Grok's response. Use '-' for standard output.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with Grok AI service (distinct from your conversation with the user).",
    ),
    model: str = Field(
        default=DEFAULT_MODEL,
        description="The Grok model to use for the request (e.g., 'grok-1').",
    ),
    temperature: float = Field(
        default=1.0,
        description="Controls randomness. Higher values (e.g., 1.0) are more creative, lower values are more deterministic.",
    ),
    max_output_tokens: int = Field(
        default=0,
        description="The maximum number of tokens to generate. 0 means use the model's default maximum.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of file paths to provide as text context to the model.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external Grok AI service. Remembered for this conversation thread.",
    ),
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
        system_prompt=system_prompt,
    )


@mcp.tool(
    description="Delegates image analysis to external Grok vision AI service on behalf of the user. Returns Grok's verbatim visual analysis to assist the user."
)
def analyze_image(
    prompt: str = Field(
        ...,
        description="The user's question about the images to delegate to external Grok vision AI service.",
    ),
    output_file: str = Field(
        default="-",
        description="File path to save Grok's visual analysis. Use '-' for standard output.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of image file paths or base64 encoded strings to be analyzed.",
    ),
    focus: str = Field(
        default="general",
        description="The area of focus for the analysis (e.g., 'ocr', 'objects'). This enhances the prompt to guide the model.",
    ),
    model: str = Field(
        default="grok-2-vision-1212",
        description="The Grok vision model to use. Must be a vision-capable model.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with Grok AI service (distinct from your conversation with the user).",
    ),
    max_output_tokens: int = Field(
        default=0,
        description="The maximum number of tokens to generate in the response. 0 means use the model's default maximum.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external Grok AI service. Remembered for this conversation thread.",
    ),
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
        system_prompt=system_prompt,
    )


def _grok_image_generation_adapter(prompt: str, model: str, **kwargs) -> dict:
    """Grok-specific image generation function with comprehensive metadata extraction."""
    # Use xai-sdk's image.sample method
    response = _get_client().image.sample(
        prompt=prompt, model=model, image_format="base64"
    )

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
    description="Delegates image generation to external Grok AI service on behalf of the user. Returns the generated image file path to assist the user."
)
def generate_image(
    prompt: str = Field(
        ...,
        description="The user's detailed description to send to external Grok AI service for image generation.",
    ),
    model: str = Field(
        default="grok-2-image-1212",
        description="The Grok model to use for image generation.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with image generation AI service (for prompt history tracking).",
    ),
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
    language_models = _get_client().models.list_language_models()
    api_model_ids = {m.name for m in language_models}

    # Also get image generation models
    image_models = _get_client().models.list_image_generation_models()
    api_model_ids.update({m.name for m in image_models})

    # Use structured model listing
    return get_structured_model_listing("grok", api_model_ids)


@mcp.tool(
    description="Checks Grok Tool server status and API connectivity. Returns version info, model availability, and a list of available functions."
)
def server_info() -> ServerInfo:
    """Get server status and Grok configuration without making a network call."""
    # Get model names from the local YAML config instead of the API
    available_models = list(MODEL_CONFIGS.keys())

    return build_server_info(
        provider_name="Grok",
        available_models=available_models,
        memory_manager=memory_manager,
        vision_support=True,
        image_generation=True,
    )


@mcp.tool(description="Tests the connection to the Grok API by listing models.")
def test_connection() -> str:
    """Tests the connection to the Grok API."""
    try:
        language_models = _get_client().models.list_language_models()
        image_models = _get_client().models.list_image_generation_models()
        total_models = len(language_models) + len(image_models)
        return f"✅ Connection successful. Found {total_models} models."
    except Exception as e:
        return f"❌ Connection failed: {e}"
