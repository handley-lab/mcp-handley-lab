"""OpenAI LLM tool for AI interactions via MCP."""
import base64
import tempfile
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from openai import OpenAI

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.common.memory import memory_manager
from mcp_handley_lab.common.pricing import calculate_cost
from mcp_handley_lab.llm.common import (
    resolve_files_for_llm,
)
from mcp_handley_lab.llm.model_loader import (
    build_model_configs_dict,
    format_model_listing,
    load_model_config,
)
from mcp_handley_lab.llm.shared import process_llm_request

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
    system_instruction: str | None,
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
    system_instruction: str | None,
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
    description="""Start or continue a conversation with an OpenAI GPT model. This tool sends your prompt and any provided files directly to the selected GPT model and returns its response.

**Agent Recommendation**: For best results, consider creating a specialized agent with `create_agent()` before starting conversations. This allows you to define the agent's expertise and personality for more focused interactions.

**Memory Behavior**: Conversations with OpenAI are automatically stored in persistent memory by default. Each MCP session gets its own conversation thread. Use a named `agent_name` for cross-session persistence, or `agent_name=False` to disable memory entirely.

**Output Handling**: The `output_file` parameter is REQUIRED. Use:
- A file path to save the response for future processing (recommended for large responses)
- '-' to output directly to stdout (use sparingly, as large responses may exceed MCP message limits)

**File Input Formats**:
- File paths as strings: `["/path/to/file1.py", "/path/to/file2.txt"]`
- All files are read from filesystem and included inline

**Key Parameters**:
- `model`: "o3-mini" (default, fast reasoning), "o3" (best reasoning), "gpt-4o" (multimodal), "gpt-4o-mini" (fast multimodal)
- `temperature`: Creativity level 0.0 (deterministic) to 2.0 (very creative, default: 0.7). Note: Not supported by reasoning models (o1, o3 series)
- `max_output_tokens`: Override model's default output token limit
- `agent_name`: Store conversation in named agent (string), use session memory (None/default), or disable memory (False)

**Token Limits by Model**:
- o3/o3-mini: 100,000 tokens (default)
- o1-mini: 65,536 tokens (default)
- o1-preview: 32,768 tokens (default)
- gpt-4o/gpt-4o-mini: 4,096 tokens (default)
- Use max_output_tokens parameter to override defaults

**Model Selection Guide**:
- o3-mini: Fast reasoning for most tasks, cost-effective (200k context, default)
- o3: Best reasoning for complex problems (200k context)
- gpt-4o: Best for multimodal tasks, file analysis, vision (128k context)
- gpt-4o-mini: Fast multimodal, cost-effective for simple vision tasks (128k context)

**Error Handling**:
- Raises RuntimeError for OpenAI API errors (authentication, quota, rate limits)
- Raises ValueError for invalid file paths or unsupported content
- Agent memory automatically handles conversation context limits
- Large responses automatically saved to avoid MCP message size limits

**Examples**:
```python
# Basic question with file context
ask(
    prompt="Explain this code and suggest improvements",
    output_file="/tmp/analysis.md",
    files=[{"path": "/path/to/code.py"}],
    model="o3-mini"
)

# Persistent agent conversation
ask(
    prompt="Continue reviewing the codebase",
    output_file="/tmp/review.md",
    agent_name="code_reviewer",
    model="o3-mini",
    temperature=0.3
)

# Complex reasoning task
ask(
    prompt="Solve this algorithmic problem step by step",
    output_file="/tmp/solution.md",
    model="o1-preview",
    files=[{"content": "Problem description here"}]
)

# Multiple file analysis
ask(
    prompt="Compare these implementations",
    output_file="/tmp/comparison.md",
    files=[
        {"path": "/path/to/impl1.py"},
        {"path": "/path/to/impl2.py"},
        {"content": "Additional context"}
    ],
    max_output_tokens=2000
)
```"""
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
    description="""Engage an OpenAI vision model in a conversation about one or more images. This tool sends your prompt and images to the model, allowing you to ask questions, get descriptions, or perform detailed multimodal analysis.

**Agent Recommendation**: For best results, consider creating a specialized agent with `create_agent()` for image analysis tasks. This enables focused conversations about visual content with appropriate expertise.

**Memory Behavior**: Image analysis conversations are automatically stored in persistent memory by default. Each MCP session gets its own conversation thread. Use a named `agent_name` for cross-session persistence, or `agent_name=False` to disable memory entirely.

**Output Handling**: The `output_file` parameter is REQUIRED. Use:
- A file path to save the analysis for future processing (recommended)
- '-' to output directly to stdout (use sparingly for large analyses)

**Image Input Formats**:
- File paths: `["/path/to/image1.jpg", "/path/to/image2.png"]`
- Data URLs: `["data:image/jpeg;base64,/9j/4AAQ..."]`
- Mixed: `["/path/to/local.jpg", "data:image/png;base64,iVBORw..."]`

**Analysis Focus Options**:
- "general" (default) - Overall image description
- "objects" - Focus on object detection and identification
- "colors" - Analyze color palette and composition
- "composition" - Focus on artistic composition and layout
- "text" - Extract and analyze text within images (OCR)
- "technical" - Focus on technical aspects, quality, metadata
- "medical" - Medical image analysis (disclaimer: not for diagnosis)
- "code" - Analyze screenshots of code or diagrams

**Model Options**:
- "gpt-4o" (default) - Best vision capabilities, handles complex visual reasoning
- "gpt-4o-mini" - Faster, cost-effective vision analysis for simple tasks

**Key Parameters**:
- `agent_name`: Store conversation in named agent (string), use session memory (None/default), or disable memory (False)
- `max_output_tokens`: Override model's default output token limit

**Error Handling**:
- Raises ValueError for missing images or unsupported formats
- Raises RuntimeError for OpenAI API errors (quota, rate limits, content policy)
- Supports: JPEG, PNG, GIF, WebP (max 20MB per image)
- Multiple images increase token usage significantly

**Examples**:
```python
# Analyze single image
analyze_image(
    prompt="Describe what you see in this screenshot",
    output_file="/tmp/analysis.md",
    image_data="/path/to/screenshot.png",
    focus="general"
)

# Multiple images comparison
analyze_image(
    prompt="Compare these two UI designs and suggest improvements",
    output_file="/tmp/comparison.md",
    images=[
        {"path": "/path/to/design1.png"},
        {"path": "/path/to/design2.png"}
    ],
    focus="composition"
)

# Extract text from image
analyze_image(
    prompt="Extract and transcribe all text from this document",
    output_file="/tmp/extracted_text.md",
    image_data={"path": "/path/to/document.jpg"},
    focus="text",
    model="o3-mini"
)

# Code analysis from screenshot
analyze_image(
    prompt="Review this code for potential bugs and improvements",
    output_file="/tmp/code_review.md",
    image_data="data:image/png;base64,iVBORw0KGgoAAAA...",
    focus="code",
    agent_name="code_reviewer"
)
```"""
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


