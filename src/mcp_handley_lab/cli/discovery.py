"""Tool discovery for MCP CLI."""
import importlib
from pathlib import Path
from typing import Dict, Any, List, Optional
import click

from .rpc_client import get_tool_client
from .config import get_aliases


def get_available_tools() -> Dict[str, str]:
    """Discover available tools from pyproject.toml script entries."""
    # Use the script entries from pyproject.toml to discover available tools
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


def get_tool_info(tool_name: str, command: str) -> Optional[Dict[str, Any]]:
    """Get detailed information about a tool and its functions."""
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


def get_function_schema(tool_name: str, function_name: str) -> Optional[Dict[str, Any]]:
    """Get the schema for a specific function."""
    tools = get_tool_with_aliases()
    
    if tool_name not in tools:
        return None
    
    tool_info = tools[tool_name]
    functions = tool_info.get("functions", {})
    
    if function_name not in functions:
        return None
    
    return functions[function_name]


def validate_tool_and_function(tool_name: str, function_name: str) -> tuple[bool, Optional[str]]:
    """Validate that a tool and function exist."""
    tools = get_tool_with_aliases()
    
    if tool_name not in tools:
        available_tools = list(tools.keys())
        return False, f"Tool '{tool_name}' not found. Available tools: {', '.join(sorted(available_tools))}"
    
    tool_info = tools[tool_name]
    functions = tool_info.get("functions", {})
    
    if function_name not in functions:
        available_functions = list(functions.keys())
        return False, f"Function '{function_name}' not found in {tool_name}. Available functions: {', '.join(sorted(available_functions))}"
    
    return True, None