import pytest
import json
import tempfile
import subprocess
from unittest.mock import patch, Mock, mock_open
from pathlib import Path
from mcp_handley_lab.jq.tool import query, edit, validate, format as jq_format, read
from mcp_handley_lab.vim.tool import prompt_user_edit, open_file, quick_edit
from mcp_handley_lab.code2prompt.tool import generate_prompt

class TestJQUnit:
    
    @pytest.mark.parametrize("data,filter,expected", [
        ('{"test": "value"}', '.test', '"value"'),
        ('{"numbers": [1,2,3]}', '.numbers | length', '3'),
        ('{"nested": {"key": "val"}}', '.nested.key', '"val"'),
        ('{"a": null}', '.a', 'null'),
        ('[]', 'length', '0'),
        ('{}', '.missing_key', 'null'),
        ('[1,2,3]', '.[1]', '2'),
        ('{"array": [1,2,3]}', '.array[0]', '1'),
    ])
    @patch('subprocess.run')
    def test_query_parameterized(self, mock_run, data, filter, expected):
        mock_run.return_value.stdout = expected
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0
        
        result = query(data=data, filter=filter)
        assert expected in result
        mock_run.assert_called()
    
    def test_edit_validation(self):
        with pytest.raises(ValueError):
            edit(file_path="", filter=".test")
        
        # Create a temporary file for filter validation
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"test": "value"}, f)
            f.flush()
            
            try:
                with pytest.raises(ValueError):
                    edit(file_path=f.name, filter="")
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @patch('subprocess.run')
    def test_validate_valid_json(self, mock_run):
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0
        
        result = validate(data='{"valid": true}')
        assert "valid" in result.lower()
    
    @patch('subprocess.run')
    def test_validate_invalid_json(self, mock_run):
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "parse error"
        mock_run.return_value.returncode = 1
        
        with pytest.raises(ValueError):
            validate(data='{"invalid": json}')
    
    @patch('subprocess.run')
    def test_format_compact(self, mock_run):
        mock_run.return_value.stdout = '{"compact":true}'
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0
        
        result = jq_format(data='{"compact": true}', compact=True)
        assert "compact" in result
    
    @patch('subprocess.run')
    def test_edit_success(self, mock_run):
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"test": "value"}, f)
            f.flush()
            
            try:
                result = edit(file_path=f.name, filter='.test = "new_value"')
                assert "success" in result.lower() or "updated" in result.lower()
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @patch('subprocess.run')  
    def test_query_compact_raw(self, mock_run):
        mock_run.return_value.stdout = "value"
        mock_run.return_value.returncode = 0
        
        result = query('{"test": "value"}', '.test', compact=True, raw_output=True)
        assert "value" in result
        
        # Verify compact and raw flags were used
        call_args = mock_run.call_args[0][0]
        assert "-c" in call_args
        assert "-r" in call_args
    
    @patch('subprocess.run')
    def test_query_file_path(self, mock_run):
        mock_run.return_value.stdout = '"value"'
        mock_run.return_value.returncode = 0
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write('{"test": "value"}')
            f.flush()
            
            try:
                result = query(f.name, '.test')
                assert '"value"' in result
                
                # Verify file path was passed to jq
                call_args = mock_run.call_args[0][0]
                assert f.name in call_args
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @patch('subprocess.run')
    def test_read_file(self, mock_run):
        mock_run.return_value.stdout = '{"formatted": true}'
        mock_run.return_value.returncode = 0
        
        result = read("/tmp/test.json", ".formatted")
        assert "formatted" in result
    
    @pytest.mark.parametrize("data,filter,error_msg,expected_exception", [
        ('{"test": "value"}', 'invalid..filter', 'jq error: invalid filter', ValueError),
        ('invalid json', '.test', 'Invalid JSON', ValueError),
        ('{"test": "value"}', '.nonexistent | error', 'Cannot index', ValueError),
        ('[]', '.[10]', 'Cannot index array with string', ValueError),
    ])
    @patch('subprocess.run')
    def test_jq_error_handling_parameterized(self, mock_run, data, filter, error_msg, expected_exception):
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "jq", stderr=error_msg)
        
        with pytest.raises(expected_exception, match="jq error"):
            query(data, filter)
    
    @patch('subprocess.run')
    def test_query_with_dict_input(self, mock_run):
        """Test query with dict input (line 20)."""
        mock_run.return_value.stdout = '"Alice"'
        mock_run.return_value.returncode = 0
        
        # Pass dict directly (FastMCP auto-parses JSON to dict)
        result = query({"name": "Alice"}, '.name')
        assert '"Alice"' in result
    
    @patch('subprocess.run')
    def test_query_with_list_input(self, mock_run):
        """Test query with list input (line 20)."""
        mock_run.return_value.stdout = '3'
        mock_run.return_value.returncode = 0
        
        # Pass list directly (FastMCP auto-parses JSON to list)
        result = query([1, 2, 3], 'length')
        assert '3' in result
    
    @patch('subprocess.run')
    def test_query_with_non_string_fallback(self, mock_run):
        """Test query with non-string data fallback (line 30)."""
        mock_run.return_value.stdout = '123'
        mock_run.return_value.returncode = 0
        
        # Pass integer (should convert to string)
        result = query(123, '.')
        assert '123' in result
    
    @patch('subprocess.run')
    def test_jq_command_not_found(self, mock_run):
        """Test jq command not found error (lines 46-47)."""
        mock_run.side_effect = FileNotFoundError("jq: command not found")
        
        with pytest.raises(RuntimeError, match="jq command not found"):
            query('{"test": "value"}', '.test')
    
    def test_format_pretty_print(self):
        """Test non-compact formatting (line 249)."""
        data = '{"b": 2, "a": 1}'
        result = jq_format(data, compact=False, sort_keys=True)
        
        # Should have indentation (non-compact)
        assert '{\n' in result
        assert '"a"' in result
        assert '"b"' in result
    
    @patch('mcp_handley_lab.jq.tool._run_jq')
    def test_server_info_success(self, mock_run_jq):
        """Test server_info function (lines 255-271)."""
        from mcp_handley_lab.jq.tool import server_info
        
        mock_run_jq.return_value = "jq-1.6"
        
        result = server_info()
        assert "JQ Tool Server Status" in result
        assert "jq-1.6" in result
        assert "Connected and ready" in result
        assert "query:" in result
        assert "edit:" in result
        assert "validate:" in result
    
    @patch('mcp_handley_lab.jq.tool._run_jq')
    def test_server_info_error(self, mock_run_jq):
        """Test server_info error handling (line 271)."""
        from mcp_handley_lab.jq.tool import server_info
        
        mock_run_jq.side_effect = RuntimeError("jq command not found")
        
        with pytest.raises(RuntimeError, match="jq command not found"):
            server_info()

