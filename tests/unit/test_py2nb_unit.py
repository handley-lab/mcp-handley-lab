"""Improved unit tests for py2nb conversion tool using tmp_path fixture."""
import json
from pathlib import Path

import pytest
from mcp_handley_lab.py2nb.converter import (
    _extract_content,
    _get_comment_type,
    _str_starts_with,
    notebook_to_python,
    python_to_notebook,
    validate_notebook_file,
    validate_python_file,
)


class TestCommentParsing:
    """Test comment parsing utilities."""

    def test_str_starts_with(self):
        """Test string prefix checking."""
        assert _str_starts_with("# hello", ["#", "//"])
        assert _str_starts_with("//hello", ["#", "//"])
        assert not _str_starts_with("hello", ["#", "//"])
        assert not _str_starts_with("", ["#", "//"])

    def test_get_comment_type(self):
        """Test comment type detection."""
        assert _get_comment_type("#| markdown content") == "markdown"
        assert _get_comment_type("# | markdown content") == "markdown"
        assert _get_comment_type("#! command content") == "command"
        assert _get_comment_type("# ! command content") == "command"
        assert _get_comment_type("#% magic command") == "command"
        assert _get_comment_type("# % magic command") == "command"
        assert _get_comment_type("#- cell separator") == "split"
        assert _get_comment_type("# - cell separator") == "split"
        assert _get_comment_type("# regular comment") is None
        assert _get_comment_type("print('hello')") is None

    def test_extract_content(self):
        """Test content extraction from comments."""
        # Markdown extraction
        assert (
            _extract_content("#| This is markdown", "markdown") == " This is markdown"
        )
        assert (
            _extract_content("# | This is markdown", "markdown") == " This is markdown"
        )

        # Command extraction
        assert _extract_content("#! ls -la", "command") == "!ls -la"
        assert _extract_content("# ! ls -la", "command") == "!ls -la"
        assert (
            _extract_content("#% matplotlib inline", "command") == "%matplotlib inline"
        )
        assert (
            _extract_content("# % matplotlib inline", "command") == "%matplotlib inline"
        )

        # Invalid type
        assert _extract_content("#| content", "invalid") == ""


