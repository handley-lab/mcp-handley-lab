"""Unified Chat Tool for AI interactions via MCP.

Provides a single entry point for multiple LLM providers (Gemini, OpenAI, Claude,
Mistral, Grok, Groq) with model-based provider inference and Git-backed memory.
"""

import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.llm.registry import get_adapter, resolve_model, validate_options
from mcp_handley_lab.llm.shared import chat as _chat
from mcp_handley_lab.llm.shared import conversation as _conversation
from mcp_handley_lab.llm.shared import process_llm_request
from mcp_handley_lab.shared.models import LLMResult  # noqa: F401 - used in type hints

mcp = FastMCP("Chat Tool")


def _resolve_session_branch(branch: str, model: str = "gemini") -> str:
    """Resolve 'session' branch to client-scoped ID for MCP context."""
    if branch != "session":
        return branch
    # mcp.get_context() is instance method on FastMCP
    context = mcp.get_context()
    client_id = getattr(context, "client_id", None) or os.getpid()
    provider, _, _ = resolve_model(model)
    return f"_session_{provider}_{client_id}"


@mcp.tool(
    description="Send a message to an LLM. Provider is auto-detected from model name. "
    "Supports Gemini, OpenAI, Claude, Mistral, Grok, and Groq. "
    "Use provider names for latest defaults (e.g., model='gemini'). "
    "Returns: {content, usage: {input_tokens, output_tokens, cost, model_used}, branch}."
)
def chat(
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
        "retrieved via conversation(action='response').",
    ),
    branch: str = Field(
        default="session",
        description="Conversation branch name. 'session' uses a shared auto-generated ID "
        "(WARNING: collides across concurrent processes). Use unique names for isolated "
        "conversations, 'false' to disable memory.",
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
    from_ref: str | None = Field(
        default=None,
        description="Fork from this ref when creating a new conversation branch. "
        "Use commit_sha from a previous response to fork from that point.",
    ),
) -> LLMResult:
    """Send a message to an LLM with automatic provider detection."""
    return _chat(
        prompt=prompt,
        prompt_file=prompt_file,
        prompt_vars=prompt_vars,
        output_file=output_file,
        branch=_resolve_session_branch(branch, model),
        model=model,
        temperature=temperature,
        files=files,
        system_prompt=system_prompt,
        system_prompt_file=system_prompt_file,
        system_prompt_vars=system_prompt_vars,
        options=options,
        from_ref=from_ref,
    )


@mcp.tool(
    description="Analyze images with vision-capable LLMs. Provider auto-detected from model. "
    "Supports Gemini, OpenAI, Claude, Mistral, and Grok vision models. "
    "Returns: {content, usage: {input_tokens, output_tokens, cost, model_used}, branch}."
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
        "Responses stored in memory and retrievable via conversation(action='response').",
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
    branch: str = Field(
        default="session",
        description="Conversation branch name. 'session' uses a shared auto-generated ID "
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
        branch=_resolve_session_branch(branch, model),
        model=canonical_model,
        provider=provider,
        generation_func=analysis_func,
        images=images,
        focus=focus,
        system_prompt=system_prompt,
        options=options,
    )


@mcp.tool(
    description="Manage conversation branches. Actions: "
    "'list' (all branches), 'log' (history with hashes), 'show' (content at ref), "
    "'response' (get assistant message by index), "
    "'edit' (start editing session with worktree), 'done' (end editing session)."
)
def conversation(
    action: str = Field(
        ...,
        description="Action to perform: 'list', 'log', 'show', 'response', 'edit', 'done'.",
    ),
    branch: str = Field(
        default="",
        description="Target branch for log/show/response actions.",
    ),
    ref: str = Field(
        default="",
        description="Specific commit ref for show action. If provided, takes precedence over branch.",
    ),
    index: int = Field(
        default=-1,
        description="For response action: assistant message index (-1=last, -2=second-to-last, 0=first).",
    ),
    limit: int = Field(
        default=20,
        description="For log action: maximum number of entries to return.",
    ),
    force: bool = Field(
        default=False,
        description="For done action: force removal even if lock not held by this process.",
    ),
) -> dict[str, Any]:
    """Git interface for conversation management."""
    # Resolve "session" branch for actions that use branch parameter
    resolved_branch = _resolve_session_branch(branch) if branch else branch
    return _conversation(
        action=action,
        branch=resolved_branch,
        ref=ref,
        index=index,
        limit=limit,
        force=force,
    )
