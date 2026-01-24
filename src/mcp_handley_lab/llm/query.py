"""Standalone LLM query function for direct use (no MCP required).

Reuses the exact same validation and adapter-calling pattern as the MCP chat tool
to ensure consistent behavior across all providers.
"""

from dataclasses import dataclass
from typing import Any

from mcp_handley_lab.llm.registry import get_adapter, resolve_model, validate_options


@dataclass
class QueryResult:
    """Result from query() with text, usage info, and raw response."""

    text: str
    input_tokens: int
    output_tokens: int
    model_used: str
    raw: dict[str, Any]


def query(
    prompt: str,
    model: str = "gemini",
    system_prompt: str = "",
    temperature: float = 1.0,
    options: dict[str, Any] | None = None,
) -> QueryResult:
    """Query an LLM directly. Works in REPL, scripts, anywhere.

    Uses the same validation and adapter infrastructure as the MCP chat tool.

    Args:
        prompt: The question/task for the LLM
        model: Model name or provider (gemini, openai, claude, etc.)
        system_prompt: System instructions (empty string = none)
        temperature: Creativity (0.0-2.0)
        options: Provider-specific options dict (grounding, reasoning_effort, etc.)

    Returns:
        QueryResult with .text, .input_tokens, .output_tokens, .model_used, .raw

    Example:
        >>> from mcp_handley_lab import llm
        >>> result = llm.query("What is 2+2?")
        >>> print(result.text)
        'The answer is 4.'
        >>> llm.query("Search for X", model="gemini", options={"grounding": True})
    """
    provider, model_id, config = resolve_model(model)
    options = options or {}
    validate_options(provider, model, config, options)

    adapter_type = "deep_research" if config.get("is_agent") else "generation"
    adapter = get_adapter(provider, adapter_type)

    response = adapter(
        prompt=prompt,
        model=model_id,
        history=[],
        system_instruction=system_prompt or None,
        temperature=temperature,
        options=options,
    )

    return QueryResult(
        text=response["text"],
        input_tokens=response.get("input_tokens", 0),
        output_tokens=response.get("output_tokens", 0),
        model_used=model_id,
        raw=response,
    )
