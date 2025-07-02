"""JQ tool for JSON manipulation via MCP."""
import asyncio
import json
from pathlib import Path
from typing import Union
from pydantic import constr
from mcp.server.fastmcp import FastMCP
from ..common.process import run_command
from ..common.exceptions import UserCancelledError

mcp = FastMCP("JQ Tool")


def _resolve_data(data: Union[str, dict, list]) -> str:
    """Resolves input, handling strings, dicts, lists, or file paths.
    
    This function gracefully handles cases where FastMCP auto-parses JSON strings
    into dictionaries or lists, converting them back to JSON strings as needed.
    """
    # If it's a dict or list (FastMCP parsed JSON), convert back to string
    if isinstance(data, (dict, list)):
        return json.dumps(data)
    
    # If it's a string, check if it's a file path
    if isinstance(data, str):
        p = Path(data)
        if p.is_file():
            return p.read_text()
        return data
    
    # Fallback: convert to string
    return str(data)


async def _run_jq(args: list[str], input_text: str | None = None) -> str:
    """Runs a jq command and raises errors on failure."""
    cmd = ["jq"] + args
    input_bytes = input_text.encode('utf-8') if input_text else None
    
    try:
        stdout, stderr = await run_command(cmd, input_data=input_bytes)
        return stdout.decode('utf-8').strip()
    except asyncio.CancelledError:
        raise UserCancelledError("JQ command was cancelled by user")
    except RuntimeError as e:
        if "Command failed" in str(e):
            # Extract stderr for better jq error messages
            error_msg = str(e).split(": ", 1)[-1]
            raise ValueError(f"jq error: {error_msg}")
        raise


@mcp.tool(description="""Queries JSON data using a jq filter expression.

Data Input: Accepts JSON strings, parsed objects/arrays, or file paths. Automatically handles FastMCP's JSON parsing and file path detection.

Filter Parameter: Defaults to "." (identity filter). Use standard jq syntax:
- `.field` - Extract field value
- `.[]` - Array elements
- `.[0]` - First array element  
- `.field1.field2` - Nested field access
- `select(.field > 5)` - Filter with condition

Output Options:
- `compact`: Single-line compressed JSON output (removes whitespace)
- `raw_output`: Raw string values without JSON quotes (useful for extracting plain text)

Error Handling:
- Raises ValueError for invalid jq filter syntax
- Raises RuntimeError if jq command not found or file read errors
- File paths are validated automatically

Examples:
```python
# Query from JSON string
query('{"users": [{"name": "Alice", "age": 30}]}', '.users[0].name')
# Returns: "Alice"

# Query from file
query('/path/to/data.json', '.users | length')
# Returns: 2

# Get raw string output
query('{"message": "Hello World"}', '.message', raw_output=True)
# Returns: Hello World (not "Hello World")

# Compact output
query('{"a": 1, "b": 2}', '.', compact=True)
# Returns: {"a":1,"b":2}
```""")
async def query(data: Union[constr(min_length=1), dict, list], filter: str = ".", compact: bool = False, raw_output: bool = False) -> str:
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
            return await _run_jq(args)
    
    # Otherwise use the resolved content
    return await _run_jq(args, input_text=data_content)


