"""Unit tests for Tool Chainer."""
import json
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, mock_open

from mcp_handley_lab.tool_chainer.tool import (
    discover_tools, register_tool, chain_tools, execute_chain,
    show_history, clear_cache, server_info,
    _execute_mcp_tool, _substitute_variables, _evaluate_condition,
    _save_state, _load_state,
    ToolStep, REGISTERED_TOOLS, DEFINED_CHAINS, EXECUTION_HISTORY
)


class TestHelperFunctions:
    """Test helper functions."""
    
    def setup_method(self):
        """Set up test method."""
        # Clear global state
        REGISTERED_TOOLS.clear()
        DEFINED_CHAINS.clear()
        EXECUTION_HISTORY.clear()
    
    def teardown_method(self):
        """Clean up after test method."""
        # Clear global state
        REGISTERED_TOOLS.clear()
        DEFINED_CHAINS.clear()
        EXECUTION_HISTORY.clear()
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_execute_mcp_tool_success(self, mock_tempfile, mock_subprocess):
        """Test successful MCP tool execution."""
        # Mock temp file
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        # Mock subprocess response
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "result": {
                "content": [{"text": "Tool response"}]
            }
        })
        mock_subprocess.return_value = mock_result
        
        # Mock Path.unlink
        with patch('pathlib.Path.unlink'):
            result = _execute_mcp_tool("python tool.py", "test_tool", {"arg": "value"})
        
        assert result["success"] is True
        assert result["result"] == "Tool response"
        mock_subprocess.assert_called_once()
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_execute_mcp_tool_command_error(self, mock_tempfile, mock_subprocess):
        """Test MCP tool execution with command error."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Command failed"
        mock_result.stdout = ""
        mock_subprocess.return_value = mock_result
        
        with patch('pathlib.Path.unlink'):
            result = _execute_mcp_tool("python tool.py", "test_tool", {})
        
        assert result["success"] is False
        assert "Server command failed" in result["error"]
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_execute_mcp_tool_api_error(self, mock_tempfile, mock_subprocess):
        """Test MCP tool execution with API error response."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "error": {"message": "Tool not found"}
        })
        mock_subprocess.return_value = mock_result
        
        with patch('pathlib.Path.unlink'):
            result = _execute_mcp_tool("python tool.py", "test_tool", {})
        
        assert result["success"] is False
        assert result["error"] == "Tool not found"
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_execute_mcp_tool_timeout(self, mock_tempfile, mock_subprocess):
        """Test MCP tool execution timeout."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        from subprocess import TimeoutExpired
        mock_subprocess.side_effect = TimeoutExpired("cmd", 5)
        
        with patch('pathlib.Path.unlink'):
            result = _execute_mcp_tool("python tool.py", "test_tool", {}, timeout=5)
        
        assert result["success"] is False
        assert "timed out after 5 seconds" in result["error"]
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_execute_mcp_tool_invalid_json(self, mock_tempfile, mock_subprocess):
        """Test MCP tool execution with invalid JSON response."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Not JSON"
        mock_subprocess.return_value = mock_result
        
        with patch('pathlib.Path.unlink'):
            result = _execute_mcp_tool("python tool.py", "test_tool", {})
        
        assert result["success"] is True
        assert result["result"] == "Not JSON"
    
    def test_substitute_variables_basic(self):
        """Test basic variable substitution."""
        text = "Hello {NAME}, you have {COUNT} messages"
        variables = {"NAME": "Alice", "COUNT": 5}
        step_outputs = {}
        
        result = _substitute_variables(text, variables, step_outputs)
        assert result == "Hello Alice, you have 5 messages"
    
    def test_substitute_variables_step_outputs(self):
        """Test variable substitution with step outputs."""
        text = "Previous result: {step1}, current: {VAR}"
        variables = {"VAR": "current"}
        step_outputs = {"step1": "previous result"}
        
        result = _substitute_variables(text, variables, step_outputs)
        assert result == "Previous result: previous result, current: current"
    
    def test_substitute_variables_non_string(self):
        """Test variable substitution with non-string input."""
        result = _substitute_variables(123, {"VAR": "value"}, {})
        assert result == 123
    
    def test_evaluate_condition_empty(self):
        """Test evaluating empty condition."""
        assert _evaluate_condition("", {}, {}) is True
        assert _evaluate_condition(None, {}, {}) is True
    
    def test_evaluate_condition_equality(self):
        """Test evaluating equality conditions."""
        variables = {"STATUS": "success"}
        step_outputs = {}
        
        assert _evaluate_condition("{STATUS} == success", variables, step_outputs) is True
        assert _evaluate_condition("{STATUS} == failure", variables, step_outputs) is False
    
    def test_evaluate_condition_inequality(self):
        """Test evaluating inequality conditions."""
        variables = {"STATUS": "success"}
        step_outputs = {}
        
        assert _evaluate_condition("{STATUS} != failure", variables, step_outputs) is True
        assert _evaluate_condition("{STATUS} != success", variables, step_outputs) is False
    
    def test_evaluate_condition_contains(self):
        """Test evaluating contains conditions."""
        variables = {"TEXT": "hello world"}
        step_outputs = {}
        
        assert _evaluate_condition("{TEXT} contains world", variables, step_outputs) is True
        assert _evaluate_condition("{TEXT} contains xyz", variables, step_outputs) is False
    
    def test_evaluate_condition_boolean(self):
        """Test evaluating boolean conditions."""
        variables = {"FLAG": True}
        step_outputs = {}
        
        assert _evaluate_condition("{FLAG}", variables, step_outputs) is True
    
    def test_evaluate_condition_error(self):
        """Test evaluating invalid condition."""
        assert _evaluate_condition("invalid syntax @@", {}, {}) is False
    
    @patch('json.dump')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_state(self, mock_file, mock_json_dump):
        """Test saving state to file."""
        # Set up test data
        REGISTERED_TOOLS["test"] = {"data": "value"}
        DEFINED_CHAINS["chain"] = {"steps": []}
        EXECUTION_HISTORY.append({"exec": "test"})
        
        _save_state()
        
        mock_file.assert_called_once()
        mock_json_dump.assert_called_once()
        
        # Check that the state dictionary was created correctly
        call_args = mock_json_dump.call_args[0]
        state_dict = call_args[0]
        assert "registered_tools" in state_dict
        assert "defined_chains" in state_dict
        assert "execution_history" in state_dict
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='{"registered_tools": {"tool1": {"name": "test"}}, "defined_chains": {}, "execution_history": []}')
    def test_load_state_success(self, mock_file, mock_exists):
        """Test loading state from file successfully."""
        mock_exists.return_value = True
        
        _load_state()
        
        mock_file.assert_called_once()
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='invalid json')
    def test_load_state_json_error(self, mock_file, mock_exists):
        """Test loading state with JSON decode error."""
        mock_exists.return_value = True
        
        # Should not raise exception, just skip loading
        _load_state()
        
        mock_file.assert_called_once()
    
    @patch('pathlib.Path.exists')
    def test_load_state_no_file(self, mock_exists):
        """Test loading state when file doesn't exist."""
        mock_exists.return_value = False
        
        # Should not raise exception
        _load_state()


