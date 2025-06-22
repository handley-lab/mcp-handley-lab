"""Code2Prompt tool for codebase analysis via MCP."""
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Code2Prompt Tool")


def _run_code2prompt(args: List[str]) -> str:
    """Runs a code2prompt command and handles errors."""
    command = ["code2prompt"] + args
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            raise ValueError(f"code2prompt error: {result.stderr.strip()}")
        return result.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError("code2prompt command not found. Please install code2prompt.")


@mcp.tool(description="Creates a structured, token-counted summary of a codebase and saves it to a file.")
def generate_prompt(
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
    sort: str = "name_asc"
) -> str:
    """Generate a structured prompt from codebase."""
    args = [path]
    
    # Create output file if not provided
    if not output_file:
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
        output_file = temp_file.name
        temp_file.close()
    
    args.extend(["--output", output_file])
    args.extend(["--output-format", output_format])
    args.extend(["--encoding", encoding])
    args.extend(["--tokens", tokens])
    args.extend(["--sort", sort])
    
    if include:
        for pattern in include:
            args.extend(["--include", pattern])
    
    if exclude:
        for pattern in exclude:
            args.extend(["--exclude", pattern])
    
    if line_numbers:
        args.append("--line-numbers")
    
    if full_directory_tree:
        args.append("--full-directory-tree")
    
    if follow_symlinks:
        args.append("--follow-symlinks")
    
    if hidden:
        args.append("--hidden")
    
    if no_codeblock:
        args.append("--no-codeblock")
    
    if absolute_paths:
        args.append("--absolute-paths")
    
    # Run code2prompt
    _run_code2prompt(args)
    
    # Get file size for reporting
    output_path = Path(output_file)
    file_size = output_path.stat().st_size
    
    return f"✅ Code2prompt Generation Successful:\n\n- **Output File Path:** `{output_file}`\n- **File Size:** {file_size:,} bytes\n\n💡 **Next Steps:** You can now use this file path (e.g., in a 'files' parameter) with other AI tools like Gemini or OpenAI for comprehensive analysis, without incurring direct context window usage from this response."


@mcp.tool(description="Performs a quick analysis of a codebase directory, returning a text-based directory tree and token count.")
def analyze_codebase(
    path: str,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    hidden: bool = False,
    encoding: str = "cl100k"
) -> str:
    """Analyze codebase structure and get directory tree with token counts."""
    args = [path, "--analyze"]
    args.extend(["--encoding", encoding])
    
    if include:
        for pattern in include:
            args.extend(["--include", pattern])
    
    if exclude:
        for pattern in exclude:
            args.extend(["--exclude", pattern])
    
    if hidden:
        args.append("--hidden")
    
    return _run_code2prompt(args)


@mcp.tool(description="Generates a structured text representation of git changes from a local repository path.")
def git_diff(
    path: str,
    mode: str = "diff",
    branch1: Optional[str] = None,
    branch2: Optional[str] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None
) -> str:
    """Generate git diff or branch comparison using code2prompt."""
    args = [path, "--git-diff"]
    
    if mode == "branch_diff" and branch1 and branch2:
        args.extend(["--git-diff-branch", f"{branch1}..{branch2}"])
    elif mode == "branch_log" and branch1 and branch2:
        args.extend(["--git-log", f"{branch1}..{branch2}"])
    
    if include:
        for pattern in include:
            args.extend(["--include", pattern])
    
    if exclude:
        for pattern in exclude:
            args.extend(["--exclude", pattern])
    
    # Create temporary output file for git diff
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
    output_file = temp_file.name
    temp_file.close()
    
    args.extend(["--output", output_file])
    
    _run_code2prompt(args)
    
    output_path = Path(output_file)
    file_size = output_path.stat().st_size
    
    return f"✅ Git Diff Generation Successful:\n\n- **Output File Path:** `{output_file}`\n- **File Size:** {file_size:,} bytes\n- **Mode:** {mode}\n\n💡 **Next Steps:** You can now analyze the git changes from this file."


@mcp.tool(description="Checks the status of the code2prompt server and verifies that the CLI tool is installed and available.")
def server_info() -> str:
    """Get server status and code2prompt version."""
    try:
        version = _run_code2prompt(["--version"])
        
        return f"""Code2Prompt Tool Server Status
==============================
Status: Connected and ready
Code2Prompt Version: {version}

Available tools:
- generate_prompt: Create structured prompts from codebases
- analyze_codebase: Quick codebase analysis with token counts
- git_diff: Generate git diffs and comparisons
- server_info: Get server status"""
    except RuntimeError as e:
        raise e