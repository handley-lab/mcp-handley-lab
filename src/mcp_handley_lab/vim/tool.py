"""Vim tool for interactive text editing via MCP."""
import os
import subprocess
import tempfile
import difflib
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Vim Tool")


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


@mcp.tool(description="Presents the given `content` in a temporary file, opens Vim for user editing, and returns the modified content. Optional `instructions` can be provided, which will be added as comments at the beginning of the file. Use this to allow a user to interactively edit text within a workflow. The `show_diff` parameter controls whether the output is the full edited text or a diff showing the changes.")
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
        subprocess.run(['vim', temp_path], check=True)
        
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


@mcp.tool(description="Opens Vim for creating new content from scratch. Optional `instructions` can be provided, which will be added as comments at the beginning of the file. `initial_content` can be used to pre-populate the file. Use this to quickly create or edit small text files.")
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
        subprocess.run(['vim', temp_path], check=True)
        
        # Read content
        with open(temp_path) as f:
            content = f.read()
        
        # Remove instruction comments if present
        content = _strip_instructions(content, instructions, suffix)
        
        return content
        
    finally:
        os.unlink(temp_path)


@mcp.tool(description="Opens an existing local file in Vim for editing. If `instructions` are provided, they are displayed in a temporary Vim buffer *before* opening the file for editing. A backup of the original file is created if `backup` is True (default). Use this to modify existing files.")
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
            subprocess.run(['vim', '-R', inst_path], check=True)
        finally:
            os.unlink(inst_path)
    
    # Open the actual file
    subprocess.run(['vim', str(path)], check=True)
    
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


@mcp.tool(description="Checks the status of the Vim Tool server and the availability of the `vim` command-line tool. Use this to verify the tool is operational before calling other Vim Tool functions.")
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