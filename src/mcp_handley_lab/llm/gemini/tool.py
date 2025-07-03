"""Gemini LLM tool for AI interactions via MCP."""
import asyncio
import base64
import io
import os
import tempfile
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

from ...common.config import settings
from ...common.memory import memory_manager
from ...common.pricing import calculate_cost, format_usage
from ..common import (
    get_gemini_safe_mime_type,
    get_session_id,
    is_text_file,
    resolve_image_data,
)
from ..model_loader import (
    build_model_configs_dict,
    format_model_listing,
    load_model_config,
)
from ..shared import create_client_decorator, process_llm_request

mcp = FastMCP("Gemini Tool")

# Configure Gemini client
client = None
initialization_error = None

try:
    # Client initialization - let SDK use default API version
    client = google_genai.Client(api_key=settings.gemini_api_key)
except Exception as e:
    client = None
    initialization_error = str(e)

# Generate session ID once at module load time
_SESSION_ID = f"_session_{os.getpid()}_{int(time.time())}"


# Create client decorator with dynamic error message
def _get_error_message():
    return f"Gemini client not initialized: {initialization_error or 'API key not configured'}"


require_client = create_client_decorator(
    lambda: client is not None, _get_error_message()
)


def _convert_history_to_gemini_format(
    history: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Convert generic history to Gemini's expected format."""
    gemini_history = []
    for message in history:
        # Map "assistant" role to "model" for Gemini
        role = "model" if message["role"] == "assistant" else message["role"]
        gemini_history.append({"role": role, "parts": [{"text": message["content"]}]})
    return gemini_history


# Load model configurations from YAML
MODEL_CONFIGS = build_model_configs_dict("gemini")

# Load default model from YAML
_config = load_model_config("gemini")
DEFAULT_MODEL = _config["default_model"]


def _get_session_id() -> str:
    """Get the persistent session ID for this MCP server process."""
    return get_session_id(mcp)


def _get_model_config(model: str) -> dict[str, int]:
    """Get token limits for a specific model."""
    return MODEL_CONFIGS.get(model, MODEL_CONFIGS[DEFAULT_MODEL])


async def _resolve_files(
    files: list[str | dict[str, str]] | None,
) -> list[Part]:
    """Resolve file inputs to structured content parts for google-genai API.

    Uses inlineData for files <20MB and Files API for larger files.
    Returns list of Part objects that can be included in contents.
    """
    if not files:
        return []

    parts = []
    for file_item in files:
        if isinstance(file_item, str):
            # Direct content string - create text part
            parts.append(Part(text=file_item))
        elif isinstance(file_item, dict):
            if "content" in file_item:
                # Direct content - create text part
                parts.append(Part(text=file_item["content"]))
            elif "path" in file_item:
                # File path - determine optimal handling based on size
                file_path = Path(file_item["path"])
                file_size = file_path.stat().st_size

                if file_size > 20 * 1024 * 1024:  # 20MB threshold
                    # Large file - use Files API
                    def _sync_upload_file(path=file_path):
                        return client.files.upload(
                            file=str(path),
                            mime_type=get_gemini_safe_mime_type(path),
                        )

                    loop = asyncio.get_running_loop()
                    uploaded_file = await loop.run_in_executor(None, _sync_upload_file)
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
    image_data: str | None = None,
    images: list[str | dict[str, str]] | None = None,
) -> list[Image.Image]:
    """Resolve image inputs to PIL Image objects."""
    image_list = []

    # Handle single image_data parameter
    if image_data:
        try:
            image_bytes = resolve_image_data(image_data)
            image_list.append(Image.open(io.BytesIO(image_bytes)))
        except Exception as e:
            raise ValueError(f"Failed to load image: {e}") from e

    # Handle images array
    if images:
        for image_item in images:
            try:
                image_bytes = resolve_image_data(image_item)
                image_list.append(Image.open(io.BytesIO(image_bytes)))
            except Exception as e:
                raise ValueError(f"Failed to load image: {e}") from e

    return image_list


