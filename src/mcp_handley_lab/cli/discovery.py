"""Tool discovery for MCP CLI."""

import json
from typing import Any

import click

from .rpc_client import get_tool_client


def get_available_tools() -> dict[str, str]:
    """Get a list of available tool commands."""
    # Map of tool names to their script entry commands
    scripts = {
        "jq": "mcp-jq",
        "vim": "mcp-vim",
        "code2prompt": "mcp-code2prompt",
        "arxiv": "mcp-arxiv",
        "google-calendar": "mcp-google-calendar",
        "gemini": "mcp-gemini",
        "openai": "mcp-openai",
        "claude": "mcp-claude",
        "google-maps": "mcp-google-maps",
        "email": "mcp-email",
        "github": "mcp-github",
        "notes": "mcp-notes",
    }

    return scripts


def get_tool_info_from_cache() -> dict[str, dict[str, Any]]:
    """Load tool information from pre-generated cache."""
    try:
        from importlib.resources import files

        schema_file = files("mcp_handley_lab") / "tool_schemas.json"
        if schema_file.is_file():
            return json.loads(schema_file.read_text()).get("tools", {})
        return {}
    except Exception as e:
        click.echo(f"Warning: Failed to load tool cache: {e}", err=True)
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
    try:
        client = get_tool_client(tool_name, command)
        tools_list = client.list_tools()

        if not tools_list:
            return None

        return {
            "name": tool_name,
            "command": command,
            "functions": {tool["name"]: tool for tool in tools_list},
        }

    except Exception as e:
        click.echo(f"Warning: Failed to get info for {tool_name}: {e}", err=True)
        return None
