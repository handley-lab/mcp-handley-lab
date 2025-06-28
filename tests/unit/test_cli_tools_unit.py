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
        
        with pytest.raises(ValueError):
            edit(file_path="/tmp/test.json", filter="")
    
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
    
    @patch('subprocess.run')
    def test_jq_error_handling(self, mock_run):
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "jq", stderr="jq error: invalid filter")
        
        with pytest.raises(ValueError, match="jq error"):
            query('{"test": "value"}', 'invalid..filter')

class TestVimUnit:
    
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open, read_data="test content")
    def test_prompt_user_edit_success(self, mock_file, mock_run):
        mock_run.return_value = None
        result = prompt_user_edit("test content", show_diff=False)
        assert "test content" in result
    
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

class TestCode2PromptUnit:
    
    def test_generate_prompt_validation(self):
        with pytest.raises(ValueError):
            generate_prompt(path="")
    
    @patch('subprocess.run')
    def test_generate_prompt_success(self, mock_run):
        mock_run.return_value.stdout = "Generated prompt successfully"
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0
        
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
    
    @patch('subprocess.run')
    def test_generate_prompt_subprocess_error(self, mock_run):
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "code2prompt", stderr="Command failed")
        
        with pytest.raises(ValueError, match="code2prompt error"):
            generate_prompt(path="/tmp/test")
    
    @patch('subprocess.run')
    def test_generate_prompt_command_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("code2prompt not found")
        
        with pytest.raises(RuntimeError, match="code2prompt command not found"):
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