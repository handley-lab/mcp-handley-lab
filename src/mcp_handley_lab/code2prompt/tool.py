"""Code2Prompt tool for codebase analysis via MCP."""
import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Code2Prompt Tool")


async def _run_code2prompt(args: List[str]) -> str:
    """Runs a code2prompt command and raises errors on failure."""
    try:
        process = await asyncio.create_subprocess_exec(
            "code2prompt", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
    except FileNotFoundError:
        raise RuntimeError("code2prompt command not found")
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        error_msg = stderr.decode('utf-8').strip()
        raise ValueError(f"code2prompt error: {error_msg}")
        
    return stdout.decode('utf-8').strip()


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
    args = [path]
    
    # Create output file if not provided
    if not output_file:
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
        output_file = temp_file.name
        temp_file.close()
    
    args.extend(["--output-file", output_file])
    args.extend(["--output-format", output_format])
    args.extend(["--encoding", encoding])
    args.extend(["--tokens", tokens])
    args.extend(["--sort", sort])
    
    for pattern in include or []:
        args.extend(["--include", pattern])
    for pattern in exclude or []:
        args.extend(["--exclude", pattern])
    
    # Boolean flags
    flags = [
        (include_priority, "--include-priority"),
        (no_ignore, "--no-ignore"),
        (line_numbers, "--line-numbers"),
        (full_directory_tree, "--full-directory-tree"),
        (follow_symlinks, "--follow-symlinks"),
        (hidden, "--hidden"),
        (no_codeblock, "--no-codeblock"),
        (absolute_paths, "--absolute-paths"),
        (include_git_diff, "--diff")
    ]
    args.extend(flag for condition, flag in flags if condition)
    
    if template:
        args.extend(["--template", template])
    
    # Git options
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