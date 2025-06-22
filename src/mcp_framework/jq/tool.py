"""JQ tool for JSON manipulation via MCP."""
import json
import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("JQ Tool")


@mcp.tool(description="Queries JSON data from a string or file using a jq filter expression.")
def query(data: str, filter: str = ".", compact: bool = False, raw_output: bool = False) -> str:
    """Query JSON data using jq filter."""
    # Check if data is a file path
    if not data.startswith('{') and not data.startswith('['):
        path = Path(data)
        if path.exists():
            with open(path) as f:
                data = f.read()
    
    cmd = ["jq"]
    if compact:
        cmd.append("-c")
    if raw_output:
        cmd.append("-r")
    cmd.append(filter)
    
    result = subprocess.run(cmd, input=data, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"jq error: {result.stderr}")
    
    return result.stdout.strip()


@mcp.tool(description="Edits a JSON file in-place using a jq transformation filter.")
def edit(file_path: str, filter: str, backup: bool = True) -> str:
    """Edit a JSON file in-place."""
    path = Path(file_path)
    
    # Create backup if requested
    if backup:
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(path.read_text())
    
    # Apply transformation
    result = subprocess.run(
        ["jq", filter, str(path)],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise ValueError(f"jq error: {result.stderr}")
    
    # Write result back
    path.write_text(result.stdout)
    
    msg = f"Successfully edited {file_path}"
    if backup:
        msg += f" (backup saved to {backup_path})"
    return msg


@mcp.tool(description="Reads and pretty-prints a JSON file, with an optional filter.")
def read(file_path: str, filter: str = ".") -> str:
    """Read and pretty-print a JSON file."""
    result = subprocess.run(
        ["jq", filter, file_path],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise ValueError(f"jq error: {result.stderr}")
    
    return result.stdout.strip()


@mcp.tool(description="Validates the syntax of JSON data from a string or file.")
def validate(data: str) -> str:
    """Validate JSON syntax."""
    # Check if data is a file path
    if not data.startswith('{') and not data.startswith('['):
        path = Path(data)
        if path.exists():
            with open(path) as f:
                data = f.read()
    
    try:
        json.loads(data)
        return "JSON is valid"
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


@mcp.tool(description="Pretty-prints or compacts JSON data from a string or file.")
def format(data: str, compact: bool = False, sort_keys: bool = False) -> str:
    """Format JSON data."""
    # Check if data is a file path
    if not data.startswith('{') and not data.startswith('['):
        path = Path(data)
        if path.exists():
            with open(path) as f:
                data = f.read()
    
    parsed = json.loads(data)
    
    if compact:
        return json.dumps(parsed, separators=(',', ':'), sort_keys=sort_keys)
    else:
        return json.dumps(parsed, indent=2, sort_keys=sort_keys)


@mcp.tool(description="Gets the status of the JQ server and jq CLI availability.")
def server_info() -> str:
    """Get server status and jq version."""
    try:
        result = subprocess.run(["jq", "--version"], capture_output=True, text=True)
        version = result.stdout.strip()
        
        return f"""JQ Tool Server Status
====================
Status: Connected and ready
JQ Version: {version}

Available tools:
- query: Query JSON data with jq filters
- edit: Edit JSON files in-place
- read: Read and pretty-print JSON files
- validate: Validate JSON syntax
- format: Format JSON data
- server_info: Get server status"""
    except FileNotFoundError:
        raise RuntimeError("jq command not found. Please install jq.")