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
    "Use provider names (gemini, openai, claude, mistral, grok, groq) for latest defaults. "
    "Use options dict for provider-specific features. Run list_models() to see options."
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
        default="-",
        description="File path to save the response. Defaults to '-' (stdout only). "
        "With global memory, responses are stored in ~/.mcp-handley-lab/ and can be "
        "retrieved later via get_response().",
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
        description="File paths to include as context.",
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

    generation_func = get_adapter(provider, "generation")

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
    "Use provider names for latest defaults."
)
def analyze_image(
    prompt: str = Field(
        ...,
        description="Question about the image(s).",
    ),
    files: list[str] = Field(
        ...,
        description="Image file paths or base64 strings to analyze.",
    ),
    output_file: str = Field(
        default="-",
        description="File path to save analysis. Defaults to '-' (stdout only). "
        "With global memory, responses are stored and retrievable via get_response().",
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
        images=files,
        focus=focus,
        system_prompt=system_prompt,
        options=options,
    )


@mcp.tool(
    description="Retrieve a past assistant response from an agent's conversation history. "
    "Only returns assistant messages (LLM responses), not user messages. "
    "Useful for accessing responses when output_file was not specified."
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
) -> str:
    """Retrieve an assistant response from an agent's conversation history.

    Returns the content of the assistant message at the specified index.
    Raises ValueError if agent not found, IndexError if no assistant responses or out of range.
    """
    from mcp_handley_lab.llm.common import get_session_id

    actual_agent_name = agent_name
    if agent_name == "session":
        if not provider:
            raise ValueError(
                "provider parameter is required when agent_name is 'session'"
            )
        actual_agent_name = get_session_id(mcp, provider)

    memory_manager = get_memory_manager()
    return memory_manager.get_response(actual_agent_name, index)
