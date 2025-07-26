"""Code2Prompt tool for codebase flattening and conversion via MCP."""

from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.shared.models import ServerInfo


class GenerationResult(BaseModel):
    """Result of code2prompt generation."""

    message: str = Field(
        ...,
        description="A confirmation message indicating the result of the generation.",
    )
    output_file_path: str = Field(
        ..., description="The absolute path to the generated prompt summary file."
    )
    file_size_bytes: int = Field(
        ..., description="The size of the generated file in bytes."
    )


mcp = FastMCP("Code2Prompt Tool")


def _run_code2prompt(args: list[str]) -> str:
    """Runs a code2prompt command."""
    cmd = ["code2prompt"] + args
    stdout, stderr = run_command(cmd)
    return stdout.decode("utf-8").strip()


@mcp.tool(
    description="Generates a structured, token-counted summary of a codebase. Supports include/exclude, git diffs, and formatting options."
)
def generate_prompt(
    path: str = Field(..., description="The source directory or file path to analyze."),
    output_file: str = Field(
        ..., description="The path where the generated summary file will be saved."
    ),
    include: list[str] = Field(
        default_factory=list,
        description="A list of glob patterns to explicitly include files (e.g., '*.py', 'src/**/*').",
    ),
    exclude: list[str] = Field(
        default_factory=list,
        description="A list of glob patterns to exclude files (e.g., '*_test.py', 'dist/*').",
    ),
    output_format: str = Field(
        "markdown",
        description="The output format for the summary. Valid options include 'markdown', 'json'.",
    ),
    line_numbers: bool = Field(
        False, description="Include line numbers in code blocks."
    ),
    full_directory_tree: bool = Field(
        False, description="Display full directory tree including empty directories."
    ),
    follow_symlinks: bool = Field(
        False, description="Follow symbolic links when scanning."
    ),
    hidden: bool = Field(False, description="Include hidden files and directories."),
    no_codeblock: bool = Field(
        False, description="Omit markdown code block fences around file content."
    ),
    absolute_paths: bool = Field(
        False, description="Use absolute paths instead of relative paths."
    ),
    encoding: str = Field(
        "cl100k",
        description="The name of the tiktoken encoding to use for token counting (e.g., 'cl100k', 'p50k_base').",
    ),
    tokens: str = Field(
        "format",
        description="Determines how token counts are displayed. Valid options are 'format', 'only', 'none'.",
    ),
    sort: str = Field(
        "name_asc",
        description="The sorting order for files. Options: 'name_asc', 'name_desc', 'tokens_asc', 'tokens_desc'.",
    ),
    include_priority: bool = Field(
        False, description="'include' patterns take priority over .gitignore rules."
    ),
    template: str = Field(
        "", description="Path to a custom Jinja2 template file to format the output."
    ),
    include_git_diff: bool = Field(
        False, description="Generate content from git diff instead of full directory."
    ),
    git_diff_branch1: str = Field(
        "",
        description="The first branch or commit for git diff comparison. Requires git_diff_branch2.",
    ),
    git_diff_branch2: str = Field(
        "",
        description="The second branch or commit for git diff comparison. Requires git_diff_branch1.",
    ),
    git_log_branch1: str = Field(
        "",
        description="The first branch or commit for git log comparison. Requires git_log_branch2.",
    ),
    git_log_branch2: str = Field(
        "",
        description="The second branch or commit for git log comparison. Requires git_log_branch1.",
    ),
    no_ignore: bool = Field(
        False, description="Disable .gitignore and .c2pignore file processing."
    ),
) -> GenerationResult:
    """Generate a structured prompt from codebase."""
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

    if git_diff_branch1 and git_diff_branch2:
        args.extend(["--git-diff-branch", git_diff_branch1, git_diff_branch2])

    if git_log_branch1 and git_log_branch2:
        args.extend(["--git-log-branch", git_log_branch1, git_log_branch2])

    _run_code2prompt(args)

    output_path = Path(output_file)
    file_size = output_path.stat().st_size

    return GenerationResult(
        message="Code2prompt Generation Successful",
        output_file_path=output_file,
        file_size_bytes=file_size,
    )


@mcp.tool(
    description="Checks the status of the Code2Prompt server and its CLI dependency. Returns version info and available functions."
)
def server_info() -> ServerInfo:
    """Get server status and code2prompt version."""
    version = _run_code2prompt(["--version"])

    return ServerInfo(
        name="Code2Prompt Tool",
        version=version.strip(),
        status="active",
        capabilities=["generate_prompt", "server_info"],
        dependencies={"code2prompt": version.strip()},
    )