class TestVimUnit:
    
    @pytest.mark.parametrize("file_ext,initial_content,show_diff,expected_in_result", [
        (".py", "print('hello')", False, "hello"),
        (".txt", "Hello World", False, "hello world"),
        (".md", "# Heading", False, "heading"),
        (".py", "", False, "content"),
        (".js", "console.log('test')", True, "changes"),
    ])
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_prompt_user_edit_parameterized(self, mock_file, mock_run, file_ext, initial_content, show_diff, expected_in_result):
        mock_file.return_value.read.return_value = initial_content or "default content"
        mock_run.return_value = None
        
        result = prompt_user_edit(initial_content, file_extension=file_ext, show_diff=show_diff)
        assert expected_in_result in result.lower()
        mock_run.assert_called_once()
    
    
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_prompt_user_edit_with_diff(self, mock_file, mock_run):
        # First read returns original, second returns modified
        mock_file.return_value.read.side_effect = ["original content", "modified content"]
        mock_run.return_value = None
        
        result = prompt_user_edit("original content", show_diff=True)
        assert "Changes made:" in result or "No changes made" in result
    
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open, read_data="test content")
    def test_prompt_user_edit_with_instructions(self, mock_file, mock_run):
        mock_run.return_value = None
        result = prompt_user_edit(
            "test content", 
            instructions="Edit this file",
            file_extension=".py"
        )
        assert "test content" in result or "no changes" in result.lower()
    
    @patch('subprocess.run')
    @patch('pathlib.Path.read_text')
    @patch('pathlib.Path.write_text')
    def test_open_file_success(self, mock_write, mock_read, mock_run):
        mock_run.return_value = None
        mock_read.return_value = "file content"
        mock_write.return_value = None
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("file content")
            
            try:
                result = open_file(f.name, show_diff=False)
                assert "file edited" in result.lower() or "backup saved" in result.lower()
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open, read_data="quick content")
    def test_quick_edit_success(self, mock_file, mock_run):
        mock_run.return_value = None
        result = quick_edit(initial_content="test", file_extension=".txt")
        assert "quick content" in result or "created successfully" in result.lower()
    
    @patch('subprocess.run')
    @patch('pathlib.Path.read_text')
    @patch('pathlib.Path.write_text')
    def test_open_file_with_backup(self, mock_write, mock_read, mock_run):
        mock_read.return_value = "original content"
        mock_write.return_value = None
        mock_run.return_value = None
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("original content")
            
            try:
                result = open_file(f.name, backup=True, show_diff=False)
                assert "backup saved" in result.lower()
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @patch('subprocess.run')
    @patch('pathlib.Path.read_text')
    @patch('pathlib.Path.write_text')
    def test_open_file_with_instructions(self, mock_write, mock_read, mock_run):
        mock_read.return_value = "original content"
        mock_write.return_value = None
        mock_run.return_value = None
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("original content")
            
            try:
                result = open_file(f.name, instructions="Edit this file carefully")
                assert "file edited" in result.lower() or "no changes" in result.lower()
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @patch('subprocess.run')  
    @patch('pathlib.Path.read_text')
    @patch('pathlib.Path.write_text')
    def test_open_file_with_diff(self, mock_write, mock_read, mock_run):
        # Return different content to trigger diff
        mock_read.side_effect = ["original content", "different content"]
        mock_write.return_value = None
        mock_run.return_value = None
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("original content")
            
            try:
                result = open_file(f.name, show_diff=True)
                assert "changes made" in result.lower() or "diff" in result.lower()
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @patch('subprocess.run')
    def test_vim_server_info(self, mock_run):
        mock_run.return_value.stdout = "VIM - Vi IMproved 8.2"
        mock_run.return_value.returncode = 0
        
        from mcp_handley_lab.vim.tool import server_info
        result = server_info()
        assert "vim" in result.lower() and "status" in result.lower()
    
    @patch('os.isatty')
    @patch('subprocess.run')
    def test_run_vim_no_tty(self, mock_run, mock_isatty):
        """Test vim without TTY (line 19)."""
        from mcp_handley_lab.vim.tool import _run_vim
        
        mock_isatty.return_value = False  # No TTY
        mock_run.return_value = None
        
        _run_vim("/tmp/test.txt")
        mock_run.assert_called()
        
        # Should call subprocess.run without special handling
        call_args = mock_run.call_args[0][0]
        assert 'vim' in call_args
        assert '/tmp/test.txt' in call_args
    
    @patch('os.isatty')
    @patch('subprocess.run')
    def test_run_vim_with_tty(self, mock_run, mock_isatty):
        """Test vim with TTY (line 19)."""
        from mcp_handley_lab.vim.tool import _run_vim
        
        mock_isatty.return_value = True  # TTY available
        mock_run.return_value = None
        
        _run_vim("/tmp/test.txt")
        mock_run.assert_called()
        
        # Should call subprocess.run 
        call_args = mock_run.call_args[0][0]
        assert 'vim' in call_args
        assert '/tmp/test.txt' in call_args
    
    def test_strip_instructions_with_separator(self):
        """Test instruction stripping with separator line (line 48)."""
        from mcp_handley_lab.vim.tool import _strip_instructions
        
        content = """# Instructions here
# More instructions
# ============================================================

actual content
more content"""
        
        result = _strip_instructions(content, "Instructions here", ".py")
        assert result == "actual content\nmore content"
    
    @patch('subprocess.run') 
    @patch('builtins.open', new_callable=mock_open, read_data="original content")
    def test_prompt_user_edit_with_changes(self, mock_file, mock_run):
        """Test diff calculation when changes are made (lines 143-147)."""
        from mcp_handley_lab.vim.tool import prompt_user_edit
        
        # Mock vim writing different content
        def side_effect(*args, **kwargs):
            # Simulate vim changing the file
            mock_file.return_value.read.return_value = "new content\nadded line"
        
        mock_run.side_effect = side_effect
        mock_file.return_value.read.return_value = "new content\nadded line"
        
        result = prompt_user_edit("original content", show_diff=True)
        
        # Should show added/removed line counts
        assert ("added" in result and "removed" in result) or "Changes made" in result
    
    @pytest.mark.parametrize("exception,error_msg,expected_exception", [
        (FileNotFoundError("vim: command not found"), "vim command not found", FileNotFoundError),
        (PermissionError("Permission denied"), "Permission denied", PermissionError),
        (subprocess.CalledProcessError(1, "vim", stderr="Vim error"), "Vim error", subprocess.CalledProcessError),
    ])
    @patch('subprocess.run')
    def test_vim_error_handling_parameterized(self, mock_run, exception, error_msg, expected_exception):
        """Test various vim error conditions."""
        from mcp_handley_lab.vim.tool import _run_vim
        
        mock_run.side_effect = exception
        
        with pytest.raises(expected_exception):
            _run_vim("/tmp/test.txt")
    
    @patch('subprocess.run')
    def test_server_info_vim_not_found(self, mock_run):
        """Test server_info when vim not found (lines 386-387)."""
        from mcp_handley_lab.vim.tool import server_info
        
        mock_run.side_effect = FileNotFoundError("vim: command not found")
        
        with pytest.raises(RuntimeError, match="vim command not found"):
            server_info()

