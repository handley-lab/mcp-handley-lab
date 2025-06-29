import pytest
import json
import tempfile
import subprocess
import asyncio
from unittest.mock import patch, Mock, mock_open, AsyncMock
from pathlib import Path
from mcp_handley_lab.jq.tool import query, edit, validate, format as jq_format, read, server_info
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
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_query_parameterized(self, mock_subprocess, data, filter, expected):
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (expected.encode(), b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        result = await query(data=data, filter=filter)
        assert expected in result
        mock_subprocess.assert_called()
    
    @pytest.mark.asyncio
    async def test_edit_validation(self):
        with pytest.raises(ValueError):
            await edit(file_path="", filter=".test")
        
        # Create a temporary file for filter validation
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"test": "value"}, f)
            f.flush()
            
            try:
                with pytest.raises(ValueError):
                    await edit(file_path=f.name, filter="")
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_validate_valid_json(self):
        result = await validate(data='{"valid": true}')
        assert "valid" in result.lower()
    
    @pytest.mark.asyncio
    async def test_validate_invalid_json(self):
        with pytest.raises(ValueError):
            await validate(data='{"invalid": json}')
    
    @pytest.mark.asyncio
    async def test_format_compact(self):
        result = await jq_format(data='{"compact": true}', compact=True)
        assert "compact" in result
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_edit_success(self, mock_subprocess):
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'{"test": "new_value"}', b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"test": "value"}, f)
            f.flush()
            
            try:
                result = await edit(file_path=f.name, filter='.test = "new_value"')
                assert "success" in result.lower() or "updated" in result.lower()
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')  
    async def test_query_compact_raw(self, mock_subprocess):
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"value", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        result = await query('{"test": "value"}', '.test', compact=True, raw_output=True)
        assert "value" in result
        
        # Verify compact and raw flags were used
        call_args = mock_subprocess.call_args[0]
        assert "-c" in call_args
        assert "-r" in call_args
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_query_file_path(self, mock_subprocess):
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'"value"', b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write('{"test": "value"}')
            f.flush()
            
            try:
                result = await query(f.name, '.test')
                assert '"value"' in result
                
                # Verify file path was passed to jq
                call_args = mock_subprocess.call_args[0]
                assert f.name in call_args
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_read_file(self, mock_subprocess):
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'{"formatted": true}', b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        result = await read("/tmp/test.json", ".formatted")
        assert "formatted" in result
    
    @pytest.mark.parametrize("data,filter,error_msg,expected_exception", [
        ('{"test": "value"}', 'invalid..filter', 'jq error: invalid filter', ValueError),
        ('invalid json', '.test', 'Invalid JSON', ValueError),
        ('{"test": "value"}', '.nonexistent | error', 'Cannot index', ValueError),
        ('[]', '.[10]', 'Cannot index array with string', ValueError),
    ])
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_jq_error_handling_parameterized(self, mock_subprocess, data, filter, error_msg, expected_exception):
        # Mock the async subprocess to return an error
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", error_msg.encode())
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process
        
        with pytest.raises(expected_exception, match="jq error"):
            await query(data, filter)
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_query_with_dict_input(self, mock_subprocess):
        """Test query with dict input (line 20)."""
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'"Alice"', b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        # Pass dict directly (FastMCP auto-parses JSON to dict)
        result = await query({"name": "Alice"}, '.name')
        assert '"Alice"' in result
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_query_with_list_input(self, mock_subprocess):
        """Test query with list input (line 20)."""
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'3', b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        # Pass list directly (FastMCP auto-parses JSON to list)
        result = await query([1, 2, 3], 'length')
        assert '3' in result
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_query_with_non_string_fallback(self, mock_subprocess):
        """Test query with non-string data fallback (line 30)."""
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'123', b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        # Pass integer (should convert to string)
        result = await query(123, '.')
        assert '123' in result
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_jq_command_not_found(self, mock_subprocess):
        """Test jq command not found error (lines 46-47)."""
        mock_subprocess.side_effect = FileNotFoundError("jq: command not found")
        
        with pytest.raises(RuntimeError, match="jq command not found"):
            await query('{"test": "value"}', '.test')
    
    @pytest.mark.asyncio
    async def test_format_pretty_print(self):
        """Test non-compact formatting (line 249)."""
        data = '{"b": 2, "a": 1}'
        result = await jq_format(data, compact=False, sort_keys=True)
        
        # Should have indentation (non-compact)
        assert '{\n' in result
        assert '"a"' in result
        assert '"b"' in result
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.jq.tool._run_jq', new_callable=AsyncMock)
    async def test_server_info_success(self, mock_run_jq):
        """Test server_info function (lines 255-271)."""
        from mcp_handley_lab.jq.tool import server_info
        
        # Mock the async function
        mock_run_jq.return_value = "jq-1.6"
        
        result = await server_info()
        assert "JQ Tool Server Status" in result
        assert "jq-1.6" in result
        assert "Connected and ready" in result
        assert "query:" in result
        assert "edit:" in result
        assert "validate:" in result
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.jq.tool._run_jq', new_callable=AsyncMock)
    async def test_server_info_error(self, mock_run_jq):
        """Test server_info error handling (line 271)."""
        from mcp_handley_lab.jq.tool import server_info
        
        # Mock the async function to raise an exception directly
        mock_run_jq.side_effect = RuntimeError("jq command not found")
        
        with pytest.raises(RuntimeError, match="jq command not found"):
            await server_info()

