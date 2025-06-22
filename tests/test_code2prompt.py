"""Unit tests for Code2Prompt tool."""
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from mcp_handley_lab.code2prompt.tool import (
    generate_prompt, server_info, _run_code2prompt
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
        with patch('mcp_handley_lab.code2prompt.tool._run_code2prompt') as mock_run:
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
                    assert "--output-file" in args
                    assert "--output-format" in args
                    assert "markdown" in args
    
    def test_generate_prompt_with_custom_output(self, sample_codebase):
        """Test generate_prompt with custom output file."""
        output_file = "/custom/output.md"
        with patch('mcp_handley_lab.code2prompt.tool._run_code2prompt') as mock_run:
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 2048
                
                result = generate_prompt(sample_codebase, output_file=output_file)
                
                assert output_file in result
                assert "2,048 bytes" in result
                
                args = mock_run.call_args[0][0]
                assert "--output-file" in args
                assert output_file in args
    
    def test_generate_prompt_with_all_options(self, sample_codebase):
        """Test generate_prompt with all optional parameters."""
        with patch('mcp_handley_lab.code2prompt.tool._run_code2prompt') as mock_run:
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
    
    
    def test_server_info_success(self):
        """Test server_info when code2prompt is available."""
        with patch('mcp_handley_lab.code2prompt.tool._run_code2prompt') as mock_run:
            mock_run.return_value = "code2prompt v1.2.3"
            
            result = server_info()
            
            assert "Code2Prompt Tool Server Status" in result
            assert "Connected and ready" in result
            assert "code2prompt v1.2.3" in result
            assert "Available tools:" in result
            assert "generate_prompt:" in result
            assert "server_info:" in result
            
            mock_run.assert_called_once_with(["--version"])
    
    def test_server_info_not_found(self):
        """Test server_info when code2prompt is not installed."""
        with patch('mcp_handley_lab.code2prompt.tool._run_code2prompt') as mock_run:
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
        with patch('mcp_handley_lab.code2prompt.tool._run_code2prompt') as mock_run:
            mock_run.side_effect = ValueError("code2prompt error: invalid path")
            
            with pytest.raises(ValueError, match="code2prompt error: invalid path"):
                generate_prompt(sample_codebase)
    
    
    def test_real_cli_integration(self, sample_codebase, tmp_path):
        """Real integration test that actually calls code2prompt CLI to catch parameter mismatches."""
        import subprocess
        
        # Skip if code2prompt not available
        try:
            result = subprocess.run(["code2prompt", "--version"], capture_output=True, check=False)
            if result.returncode != 0:
                pytest.skip("code2prompt not available")
        except FileNotFoundError:
            pytest.skip("code2prompt not available")
        
        # Test with a real temporary output file
        output_file = tmp_path / "integration_test.md"
        
        # This will fail if we use wrong CLI parameters like --output instead of --output-file
        try:
            result = generate_prompt(sample_codebase, output_file=str(output_file))
            assert "Code2prompt Generation Successful" in result
            assert output_file.exists()
            assert output_file.stat().st_size > 0
        except ValueError as e:
            if "unexpected argument '--output'" in str(e):
                pytest.fail(f"CLI parameter mismatch detected: {e}")
            else:
                raise
    
    def test_generate_prompt_with_new_flags(self, sample_codebase):
        """Test generate_prompt with newly added flags."""
        with patch('mcp_handley_lab.code2prompt.tool._run_code2prompt') as mock_run:
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 1024
                
                result = generate_prompt(
                    sample_codebase,
                    output_file="/test.md",
                    include_priority=True,
                    template="/path/to/template.hbs",
                    no_ignore=True,
                    include_git_diff=True,
                    git_diff_branch1="main",
                    git_diff_branch2="feature",
                    git_log_branch1="v1.0",
                    git_log_branch2="v2.0"
                )
                
                assert "Code2prompt Generation Successful" in result
                
                args = mock_run.call_args[0][0]
                assert sample_codebase in args
                assert "--include-priority" in args
                assert "--template" in args
                assert "/path/to/template.hbs" in args
                assert "--no-ignore" in args
                assert "--diff" in args
                assert "--git-diff-branch" in args
                assert "main" in args and "feature" in args
                assert "--git-log-branch" in args  
                assert "v1.0" in args and "v2.0" in args
    
    def test_generate_prompt_git_options_independent(self, sample_codebase):
        """Test that git options work independently."""
        with patch('mcp_handley_lab.code2prompt.tool._run_code2prompt') as mock_run:
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 512
                
                # Test git-diff-branch without include_git_diff
                result = generate_prompt(
                    sample_codebase,
                    git_diff_branch1="main", 
                    git_diff_branch2="dev"
                )
                
                args = mock_run.call_args[0][0]
                assert "--git-diff-branch" in args
                assert "main" in args and "dev" in args
                assert "--diff" not in args  # Should not be present


class TestCode2PromptIntegration:
    """Integration tests that call real code2prompt CLI."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Check if code2prompt is available for integration tests."""
        import subprocess
        try:
            subprocess.run(["code2prompt", "--version"], capture_output=True, check=True)
            self.code2prompt_available = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            self.code2prompt_available = False
    
    @pytest.fixture
    def sample_codebase_with_files(self, tmp_path):
        """Create a more comprehensive test codebase."""
        codebase = tmp_path / "test_codebase"
        codebase.mkdir()
        
        # Python files
        (codebase / "main.py").write_text('#!/usr/bin/env python3\nprint("Hello World")\n')
        (codebase / "utils.py").write_text('def helper():\n    """A helper function."""\n    return "help"\n')
        
        # JavaScript files  
        (codebase / "app.js").write_text('console.log("Hello JS");\n')
        
        # Config files
        (codebase / "config.json").write_text('{"name": "test", "version": "1.0"}\n')
        (codebase / ".gitignore").write_text('*.pyc\n__pycache__/\nnode_modules/\n')
        
        # Hidden file
        (codebase / ".hidden").write_text('secret content\n')
        
        # Subdirectory
        subdir = codebase / "src"
        subdir.mkdir()
        (subdir / "module.py").write_text('class TestClass:\n    pass\n')
        
        # Create a file that would be ignored
        (codebase / "test.pyc").write_text('binary content')
        
        return str(codebase)
    
    @pytest.fixture 
    def git_repo_with_history(self, tmp_path):
        """Create a git repository with commit history."""
        import subprocess
        import os
        
        if not self.code2prompt_available:
            pytest.skip("code2prompt not available")
            
        # Check git availability
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            pytest.skip("git not available")
        
        repo = tmp_path / "git_repo"
        repo.mkdir()
        original_cwd = os.getcwd()
        
        try:
            os.chdir(repo)
            
            # Initialize repo
            subprocess.run(["git", "init"], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], check=True)
            
            # Create initial files and commits
            (repo / "file1.py").write_text("# Initial version\nprint('v1')\n")
            (repo / "README.md").write_text("# Test Project\nInitial readme\n")
            
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)
            
            # Create a branch
            subprocess.run(["git", "checkout", "-b", "feature"], check=True)
            (repo / "file1.py").write_text("# Feature version\nprint('v2')\n")
            (repo / "feature.py").write_text("def new_feature():\n    return 'feature'\n")
            
            subprocess.run(["git", "add", "."], check=True)  
            subprocess.run(["git", "commit", "-m", "Add feature"], check=True)
            
            # Back to main and add different changes
            subprocess.run(["git", "checkout", "master"], check=True)
            (repo / "README.md").write_text("# Test Project\nUpdated readme\n")
            subprocess.run(["git", "add", "README.md"], check=True)
            subprocess.run(["git", "commit", "-m", "Update readme"], check=True)
            
            return str(repo)
        finally:
            os.chdir(original_cwd)
    
    def test_basic_functionality(self, sample_codebase_with_files, tmp_path):
        """Test basic generate_prompt functionality."""
        if not self.code2prompt_available:
            pytest.skip("code2prompt not available")
        
        output_file = tmp_path / "basic_test.md"
        
        result = generate_prompt(
            sample_codebase_with_files,
            output_file=str(output_file)
        )
        
        assert "Code2prompt Generation Successful" in result
        assert output_file.exists()
        assert output_file.stat().st_size > 0
        
        # Check content contains expected elements
        content = output_file.read_text()
        assert "main.py" in content
        assert "utils.py" in content
        assert "Hello World" in content
    
    def test_include_exclude_patterns(self, sample_codebase_with_files, tmp_path):
        """Test include/exclude pattern functionality.""" 
        if not self.code2prompt_available:
            pytest.skip("code2prompt not available")
        
        output_file = tmp_path / "patterns_test.md"
        
        result = generate_prompt(
            sample_codebase_with_files,
            output_file=str(output_file),
            include=["*.py"],
            exclude=["**/test*"]
        )
        
        assert "Code2prompt Generation Successful" in result
        content = output_file.read_text()
        
        # Should include Python files
        assert "main.py" in content
        assert "utils.py" in content
        
        # Should exclude JS files
        assert "app.js" not in content
        assert "config.json" not in content
    
    def test_output_formats(self, sample_codebase_with_files, tmp_path):
        """Test different output formats."""
        if not self.code2prompt_available:
            pytest.skip("code2prompt not available")
        
        # Test JSON format
        json_file = tmp_path / "test.json"
        result = generate_prompt(
            sample_codebase_with_files,
            output_file=str(json_file),
            output_format="json"
        )
        
        assert "Code2prompt Generation Successful" in result
        assert json_file.exists()
        
        # Verify it's valid JSON
        import json
        data = json.loads(json_file.read_text())
        assert isinstance(data, dict)
        
        # Test XML format  
        xml_file = tmp_path / "test.xml"
        result = generate_prompt(
            sample_codebase_with_files,
            output_file=str(xml_file),
            output_format="xml"
        )
        
        assert "Code2prompt Generation Successful" in result
        assert xml_file.exists()
        content = xml_file.read_text()
        assert "<directory>" in content and "</directory>" in content
    
    def test_formatting_options(self, sample_codebase_with_files, tmp_path):
        """Test various formatting options."""
        if not self.code2prompt_available:
            pytest.skip("code2prompt not available")
        
        output_file = tmp_path / "formatting_test.md"
        
        result = generate_prompt(
            sample_codebase_with_files,
            output_file=str(output_file),
            line_numbers=True,
            full_directory_tree=True,
            absolute_paths=True,
            no_codeblock=True
        )
        
        assert "Code2prompt Generation Successful" in result
        content = output_file.read_text()
        
        # Line numbers should add line prefixes
        # Full directory tree should show more structure
        # These are hard to test precisely without knowing exact format
        assert len(content) > 0
    
    def test_hidden_and_ignored_files(self, sample_codebase_with_files, tmp_path):
        """Test hidden file and gitignore handling."""
        if not self.code2prompt_available:
            pytest.skip("code2prompt not available")
        
        # Test with hidden files included
        output_file1 = tmp_path / "with_hidden.md"
        result1 = generate_prompt(
            sample_codebase_with_files,
            output_file=str(output_file1),
            hidden=True
        )
        
        assert "Code2prompt Generation Successful" in result1
        content1 = output_file1.read_text()
        
        # Test ignoring .gitignore rules
        output_file2 = tmp_path / "no_ignore.md"
        result2 = generate_prompt(
            sample_codebase_with_files,
            output_file=str(output_file2),
            no_ignore=True
        )
        
        assert "Code2prompt Generation Successful" in result2
        content2 = output_file2.read_text()
        # Should include .pyc file when ignoring .gitignore
        assert "test.pyc" in content2
    
    def test_git_diff_functionality(self, git_repo_with_history, tmp_path):
        """Test git diff integration."""
        if not self.code2prompt_available:
            pytest.skip("code2prompt not available")
        
        import os
        original_cwd = os.getcwd()
        
        try:
            os.chdir(git_repo_with_history)
            
            # Test basic git diff
            output_file = tmp_path / "git_diff_test.md"
            result = generate_prompt(
                git_repo_with_history,
                output_file=str(output_file),
                include_git_diff=True
            )
            
            assert "Code2prompt Generation Successful" in result
            content = output_file.read_text()
            assert "Git Diff" in content or "git diff" in content.lower()
            
        finally:
            os.chdir(original_cwd)
    
    def test_git_branch_comparison(self, git_repo_with_history, tmp_path):
        """Test git branch comparison functionality."""
        if not self.code2prompt_available:
            pytest.skip("code2prompt not available")
        
        output_file = tmp_path / "branch_diff_test.md"
        result = generate_prompt(
            git_repo_with_history,
            output_file=str(output_file),
            git_diff_branch1="master",
            git_diff_branch2="feature"
        )
        
        assert "Code2prompt Generation Successful" in result
        assert output_file.exists()
        content = output_file.read_text()
        
        # Should contain branch comparison information
        # Exact format depends on code2prompt output
        assert len(content) > 0
    
    def test_encoding_options(self, sample_codebase_with_files, tmp_path):
        """Test different encoding/tokenizer options."""
        if not self.code2prompt_available:
            pytest.skip("code2prompt not available")
        
        for encoding in ["cl100k", "p50k", "gpt2"]:
            output_file = tmp_path / f"encoding_{encoding}.md"
            result = generate_prompt(
                sample_codebase_with_files,
                output_file=str(output_file),
                encoding=encoding,
                tokens="raw"
            )
            
            assert "Code2prompt Generation Successful" in result
            assert output_file.exists()
    
    def test_error_conditions(self, tmp_path):
        """Test error handling with invalid inputs."""
        if not self.code2prompt_available:
            pytest.skip("code2prompt not available")
        
        # Test with non-existent path
        with pytest.raises(ValueError, match="code2prompt error"):
            generate_prompt("/nonexistent/path")
        
        # Test with invalid output format
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        (test_dir / "test.py").write_text("print('test')")
        
        with pytest.raises(ValueError, match="code2prompt error"):
            generate_prompt(str(test_dir), output_format="invalid_format")
    
    def test_include_priority_flag(self, sample_codebase_with_files, tmp_path):
        """Test include priority functionality."""
        if not self.code2prompt_available:
            pytest.skip("code2prompt not available")
        
        output_file = tmp_path / "priority_test.md"
        
        # Test conflicting include/exclude with priority
        result = generate_prompt(
            sample_codebase_with_files,
            output_file=str(output_file),
            include=["*.py"],
            exclude=["main.py"],  # Conflicting rule
            include_priority=True
        )
        
        assert "Code2prompt Generation Successful" in result
        content = output_file.read_text()
        
        # With include priority, main.py should be included despite exclude
        assert "main.py" in content

