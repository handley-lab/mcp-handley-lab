"""py2nb conversion tool for MCP - bidirectional Python script ↔ Jupyter notebook conversion."""

import subprocess
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.shared.models import ServerInfo

from .converter import (
    notebook_to_python,
    python_to_notebook,
    validate_notebook_file,
    validate_python_file,
)
from .models import (
    ConversionResult,
    ExecutionResult,
    RoundtripResult,
    ValidationResult,
)

mcp = FastMCP("py2nb Conversion Tool")


@mcp.tool(
    description="Converts a Python script to a Jupyter notebook. Supports comment syntax for markdown cells (#|), command cells (#!), and cell splits (#-). Returns structured conversion result."
)
def py_to_notebook(
    script_path: str = Field(
        ...,
        description="Path to the Python script file to convert to a Jupyter notebook.",
    ),
    output_path: str = Field(
        default="",
        description="Path for the output notebook file. If empty, uses script name with .ipynb extension.",
    ),
    backup: bool = Field(
        default=True,
        description="If True, creates a backup of the original script file with .bak extension.",
    ),
) -> ConversionResult:
    """Convert Python script to Jupyter notebook."""
    script_path = Path(script_path)

    if not script_path.exists():
        raise FileNotFoundError(f"Script file not found: {script_path}")

    backup_path_str = None
    # Create backup if requested
    if backup:
        backup_path = script_path.with_suffix(script_path.suffix + ".bak")
        backup_path.write_text(script_path.read_text())
        backup_path_str = str(backup_path)

    # Convert to notebook
    notebook_path = python_to_notebook(str(script_path), output_path)

    # Validate the created notebook
    if not validate_notebook_file(notebook_path):
        raise RuntimeError(f"Generated notebook failed validation: {notebook_path}")

    message = f"Successfully converted {script_path} to {notebook_path}"
    if backup:
        message += f"\nBackup saved to: {backup_path_str}"

    return ConversionResult(
        success=True,
        input_path=str(script_path),
        output_path=notebook_path,
        backup_path=backup_path_str,
        message=message,
    )


@mcp.tool(
    description="Converts a Jupyter notebook to a Python script. Preserves markdown as #| comments, command cells as #! comments, and adds cell separators. Returns structured conversion result."
)
def notebook_to_py(
    notebook_path: str = Field(
        ...,
        description="Path to the Jupyter notebook file to convert to Python script.",
    ),
    output_path: str = Field(
        default="",
        description="Path for the output Python script. If empty, uses notebook name with .py extension.",
    ),
    validate_files: bool = Field(
        default=True,
        description="If True, validates the input notebook and output script for correct syntax.",
    ),
    backup: bool = Field(
        default=True,
        description="If True, creates a backup of the original notebook file with .bak extension.",
    ),
) -> ConversionResult:
    """Convert Jupyter notebook to Python script."""
    notebook_path = Path(notebook_path)

    if not notebook_path.exists():
        raise FileNotFoundError(f"Notebook file not found: {notebook_path}")

    # Validate input notebook
    if validate_files and not validate_notebook_file(str(notebook_path)):
        raise ValueError(f"Invalid notebook file: {notebook_path}")

    backup_path_str = None
    # Create backup if requested
    if backup:
        backup_path = notebook_path.with_suffix(notebook_path.suffix + ".bak")
        backup_path.write_text(notebook_path.read_text())
        backup_path_str = str(backup_path)

    # Convert to Python script
    script_path = notebook_to_python(str(notebook_path), output_path)

    # Validate the created script
    if validate_files and not validate_python_file(script_path):
        raise RuntimeError(f"Generated script failed validation: {script_path}")

    message = f"Successfully converted {notebook_path} to {script_path}"
    if backup:
        message += f"\nBackup saved to: {backup_path_str}"

    return ConversionResult(
        success=True,
        input_path=str(notebook_path),
        output_path=script_path,
        backup_path=backup_path_str,
        message=message,
    )


