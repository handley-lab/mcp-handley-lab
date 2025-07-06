#!/usr/bin/env python3
"""Generate tool schemas for fast CLI startup."""
import json
import asyncio
import hashlib
from pathlib import Path
from typing import Dict, Any
import importlib


def get_file_hash(file_path: Path) -> str:
    """Get SHA256 hash of a file."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


async def introspect_tool(tool_name: str, module_path: str) -> Dict[str, Any]:
    """Introspect a single tool module."""
    try:
        module = importlib.import_module(module_path)
        if not hasattr(module, 'mcp'):
            return None
        
        mcp_instance = module.mcp
        tools_list = await mcp_instance.list_tools()
        
        functions = {}
        for tool_info in tools_list:
            func_name = tool_info.name
            functions[func_name] = {
                "name": func_name,
                "description": tool_info.description or "No description",
                "inputSchema": tool_info.inputSchema or {},
                "outputSchema": tool_info.outputSchema or {}
            }
        
        # Get source file path and hash
        source_file = Path(module.__file__)
        
        return {
            "name": tool_name,
            "functions": functions,
            "source_file": str(source_file),
            "source_hash": get_file_hash(source_file)
        }
        
    except Exception as e:
        print(f"Warning: Failed to introspect {tool_name}: {e}")
        return None


async def generate_schemas():
    """Generate all tool schemas."""
    
    # Map tool names to their module paths
    tool_modules = {
        "jq": "mcp_handley_lab.jq.tool",
        "vim": "mcp_handley_lab.vim.tool",
        "code2prompt": "mcp_handley_lab.code2prompt.tool",
        "arxiv": "mcp_handley_lab.arxiv.tool",
        "google-calendar": "mcp_handley_lab.google_calendar.tool",
        "gemini": "mcp_handley_lab.llm.gemini.tool",
        "openai": "mcp_handley_lab.llm.openai.tool",
        "claude": "mcp_handley_lab.llm.claude.tool",
        "agent": "mcp_handley_lab.llm.agent.tool",
        "email": "mcp_handley_lab.email.tool",
        "github": "mcp_handley_lab.github.tool",
    }
    
    schema_data = {
        "version": "1.0",
        "generated_at": "2024-01-01T00:00:00Z",  # Will be updated
        "tools": {}
    }
    
    print("Generating tool schemas...")
    
    for tool_name, module_path in tool_modules.items():
        print(f"  Introspecting {tool_name}...")
        tool_info = await introspect_tool(tool_name, module_path)
        
        if tool_info:
            schema_data["tools"][tool_name] = tool_info
            print(f"    ✓ Found {len(tool_info['functions'])} functions")
        else:
            print(f"    ✗ Failed to introspect")
    
    # Update generation timestamp
    from datetime import datetime
    schema_data["generated_at"] = datetime.utcnow().isoformat() + "Z"
    
    # Write to package data directory
    package_dir = Path(__file__).parent.parent / "src" / "mcp_handley_lab"
    schema_file = package_dir / "tool_schemas.json"
    
    with open(schema_file, "w") as f:
        json.dump(schema_data, f, indent=2)
    
    print(f"\nSchema file generated: {schema_file}")
    print(f"Total tools: {len(schema_data['tools'])}")


if __name__ == "__main__":
    asyncio.run(generate_schemas())