class TestCode2PromptUnit:
    
    def test_generate_prompt_validation(self):
        with pytest.raises(ValueError):
            generate_prompt(path="")
    
    @patch('subprocess.run')
    @patch('pathlib.Path.stat')
    def test_generate_prompt_success(self, mock_stat, mock_run):
        mock_run.return_value.stdout = "Generated prompt successfully"
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0
        mock_stat.return_value.st_size = 1024  # Mock file size
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
                f.write("test content")
                
            try:
                result = generate_prompt(
                    path=temp_dir,
                    output_file=f.name
                )
                assert "success" in result.lower()
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @patch('subprocess.run')
    def test_generate_prompt_with_filters(self, mock_run):
        mock_run.return_value.stdout = "Generated with filters"
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
                f.write("test content")

            try:
                result = generate_prompt(
                    path=temp_dir,
                    include=["*.py"],
                    exclude=["__pycache__"],
                    output_file=f.name
                )
                assert "success" in result.lower() or "generated" in result.lower()
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @pytest.mark.parametrize("exception,error_msg,expected_exception", [
        (subprocess.CalledProcessError(1, "code2prompt", stderr="Command failed"), "code2prompt error", ValueError),
        (subprocess.CalledProcessError(2, "code2prompt", stderr="Invalid path"), "code2prompt error", ValueError),
        (FileNotFoundError("code2prompt not found"), "code2prompt command not found", RuntimeError),
        (PermissionError("Permission denied"), "Permission denied", PermissionError),
    ])
    @patch('subprocess.run')
    def test_code2prompt_error_handling_parameterized(self, mock_run, exception, error_msg, expected_exception):
        """Test various code2prompt error conditions."""
        mock_run.side_effect = exception
        
        with pytest.raises(expected_exception):
            generate_prompt(path="/tmp/test")
    
    
    @patch('subprocess.run')
    @patch('pathlib.Path.stat')
    def test_generate_prompt_all_options(self, mock_stat, mock_run):
        mock_run.return_value.stdout = "Generated with all options"
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0
        mock_stat.return_value.st_size = 2048
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
                f.write("test content")
                
                result = generate_prompt(
                    path=temp_dir,
                    output_file=f.name,
                    include_priority=True,
                    template="/tmp/template.txt",
                    no_ignore=True,
                    line_numbers=True,
                    full_directory_tree=True,
                    follow_symlinks=True,
                    hidden=True,
                    no_codeblock=True,
                    absolute_paths=True,
                    include_git_diff=True,
                    git_diff_branch1="main",
                    git_diff_branch2="feature"
                )
                assert "success" in result.lower()
                
                Path(f.name).unlink(missing_ok=True)
    
    @patch('subprocess.run')
    @patch('pathlib.Path.stat')
    def test_generate_prompt_git_options(self, mock_stat, mock_run):
        mock_run.return_value.stdout = "Generated with git options"
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0
        mock_stat.return_value.st_size = 1024
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
                f.write("test content")
                
                result = generate_prompt(
                    path=temp_dir,
                    output_file=f.name,
                    git_log_branch1="v1.0.0",
                    git_log_branch2="HEAD"
                )
                assert "success" in result.lower()
                
                Path(f.name).unlink(missing_ok=True)
    
    @patch('subprocess.run')
    def test_server_info(self, mock_run):
        mock_run.return_value.stdout = "code2prompt version 1.2.3"
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0
        
        # Import the server_info function 
        from mcp_handley_lab.code2prompt.tool import server_info
        result = server_info()
        assert "status" in result.lower() and "code2prompt" in result.lower()
    
    @patch('subprocess.run')
    def test_server_info_error_handling(self, mock_run):
        """Test server_info error handling (lines 168-169)."""
        from mcp_handley_lab.code2prompt.tool import server_info
        
        mock_run.side_effect = FileNotFoundError("code2prompt: command not found")
        
        with pytest.raises(RuntimeError, match="code2prompt command not found"):
            server_info()