class TestPythonToNotebook:
    """Test Python to notebook conversion."""

    def test_simple_conversion(self, tmp_path):
        """Test basic Python to notebook conversion."""
        python_file = tmp_path / "test_script.py"
        python_file.write_text(
            """print("Hello, World!")
x = 42
print(x)
"""
        )

        notebook_file = python_to_notebook(str(python_file))
        notebook_path = Path(notebook_file)

        assert notebook_path.exists()

        with open(notebook_path) as f:
            notebook_data = json.load(f)

        assert notebook_data["nbformat"] == 4
        assert len(notebook_data["cells"]) == 1
        assert notebook_data["cells"][0]["cell_type"] == "code"
        source_text = "".join(notebook_data["cells"][0]["source"])
        assert 'print("Hello, World!")' in source_text

    def test_markdown_cells(self, tmp_path):
        """Test markdown cell conversion."""
        python_file = tmp_path / "test_markdown.py"
        python_file.write_text(
            """#| # This is a heading
#| This is some markdown text
print("Hello")
"""
        )

        notebook_file = python_to_notebook(str(python_file))
        notebook_path = Path(notebook_file)

        with open(notebook_path) as f:
            notebook_data = json.load(f)

        assert len(notebook_data["cells"]) == 2

        # First cell should be markdown
        assert notebook_data["cells"][0]["cell_type"] == "markdown"
        markdown_text = "".join(notebook_data["cells"][0]["source"])
        assert "# This is a heading" in markdown_text
        assert "This is some markdown text" in markdown_text

        # Second cell should be code
        assert notebook_data["cells"][1]["cell_type"] == "code"
        code_text = "".join(notebook_data["cells"][1]["source"])
        assert 'print("Hello")' in code_text

    def test_command_cells(self, tmp_path):
        """Test command cell conversion."""
        python_file = tmp_path / "test_commands.py"
        python_file.write_text(
            """#! ls -la
#% matplotlib inline
print("Hello")
"""
        )

        notebook_file = python_to_notebook(str(python_file))
        notebook_path = Path(notebook_file)

        with open(notebook_path) as f:
            notebook_data = json.load(f)

        assert len(notebook_data["cells"]) == 2

        # First cell should be command with both commands
        assert notebook_data["cells"][0]["cell_type"] == "code"
        assert "command" in notebook_data["cells"][0]["metadata"]["tags"]
        command_text = "".join(notebook_data["cells"][0]["source"])
        assert "!ls -la" in command_text
        assert "%matplotlib inline" in command_text

        # Second cell should be regular code
        assert notebook_data["cells"][1]["cell_type"] == "code"
        assert "command" not in notebook_data["cells"][1]["metadata"].get("tags", [])

    def test_cell_separators(self, tmp_path):
        """Test cell separator handling."""
        python_file = tmp_path / "test_separators.py"
        python_file.write_text(
            """print("First cell")
#-
print("Second cell")
# -
print("Third cell")
"""
        )

        notebook_file = python_to_notebook(str(python_file))
        notebook_path = Path(notebook_file)

        with open(notebook_path) as f:
            notebook_data = json.load(f)

        assert len(notebook_data["cells"]) == 3

        # Verify each cell has the correct content
        cell0_text = "".join(notebook_data["cells"][0]["source"])
        cell1_text = "".join(notebook_data["cells"][1]["source"])
        cell2_text = "".join(notebook_data["cells"][2]["source"])
        assert "First cell" in cell0_text
        assert "Second cell" in cell1_text
        assert "Third cell" in cell2_text

    def test_mixed_content(self, tmp_path):
        """Test mixed content with all comment types."""
        python_file = tmp_path / "test_mixed.py"
        python_file.write_text(
            """#| # Data Analysis
#| This notebook analyzes data
#! import pandas as pd
#% matplotlib inline
import numpy as np
print("Starting analysis")
#-
#| ## Results
print("Results here")
"""
        )

        notebook_file = python_to_notebook(str(python_file))
        notebook_path = Path(notebook_file)

        with open(notebook_path) as f:
            notebook_data = json.load(f)

        # Should have markdown, command, code, markdown, code cells
        assert len(notebook_data["cells"]) >= 4

        # Find cells by type and content
        markdown_cells = [
            cell for cell in notebook_data["cells"] if cell["cell_type"] == "markdown"
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

        # Verify we have the right number of each cell type
        assert len(markdown_cells) == 2
        assert len(command_cells) == 1
        assert len(code_cells) >= 1

        # Verify content
        markdown_text = "".join(markdown_cells[0]["source"])
        assert "Data Analysis" in markdown_text

        command_text = "".join(command_cells[0]["source"])
        assert "import pandas as pd" in command_text

        code_text = "".join(code_cells[0]["source"])
        assert "numpy" in code_text

        results_text = "".join(markdown_cells[1]["source"])
        assert "Results" in results_text

    def test_file_not_found(self):
        """Test handling of non-existent file."""
        with pytest.raises(FileNotFoundError):
            python_to_notebook("/non/existent/file.py")

    def test_custom_output_path(self, tmp_path):
        """Test custom output path specification."""
        python_file = tmp_path / "test_script.py"
        python_file.write_text("print('test')")

        custom_output = tmp_path / "custom_notebook.ipynb"
        notebook_file = python_to_notebook(str(python_file), str(custom_output))

        assert notebook_file == str(custom_output)
        assert custom_output.exists()

    def test_empty_file(self, tmp_path):
        """Test conversion of empty Python file."""
        python_file = tmp_path / "empty.py"
        python_file.write_text("")

        notebook_file = python_to_notebook(str(python_file))
        notebook_path = Path(notebook_file)

        assert notebook_path.exists()

        with open(notebook_path) as f:
            notebook_data = json.load(f)

        assert notebook_data["nbformat"] == 4
        assert len(notebook_data["cells"]) == 0  # No cells for empty file

    def test_only_comments(self, tmp_path):
        """Test conversion of file with only comments."""
        python_file = tmp_path / "comments_only.py"
        python_file.write_text(
            """#| # Only Markdown
#| This file has only markdown comments
"""
        )

        notebook_file = python_to_notebook(str(python_file))
        notebook_path = Path(notebook_file)

        with open(notebook_path) as f:
            notebook_data = json.load(f)

        assert len(notebook_data["cells"]) == 1
        assert notebook_data["cells"][0]["cell_type"] == "markdown"
        markdown_text = "".join(notebook_data["cells"][0]["source"])
        assert "# Only Markdown" in markdown_text


class TestNotebookToPython:
    """Test notebook to Python conversion."""

    def test_simple_conversion(self, tmp_path):
        """Test basic notebook to Python conversion."""
        notebook_data = {
            "nbformat": 4,
            "nbformat_minor": 2,
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["print('Hello, World!')\n", "x = 42\n", "print(x)"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None,
                }
            ],
        }

        notebook_file = tmp_path / "test_notebook.ipynb"
        with open(notebook_file, "w") as f:
            json.dump(notebook_data, f)

        python_file = notebook_to_python(str(notebook_file))
        python_path = Path(python_file)

        assert python_path.exists()

        content = python_path.read_text()
        assert "print('Hello, World!')" in content
        assert "x = 42" in content
        assert "print(x)" in content

    def test_markdown_conversion(self, tmp_path):
        """Test markdown cell conversion."""
        notebook_data = {
            "nbformat": 4,
            "nbformat_minor": 2,
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": ["# This is a heading\n", "This is some markdown text\n"],
                    "metadata": {},
                },
                {
                    "cell_type": "code",
                    "source": ["print('Hello')\n"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None,
                },
            ],
        }

        notebook_file = tmp_path / "test_markdown.ipynb"
        with open(notebook_file, "w") as f:
            json.dump(notebook_data, f)

        python_file = notebook_to_python(str(notebook_file))
        python_path = Path(python_file)

        content = python_path.read_text()
        assert "#| # This is a heading" in content
        assert "#| This is some markdown text" in content
        assert "print('Hello')" in content

    def test_command_cell_conversion(self, tmp_path):
        """Test command cell conversion."""
        notebook_data = {
            "nbformat": 4,
            "nbformat_minor": 2,
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["!ls -la\n", "%matplotlib inline\n"],
                    "metadata": {"tags": ["command"]},
                    "outputs": [],
                    "execution_count": None,
                },
                {
                    "cell_type": "code",
                    "source": ["print('Hello')\n"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None,
                },
            ],
        }

        notebook_file = tmp_path / "test_commands.ipynb"
        with open(notebook_file, "w") as f:
            json.dump(notebook_data, f)

        python_file = notebook_to_python(str(notebook_file))
        python_path = Path(python_file)

        content = python_path.read_text()
        assert "#! ls -la" in content
        assert "#! %matplotlib inline" in content
        assert "print('Hello')" in content

    def test_cell_separators(self, tmp_path):
        """Test cell separator insertion."""
        notebook_data = {
            "nbformat": 4,
            "nbformat_minor": 2,
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["print('First')\n"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None,
                },
                {
                    "cell_type": "code",
                    "source": ["print('Second')\n"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None,
                },
            ],
        }

        notebook_file = tmp_path / "test_separators.ipynb"
        with open(notebook_file, "w") as f:
            json.dump(notebook_data, f)

        python_file = notebook_to_python(str(notebook_file))
        python_path = Path(python_file)

        content = python_path.read_text()
        assert "print('First')" in content
        assert "#-------------------------------" in content
        assert "print('Second')" in content

    def test_file_not_found(self):
        """Test handling of non-existent notebook file."""
        with pytest.raises(FileNotFoundError):
            notebook_to_python("/non/existent/file.ipynb")

    def test_custom_output_path(self, tmp_path):
        """Test custom output path specification."""
        notebook_data = {
            "nbformat": 4,
            "nbformat_minor": 2,
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["print('test')\n"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None,
                }
            ],
        }

        notebook_file = tmp_path / "test_notebook.ipynb"
        with open(notebook_file, "w") as f:
            json.dump(notebook_data, f)

        custom_output = tmp_path / "custom_script.py"
        python_file = notebook_to_python(str(notebook_file), str(custom_output))

        assert python_file == str(custom_output)
        assert custom_output.exists()

    def test_empty_notebook(self, tmp_path):
        """Test conversion of notebook with no cells."""
        notebook_data = {"nbformat": 4, "nbformat_minor": 2, "cells": []}

        notebook_file = tmp_path / "empty_notebook.ipynb"
        with open(notebook_file, "w") as f:
            json.dump(notebook_data, f)

        python_file = notebook_to_python(str(notebook_file))
        python_path = Path(python_file)

        assert python_path.exists()
        content = python_path.read_text()
        assert content.strip() == ""  # Should be empty or just whitespace

    def test_notebook_with_empty_cells(self, tmp_path):
        """Test conversion of notebook with empty cells."""
        notebook_data = {
            "nbformat": 4,
            "nbformat_minor": 2,
            "cells": [
                {
                    "cell_type": "code",
                    "source": [],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None,
                },
                {
                    "cell_type": "markdown",
                    "source": ["# Valid content\n"],
                    "metadata": {},
                },
            ],
        }

        notebook_file = tmp_path / "empty_cells.ipynb"
        with open(notebook_file, "w") as f:
            json.dump(notebook_data, f)

        python_file = notebook_to_python(str(notebook_file))
        python_path = Path(python_file)

        content = python_path.read_text()
        assert "#| # Valid content" in content  # Should handle empty cells gracefully


