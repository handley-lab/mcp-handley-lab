"""Claude LLM tool for AI interactions via MCP."""
import base64
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from mcp.server.fastmcp import FastMCP

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    determine_mime_type,
    resolve_files_for_llm,
    resolve_image_data,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.model_loader import (
    build_model_configs_dict,
    format_model_listing,
    load_model_config,
)
from mcp_handley_lab.llm.shared import process_llm_request
from mcp_handley_lab.shared.models import LLMResult, ServerInfo

mcp = FastMCP("Claude Tool")

# Configure Claude client - fail fast if API key is invalid/missing
client = Anthropic(api_key=settings.anthropic_api_key)

# Load model configurations from YAML
MODEL_CONFIGS = build_model_configs_dict("claude")

# Load default model from YAML
_config = load_model_config("claude")
DEFAULT_MODEL = _config["default_model"]


# Client initialization decorator is no longer needed with fail-fast approach
# If we reach this point, the client is guaranteed to be initialized
def require_client(func):
    """Identity decorator - no longer needed with fail-fast approach."""
    return func


def _resolve_model_alias(model: str) -> str:
    """Resolve model aliases to full model names."""
    aliases = {
        "sonnet": "claude-3-5-sonnet-20241022",
        "opus": "claude-3-opus-20240229",
        "haiku": "claude-3-5-haiku-20241022",
    }
    return aliases.get(model, model)


def _get_model_config(model: str) -> dict[str, int]:
    """Get token limits for a specific model."""
    resolved_model = _resolve_model_alias(model)
    return MODEL_CONFIGS.get(resolved_model, MODEL_CONFIGS[DEFAULT_MODEL])