@mcp.tool(
    description="Validates a notebook file structure and syntax. Returns structured validation result with status and error details."
)
def validate_notebook(
    notebook_path: str = Field(
        ...,
        description="Path to the Jupyter notebook file to validate for correct structure and syntax.",
    ),
) -> ValidationResult:
    """Validate notebook file structure."""
    if not Path(notebook_path).exists():
        return ValidationResult(
            valid=False,
            file_path=notebook_path,
            message="File not found",
            error_details=f"File does not exist: {notebook_path}",
        )

    try:
        is_valid = validate_notebook_file(notebook_path)
        if is_valid:
            return ValidationResult(
                valid=True,
                file_path=notebook_path,
                message="Notebook validation passed",
            )
        else:
            return ValidationResult(
                valid=False,
                file_path=notebook_path,
                message="Notebook validation failed",
                error_details="Invalid notebook structure",
            )
    except Exception as e:
        return ValidationResult(
            valid=False,
            file_path=notebook_path,
            message="Notebook validation failed",
            error_details=str(e),
        )


@mcp.tool(
    description="Validates a Python script file syntax. Returns structured validation result with status and error details."
)
def validate_python(
    script_path: str = Field(
        ...,
        description="Path to the Python script file to validate for correct syntax.",
    ),
) -> ValidationResult:
    """Validate Python script file syntax."""
    if not Path(script_path).exists():
        return ValidationResult(
            valid=False,
            file_path=script_path,
            message="File not found",
            error_details=f"File does not exist: {script_path}",
        )

    try:
        is_valid = validate_python_file(script_path)
        if is_valid:
            return ValidationResult(
                valid=True,
                file_path=script_path,
                message="Python script validation passed",
            )
        else:
            return ValidationResult(
                valid=False,
                file_path=script_path,
                message="Python script validation failed",
                error_details="Python syntax error detected",
            )
    except Exception as e:
        return ValidationResult(
            valid=False,
            file_path=script_path,
            message="Python script validation failed",
            error_details=str(e),
        )


@mcp.tool(
    description="Performs round-trip conversion testing (py→nb→py) to verify conversion fidelity. Returns structured comparison results with difference details."
)
def test_roundtrip(
    script_path: str = Field(
        ...,
        description="Path to the Python script to test for round-trip conversion fidelity (py→nb→py).",
    ),
    cleanup: bool = Field(
        default=True,
        description="If True, removes temporary files created during the round-trip test.",
    ),
) -> RoundtripResult:
    """Test round-trip conversion fidelity."""
    script_path = Path(script_path)

    if not script_path.exists():
        return RoundtripResult(
            success=False,
            input_path=str(script_path),
            differences_found=False,
            message="Script file not found",
            temporary_files_cleaned=True,
        )

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

        differences_found = original_normalized != roundtrip_normalized
        diff_output = None

        if differences_found:
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
            diff_output = "".join(diff)

        # Cleanup temporary files
        cleaned = True
        if cleanup:
            try:
                if notebook_path.exists():
                    notebook_path.unlink()
                if roundtrip_path.exists():
                    roundtrip_path.unlink()
            except Exception:
                cleaned = False

        message = (
            "Round-trip conversion successful"
            if not differences_found
            else "Round-trip differences detected"
        )

        return RoundtripResult(
            success=True,
            input_path=str(script_path),
            differences_found=differences_found,
            message=message,
            diff_output=diff_output,
            temporary_files_cleaned=cleaned,
        )

    except Exception as e:
        return RoundtripResult(
            success=False,
            input_path=str(script_path),
            differences_found=False,
            message=f"Round-trip test failed: {str(e)}",
            temporary_files_cleaned=cleanup,
        )


@mcp.tool(
    description="Checks the status of the Notebook Conversion Tool server and nbformat dependency. Returns structured server information with versions and capabilities."
)
def server_info() -> ServerInfo:
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

    available_tools = [
        "py_to_notebook",
        "notebook_to_py",
        "validate_notebook",
        "validate_python",
        "test_roundtrip",
        "execute_notebook",
        "server_info",
    ]

    comment_syntax = {
        "#| or # |": "Markdown cells",
        "#! or # !": "Command cells (magic commands)",
        "#- or # -": "Cell separators",
        "#% or # %": "Command cells (alternative syntax)",
    }

    return ServerInfo(
        name="py2nb Conversion Tool",
        version="1.0.0",
        status="active",
        capabilities=available_tools,
        dependencies={
            "nbformat": nbformat_version,
            "jupyter": jupyter_info,
            "comment_syntax": str(comment_syntax),
        },
    )


