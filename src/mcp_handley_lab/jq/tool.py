"""JQ tool for JSON manipulation via MCP."""
import json
import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("JQ Tool")


def _resolve_data(data_or_path: str) -> str:
    """Resolves input, reading from a file if it exists, otherwise returning the data."""
    p = Path(data_or_path)
    if p.is_file():
        return p.read_text()
    return data_or_path


def _run_jq(args: list[str], input_text: str | None = None) -> str:
    """Runs a jq command and handles errors."""
    command = ["jq"] + args
    try:
        result = subprocess.run(
            command,
            input=input_text,
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            raise ValueError(f"jq error: {result.stderr.strip()}")
        return result.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError("jq command not found. Please install jq.")


@mcp.tool(description="Queries JSON data using a jq filter expression. The `data` parameter can be either a JSON string or a path to a JSON file. If `data` is a valid file path, the file will be read; otherwise, `data` is treated as a JSON string. Use `compact` for compressed output and `raw_output` to output raw string values instead of JSON strings.")
def query(data: str, filter: str = ".", compact: bool = False, raw_output: bool = False) -> str:
    """Query JSON data using jq filter."""
    args = []
    if compact:
        args.append("-c")
    if raw_output:
        args.append("-r")
    args.append(filter)
    
    # Check if data is a file path - if so, pass directly to jq for efficiency
    p = Path(data)
    if p.is_file():
        args.append(str(p))
        return _run_jq(args)
    else:
        return _run_jq(args, input_text=data)


@mcp.tool(description="Edits a JSON file *in-place* using a jq filter. The `filter` should perform a transformation on the JSON data. A backup of the original file is created if `backup` is True (default). Use this to modify JSON files directly.")
def edit(file_path: str, filter: str, backup: bool = True) -> str:
    """Edit a JSON file in-place."""
    path = Path(file_path)
    
    # Create backup if requested
    if backup:
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(path.read_text())
    
    # Apply transformation
    result = _run_jq([filter, str(path)])
    
    # Write result back
    path.write_text(result)
    
    msg = f"Successfully edited {file_path}"
    if backup:
        msg += f" (backup saved to {backup_path})"
    return msg


@mcp.tool(description="Reads a JSON file and pretty-prints its contents, optionally filtered by a jq expression. This is helpful for LLMs to process and understand JSON file structures.")
def read(file_path: str, filter: str = ".") -> str:
    """Read and pretty-print a JSON file."""
    return _run_jq([filter, file_path])


@mcp.tool(description="Validates the syntax of JSON data. The `data` parameter can be a JSON string or a path to a JSON file. Use this to check if JSON data is well-formed before processing it.")
def validate(data: str) -> str:
    """Validate JSON syntax."""
    data_content = _resolve_data(data)
    
    try:
        json.loads(data_content)
        return "JSON is valid"
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


@mcp.tool(description="Formats JSON data, either compacting or pretty-printing it. The `data` parameter can be a JSON string or a file path. Useful for making JSON data more readable or for reducing its size.")
def format(data: str, compact: bool = False, sort_keys: bool = False) -> str:
    """Format JSON data."""
    data_content = _resolve_data(data)
    parsed = json.loads(data_content)
    
    if compact:
        return json.dumps(parsed, separators=(',', ':'), sort_keys=sort_keys)
    else:
        return json.dumps(parsed, indent=2, sort_keys=sort_keys)


@mcp.tool(description="Checks the status of the JQ server and the availability of the `jq` command-line tool. Use this to verify the tool is operational before calling other JQ functions.")
def server_info() -> str:
    """Get server status and jq version."""
    try:
        version = _run_jq(["--version"])
        
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
    except RuntimeError as e:
        raise e