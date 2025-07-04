"""Claude LLM tool for AI interactions via MCP."""
import base64
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic
from mcp.server.fastmcp import FastMCP

from ...common.config import settings
from ...common.memory import memory_manager
from ..common import (
    determine_mime_type,
    is_text_file,
    resolve_image_data,
)
from ..model_loader import (
    build_model_configs_dict,
    format_model_listing,
    load_model_config,
)
from ..shared import process_llm_request

mcp = FastMCP("Claude Tool")

# Configure Claude client - fail fast if API key is invalid/missing
client = AsyncAnthropic(api_key=settings.anthropic_api_key)

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


async def _resolve_files(files: list[str | dict[str, str]] | None) -> str:
    """Resolve file inputs to text content for Claude.

    Claude has a large context window (200K tokens), so we can include most files directly.
    Returns a string with all file contents concatenated.
    """
    if not files:
        return ""

    file_contents = []

    for file_item in files:
        if isinstance(file_item, str):
            # Direct content string
            file_contents.append(file_item)
        elif isinstance(file_item, dict):
            if "content" in file_item:
                # Direct content from dict
                file_contents.append(file_item["content"])
            elif "path" in file_item:
                # File path - read content
                file_path = Path(file_item["path"])
                if not file_path.exists():
                    raise FileNotFoundError(f"File not found: {file_path}")

                file_size = file_path.stat().st_size

                # Claude can handle large files, but let's be reasonable (20MB limit)
                if file_size > 20 * 1024 * 1024:
                    raise ValueError(f"File too large: {file_path} ({file_size} bytes)")

                if is_text_file(file_path):
                    # Text file - read directly
                    content = file_path.read_text(encoding="utf-8")
                    file_contents.append(f"[File: {file_path.name}]\n{content}")
                else:
                    # Binary file - describe only (Claude doesn't need base64 for non-image files)
                    mime_type = determine_mime_type(file_path)
                    file_contents.append(
                        f"[Binary file: {file_path.name}, {mime_type}, {file_size} bytes - content not included]"
                    )

    return "\n\n".join(file_contents)


