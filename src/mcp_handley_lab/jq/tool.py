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


@mcp.tool(description="""Queries JSON data using a jq filter expression.

Data Input: Can be either a JSON string or a file path. If a valid file path, the file is read automatically.

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
def read(file_path: str, filter: str = ".") -> str:
    """Read and pretty-print a JSON file."""
    return _run_jq([filter, file_path])


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
def validate(data: str) -> str:
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
def format(data: str, compact: bool = False, sort_keys: bool = False) -> str:
    """Format JSON data."""
    data_content = _resolve_data(data)
    parsed = json.loads(data_content)
    
    if compact:
        return json.dumps(parsed, separators=(',', ':'), sort_keys=sort_keys)
    else:
        return json.dumps(parsed, indent=2, sort_keys=sort_keys)


@mcp.tool(description="Checks JQ tool server status and command availability. Returns version information and available functions. Use this to verify jq is properly installed and accessible.")
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