def _convert_history_to_claude_format(
    history: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Convert generic history to Claude's expected format.

    Claude requires alternating user/assistant messages. This function validates
    and fixes the sequence if needed.
    """
    if not history:
        return []

    claude_history = []
    last_role = None

    for message in history:
        role = message["role"]
        content = message["content"]

        # Skip system messages (handled separately in Claude)
        if role == "system":
            continue

        # If we have consecutive messages from the same role, merge them
        if role == last_role and claude_history:
            # Merge with previous message
            claude_history[-1]["content"] += "\n\n" + content
        else:
            # Add as new message
            claude_history.append({"role": role, "content": content})
            last_role = role

    # Ensure history starts with user message (Claude requirement)
    if claude_history and claude_history[0]["role"] != "user":
        # Prepend a placeholder user message if needed
        claude_history.insert(
            0, {"role": "user", "content": "[Previous conversation context]"}
        )

    return claude_history


def _resolve_files(files: list[str]) -> LLMResult:
    """Resolve file inputs to text content for Claude.

    Claude has a large context window (200K tokens), so we can include most files directly.
    Returns a string with all file contents concatenated.
    """
    if not files:
        return ""

    # Use shared file resolution with larger max size for Claude's big context
    file_contents = resolve_files_for_llm(files, max_file_size=20 * 1024 * 1024)  # 20MB
    return "\n\n".join(file_contents)


def _resolve_images_to_content_blocks(
    images: list[str] = [],
) -> list[dict[str, Any]]:
    """Resolve image inputs to Claude content blocks."""
    image_blocks = []

    # Handle images array
    if images:
        for image_item in images:
            image_bytes = resolve_image_data(image_item)

            # Determine media type
            if isinstance(image_item, str):
                if image_item.startswith("data:image"):
                    media_type = image_item.split(";")[0].split(":")[1]
                else:
                    # File path - use determine_mime_type for consistency
                    media_type = determine_mime_type(Path(image_item))
                    if not media_type.startswith("image/"):
                        media_type = "image/jpeg"
            elif isinstance(image_item, dict) and "path" in image_item:
                media_type = determine_mime_type(Path(image_item["path"]))
                if not media_type.startswith("image/"):
                    media_type = "image/jpeg"
            else:
                media_type = "image/jpeg"

            encoded_data = base64.b64encode(image_bytes).decode("utf-8")
            image_blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": encoded_data,
                    },
                }
            )

    return image_blocks


def _claude_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Claude-specific text generation function for the shared processor."""
    # Extract Claude-specific parameters
    temperature = kwargs.get("temperature", 0.7)
    files = kwargs.get("files")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Get model configuration
    model_config = _get_model_config(model)
    max_output = model_config["output_tokens"]
    output_tokens = (
        min(max_output_tokens, max_output) if max_output_tokens > 0 else max_output
    )

    # Resolve file contents
    file_content = _resolve_files(files)

    # Build user content
    user_content = prompt
    if file_content:
        user_content += "\n\n" + file_content

    # Convert history to Claude format
    claude_history = _convert_history_to_claude_format(history)

    # Add current user message
    claude_history.append({"role": "user", "content": user_content})

    # Resolve model alias and prepare request parameters
    resolved_model = _resolve_model_alias(model)
    request_params = {
        "model": resolved_model,
        "messages": claude_history,
        "max_tokens": output_tokens,
        "temperature": temperature,
        "timeout": 599,
    }

    # Add system instruction if provided
    if system_instruction:
        request_params["system"] = system_instruction

    # Make API call
    response = client.messages.create(**request_params)

    if not response.content or not response.content[0].text:
        raise RuntimeError("No response text generated")

    return {
        "text": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


def _claude_image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Claude-specific image analysis function for the shared processor."""
    # Extract image analysis specific parameters
    images = kwargs.get("images", [])
    focus = kwargs.get("focus", "general")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Enhance prompt based on focus
    if focus != "general":
        prompt = f"Focus on {focus} aspects. {prompt}"

    # Get model configuration
    model_config = _get_model_config(model)
    max_output = model_config["output_tokens"]
    output_tokens = (
        min(max_output_tokens, max_output) if max_output_tokens > 0 else max_output
    )

    # Resolve images to content blocks
    image_blocks = _resolve_images_to_content_blocks(images)

    # Build content with text and images
    content_blocks = [{"type": "text", "text": prompt}] + image_blocks

    # Convert history to Claude format
    claude_history = _convert_history_to_claude_format(history)

    # Add current user message with images
    claude_history.append({"role": "user", "content": content_blocks})

    # Resolve model alias and prepare request parameters
    resolved_model = _resolve_model_alias(model)
    request_params = {
        "model": resolved_model,
        "messages": claude_history,
        "max_tokens": output_tokens,
        "temperature": 0.7,
        "timeout": 599,
    }

    # Add system instruction if provided
    if system_instruction:
        request_params["system"] = system_instruction

    # Make API call
    response = client.messages.create(**request_params)

    if not response.content or not response.content[0].text:
        raise RuntimeError("No response text generated")

    return {
        "text": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


@mcp.tool(
    description="Sends a prompt to a Claude model for a conversational response. Use `agent_name` for persistent memory and `files` to provide context. Response is saved to `output_file` ('-' for stdout)."
)
@require_client
def ask(
    prompt: str,
    output_file: str = "-",
    agent_name: str = "session",
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    files: list[str] = [],
    max_output_tokens: int = 0,
) -> LLMResult:
    """Ask Claude a question with optional persistent memory."""
    # Resolve model alias to full model name for consistent pricing
    resolved_model = _resolve_model_alias(model)
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=resolved_model,
        provider="claude",
        generation_func=_claude_generation_adapter,
        mcp_instance=mcp,
        temperature=temperature,
        files=files,
        max_output_tokens=max_output_tokens,
    )


@mcp.tool(
    description="Analyzes images using Claude's vision capabilities. Provide a prompt and a list of image file paths. Use `agent_name` for persistent memory. Response is saved to `output_file` ('-' for stdout)."
)
@require_client
def analyze_image(
    prompt: str,
    output_file: str = "-",
    files: list[str] = [],
    focus: str = "general",
    model: str = "claude-3-5-sonnet-20240620",
    agent_name: str = "session",
    max_output_tokens: int = 0,
) -> LLMResult:
    """Analyze images with Claude vision model."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="claude",
        generation_func=_claude_image_analysis_adapter,
        mcp_instance=mcp,
        images=files,
        focus=focus,
        max_output_tokens=max_output_tokens,
    )


@mcp.tool(
    description="Retrieves a comprehensive catalog of all available Claude models with pricing, capabilities, and performance information. Helps compare models and select the most suitable one for specific tasks or budget constraints."
)
def list_models() -> LLMResult:
    """List available Claude models with detailed information."""
    # Use YAML-based model listing
    return format_model_listing("claude")


@mcp.tool(
    description="Checks the status of the Claude Tool server and API connectivity. Returns connection status and list of available tools. Use this to verify the tool is operational before making other requests."
)
@require_client
def server_info() -> ServerInfo:
    """Get server status and Claude configuration."""
    # Test API by making a simple request
    client.messages.create(
        model="claude-3-5-haiku-20241022",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10,
    )

    # Get agent count
    agent_count = len(memory_manager.list_agents())

    available_models = list(MODEL_CONFIGS.keys())

    return ServerInfo(
        name="Claude Tool",
        version="1.0.0",
        status="active",
        capabilities=[
            "ask - Chat with Claude models (persistent memory enabled by default)",
            "analyze_image - Image analysis with vision models (persistent memory enabled by default)",
            "list_models - List available Claude models with detailed information",
            "server_info - Get server status",
        ],
        dependencies={
            "api_key": "configured",
            "available_models": f"{len(available_models)} models",
            "active_agents": str(agent_count),
            "memory_storage": str(memory_manager.storage_dir),
            "vision_support": "true",
            "image_generation": "false",
        },
    )