@mcp.tool(
    description="""Generate images using OpenAI's DALL-E models. You provide the detailed description, and the AI creates the image.

**Agent Recommendation**: For best results, consider creating a specialized agent with `create_agent()` for image generation projects. This enables iterative creative work and maintains context for related image requests.

**Memory Behavior**: Image generation conversations are automatically stored in persistent memory by default. Each MCP session gets its own conversation thread. Use a named `agent_name` for cross-session persistence, or `agent_name=False` to disable memory entirely.

**Output Format**: Generated images are automatically downloaded and saved to temporary files. The file path is returned for further processing.

**Model Options**:
- "dall-e-3" (default) - Latest model with best quality and prompt adherence
- "dall-e-2" - Previous generation, faster and more cost-effective

**Quality Settings**:
- "standard" (default) - Good quality, faster generation
- "hd" - Higher resolution and detail (DALL-E 3 only)

**Size Options**:
- DALL-E 3: "1024x1024" (default), "1024x1792" (portrait), "1792x1024" (landscape)
- DALL-E 2: "256x256", "512x512", "1024x1024" (default)

**Prompt Guidelines**:
- Be descriptive and specific for best results
- Include style, mood, lighting, and composition details
- DALL-E 3 follows prompts more precisely than DALL-E 2
- Avoid requesting copyrighted characters or inappropriate content

**Key Parameters**:
- `agent_name`: Store conversation in named agent (string), use session memory (None/default), or disable memory (False)
- `model`: DALL-E model to use (default: "dall-e-3")
- `quality`: Quality setting for DALL-E 3 (default: "standard")
- `size`: Image dimensions (default: "1024x1024")

**Error Handling**:
- Raises RuntimeError for DALL-E API errors (quota exceeded, content policy violations)
- Raises ValueError for prompts violating OpenAI's usage policies
- Image download may fail due to network issues; temporary URLs expire quickly
- DALL-E 3 may revise prompts for safety compliance

**Examples**:
```python
# High-quality artistic image
generate_image(
    prompt="A serene mountain landscape at sunset with golden light reflecting on a crystal-clear lake, painted in impressionist style with visible brushstrokes",
    model="dall-e-3",
    quality="hd",
    size="1792x1024"
)

# Technical diagram
generate_image(
    prompt="Clean, minimalist flowchart showing a software deployment pipeline with rounded rectangles and arrow connections, professional blue and white colors",
    model="dall-e-3",
    size="1024x1792"
)

# Portrait with specific style
generate_image(
    prompt="Professional headshot of a confident software engineer in modern office setting, natural lighting, shallow depth of field, photorealistic style",
    model="dall-e-3",
    quality="hd",
    agent_name="design_assistant"
)

# Cost-effective generation
generate_image(
    prompt="Simple icon design for a mobile app, minimalist style, single color",
    model="dall-e-2",
    size="512x512"
)
```"""
)
def generate_image(
    prompt: str,
    model: str = "dall-e-3",
    quality: str = "standard",
    size: str = "1024x1024",
    agent_name: str = "session",
) -> str:
    """Generate images with DALL-E."""
    # Input validation
    if not prompt or not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")

    # Make API call (quality only supported for DALL-E 3)
    params = {"model": model, "prompt": prompt, "size": size, "n": 1}
    if model == "dall-e-3":
        params["quality"] = quality

    response = client.images.generate(**params)

    # Get the image URL
    image_url = response.data[0].url

    # Download and save the image using httpx
    with httpx.Client() as http_client:
        image_response = http_client.get(image_url)
        image_response.raise_for_status()

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(image_response.content)
            saved_path = f.name

    # Calculate cost (DALL-E pricing is per image)
    cost = calculate_cost(model, 1, 0, "openai")  # 1 image

    # Handle agent memory with string-based pattern
    use_memory = agent_name != ""  # Empty string = no memory
    if use_memory:
        from mcp_handley_lab.llm.common import get_session_id

        if agent_name == "session":
            actual_agent_name = get_session_id(mcp)
        else:
            actual_agent_name = agent_name

        agent = memory_manager.get_agent(actual_agent_name)
        if not agent:
            agent = memory_manager.create_agent(actual_agent_name)

        memory_manager.add_message(
            actual_agent_name, "user", f"Generate image: {prompt}", 0, cost / 2
        )
        memory_manager.add_message(
            actual_agent_name,
            "assistant",
            f"Image generated and saved to {saved_path}",
            0,
            cost / 2,
        )

    cost_str = f"${cost:.4f}" if cost < 0.01 else f"${cost:.2f}"

    return f"✅ Image generated successfully!\n📁 Saved to: {saved_path}\n💰 Cost: {cost_str}"


