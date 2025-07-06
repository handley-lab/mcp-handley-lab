"""Vim tool for interactive text editing via MCP."""
import difflib
import os
import subprocess
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Vim Tool")


def _run_vim(file_path: str, vim_args: list[str] = None) -> None:
    """Run vim directly using subprocess."""
    vim_cmd = ["vim"] + (vim_args or []) + [file_path]

    # Check if we have a TTY - if yes, run vim directly
    if os.isatty(0):  # stdin is a tty
        subprocess.run(vim_cmd, check=True)
    else:
        # No TTY available - this will happen in non-interactive environments
        # Just run vim anyway and let it handle the situation
        subprocess.run(
            vim_cmd,
            capture_output=True,
            check=True,
        )


def _handle_instructions_and_content(
    temp_path: str, suffix: str, instructions: str, initial_content: str
) -> None:
    """Write content with optional instructions to temp file."""
    comment_char = "#" if suffix in [".py", ".sh", ".yaml", ".yml"] else "//"

    with open(temp_path, "w") as f:
        if instructions:
            for line in instructions.strip().split("\n"):
                f.write(f"{comment_char} {line}\n")
            f.write(f"{comment_char} {'='*60}\n\n")
        f.write(initial_content)


def _strip_instructions(content: str, instructions: str, suffix: str) -> str:
    """Remove instruction comments from content."""
    if not instructions:
        return content

    comment_char = "#" if suffix in [".py", ".sh", ".yaml", ".yml"] else "//"
    lines = content.split("\n")

    for i, line in enumerate(lines):
        if line.strip() == comment_char + " " + "=" * 60:
            return "\n".join(lines[i + 2 :])  # Skip separator and blank line
    return content


@mcp.tool(
    description="Opens Vim to edit content in a temporary file. Provide initial `content` and optional `instructions`. Set `file_extension` for syntax highlighting. Returns a diff of changes by default or full content if `show_diff=False`."
)
def prompt_user_edit(
    content: str,
    file_extension: str = ".txt",
    instructions: str = "",
    show_diff: bool = True,
    keep_file: bool = False,
) -> str:
    """Open vim for editing provided content."""
    # Create temp file with proper extension
    suffix = file_extension if file_extension.startswith(".") else f".{file_extension}"
    fd, temp_path = tempfile.mkstemp(suffix=suffix, text=True)

    try:
        # Write initial content with optional instructions
        os.close(fd)  # Close file descriptor so we can use regular file operations
        _handle_instructions_and_content(temp_path, suffix, instructions, content)

        # Open vim
        _run_vim(temp_path)

        # Read edited content
        with open(temp_path) as f:
            edited_content = f.read()

        # Remove instruction comments if present
        edited_content = _strip_instructions(edited_content, instructions, suffix)

        if show_diff:
            # Calculate diff
            original_lines = content.splitlines(keepends=True)
            edited_lines = edited_content.splitlines(keepends=True)

            diff = list(
                difflib.unified_diff(
                    original_lines, edited_lines, fromfile="original", tofile="edited"
                )
            )

            if diff:
                added = sum(
                    1
                    for line in diff
                    if line.startswith("+") and not line.startswith("+++")
                )
                removed = sum(
                    1
                    for line in diff
                    if line.startswith("-") and not line.startswith("---")
                )

                result = (
                    f"Changes made: {added} lines added, {removed} lines removed\n\n"
                )
                result += "".join(diff)
            else:
                result = "No changes made"
        else:
            result = edited_content

        return result

    finally:
        if not keep_file:
            os.unlink(temp_path)


@mcp.tool(
    description="Opens Vim to create new content from scratch with optional `initial_content` and `instructions`. Creates a temporary file, opens Vim for editing, then returns the final content. Instructions are shown as comments and automatically stripped."
)
def quick_edit(
    file_extension: str = ".txt",
    instructions: str | None = None,
    initial_content: str = "",
) -> str:
    """Open vim for creating new content."""
    # Create temp file
    suffix = file_extension if file_extension.startswith(".") else f".{file_extension}"
    fd, temp_path = tempfile.mkstemp(suffix=suffix, text=True)

    try:
        # Write initial content with optional instructions
        os.close(fd)  # Close file descriptor so we can use regular file operations
        _handle_instructions_and_content(
            temp_path, suffix, instructions, initial_content
        )

        # Open vim
        _run_vim(temp_path)

        # Read content
        with open(temp_path) as f:
            content = f.read()

        # Remove instruction comments if present
        content = _strip_instructions(content, instructions, suffix)

        return content

    finally:
        os.unlink(temp_path)


@mcp.tool(
    description="Opens an existing file in Vim for interactive editing. If `instructions` are provided, the user must first view them in a read-only buffer before proceeding. Creates a backup (.bak) by default. Returns a diff of the changes."
)
def open_file(
    file_path: str,
    instructions: str = "",
    show_diff: bool = True,
    backup: bool = True,
) -> str:
    """Open existing file in vim."""
    path = Path(file_path)

    # Read original content
    original_content = path.read_text()

    # Create backup if requested
    if backup:
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(original_content)

    # If instructions provided, show them in a temp file first
    if instructions:
        fd, inst_path = tempfile.mkstemp(suffix=".txt", text=True)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(f"INSTRUCTIONS FOR EDITING: {file_path}\n")
                f.write("=" * 60 + "\n")
                f.write(instructions + "\n")
                f.write("=" * 60 + "\n")
                f.write("\nPress any key to continue to the file...")

            # Show instructions
            _run_vim(inst_path, ["-R"])
        finally:
            os.unlink(inst_path)

    # Open the actual file
    _run_vim(str(path))

    # Read edited content
    edited_content = path.read_text()

    if show_diff:
        # Calculate diff
        original_lines = original_content.splitlines(keepends=True)
        edited_lines = edited_content.splitlines(keepends=True)

        diff = list(
            difflib.unified_diff(
                original_lines,
                edited_lines,
                fromfile=f"{file_path}.original",
                tofile=file_path,
            )
        )

        if diff:
            added = sum(
                1
                for line in diff
                if line.startswith("+") and not line.startswith("+++")
            )
            removed = sum(
                1
                for line in diff
                if line.startswith("-") and not line.startswith("---")
            )

            result = f"File edited: {file_path}\n"
            result += f"Changes: {added} lines added, {removed} lines removed\n"
            if backup:
                result += f"Backup saved to: {backup_path}\n"
            result += "\n" + "".join(diff)
        else:
            result = f"No changes made to {file_path}"
    else:
        result = f"File edited: {file_path}"
        if backup:
            result += f"\nBackup saved to: {backup_path}"

    return result


@mcp.tool(
    description="Checks Vim Tool server status and vim command availability. Returns vim version information and available tool functions. Use this to verify vim is installed and accessible before using other vim tools."
)
def server_info() -> str:
    """Get server status and vim version."""
    try:
        result = subprocess.run(
            ["vim", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        raise RuntimeError("vim command not found") from None

    # Extract first line of version info
    version_line = result.stdout.split("\n")[0]

    return f"""Vim Tool Server Status
=====================
Status: Connected and ready
Vim Version: {version_line}

Available tools:
- prompt_user_edit: Edit provided content in vim
- quick_edit: Create new content in vim
- open_file: Edit existing files in vim
- server_info: Get server status"""
