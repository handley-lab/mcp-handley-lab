"""Integration tests for code2prompt tool using real CLI subprocess calls."""

import shutil
import tempfile
from pathlib import Path

import pytest
from mcp_handley_lab.code2prompt.tool import mcp


class TestCode2PromptIntegration:
    """Test code2prompt tool with real CLI subprocess calls."""

    @pytest.fixture
    def sample_project(self):
        """Create a temporary directory with sample source files."""
        temp_dir = Path(tempfile.mkdtemp())

        # Create some sample files
        (temp_dir / "main.py").write_text(
            '''#!/usr/bin/env python3
"""Main module for testing."""

def hello_world():
    """Print hello world."""
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
'''
        )

        (temp_dir / "utils.py").write_text(
            '''"""Utility functions."""

def add(a, b):
    """Add two numbers."""
    return a + b

def multiply(a, b):
    """Multiply two numbers."""
    return a * b
'''
        )

        (temp_dir / "README.md").write_text(
            """# Test Project

This is a test project for code2prompt integration testing.

## Features
- Hello world functionality
- Basic math utilities
"""
        )

        # Create a subdirectory
        subdir = temp_dir / "submodule"
        subdir.mkdir()
        (subdir / "helper.py").write_text(
            '''"""Helper functions."""

def format_output(text):
    """Format text output."""
    return f"[OUTPUT] {text}"
'''
        )

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_generate_prompt_basic_functionality(self, sample_project):
        """Test basic code2prompt generation with real CLI."""
        output_file = sample_project / "output.md"

        _, response = await mcp.call_tool(
            "generate_prompt",
            {"path": str(sample_project), "output_file": str(output_file)},
        )
        assert "error" not in response, response.get("error")
        result = response

        # Verify the output file was created
        assert output_file.exists()

        # Verify the result message indicates success
        assert "success" in result["message"].lower()

        # Verify the output contains expected content
        content = output_file.read_text()
        assert "main.py" in content
        assert "utils.py" in content
        assert "hello_world" in content
        assert "def add" in content

    @pytest.mark.asyncio
    async def test_generate_prompt_with_include_filter(self, sample_project):
        """Test code2prompt with include filter for Python files only."""
        output_file = sample_project / "python_only.md"

        _, response = await mcp.call_tool(
            "generate_prompt",
            {
                "path": str(sample_project),
                "include": ["*.py"],
                "output_file": str(output_file),
            },
        )
        assert "error" not in response, response.get("error")
        result = response

        assert output_file.exists()
        assert "success" in result["message"].lower()

        content = output_file.read_text()
        assert "main.py" in content
        assert "utils.py" in content
        # README.md should not be included
        assert "# Test Project" not in content

    @pytest.mark.asyncio
    async def test_generate_prompt_with_exclude_filter(self, sample_project):
        """Test code2prompt with exclude filter."""
        output_file = sample_project / "no_readme.md"

        _, response = await mcp.call_tool(
            "generate_prompt",
            {
                "path": str(sample_project),
                "exclude": ["*.md"],
                "output_file": str(output_file),
            },
        )
        assert "error" not in response, response.get("error")
        result = response

        assert output_file.exists()
        assert "success" in result["message"].lower()

        content = output_file.read_text()
        assert "main.py" in content
        assert "utils.py" in content
        # README.md content should not be included
        assert "# Test Project" not in content

    @pytest.mark.asyncio
    async def test_generate_prompt_line_numbers(self, sample_project):
        """Test code2prompt with line numbers enabled."""
        output_file = sample_project / "with_lines.md"

        _, response = await mcp.call_tool(
            "generate_prompt",
            {
                "path": str(sample_project),
                "line_numbers": True,
                "output_file": str(output_file),
            },
        )
        assert "error" not in response, response.get("error")
        result = response

        assert output_file.exists()
        assert "success" in result["message"].lower()

        content = output_file.read_text()
        # Should contain line numbers (code2prompt uses format like "   1 |")
        assert "   1 |" in content

    @pytest.mark.asyncio
    async def test_generate_prompt_full_directory_tree(self, sample_project):
        """Test code2prompt with full directory tree."""
        output_file = sample_project / "full_tree.md"

        _, response = await mcp.call_tool(
            "generate_prompt",
            {
                "path": str(sample_project),
                "full_directory_tree": True,
                "output_file": str(output_file),
            },
        )
        assert "error" not in response, response.get("error")
        result = response

        assert output_file.exists()
        assert "success" in result["message"].lower()

        content = output_file.read_text()
        # Should show directory structure
        assert "submodule" in content

    @pytest.mark.asyncio
    async def test_generate_prompt_nonexistent_path(self):
        """Test code2prompt with nonexistent path - should fail fast."""
        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="Command failed|not found|doesn't exist"):
            await mcp.call_tool(
                "generate_prompt",
                {
                    "path": "/nonexistent/path/123456",
                    "output_file": "/tmp/test_output.md",
                },
            )

    @pytest.mark.asyncio
    async def test_generate_prompt_invalid_template(self, sample_project):
        """Test code2prompt with invalid template path - should fail fast."""
        from mcp.server.fastmcp.exceptions import ToolError

        output_file = sample_project / "output.md"

        with pytest.raises(ToolError):
            await mcp.call_tool(
                "generate_prompt",
                {
                    "path": str(sample_project),
                    "template": "/nonexistent/template.txt",
                    "output_file": str(output_file),
                },
            )

    @pytest.mark.asyncio
    async def test_server_info_real_cli(self):
        """Test server_info with real code2prompt CLI."""
        try:
            _, response = await mcp.call_tool("server_info", {})
            assert "error" not in response, response.get("error")
            result = response

            assert result["status"] == "active"
            assert "Code2Prompt Tool" in result["name"]
            assert "generate_prompt" in result["capabilities"]
        except FileNotFoundError:
            pytest.skip("code2prompt CLI not installed")

    @pytest.mark.asyncio
    async def test_generate_prompt_complex_options(self, sample_project):
        """Test code2prompt with multiple complex options."""
        output_file = sample_project / "complex.md"

        _, response = await mcp.call_tool(
            "generate_prompt",
            {
                "path": str(sample_project),
                "include": ["*.py", "*.md"],
                "exclude": ["__pycache__"],
                "line_numbers": True,
                "full_directory_tree": True,
                "absolute_paths": True,
                "output_file": str(output_file),
            },
        )
        assert "error" not in response, response.get("error")
        result = response

        assert output_file.exists()
        assert "success" in result["message"].lower()

        content = output_file.read_text()
        assert len(content) > 100  # Should have substantial content

    @pytest.mark.asyncio
    async def test_generate_prompt_file_size_reporting(self, sample_project):
        """Test that file size is reported correctly."""
        output_file = sample_project / "sized.md"

        _, response = await mcp.call_tool(
            "generate_prompt",
            {"path": str(sample_project), "output_file": str(output_file)},
        )
        assert "error" not in response, response.get("error")
        result = response

        assert output_file.exists()
        # The result should include file size in the result object
        assert result["file_size_bytes"] > 0
        assert result["output_file_path"] == str(output_file)
