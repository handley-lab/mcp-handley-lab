#!/usr/bin/env python3
"""
Simple MCP schema token measurement by importing installed tools.
"""

import json
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


def analyze_tool_schemas():
    """Analyze MCP tool schemas by importing modules."""

    # Import the main tools we can access
    tool_modules = [
        ("Vim", "mcp_handley_lab.vim.tool"),
        ("Code2Prompt", "mcp_handley_lab.code2prompt.tool"),
        ("ArXiv", "mcp_handley_lab.arxiv.tool"),
        ("Py2Nb", "mcp_handley_lab.py2nb.tool"),
        ("Google Maps", "mcp_handley_lab.google_maps.tool"),
        ("LLM Gemini", "mcp_handley_lab.llm.gemini.tool"),
        ("LLM OpenAI", "mcp_handley_lab.llm.openai.tool"),
        ("LLM Claude", "mcp_handley_lab.llm.claude.tool"),
        ("LLM Grok", "mcp_handley_lab.llm.grok.tool"),
        ("Email", "mcp_handley_lab.email.tool"),
    ]

    total_tokens = 0
    total_tools = 0
    successful_imports = 0

    print("MCP Schema Token Analysis")
    print("=" * 50)

    for tool_name, module_name in tool_modules:
        print(f"\n📦 {tool_name}")
        print("-" * 30)

        try:
            # Import the module
            module = __import__(module_name, fromlist=[""])

            # Find the mcp instance (usually named 'mcp')
            mcp_instance = getattr(module, "mcp", None)
            if not mcp_instance or not hasattr(mcp_instance, "_tools"):
                # Fallback: search for any FastMCP instance
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if hasattr(attr, "_tools") and hasattr(attr, "list_tools"):
                        mcp_instance = attr
                        break

            if not mcp_instance:
                print("  ❌ No FastMCP instance found")
                continue

            # Get tool information from the tool manager
            tools_info = []
            try:
                # Try to get tools via list_tools method (async)
                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                tools_result = loop.run_until_complete(mcp_instance.list_tools())

                # Convert MCP tools to our format
                if hasattr(tools_result, "tools"):
                    for tool in tools_result.tools:
                        tools_info.append(
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.inputSchema,
                            }
                        )
                loop.close()
            except Exception as e:
                print(f"    ⚠️  Could not get tools via list_tools: {e}")
                # Fallback to tool manager inspection
                if hasattr(mcp_instance, "_tool_manager") and hasattr(
                    mcp_instance._tool_manager, "tools"
                ):
                    for (
                        tool_name,
                        tool_info,
                    ) in mcp_instance._tool_manager.tools.items():
                        tools_info.append(
                            {
                                "name": tool_name,
                                "description": str(
                                    getattr(tool_info, "description", "")
                                ),
                                "inputSchema": str(
                                    getattr(tool_info, "inputSchema", {})
                                ),
                            }
                        )

            if not tools_info:
                print("  ❌ No tools found in instance")
                continue

            # Calculate tokens
            compact_json = json.dumps(tools_info)

            tool_count = len(tools_info)
            schema_tokens = count_tokens(compact_json)

            print(f"  ✅ Tools: {tool_count}")
            print(f"  📊 Schema tokens: {schema_tokens:,}")
            print(f"  📈 Avg per tool: {schema_tokens // tool_count:,}")

            for tool in tools_info:
                tool_json = json.dumps(tool)
                tool_tokens = count_tokens(tool_json)
                print(f"    • {tool['name']}: {tool_tokens:,} tokens")

            total_tokens += schema_tokens
            total_tools += tool_count
            successful_imports += 1

        except Exception as e:
            print(f"  ❌ Import failed: {e}")

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Successful imports: {successful_imports}")
    print(f"Total tools: {total_tools}")
    print(f"Total schema tokens: {total_tokens:,}")
    if total_tools > 0:
        print(f"Average tokens per tool: {total_tokens // total_tools:,}")

    # Context window analysis
    if total_tokens > 0:
        print("\nContext window impact:")
        print(f"  Claude 3.5 Sonnet (200K): {(total_tokens/200000)*100:.1f}%")
        print(f"  GPT-4 (128K): {(total_tokens/128000)*100:.1f}%")
        print(f"  GPT-4o (128K): {(total_tokens/128000)*100:.1f}%")


if __name__ == "__main__":
    analyze_tool_schemas()