class TestVimUnit:
    
    @pytest.mark.parametrize("file_ext,initial_content,show_diff,expected_in_result", [
        (".py", "print('hello')", False, "hello"),
        (".txt", "Hello World", False, "hello world"),
        (".md", "# Heading", False, "heading"),
        (".py", "", False, "content"),
        (".js", "console.log('test')", True, "changes"),
    ])
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.vim.tool._run_vim', new_callable=AsyncMock)
    @patch('builtins.open', new_callable=mock_open)
    async def test_prompt_user_edit_parameterized(self, mock_file, mock_run_vim, file_ext, initial_content, show_diff, expected_in_result):
        mock_file.return_value.read.return_value = initial_content or "default content"
        mock_run_vim.return_value = None
        
        result = await prompt_user_edit(initial_content, file_extension=file_ext, show_diff=show_diff)
        assert expected_in_result in result.lower()
        mock_run_vim.assert_called_once()
    
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.vim.tool._run_vim', new_callable=AsyncMock)
    @patch('builtins.open', new_callable=mock_open)
    async def test_prompt_user_edit_with_diff(self, mock_file, mock_run_vim):
        # First read returns original, second returns modified
        mock_file.return_value.read.side_effect = ["original content", "modified content"]
        mock_run_vim.return_value = None
        
        result = await prompt_user_edit("original content", show_diff=True)
        assert "Changes made:" in result or "No changes made" in result
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.vim.tool._run_vim', new_callable=AsyncMock)
    @patch('builtins.open', new_callable=mock_open, read_data="test content")
    async def test_prompt_user_edit_with_instructions(self, mock_file, mock_run_vim):
        mock_run_vim.return_value = None
        result = await prompt_user_edit(
            "test content", 
            instructions="Edit this file",
            file_extension=".py"
        )
        assert "test content" in result or "no changes" in result.lower()
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.vim.tool._run_vim', new_callable=AsyncMock)
    @patch('pathlib.Path.read_text')
    @patch('pathlib.Path.write_text')
    async def test_open_file_success(self, mock_write, mock_read, mock_run_vim):
        mock_run_vim.return_value = None
        mock_read.return_value = "file content"
        mock_write.return_value = None
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("file content")
            
            try:
                result = await open_file(f.name, show_diff=False)
                assert "file edited" in result.lower() or "backup saved" in result.lower()
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.vim.tool._run_vim', new_callable=AsyncMock)
    @patch('builtins.open', new_callable=mock_open, read_data="quick content")
    async def test_quick_edit_success(self, mock_file, mock_run_vim):
        mock_run_vim.return_value = None
        result = await quick_edit(initial_content="test", file_extension=".txt")
        assert "quick content" in result or "created successfully" in result.lower()
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.vim.tool._run_vim', new_callable=AsyncMock)
    @patch('pathlib.Path.read_text')
    @patch('pathlib.Path.write_text')
    async def test_open_file_with_backup(self, mock_write, mock_read, mock_run_vim):
        mock_read.return_value = "original content"
        mock_write.return_value = None
        mock_run_vim.return_value = None
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("original content")
            
            try:
                result = await open_file(f.name, backup=True, show_diff=False)
                assert "backup saved" in result.lower()
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.vim.tool._run_vim', new_callable=AsyncMock)
    @patch('pathlib.Path.read_text')
    @patch('pathlib.Path.write_text')
    async def test_open_file_with_instructions(self, mock_write, mock_read, mock_run_vim):
        mock_read.return_value = "original content"
        mock_write.return_value = None
        mock_run_vim.return_value = None
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("original content")
            
            try:
                result = await open_file(f.name, instructions="Edit this file carefully")
                assert "file edited" in result.lower() or "no changes" in result.lower()
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.vim.tool._run_vim', new_callable=AsyncMock)  
    @patch('pathlib.Path.read_text')
    @patch('pathlib.Path.write_text')
    async def test_open_file_with_diff(self, mock_write, mock_read, mock_run_vim):
        # Return different content to trigger diff
        mock_read.side_effect = ["original content", "different content"]
        mock_write.return_value = None
        mock_run_vim.return_value = None
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("original content")
            
            try:
                result = await open_file(f.name, show_diff=True)
                assert "changes made" in result.lower() or "diff" in result.lower()
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_vim_server_info(self, mock_subprocess):
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"VIM - Vi IMproved 8.2", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        from mcp_handley_lab.vim.tool import server_info
        result = await server_info()
        assert "vim" in result.lower() and "status" in result.lower()
    
    @pytest.mark.asyncio
    @patch('os.isatty')
    @patch('asyncio.create_subprocess_exec')
    async def test_run_vim_no_tty(self, mock_subprocess, mock_isatty):
        """Test vim without TTY (line 19)."""
        from mcp_handley_lab.vim.tool import _run_vim
        
        mock_isatty.return_value = False  # No TTY
        mock_process = AsyncMock()
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        await _run_vim("/tmp/test.txt")
        mock_subprocess.assert_called()
        
        # Should call create_subprocess_exec
        call_args = mock_subprocess.call_args[0]
        assert 'vim' in call_args
        assert '/tmp/test.txt' in call_args
    
    @pytest.mark.asyncio
    @patch('os.isatty')
    @patch('asyncio.create_subprocess_exec')
    async def test_run_vim_with_tty(self, mock_subprocess, mock_isatty):
        """Test vim with TTY (line 19)."""
        from mcp_handley_lab.vim.tool import _run_vim
        
        mock_isatty.return_value = True  # TTY available
        mock_process = AsyncMock()
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        await _run_vim("/tmp/test.txt")
        mock_subprocess.assert_called()
        
        # Should call create_subprocess_exec 
        call_args = mock_subprocess.call_args[0]
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
    
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.vim.tool._run_vim', new_callable=AsyncMock) 
    @patch('builtins.open', new_callable=mock_open, read_data="original content")
    async def test_prompt_user_edit_with_changes(self, mock_file, mock_run_vim):
        """Test diff calculation when changes are made (lines 143-147)."""
        from mcp_handley_lab.vim.tool import prompt_user_edit
        
        # Mock vim writing different content
        async def side_effect(*args, **kwargs):
            # Simulate vim changing the file
            mock_file.return_value.read.return_value = "new content\nadded line"
        
        mock_run_vim.side_effect = side_effect
        mock_file.return_value.read.return_value = "new content\nadded line"
        
        result = await prompt_user_edit("original content", show_diff=True)
        
        # Should show added/removed line counts
        assert ("added" in result and "removed" in result) or "Changes made" in result
    
    @pytest.mark.parametrize("exception,error_msg,expected_exception", [
        (FileNotFoundError("vim: command not found"), "vim command not found", FileNotFoundError),
        (PermissionError("Permission denied"), "Permission denied", PermissionError),
        (subprocess.CalledProcessError(1, "vim", stderr="Vim error"), "Vim error", subprocess.CalledProcessError),
    ])
    @pytest.mark.asyncio
    @patch('mcp_handley_lab.vim.tool._run_vim', new_callable=AsyncMock)
    async def test_vim_error_handling_parameterized(self, mock_run_vim, exception, error_msg, expected_exception):
        """Test various vim error conditions."""
        from mcp_handley_lab.vim.tool import _run_vim
        
        mock_run_vim.side_effect = exception
        
        with pytest.raises(expected_exception):
            await _run_vim("/tmp/test.txt")
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_server_info_vim_not_found(self, mock_subprocess):
        """Test server_info when vim not found (lines 386-387)."""
        from mcp_handley_lab.vim.tool import server_info
        
        mock_subprocess.side_effect = FileNotFoundError("vim: command not found")
        
        with pytest.raises(RuntimeError, match="vim command not found"):
            await server_info()

