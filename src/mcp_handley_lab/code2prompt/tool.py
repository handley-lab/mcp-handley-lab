"""Code2Prompt tool for codebase flattening and conversion via MCP."""
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.shared.models import ServerInfo


class GenerationResult(BaseModel):
    """Result of code2prompt generation."""

    message: str
    output_file_path: str
    file_size_bytes: int


mcp = FastMCP("Code2Prompt Tool")


def _run_code2prompt(args: list[str]) -> str:
    """Runs a code2prompt command."""
    cmd = ["code2prompt"] + args
    stdout, stderr = run_command(cmd)
    return stdout.decode("utf-8").strip()


@mcp.tool(
    description="Generates a structured, token-counted summary of a source code directory, saving it to a file. Supports include/exclude patterns and git diffs. Returns the path to the generated summary."
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
) -> GenerationResult:
    """Generate a structured prompt from codebase."""
    if not output_file:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as temp_file:
            output_file = temp_file.name
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
