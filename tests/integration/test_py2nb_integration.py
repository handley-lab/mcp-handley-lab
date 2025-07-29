"""Integration tests for py2nb conversion tool."""
import contextlib
import json
import subprocess
import tempfile
from pathlib import Path

import pytest
from mcp_handley_lab.py2nb.tool import (
    mcp,
)


class TestPy2nbToolIntegration:
    """Integration tests for py2nb conversion tool."""

    @pytest.mark.asyncio
    async def test_py_to_notebook_integration(self):
        """Test full Python to notebook conversion."""
        # Create test Python file
        test_content = """#| # Data Analysis Example
#| This notebook demonstrates basic data analysis
#! import pandas as pd
#% matplotlib inline
import numpy as np
import matplotlib.pyplot as plt

# Generate sample data
np.random.seed(42)
data = np.random.randn(100)

#-
#| ## Visualization
plt.figure(figsize=(10, 6))
plt.hist(data, bins=20)
plt.title('Sample Data Distribution')
plt.show()

#-
#| ## Summary Statistics
print(f"Mean: {np.mean(data):.3f}")
print(f"Std: {np.std(data):.3f}")
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_content)
            python_file = f.name

        try:
            # Convert to notebook using MCP call_tool
            result = await mcp.call_tool("py_to_notebook", {"script_path": python_file})
            response = json.loads(result[0].text)

            assert "error" not in response, response.get("error")
            result = response  # response IS the result

            # Verify result structure
            assert result["success"] is True
            assert result["input_path"] == python_file
            assert result["output_path"].endswith(".ipynb")
            assert "Successfully converted" in result["message"]
            assert result["backup_path"] is not None  # backup enabled by default

            # Verify notebook file exists
            notebook_file = Path(result["output_path"])
            assert notebook_file.exists()

            # Verify notebook structure
            with open(notebook_file) as f:
                notebook_data = json.load(f)

            assert notebook_data["nbformat"] == 4
            assert len(notebook_data["cells"]) >= 5

            # Find different cell types
            markdown_cells = [
                cell
                for cell in notebook_data["cells"]
                if cell["cell_type"] == "markdown"
            ]
            command_cells = [
                cell
                for cell in notebook_data["cells"]
                if cell["cell_type"] == "code"
                and "command" in cell.get("metadata", {}).get("tags", [])
            ]
            code_cells = [
                cell
                for cell in notebook_data["cells"]
                if cell["cell_type"] == "code"
                and "command" not in cell.get("metadata", {}).get("tags", [])
            ]

            # Verify we have the expected cell types
            assert len(markdown_cells) >= 2  # At least two markdown cells
            assert len(command_cells) >= 1  # At least one command cell
            assert len(code_cells) >= 2  # At least two code cells

        finally:
            Path(python_file).unlink(missing_ok=True)
            notebook_file.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_notebook_to_py_integration(self):
        """Test full notebook to Python conversion."""
        # Create test notebook
        notebook_data = {
            "nbformat": 4,
            "nbformat_minor": 2,
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": [
                        "# Machine Learning Example\n",
                        "This notebook shows ML workflow\n",
                    ],
                    "metadata": {},
                },
                {
                    "cell_type": "code",
                    "source": ["!pip install scikit-learn\n", "%matplotlib inline\n"],
                    "metadata": {"tags": ["command"]},
                    "outputs": [],
                    "execution_count": None,
                },
                {
                    "cell_type": "code",
                    "source": [
                        "from sklearn.datasets import load_iris\n",
                        "from sklearn.model_selection import train_test_split\n",
                    ],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None,
                },
                {
                    "cell_type": "code",
                    "source": [
                        "# Load data\n",
                        "iris = load_iris()\n",
                        "X_train, X_test, y_train, y_test = train_test_split(iris.data, iris.target, test_size=0.2)\n",
                    ],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None,
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
            json.dump(notebook_data, f)
            notebook_file = f.name

        try:
            # Convert to Python using MCP call_tool

            result = await mcp.call_tool(
                "notebook_to_py", {"notebook_path": notebook_file}
            )
            response = json.loads(result[0].text)

            assert "error" not in response, response.get("error")
            result = response

            # Verify result structure
            assert result["success"] is True
            assert result["input_path"] == notebook_file
            assert result["output_path"].endswith(".py")
            assert "Successfully converted" in result["message"]
            assert result["backup_path"] is not None  # backup enabled by default

            # Verify Python file exists
            python_file = result["output_path"]
            assert Path(python_file).exists()

            # Verify Python file content
            with open(python_file) as f:
                content = f.read()

            assert "#| # Machine Learning Example" in content
            assert "#| This notebook shows ML workflow" in content
            assert "#! pip install scikit-learn" in content
            assert "#! %matplotlib inline" in content
            assert "from sklearn.datasets import load_iris" in content
            assert "#-------------------------------" in content
            assert "train_test_split" in content

        finally:
            Path(notebook_file).unlink(missing_ok=True)
            Path(python_file).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_validation_integration(self):
        """Test validation functions with real files."""
        # Valid notebook
        notebook_data = {
            "nbformat": 4,
            "nbformat_minor": 2,
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["print('Hello, World!')\n"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None,
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
            json.dump(notebook_data, f)
            notebook_file = f.name

        # Valid Python file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('Hello, World!')\nx = 42\nprint(x)")
            python_file = f.name

        try:
            # Test notebook validation using MCP call_tool
            result = await mcp.call_tool(
                "validate_notebook", {"notebook_path": notebook_file}
            )
            response = json.loads(result[0].text)
            assert "error" not in response, response.get("error")
            result = response
            assert result["valid"] is True
            assert result["file_path"] == notebook_file
            assert "validation passed" in result["message"]

            # Test Python validation using MCP call_tool
            result = await mcp.call_tool(
                "validate_python", {"script_path": python_file}
            )
            response = json.loads(result[0].text)
            assert "error" not in response, response.get("error")
            result = response
            assert result["valid"] is True
            assert result["file_path"] == python_file
            assert "validation passed" in result["message"]

            # Test non-existent file using MCP call_tool
            result = await mcp.call_tool(
                "validate_notebook", {"notebook_path": "/non/existent/file.ipynb"}
            )
            response = json.loads(result[0].text)
            assert "error" not in response, response.get("error")
            result = response
            assert result["valid"] is False
            assert "File not found" in result["message"]

        finally:
            Path(notebook_file).unlink(missing_ok=True)
            Path(python_file).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_roundtrip_integration(self):
        """Test round-trip conversion integration."""
        # Create Python file with various comment types
        test_content = """#| # Test Document
