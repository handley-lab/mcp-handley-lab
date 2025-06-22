"""Tests for Vim tool."""
import pytest
from unittest.mock import Mock, patch, mock_open
import tempfile
import os

from mcp_framework.vim.tool import (
    prompt_user_edit, quick_edit, open_file, server_info,
    _handle_instructions_and_content, _strip_instructions
)


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_handle_instructions_and_content_with_instructions(self):
        """Test writing content with instructions."""
        mock_open_func = mock_open()
        with patch('builtins.open', mock_open_func):
            _handle_instructions_and_content(
                "/tmp/test.py", 
                ".py", 
                "This is a test instruction\nSecond line", 
                "print('hello')"
            )
        
        mock_open_func.assert_called_once_with("/tmp/test.py", "w")
        handle = mock_open_func()
        
        # Check the writes
        expected_calls = [
            Mock(call=('write', ('# This is a test instruction\n',), {})),
            Mock(call=('write', ('# Second line\n',), {})),
            Mock(call=('write', ('# ============================================================\n\n',), {})),
            Mock(call=('write', ("print('hello')",), {}))
        ]
        
        # Verify content was written
        written_content = ''.join([call.args[0] for call in handle.write.call_args_list])
        assert "# This is a test instruction" in written_content
        assert "# Second line" in written_content
        assert "# ========" in written_content
        assert "print('hello')" in written_content
    
    def test_handle_instructions_and_content_without_instructions(self):
        """Test writing content without instructions."""
        mock_open_func = mock_open()
        with patch('builtins.open', mock_open_func):
            _handle_instructions_and_content(
                "/tmp/test.txt", 
                ".txt", 
                "", 
                "Hello world"
            )
        
        handle = mock_open_func()
        written_content = ''.join([call.args[0] for call in handle.write.call_args_list])
        assert written_content == "Hello world"
    
    def test_handle_instructions_and_content_js_comments(self):
        """Test writing content with JavaScript-style comments."""
        mock_open_func = mock_open()
        with patch('builtins.open', mock_open_func):
            _handle_instructions_and_content(
                "/tmp/test.js", 
                ".js", 
                "JavaScript instruction", 
                "console.log('hello');"
            )
        
        handle = mock_open_func()
        written_content = ''.join([call.args[0] for call in handle.write.call_args_list])
        assert "// JavaScript instruction" in written_content
        assert "// ========" in written_content
    
    def test_strip_instructions_with_python_comments(self):
        """Test stripping instructions from Python content."""
        content = """# Test instruction
# Another line
# ============================================================

print('hello')
print('world')"""
        
        result = _strip_instructions(content, "Test instruction", ".py")
        
        assert result == "print('hello')\nprint('world')"
    
    def test_strip_instructions_with_js_comments(self):
        """Test stripping instructions from JavaScript content."""
        content = """// Test instruction
// ============================================================

console.log('hello');"""
        
        result = _strip_instructions(content, "Test instruction", ".js")
        
        assert result == "console.log('hello');"
    
    def test_strip_instructions_without_instructions(self):
        """Test stripping when no instructions provided."""
        content = "print('hello')"
        
        result = _strip_instructions(content, "", ".py")
        
        assert result == "print('hello')"
    
    def test_strip_instructions_no_separator_found(self):
        """Test stripping when separator is not found."""
        content = "print('hello')"
        
        result = _strip_instructions(content, "Some instruction", ".py")
        
        assert result == "print('hello')"


