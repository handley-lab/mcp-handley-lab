"""OpenAI LLM tool for AI interactions via MCP."""
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from openai import OpenAI

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

mcp = FastMCP("OpenAI Tool")

# Configure OpenAI client
client = OpenAI(api_key=settings.openai_api_key)

# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL, _get_model_config = load_provider_models("openai")


def _openai_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """OpenAI-specific text generation function for the shared processor."""
    # Extract OpenAI-specific parameters
    temperature = kwargs.get("temperature", 1.0)
    files = kwargs.get("files")
    max_output_tokens = kwargs.get("max_output_tokens")
    enable_logprobs = kwargs["enable_logprobs"]
    top_logprobs = kwargs["top_logprobs"]

    # Build messages
    messages = []

    # Add system instruction if provided
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    # Add history (already in OpenAI format)
    messages.extend(history)

    # Resolve files
    inline_content = resolve_files_for_llm(files)

    # Add user message with any inline content
    user_content = prompt
    if inline_content:
        user_content += "\n\n" + "\n\n".join(inline_content)
    messages.append({"role": "user", "content": user_content})

    # Get model configuration
    model_config = _get_model_config(model)
    param_name = model_config["param"]
    default_tokens = model_config["output_tokens"]

    # Build request parameters
    request_params = {
        "model": model,
        "messages": messages,
    }

    # Add logprobs if requested
    if enable_logprobs:
        request_params["logprobs"] = True
        if top_logprobs > 0:
            request_params["top_logprobs"] = top_logprobs

    request_params["temperature"] = temperature

    # Add max tokens with correct parameter name
    if max_output_tokens > 0:
        request_params[param_name] = max_output_tokens
    else:
        request_params[param_name] = default_tokens

    # Make API call
    response = client.chat.completions.create(**request_params)

    if not response.choices or not response.choices[0].message.content:
        raise RuntimeError("No response generated")

    # Extract additional OpenAI metadata
    choice = response.choices[0]
    finish_reason = choice.finish_reason

    # Extract logprobs for confidence assessment
    avg_logprobs = 0.0
    if choice.logprobs and choice.logprobs.content:
        logprobs = [token.logprob for token in choice.logprobs.content]
        avg_logprobs = sum(logprobs) / len(logprobs)

    # Extract token details
    completion_tokens_details = {}
    if response.usage.completion_tokens_details:
        details = response.usage.completion_tokens_details
        completion_tokens_details = {
            "reasoning_tokens": details.reasoning_tokens,
            "accepted_prediction_tokens": details.accepted_prediction_tokens,
            "rejected_prediction_tokens": details.rejected_prediction_tokens,
            "audio_tokens": details.audio_tokens,
        }

    prompt_tokens_details = {}
    if response.usage.prompt_tokens_details:
        details = response.usage.prompt_tokens_details
        prompt_tokens_details = {
            "cached_tokens": details.cached_tokens,
            "audio_tokens": details.audio_tokens,
        }

    return {
        "text": response.choices[0].message.content,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "finish_reason": finish_reason,
        "avg_logprobs": avg_logprobs,
        "model_version": response.model,
        "response_id": response.id,
        "system_fingerprint": response.system_fingerprint or "",
        "service_tier": response.service_tier or "",
        "completion_tokens_details": completion_tokens_details,
        "prompt_tokens_details": prompt_tokens_details,
    }


def _openai_image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """OpenAI-specific image analysis function for the shared processor."""
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

    # Build message content with images in OpenAI format
    content = [{"type": "text", "text": prompt_text}]
    for image_block in image_blocks:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_block['mime_type']};base64,{image_block['data']}"
                },
            }
        )

    # Build messages
    messages = []

    # Add system instruction if provided
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    # Add history (already in OpenAI format)
    messages.extend(history)

    # Add current message with images
    messages.append({"role": "user", "content": content})

    # Get model configuration
    model_config = _get_model_config(model)
    param_name = model_config["param"]
    default_tokens = model_config["output_tokens"]

    # Build request parameters
    request_params = {
        "model": model,
        "messages": messages,
    }

    # Only add temperature for models that support it (reasoning models don't)
    if not model.startswith(("o1", "o3", "o4")):
        request_params["temperature"] = 1.0

    # Add max tokens with correct parameter name
    if max_output_tokens > 0:
        request_params[param_name] = max_output_tokens
    else:
        request_params[param_name] = default_tokens

    # Make API call
    response = client.chat.completions.create(**request_params)

    if not response.choices or not response.choices[0].message.content:
        raise RuntimeError("No response generated")

    return {
        "text": response.choices[0].message.content,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "finish_reason": response.choices[0].finish_reason,
        "avg_logprobs": 0.0,  # Image analysis doesn't use logprobs
        "model_version": response.model,
        "response_id": response.id,
        "system_fingerprint": response.system_fingerprint or "",
        "service_tier": response.service_tier or "",
        "completion_tokens_details": {},  # Not available for vision models
        "prompt_tokens_details": {},  # Not available for vision models
    }


