"""JQ tool for JSON manipulation via MCP."""
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_handley_lab.common.process import run_command

mcp = FastMCP("JQ Tool")


def _resolve_data(data: str) -> str:
    """Resolves input, handling strings or file paths.

    Note: While the type signature indicates str, FastMCP may still pass
    parsed JSON objects at runtime. This function handles both cases gracefully.
    """
    # Handle non-string inputs (FastMCP auto-parsing)
    if not isinstance(data, str):
        return json.dumps(data)

    # If it's a string, check if it's a file path
    p = Path(data)
    if p.is_file():
        return p.read_text()

    # Otherwise treat as JSON string
    return data


def _run_jq(args: list[str], input_text: str | None = None) -> str:
    """Runs a jq command."""
    cmd = ["jq"] + args
    input_bytes = input_text.encode("utf-8") if input_text else None

    stdout, stderr = run_command(cmd, input_data=input_bytes)
    return stdout.decode("utf-8").strip()


@mcp.tool(
    description="Applies a `jq` filter expression to JSON data. The `data` can be a JSON string or a file path. The `filter` uses standard jq syntax (e.g., '.users[0].name'). Use `raw_output=True` to get a plain string without quotes, or `compact=True` for single-line JSON output."
)
def query(
    data: str,
    filter: str = ".",
    compact: bool = False,
    raw_output: bool = False,
) -> str:
    """Query JSON data using jq filter."""
    flags = [(compact, "-c"), (raw_output, "-r")]
    args = [flag for condition, flag in flags if condition] + [filter]

    # Resolve data to handle various input types
    data_content = _resolve_data(data)

    # Check if original data is a file path - if so, pass directly to jq for efficiency
    if isinstance(data, str):
        p = Path(data)
        if p.is_file():
            args.append(str(p))
            return _run_jq(args)

    # Otherwise use the resolved content
    return _run_jq(args, input_text=data_content)


@mcp.tool(
    description="Edits a JSON file in-place using a jq transformation `filter` (e.g., '.debug = true'). WARNING: This modifies the original file. A backup file with a .bak extension is created by default; set `backup=False` to disable this."
)
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


@mcp.tool(
    description="Reads and pretty-prints a JSON file with optional jq filtering. Useful for exploring JSON file structure before processing. The `filter` parameter allows extracting specific parts of the file."
)
def read(file_path: str, filter: str = ".") -> str:
    """Read and pretty-print a JSON file."""
    return _run_jq([filter, file_path])


@mcp.tool(
    description="Validates JSON syntax for JSON strings or file paths. Returns 'JSON is valid' for well-formed JSON. Provides detailed error messages with line and character positions for syntax errors."
)
def validate(data: str) -> str:
    """Validate JSON syntax."""
    data_content = _resolve_data(data)

    json.loads(data_content)
    return "JSON is valid"


@mcp.tool(
    description="Formats JSON data for readability or compactness. Takes a JSON string or file path. Use `compact=True` for single-line format or `sort_keys=True` to alphabetically sort object keys."
)
def format(
    data: str,
    compact: bool = False,
    sort_keys: bool = False,
) -> str:
    """Format JSON data."""
    data_content = _resolve_data(data)
    parsed = json.loads(data_content)

    if compact:
        return json.dumps(parsed, separators=(",", ":"), sort_keys=sort_keys)
    else:
        return json.dumps(parsed, indent=2, sort_keys=sort_keys)


@mcp.tool(
    description="Checks the status of the JQ tool server and verifies `jq` command availability. Returns server status, jq version, and list of available tools. Use this to verify the tool is operational before making other requests."
)
def server_info() -> str:
    """Get server status and jq version."""
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
