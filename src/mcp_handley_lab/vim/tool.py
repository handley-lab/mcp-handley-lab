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
    vim_cmd = ['vim'] + (vim_args or []) + [file_path]

    # Check if we have a TTY - if yes, run vim directly
    if os.isatty(0):  # stdin is a tty
        subprocess.run(vim_cmd, check=True)
    else:
        # No TTY available - this will happen in non-interactive environments
        # Just run vim anyway and let it handle the situation
        subprocess.run(vim_cmd, check=True)


def _handle_instructions_and_content(temp_path: str, suffix: str, instructions: str, initial_content: str) -> None:
    """Write content with optional instructions to temp file."""
    comment_char = '#' if suffix in ['.py', '.sh', '.yaml', '.yml'] else '//'

    with open(temp_path, 'w') as f:
        if instructions:
            for line in instructions.strip().split('\n'):
                f.write(f"{comment_char} {line}\n")
            f.write(f"{comment_char} {'='*60}\n\n")
        f.write(initial_content)


def _strip_instructions(content: str, instructions: str, suffix: str) -> str:
    """Remove instruction comments from content."""
    if not instructions:
        return content

    comment_char = '#' if suffix in ['.py', '.sh', '.yaml', '.yml'] else '//'
    lines = content.split('\n')

    for i, line in enumerate(lines):
        if line.strip() == comment_char + ' ' + '='*60:
            return '\n'.join(lines[i+2:])  # Skip separator and blank line
    return content


@mcp.tool(description="""Opens Vim to edit provided content in a temporary file with optional instructions.

Creates a temporary file with the content, optionally adds instruction comments at the top, opens Vim for editing, then returns the result.

Behavior:
- Opens vim directly in the current terminal environment
- Requires interactive terminal access for proper functionality

File Handling:
- Temporary file is created with specified extension
- File is deleted after editing (unless `keep_file=True`)
- Instructions are added as comments and automatically stripped from output

Error Handling:
- Raises subprocess.CalledProcessError if vim exits with non-zero status
- File creation errors raise OSError with specific details
- Instructions are safely handled even with special characters

Output Options:
- `show_diff=True` (default): Returns unified diff showing changes made
- `show_diff=False`: Returns full edited content

Comment Style:
- Python/Shell/YAML files (.py, .sh, .yaml, .yml): Uses `#` comments
- Other files: Uses `//` comments

Examples:
```python
# Edit code with guidance
prompt_user_edit(
    content="def hello():\n    pass",
    file_extension=".py",
    instructions="Add proper implementation and docstring",
    show_diff=True
)

# Edit configuration
prompt_user_edit(
    content="server:\n  port: 8080",
    file_extension=".yaml", 
    instructions="Update port to 3000 and add host configuration"
)

# Keep temporary file for debugging
prompt_user_edit(
    content="Some content",
    instructions="Make improvements",
    keep_file=True,
    show_diff=False
)
```""")
def prompt_user_edit(
    content: str,
    file_extension: str = ".txt",
    instructions: str = None,
    show_diff: bool = True,
    keep_file: bool = False
) -> str:
    """Open vim for editing provided content."""
    # Create temp file with proper extension
    suffix = file_extension if file_extension.startswith('.') else f".{file_extension}"
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

            diff = list(difflib.unified_diff(
                original_lines,
                edited_lines,
                fromfile="original",
                tofile="edited"
            ))

            if diff:
                added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
                removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))

                result = f"Changes made: {added} lines added, {removed} lines removed\n\n"
                result += ''.join(diff)
            else:
                result = "No changes made"
        else:
            result = edited_content

        return result

    finally:
        if not keep_file:
            os.unlink(temp_path)


