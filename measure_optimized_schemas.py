#!/usr/bin/env python3
"""
Measure token usage of optimized MCP schemas by extracting docstrings from actual tool code.
"""

import re
import sys
from pathlib import Path

import tiktoken

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))


def count_tokens(text: str, encoding: str = "cl100k_base") -> int:
    """Count tokens using tiktoken."""
    enc = tiktoken.get_encoding(encoding)
    return len(enc.encode(text))


def extract_tool_schemas(file_path):
    """Extract @mcp.tool descriptions and Field descriptions from a Python file."""
    with open(file_path) as f:
        content = f.read()

    # Find all @mcp.tool decorators and their descriptions
    tool_pattern = r'@mcp\.tool\(\s*description="([^"]+)"\s*\)'
    tools = re.findall(tool_pattern, content)

    # Find all Field descriptions
    field_pattern = r'Field\([^)]*description="([^"]+)"[^)]*\)'
    fields = re.findall(field_pattern, content)

    return tools, fields


def analyze_optimized_schemas():
    """Analyze the optimized tool schemas."""

    src_dir = project_root / "src" / "mcp_handley_lab"

    # Tool files to analyze
    tool_files = [
        ("OpenAI", src_dir / "llm" / "openai" / "tool.py"),
        ("Gemini", src_dir / "llm" / "gemini" / "tool.py"),
        ("Claude", src_dir / "llm" / "claude" / "tool.py"),
        ("Grok", src_dir / "llm" / "grok" / "tool.py"),
        ("Google Calendar", src_dir / "google_calendar" / "tool.py"),
        ("Code2Prompt", src_dir / "code2prompt" / "tool.py"),
        ("ArXiv", src_dir / "arxiv" / "tool.py"),
        ("Vim", src_dir / "vim" / "tool.py"),
    ]

    print("Optimized MCP Schema Token Analysis")
    print("=" * 50)

    total_tokens = 0
    total_tools = 0
    total_fields = 0

    for tool_name, file_path in tool_files:
        if not file_path.exists():
            print(f"❌ {tool_name}: File not found")
            continue

        print(f"\n📦 {tool_name.upper()}")
        print("-" * 30)

        try:
            tools, fields = extract_tool_schemas(file_path)

            # Calculate tokens for tool descriptions
            tool_tokens = sum(count_tokens(desc) for desc in tools)

            # Calculate tokens for field descriptions
            field_tokens = sum(count_tokens(desc) for desc in fields)

            # Estimate total tokens for this tool (including schema structure)
            # Add overhead for JSON structure, parameter names, types, etc.
            structure_overhead = (
                len(tools) * 50 + len(fields) * 20
            )  # Conservative estimate
            total_tool_tokens = tool_tokens + field_tokens + structure_overhead

            print(f"  Tool functions: {len(tools)}")
            print(f"  Field parameters: {len(fields)}")
            print(f"  Description tokens: {tool_tokens + field_tokens:,}")
            print(f"  Estimated total tokens: {total_tool_tokens:,}")

            # Show individual tool descriptions
            for i, desc in enumerate(tools, 1):
                desc_tokens = count_tokens(desc)
                print(f'    • Function {i}: {desc_tokens:,} tokens - "{desc[:50]}..."')

            total_tokens += total_tool_tokens
            total_tools += len(tools)
            total_fields += len(fields)

        except Exception as e:
            print(f"  ❌ Error analyzing {tool_name}: {e}")

    print("\n" + "=" * 50)
    print("OPTIMIZED SUMMARY")
    print("=" * 50)
    print(f"Total tool functions: {total_tools}")
    print(f"Total field parameters: {total_fields}")
    print(f"Estimated total schema tokens: {total_tokens:,}")

    if total_tools > 0:
        print(f"Average tokens per function: {total_tokens // total_tools:,}")

    # Compare with original
    original_tokens = 13996  # From previous analysis
    if total_tokens < original_tokens:
        savings = original_tokens - total_tokens
        percentage = (savings / original_tokens) * 100
        print("\n📊 OPTIMIZATION RESULTS:")
        print(f"Original schema tokens: {original_tokens:,}")
        print(f"Optimized schema tokens: {total_tokens:,}")
        print(f"Tokens saved: {savings:,}")
        print(f"Reduction: {percentage:.1f}%")

    # Context window analysis
    print("\nOptimized context window impact:")
    print(f"  Claude 3.5 Sonnet (200K): {(total_tokens/200000)*100:.1f}%")
    print(f"  GPT-4 (128K): {(total_tokens/128000)*100:.1f}%")
    print(f"  GPT-4o (128K): {(total_tokens/128000)*100:.1f}%")


if __name__ == "__main__":
    analyze_optimized_schemas()