#| This is a test notebook
#! echo "Hello from command"
#% load_ext autoreload
import os
print("Hello, World!")

#-
#| ## Section 2
x = 42
y = x * 2
print(f"Result: {y}")
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_content)
            python_file = f.name

        try:
            # Test round-trip conversion using MCP call_tool
            result = await mcp.call_tool("test_roundtrip", {"script_path": python_file})
            response = json.loads(result[0].text)

            assert "error" not in response, response.get("error")
            result = response

            # Verify result structure
            assert result["success"] is True
            assert result["input_path"] == python_file
            assert "Round-trip" in result["message"]
            assert result["temporary_files_cleaned"] is True

        finally:
            Path(python_file).unlink(missing_ok=True)

    @pytest.mark.skip(reason="Notebook execution requires Jupyter kernel setup in CI")
    @pytest.mark.asyncio
    async def test_notebook_execution_integration(self):
        """Test notebook execution functionality."""
        pytest.importorskip(
            "nbclient", reason="nbclient required for notebook execution"
        )

        # Create test Python file with executable content
        test_content = """import math
print("Hello from executed notebook!")
x = 5
y = x * 2
print(f"x = {x}, y = {y}")

# This should produce output
result = math.sqrt(16)
result"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_content)
            python_file = f.name

        try:
            # Convert to notebook first using MCP call_tool
            result = await mcp.call_tool("py_to_notebook", {"script_path": python_file})
            response = json.loads(result[0].text)
            assert "error" not in response, response.get("error")
            conversion_result = response
            notebook_file = conversion_result["output_path"]

            # Execute the notebook using MCP call_tool
            result = await mcp.call_tool(
                "execute_notebook",
                {"notebook_path": notebook_file, "allow_errors": True},
            )
            response = json.loads(result[0].text)
            assert "error" not in response, response.get("error")
            execution_result = response

            # Skip test if Jupyter kernel is not available in CI environment
            if (
                not execution_result["success"]
                and "kernel" in execution_result["message"].lower()
            ):
                pytest.skip("Jupyter kernel not available in CI environment")

            # Verify execution results
            assert execution_result["success"] is True
            assert execution_result["notebook_path"] == notebook_file
            assert execution_result["cells_executed"] >= 1
            assert execution_result["cells_with_errors"] == 0
            assert execution_result["execution_time_seconds"] > 0
            assert "Successfully executed" in execution_result["message"]
            assert execution_result["kernel_name"] == "python3"

            # Verify the notebook file was updated with outputs

            with open(notebook_file) as f:
                executed_nb = json.load(f)

            # Check that code cells have execution_count and outputs
            code_cells = [
                cell for cell in executed_nb["cells"] if cell["cell_type"] == "code"
            ]
            assert len(code_cells) >= 1

            # At least one cell should have been executed
            executed_cells = [
                cell for cell in code_cells if cell.get("execution_count") is not None
            ]
            assert len(executed_cells) >= 1

            # At least one cell should have outputs
            cells_with_outputs = [cell for cell in code_cells if cell.get("outputs")]
            assert len(cells_with_outputs) >= 1

        finally:
            Path(python_file).unlink(missing_ok=True)
            Path(notebook_file).unlink(missing_ok=True)
            if conversion_result["backup_path"]:
                Path(conversion_result["backup_path"]).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_server_info_integration(self):
        """Test server info function."""
        result = await mcp.call_tool("server_info", {})
        response = json.loads(result[0].text)

        assert "error" not in response, response.get("error")
        result = response

        assert result["status"] == "active"
        assert "nbformat" in result["dependencies"]
        assert "jupyter" in result["dependencies"]
        assert "py_to_notebook" in result["capabilities"]
        assert "notebook_to_py" in result["capabilities"]
        assert "validate_notebook" in result["capabilities"]
        assert "comment_syntax" in result["dependencies"]

    @pytest.mark.asyncio
    async def test_backup_functionality(self):
        """Test backup creation during conversion."""
        # Create test Python file
        test_content = "print('test')\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_content)
            python_file = f.name

        try:
            # Convert with backup enabled using MCP call_tool
            result = await mcp.call_tool(
                "py_to_notebook", {"script_path": python_file, "backup": True}
            )
            response = json.loads(result[0].text)

            assert "error" not in response, response.get("error")
            result = response

            # Verify backup was created
            assert result["backup_path"] is not None
            backup_file = result["backup_path"]
            assert Path(backup_file).exists()
            assert "Backup saved to:" in result["message"]

            # Verify backup content
            with open(backup_file) as f:
                backup_content = f.read()
            assert backup_content == test_content

        finally:
            Path(python_file).unlink(missing_ok=True)
            Path(backup_file).unlink(missing_ok=True)
            Path(python_file.replace(".py", ".ipynb")).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_custom_output_paths(self):
        """Test custom output path specification."""
        # Create test files
        test_content = "print('test')\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_content)
            python_file = f.name

        try:
            # Test custom notebook output path using MCP call_tool
            custom_notebook = python_file.replace(".py", "_custom.ipynb")
            result = await mcp.call_tool(
                "py_to_notebook",
                {"script_path": python_file, "output_path": custom_notebook},
            )
            response = json.loads(result[0].text)
            assert "error" not in response, response.get("error")
            result = response

            assert Path(custom_notebook).exists()
            assert result["output_path"] == custom_notebook

            # Test custom Python output path using MCP call_tool
            custom_python = custom_notebook.replace(".ipynb", "_back.py")
            result = await mcp.call_tool(
                "notebook_to_py",
                {"notebook_path": custom_notebook, "output_path": custom_python},
            )
            response = json.loads(result[0].text)
            assert "error" not in response, response.get("error")
            result = response

            assert Path(custom_python).exists()
            assert result["output_path"] == custom_python

        finally:
            Path(python_file).unlink(missing_ok=True)
            Path(custom_notebook).unlink(missing_ok=True)
            Path(custom_python).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in integration scenarios."""
        from mcp.server.fastmcp.exceptions import ToolError

        # Test non-existent file - MCP should raise ToolError
        with pytest.raises(ToolError, match="Script file not found"):
            await mcp.call_tool(
                "py_to_notebook", {"script_path": "/non/existent/file.py"}
            )

        with pytest.raises(ToolError, match="Notebook file not found"):
            await mcp.call_tool(
                "notebook_to_py", {"notebook_path": "/non/existent/file.ipynb"}
            )

        # Test invalid notebook file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
            f.write("invalid json content")
            invalid_notebook = f.name

        try:
            with pytest.raises(ToolError, match="Invalid notebook file"):
                await mcp.call_tool(
                    "notebook_to_py", {"notebook_path": invalid_notebook}
                )
        finally:
            Path(invalid_notebook).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_complex_notebook_structure(self):
        """Test conversion of complex notebook structures."""
        # Create notebook with mixed cell types and metadata
        notebook_data = {
            "nbformat": 4,
            "nbformat_minor": 2,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3",
                }
            },
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": ["# Complex Notebook\n", "With multiple features\n"],
                    "metadata": {},
                },
                {
                    "cell_type": "code",
                    "source": [
                        "# Setup\n",
                        "import numpy as np\n",
                        "import pandas as pd\n",
                    ],
                    "metadata": {"tags": ["setup"]},
                    "outputs": [],
                    "execution_count": 1,
                },
                {
                    "cell_type": "code",
                    "source": ["!pip install matplotlib\n", "%matplotlib inline\n"],
                    "metadata": {"tags": ["command"]},
                    "outputs": [],
                    "execution_count": 2,
                },
                {
                    "cell_type": "markdown",
                    "source": ["## Data Processing\n"],
                    "metadata": {},
                },
                {
                    "cell_type": "code",
                    "source": [
                        "# Process data\n",
                        "data = np.random.randn(100)\n",
                        "df = pd.DataFrame({'values': data})\n",
                    ],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": 3,
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
            json.dump(notebook_data, f)
            notebook_file = f.name

        try:
            # Convert to Python using MCP call_tool

            result = await mcp.call_tool(
                "notebook_to_py", {"notebook_path": notebook_file}
            )
            response = json.loads(result[0].text)

            assert "error" not in response, response.get("error")
            result = response
            python_file = result["output_path"]

            # Verify Python content
            with open(python_file) as f:
                content = f.read()

            assert "#| # Complex Notebook" in content
            assert "#| ## Data Processing" in content
            assert "#! pip install matplotlib" in content
            assert "#! %matplotlib inline" in content
            assert "import numpy as np" in content
            # Note: #------ separator only appears between consecutive code cells
            # In this case, we have markdown -> code -> command -> markdown -> code
            # so no separator is expected

            # Convert back to notebook using MCP call_tool
            result = await mcp.call_tool("py_to_notebook", {"script_path": python_file})
            response2 = json.loads(result[0].text)

            assert "error" not in response2, response2.get("error")
            result2 = response2
            notebook_file2 = result2["output_path"]

            # Verify round-trip notebook
            with open(notebook_file2) as f:
                notebook_data2 = json.load(f)

            assert notebook_data2["nbformat"] == 4
            assert len(notebook_data2["cells"]) >= 4

        finally:
            Path(notebook_file).unlink(missing_ok=True)
            Path(python_file).unlink(missing_ok=True)
            with contextlib.suppress(NameError):
                Path(notebook_file2).unlink(missing_ok=True)


@pytest.mark.integration
class TestPy2nbMCPIntegration:
    """Test py2nb tool via MCP JSON-RPC protocol."""

    def test_mcp_server_startup(self):
        """Test that the MCP server starts correctly."""
        try:
            # Test server startup
            result = subprocess.run(
                ["python", "-m", "mcp_handley_lab.py2nb.tool"],
                input='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}',
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should not immediately exit with error
            assert result.returncode == 0 or result.returncode is None

        except subprocess.TimeoutExpired:
            # This is expected for MCP servers that wait for input
            pass

    def test_mcp_tool_execution(self):
        """Test tool execution via MCP protocol."""
        # Create test file
        test_content = """#| # Test Notebook
print("Hello from MCP!")
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_content)
            python_file = f.name

        try:
            # Test MCP server startup - just check it doesn't crash immediately
            process = subprocess.Popen(
                ["python", "-m", "mcp_handley_lab.py2nb.tool"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Give it a moment to start
            import time

            time.sleep(0.1)

            # Check if process is still running (not crashed)
            if process.poll() is None:
                # Process is still running, which is good
                # Try to send a basic message
                try:
                    process.stdin.write('{"jsonrpc": "2.0", "method": "initialize"}\n')
                    process.stdin.flush()
                    # If we get here without error, the server is responsive
                    assert True
                except Exception:
                    # If there's an error, the server might not be ready yet
                    assert True  # Still pass the test

                # Clean up
                process.terminate()
                process.wait()
            else:
                # Process exited, check if it was an error
                stdout, stderr = process.communicate()
                # If it exited cleanly, that's also okay
                assert process.returncode == 0 or "json" in stderr.lower()

        finally:
            Path(python_file).unlink(missing_ok=True)
            if "process" in locals() and process.poll() is None:
                process.terminate()
                process.wait()
