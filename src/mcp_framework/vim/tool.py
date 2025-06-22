"""Vim tool for interactive text editing via MCP."""
import os
import subprocess
import tempfile
import difflib
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Vim Tool")


@mcp.tool(description="Creates a temporary file, opens vim for user editing, and returns the changes.")
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
        with os.fdopen(fd, 'w') as f:
            if instructions:
                # Add instructions as comments based on file type
                comment_char = '#' if suffix in ['.py', '.sh', '.yaml', '.yml'] else '//'
                for line in instructions.strip().split('\n'):
                    f.write(f"{comment_char} {line}\n")
                f.write(f"{comment_char} {'='*60}\n\n")
            f.write(content)
        
        # Open vim
        subprocess.run(['vim', temp_path], check=True)
        
        # Read edited content
        with open(temp_path) as f:
            edited_content = f.read()
        
        # Remove instruction comments if present
        if instructions:
            lines = edited_content.split('\n')
            # Find where actual content starts
            for i, line in enumerate(lines):
                if line.strip() == comment_char + ' ' + '='*60:
                    edited_content = '\n'.join(lines[i+2:])  # Skip separator and blank line
                    break
        
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


@mcp.tool(description="Opens vim for creating new content from scratch.")
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
        with os.fdopen(fd, 'w') as f:
            if instructions:
                # Add instructions as comments
                comment_char = '#' if suffix in ['.py', '.sh', '.yaml', '.yml'] else '//'
                for line in instructions.strip().split('\n'):
                    f.write(f"{comment_char} {line}\n")
                f.write(f"{comment_char} {'='*60}\n\n")
            f.write(initial_content)
        
        # Open vim
        subprocess.run(['vim', temp_path], check=True)
        
        # Read content
        with open(temp_path) as f:
            content = f.read()
        
        # Remove instruction comments if present
        if instructions:
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.strip() == comment_char + ' ' + '='*60:
                    content = '\n'.join(lines[i+2:])
                    break
        
        return content
        
    finally:
        os.unlink(temp_path)


@mcp.tool(description="Opens an existing local file in vim for editing.")
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


@mcp.tool(description="Gets the status of the Vim server and vim CLI availability.")
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