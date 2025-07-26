#!/usr/bin/env python3
"""
Analyze token usage of existing MCP schemas from tool_schemas.json
"""

import json
from pathlib import Path

import tiktoken


def count_tokens(text: str, encoding: str = "cl100k_base") -> int:
    """Count tokens using tiktoken."""
    enc = tiktoken.get_encoding(encoding)
    return len(enc.encode(text))


def analyze_schema_file():
    """Analyze the existing tool_schemas.json file."""

    schema_file = (
        Path(__file__).parent / "src" / "mcp_handley_lab" / "tool_schemas.json"
    )

    if not schema_file.exists():
        print(f"❌ Schema file not found: {schema_file}")
        return

    with open(schema_file) as f:
        schema_data = json.load(f)

    tools = schema_data.get("tools", {})

    print("MCP Schema Token Analysis")
    print("=" * 50)
    print(f"Schema file: {schema_file}")
    print(f"Total tools: {len(tools)}")
    print()

    total_tokens = 0
    total_functions = 0

    for tool_name, tool_data in tools.items():
        print(f"📦 {tool_name.upper()}")
        print("-" * 30)

        functions = tool_data.get("functions", {})
        function_count = len(functions)
        total_functions += function_count

        # Calculate tokens for this tool
        tool_json = json.dumps(tool_data)
        tool_tokens = count_tokens(tool_json)

        print(f"  Functions: {function_count}")
        print(f"  Total tokens: {tool_tokens:,}")

        if function_count > 0:
            print(f"  Avg per function: {tool_tokens // function_count:,}")

        # Show individual function tokens
        for func_name, func_data in functions.items():
            func_json = json.dumps(func_data)
            func_tokens = count_tokens(func_json)
            print(f"    • {func_name}: {func_tokens:,} tokens")

        total_tokens += tool_tokens
        print()

    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Total tools: {len(tools)}")
    print(f"Total functions: {total_functions}")
    print(f"Total schema tokens: {total_tokens:,}")

    if total_functions > 0:
        print(f"Average tokens per function: {total_tokens // total_functions:,}")

    # Context window analysis
    print("\nContext window impact:")
    print(f"  Claude 3.5 Sonnet (200K): {(total_tokens/200000)*100:.1f}%")
    print(f"  GPT-4 (128K): {(total_tokens/128000)*100:.1f}%")
    print(f"  GPT-4o (128K): {(total_tokens/128000)*100:.1f}%")

    # Breakdown by category
    print("\nBreakdown by category:")

    categories = {
        "LLM Tools": ["gemini", "openai", "claude", "agent"],
        "Development": ["vim", "code2prompt", "github"],
        "Productivity": ["google-calendar", "email"],
        "Research": ["arxiv"],
        "Utilities": ["jq"],
    }

    for category, tool_names in categories.items():
        category_tokens = 0
        category_functions = 0

        for tool_name in tool_names:
            if tool_name in tools:
                tool_json = json.dumps(tools[tool_name])
                category_tokens += count_tokens(tool_json)
                category_functions += len(tools[tool_name].get("functions", {}))

        if category_tokens > 0:
            print(
                f"  {category}: {category_tokens:,} tokens ({category_functions} functions)"
            )

    # Show largest tools
    print("\nLargest tools by token count:")
    tool_sizes = []
    for tool_name, tool_data in tools.items():
        tool_json = json.dumps(tool_data)
        tool_tokens = count_tokens(tool_json)
        tool_sizes.append((tool_name, tool_tokens, len(tool_data.get("functions", {}))))

    tool_sizes.sort(key=lambda x: x[1], reverse=True)

    for i, (tool_name, tokens, functions) in enumerate(tool_sizes[:5], 1):
        print(f"  {i}. {tool_name}: {tokens:,} tokens ({functions} functions)")


if __name__ == "__main__":
    analyze_schema_file()
