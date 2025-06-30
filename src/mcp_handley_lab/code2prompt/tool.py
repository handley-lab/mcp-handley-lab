"""Code2Prompt tool for codebase analysis via MCP."""
import tempfile
from pathlib import Path
from typing import List, Optional
from mcp.server.fastmcp import FastMCP
from ..common.process import run_command

mcp = FastMCP("Code2Prompt Tool")


async def _run_code2prompt(args: List[str]) -> str:
    """Runs a code2prompt command and raises errors on failure."""
    cmd = ["code2prompt"] + args
    
    try:
        stdout, stderr = await run_command(cmd)
        return stdout.decode('utf-8').strip()
    except RuntimeError as e:
        if "Command failed" in str(e):
            # Extract stderr for better code2prompt error messages
            error_msg = str(e).split(": ", 1)[-1]
            raise ValueError(f"code2prompt error: {error_msg}")
        raise


@mcp.tool(description="""Generates a structured, token-counted summary of a codebase and saves it to a file.

Use this tool to create a summary file of a large codebase for analysis by an LLM. The primary output is a file, and the tool returns the path to this file.

**Key Parameters:**
- `path`: The path to the codebase to analyze.
- `output_file`: The path to save the summary file to. If not provided, a temporary file is created.
- `include`/`exclude`: Glob patterns to filter files (e.g., `["*.py"]`, `["node_modules"]`).
- `output_format`: The format of the summary file ("markdown", "json", "xml", or "plain").
- `include_git_diff`: Set to `True` to include a git diff in the summary. Requires `git_diff_branch1` and `git_diff_branch2`.

**Input/Output:**
- **Input**: A path to a directory.
- **Output**: A string containing the path to the generated summary file.

**Error Handling:**
- Raises `ValueError` if `code2prompt` returns an error.
- Raises `RuntimeError` if the `code2prompt` command is not found.

**Examples:**
```python
# Analyze a Python project and save the summary to a file.
generate_prompt(
    path="/path/to/project",
    include=["*.py"],
    exclude=["__pycache__", "venv"],
    output_file="/tmp/summary.md"
)

# Generate a summary including a git diff.
generate_prompt(
    path="/path/to/project",
    include_git_diff=True,
    git_diff_branch1="main",
    git_diff_branch2="feature-branch",
    output_file="/tmp/diff_summary.md"
)
```""")
async def generate_prompt(
    path: str,
    output_file: Optional[str] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    output_format: str = "markdown",
    line_numbers: bool = False,
    full_directory_tree: bool = False,
    follow_symlinks: bool = False,
    hidden: bool = False,
    no_codeblock: bool = False,
    absolute_paths: bool = False,
    encoding: str = "cl100k",
    tokens: str = "format",
    sort: str = "name_asc",
    include_priority: bool = False,
    template: Optional[str] = None,
    include_git_diff: bool = False,
    git_diff_branch1: Optional[str] = None,
    git_diff_branch2: Optional[str] = None,
    git_log_branch1: Optional[str] = None,
    git_log_branch2: Optional[str] = None,
    no_ignore: bool = False
) -> str:
    """Generate a structured prompt from codebase."""
    # Create output file if not provided
    if not output_file:
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
        output_file = temp_file.name
        temp_file.close()
    
    # Define all arguments in one data structure
    arg_definitions = [
        {"name": "--output-file", "value": output_file, "type": "value"},
        {"name": "--output-format", "value": output_format, "type": "value"},
        {"name": "--encoding", "value": encoding, "type": "value"},
        {"name": "--tokens", "value": tokens, "type": "value"},
        {"name": "--sort", "value": sort, "type": "value"},
        {"name": "--template", "value": template, "type": "optional_value"},
        {"name": "--include-priority", "condition": include_priority, "type": "flag"},
        {"name": "--no-ignore", "condition": no_ignore, "type": "flag"},
        {"name": "--line-numbers", "condition": line_numbers, "type": "flag"},
        {"name": "--full-directory-tree", "condition": full_directory_tree, "type": "flag"},
        {"name": "--follow-symlinks", "condition": follow_symlinks, "type": "flag"},
        {"name": "--hidden", "condition": hidden, "type": "flag"},
        {"name": "--no-codeblock", "condition": no_codeblock, "type": "flag"},
        {"name": "--absolute-paths", "condition": absolute_paths, "type": "flag"},
        {"name": "--diff", "condition": include_git_diff, "type": "flag"},
        {"name": "--include", "values": include or [], "type": "multi_value"},
        {"name": "--exclude", "values": exclude or [], "type": "multi_value"},
    ]

    # Build command args
    args = [path]
    for arg_def in arg_definitions:
        if arg_def["type"] == "value" and arg_def.get("value"):
            args.extend([arg_def["name"], str(arg_def["value"])])
        elif arg_def["type"] == "optional_value" and arg_def.get("value"):
            args.extend([arg_def["name"], str(arg_def["value"])])
        elif arg_def["type"] == "flag" and arg_def.get("condition"):
            args.append(arg_def["name"])
        elif arg_def["type"] == "multi_value":
            for val in arg_def.get("values", []):
                args.extend([arg_def["name"], val])
    
    # Special handling for git branch options
    if git_diff_branch1 and git_diff_branch2:
        args.extend(["--git-diff-branch", git_diff_branch1, git_diff_branch2])
    
    if git_log_branch1 and git_log_branch2:
        args.extend(["--git-log-branch", git_log_branch1, git_log_branch2])
    
    # Run code2prompt
    await _run_code2prompt(args)
    
    # Get file size for reporting
    output_path = Path(output_file)
    file_size = output_path.stat().st_size
    
    return f"✅ Code2prompt Generation Successful:\n\n- **Output File Path:** `{output_file}`\n- **File Size:** {file_size:,} bytes\n\n💡 **Next Steps:** You can now use this file path (e.g., in a 'files' parameter) with other AI tools like Gemini or OpenAI for comprehensive analysis, without incurring direct context window usage from this response."




@mcp.tool(description="Checks the status of the Code2Prompt server and the availability of the `code2prompt` CLI tool. Use this to verify the tool is operational before calling other Code2Prompt functions. Returns version information and available commands.")
async def server_info() -> str:
    """Get server status and code2prompt version."""
    try:
        version = await _run_code2prompt(["--version"])
        
        return f"""Code2Prompt Tool Server Status
==============================
Status: Connected and ready
Code2Prompt Version: {version}

Available tools:
- generate_prompt: Create structured prompts from codebases (includes git diff options)
- server_info: Get server status"""
    except RuntimeError as e:
        raise e