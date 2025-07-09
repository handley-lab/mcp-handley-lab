"""Notebook conversion tool for MCP - bidirectional Python script ↔ Jupyter notebook conversion."""
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .converter import (
    notebook_to_python,
    python_to_notebook,
    validate_notebook_file,
    validate_python_file,
)

mcp = FastMCP("Notebook Conversion Tool")


@mcp.tool(
    description="Converts a Python script to a Jupyter notebook. Supports comment syntax for markdown cells (#|), command cells (#!), and cell splits (#-). Returns the path to the created notebook."
)
def py_to_notebook(
    script_path: str,
    output_path: str = "",
    backup: bool = True,
) -> str:
    """Convert Python script to Jupyter notebook."""
    script_path = Path(script_path)

    if not script_path.exists():
        raise FileNotFoundError(f"Script file not found: {script_path}")

    # Create backup if requested
    if backup:
        backup_path = script_path.with_suffix(script_path.suffix + ".bak")
        backup_path.write_text(script_path.read_text())

    # Convert to notebook
    notebook_path = python_to_notebook(str(script_path), output_path)

    # Validate the created notebook
    if not validate_notebook_file(notebook_path):
        raise RuntimeError(f"Generated notebook failed validation: {notebook_path}")

    result = f"Successfully converted {script_path} to {notebook_path}"
    if backup:
        result += f"\nBackup saved to: {backup_path}"

    return result


@mcp.tool(
    description="Converts a Jupyter notebook to a Python script. Preserves markdown as #| comments, command cells as #! comments, and adds cell separators. Returns the path to the created script."
)
def notebook_to_py(
    notebook_path: str,
    output_path: str = "",
    validate_files: bool = True,
    backup: bool = True,
) -> str:
    """Convert Jupyter notebook to Python script."""
    notebook_path = Path(notebook_path)

    if not notebook_path.exists():
        raise FileNotFoundError(f"Notebook file not found: {notebook_path}")

    # Validate input notebook
    if validate_files and not validate_notebook_file(str(notebook_path)):
        raise ValueError(f"Invalid notebook file: {notebook_path}")

    # Create backup if requested
    if backup:
        backup_path = notebook_path.with_suffix(notebook_path.suffix + ".bak")
        backup_path.write_text(notebook_path.read_text())

    # Convert to Python script
    script_path = notebook_to_python(str(notebook_path), output_path)

    # Validate the created script
    if validate_files and not validate_python_file(script_path):
        raise RuntimeError(f"Generated script failed validation: {script_path}")

    result = f"Successfully converted {notebook_path} to {script_path}"
    if backup:
        result += f"\nBackup saved to: {backup_path}"

    return result


@mcp.tool(
    description="Validates a notebook file structure and syntax. Returns validation status and any error messages found."
)
def validate_notebook(notebook_path: str) -> str:
    """Validate notebook file structure."""
    if not Path(notebook_path).exists():
        return f"❌ File not found: {notebook_path}"

    try:
        if validate_notebook_file(notebook_path):
            return f"✅ Notebook validation passed: {notebook_path}"
        else:
            return f"❌ Notebook validation failed: {notebook_path} - Invalid structure"
    except Exception as e:
        return f"❌ Notebook validation failed: {notebook_path} - {str(e)}"


@mcp.tool(
    description="Validates a Python script file syntax. Returns validation status and any error messages found."
)
def validate_python(script_path: str) -> str:
    """Validate Python script file syntax."""
    if not Path(script_path).exists():
        return f"❌ File not found: {script_path}"

    try:
        if validate_python_file(script_path):
            return f"✅ Python script validation passed: {script_path}"
        else:
            return f"❌ Python script validation failed: {script_path} - Syntax error"
    except Exception as e:
        return f"❌ Python script validation failed: {script_path} - {str(e)}"


@mcp.tool(
    description="Performs round-trip conversion testing (py→nb→py) to verify conversion fidelity. Returns comparison results and any differences found."
)
def test_roundtrip(
    script_path: str,
    cleanup: bool = True,
) -> str:
    """Test round-trip conversion fidelity."""
    script_path = Path(script_path)

    if not script_path.exists():
        return f"❌ Script file not found: {script_path}"

    try:
        # Original content
        original_content = script_path.read_text()

        # Convert to notebook
        notebook_path = script_path.with_suffix(".ipynb")
        python_to_notebook(str(script_path), str(notebook_path))

        # Convert back to Python
        roundtrip_path = script_path.with_suffix(".roundtrip.py")
        notebook_to_python(str(notebook_path), str(roundtrip_path))

        # Compare content
        roundtrip_content = roundtrip_path.read_text()

        # Normalize whitespace for comparison
        original_normalized = "\n".join(
            line.rstrip() for line in original_content.splitlines()
        )
        roundtrip_normalized = "\n".join(
            line.rstrip() for line in roundtrip_content.splitlines()
        )

        if original_normalized == roundtrip_normalized:
            result = f"✅ Round-trip conversion successful: {script_path}"
        else:
            # Show differences
            import difflib

            diff = list(
                difflib.unified_diff(
                    original_content.splitlines(keepends=True),
                    roundtrip_content.splitlines(keepends=True),
                    fromfile=str(script_path),
                    tofile=str(roundtrip_path),
                    lineterm="",
                )
            )

            result = f"⚠️ Round-trip differences found in {script_path}:\n\n"
            result += "".join(diff)

        # Cleanup temporary files
        if cleanup:
            if notebook_path.exists():
                notebook_path.unlink()
            if roundtrip_path.exists():
                roundtrip_path.unlink()

        return result

    except Exception as e:
        return f"❌ Round-trip test failed: {script_path} - {str(e)}"


@mcp.tool(
    description="Checks the status of the Notebook Conversion Tool server and nbformat dependency. Returns version info and available functions."
)
def server_info() -> str:
    """Get server status and dependency information."""
    try:
        import nbformat

        nbformat_version = nbformat.__version__
    except ImportError:
        nbformat_version = "Not installed"

    # Check if jupyter is available for optional execution
    try:
        result = subprocess.run(
            ["jupyter", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        jupyter_info = result.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.CalledProcessError):
        jupyter_info = "Not available"

    return f"""Notebook Conversion Tool Server Status
========================================
Status: Connected and ready
nbformat Version: {nbformat_version}
Jupyter: {jupyter_info}

Available tools:
- py_to_notebook: Convert Python script to Jupyter notebook
- notebook_to_py: Convert Jupyter notebook to Python script
- validate_notebook: Validate notebook file structure
- validate_python: Validate Python script syntax
- test_roundtrip: Test round-trip conversion fidelity
- server_info: Get server status

Comment Syntax Support:
- #| or # | : Markdown cells
- #! or # ! : Command cells (magic commands)
- #- or # - : Cell separators
- #% or # % : Command cells (alternative syntax)"""