@mcp.tool(
    description="Executes all cells in a Jupyter notebook and populates outputs as if a user ran every cell. Returns structured execution results with cell counts and timing."
)
def execute_notebook(
    notebook_path: str = Field(
        ..., description="Path to the Jupyter notebook file to execute all cells."
    ),
    allow_errors: bool = Field(
        default=False,
        description="If True, continues execution even when cells raise exceptions.",
    ),
    timeout: int = Field(
        default=600,
        description="Maximum time in seconds to wait for each cell to execute.",
        gt=0,
    ),
    kernel_name: str = Field(
        default="python3",
        description="Name of the Jupyter kernel to use for execution (e.g., 'python3', 'python').",
    ),
) -> ExecutionResult:
    """Execute all cells in a notebook and populate outputs."""
    notebook_path = Path(notebook_path)

    if not notebook_path.exists():
        return ExecutionResult(
            success=False,
            notebook_path=str(notebook_path),
            cells_executed=0,
            cells_with_errors=0,
            execution_time_seconds=0.0,
            message="Notebook file not found",
            error_details=f"File does not exist: {notebook_path}",
        )

    # Validate notebook first
    if not validate_notebook_file(str(notebook_path)):
        return ExecutionResult(
            success=False,
            notebook_path=str(notebook_path),
            cells_executed=0,
            cells_with_errors=0,
            execution_time_seconds=0.0,
            message="Invalid notebook file",
            error_details="Notebook file has invalid structure",
        )

    try:
        import nbformat
        from nbclient import NotebookClient
        from nbclient.exceptions import CellExecutionError
    except ImportError as e:
        return ExecutionResult(
            success=False,
            notebook_path=str(notebook_path),
            cells_executed=0,
            cells_with_errors=0,
            execution_time_seconds=0.0,
            message="Missing dependencies",
            error_details=f"Required libraries not installed: {e}",
        )

    try:
        # Load the notebook
        with open(notebook_path, encoding="utf-8") as f:
            nb = nbformat.read(f, as_version=4)

        # Create execution client
        client = NotebookClient(
            nb,
            timeout=timeout,
            kernel_name=kernel_name,
            allow_errors=allow_errors,
            resources={"metadata": {"path": str(notebook_path.parent)}},
        )

        # Execute the notebook
        start_time = time.time()

        try:
            client.execute()
            execution_success = True
            error_message = None
        except CellExecutionError as e:
            execution_success = False
            error_message = str(e)
        except Exception as e:
            execution_success = False
            error_message = f"Execution failed: {str(e)}"

        end_time = time.time()
        execution_time = end_time - start_time

        # Count executed cells and errors
        cells_executed = 0
        cells_with_errors = 0

        for cell in client.nb.cells:
            if cell.cell_type == "code":
                if (
                    hasattr(cell, "execution_count")
                    and cell.execution_count is not None
                ):
                    cells_executed += 1

                # Check for errors in outputs
                if hasattr(cell, "outputs"):
                    for output in cell.outputs:
                        if output.get("output_type") == "error":
                            cells_with_errors += 1
                            break

        # Save the executed notebook back to file
        with open(notebook_path, "w", encoding="utf-8") as f:
            nbformat.write(client.nb, f)

        if execution_success:
            message = f"Successfully executed {cells_executed} cells in {execution_time:.2f} seconds"
            if cells_with_errors > 0:
                message += f" ({cells_with_errors} cells had errors)"
        else:
            message = f"Execution stopped after {cells_executed} cells due to error"

        return ExecutionResult(
            success=execution_success,
            notebook_path=str(notebook_path),
            cells_executed=cells_executed,
            cells_with_errors=cells_with_errors,
            execution_time_seconds=execution_time,
            message=message,
            error_details=error_message,
            kernel_name=kernel_name,
        )

    except Exception as e:
        return ExecutionResult(
            success=False,
            notebook_path=str(notebook_path),
            cells_executed=0,
            cells_with_errors=0,
            execution_time_seconds=0.0,
            message="Execution failed",
            error_details=str(e),
            kernel_name=kernel_name,
        )