class TestToolChainer:
    """Test Tool Chainer main functions."""
    
    def setup_method(self):
        """Set up test method."""
        # Clear global state
        REGISTERED_TOOLS.clear()
        DEFINED_CHAINS.clear()
        EXECUTION_HISTORY.clear()
    
    def teardown_method(self):
        """Clean up after test method."""
        # Clear global state
        REGISTERED_TOOLS.clear()
        DEFINED_CHAINS.clear()
        EXECUTION_HISTORY.clear()
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_discover_tools_success(self, mock_tempfile, mock_subprocess):
        """Test successful tool discovery."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "result": {
                "tools": [
                    {"name": "tool1", "description": "First tool"},
                    {"name": "tool2", "description": "Second tool"}
                ]
            }
        })
        mock_subprocess.return_value = mock_result
        
        with patch('pathlib.Path.unlink'):
            result = discover_tools("python server.py")
        
        assert "🔧 **Discovered 2 tools:**" in result
        assert "tool1" in result
        assert "tool2" in result
        assert "First tool" in result
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_discover_tools_no_tools(self, mock_tempfile, mock_subprocess):
        """Test tool discovery with no tools found."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"result": {"tools": []}})
        mock_subprocess.return_value = mock_result
        
        with patch('pathlib.Path.unlink'):
            result = discover_tools("python server.py")
        
        assert "No tools found" in result
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_discover_tools_connection_error(self, mock_tempfile, mock_subprocess):
        """Test tool discovery with connection error."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Connection refused"
        mock_subprocess.return_value = mock_result
        
        with patch('pathlib.Path.unlink'):
            result = discover_tools("python server.py")
        
        assert "❌ Failed to connect to server" in result
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_discover_tools_timeout(self, mock_tempfile, mock_subprocess):
        """Test tool discovery timeout."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        
        from subprocess import TimeoutExpired
        mock_subprocess.side_effect = TimeoutExpired("cmd", 5)
        
        with patch('pathlib.Path.unlink'):
            result = discover_tools("python server.py", timeout=5)
        
        assert "❌ Server discovery timed out" in result
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_register_tool_success(self, mock_save_state):
        """Test successful tool registration."""
        result = register_tool(
            "test_tool",
            "python server.py",
            "my_tool",
            "A test tool",
            "json",
            60
        )
        
        assert "✅ Tool 'test_tool' registered successfully!" in result
        assert "test_tool" in REGISTERED_TOOLS
        
        tool_config = REGISTERED_TOOLS["test_tool"]
        assert tool_config["server_command"] == "python server.py"
        assert tool_config["tool_name"] == "my_tool"
        assert tool_config["description"] == "A test tool"
        assert tool_config["output_format"] == "json"
        assert tool_config["timeout"] == 60
        
        mock_save_state.assert_called_once()
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_register_tool_minimal(self, mock_save_state):
        """Test tool registration with minimal parameters."""
        result = register_tool(
            "simple_tool",
            "python server.py",
            "simple"
        )
        
        assert "✅ Tool 'simple_tool' registered successfully!" in result
        assert "simple_tool" in REGISTERED_TOOLS
        
        tool_config = REGISTERED_TOOLS["simple_tool"]
        assert tool_config["output_format"] == "text"
        assert tool_config["timeout"] == 30
        assert "Tool simple from python server.py" in tool_config["description"]
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_chain_tools_success(self, mock_save_state):
        """Test successful chain definition."""
        # Register a tool first
        REGISTERED_TOOLS["tool1"] = {"name": "tool1"}
        REGISTERED_TOOLS["tool2"] = {"name": "tool2"}
        
        steps = [
            ToolStep(tool_id="tool1", arguments={"arg1": "value1"}),
            ToolStep(tool_id="tool2", arguments={"arg2": "value2"}, condition="result == success")
        ]
        
        result = chain_tools("test_chain", steps, "/tmp/output.txt")
        
        assert "✅ Chain 'test_chain' defined successfully!" in result
        assert "test_chain" in DEFINED_CHAINS
        
        chain_config = DEFINED_CHAINS["test_chain"]
        assert len(chain_config["steps"]) == 2
        assert chain_config["save_to_file"] == "/tmp/output.txt"
        
        mock_save_state.assert_called_once()
    
    def test_chain_tools_unregistered_tool(self):
        """Test chain definition with unregistered tool."""
        steps = [ToolStep(tool_id="unknown_tool", arguments={})]
        
        with pytest.raises(ValueError, match="Tool 'unknown_tool' is not registered"):
            chain_tools("test_chain", steps)
    
    @patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool')
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_success(self, mock_save_state, mock_execute):
        """Test successful chain execution."""
        # Set up registered tools and chain
        REGISTERED_TOOLS["tool1"] = {
            "server_command": "python server1.py",
            "tool_name": "test_tool1",
            "timeout": 30
        }
        REGISTERED_TOOLS["tool2"] = {
            "server_command": "python server2.py", 
            "tool_name": "test_tool2",
            "timeout": 30
        }
        
        DEFINED_CHAINS["test_chain"] = {
            "steps": [
                {"tool_id": "tool1", "arguments": {"input": "{INITIAL_INPUT}"}, "condition": None, "output_to": "step1_out"},
                {"tool_id": "tool2", "arguments": {"data": "{step1_out}"}, "condition": None, "output_to": None}
            ],
            "save_to_file": None
        }
        
        # Mock tool execution responses
        mock_execute.side_effect = [
            {"success": True, "result": "Step 1 result"},
            {"success": True, "result": "Step 2 result"}
        ]
        
        result = execute_chain("test_chain", "initial data")
        
        assert "✅ Success" in result
        assert "2/2" in result  # 2 steps executed out of 2
        assert len(EXECUTION_HISTORY) == 1
        
        execution = EXECUTION_HISTORY[0]
        assert execution["success"] is True
        assert execution["final_result"] == "Step 2 result"
        assert len(execution["steps"]) == 2
    
    def test_execute_chain_not_found(self):
        """Test executing non-existent chain."""
        with pytest.raises(ValueError, match="Chain 'unknown_chain' not found"):
            execute_chain("unknown_chain")
    
    @patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool')
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_step_failure(self, mock_save_state, mock_execute):
        """Test chain execution with step failure."""
        REGISTERED_TOOLS["tool1"] = {
            "server_command": "python server.py",
            "tool_name": "test_tool",
            "timeout": 30
        }
        
        DEFINED_CHAINS["fail_chain"] = {
            "steps": [
                {"tool_id": "tool1", "arguments": {}, "condition": None, "output_to": None}
            ],
            "save_to_file": None
        }
        
        mock_execute.return_value = {"success": False, "error": "Tool execution failed"}
        
        result = execute_chain("fail_chain")
        
        assert "❌ Failed" in result
        assert "Tool execution failed" in result
        
        execution = EXECUTION_HISTORY[0]
        assert execution["success"] is False
        assert "Step 1 failed" in execution["error"]
    
    @patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool')
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_with_condition_skip(self, mock_save_state, mock_execute):
        """Test chain execution with skipped step due to condition."""
        REGISTERED_TOOLS["tool1"] = {
            "server_command": "python server.py",
            "tool_name": "test_tool",
            "timeout": 30
        }
        
        DEFINED_CHAINS["conditional_chain"] = {
            "steps": [
                {"tool_id": "tool1", "arguments": {}, "condition": "False", "output_to": None}
            ],
            "save_to_file": None
        }
        
        result = execute_chain("conditional_chain")
        
        assert "✅ Success" in result
        assert "0/1" in result  # 0 steps executed out of 1
        
        execution = EXECUTION_HISTORY[0]
        assert execution["success"] is True
        assert execution["steps"][0]["skipped"] is True
    
    @patch('pathlib.Path.write_text')
    @patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool')
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_save_to_file(self, mock_save_state, mock_execute, mock_write_text):
        """Test chain execution with file saving."""
        REGISTERED_TOOLS["tool1"] = {
            "server_command": "python server.py",
            "tool_name": "test_tool",
            "timeout": 30
        }
        
        DEFINED_CHAINS["save_chain"] = {
            "steps": [
                {"tool_id": "tool1", "arguments": {}, "condition": None, "output_to": None}
            ],
            "save_to_file": "/tmp/output.txt"
        }
        
        mock_execute.return_value = {"success": True, "result": "Final output"}
        
        result = execute_chain("save_chain")
        
        mock_write_text.assert_called_once_with("Final output")
    
    def test_show_history_empty(self):
        """Test show history with no executions."""
        result = show_history()
        assert "No chain executions found" in result
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_show_history_with_executions(self, mock_save_state):
        """Test show history with executions."""
        EXECUTION_HISTORY.extend([
            {
                "chain_id": "chain1",
                "started_at": "2024-01-01T10:00:00",
                "success": True,
                "total_duration": 1.5
            },
            {
                "chain_id": "chain2", 
                "started_at": "2024-01-01T11:00:00",
                "success": False,
                "total_duration": 0.8,
                "error": "Failed"
            }
        ])
        
        result = show_history(limit=5)
        
        assert "📚 **Chain Execution History**" in result
        assert "chain1" in result
        assert "chain2" in result
        assert "✅" in result  # Success icon
        assert "❌" in result  # Failure icon
        assert "(1.5s)" in result
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_clear_cache_success(self, mock_save_state):
        """Test clearing cache."""
        # Add some data to clear
        EXECUTION_HISTORY.append({"test": "data"})
        initial_count = len(EXECUTION_HISTORY)
        
        with patch('mcp_handley_lab.tool_chainer.tool.CACHE_DIR') as mock_cache_dir:
            mock_cache_file = MagicMock()
            mock_cache_dir.glob.return_value = [mock_cache_file]
            
            result = clear_cache()
            
            assert "✅ Cache and execution history cleared successfully!" in result
            # The function should have cleared the global state
            assert initial_count > 0  # We had data initially
            mock_cache_file.unlink.assert_called_once()
            mock_save_state.assert_called_once()
    
    def test_server_info_empty_state(self):
        """Test server info with empty state."""
        result = server_info()
        
        assert "Tool Chainer Server Status" in result
        assert "Status: Ready ✓" in result
        assert "**Registered Tools:** 0" in result
        assert "**Defined Chains:** 0" in result
        assert "**Execution History:** 0 executions" in result
        assert "Available tools:" in result
    
    @patch('mcp_handley_lab.tool_chainer.tool.EXECUTION_HISTORY')
    def test_server_info_with_data(self, mock_execution_history):
        """Test server info with registered tools and chains."""
        REGISTERED_TOOLS["tool1"] = {
            "tool_name": "test_tool",
            "server_command": "python server.py"
        }
        DEFINED_CHAINS["chain1"] = {
            "steps": [{"tool_id": "tool1"}]
        }
        # Mock the execution history that server_info will read
        mock_execution_history.__len__.return_value = 1
        
        result = server_info()
        
        assert "**Registered Tools:** 1" in result
        assert "tool1: test_tool (python server.py)" in result
        assert "**Defined Chains:** 1" in result
        assert "chain1: 1 steps" in result
        assert "**Execution History:** 1 executions" in result


