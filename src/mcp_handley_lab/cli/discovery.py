"""Tool discovery for MCP CLI."""

import json
from typing import Any

from mcp_handley_lab.cli.rpc_client import get_tool_client


def get_available_tools() -> dict[str, str]:
    """Get a list of available tool commands."""
    # Map of tool names to their script entry commands
    scripts = {
        "jq": "mcp-jq",
        "vim": "mcp-vim",
        "code2prompt": "mcp-code2prompt",
        "arxiv": "mcp-arxiv",
        "google-calendar": "mcp-google-calendar",
        "google-maps": "mcp-google-maps",
        "email": "mcp-email",
        "github": "mcp-github",
        "notes": "mcp-notes",
        # LLM tools
        "llm-chat": "mcp-llm-chat",
        "llm-image": "mcp-llm-image",
        "llm-embeddings": "mcp-llm-embeddings",
        "llm-ocr": "mcp-llm-ocr",
        "llm-audio": "mcp-llm-audio",
        "llm-models": "mcp-llm-models",
    }

    return scripts


def get_tool_info_from_cache() -> dict[str, dict[str, Any]]:
    """Load tool information from pre-generated cache."""
    from importlib.resources import files

    schema_file = files("mcp_handley_lab") / "tool_schemas.json"
    try:
        return json.loads(schema_file.read_text()).get("tools", {})
    except FileNotFoundError:
        return {}


def get_tool_info(tool_name: str, command: str) -> dict[str, Any] | None:
    """Get detailed information about a tool - try cache first, fallback to RPC introspection."""

    # Try cached schema first (instant)
    cached_tools = get_tool_info_from_cache()
    if tool_name in cached_tools:
        tool_info = cached_tools[tool_name].copy()
        tool_info["command"] = command
        return tool_info

    # Fallback to RPC introspection
    client = get_tool_client(tool_name, command)
    tools_list = client.list_tools()

    if not tools_list:
        return None

    return {
        "name": tool_name,
        "command": command,
        "functions": {tool["name"]: tool for tool in tools_list},
    }
