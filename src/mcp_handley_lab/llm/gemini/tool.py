"""Gemini LLM tool for AI interactions via MCP."""
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

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.common.memory import memory_manager
from mcp_handley_lab.common.pricing import calculate_cost, format_usage
from mcp_handley_lab.llm.common import (
    get_gemini_safe_mime_type,
    get_session_id,
    is_text_file,
    resolve_image_data,
)
from mcp_handley_lab.llm.model_loader import (
    build_model_configs_dict,
    format_model_listing,
    load_model_config,
)
from mcp_handley_lab.llm.shared import process_llm_request

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


def _resolve_files(
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
    image_data: str | None = None,
    images: list[str | dict[str, str]] | None = None,
) -> list[Image.Image]:
    """Resolve image inputs to PIL Image objects."""
    image_list = []

    # Handle single image_data parameter
    if image_data:
        image_bytes = resolve_image_data(image_data)
        image_list.append(Image.open(io.BytesIO(image_bytes)))

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
    file_parts = _resolve_files(files)

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

    # Convert history to Gemini format
    gemini_history = _convert_history_to_gemini_format(history)

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

    return {
        "text": response.text,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count,
    }


def _gemini_image_analysis_adapter(
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
    }


@mcp.tool(
    description="Sends your prompt and files to a Google Gemini model for conversational response. Use `agent_name` for persistent memory or `agent_name=False` to disable it. Set `grounding=True` for current information via Google Search. Response saved to required `output_file` ('-' for stdout). Key models: 'gemini-2.5-flash' (fast), 'gemini-2.5-pro' (advanced)."
)
@require_client
def ask(
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
    description="Analyzes images using a Gemini vision model. Requires a `prompt` and image data (via `image_data` or `images` parameters). Supports persistent memory via `agent_name`. Use the `focus` parameter ('objects', 'text', etc.) to guide the analysis. Returns the analysis to the required `output_file` ('-' for stdout)."
)
@require_client
def analyze_image(
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
    return process_llm_request(
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
    description="Generates high-quality images using Google's Imagen 3 model. Provide creative prompts and the AI generates visual content. Supports persistent memory via `agent_name` parameter. Generated images are saved as PNG files to temporary locations."
)
@require_client
def generate_image(
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

    # Generate image
    response = client.models.generate_images(
        model=actual_model,
        prompt=prompt,
        config=GenerateImagesConfig(number_of_images=1, aspect_ratio="1:1"),
    )

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
    cost = calculate_cost(model, input_tokens, output_tokens, "gemini")

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


@mcp.tool(
    description="Lists all available Gemini models with pricing, capabilities, and context windows. Helps compare models for cost, performance, and features to select the best model for specific tasks."
)
@require_client
def list_models() -> str:
    """List available Gemini models with detailed information."""

    # Get models from API
    models_response = client.models.list()
    api_model_names = {model.name.split("/")[-1] for model in models_response}

    # Use YAML-based model listing
    return format_model_listing("gemini", api_model_names)


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
def server_info() -> str:
    """Get server status and Gemini configuration."""

    # Test API by listing models
    models_response = client.models.list()
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