async def _gemini_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str | None,
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
    file_parts = await _resolve_files(files)

    # Get model configuration and token limits
    model_config = _get_model_config(model)
    max_output = model_config["output_tokens"]
    output_tokens = (
        min(max_output_tokens, max_output)
        if max_output_tokens is not None
        else max_output
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
    loop = asyncio.get_running_loop()

    # Convert history to Gemini format
    gemini_history = _convert_history_to_gemini_format(history)

    # Generate content (cancellation handled by process_llm_request wrapper)
    if gemini_history:
        # Continue existing conversation
        user_parts = [Part(text=prompt)] + file_parts
        contents = gemini_history + [
            {"role": "user", "parts": [part.to_json_dict() for part in user_parts]}
        ]
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=model, contents=contents, config=config
            ),
        )
    else:
        # New conversation
        if file_parts:
            content_parts = [Part(text=prompt)] + file_parts
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=model, contents=content_parts, config=config
                ),
            )
        else:
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=model, contents=prompt, config=config
                ),
            )

    if not response.text:
        raise RuntimeError("No response text generated")

    return {
        "text": response.text,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count,
    }


async def _gemini_image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str | None,
    **kwargs,
) -> dict[str, Any]:
    """Gemini-specific image analysis function for the shared processor."""
    # Extract image analysis specific parameters
    image_data = kwargs.get("image_data")
    images = kwargs.get("images")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Load images
    image_list = _resolve_images(image_data, images)

    # Get model configuration
    model_config = _get_model_config(model)
    max_output = model_config["output_tokens"]
    output_tokens = (
        min(max_output_tokens, max_output)
        if max_output_tokens is not None
        else max_output
    )

    # Prepare content with images
    content = [prompt] + image_list

    # Prepare the config
    config_params = {"max_output_tokens": output_tokens, "temperature": 0.7}
    if system_instruction:
        config_params["system_instruction"] = system_instruction

    config = GenerateContentConfig(**config_params)

    # Convert history to Gemini format
    _convert_history_to_gemini_format(history)

    # Generate response - image analysis starts fresh conversation (cancellation handled by process_llm_request wrapper)
    def _sync_generate_content_image():
        return client.models.generate_content(
            model=model, contents=content, config=config
        )

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, _sync_generate_content_image)

    if not response.text:
        raise RuntimeError("No response text generated")

    return {
        "text": response.text,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count,
    }


