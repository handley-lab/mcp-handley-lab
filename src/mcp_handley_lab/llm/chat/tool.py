"""Unified Chat Tool for AI interactions via MCP.

Provides a single entry point for multiple LLM providers (Gemini, OpenAI, Claude,
Mistral, Grok, Groq) with model-based provider inference.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.llm.memory import get_memory_manager
from mcp_handley_lab.llm.registry import (
    get_adapter,
    resolve_model,
    validate_options,
)
from mcp_handley_lab.llm.shared import process_llm_request
from mcp_handley_lab.shared.models import LLMResult

mcp = FastMCP("Chat Tool")


@mcp.tool(
    description="Send a message to an LLM. Provider is auto-detected from model name. "
    "Supports Gemini, OpenAI, Claude, Mistral, Grok, and Groq. "
    "Use provider names for latest defaults (e.g., model='gemini'). "
    "Returns: {content, usage: {input_tokens, output_tokens, cost, model_used}, agent_name}."
)
def ask(
    prompt: str | None = Field(
        default=None,
        description="The message to send to the LLM.",
    ),
    prompt_file: str | None = Field(
        default=None,
        description="Path to a file containing the prompt. Cannot be used with 'prompt'.",
    ),
    prompt_vars: dict[str, str] = Field(
        default_factory=dict,
        description="Variables for template substitution using ${var} syntax.",
    ),
    output_file: str = Field(
        default="",
        description="File path to save the response. Empty string means no file output. "
        "Responses are always stored in memory (~/.mcp-handley-lab/) and can be "
        "retrieved via get_response().",
    ),
    agent_name: str = Field(
        default="session",
        description="Conversation thread name. 'session' uses a shared auto-generated ID "
        "(WARNING: collides across sub-agents). Use unique names for isolated conversations, "
        "'false' to disable memory.",
    ),
    model: str = Field(
        default="gemini",
        description="Model or provider name. Provider is inferred automatically. "
        "Use provider names (gemini, openai, claude) for latest defaults, "
        "or specific model IDs. Run list_models() to see available options.",
    ),
    temperature: float = Field(
        default=1.0,
        description="Controls randomness (0.0-2.0). Higher is more creative.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="Files to include as context. Accepts: local paths, URLs, "
        "or data URIs (data:mime/type;base64,...). Text files read as content, "
        "images/PDFs sent to multimodal models.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions for the conversation.",
    ),
    system_prompt_file: str | None = Field(
        default=None,
        description="Path to a file containing system instructions.",
    ),
    system_prompt_vars: dict[str, str] = Field(
        default_factory=dict,
        description="Variables for system prompt template substitution.",
    ),
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific options. Use mcp-models list_models() to discover. "
        "Examples: grounding (Gemini), reasoning_effort (OpenAI), enable_thinking (Claude).",
    ),
) -> LLMResult:
    """Send a message to an LLM with automatic provider detection."""
    provider, canonical_model, model_config = resolve_model(model)
    validate_options(provider, model, model_config, options)

    # Route agent models (e.g., deep research) to their specialized adapter
    adapter_type = "deep_research" if model_config.get("is_agent") else "generation"
    generation_func = get_adapter(provider, adapter_type)

    return process_llm_request(
        prompt=prompt,
        prompt_file=prompt_file,
        prompt_vars=prompt_vars,
        output_file=output_file,
        agent_name=agent_name,
        model=canonical_model,
        provider=provider,
        generation_func=generation_func,
        mcp_instance=mcp,
        temperature=temperature,
        files=files,
        system_prompt=system_prompt,
        system_prompt_file=system_prompt_file,
        system_prompt_vars=system_prompt_vars,
        options=options,
    )


@mcp.tool(
    description="Analyze images with vision-capable LLMs. Provider auto-detected from model. "
    "Supports Gemini, OpenAI, Claude, Mistral, and Grok vision models. "
    "Returns: {content, usage: {input_tokens, output_tokens, cost, model_used}, agent_name}."
)
def analyze_image(
    prompt: str = Field(
        ...,
        description="Question about the image(s).",
    ),
    images: list[str] = Field(
        ...,
        description="Images to analyze. Accepts: local paths, URLs, "
        "data URIs (data:image/png;base64,...), or raw base64 strings.",
    ),
    output_file: str = Field(
        default="",
        description="File path to save analysis. Empty string means no file output. "
        "Responses stored in memory and retrievable via get_response().",
    ),
    model: str = Field(
        default="gemini",
        description="Vision model or provider name. Provider is inferred automatically. "
        "Use provider names for latest defaults, or specific model IDs.",
    ),
    focus: str = Field(
        default="general",
        description="Analysis focus (e.g., 'ocr', 'objects', 'general').",
    ),
    agent_name: str = Field(
        default="session",
        description="Conversation thread name. 'session' uses a shared auto-generated ID "
        "(WARNING: collides across sub-agents). Use unique names for isolated conversations.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions for the analysis.",
    ),
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific options.",
    ),
) -> LLMResult:
    """Analyze images with vision-capable LLMs."""
    provider, canonical_model, model_config = resolve_model(model)
    validate_options(provider, model, model_config, options)

    analysis_func = get_adapter(provider, "image_analysis")

    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=canonical_model,
        provider=provider,
        generation_func=analysis_func,
        mcp_instance=mcp,
        images=images,
        focus=focus,
        system_prompt=system_prompt,
        options=options,
    )


@mcp.tool(
    description="Retrieve a past assistant response from an agent's conversation history. "
    "Only returns assistant messages (LLM responses), not user messages. "
    "Returns: {content, usage: {input_tokens, output_tokens, cost, model_used}, agent_name, ...metadata}."
)
def get_response(
    agent_name: str = Field(
        ...,
        description="The agent name to retrieve the response from. "
        "Use 'session' with provider param to get current session's responses.",
    ),
    index: int = Field(
        default=-1,
        description="Response index among assistant messages only. "
        "Use -1 for last response, -2 for second-to-last, 0 for first, etc.",
    ),
    provider: str = Field(
        default="",
        description="Provider name (gemini, openai, etc.) to resolve 'session' agent name. "
        "Required when agent_name is 'session'.",
    ),
    output_file: str = Field(
        default="",
        description="File path to save response content. Empty string means no file output.",
    ),
) -> dict[str, Any]:
    """Retrieve an assistant response from an agent's conversation history.

    Returns the full message dict including content and usage metadata.
    Raises ValueError if agent not found, IndexError if no assistant responses or out of range.
    """
    from pathlib import Path

    from mcp_handley_lab.llm.common import get_session_id

    actual_agent_name = agent_name
    if agent_name == "session":
        if not provider:
            raise ValueError(
                "provider parameter is required when agent_name is 'session'"
            )
        actual_agent_name = get_session_id(mcp, provider)

    memory_manager = get_memory_manager()
    response = memory_manager.get_response(actual_agent_name, index)

    if output_file:
        Path(output_file).write_text(response["content"])

    return response


@mcp.tool(
    description="Review conversation histories in JSON format. "
    "Shows user questions in full and abbreviated assistant responses. "
    "Returns: {project, agents: [{name, stats, messages: [{role, content, timestamp, response_index?}]}]}."
)
def review_conversations(
    agent_name: str = Field(
        default="",
        description="Filter to specific agent. Empty for all agents.",
    ),
    output_file: str = Field(
        default="",
        description="File path to save review. Empty string means no file output.",
    ),
    max_response_chars: int = Field(
        default=200,
        description="Max characters per assistant response (truncated with ...).",
    ),
) -> dict[str, Any]:
    """Review all agents' conversation histories with truncated assistant responses.

    Returns JSON with agent stats, system prompts, and messages.
    Assistant responses show response_index for use with get_response().
    """
    import json
    from pathlib import Path

    memory_manager = get_memory_manager()
    agents = memory_manager.list_agents()

    # Filter to specific agent if requested
    if agent_name:
        agents = [a for a in agents if a.name == agent_name]
        if not agents:
            raise ValueError(f"Agent '{agent_name}' not found")

    result = {
        "project": str(memory_manager.cwd),
        "agents": [a.get_conversation_summary(max_response_chars) for a in agents],
    }

    if output_file:
        Path(output_file).write_text(json.dumps(result, indent=2))

    return result