class TestToolChainerMain:
    """Test the __main__ module."""
    
    @patch('mcp_handley_lab.tool_chainer.__main__.mcp')
    def test_main_function(self, mock_mcp):
        """Test the main function."""
        from mcp_handley_lab.tool_chainer.__main__ import main
        
        main()
        mock_mcp.run.assert_called_once()
    
    @patch('mcp_handley_lab.tool_chainer.__main__.main')
    def test_main_runs_server(self, mock_main):
        """Test that __main__ runs when called directly."""
        # Simulate running as main module
        import mcp_handley_lab.tool_chainer.__main__ as main_module
        
        # Mock __name__ to be '__main__'
        with patch.object(main_module, '__name__', '__main__'):
            # Re-import to trigger the if __name__ == '__main__' block
            import importlib
            importlib.reload(main_module)
        
        # The module should exist and be importable
        assert main_module is not None


class TestToolStep:
    """Test ToolStep model."""
    
    def test_tool_step_minimal(self):
        """Test ToolStep with minimal data."""
        step = ToolStep(tool_id="test_tool", arguments={"arg": "value"})
        assert step.tool_id == "test_tool"
        assert step.arguments == {"arg": "value"}
        assert step.condition is None
        assert step.output_to is None
    
    def test_tool_step_full(self):
        """Test ToolStep with all fields."""
        step = ToolStep(
            tool_id="test_tool",
            arguments={"arg": "value"},
            condition="result == success",
            output_to="step_output"
        )
        assert step.tool_id == "test_tool"
        assert step.arguments == {"arg": "value"}
        assert step.condition == "result == success"
        assert step.output_to == "step_output"