@mcp.tool(
    description="""Start or continue a conversation with a Google Gemini model. This tool sends your prompt, along with any provided files, directly to the Gemini model and returns its response.

**Agent Recommendation**: For best results, consider creating a specialized agent with `create_agent()` before starting conversations. This allows you to define the agent's expertise and personality for more focused interactions.

**Memory Behavior**: Conversations with Gemini are automatically stored in persistent memory by default. Each MCP session gets its own conversation thread. Use a named `agent_name` for cross-session persistence, or `agent_name=False` to disable memory entirely.

CRITICAL: The `output_file` parameter is REQUIRED. Use:
- A file path to save the response for future processing (recommended for large responses)
- '-' to output directly to stdout (use sparingly, as large responses may exceed MCP message limits)

File Input Formats:
- {"path": "/path/to/file"} - Reads file from filesystem
- {"content": "text content"} - Uses provided text directly
- "direct string" - Treats string as literal content

Key Parameters:
- `model`: "gemini-2.5-flash" (fast, default), "gemini-2.5-pro" (advanced reasoning), or full model name
- `grounding`: Enable Google Search integration for current/recent information and factual accuracy (default: False, may increase response time). **Recommended for**: current date/time, recent events, real-time data, breaking news, or any information that may have changed recently
- `agent_name`: Store conversation in named agent (string), use session memory (None/default), or disable memory (False)
- `temperature`: Creativity level 0.0 (deterministic) to 1.0 (creative, default: 0.7)

Error Handling:
- Raises RuntimeError for Gemini API errors (authentication, quota, network)
- Raises ValueError for invalid file paths or malformed requests
- Large responses automatically saved to avoid MCP message size limits

Examples:
```python
# Quick question with stdout (default, immediate response)
ask(prompt="What is 2+2?")

# Continue conversation in same session
ask(prompt="Now multiply that by 3")

# Longer response saved to file
ask(
    prompt="Explain this code in detail",
    output_file="/tmp/explanation.md",
    files=[{"path": "/path/to/code.py"}]
)

# Named agent for cross-session persistence
ask(
    prompt="Review this codebase",
    output_file="/tmp/review.md",
    agent_name="code_reviewer",
    model="gemini-2.5-pro"
)

# One-off query with grounding
ask(
    prompt="What is the weather like?",
    agent_name=False,
    grounding=True
)
```"""
)
@require_client
async def ask(
    prompt: str,
    output_file: str | None = "-",
    agent_name: str | bool | None = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    grounding: bool = False,
    files: list[str | dict[str, str]] | None = None,
    max_output_tokens: int | None = None,
) -> str:
    """Ask Gemini a question with optional persistent memory.

    Args:
        prompt: The question or instruction to send to Gemini
        output_file: Output destination - use '-' for immediate stdout (default, faster for short queries) or file path for longer responses
        agent_name: Named agent for persistent memory (None=session, False=disabled)
        model: Gemini model name (gemini-2.5-flash for speed, gemini-2.5-pro for complex reasoning)
        temperature: Creativity level 0.0-1.0 (default: 0.7)
        grounding: Enable Google Search integration for current information
        files: List of files to include as context
        max_output_tokens: Override model's default output token limit

    Token Limits by Model:
        - gemini-2.5-flash/pro: 65,536 tokens (default)
        - gemini-1.5-flash/pro: 8,192 tokens (default)
        - Use max_output_tokens parameter to override defaults

    Example with custom token limit:
        ask(prompt="Write a long essay", model="gemini-2.5-flash", max_output_tokens=32000)
    """
    return await process_llm_request(
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
    description="""Engage Gemini's vision capabilities to analyze and discuss images. This tool sends your prompt and images to a Gemini vision model, allowing you to have a conversation about the visual content.

**Agent Recommendation**: Consider creating a specialized agent with `create_agent()` for image analysis tasks. This enables focused conversations about visual content with appropriate expertise.

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

Model Options:
- "gemini-2.5-pro" (default) - Best for detailed analysis and complex reasoning
- "gemini-2.5-flash" - Faster response, good for simple image descriptions

Key Parameters:
- `agent_name`: Store conversation in named agent (string), use session memory (None/default), or disable memory (False)

Error Handling:
- Raises ValueError for missing or invalid image inputs
- Raises RuntimeError for Gemini API errors (quota, authentication, unsupported formats)
- Supports common formats: JPEG, PNG, GIF, WebP
- Large images may be automatically resized by the API

Examples:
```python
# Quick image analysis with stdout (default)
analyze_image(
    prompt="What's in this image?",
    image_data="/path/to/photo.jpg"
)

# Continue analysis in same session
analyze_image(
    prompt="Now focus on the text in the image",
    focus="text"
)

# Detailed analysis saved to file
analyze_image(
    prompt="Analyze this architectural diagram in detail",
    output_file="/tmp/architecture.md",
    image_data={"path": "/path/to/diagram.png"},
    agent_name="architect_reviewer",
    focus="technical"
)

# One-off analysis without memory
analyze_image(
    prompt="What's in this random image?",
    image_data="data:image/png;base64,iVBORw0KGgoAAAA...",
    agent_name=False
)
```"""
)
@require_client
async def analyze_image(
    prompt: str,
    output_file: str | None = "-",
    image_data: str | None = None,
    images: list[str | dict[str, str]] | None = None,
    focus: str = "general",
    model: str = DEFAULT_MODEL,
    agent_name: str | bool | None = None,
    max_output_tokens: int | None = None,
) -> str:
    """Analyze images with Gemini vision model."""
    return await process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="gemini",
        generation_func=_gemini_image_analysis_adapter,
        mcp_instance=mcp,
        image_data=image_data,
        images=images,
        focus=focus,
        max_output_tokens=max_output_tokens,
    )


