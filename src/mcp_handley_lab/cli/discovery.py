"""Tool discovery for MCP CLI."""
import importlib
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import click

from .rpc_client import get_tool_client
from .config import get_aliases


def get_available_tools() -> Dict[str, str]:
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
        "agent": "mcp-agent",
        "email": "mcp-email",
        "github": "mcp-github",
    }
    
    return scripts




def get_tool_info_from_cache() -> Dict[str, Dict[str, Any]]:
    """Load tool information from pre-generated cache."""
    try:
        # Use importlib.resources for proper package data access
        try:
            # Python 3.9+
            from importlib.resources import files
            schema_file = files("mcp_handley_lab") / "tool_schemas.json"
            if schema_file.is_file():
                schema_data = json.loads(schema_file.read_text())
                return schema_data.get("tools", {})
        except ImportError:
            # Python 3.8 fallback
            from importlib.resources import read_text
            schema_text = read_text("mcp_handley_lab", "tool_schemas.json")
            schema_data = json.loads(schema_text)
            return schema_data.get("tools", {})
        
        return {}
    
    except Exception as e:
        click.echo(f"Warning: Failed to load tool cache: {e}", err=True)
        return {}


def get_tool_info(tool_name: str, command: str) -> Optional[Dict[str, Any]]:
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
            "functions": {tool["name"]: tool for tool in tools_list}
        }
        
    except Exception as e:
        click.echo(f"Warning: Failed to get info for {tool_name}: {e}", err=True)
        return None


def discover_all_tools() -> Dict[str, Dict[str, Any]]:
    """Discover all available tools and their capabilities."""
    available_tools = get_available_tools()
    tools_info = {}
    
    for tool_name, command in available_tools.items():
        tool_info = get_tool_info(tool_name, command)
        if tool_info:
            tool_info["display_name"] = tool_name
            tools_info[tool_name] = tool_info
    
    return tools_info


def get_tool_with_aliases() -> Dict[str, Dict[str, Any]]:
    """Get all tools including aliases from configuration."""
    tools = discover_all_tools()
    aliases = get_aliases()
    
    # Add aliases to the tools dict
    for alias, target_tool in aliases.items():
        if target_tool in tools:
            # Create a copy of the target tool with the alias name
            alias_info = tools[target_tool].copy()
            alias_info["display_name"] = alias
            alias_info["is_alias"] = True
            alias_info["target_tool"] = target_tool
            tools[alias] = alias_info
    
    return tools


