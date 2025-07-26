"""LLM response formatter for better CLI display."""

from typing import Any


def format_llm_response(response: dict[str, Any], max_content_length: int = 200) -> str:
    """Format LLM response for clean CLI display.

    Args:
        response: LLM response dictionary
        max_content_length: Maximum characters to show from content

    Returns:
        Formatted string for display
    """
    if not isinstance(response, dict):
        return str(response)

    # Extract key information
    content = response.get("content", "")
    usage = response.get("usage", {})
    agent_name = response.get("agent_name", "")
    model = usage.get("model_used", "")

    # Format content preview
    if len(content) > max_content_length:
        content_preview = content[:max_content_length] + "..."
    else:
        content_preview = content

    # Clean up content for display (remove excessive newlines)
    content_preview = " ".join(content_preview.split())

    # Build formatted output
    output = []

    # Header with model and agent info
    header_parts = []
    if model:
        header_parts.append(f"Model: {model}")
    if agent_name:
        header_parts.append(f"Agent: {agent_name}")

    if header_parts:
        output.append("🤖 " + " | ".join(header_parts))

    # Usage stats
    if usage:
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cost = usage.get("cost", 0)

        usage_line = f"📊 Tokens: {input_tokens} in → {output_tokens} out"
        if cost > 0:
            usage_line += f" | Cost: ${cost:.4f}"
        output.append(usage_line)

    # Content preview
    if content_preview:
        output.append("💬 " + content_preview)

    # Additional metadata if available
    finish_reason = response.get("finish_reason")
    if finish_reason and finish_reason != "stop":
        output.append(f"⚠️  Finish reason: {finish_reason}")

    return "\n".join(output)


def format_usage_only(response: dict[str, Any]) -> str:
    """Extract and format only usage statistics.

    Args:
        response: LLM response dictionary

    Returns:
        Formatted usage string
    """
    if not isinstance(response, dict):
        return "No usage data"

    usage = response.get("usage", {})
    if not usage:
        return "No usage data"

    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cost = usage.get("cost", 0)
    model = usage.get("model_used", "unknown")

    parts = [
        f"Input: {input_tokens:,} tokens",
        f"Output: {output_tokens:,} tokens",
        f"Total: {input_tokens + output_tokens:,} tokens",
    ]

    if cost > 0:
        parts.append(f"Cost: ${cost:.4f}")

    return f"{model} | " + " | ".join(parts)


def extract_content_only(response: dict[str, Any]) -> str:
    """Extract only the content from LLM response.

    Args:
        response: LLM response dictionary

    Returns:
        Content string
    """
    if not isinstance(response, dict):
        return str(response)

    return response.get("content", "")
