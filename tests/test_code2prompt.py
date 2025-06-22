"""Unit tests for Code2Prompt tool."""
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from mcp_framework.code2prompt.tool import (
    generate_prompt, analyze_codebase, git_diff, server_info, _run_code2prompt
)


class TestCode2PromptTool:
    """Test cases for Code2Prompt tool methods."""
    
    @pytest.fixture
    def sample_codebase(self, tmp_path):
        """Create a temporary codebase directory."""
        code_dir = tmp_path / "sample_code"
        code_dir.mkdir()
        
        # Create a simple Python file
        (code_dir / "main.py").write_text('print("Hello, World!")')
        (code_dir / "utils.py").write_text('def helper():\n    return "help"')
        
        # Create a subdirectory with more files
        sub_dir = code_dir / "src"
        sub_dir.mkdir()
        (sub_dir / "app.py").write_text('class App:\n    pass')
        
        return str(code_dir)
    
    def test_generate_prompt_basic(self, sample_codebase):
        """Test generate_prompt with basic parameters."""
        with patch('mcp_framework.code2prompt.tool._run_code2prompt') as mock_run:
            with patch('tempfile.NamedTemporaryFile') as mock_temp:
                mock_file = MagicMock()
                mock_file.name = "/tmp/test_output.md"
                mock_temp.return_value = mock_file
                
                with patch('pathlib.Path.stat') as mock_stat:
                    mock_stat.return_value.st_size = 1024
                    
                    result = generate_prompt(sample_codebase)
                    
                    assert "Code2prompt Generation Successful" in result
                    assert "/tmp/test_output.md" in result
                    assert "1,024 bytes" in result
                    
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert sample_codebase in args
                    assert "--output" in args
                    assert "--output-format" in args
                    assert "markdown" in args
    
    def test_generate_prompt_with_custom_output(self, sample_codebase):
        """Test generate_prompt with custom output file."""
        output_file = "/custom/output.md"
        with patch('mcp_framework.code2prompt.tool._run_code2prompt') as mock_run:
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 2048
                
                result = generate_prompt(sample_codebase, output_file=output_file)
                
                assert output_file in result
                assert "2,048 bytes" in result
                
                args = mock_run.call_args[0][0]
                assert "--output" in args
                assert output_file in args
    
    def test_generate_prompt_with_all_options(self, sample_codebase):
        """Test generate_prompt with all optional parameters."""
        with patch('mcp_framework.code2prompt.tool._run_code2prompt') as mock_run:
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 512
                
                result = generate_prompt(
                    sample_codebase,
                    output_file="/test.json",
                    include=["*.py", "*.js"],
                    exclude=["*.pyc", "__pycache__"],
                    output_format="json",
                    line_numbers=True,
                    full_directory_tree=True,
                    follow_symlinks=True,
                    hidden=True,
                    no_codeblock=True,
                    absolute_paths=True,
                    encoding="p50k",
                    tokens="raw",
                    sort="date_desc"
                )
                
                assert "Code2prompt Generation Successful" in result
                
                args = mock_run.call_args[0][0]
                assert sample_codebase in args
                assert "--output-format" in args
                assert "json" in args
                assert "--include" in args
                assert "*.py" in args
                assert "*.js" in args
                assert "--exclude" in args
                assert "*.pyc" in args
                assert "__pycache__" in args
                assert "--line-numbers" in args
                assert "--full-directory-tree" in args
                assert "--follow-symlinks" in args
                assert "--hidden" in args
                assert "--no-codeblock" in args
                assert "--absolute-paths" in args
                assert "--encoding" in args
                assert "p50k" in args
                assert "--tokens" in args
                assert "raw" in args
                assert "--sort" in args
                assert "date_desc" in args
    
    def test_analyze_codebase_basic(self, sample_codebase):
        """Test analyze_codebase with basic parameters."""
        with patch('mcp_framework.code2prompt.tool._run_code2prompt') as mock_run:
            mock_run.return_value = "Directory structure:\n├── main.py\n└── utils.py\n\nTotal tokens: 150"
            
            result = analyze_codebase(sample_codebase)
            
            assert "Directory structure:" in result
            assert "Total tokens: 150" in result
            
            args = mock_run.call_args[0][0]
            assert sample_codebase in args
            assert "--analyze" in args
            assert "--encoding" in args
            assert "cl100k" in args
    
    def test_analyze_codebase_with_options(self, sample_codebase):
        """Test analyze_codebase with optional parameters."""
        with patch('mcp_framework.code2prompt.tool._run_code2prompt') as mock_run:
            mock_run.return_value = "Analysis complete"
            
            result = analyze_codebase(
                sample_codebase,
                include=["*.py"],
                exclude=["test_*"],
                hidden=True,
                encoding="p50k"
            )
            
            assert "Analysis complete" in result
            
            args = mock_run.call_args[0][0]
            assert "--include" in args
            assert "*.py" in args
            assert "--exclude" in args
            assert "test_*" in args
            assert "--hidden" in args
            assert "--encoding" in args
            assert "p50k" in args
    
    def test_git_diff_basic(self, sample_codebase):
        """Test git_diff with basic parameters."""
        with patch('mcp_framework.code2prompt.tool._run_code2prompt') as mock_run:
            with patch('tempfile.NamedTemporaryFile') as mock_temp:
                mock_file = MagicMock()
                mock_file.name = "/tmp/git_diff.md"
                mock_temp.return_value = mock_file
                
                with patch('pathlib.Path.stat') as mock_stat:
                    mock_stat.return_value.st_size = 756
                    
                    result = git_diff(sample_codebase)
                    
                    assert "Git Diff Generation Successful" in result
                    assert "/tmp/git_diff.md" in result
                    assert "756 bytes" in result
                    assert "Mode:** diff" in result
                    
                    args = mock_run.call_args[0][0]
                    assert sample_codebase in args
                    assert "--git-diff" in args
    
    def test_git_diff_branch_diff(self, sample_codebase):
        """Test git_diff with branch comparison."""
        with patch('mcp_framework.code2prompt.tool._run_code2prompt') as mock_run:
            with patch('tempfile.NamedTemporaryFile') as mock_temp:
                mock_file = MagicMock()
                mock_file.name = "/tmp/branch_diff.md"
                mock_temp.return_value = mock_file
                
                with patch('pathlib.Path.stat') as mock_stat:
                    mock_stat.return_value.st_size = 1200
                    
                    result = git_diff(
                        sample_codebase,
                        mode="branch_diff",
                        branch1="main",
                        branch2="feature"
                    )
                    
                    assert "Git Diff Generation Successful" in result
                    assert "Mode:** branch_diff" in result
                    
                    args = mock_run.call_args[0][0]
                    assert "--git-diff-branch" in args
                    assert "main..feature" in args
    
    def test_git_diff_branch_log(self, sample_codebase):
        """Test git_diff with branch log mode."""
        with patch('mcp_framework.code2prompt.tool._run_code2prompt') as mock_run:
            with patch('tempfile.NamedTemporaryFile') as mock_temp:
                mock_file = MagicMock()
                mock_file.name = "/tmp/branch_log.md"
                mock_temp.return_value = mock_file
                
                with patch('pathlib.Path.stat') as mock_stat:
                    mock_stat.return_value.st_size = 890
                    
                    result = git_diff(
                        sample_codebase,
                        mode="branch_log",
                        branch1="v1.0",
                        branch2="v2.0",
                        include=["*.py"],
                        exclude=["*.pyc"]
                    )
                    
                    assert "Git Diff Generation Successful" in result
                    assert "Mode:** branch_log" in result
                    
                    args = mock_run.call_args[0][0]
                    assert "--git-log" in args
                    assert "v1.0..v2.0" in args
                    assert "--include" in args
                    assert "*.py" in args
                    assert "--exclude" in args
                    assert "*.pyc" in args
    
    def test_server_info_success(self):
        """Test server_info when code2prompt is available."""
        with patch('mcp_framework.code2prompt.tool._run_code2prompt') as mock_run:
            mock_run.return_value = "code2prompt v1.2.3"
            
            result = server_info()
            
            assert "Code2Prompt Tool Server Status" in result
            assert "Connected and ready" in result
            assert "code2prompt v1.2.3" in result
            assert "Available tools:" in result
            assert "generate_prompt:" in result
            assert "analyze_codebase:" in result
            assert "git_diff:" in result
            assert "server_info:" in result
            
            mock_run.assert_called_once_with(["--version"])
    
    def test_server_info_not_found(self):
        """Test server_info when code2prompt is not installed."""
        with patch('mcp_framework.code2prompt.tool._run_code2prompt') as mock_run:
            mock_run.side_effect = RuntimeError("code2prompt command not found. Please install code2prompt.")
            
            with pytest.raises(RuntimeError, match="code2prompt command not found"):
                server_info()
    
    def test_run_code2prompt_success(self):
        """Test _run_code2prompt with successful execution."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="success output", stderr="", returncode=0
            )
            
            result = _run_code2prompt(["--version"])
            
            assert result == "success output"
            mock_run.assert_called_once_with(
                ["code2prompt", "--version"],
                capture_output=True,
                text=True,
                check=False
            )
    
    def test_run_code2prompt_error(self):
        """Test _run_code2prompt with command error."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="", stderr="invalid argument", returncode=1
            )
            
            with pytest.raises(ValueError, match="code2prompt error: invalid argument"):
                _run_code2prompt(["--invalid"])
    
    def test_run_code2prompt_not_found(self):
        """Test _run_code2prompt when command is not found."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            
            with pytest.raises(RuntimeError, match="code2prompt command not found"):
                _run_code2prompt(["--version"])
    
    def test_generate_prompt_error(self, sample_codebase):
        """Test generate_prompt with code2prompt error."""
        with patch('mcp_framework.code2prompt.tool._run_code2prompt') as mock_run:
            mock_run.side_effect = ValueError("code2prompt error: invalid path")
            
            with pytest.raises(ValueError, match="code2prompt error: invalid path"):
                generate_prompt(sample_codebase)
    
    def test_analyze_codebase_error(self, sample_codebase):
        """Test analyze_codebase with code2prompt error."""
        with patch('mcp_framework.code2prompt.tool._run_code2prompt') as mock_run:
            mock_run.side_effect = ValueError("code2prompt error: no files found")
            
            with pytest.raises(ValueError, match="code2prompt error: no files found"):
                analyze_codebase(sample_codebase)
    
    def test_git_diff_error(self, sample_codebase):
        """Test git_diff with code2prompt error."""
        with patch('mcp_framework.code2prompt.tool._run_code2prompt') as mock_run:
            mock_run.side_effect = ValueError("code2prompt error: not a git repository")
            
            with pytest.raises(ValueError, match="code2prompt error: not a git repository"):
                git_diff(sample_codebase)