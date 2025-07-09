"""Core notebook conversion logic for bidirectional Python script ↔ Jupyter notebook conversion."""
import json
from pathlib import Path
from typing import Any

import nbformat.v4

# Comment syntax patterns from original py2nb
CELL_SPLIT_CHARS = ["#-", "# -"]
MARKDOWN_CHARS = ["#|", "# |"]
COMMAND_CHARS = ["#!", "# !", "#%", "# %"]


def _str_starts_with(string: str, options: list[str]) -> bool:
    """Check if string starts with any of the given options."""
    return any(string.startswith(opt) for opt in options)


def _get_comment_type(line: str) -> str | None:
    """Determine the type of comment based on prefix."""
    if _str_starts_with(line, COMMAND_CHARS):
        return "command"
    elif _str_starts_with(line, MARKDOWN_CHARS):
        return "markdown"
    elif _str_starts_with(line, CELL_SPLIT_CHARS):
        return "split"
    return None


def _extract_content(line: str, comment_type: str) -> str:
    """Extract content from comment line based on type."""
    if comment_type == "command":
        # Find first ! or % and return the command marker plus everything after it
        if "!" in line:
            return "!" + line[line.index("!") + 1 :].lstrip()
        elif "%" in line:
            return "%" + line[line.index("%") + 1 :].lstrip()
    elif comment_type == "markdown":
        # Find first | and return everything after it
        return line[line.index("|") + 1 :]
    return ""


def _new_cell(nb: Any, cell_content: str, cell_type: str = "code") -> str:
    """Create a new cell with proper metadata."""
    cell_content = cell_content.strip()
    if cell_content:
        if cell_type == "markdown":
            cell = nbformat.v4.new_markdown_cell(cell_content)
        elif cell_type == "command":
            cell = nbformat.v4.new_code_cell(cell_content)
            cell.metadata.update({"tags": ["command"], "collapsed": False})
        else:  # code cell
            cell = nbformat.v4.new_code_cell(cell_content)

        nb.cells.append(cell)
    return ""


def _validate_notebook(nb: Any) -> None:
    """Validate notebook structure and fix common issues."""
    for cell in nb.cells:
        # Remove auto-generated cell ids for consistent format
        if "id" in cell:
            del cell["id"]

        # Ensure proper cell structure
        if not hasattr(cell, "metadata"):
            cell.metadata = {}

        if cell.cell_type == "code":
            # Ensure code cells have required fields
            if not hasattr(cell, "execution_count"):
                cell.execution_count = None
            if not hasattr(cell, "outputs"):
                cell.outputs = []
        elif cell.cell_type == "markdown":
            # Ensure markdown cells don't have code cell fields
            if hasattr(cell, "execution_count"):
                delattr(cell, "execution_count")
            if hasattr(cell, "outputs"):
                delattr(cell, "outputs")

        # Ensure source is a list
        if isinstance(cell.source, str):
            cell.source = cell.source.splitlines(True)


