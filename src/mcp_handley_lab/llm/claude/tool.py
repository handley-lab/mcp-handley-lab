"""Claude LLM tool for AI interactions via MCP."""

from typing import Any

from anthropic import Anthropic
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    build_server_info,
    load_provider_models,
    resolve_files_for_llm,
    resolve_images_for_multimodal_prompt,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.model_loader import (
    get_structured_model_listing,
)
from mcp_handley_lab.llm.shared import process_llm_request
from mcp_handley_lab.shared.models import LLMResult, ModelListing, ServerInfo

mcp = FastMCP("Claude Tool")

# Configure Claude client - fail fast if API key is invalid/missing
client = Anthropic(api_key=settings.anthropic_api_key)

# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL, _get_model_config = load_provider_models("claude")


def _resolve_model_alias(model: str) -> str:
    """Resolve model aliases to full model names."""
    aliases = {
        "sonnet": "claude-3-5-sonnet-20241022",
        "opus": "claude-3-opus-20240229",
        "haiku": "claude-3-5-haiku-20241022",
    }
    return aliases.get(model, model)


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
    images: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Resolve image inputs to Claude content blocks."""
    if images is None:
        images = []
    # Use standardized image processing
    _, image_blocks = resolve_images_for_multimodal_prompt("", images)

    # Convert to Claude's specific format
    claude_image_blocks = []
    for image_block in image_blocks:
        claude_image_blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_block["mime_type"],
                    "data": image_block["data"],
                },
            }
        )

    return claude_image_blocks


def _claude_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Claude-specific text generation function for the shared processor."""
    # Extract Claude-specific parameters
    temperature = kwargs.get("temperature", 1.0)
    files = kwargs.get("files")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Get model configuration
    resolved_model = _resolve_model_alias(model)
    model_config = _get_model_config(resolved_model)
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

    # Extract additional Claude metadata
    return {
        "text": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "finish_reason": response.stop_reason,
        "avg_logprobs": 0.0,  # Claude doesn't provide logprobs
        "model_version": response.model,
        "response_id": response.id,
        "stop_sequence": response.stop_sequence or "",
        "cache_creation_input_tokens": response.usage.cache_creation_input_tokens or 0,
        "cache_read_input_tokens": response.usage.cache_read_input_tokens or 0,
        "service_tier": response.usage.service_tier or "",
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
    resolved_model = _resolve_model_alias(model)
    model_config = _get_model_config(resolved_model)
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
        "temperature": 1.0,
        "timeout": 599,
    }

    # Add system instruction if provided
    if system_instruction:
        request_params["system"] = system_instruction

    # Make API call
    response = client.messages.create(**request_params)

    return {
        "text": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "finish_reason": response.stop_reason,
        "avg_logprobs": 0.0,  # Claude doesn't provide logprobs
        "model_version": response.model,
        "response_id": response.id,
        "stop_sequence": response.stop_sequence or "",
        "cache_creation_input_tokens": response.usage.cache_creation_input_tokens or 0,
        "cache_read_input_tokens": response.usage.cache_read_input_tokens or 0,
        "service_tier": response.usage.service_tier or "",
    }


@mcp.tool(
    description="Delegates a user query to external Anthropic Claude AI service on behalf of the human user. Returns Claude's verbatim response to assist the user. Use `agent_name` for separate conversation thread. For reviewing documents/code: provide context via `files` parameter or use code2prompt first."
)
def ask(
    prompt: str = Field(
        ...,
        description="The user's question to delegate to external Claude AI service.",
    ),
    output_file: str = Field(
        "-",
        description="Path to save Claude's response. Use '-' to stream the output directly to stdout.",
    ),
    agent_name: str = Field(
        "session",
        description="Separate conversation thread with Claude AI service (distinct from your conversation with the user).",
    ),
    model: str = Field(
        DEFAULT_MODEL,
        description="The Claude model to use (e.g., 'claude-3-5-sonnet-20240620'). Can also use aliases like 'sonnet', 'opus', or 'haiku'.",
    ),
    temperature: float = Field(
        1.0,
        description="Controls randomness (0.0 to 2.0). Higher values like 1.0 are more creative, while lower values are more deterministic.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of file paths to be read and included as context in the prompt.",
    ),
    max_output_tokens: int = Field(
        0,
        description="Maximum number of tokens to generate in the response. If 0, uses the model's default maximum.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external Claude AI service. Remembered for this conversation thread.",
    ),
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
        system_prompt=system_prompt,
    )


@mcp.tool(
    description="Delegates image analysis to external Claude vision AI service on behalf of the user. Returns Claude's verbatim visual analysis to assist the user."
)
def analyze_image(
    prompt: str = Field(
        ...,
        description="The user's question about the images to delegate to external Claude vision AI service.",
    ),
    output_file: str = Field(
        "-",
        description="Path to save Claude's visual analysis. Use '-' to stream the output directly to stdout.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of image file paths to be analyzed along with the prompt.",
    ),
    focus: str = Field(
        "general",
        description="Specifies the focus of the analysis (e.g., 'text' to transcribe, 'objects' to identify).",
    ),
    model: str = Field(
        "claude-3-5-sonnet-20240620",
        description="The vision-capable Claude model to use for the analysis. Must be a model that supports image inputs.",
    ),
    agent_name: str = Field(
        "session",
        description="Separate conversation thread with Claude AI service (distinct from your conversation with the user).",
    ),
    max_output_tokens: int = Field(
        0,
        description="Maximum number of tokens to generate in the response. If 0, uses the model's default maximum.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external Claude AI service. Remembered for this conversation thread.",
    ),
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
        system_prompt=system_prompt,
    )


@mcp.tool(
    description="Retrieves a comprehensive catalog of all available Claude models with pricing, capabilities, and performance information. Helps compare models and select the most suitable one for specific tasks or budget constraints."
)
def list_models() -> ModelListing:
    """List available Claude models with detailed information."""
    # Use structured model listing
    return get_structured_model_listing("claude")


@mcp.tool(
    description="Checks the status of the Claude Tool server and API connectivity. Returns connection status and list of available tools. Use this to verify the tool is operational before making other requests."
)
def server_info() -> ServerInfo:
    """Get server status and Claude configuration."""
    # Test API by making a simple request
    client.messages.create(
        model="claude-3-5-haiku-20241022",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10,
    )

    available_models = list(MODEL_CONFIGS.keys())

    return build_server_info(
        provider_name="Claude",
        available_models=available_models,
        memory_manager=memory_manager,
        vision_support=True,
        image_generation=False,
    )