@mcp.tool(
    description="""Instruct Google's Imagen 3 model to generate a high-quality image from your text prompt. You provide the creative direction, and the AI generates the visual content.

**Agent Recommendation**: Consider creating a specialized agent with `create_agent()` for image generation projects. This enables iterative creative work and maintains context for related image requests.

**Memory Behavior**: Image generation requests are automatically stored in persistent memory by default. Each MCP session gets its own conversation thread. Use a named `agent_name` for cross-session persistence, or `agent_name=False` to disable memory entirely.

Creates images from text descriptions with advanced artistic capabilities. Generated images are saved as PNG files to a temporary location.

Prompt Guidelines:
- Be descriptive and specific for best results
- Include style, mood, lighting, and composition details
- Mention aspect ratio preferences if needed
- Avoid requesting copyrighted characters or inappropriate content

Key Parameters:
- `agent_name`: Store conversation in named agent (string), use session memory (None/default), or disable memory (False)

Examples:
```python
# Generate with session memory (default)
generate_image(
    prompt="A serene mountain landscape at sunset, with golden light reflecting on a crystal-clear lake, painted in impressionist style"
)

# Continue with variations in same session
generate_image(
    prompt="Now make it more abstract and colorful"
)

# Named agent for cross-session persistence
generate_image(
    prompt="Professional headshot of a confident software engineer",
    agent_name="portrait_artist"
)

# One-off generation without memory
generate_image(
    prompt="Random abstract art",
    agent_name=False
)
```

Note: Generated images are automatically saved to temporary files. Use the returned file path for further processing.

Error Handling:
- Raises RuntimeError for Imagen API errors (quota exceeded, content policy violations)
- Raises ValueError for prompts that violate content policies
- Generated images are PNG format, saved to system temp directory"""
)
@require_client
async def generate_image(
    prompt: str, model: str = "imagen-3", agent_name: str | bool | None = None
) -> str:
    """Generate images with Google's Imagen 3 model."""
    # Input validation
    if not prompt or not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")
    if agent_name is not None and agent_name is not False and not agent_name.strip():
        raise ValueError("Agent name cannot be empty when provided")

    # Map model names to actual model IDs
    model_mapping = {
        "imagen-3": "imagen-3.0-generate-002",
        "image": "imagen-3.0-generate-002",
        "image-flash": "imagen-3.0-generate-002",
    }

    actual_model = model_mapping.get(model, "imagen-3.0-generate-002")

    try:
        # Generate image
        def _sync_generate_images():
            return client.models.generate_images(
                model=actual_model,
                prompt=prompt,
                config=GenerateImagesConfig(number_of_images=1, aspect_ratio="1:1"),
            )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, _sync_generate_images)

        if not response.generated_images:
            raise RuntimeError("No images were generated")

        # Save the generated image
        generated_image = response.generated_images[0]
        if not generated_image.image or not generated_image.image.image_bytes:
            raise RuntimeError("Generated image has no data")

        # Save to temporary file
        import uuid

        file_id = str(uuid.uuid4())[:8]
        filename = f"gemini_generated_{file_id}.png"
        filepath = Path(tempfile.gettempdir()) / filename

        filepath.write_bytes(generated_image.image.image_bytes)

        # Calculate usage and cost (estimate)
        input_tokens = len(prompt.split()) * 2  # Rough estimate
        output_tokens = 1  # Image generation
        cost = calculate_cost(actual_model, input_tokens, output_tokens, "gemini")

        # Handle agent memory (only if enabled)
        use_memory = agent_name is not False

        if use_memory:
            # Use session-specific agent if no agent_name provided
            if not agent_name:
                agent_name = _get_session_id()

            agent = memory_manager.get_agent(agent_name)
            if not agent:
                agent = memory_manager.create_agent(agent_name)

            memory_manager.add_message(
                agent_name, "user", f"Generate image: {prompt}", input_tokens, cost / 2
            )
            memory_manager.add_message(
                agent_name,
                "assistant",
                f"Generated image saved to {filepath}",
                output_tokens,
                cost / 2,
            )

        # Format response
        file_size = len(generated_image.image.image_bytes)
        usage_info = format_usage(input_tokens, output_tokens, cost)

        return f"✅ **Image Generated Successfully**\n\n📁 **File:** `{filepath}`\n📏 **Size:** {file_size:,} bytes\n\n{usage_info}"

    except Exception as e:
        raise RuntimeError(f"Error generating image with Imagen: {e}") from e


