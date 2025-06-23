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


@mcp.tool(description="Generates a structured, token-counted summary of a codebase and saves it to a file. This allows LLMs to process large codebases efficiently by referencing the summary file, avoiding excessive context window usage. Use this tool when you need to analyze a codebase that is too large to fit directly in the LLM's context window. The output file path should then be used as a 'file' input to an LLM tool. Includes options for filtering files, controlling output format, and incorporating git diff information.")
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
    
    if include:
        for pattern in include:
            args.extend(["--include", pattern])
    
    if exclude:
        for pattern in exclude:
            args.extend(["--exclude", pattern])
    
    if include_priority:
        args.append("--include-priority")
    
    if template:
        args.extend(["--template", template])
    
    if no_ignore:
        args.append("--no-ignore")
    
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
    
    # Add git options (can be used independently or together)
    if include_git_diff:
        args.append("--diff")
    
    if git_diff_branch1 and git_diff_branch2:
        args.extend(["--git-diff-branch", git_diff_branch1, git_diff_branch2])
    
    if git_log_branch1 and git_log_branch2:
        args.extend(["--git-log-branch", git_log_branch1, git_log_branch2])
    
    # Run code2prompt
    _run_code2prompt(args)
    
    # Get file size for reporting
    output_path = Path(output_file)
    file_size = output_path.stat().st_size
    
    return f"✅ Code2prompt Generation Successful:\n\n- **Output File Path:** `{output_file}`\n- **File Size:** {file_size:,} bytes\n\n💡 **Next Steps:** You can now use this file path (e.g., in a 'files' parameter) with other AI tools like Gemini or OpenAI for comprehensive analysis, without incurring direct context window usage from this response."




@mcp.tool(description="Checks the status of the Code2Prompt server and the availability of the `code2prompt` CLI tool. Use this to verify the tool is operational before calling other Code2Prompt functions.")
def server_info() -> str:
    """Get server status and code2prompt version."""
    try:
        version = _run_code2prompt(["--version"])
        
        return f"""Code2Prompt Tool Server Status
==============================
Status: Connected and ready
Code2Prompt Version: {version}

Available tools:
- generate_prompt: Create structured prompts from codebases (includes git diff options)
- server_info: Get server status"""
    except RuntimeError as e:
        raise e