def _resolve_images_to_content_blocks(
    image_data: str | None = None,
    images: list[str | dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Resolve image inputs to Claude content blocks."""
    image_blocks = []

    # Handle single image_data parameter
    if image_data:
        image_bytes = resolve_image_data(image_data)
        # Determine media type
        if isinstance(image_data, str) and image_data.startswith("data:image"):
            media_type = image_data.split(";")[0].split(":")[1]
        else:
            # File path - use determine_mime_type for consistent MIME detection
            media_type = determine_mime_type(Path(str(image_data)))
            # Default to JPEG for non-image types
            if not media_type.startswith("image/"):
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


async def _claude_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str | None,
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
        min(max_output_tokens, max_output)
        if max_output_tokens is not None
        else max_output
    )

    # Resolve file contents
    file_content = await _resolve_files(files)

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
    }

    # Add system instruction if provided
    if system_instruction:
        request_params["system"] = system_instruction

    # Make API call
    response = await client.messages.create(**request_params)

    if not response.content or not response.content[0].text:
        raise RuntimeError("No response text generated")

    return {
        "text": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


async def _claude_image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str | None,
    **kwargs,
) -> dict[str, Any]:
    """Claude-specific image analysis function for the shared processor."""
    # Extract image analysis specific parameters
    image_data = kwargs.get("image_data")
    images = kwargs.get("images")
    focus = kwargs.get("focus", "general")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Enhance prompt based on focus
    if focus != "general":
        prompt = f"Focus on {focus} aspects. {prompt}"

    # Get model configuration
    model_config = _get_model_config(model)
    max_output = model_config["output_tokens"]
    output_tokens = (
        min(max_output_tokens, max_output)
        if max_output_tokens is not None
        else max_output
    )

    # Resolve images to content blocks
    image_blocks = _resolve_images_to_content_blocks(image_data, images)

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
    }

    # Add system instruction if provided
    if system_instruction:
        request_params["system"] = system_instruction

    # Make API call
    response = await client.messages.create(**request_params)

    if not response.content or not response.content[0].text:
        raise RuntimeError("No response text generated")

    return {
        "text": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


@mcp.tool(
    description="""Asks a question to a Claude model with optional file context and persistent memory.

**Memory Behavior**: Conversations are automatically stored in persistent memory by default. Each MCP session gets its own conversation thread. Use a named `agent_name` for cross-session persistence, or `agent_name=False` to disable memory entirely.

CRITICAL: The `output_file` parameter is REQUIRED. Use:
- A file path to save the response for future processing (recommended for large responses)
- '-' to output directly to stdout (use sparingly, as large responses may exceed MCP message limits)

File Input Formats:
- {"path": "/path/to/file"} - Reads file from filesystem
- {"content": "text content"} - Uses provided text directly
- "direct string" - Treats string as literal content

Key Parameters:
- `model`: "sonnet" (balanced, default), "opus" (best reasoning), "haiku" (fast), or full model name
- `temperature`: Creativity level 0.0 (deterministic) to 1.0 (creative, default: 0.7)
- `max_output_tokens`: Override model's default output token limit
- `agent_name`: Store conversation in named agent (string), use session memory (None/default), or disable memory (False)

Token Limits by Model:
- claude-3-opus: 4,096 tokens (default), 200k context
- claude-3-5-sonnet: 8,192 tokens (default), 200k context
- claude-3-5-haiku: 8,192 tokens (default), 200k context
- Use max_output_tokens parameter to override defaults

Model Selection Guide:
- sonnet: Best balance of speed and capability (default)
- opus: Best for complex reasoning and analysis
- haiku: Fastest and most cost-effective

Error Handling:
- Raises RuntimeError for Claude API errors (authentication, quota, network)
- Raises ValueError for invalid file paths or malformed requests
- Large responses automatically saved to avoid MCP message size limits

Examples:
```python
# Basic question with session memory (default)
ask(
    prompt="Explain this code",
    output_file="/tmp/explanation.md",
    files=[{"path": "/path/to/code.py"}]
)

# Continue conversation in same session
ask(
    prompt="Now show me how to optimize it",
    output_file="/tmp/optimization.md"
)

# Named agent for cross-session persistence
ask(
    prompt="Review this codebase",
    output_file="/tmp/review.md",
    agent_name="code_reviewer",
    model="opus"
)

# Disable memory for one-off queries
ask(
    prompt="What's the weather like?",
    output_file="/tmp/weather.md",
    agent_name=False,
    model="haiku"
)
```"""
)
@require_client
async def ask(
    prompt: str,
    output_file: str,
    agent_name: str | bool | None = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    files: list[str | dict[str, str]] | None = None,
    max_output_tokens: int | None = None,
) -> str:
    """Ask Claude a question with optional persistent memory."""
    # Resolve model alias to full model name for consistent pricing
    resolved_model = _resolve_model_alias(model)
    return await process_llm_request(
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
    description="""Analyzes images using Claude's advanced vision capabilities.

**Memory Behavior**: Image analysis conversations are automatically stored in persistent memory by default. Each MCP session gets its own conversation thread. Use a named `agent_name` for cross-session persistence, or `agent_name=False` to disable memory entirely.

CRITICAL: The `output_file` parameter is REQUIRED. Use:
- A file path to save the analysis for future processing (recommended)
- '-' to output directly to stdout (use sparingly for large analyses)

Image Input Formats:
- {"path": "/path/to/image.jpg"} - Read from filesystem (preferred)
- {"data": "base64_encoded_data"} - Base64 encoded image data
- "data:image/jpeg;base64,/9j/4AAQ..." - Data URL format
- "/path/to/image.jpg" - Direct path string (legacy, use dict format instead)

Analysis Focus Options:
- "general" (default) - Overall image description
- "objects" - Focus on object detection and identification
- "colors" - Analyze color palette and composition
- "composition" - Focus on artistic composition and layout
- "text" - Extract and analyze text within images
- "technical" - Focus on technical aspects, quality, metadata
- "code" - Analyze screenshots of code or diagrams

Model Options:
- "claude-3-5-sonnet-20240620" (default) - Best for detailed analysis
- "claude-3-opus-20240229" - Best for complex visual reasoning
- "claude-3-5-haiku-20241022" - Faster response for simple descriptions

Key Parameters:
- `agent_name`: Store conversation in named agent (string), use session memory (None/default), or disable memory (False)

Error Handling:
- Raises ValueError for missing or invalid image inputs
- Raises RuntimeError for Claude API errors (quota, authentication, unsupported formats)
- Supports common formats: JPEG, PNG, GIF, WebP
- Large images may be automatically resized by the API

Examples:
```python
# Analyze image with session memory (default)
analyze_image(
    prompt="Describe what you see in this image",
    output_file="/tmp/analysis.md",
    image_data="/path/to/photo.jpg",
    focus="general"
)

# Continue analysis in same session
analyze_image(
    prompt="Now focus on the text in the image",
    output_file="/tmp/text_analysis.md",
    focus="text"
)

# Named agent for cross-session persistence
analyze_image(
    prompt="Analyze this architectural diagram",
    output_file="/tmp/architecture.md",
    image_data={"path": "/path/to/diagram.png"},
    agent_name="architect_reviewer",
    focus="technical"
)

# One-off analysis without memory
analyze_image(
    prompt="What's in this random image?",
    output_file="/tmp/random.md",
    image_data="data:image/png;base64,iVBORw0KGgoAAAA...",
    agent_name=False
)
```"""
)
@require_client
async def analyze_image(
    prompt: str,
    output_file: str,
    image_data: str | None = None,
    images: list[str | dict[str, str]] | None = None,
    focus: str = "general",
    model: str = "claude-3-5-sonnet-20240620",
    agent_name: str | bool | None = None,
    max_output_tokens: int | None = None,
) -> str:
    """Analyze images with Claude vision model."""
    return await process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="claude",
        generation_func=_claude_image_analysis_adapter,
        mcp_instance=mcp,
        image_data=image_data,
        images=images,
        focus=focus,
        max_output_tokens=max_output_tokens,
    )


@mcp.tool(
    description="""Retrieves a comprehensive catalog of all available Claude models to aid in model discovery and selection.

**Purpose & Benefits:**
This tool helps users:
- Discover all models offered by Anthropic's Claude family
- Compare models based on cost, performance, context windows, and capabilities
- Identify the most suitable Claude model for specific tasks or budget constraints
- Understand model generations and performance tiers (Opus, Sonnet, Haiku)

**Returns:**
Formatted listing with detailed information including:
- Model IDs and descriptions
- Context windows (all Claude models: 200K tokens)
- Pricing per 1M tokens (input/output)
- Capabilities (text generation, vision, coding, analysis, etc.)
- Model tiers (Opus: most capable, Sonnet: balanced, Haiku: fastest)
- Cache pricing options for repeated content

**Examples:**
```python
# Discover all available models
list_models()

# Use cases this enables:
# - "Which Claude model is fastest?" → claude-3-5-haiku ($0.80/M input)
# - "What's the most capable model?" → claude-opus-4 ($15.00/M input)
# - "Which models support vision?" → All Claude models support image analysis
# - "Show me balanced cost/performance" → claude-sonnet-4, claude-sonnet-3.7
# - "What's the latest Claude generation?" → Claude 4 series
# - "Which models have cache pricing?" → All models (5-min and 1-hour tiers)
```"""
)
async def list_models() -> str:
    """List available Claude models with detailed information."""
    # Use YAML-based model listing
    return format_model_listing("claude")


@mcp.tool(
    description="""Checks the status of the Claude Tool server and API connectivity.

Use this to verify that the tool is operational before making other requests.

**Input/Output:**
- **Input**: None.
- **Output**: A string containing the server status, API connection status, and a list of available tools.

**Error Handling:**
- Raises `RuntimeError` if the Claude API is not configured correctly.

**Examples:**
```python
# Check the server status.
server_info()
```"""
)
@require_client
async def server_info() -> str:
    """Get server status and Claude configuration."""
    # Test API by making a simple request
    await client.messages.create(
        model="claude-3-5-haiku-20241022",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10,
    )

    # Get agent count
    agent_count = len(memory_manager.list_agents())

    available_models = list(MODEL_CONFIGS.keys())

    return f"""Claude Tool Server Status
==========================
Status: Connected and ready
API Key: Configured ✓
Available Models: {len(available_models)} models
- {', '.join(available_models[:3])}{'...' if len(available_models) > 3 else ''}

Model Features:
- Context Window: 200,000 tokens (all models)
- Vision Support: ✓ (all models)
- Image Generation: ✗ (not available)

Agent Management:
- Active Agents: {agent_count}
- Memory Storage: {memory_manager.storage_dir}

Available tools:
- ask: Chat with Claude models (persistent memory by default, agent_name=False to disable)
- analyze_image: Image analysis with vision models (persistent memory by default, agent_name=False to disable)
- server_info: Get server status

Note: Claude does not support image generation. Use Gemini or OpenAI for image generation tasks."""