class TestValidation:
    """Test validation functions."""

    def test_validate_notebook_file_valid(self, tmp_path):
        """Test validation of valid notebook file."""
        notebook_data = {
            "nbformat": 4,
            "nbformat_minor": 2,
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["print('test')\n"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None,
                }
            ],
        }

        notebook_file = tmp_path / "valid_notebook.ipynb"
        with open(notebook_file, "w") as f:
            json.dump(notebook_data, f)

        assert validate_notebook_file(str(notebook_file))

    def test_validate_notebook_file_invalid_json(self, tmp_path):
        """Test validation of invalid JSON file."""
        notebook_file = tmp_path / "invalid.ipynb"
        notebook_file.write_text("invalid json content")

        assert not validate_notebook_file(str(notebook_file))

    def test_validate_notebook_file_missing_cells(self, tmp_path):
        """Test validation of notebook missing cells."""
        notebook_data = {"nbformat": 4, "nbformat_minor": 2}

        notebook_file = tmp_path / "missing_cells.ipynb"
        with open(notebook_file, "w") as f:
            json.dump(notebook_data, f)

        assert not validate_notebook_file(str(notebook_file))

    def test_validate_notebook_file_not_found(self):
        """Test validation of non-existent file."""
        assert not validate_notebook_file("/non/existent/file.ipynb")

    def test_validate_python_file_valid(self, tmp_path):
        """Test validation of valid Python file."""
        python_file = tmp_path / "valid.py"
        python_file.write_text("print('Hello, World!')\nx = 42\nprint(x)")

        assert validate_python_file(str(python_file))

    def test_validate_python_file_syntax_error(self, tmp_path):
        """Test validation of Python file with syntax error."""
        python_file = tmp_path / "invalid.py"
        python_file.write_text("print('Hello, World!'\n# Missing closing parenthesis")

        assert not validate_python_file(str(python_file))

    def test_validate_python_file_not_found(self):
        """Test validation of non-existent Python file."""
        assert not validate_python_file("/non/existent/file.py")