class TestPromptUserEdit:
    """Test prompt_user_edit function."""
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    @patch('mcp_framework.vim.tool.tempfile.mkstemp')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.close')
    @patch('os.unlink')
    def test_prompt_user_edit_basic(self, mock_unlink, mock_close, mock_file, 
                                   mock_mkstemp, mock_subprocess):
        """Test basic prompt user edit functionality."""
        mock_mkstemp.return_value = (3, "/tmp/test.txt")
        
        # Mock file reading to return edited content
        mock_file.return_value.read.return_value = "Hello, world!\nEdited content"
        
        result = prompt_user_edit(
            content="Hello, world!",
            file_extension=".txt",
            show_diff=False
        )
        
        assert result == "Hello, world!\nEdited content"
        mock_subprocess.assert_called_once_with(['vim', '/tmp/test.txt'], check=True)
        mock_close.assert_called_once_with(3)
        mock_unlink.assert_called_once_with("/tmp/test.txt")
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    @patch('mcp_framework.vim.tool.tempfile.mkstemp')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.close')
    @patch('os.unlink')
    def test_prompt_user_edit_with_instructions(self, mock_unlink, mock_close, mock_file, 
                                               mock_mkstemp, mock_subprocess):
        """Test prompt user edit with instructions."""
        mock_mkstemp.return_value = (3, "/tmp/test.py")
        
        # Mock file reading to return content without instructions
        mock_file.return_value.read.return_value = """# Edit this file
# ============================================================

print('hello')
print('edited')"""
        
        result = prompt_user_edit(
            content="print('hello')",
            file_extension=".py",
            instructions="Edit this file",
            show_diff=False
        )
        
        assert result == "print('hello')\nprint('edited')"
        mock_subprocess.assert_called_once_with(['vim', '/tmp/test.py'], check=True)
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    @patch('mcp_framework.vim.tool.tempfile.mkstemp')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.close')
    @patch('os.unlink')
    def test_prompt_user_edit_with_diff(self, mock_unlink, mock_close, mock_file, 
                                       mock_mkstemp, mock_subprocess):
        """Test prompt user edit with diff output."""
        mock_mkstemp.return_value = (3, "/tmp/test.txt")
        
        # Mock file reading to return edited content
        mock_file.return_value.read.return_value = "Hello, world!\nEdited line"
        
        result = prompt_user_edit(
            content="Hello, world!\nOriginal line",
            show_diff=True
        )
        
        assert "Changes made:" in result
        assert "lines added" in result
        assert "lines removed" in result
        mock_subprocess.assert_called_once_with(['vim', '/tmp/test.txt'], check=True)
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    @patch('mcp_framework.vim.tool.tempfile.mkstemp')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.close')
    @patch('os.unlink')
    def test_prompt_user_edit_no_changes(self, mock_unlink, mock_close, mock_file, 
                                        mock_mkstemp, mock_subprocess):
        """Test prompt user edit when no changes are made."""
        mock_mkstemp.return_value = (3, "/tmp/test.txt")
        
        # Mock file reading to return same content
        mock_file.return_value.read.return_value = "Hello, world!"
        
        result = prompt_user_edit(
            content="Hello, world!",
            show_diff=True
        )
        
        assert result == "No changes made"
        mock_subprocess.assert_called_once_with(['vim', '/tmp/test.txt'], check=True)
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    @patch('mcp_framework.vim.tool.tempfile.mkstemp')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.close')
    def test_prompt_user_edit_keep_file(self, mock_close, mock_file, 
                                       mock_mkstemp, mock_subprocess):
        """Test prompt user edit with keep_file=True."""
        mock_mkstemp.return_value = (3, "/tmp/test.txt")
        mock_file.return_value.read.return_value = "Hello, world!"
        
        with patch('os.unlink') as mock_unlink:
            result = prompt_user_edit(
                content="Hello, world!",
                keep_file=True,
                show_diff=False
            )
            
            assert result == "Hello, world!"
            mock_unlink.assert_not_called()


class TestQuickEdit:
    """Test quick_edit function."""
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    @patch('mcp_framework.vim.tool.tempfile.mkstemp')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.close')
    @patch('os.unlink')
    def test_quick_edit_basic(self, mock_unlink, mock_close, mock_file, 
                             mock_mkstemp, mock_subprocess):
        """Test basic quick edit functionality."""
        mock_mkstemp.return_value = (3, "/tmp/test.txt")
        mock_file.return_value.read.return_value = "New content created"
        
        result = quick_edit(file_extension=".txt")
        
        assert result == "New content created"
        mock_subprocess.assert_called_once_with(['vim', '/tmp/test.txt'], check=True)
        mock_close.assert_called_once_with(3)
        mock_unlink.assert_called_once_with("/tmp/test.txt")
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    @patch('mcp_framework.vim.tool.tempfile.mkstemp')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.close')
    @patch('os.unlink')
    def test_quick_edit_with_instructions(self, mock_unlink, mock_close, mock_file, 
                                         mock_mkstemp, mock_subprocess):
        """Test quick edit with instructions."""
        mock_mkstemp.return_value = (3, "/tmp/test.py")
        
        # Mock file reading to return content without instructions
        mock_file.return_value.read.return_value = """# Create a Python script
# ============================================================

print('Hello, world!')"""
        
        result = quick_edit(
            file_extension=".py",
            instructions="Create a Python script"
        )
        
        assert result == "print('Hello, world!')"
        mock_subprocess.assert_called_once_with(['vim', '/tmp/test.py'], check=True)
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    @patch('mcp_framework.vim.tool.tempfile.mkstemp')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.close')
    @patch('os.unlink')
    def test_quick_edit_with_initial_content(self, mock_unlink, mock_close, mock_file, 
                                            mock_mkstemp, mock_subprocess):
        """Test quick edit with initial content."""
        mock_mkstemp.return_value = (3, "/tmp/test.txt")
        mock_file.return_value.read.return_value = "Initial content\nEdited content"
        
        result = quick_edit(
            initial_content="Initial content"
        )
        
        assert result == "Initial content\nEdited content"
        mock_subprocess.assert_called_once_with(['vim', '/tmp/test.txt'], check=True)


