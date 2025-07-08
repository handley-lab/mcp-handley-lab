"""OpenAI LLM tool for AI interactions via MCP."""
import base64
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from openai import OpenAI

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    resolve_files_for_llm,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.model_loader import (
    build_model_configs_dict,
    format_model_listing,
    load_model_config,
)
from mcp_handley_lab.llm.shared import process_image_generation, process_llm_request
from mcp_handley_lab.shared.models import ServerInfo

mcp = FastMCP("OpenAI Tool")

# Configure OpenAI client
client = OpenAI(api_key=settings.openai_api_key)

# Load model configurations from YAML
MODEL_CONFIGS = build_model_configs_dict("openai")

# Load default model from YAML
_config = load_model_config("openai")
DEFAULT_MODEL = _config["default_model"]


def _get_model_config(model: str) -> dict[str, Any]:
    """Get token limits and parameter name for a specific model."""
    return MODEL_CONFIGS.get(model, MODEL_CONFIGS[DEFAULT_MODEL])


def _openai_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """OpenAI-specific text generation function for the shared processor."""
    # Extract OpenAI-specific parameters
    temperature = kwargs.get("temperature", 0.7)
    files = kwargs.get("files")
    max_output_tokens = kwargs.get("max_output_tokens")

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

    # Only add temperature for models that support it (reasoning models don't)
    if not model.startswith(("o1", "o3", "o4")):
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

    return {
        "text": response.choices[0].message.content,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
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

    # Build message content with images
    content = [{"type": "text", "text": prompt}]
    for image_url in image_urls:
        content.append({"type": "image_url", "image_url": {"url": image_url}})

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
        request_params["temperature"] = 0.7

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
    }


@mcp.tool(
    description="Sends a prompt to an OpenAI GPT model for a conversational response. Use `agent_name` for persistent memory and `files` to provide context. Response is saved to the required `output_file` ('-' for stdout)."
)
def ask(
    prompt: str,
    output_file: str = "-",
    agent_name: str = "session",
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_output_tokens: int = 0,
    files: list[str] = [],
) -> str:
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
) -> str:
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
    """OpenAI-specific image generation function."""
    params = {"model": model, "prompt": prompt, "size": kwargs.get("size"), "n": 1}
    if model == "dall-e-3":
        params["quality"] = kwargs.get("quality")

    response = client.images.generate(**params)
    image_url = response.data[0].url

    # Download the image
    with httpx.Client() as http_client:
        image_response = http_client.get(image_url)
        image_response.raise_for_status()
        return {"image_bytes": image_response.content}


@mcp.tool(
    description="Generates an image using OpenAI's DALL-E models from a text prompt. Supports different quality and size options. Returns the file path of the saved image."
)
def generate_image(
    prompt: str,
    model: str = "dall-e-3",
    quality: str = "standard",
    size: str = "1024x1024",
    agent_name: str = "session",
) -> str:
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
def list_models() -> str:
    """List available OpenAI models with detailed information."""
    # Get models from API for availability checking
    api_models = client.models.list()
    api_model_ids = {m.id for m in api_models.data}

    # Use YAML-based model listing
    return format_model_listing("openai", api_model_ids)


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

    # Get agent count
    agent_count = len(memory_manager.list_agents())

    return ServerInfo(
        name="OpenAI Tool",
        version="1.0.0",
        status="active",
        capabilities=[
            "ask - Chat with GPT models (persistent memory enabled by default)",
            "analyze_image - Image analysis with vision models (persistent memory enabled by default)",
            "generate_image - Generate images with DALL-E",
            "list_models - List available OpenAI models with detailed information",
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