def python_to_notebook(script_path: str, output_path: str | None = None) -> str:
    """Convert Python script to Jupyter notebook."""
    script_path = Path(script_path)

    if not script_path.exists():
        raise FileNotFoundError(f"Script file not found: {script_path}")

    # Determine output path
    if output_path:
        notebook_path = Path(output_path)
        if notebook_path.suffix != ".ipynb":
            notebook_path = notebook_path.with_suffix(".ipynb")
    else:
        notebook_path = script_path.with_suffix(".ipynb")

    with open(script_path, encoding="utf-8") as f:
        # Initialize cells and notebook
        markdown_cell = ""
        code_cell = ""
        command_cell = ""
        nb = nbformat.v4.new_notebook()

        # Set notebook metadata
        nb.metadata.update(
            {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3",
                },
                "language_info": {
                    "codemirror_mode": {"name": "ipython", "version": 3},
                    "file_extension": ".py",
                    "mimetype": "text/x-python",
                    "name": "python",
                    "nbconvert_exporter": "python",
                    "pygments_lexer": "ipython3",
                    "version": "3.8.0",
                },
            }
        )

        # Set consistent nbformat version
        nb.nbformat = 4
        nb.nbformat_minor = 2

        for line in f:
            comment_type = _get_comment_type(line)

            if comment_type:
                # Finish current code cell before processing comment
                code_cell = _new_cell(nb, code_cell, "code")

                if comment_type == "markdown":
                    # Add to markdown cell
                    markdown_cell += _extract_content(line, "markdown")
                elif comment_type == "command":
                    # Finish any pending markdown cell
                    markdown_cell = _new_cell(nb, markdown_cell, "markdown")
                    # Add to command cell
                    command_cell += _extract_content(line, "command") + "\n"
                elif comment_type == "split":
                    # Finish any pending cells and start fresh
                    markdown_cell = _new_cell(nb, markdown_cell, "markdown")
                    command_cell = _new_cell(nb, command_cell, "command")
            else:
                # Regular code line - finish pending markdown/command cells
                markdown_cell = _new_cell(nb, markdown_cell, "markdown")
                command_cell = _new_cell(nb, command_cell, "command")
                # Add to code cell
                code_cell += line

        # Finish any remaining cells
        markdown_cell = _new_cell(nb, markdown_cell, "markdown")
        command_cell = _new_cell(nb, command_cell, "command")
        code_cell = _new_cell(nb, code_cell, "code")

        # Always validate notebook structure for cleanup
        _validate_notebook(nb)

        # Write notebook
        with open(notebook_path, "w", encoding="utf-8") as f:
            nbformat.write(nb, f, version=nbformat.NO_CONVERT)

        return str(notebook_path)


def notebook_to_python(notebook_path: str, output_path: str | None = None) -> str:
    """Convert Jupyter notebook to Python script."""
    notebook_path = Path(notebook_path)

    if not notebook_path.exists():
        raise FileNotFoundError(f"Notebook file not found: {notebook_path}")

    # Determine output path
    if output_path:
        script_path = Path(output_path)
        if script_path.suffix != ".py":
            script_path = script_path.with_suffix(".py")
    else:
        script_path = notebook_path.with_suffix(".py")

    with (
        open(notebook_path, encoding="utf-8") as f_in,
        open(script_path, "w", encoding="utf-8") as f_out,
    ):
        last_source = ""
        notebook_data = json.load(f_in)

        for cell in notebook_data["cells"]:
            if last_source == "code" and cell["cell_type"] == "code":
                # Check if this is a command cell
                is_command_cell = "command" in cell.get("metadata", {}).get("tags", [])
                if not is_command_cell:
                    f_out.write("#-------------------------------\n\n")

            for line in cell["source"]:
                if cell["cell_type"] == "markdown":
                    line = "#| " + line.lstrip()
                elif cell["cell_type"] == "code":
                    # Check if this is a command cell
                    is_command_cell = "command" in cell.get("metadata", {}).get(
                        "tags", []
                    )
                    if is_command_cell:
                        # Remove leading ! if present (from py2nb conversion)
                        stripped_line = line.lstrip()
                        if stripped_line.startswith("!"):
                            stripped_line = stripped_line[1:].lstrip()
                        line = "#! " + stripped_line
                line = line.rstrip() + "\n"
                f_out.write(line)
            f_out.write("\n")
            last_source = cell["cell_type"]

    return str(script_path)


def validate_notebook_file(notebook_path: str) -> bool:
    """Validate a notebook file can be loaded and has valid structure."""
    try:
        with open(notebook_path, encoding="utf-8") as f:
            notebook_data = json.load(f)

        # Basic structure validation
        if "cells" not in notebook_data:
            return False

        for cell in notebook_data["cells"]:
            if "cell_type" not in cell or "source" not in cell:
                return False

        return True
    except (json.JSONDecodeError, FileNotFoundError):
        return False


def validate_python_file(script_path: str) -> bool:
    """Validate a Python file can be read and parsed."""
    try:
        with open(script_path, encoding="utf-8") as f:
            content = f.read()

        # Try to compile the Python code (basic syntax check)
        compile(content, script_path, "exec")
        return True
    except (SyntaxError, FileNotFoundError):
        return False