@mcp.tool(
    description="""Retrieves a comprehensive catalog of all available Gemini models to aid in model discovery and selection.

**Purpose & Benefits:**
This tool helps users:
- Discover all models offered by Google's Gemini family and related models (Imagen, Veo)
- Compare models based on cost, performance, context windows, and capabilities
- Identify the most suitable Gemini model for specific tasks or budget constraints
- Understand model generations and recommended use cases

**Returns:**
Formatted listing with detailed information including:
- Model IDs and descriptions
- Context windows and token limits
- Pricing per 1M tokens (tiered, modality-based, or per-image/second)
- Capabilities (text generation, image understanding, multimodal, etc.)
- Recommended use cases and performance characteristics
- API availability status

**Examples:**
```python
# Discover all available models
list_models()

# Use cases this enables:
# - "Which models support image input?" → gemini-2.5-pro, gemini-2.5-flash, etc.
# - "What's the cheapest text model?" → gemini-1.5-flash-8b ($0.0375/M input)
# - "Which model has the largest context?" → gemini-2.5-pro (2M tokens)
# - "Show me image generation models" → imagen-4, imagen-4-ultra, imagen-3
# - "What models support video generation?" → veo-2 ($0.35/second)
```"""
)
@require_client
async def list_models() -> str:
    """List available Gemini models with detailed information."""
    try:
        # Get models from API
        def _sync_list_models():
            return client.models.list()

        loop = asyncio.get_running_loop()
        models_response = await loop.run_in_executor(None, _sync_list_models)
        api_model_names = {model.name.split("/")[-1] for model in models_response}

        # Use YAML-based model listing
        return format_model_listing("gemini", api_model_names)

    except Exception as e:
        raise RuntimeError(f"Failed to list Gemini models: {e}") from e


@mcp.tool(
    description="""Checks the status of the Gemini Tool server and API connectivity.

Use this to verify that the tool is operational before making other requests.

**Input/Output:**
- **Input**: None.
- **Output**: A string containing the server status, API connection status, and a list of available tools.

**Error Handling:**
- Raises `RuntimeError` if the Gemini API is not configured correctly.

**Examples:**
```python
# Check the server status.
server_info()
```"""
)
@require_client
async def server_info() -> str:
    """Get server status and Gemini configuration."""
    try:
        # Test API by listing models
        def _sync_list_models():
            return client.models.list()

        loop = asyncio.get_running_loop()
        models_response = await loop.run_in_executor(None, _sync_list_models)
        available_models = []
        for model in models_response:
            if "gemini" in model.name:
                available_models.append(model.name.split("/")[-1])

        # Get agent count
        agent_count = len(memory_manager.list_agents())

        return f"""Gemini Tool Server Status
==========================
Status: Connected and ready
API Key: Configured ✓
Available Models: {len(available_models)} models
- {', '.join(available_models[:5])}{'...' if len(available_models) > 5 else ''}

Agent Management:
- Active Agents: {agent_count}
- Memory Storage: {memory_manager.storage_dir}

Available tools:
- ask: Chat with Gemini models (persistent memory by default, agent_name=False to disable)
- analyze_image: Image analysis with vision models (persistent memory by default, agent_name=False to disable)
- generate_image: Generate images with Imagen 3 (persistent memory by default, agent_name=False to disable)
- create_agent: Create persistent conversation agents
- list_agents: List all agents and stats
- agent_stats: Get detailed agent statistics
- get_response: Retrieve messages from agent conversation history
- clear_agent: Clear agent conversation history
- delete_agent: Permanently delete agents
- server_info: Get server status"""

    except Exception as e:
        raise RuntimeError(f"Gemini API configuration error: {e}") from e
