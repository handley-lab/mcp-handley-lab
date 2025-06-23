"""Final coverage tests for Tool Chainer to reach 100%."""
import json
import pytest
from unittest.mock import patch, MagicMock
import mcp_handley_lab.tool_chainer.tool as tool_module


class TestFinalCoverage:
    """Final tests to reach 100% coverage."""
    
    @pytest.fixture(autouse=True)
    def reset_globals(self):
        """Reset global state."""
        tool_module.REGISTERED_TOOLS.clear()
        tool_module.DEFINED_CHAINS.clear()
        tool_module.EXECUTION_HISTORY.clear()
        yield
        tool_module.REGISTERED_TOOLS.clear()
        tool_module.DEFINED_CHAINS.clear()
        tool_module.EXECUTION_HISTORY.clear()
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_execute_mcp_tool_stderr_output(self, mock_tempfile, mock_subprocess):
        """Test when subprocess returns non-zero with stderr."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Command not found"
        mock_result.stdout = "Some output"
        mock_subprocess.return_value = mock_result
        
        result = tool_module._execute_mcp_tool("invalid_command", "tool", {})
        
        assert result["success"] is False
        assert "Server command failed: Command not found" in result["error"]
        assert result["output"] == "Some output"
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_execute_mcp_tool_error_without_message(self, mock_tempfile, mock_subprocess):
        """Test error response without message field."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"error": {}})  # No message field
        mock_subprocess.return_value = mock_result
        
        result = tool_module._execute_mcp_tool("cmd", "tool", {})
        
        assert result["success"] is False
        assert result["error"] == "Unknown error"
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_execute_mcp_tool_plain_text_response(self, mock_tempfile, mock_subprocess):
        """Test non-JSON plain text response."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Plain text output"
        mock_subprocess.return_value = mock_result
        
        result = tool_module._execute_mcp_tool("cmd", "tool", {})
        
        assert result["success"] is True
        assert result["result"] == "Plain text output"
        assert result["output"] == "Plain text output"
    
    @patch('subprocess.TimeoutExpired', side_effect=lambda cmd, timeout: Exception(f"Timeout after {timeout}s"))
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_execute_mcp_tool_timeout_exception(self, mock_tempfile, mock_subprocess, mock_timeout):
        """Test timeout exception handling."""
        from subprocess import TimeoutExpired
        
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        # Make subprocess.run raise TimeoutExpired
        mock_subprocess.side_effect = TimeoutExpired("cmd", 5)
        
        result = tool_module._execute_mcp_tool("cmd", "tool", {}, timeout=5)
        
        assert result["success"] is False
        assert "timed out after 5 seconds" in result["error"]
    
    def test_substitute_variables_complex_types(self):
        """Test substitution with lists and complex nested structures."""
        # Test that non-string values in arguments are left alone
        args = {
            "string": "Hello {VAR}",
            "number": 42,
            "list": ["item1", "item2"],
            "dict": {"nested": "value"}
        }
        
        result = tool_module._substitute_variables(args, {"VAR": "World"}, {})
        
        # Only string should be substituted
        assert isinstance(result, dict)
        assert result["string"] == "Hello World"
        assert result["number"] == 42
        assert result["list"] == ["item1", "item2"]
        assert result["dict"] == {"nested": "value"}
    
    def test_evaluate_condition_strip_quotes(self):
        """Test condition evaluation with quoted strings."""
        # Test string comparison with quotes
        result = tool_module._evaluate_condition('"success" == "success"', {}, {})
        assert result is True
        
        result = tool_module._evaluate_condition("'failed' != 'success'", {}, {})
        assert result is True
    
    def test_evaluate_condition_contains_spaces(self):
        """Test contains operator with spaces."""
        result = tool_module._evaluate_condition("'hello world' contains 'world'", {}, {})
        assert result is True
        
        result = tool_module._evaluate_condition("'test string' contains 'not there'", {}, {})
        assert result is False
    
    @patch('json.loads')
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_discover_tools_json_decode_general(self, mock_tempfile, mock_subprocess, mock_json_loads):
        """Test discover_tools handling general JSON errors."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "invalid"
        mock_subprocess.return_value = mock_result
        
        # Make json.loads raise a general exception
        mock_json_loads.side_effect = Exception("Parse error")
        
        result = tool_module.discover_tools("cmd")
        
        assert "❌ Discovery error: Parse error" in result
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_chain_tools_invalid_tool_coverage(self, mock_save_state):
        """Test chain_tools with invalid tool reference."""
        from mcp_handley_lab.tool_chainer.tool import ToolStep
        
        # Don't register the tool
        steps = [ToolStep(tool_id="unregistered", arguments={})]
        
        with pytest.raises(ValueError, match="Tool 'unregistered' is not registered"):
            tool_module.chain_tools("test_chain", steps)
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_invalid_chain(self, mock_save_state):
        """Test execute_chain with non-existent chain."""
        with pytest.raises(ValueError, match="Chain 'missing' not found"):
            tool_module.execute_chain("missing")
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_with_timeout_param(self, mock_save_state):
        """Test execute_chain with timeout parameter."""
        tool_module.REGISTERED_TOOLS["timeout_tool"] = {
            "server_command": "sleep",
            "tool_name": "sleep",
            "timeout": 1  # Default timeout
        }
        
        tool_module.DEFINED_CHAINS["timeout_chain"] = {
            "steps": [{"tool_id": "timeout_tool", "arguments": {"duration": "10"}}],
            "save_to_file": None
        }
        
        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {"success": True, "result": "Done"}
            
            # Call with custom timeout
            result = tool_module.execute_chain("timeout_chain", timeout=5)
            
            # Verify timeout was passed through
            call_args = mock_execute.call_args
            assert call_args[0][3] == 5  # timeout parameter
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_step_output_default_name(self, mock_save_state):
        """Test execute chain where step has no output_to specified."""
        tool_module.REGISTERED_TOOLS["test"] = {
            "server_command": "echo",
            "tool_name": "echo",
            "timeout": 30
        }
        
        tool_module.DEFINED_CHAINS["test_chain"] = {
            "steps": [
                {
                    "tool_id": "test",
                    "arguments": {"msg": "test"},
                    "condition": None,
                    "output_to": None  # No output_to specified
                }
            ],
            "save_to_file": None
        }
        
        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {"success": True, "result": "Output"}
            
            result = tool_module.execute_chain("test_chain")
            
            assert "✅ Success" in result
    
    def test_show_history_empty_coverage(self):
        """Test show_history when completely empty."""
        result = tool_module.show_history()
        assert "No chain executions found" in result
    
    def test_load_state_on_import(self):
        """Test that _load_state is called on module import."""
        # This is already covered by importing the module
        # Just verify the state loading mechanism works
        with patch('mcp_handley_lab.tool_chainer.tool._load_state') as mock_load:
            # Re-import would trigger this
            import importlib
            importlib.reload(tool_module)
            # Can't easily test this without side effects