@mcp.tool(description="""Edits a JSON file in-place using a jq transformation filter.

WARNING: Modifies the original file. Backup is created by default (.bak extension).

Error Handling:
- Raises ValueError for invalid jq transformation syntax
- Raises FileNotFoundError if input file doesn't exist
- Raises PermissionError if file cannot be written
- Backup creation may fail silently if disk space insufficient

Filter must be a transformation expression that modifies the data:
- `.field = "new_value"` - Set field value
- `.items += [{"new": "item"}]` - Add to array
- `del(.field)` - Delete field
- `.[] |= select(.age > 18)` - Filter array elements

Examples:
```python
# Update a field
edit('/path/config.json', '.debug = true')

# Add new item to array
edit('/path/users.json', '.users += [{"name": "Bob", "age": 25}]')

# Remove field
edit('/path/data.json', 'del(.temp_field)')

# Transform all array items
edit('/path/products.json', '.products[].price *= 1.1')
```""")
async def edit(file_path: constr(min_length=1), filter: constr(min_length=1), backup: bool = True) -> str:
    """Edit a JSON file in-place."""
    
    path = Path(file_path)
    
    # Create backup if requested
    if backup:
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(path.read_text())
    
    # Apply transformation
    result = await _run_jq([filter, str(path)])
    
    # Write result back
    path.write_text(result)
    
    msg = f"Successfully edited {file_path}"
    if backup:
        msg += f" (backup saved to {backup_path})"
    return msg


@mcp.tool(description="""Reads and pretty-prints a JSON file with optional jq filtering.

Useful for exploring JSON file structure before processing. The `filter` parameter allows extracting specific parts.

Examples:
```python
# Read entire file
read('/path/config.json')

# Read specific section
read('/path/data.json', '.users')

# Read with transformation
read('/path/products.json', '.items | length')
```""")
async def read(file_path: str, filter: str = ".") -> str:
    """Read and pretty-print a JSON file."""
    return await _run_jq([filter, file_path])


@mcp.tool(description="""Validates JSON syntax for strings or files.

Returns "JSON is valid" for well-formed JSON, raises ValueError with specific error for invalid JSON.

Error Details:
- Provides line and character position for syntax errors
- Identifies specific JSON parsing issues (missing quotes, brackets, etc.)
- Works with both file paths and direct JSON strings

Examples:
```python
# Validate JSON string
validate('{"valid": true}')
# Returns: "JSON is valid"

# Validate file
validate('/path/data.json')

# Invalid JSON raises error
validate('{invalid: json}')
# Raises: ValueError("Invalid JSON: ...")
```""")
async def validate(data: Union[constr(min_length=1), dict, list]) -> str:
    """Validate JSON syntax."""
    data_content = _resolve_data(data)
    
    try:
        json.loads(data_content)
        return "JSON is valid"
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


@mcp.tool(description="""Formats JSON data for readability or compactness.

Data Input: JSON string or file path (auto-detected).

Formatting Options:
- `compact`: Single-line format (removes indentation and whitespace)
- `sort_keys`: Alphabetically sort object keys at all levels

Error Handling:
- Raises ValueError for malformed JSON input
- Raises FileNotFoundError if file path provided but doesn't exist
- Returns formatted JSON or raises specific parsing errors

Examples:
```python
# Pretty-print JSON
format('{"b":2,"a":1}')
# Returns:
# {
#   "b": 2,
#   "a": 1
# }

# Compact format with sorted keys
format('{"b":2,"a":1}', compact=True, sort_keys=True)
# Returns: {"a":1,"b":2}

# Format file
format('/path/data.json', sort_keys=True)
```""")
async def format(data: Union[constr(min_length=1), dict, list], compact: bool = False, sort_keys: bool = False) -> str:
    """Format JSON data."""
    data_content = _resolve_data(data)
    parsed = json.loads(data_content)
    
    if compact:
        return json.dumps(parsed, separators=(',', ':'), sort_keys=sort_keys)
    else:
        return json.dumps(parsed, indent=2, sort_keys=sort_keys)


@mcp.tool(description="""Checks the status of the JQ tool server and the availability of the `jq` command.

Use this to verify that the tool is operational before making other requests.

**Input/Output:**
- **Input**: None.
- **Output**: A string containing the server status, `jq` version, and a list of available tools.

**Error Handling:**
- Raises `RuntimeError` if the `jq` command is not found.

**Examples:**
```python
# Check the server status.
server_info()
```""")
async def server_info() -> str:
    """Get server status and jq version."""
    try:
        version = await _run_jq(["--version"])
        
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