class TestOpenFile:
    """Test open_file function."""
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    @patch('mcp_framework.vim.tool.Path')
    def test_open_file_basic(self, mock_path_class, mock_subprocess):
        """Test basic open file functionality."""
        # Mock Path object
        mock_path = Mock()
        mock_path.read_text.side_effect = ["Original content", "Edited content"]
        mock_path.suffix = ".txt"
        mock_path.__str__ = Mock(return_value="/tmp/test.txt")
        mock_backup_path = Mock()
        mock_path.with_suffix.return_value = mock_backup_path
        mock_path_class.return_value = mock_path
        
        result = open_file(
            file_path="/tmp/test.txt",
            show_diff=False
        )
        
        assert "File edited: /tmp/test.txt" in result
        mock_subprocess.assert_called_once_with(['vim', '/tmp/test.txt'], check=True)
        mock_backup_path.write_text.assert_called_once_with("Original content")
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    @patch('mcp_framework.vim.tool.tempfile.mkstemp')
    @patch('mcp_framework.vim.tool.Path')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.unlink')
    @patch('os.fdopen')
    def test_open_file_with_instructions(self, mock_fdopen, mock_unlink, mock_file, mock_path_class, 
                                        mock_mkstemp, mock_subprocess):
        """Test open file with instructions."""
        mock_mkstemp.return_value = (3, "/tmp/instructions.txt")
        
        # Mock fdopen to return a mock file
        mock_fdopen.return_value.__enter__ = Mock(return_value=Mock())
        mock_fdopen.return_value.__exit__ = Mock(return_value=None)
        
        # Mock Path object
        mock_path = Mock()
        mock_path.read_text.side_effect = ["Original content", "Edited content"]
        mock_path.suffix = ".txt"
        mock_path.__str__ = Mock(return_value="/tmp/test.txt")
        mock_backup_path = Mock()
        mock_path.with_suffix.return_value = mock_backup_path
        mock_path_class.return_value = mock_path
        
        result = open_file(
            file_path="/tmp/test.txt",
            instructions="Edit this file carefully",
            show_diff=False
        )
        
        assert "File edited: /tmp/test.txt" in result
        # Should call vim twice: once for instructions, once for actual file
        assert mock_subprocess.call_count == 2
        mock_unlink.assert_called_once_with("/tmp/instructions.txt")
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    @patch('mcp_framework.vim.tool.Path')
    def test_open_file_with_diff(self, mock_path_class, mock_subprocess):
        """Test open file with diff output."""
        # Mock Path object
        mock_path = Mock()
        mock_path.read_text.side_effect = ["Original content\nLine 2", "Edited content\nLine 2\nLine 3"]
        mock_path.suffix = ".txt"
        mock_path.__str__ = Mock(return_value="/tmp/test.txt")
        mock_backup_path = Mock()
        mock_backup_path.__str__ = Mock(return_value="/tmp/test.txt.bak")
        mock_path.with_suffix.return_value = mock_backup_path
        mock_path_class.return_value = mock_path
        
        result = open_file(
            file_path="/tmp/test.txt",
            show_diff=True,
            backup=True
        )
        
        assert "File edited: /tmp/test.txt" in result
        assert "Changes:" in result
        assert "lines added" in result
        assert "Backup saved to:" in result
        mock_backup_path.write_text.assert_called_once_with("Original content\nLine 2")
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    @patch('mcp_framework.vim.tool.Path')
    def test_open_file_no_changes(self, mock_path_class, mock_subprocess):
        """Test open file when no changes are made."""
        # Mock Path object
        mock_path = Mock()
        mock_path.read_text.return_value = "Same content"
        mock_path_class.return_value = mock_path
        
        result = open_file(
            file_path="/tmp/test.txt",
            show_diff=True,
            backup=False
        )
        
        assert "No changes made to /tmp/test.txt" in result
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    @patch('mcp_framework.vim.tool.Path')
    def test_open_file_no_backup(self, mock_path_class, mock_subprocess):
        """Test open file without backup."""
        # Mock Path object
        mock_path = Mock()
        mock_path.read_text.side_effect = ["Original", "Edited"]
        mock_path_class.return_value = mock_path
        
        result = open_file(
            file_path="/tmp/test.txt",
            backup=False,
            show_diff=False
        )
        
        assert "File edited: /tmp/test.txt" in result
        assert "Backup saved to:" not in result


class TestServerInfo:
    """Test server_info function."""
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    def test_server_info_success(self, mock_subprocess):
        """Test successful server info."""
        mock_result = Mock()
        mock_result.stdout = "VIM - Vi IMproved 8.2 (2019 Dec 12, compiled Oct 01 2021 01:51:08)\nIncluded patches: 1-2434"
        mock_subprocess.return_value = mock_result
        
        result = server_info()
        
        assert "Vim Tool Server Status" in result
        assert "Connected and ready" in result
        assert "VIM - Vi IMproved 8.2" in result
        assert "prompt_user_edit" in result
        assert "quick_edit" in result
        assert "open_file" in result
        mock_subprocess.assert_called_once_with(['vim', '--version'], capture_output=True, text=True)
    
    @patch('mcp_framework.vim.tool.subprocess.run')
    def test_server_info_vim_not_found(self, mock_subprocess):
        """Test server info when vim is not found."""
        mock_subprocess.side_effect = FileNotFoundError("vim command not found")
        
        with pytest.raises(RuntimeError) as exc_info:
            server_info()
        
        assert "vim command not found" in str(exc_info.value)
        mock_subprocess.assert_called_once_with(['vim', '--version'], capture_output=True, text=True)