@mcp.tool(
    description="Sends a prompt to an OpenAI GPT model for a conversational response. Use `agent_name` for persistent memory and `files` to provide context. Response is saved to the required `output_file` ('-' for stdout)."
)
def ask(
    prompt: str,
    output_file: str = "-",
    agent_name: str = "session",
    model: str = DEFAULT_MODEL,
    temperature: float = 1.0,
    max_output_tokens: int = 0,
    files: list[str] = [],
    enable_logprobs: bool = False,
    top_logprobs: int = 0,
) -> LLMResult:
    """Ask OpenAI a question with optional persistent memory."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="openai",
        generation_func=_openai_generation_adapter,
        mcp_instance=mcp,
        temperature=temperature,
        files=files,
        max_output_tokens=max_output_tokens,
        enable_logprobs=enable_logprobs,
        top_logprobs=top_logprobs,
    )


@mcp.tool(
    description="Analyzes images using an OpenAI vision model (GPT-4o series). Provide a prompt and a list of image file paths. Use `agent_name` for persistent memory. Response is saved to `output_file` ('-' for stdout)."
)
def analyze_image(
    prompt: str,
    output_file: str = "-",
    files: list[str] = [],
    focus: str = "general",
    model: str = "gpt-4o",
    agent_name: str = "session",
    max_output_tokens: int = 0,
) -> LLMResult:
    """Analyze images with OpenAI vision model."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="openai",
        generation_func=_openai_image_analysis_adapter,
        mcp_instance=mcp,
        images=files,
        focus=focus,
        max_output_tokens=max_output_tokens,
    )


def _openai_image_generation_adapter(prompt: str, model: str, **kwargs) -> dict:
    """OpenAI-specific image generation function with comprehensive metadata extraction."""
    # Extract parameters for metadata
    size = kwargs.get("size", "1024x1024")
    quality = kwargs.get("quality", "standard")

    params = {"model": model, "prompt": prompt, "size": size, "n": 1}
    if model == "dall-e-3":
        params["quality"] = quality

    response = client.images.generate(**params)
    image = response.data[0]

    # Download the image
    with httpx.Client() as http_client:
        image_response = http_client.get(image.url)
        image_response.raise_for_status()
        image_bytes = image_response.content

    # Extract comprehensive metadata
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
        "requested_format": "png",  # OpenAI always returns PNG
        "mime_type": "image/png",
        "original_url": image.url,
        "openai_metadata": openai_metadata,
    }


@mcp.tool(
    description="Generates an image using OpenAI's DALL-E models from a text prompt. Supports different quality and size options. Returns the file path of the saved image."
)
def generate_image(
    prompt: str,
    model: str = "dall-e-3",
    quality: str = "standard",
    size: str = "1024x1024",
    agent_name: str = "session",
) -> ImageGenerationResult:
    """Generate images with DALL-E."""
    return process_image_generation(
        prompt=prompt,
        agent_name=agent_name,
        model=model,
        provider="openai",
        generation_func=_openai_image_generation_adapter,
        mcp_instance=mcp,
        quality=quality,
        size=size,
    )


@mcp.tool(
    description="Retrieves a catalog of available OpenAI models with their capabilities, pricing, and context windows. Use this to select the best model for a task."
)
def list_models() -> ModelListing:
    """List available OpenAI models with detailed information."""
    # Get models from API for availability checking
    api_models = client.models.list()
    api_model_ids = {m.id for m in api_models.data}

    # Use structured model listing
    return get_structured_model_listing("openai", api_model_ids)


@mcp.tool(
    description="Checks OpenAI Tool server status and API connectivity. Returns version info, model availability, and a list of available functions."
)
def server_info() -> ServerInfo:
    """Get server status and OpenAI configuration."""
    # Test API key by listing models
    models = client.models.list()
    available_models = [
        m.id for m in models.data if m.id.startswith(("gpt", "dall-e", "text-", "o1"))
    ]

    return build_server_info(
        provider_name="OpenAI",
        available_models=available_models,
        memory_manager=memory_manager,
        vision_support=True,
        image_generation=True,
    )
