"""Code2Prompt tool for codebase flattening and conversion via MCP."""
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_handley_lab.common.process import run_command

mcp = FastMCP("Code2Prompt Tool")


def _run_code2prompt(args: list[str]) -> str:
    """Runs a code2prompt command."""
    cmd = ["code2prompt"] + args
    stdout, stderr = run_command(cmd)
    return stdout.decode("utf-8").strip()


@mcp.tool(
    description="Analyzes a source code directory and generates a structured, token-counted summary, saving it to a file. Useful for preparing a large codebase for LLM analysis. Key inputs are the `path` to the code and an `output_file`. Supports filtering files with `include`/`exclude` patterns and can incorporate a `git diff`. Returns the path to the generated summary file."
)
def generate_prompt(
    path: str,
    output_file: str = "",
    include: list[str] = [],
    exclude: list[str] = [],
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
    template: str = "",
    include_git_diff: bool = False,
    git_diff_branch1: str = "",
    git_diff_branch2: str = "",
    git_log_branch1: str = "",
    git_log_branch2: str = "",
    no_ignore: bool = False,
) -> str:
    """Generate a structured prompt from codebase."""
    # Create output file if not provided
    if not output_file:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as temp_file:
            output_file = temp_file.name

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
        {
            "name": "--full-directory-tree",
            "condition": full_directory_tree,
            "type": "flag",
        },
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
        if (
            arg_def["type"] == "value"
            and arg_def.get("value")
            or arg_def["type"] == "optional_value"
            and arg_def.get("value")
        ):
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
    _run_code2prompt(args)

    # Get file size for reporting
    output_path = Path(output_file)
    file_size = output_path.stat().st_size

    return f"✅ Code2prompt Generation Successful:\n\n- **Output File Path:** `{output_file}`\n- **File Size:** {file_size:,} bytes\n\n💡 **Next Steps:** You can now use this file path (e.g., in a 'files' parameter) with other AI tools like Gemini or OpenAI for comprehensive analysis, without incurring direct context window usage from this response."


@mcp.tool(
    description="Verifies the Code2Prompt tool is operational. Checks for the `code2prompt` CLI and returns its version information and a list of available commands. Use this to confirm the server is ready before generating a codebase summary."
)
def server_info() -> str:
    """Get server status and code2prompt version."""
    version = _run_code2prompt(["--version"])

    return f"""Code2Prompt Tool Server Status
==============================
Status: Connected and ready
Code2Prompt Version: {version}

Available tools:
- generate_prompt: Create structured prompts from codebases (includes git diff options)
- server_info: Get server status"""
