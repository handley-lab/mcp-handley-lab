"""Isolated unit tests for Tool Chainer to ensure 100% coverage."""
import json
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, mock_open, PropertyMock

# Import directly what we need to test
import mcp_handley_lab.tool_chainer.tool as tool_module


class TestToolChainerCoverage:
    """Test Tool Chainer functions for 100% coverage."""
    
    @pytest.fixture(autouse=True)
    def reset_globals(self):
        """Reset global state before each test."""
        # Store original values
        original_registered = tool_module.REGISTERED_TOOLS.copy()
        original_chains = tool_module.DEFINED_CHAINS.copy()
        original_history = tool_module.EXECUTION_HISTORY.copy()
        
        # Clear before test
        tool_module.REGISTERED_TOOLS.clear()
        tool_module.DEFINED_CHAINS.clear()
        tool_module.EXECUTION_HISTORY.clear()
        
        yield
        
        # Restore after test
        tool_module.REGISTERED_TOOLS.clear()
        tool_module.REGISTERED_TOOLS.update(original_registered)
        tool_module.DEFINED_CHAINS.clear()
        tool_module.DEFINED_CHAINS.update(original_chains)
        tool_module.EXECUTION_HISTORY.clear()
        tool_module.EXECUTION_HISTORY.extend(original_history)
    
    def test_save_state_coverage(self):
        """Test _save_state function."""
        tool_module.REGISTERED_TOOLS["test"] = {"data": "value"}
        tool_module.DEFINED_CHAINS["chain"] = {"steps": []}
        tool_module.EXECUTION_HISTORY.append({"exec": "test"})
        
        mock_file = mock_open()
        with patch('builtins.open', mock_file), \
             patch('mcp_handley_lab.tool_chainer.tool.CACHE_DIR') as mock_cache_dir:
            mock_cache_dir.__truediv__.return_value = "fake_path"
            tool_module._save_state()
        
        # Verify file was opened for writing
        mock_file.assert_called_once_with("fake_path", "w")
        
        # Get what was written
        handle = mock_file()
        written_data = ''.join(call.args[0] for call in handle.write.call_args_list)
        
        # Verify JSON structure
        data = json.loads(written_data)
        assert "registered_tools" in data
        assert "defined_chains" in data
        assert "execution_history" in data
    
    def test_load_state_exists_coverage(self):
        """Test _load_state when file exists."""
        test_state = {
            "registered_tools": {"tool1": {"name": "test"}},
            "defined_chains": {"chain1": {"steps": []}},
            "execution_history": [{"id": "test"}]
        }
        
        mock_file = mock_open(read_data=json.dumps(test_state))
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        
        with patch('builtins.open', mock_file), \
             patch('mcp_handley_lab.tool_chainer.tool.CACHE_DIR') as mock_cache_dir:
            mock_cache_dir.__truediv__.return_value = mock_path
            tool_module._load_state()
        
        assert "tool1" in tool_module.REGISTERED_TOOLS
        assert "chain1" in tool_module.DEFINED_CHAINS
        assert len(tool_module.EXECUTION_HISTORY) == 1
    
    def test_load_state_not_exists_coverage(self):
        """Test _load_state when file doesn't exist."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        
        with patch('mcp_handley_lab.tool_chainer.tool.CACHE_DIR') as mock_cache_dir:
            mock_cache_dir.__truediv__.return_value = mock_path
            tool_module._load_state()
        
        # Should not raise error
        assert len(tool_module.REGISTERED_TOOLS) == 0
    
    def test_load_state_json_error_coverage(self):
        """Test _load_state with JSON decode error."""
        mock_file = mock_open(read_data="invalid json")
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        
        with patch('builtins.open', mock_file), \
             patch('mcp_handley_lab.tool_chainer.tool.CACHE_DIR') as mock_cache_dir:
            mock_cache_dir.__truediv__.return_value = mock_path
            tool_module._load_state()
        
        # Should not raise error, just skip loading
        assert len(tool_module.REGISTERED_TOOLS) == 0
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_execute_mcp_tool_exception_coverage(self, mock_unlink, mock_tempfile, mock_subprocess):
        """Test _execute_mcp_tool general exception handling."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        # Make subprocess.run raise a general exception
        mock_subprocess.side_effect = Exception("Unexpected error")
        
        result = tool_module._execute_mcp_tool("python tool.py", "test_tool", {})
        
        assert result["success"] is False
        assert "Execution error: Unexpected error" in result["error"]
    
    def test_evaluate_condition_eval_coverage(self):
        """Test _evaluate_condition with eval path."""
        # Test simple boolean expression that goes through eval
        result = tool_module._evaluate_condition("1 < 2", {}, {})
        assert result is True
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_discover_tools_server_error_coverage(self, mock_unlink, mock_tempfile, mock_subprocess):
        """Test discover_tools with server error response."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "error": {"message": "Server error occurred"}
        })
        mock_subprocess.return_value = mock_result
        
        result = tool_module.discover_tools("python server.py")
        
        assert "❌ Server error:" in result
        assert "Server error occurred" in result
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_discover_tools_general_exception_coverage(self, mock_unlink, mock_tempfile, mock_subprocess):
        """Test discover_tools with general exception."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_subprocess.side_effect = Exception("Unexpected error")
        
        result = tool_module.discover_tools("python server.py")
        
        assert "❌ Discovery error:" in result
        assert "Unexpected error" in result
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    @patch('pathlib.Path.write_text')
    def test_execute_chain_save_to_file_coverage(self, mock_write_text, mock_save_state):
        """Test execute_chain with save_to_file functionality."""
        # Set up a chain with save_to_file
        tool_module.REGISTERED_TOOLS["test_tool"] = {
            "server_command": "python server.py",
            "tool_name": "test",
            "timeout": 30
        }
        
        tool_module.DEFINED_CHAINS["save_chain"] = {
            "steps": [{
                "tool_id": "test_tool",
                "arguments": {},
                "condition": None,
                "output_to": None
            }],
            "save_to_file": "/tmp/output.txt"
        }
        
        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {"success": True, "result": "Test output"}
            result = tool_module.execute_chain("save_chain")
        
        # Should have saved to file
        mock_write_text.assert_called_once_with("Test output")
        assert "✅ Success" in result
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    @patch('pathlib.Path.write_text')
    def test_execute_chain_save_error_coverage(self, mock_write_text, mock_save_state):
        """Test execute_chain with save file error."""
        # Set up a chain with save_to_file that will fail
        tool_module.REGISTERED_TOOLS["test_tool"] = {
            "server_command": "python server.py",
            "tool_name": "test",
            "timeout": 30
        }
        
        tool_module.DEFINED_CHAINS["save_chain"] = {
            "steps": [{
                "tool_id": "test_tool",
                "arguments": {},
                "condition": None,
                "output_to": None
            }],
            "save_to_file": "/tmp/output.txt"
        }
        
        # Make file writing fail
        mock_write_text.side_effect = PermissionError("Cannot write file")
        
        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {"success": True, "result": "Test output"}
            result = tool_module.execute_chain("save_chain")
        
        # Should succeed but note the save error in execution log
        assert "✅ Success" in result
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_general_exception_coverage(self, mock_save_state):
        """Test execute_chain with general exception."""
        tool_module.DEFINED_CHAINS["error_chain"] = {
            "steps": [{
                "tool_id": "nonexistent_tool",
                "arguments": {},
                "condition": None,
                "output_to": None
            }],
            "save_to_file": None
        }
        
        result = tool_module.execute_chain("error_chain")
        
        assert "❌ Failed" in result
        assert "Chain execution error" in result
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_with_variables_coverage(self, mock_save_state):
        """Test execute_chain with variable substitution."""
        tool_module.REGISTERED_TOOLS["echo_tool"] = {
            "server_command": "echo",
            "tool_name": "echo",
            "timeout": 30
        }
        
        tool_module.DEFINED_CHAINS["var_chain"] = {
            "steps": [{
                "tool_id": "echo_tool",
                "arguments": {"message": "Hello {NAME}"},
                "condition": None,
                "output_to": "greeting"
            }],
            "save_to_file": None
        }
        
        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {"success": True, "result": "Hello World"}
            
            result = tool_module.execute_chain(
                "var_chain",
                variables={"NAME": "World"}
            )
        
        assert "✅ Success" in result
        
        # Check that variable was substituted
        call_args = mock_execute.call_args[0]
        assert call_args[2]["message"] == "Hello World"
    
    def test_show_history_with_no_duration_coverage(self):
        """Test show_history with execution that has no duration."""
        tool_module.EXECUTION_HISTORY.append({
            "chain_id": "test_chain",
            "started_at": "2024-01-01T10:00:00",
            "success": True,
            # No total_duration field
        })
        
        result = tool_module.show_history()
        
        assert "test_chain" in result
        assert "(0.0s)" in result  # Default duration
    
    @patch('pathlib.Path.glob')
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_clear_cache_coverage(self, mock_save_state, mock_glob):
        """Test clear_cache function."""
        # Set up some data to clear
        tool_module.EXECUTION_HISTORY.append({"test": "data"})
        
        # Mock cache files
        mock_file1 = MagicMock()
        mock_file2 = MagicMock()
        mock_glob.return_value = [mock_file1, mock_file2]
        
        result = tool_module.clear_cache()
        
        assert "✅ Cache and execution history cleared successfully!" in result
        assert len(tool_module.EXECUTION_HISTORY) == 0
        mock_file1.unlink.assert_called_once()
        mock_file2.unlink.assert_called_once()
        mock_save_state.assert_called_once()
    
    def test_server_info_complete_coverage(self):
        """Test server_info with all data."""
        tool_module.REGISTERED_TOOLS["tool1"] = {
            "tool_name": "test_tool",
            "server_command": "python server.py"
        }
        tool_module.DEFINED_CHAINS["chain1"] = {
            "steps": [{"tool_id": "tool1"}]
        }
        tool_module.EXECUTION_HISTORY.append({"test": "execution"})
        
        result = tool_module.server_info()
        
        assert "Tool Chainer Server Status" in result
        assert "Status: Ready ✓" in result
        assert "**Registered Tools:** 1" in result
        assert "tool1: test_tool" in result
        assert "**Defined Chains:** 1" in result
        assert "chain1: 1 steps" in result
        assert "**Execution History:** 1 executions" in result


    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_execute_mcp_tool_json_parse_coverage(self, mock_unlink, mock_tempfile, mock_subprocess):
        """Test _execute_mcp_tool with various JSON responses."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        # Test response with nested result structure
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "result": {
                "content": [
                    {"text": "Response text"},
                    {"other": "data"}
                ]
            }
        })
        mock_subprocess.return_value = mock_result
        
        result = tool_module._execute_mcp_tool("python tool.py", "test_tool", {})
        
        assert result["success"] is True
        assert result["result"] == "Response text"
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_execute_mcp_tool_empty_content_coverage(self, mock_unlink, mock_tempfile, mock_subprocess):
        """Test _execute_mcp_tool with empty content array."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        # Test response with empty content
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "result": {
                "content": []
            }
        })
        mock_subprocess.return_value = mock_result
        
        result = tool_module._execute_mcp_tool("python tool.py", "test_tool", {})
        
        assert result["success"] is True
        assert result["result"] == ""
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_execute_mcp_tool_cleanup_error_coverage(self, mock_unlink, mock_tempfile, mock_subprocess):
        """Test _execute_mcp_tool when cleanup fails."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"result": {"content": [{"text": "OK"}]}})
        mock_subprocess.return_value = mock_result
        
        # Make unlink fail
        mock_unlink.side_effect = OSError("Cannot delete")
        
        # Should still succeed even if cleanup fails
        result = tool_module._execute_mcp_tool("python tool.py", "test_tool", {})
        assert result["success"] is True
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_execute_mcp_tool_no_text_coverage(self, mock_unlink, mock_tempfile, mock_subprocess):
        """Test _execute_mcp_tool with content but no text field."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        # Test response with content but no text
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "result": {
                "content": [{"other": "data"}]
            }
        })
        mock_subprocess.return_value = mock_result
        
        result = tool_module._execute_mcp_tool("python tool.py", "test_tool", {})
        
        assert result["success"] is True
        assert result["result"] == ""
    
    def test_substitute_variables_edge_cases_coverage(self):
        """Test _substitute_variables with edge cases."""
        # Test with non-string arguments in step
        result = tool_module._substitute_variables(
            {"key": "value {VAR}", "number": 123},
            {"VAR": "test"},
            {}
        )
        # Should return as-is for non-string
        assert result == {"key": "value {VAR}", "number": 123}
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_register_tool_and_chain_coverage(self, mock_save_state):
        """Test register_tool and chain_tools for coverage."""
        # Register a tool
        result = tool_module.register_tool(
            "coverage_tool",
            "python coverage.py",
            "test_func",
            "Test tool for coverage",
            "json",
            45
        )
        assert "✅ Tool 'coverage_tool' registered successfully!" in result
        
        # Create a chain
        from mcp_handley_lab.tool_chainer.tool import ToolStep
        steps = [
            ToolStep(
                tool_id="coverage_tool",
                arguments={"test": "arg"},
                condition="True",
                output_to="output1"
            )
        ]
        
        result = tool_module.chain_tools("coverage_chain", steps, "/tmp/out.json")
        assert "✅ Chain 'coverage_chain' defined successfully!" in result
        assert "output1" in result
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_skipped_steps_coverage(self, mock_save_state):
        """Test execute_chain with all steps skipped."""
        tool_module.REGISTERED_TOOLS["skip_tool"] = {
            "server_command": "echo",
            "tool_name": "echo",
            "timeout": 30
        }
        
        tool_module.DEFINED_CHAINS["skip_chain"] = {
            "steps": [{
                "tool_id": "skip_tool",
                "arguments": {},
                "condition": "False",  # Will be skipped
                "output_to": None
            }],
            "save_to_file": None
        }
        
        result = tool_module.execute_chain("skip_chain")
        
        assert "✅ Success" in result
        assert "0/1" in result  # 0 executed, 1 total
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_complex_substitution_coverage(self, mock_save_state):
        """Test execute_chain with complex variable substitution."""
        tool_module.REGISTERED_TOOLS["complex_tool"] = {
            "server_command": "echo",
            "tool_name": "echo",
            "timeout": 30
        }
        
        tool_module.DEFINED_CHAINS["complex_chain"] = {
            "steps": [
                {
                    "tool_id": "complex_tool",
                    "arguments": {
                        "text": "Hello {INITIAL_INPUT}",
                        "number": 42,  # Non-string argument
                        "nested": {"key": "value"}  # Complex type
                    },
                    "condition": None,
                    "output_to": "step_1"
                },
                {
                    "tool_id": "complex_tool",
                    "arguments": {"text": "Result: {step_1}"},
                    "condition": None,
                    "output_to": None
                }
            ],
            "save_to_file": None
        }
        
        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {"success": True, "result": "Hello World"}
            
            result = tool_module.execute_chain("complex_chain", initial_input="World")
        
        assert "✅ Success" in result
        assert "2/2" in result


class TestToolStepModel:
    """Test ToolStep pydantic model."""
    
    def test_tool_step_validation(self):
        """Test ToolStep model validation."""
        from mcp_handley_lab.tool_chainer.tool import ToolStep
        
        # Valid step
        step = ToolStep(
            tool_id="test",
            arguments={"arg": "value"},
            condition="test == true",
            output_to="result"
        )
        assert step.tool_id == "test"
        assert step.condition == "test == true"
        assert step.output_to == "result"
        
        # Minimal step
        step2 = ToolStep(tool_id="minimal", arguments={})
        assert step2.condition is None
        assert step2.output_to is None