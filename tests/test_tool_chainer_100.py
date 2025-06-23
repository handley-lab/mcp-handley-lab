"""Final push to 100% coverage for Tool Chainer."""
import json
import subprocess
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, mock_open
import mcp_handley_lab.tool_chainer.tool as tool_module


class TestToolChainer100Coverage:
    """Tests to reach 100% coverage."""
    
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
    
    @patch('pathlib.Path.unlink')
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_discover_tools_timeout_coverage(self, mock_tempfile, mock_subprocess, mock_unlink):
        """Test discover_tools with timeout."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        # Make subprocess.run raise TimeoutExpired
        mock_subprocess.side_effect = subprocess.TimeoutExpired("cmd", 5)
        
        result = tool_module.discover_tools("python server.py", timeout=5)
        
        assert "❌ Server discovery timed out after 5 seconds" in result
    
    @patch('pathlib.Path.unlink')
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_discover_tools_with_tools_coverage(self, mock_tempfile, mock_subprocess, mock_unlink):
        """Test discover_tools when tools are found."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "result": {
                "tools": [
                    {"name": "tool1", "description": "First tool"},
                    {"name": "tool2"}  # No description
                ]
            }
        })
        mock_subprocess.return_value = mock_result
        
        result = tool_module.discover_tools("python server.py")
        
        assert "🔧 **Discovered 2 tools:**" in result
        assert "**tool1**" in result
        assert "First tool" in result
        assert "**tool2**" in result
        assert "No description" in result
    
    @patch('pathlib.Path.unlink')
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_discover_tools_server_error_with_message(self, mock_tempfile, mock_subprocess, mock_unlink):
        """Test discover_tools with server error that has message."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "error": {"message": "Authentication failed"}
        })
        mock_subprocess.return_value = mock_result
        
        result = tool_module.discover_tools("python server.py")
        
        assert "❌ Server error: Authentication failed" in result
    
    @patch('mcp_handley_lab.tool_chainer.tool.Path')
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_execute_mcp_tool_cleanup_always_happens(self, mock_tempfile, mock_subprocess, mock_path_class):
        """Test that cleanup happens even after exceptions."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        # Create a mock Path instance
        mock_path_instance = MagicMock()
        mock_path_class.return_value = mock_path_instance
        
        # Make subprocess.run raise an exception
        mock_subprocess.side_effect = Exception("Unexpected error")
        
        result = tool_module._execute_mcp_tool("cmd", "tool", {})
        
        # Verify cleanup was attempted
        mock_path_class.assert_called_with("/tmp/request.json")
        mock_path_instance.unlink.assert_called_once()
        
        assert result["success"] is False
        assert "Execution error: Unexpected error" in result["error"]
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_step_failure_coverage(self, mock_save_state):
        """Test execute_chain when a step fails."""
        tool_module.REGISTERED_TOOLS["fail_tool"] = {
            "server_command": "false",
            "tool_name": "fail",
            "timeout": 30
        }
        
        tool_module.DEFINED_CHAINS["fail_chain"] = {
            "steps": [
                {
                    "tool_id": "fail_tool",
                    "arguments": {},
                    "condition": None,
                    "output_to": None
                },
                {
                    "tool_id": "fail_tool",
                    "arguments": {},
                    "condition": None,
                    "output_to": None
                }
            ],
            "save_to_file": None
        }
        
        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            # First call fails
            mock_execute.return_value = {"success": False, "error": "Command failed"}
            
            result = tool_module.execute_chain("fail_chain")
        
        assert "❌ Failed" in result
        assert "Step 1 failed: Command failed" in result
        # Should not execute second step
        assert mock_execute.call_count == 1
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_save_error_logging(self, mock_save_state):
        """Test that save errors are logged in execution history."""
        tool_module.REGISTERED_TOOLS["save_tool"] = {
            "server_command": "echo",
            "tool_name": "echo",
            "timeout": 30
        }
        
        tool_module.DEFINED_CHAINS["save_error_chain"] = {
            "steps": [{
                "tool_id": "save_tool",
                "arguments": {"msg": "test"},
                "condition": None,
                "output_to": None
            }],
            "save_to_file": "/invalid/path/file.txt"
        }
        
        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {"success": True, "result": "Output"}
            
            with patch('pathlib.Path.write_text') as mock_write:
                mock_write.side_effect = PermissionError("No write access")
                
                result = tool_module.execute_chain("save_error_chain")
        
        # Should still succeed
        assert "✅ Success" in result
        
        # Check that error was logged
        execution = tool_module.EXECUTION_HISTORY[-1]
        assert "save_error" in execution
        assert "Failed to save to file" in execution["save_error"]
    
    def test_server_info_no_data(self):
        """Test server_info with empty state."""
        result = tool_module.server_info()
        
        assert "Tool Chainer Server Status" in result
        assert "**Registered Tools:** 0" in result
        assert "**Defined Chains:** 0" in result
        assert "**Execution History:** 0 executions" in result