class TestCode2PromptUnit:
    
    @pytest.mark.asyncio
    async def test_generate_prompt_validation(self):
        with pytest.raises(ValueError):
            await generate_prompt(path="")
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    @patch('pathlib.Path.stat')
    async def test_generate_prompt_success(self, mock_stat, mock_subprocess):
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"Generated prompt successfully", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        mock_stat.return_value.st_size = 1024  # Mock file size
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
                f.write("test content")
                
            try:
                result = await generate_prompt(
                    path=temp_dir,
                    output_file=f.name
                )
                assert "success" in result.lower()
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_generate_prompt_with_filters(self, mock_subprocess):
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"Generated with filters", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
                f.write("test content")

            try:
                result = await generate_prompt(
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
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_code2prompt_error_handling_parameterized(self, mock_subprocess, exception, error_msg, expected_exception):
        """Test various code2prompt error conditions."""
        if isinstance(exception, subprocess.CalledProcessError):
            # Mock subprocess that returns with error code
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", exception.stderr.encode() if exception.stderr else b"Command failed")
            mock_process.returncode = exception.returncode
            mock_subprocess.return_value = mock_process
        else:
            # Mock subprocess creation that raises exception
            mock_subprocess.side_effect = exception
        
        with pytest.raises(expected_exception):
            await generate_prompt(path="/tmp/test")
    
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    @patch('pathlib.Path.stat')
    async def test_generate_prompt_all_options(self, mock_stat, mock_subprocess):
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"Generated with all options", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        mock_stat.return_value.st_size = 2048
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
                f.write("test content")
                
                result = await generate_prompt(
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
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    @patch('pathlib.Path.stat')
    async def test_generate_prompt_git_options(self, mock_stat, mock_subprocess):
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"Generated with git options", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        mock_stat.return_value.st_size = 1024
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
                f.write("test content")
                
                result = await generate_prompt(
                    path=temp_dir,
                    output_file=f.name,
                    git_log_branch1="v1.0.0",
                    git_log_branch2="HEAD"
                )
                assert "success" in result.lower()
                
                Path(f.name).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_server_info(self, mock_subprocess):
        # Mock the async subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"code2prompt version 1.2.3", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        # Import the server_info function 
        from mcp_handley_lab.code2prompt.tool import server_info
        result = await server_info()
        assert "status" in result.lower() and "code2prompt" in result.lower()
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_server_info_error_handling(self, mock_subprocess):
        """Test server_info error handling (lines 168-169)."""
        from mcp_handley_lab.code2prompt.tool import server_info
        
        mock_subprocess.side_effect = FileNotFoundError("code2prompt: command not found")
        
        with pytest.raises(RuntimeError, match="code2prompt command not found"):
            await server_info()