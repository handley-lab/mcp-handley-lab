"""Integration tests for vim tool - limited to non-interactive functionality."""

import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.vim.tool import server_info


class TestVimIntegration:
    """Test vim tool integration - focusing on non-hanging functionality."""

    def test_server_info_real_vim(self):
        """Test server_info with real vim CLI."""
        try:
            result = server_info()
            assert result.status == "active"
            assert "vim" in result.name.lower()
            assert "prompt_user_edit" in result.capabilities
            assert "quick_edit" in result.capabilities
            assert "open_file" in result.capabilities
        except FileNotFoundError:
            pytest.skip("vim command not installed")

    def test_vim_version_detection(self):
        """Test that vim version can be detected."""
        try:
            result = server_info()
            # Should contain vim version info
            dependencies = result.dependencies
            assert "vim" in dependencies
            # Version string should contain some version info
            vim_info = dependencies["vim"]
            assert vim_info  # Should not be empty
        except FileNotFoundError:
            pytest.skip("vim command not installed")

    def test_vim_non_interactive_edit(self):
        """Test that vim can be executed non-interactively to edit a file."""
        import subprocess

        initial_content = "Hello world\nLine 2\nLine 3"
        # The Vim Ex command: substitute 'world' with 'Vim' and write-quit
        vim_command = "s/world/Vim/g | wq"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(initial_content)
            f.flush()
            temp_path = f.name

        try:
            # Build the non-interactive vim command
            command = [
                "vim",
                "-u",
                "DEFAULTS",  # Use default settings, ignore user's .vimrc
                "-i",
                "NONE",  # Don't use .viminfo file (test isolation)
                "-n",  # No swap file
                "--not-a-term",  # Hint to vim it's not in a real terminal
                "-c",
                vim_command,  # Execute the command
                temp_path,
            ]

            # Execute vim non-interactively - should complete quickly
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,  # Prevent stdin deadlock
                timeout=5,  # Fail fast if hanging
            )

            # Verify the file was modified as expected
            modified_content = Path(temp_path).read_text()
            assert "Hello Vim" in modified_content
            assert "Line 2" in modified_content  # Other content preserved
            assert initial_content != modified_content

        except FileNotFoundError:
            pytest.skip("vim command not installed")
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_vim_availability_smoke_test(self):
        """Test that vim command is available and executable."""
        import subprocess

        try:
            result = subprocess.run(
                ["vim", "--version"], check=True, capture_output=True, text=True
            )
            assert "VIM - Vi IMproved" in result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("vim command not installed or not working")

    def test_vim_multiple_commands_single_execution(self):
        """Test vim with multiple commands in a single -c execution."""
        import subprocess

        initial_content = "Hello world\nGoodbye world\nAnother line"
        # Chain multiple Ex commands with | separator
        vim_commands = (
            "%s/world/Vim/g | %s/Hello/Greetings/g | %s/Goodbye/Farewell/g | wq"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(initial_content)
            f.flush()
            temp_path = f.name

        try:
            command = [
                "vim",
                "-u",
                "DEFAULTS",
                "-i",
                "NONE",
                "-n",
                "--not-a-term",
                "-c",
                vim_commands,
                temp_path,
            ]

            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=5,
            )

            # Verify all transformations were applied
            modified_content = Path(temp_path).read_text()
            assert "Greetings Vim" in modified_content
            assert "Farewell Vim" in modified_content
            assert "Another line" in modified_content

        except FileNotFoundError:
            pytest.skip("vim command not installed")
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_instruction_stripping_logic(self):
        """Test instruction stripping functionality without vim interaction."""
        from mcp_handley_lab.vim.tool import _strip_instructions

        content_with_instructions = """# Instructions: Edit this file carefully
# Make sure to follow Python conventions
# ============================================================

def hello():
    print("world")
"""

        result = _strip_instructions(
            content_with_instructions, "Edit this file carefully", ".py"
        )

        # Should strip instructions and separator
        assert "Instructions:" not in result
        assert "def hello():" in result

    def test_vim_error_handling_for_nonexistent_files(self):
        """Test that vim handles nonexistent files - documents the limitation."""
        import subprocess

        try:
            # Try to edit a nonexistent file with vim
            command = [
                "vim",
                "-u",
                "DEFAULTS",
                "-i",
                "NONE",
                "-n",
                "--not-a-term",
                "-c",
                "q!",  # Force quit without saving
                "/definitely/nonexistent/path/file.txt",
            ]

            # Vim may hang on file creation errors - use timeout
            subprocess.run(
                command,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=2,  # Short timeout since this often hangs
            )

        except FileNotFoundError:
            pytest.skip("vim command not installed")