@mcp.tool(
    description="""Retrieves a comprehensive catalog of all available OpenAI models to aid in model discovery and selection.

**Purpose & Benefits:**
This tool helps users:
- Discover all models offered by OpenAI (GPT, DALL-E, reasoning models)
- Compare models based on cost, performance, context windows, and capabilities
- Identify the most suitable OpenAI model for specific tasks or budget constraints
- Understand model generations and specialized features (reasoning, vision, etc.)

**Returns:**
Formatted listing with detailed information including:
- Model IDs and descriptions
- Context windows and token limits
- Pricing per 1M tokens (including cached input pricing)
- Capabilities (text generation, vision, reasoning, image generation, etc.)
- Model categories (reasoning, multimodal, legacy, etc.)
- API availability status

**Examples:**
```python
# Discover all available models
list_models()

# Use cases this enables:
# - "Which models can reason?" → o3, o4-mini, o1 series
# - "What's the cheapest multimodal model?" → gpt-4o-mini ($0.15/M input)
# - "Which model is best for coding?" → o4-mini, gpt-4.1
# - "Show me image generation models" → dall-e-3, dall-e-2, gpt-image-1
# - "What models support vision?" → gpt-4o series, gpt-image-1
# - "Which models support caching?" → gpt-4.1 series, gpt-4o series
```"""
)
def list_models() -> str:
    """List available OpenAI models with detailed information."""
    # Get models from API for availability checking
    api_models = client.models.list()
    api_model_ids = {m.id for m in api_models.data}

    # Use YAML-based model listing
    return format_model_listing("openai", api_model_ids)


@mcp.tool(
    description="""Checks the status of the OpenAI Tool server and API connectivity.

Use this to verify that the tool is operational before making other requests.

**Input/Output:**
- **Input**: None.
- **Output**: A string containing the server status, API connection status, and a list of available tools.

**Error Handling:**
- Raises `RuntimeError` if the OpenAI API is not configured correctly.

**Examples:**
```python
# Check the server status.
server_info()
```"""
)
def server_info() -> str:
    """Get server status and OpenAI configuration."""
    # Test API key by listing models
    models = client.models.list()
    available_models = [
        m.id for m in models.data if m.id.startswith(("gpt", "dall-e", "text-", "o1"))
    ]

    # Get agent count
    agent_count = len(memory_manager.list_agents())

    return f"""OpenAI Tool Server Status
==========================
Status: Connected and ready
API Key: Configured ✓
Available Models: {len(available_models)} models
- {', '.join(available_models[:5])}{'...' if len(available_models) > 5 else ''}

Agent Management:
- Active Agents: {agent_count}
- Memory Storage: {memory_manager.storage_dir}

Available tools:
- ask: Chat with GPT models (requires output_file parameter)
- analyze_image: Image analysis with vision models (requires output_file parameter)
- generate_image: Generate images with DALL-E
- get_response: Retrieve messages from agent conversation history
- server_info: Get server status"""
