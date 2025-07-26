#!/usr/bin/env python3
"""
Measure token usage of MCP schemas across all tools in the project.
"""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import tiktoken

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))


async def get_tool_schemas(module_path: str) -> dict[str, Any]:
    """Extract MCP tool schemas from a module."""
    try:
        spec = importlib.util.spec_from_file_location("module", module_path)
        if not spec or not spec.loader:
            return {}

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find FastMCP instance
        mcp_instance = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if hasattr(attr, "list_tools"):
                mcp_instance = attr
                break

        if not mcp_instance:
            return {}

        # Get tool schemas
        tools_result = await mcp_instance.list_tools()
        return {
            "module": module_path,
            "tools": tools_result.tools if hasattr(tools_result, "tools") else [],
        }
    except Exception as e:
        print(f"Error loading {module_path}: {e}")
        return {}


def count_tokens(text: str, encoding: str = "cl100k_base") -> int:
    """Count tokens using tiktoken."""
    enc = tiktoken.get_encoding(encoding)
    return len(enc.encode(text))


def analyze_schema_tokens(schema_data: dict[str, Any]) -> dict[str, int]:
    """Analyze token usage of schema components."""

    # Convert schema to JSON string for token counting
    schema_json = json.dumps(schema_data, indent=2)

    return {
        "total_tokens": count_tokens(schema_json),
        "compact_tokens": count_tokens(json.dumps(schema_data)),
        "tool_count": len(schema_data.get("tools", [])),
        "avg_tokens_per_tool": count_tokens(schema_json)
        // max(len(schema_data.get("tools", [])), 1),
    }


async def main():
    """Main analysis function."""

    # Find all MCP tool modules
    src_dir = project_root / "src" / "mcp_handley_lab"
    tool_modules = []

    # Look for tool.py files in subdirectories
    for tool_dir in src_dir.rglob("tool.py"):
        if tool_dir.is_file():
            tool_modules.append(str(tool_dir))

    print(f"Found {len(tool_modules)} MCP tool modules:")
    for module in tool_modules:
        print(f"  - {Path(module).relative_to(src_dir)}")

    print("\n" + "=" * 60)
    print("MCP SCHEMA TOKEN ANALYSIS")
    print("=" * 60)

    total_tokens = 0
    total_tools = 0

    for module_path in tool_modules:
        module_name = Path(module_path).parent.name
        print(f"\n📦 {module_name.upper()}")
        print("-" * 40)

        schema_data = await get_tool_schemas(module_path)

        if not schema_data or not schema_data.get("tools"):
            print("  ❌ No tools found or failed to load")
            continue

        analysis = analyze_schema_tokens(schema_data)

        print(f"  Tools: {analysis['tool_count']}")
        print(f"  Schema tokens (formatted): {analysis['total_tokens']:,}")
        print(f"  Schema tokens (compact): {analysis['compact_tokens']:,}")
        print(f"  Avg tokens per tool: {analysis['avg_tokens_per_tool']:,}")

        # Show individual tool info
        for tool in schema_data["tools"]:
            tool_json = json.dumps(tool, indent=2)
            tool_tokens = count_tokens(tool_json)
            print(f"    • {tool['name']}: {tool_tokens:,} tokens")

        total_tokens += analysis["compact_tokens"]
        total_tools += analysis["tool_count"]

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total tools: {total_tools}")
    print(f"Total schema tokens (compact): {total_tokens:,}")
    print(f"Average tokens per tool: {total_tokens // max(total_tools, 1):,}")

    # Context window analysis
    print("\nContext window impact:")
    print(f"  Claude 3.5 Sonnet (200K): {(total_tokens/200000)*100:.1f}%")
    print(f"  GPT-4 (128K): {(total_tokens/128000)*100:.1f}%")
    print(f"  GPT-4o (128K): {(total_tokens/128000)*100:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