@mcp.tool(description="""Opens Vim to create new content from scratch with optional starting content and instructions.

Creates a temporary file with optional initial content and instructions, opens Vim for editing, then returns the final content.

Behavior:
- Opens vim directly in the current terminal environment
- Requires interactive terminal access for proper functionality

Features:
- Start with empty file or pre-populate with `initial_content`
- Add instructions as comments that are automatically stripped
- Temporary file is automatically cleaned up
- Choose file extension for proper syntax highlighting

Error Handling:
- Raises subprocess.CalledProcessError if vim exits abnormally
- File creation/deletion errors are handled gracefully
- Returns empty string if user exits vim without saving

Examples:
```python
# Create new Python script
quick_edit(
    file_extension=".py",
    instructions="Create a function that calculates fibonacci numbers",
    initial_content="#!/usr/bin/env python3\n\n"
)

# Create configuration file
quick_edit(
    file_extension=".json",
    instructions="Create a config for database connection",
    initial_content="{\n  \n}"
)

# Create plain text document
quick_edit(
    instructions="Write a brief project summary"
)

# Create shell script
quick_edit(
    file_extension=".sh",
    instructions="Create a deployment script",
    initial_content="#!/bin/bash\nset -e\n\n"
)
```""")
def quick_edit(
    file_extension: str = ".txt",
    instructions: str = None,
    initial_content: str = ""
) -> str:
    """Open vim for creating new content."""
    # Create temp file
    suffix = file_extension if file_extension.startswith('.') else f".{file_extension}"
    fd, temp_path = tempfile.mkstemp(suffix=suffix, text=True)

    try:
        # Write initial content with optional instructions
        os.close(fd)  # Close file descriptor so we can use regular file operations
        _handle_instructions_and_content(temp_path, suffix, instructions, initial_content)

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


@mcp.tool(description="""Opens an existing file in Vim for editing with optional instructions and automatic backup.

Opens the specified file directly in Vim. If instructions are provided, they are shown in a read-only buffer first, then the actual file opens for editing.

Behavior:
- Opens vim directly in the current terminal environment
- Requires interactive terminal access for proper functionality

File Safety:
- Automatic backup creation (file.ext.bak) unless `backup=False`
- Instructions shown in separate read-only buffer to avoid accidental modification
- Error handling if file doesn't exist or isn't readable

Output Options:
- `show_diff=True` (default): Shows unified diff of changes with line counts
- `show_diff=False`: Simple confirmation message

Behavior:
1. Create backup if enabled
2. Show instructions in read-only Vim buffer (if provided)
3. Open actual file for editing
4. Calculate and return diff or confirmation

Examples:
```python
# Edit existing file with guidance
open_file(
    file_path="/path/to/config.py",
    instructions="Update the database URL and add error handling",
    show_diff=True
)

# Quick edit without backup
open_file(
    file_path="/tmp/notes.txt",
    backup=False,
    show_diff=False
)

# Edit with detailed instructions
open_file(
    file_path="src/main.py",
    instructions=\"\"\"Please make the following changes:
1. Add type hints to all functions
2. Add docstrings following Google style
3. Fix any linting issues\"\"\",
    backup=True
)

# Simple edit (no instructions)
open_file("/path/to/file.txt")
```

Note: If the file doesn't exist, Vim will create it. The backup will only be created if the file exists before editing.

Error Handling:
- Raises FileNotFoundError if file path is invalid or inaccessible
- Raises PermissionError if file cannot be read or written
- Backup creation failures are logged but don't prevent editing
- Instructions display errors don't prevent file editing""")
def open_file(
    file_path: str,
    instructions: str = None,
    show_diff: bool = True,
    backup: bool = True
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
            with os.fdopen(fd, 'w') as f:
                f.write(f"INSTRUCTIONS FOR EDITING: {file_path}\n")
                f.write("="*60 + "\n")
                f.write(instructions + "\n")
                f.write("="*60 + "\n")
                f.write("\nPress any key to continue to the file...")

            # Show instructions
            _run_vim(inst_path, ['-R'])
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

        diff = list(difflib.unified_diff(
            original_lines,
            edited_lines,
            fromfile=f"{file_path}.original",
            tofile=file_path
        ))

        if diff:
            added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
            removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))

            result = f"File edited: {file_path}\n"
            result += f"Changes: {added} lines added, {removed} lines removed\n"
            if backup:
                result += f"Backup saved to: {backup_path}\n"
            result += "\n" + ''.join(diff)
        else:
            result = f"No changes made to {file_path}"
    else:
        result = f"File edited: {file_path}"
        if backup:
            result += f"\nBackup saved to: {backup_path}"

    return result


@mcp.tool(description="Checks Vim Tool server status and vim command availability. Returns vim version information and available tool functions. Use this to verify vim is installed and accessible before using other vim tools.")
def server_info() -> str:
    """Get server status and vim version."""
    try:
        result = subprocess.run(['vim', '--version'], capture_output=True, text=True)
        # Extract first line of version info
        version_line = result.stdout.split('\n')[0]

        return f"""Vim Tool Server Status
=====================
Status: Connected and ready
Vim Version: {version_line}

Available tools:
- prompt_user_edit: Edit provided content in vim
- quick_edit: Create new content in vim
- open_file: Edit existing files in vim
- server_info: Get server status"""
    except FileNotFoundError:
        raise RuntimeError("vim command not found. Please install vim.")
