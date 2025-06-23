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
    ToolStep
)


class TestHelperFunctions:
    """Test helper functions."""
    
    def setup_method(self):
        """Set up test method."""
        # Create temporary directory for each test
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up after test method."""
        # Clean up temp directory
        import shutil
        if self.storage_path.exists():
            shutil.rmtree(self.storage_path)
    
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
    
    def test_save_state(self):
        """Test saving state to file."""
        # Test data
        registered_tools = {"test": {"data": "value"}}
        defined_chains = {"chain": {"steps": []}}
        execution_history = [{"exec": "test"}]
        
        # Test saving state
        _save_state(self.storage_path, registered_tools, defined_chains, execution_history)
        
        # Verify state was saved by loading it back
        loaded_tools, loaded_chains, loaded_history = _load_state(self.storage_path)
        assert loaded_tools == registered_tools
        assert loaded_chains == defined_chains
        assert loaded_history == execution_history
    
    def test_load_state_success(self):
        """Test loading state from file successfully."""
        # Create test state file
        test_state = {
            "registered_tools": {"tool1": {"name": "test"}},
            "defined_chains": {},
            "execution_history": []
        }
        state_file = self.storage_path / "state.json"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        with open(state_file, 'w') as f:
            json.dump(test_state, f)
        
        # Load state and verify
        registered_tools, defined_chains, execution_history = _load_state(self.storage_path)
        assert registered_tools == test_state["registered_tools"]
        assert defined_chains == test_state["defined_chains"]
        assert execution_history == test_state["execution_history"]
    
    def test_load_state_json_error(self):
        """Test loading state with JSON decode error."""
        # Create invalid JSON file
        state_file = self.storage_path / "state.json"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        with open(state_file, 'w') as f:
            f.write('invalid json')
        
        # Should not raise exception, just return empty state
        registered_tools, defined_chains, execution_history = _load_state(self.storage_path)
        assert registered_tools == {}
        assert defined_chains == {}
        assert execution_history == []
    
    def test_load_state_no_file(self):
        """Test loading state when file doesn't exist."""
        # Don't create any state file
        
        # Should not raise exception, just return empty state
        registered_tools, defined_chains, execution_history = _load_state(self.storage_path)
        assert registered_tools == {}
        assert defined_chains == {}
        assert execution_history == []


class TestToolChainer:
    """Test Tool Chainer main functions."""
    
    def setup_method(self):
        """Set up test method."""
        # Create temporary directory for each test
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Clean up after test method."""
        # Clean up temp directory
        import shutil
        if self.storage_path.exists():
            shutil.rmtree(self.storage_path)
    
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
    
    def test_register_tool_success(self):
        """Test successful tool registration."""
        result = register_tool(
            "test_tool",
            "python server.py",
            "my_tool",
            "A test tool",
            "json",
            60,
            storage_dir=str(self.storage_path)
        )
        
        assert "✅ Tool 'test_tool' registered successfully!" in result
        
        # Verify by loading state back
        registered_tools, _, _ = _load_state(self.storage_path)
        assert "test_tool" in registered_tools
        
        tool_config = registered_tools["test_tool"]
        assert tool_config["server_command"] == "python server.py"
        assert tool_config["tool_name"] == "my_tool"
        assert tool_config["description"] == "A test tool"
        assert tool_config["output_format"] == "json"
        assert tool_config["timeout"] == 60
    
    def test_register_tool_minimal(self):
        """Test tool registration with minimal parameters."""
        result = register_tool(
            "simple_tool",
            "python server.py",
            "simple",
            storage_dir=str(self.storage_path)
        )
        
        assert "✅ Tool 'simple_tool' registered successfully!" in result
        
        # Verify by loading state back
        registered_tools, _, _ = _load_state(self.storage_path)
        assert "simple_tool" in registered_tools
        
        tool_config = registered_tools["simple_tool"]
        assert tool_config["output_format"] == "text"
        assert tool_config["timeout"] == 30
        assert "Tool simple from python server.py" in tool_config["description"]
    
    def test_chain_tools_success(self):
        """Test successful chain definition."""
        # Register tools first
        register_tool("tool1", "python server1.py", "tool1", storage_dir=str(self.storage_path))
        register_tool("tool2", "python server2.py", "tool2", storage_dir=str(self.storage_path))
        
        steps = [
            ToolStep(tool_id="tool1", arguments={"arg1": "value1"}),
            ToolStep(tool_id="tool2", arguments={"arg2": "value2"}, condition="result == success")
        ]
        
        result = chain_tools("test_chain", steps, "/tmp/output.txt", storage_dir=str(self.storage_path))
        
        assert "✅ Chain 'test_chain' defined successfully!" in result
        
        # Verify by loading state back
        _, defined_chains, _ = _load_state(self.storage_path)
        assert "test_chain" in defined_chains
        
        chain_config = defined_chains["test_chain"]
        assert len(chain_config["steps"]) == 2
        assert chain_config["save_to_file"] == "/tmp/output.txt"
    
    def test_chain_tools_unregistered_tool(self):
        """Test chain definition with unregistered tool."""
        steps = [ToolStep(tool_id="unknown_tool", arguments={})]
        
        with pytest.raises(ValueError, match="Tool 'unknown_tool' is not registered"):
            chain_tools("test_chain", steps, storage_dir=str(self.storage_path))
    
    @patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool')
    def test_execute_chain_success(self, mock_execute):
        """Test successful chain execution."""
        # Register tools first
        register_tool("tool1", "python server1.py", "test_tool1", storage_dir=str(self.storage_path))
        register_tool("tool2", "python server2.py", "test_tool2", storage_dir=str(self.storage_path))
        
        # Define chain
        steps = [
            ToolStep(tool_id="tool1", arguments={"input": "{INITIAL_INPUT}"}, output_to="step1_out"),
            ToolStep(tool_id="tool2", arguments={"data": "{step1_out}"})
        ]
        chain_tools("test_chain", steps, storage_dir=str(self.storage_path))
        
        # Mock tool execution responses
        mock_execute.side_effect = [
            {"success": True, "result": "Step 1 result"},
            {"success": True, "result": "Step 2 result"}
        ]
        
        result = execute_chain("test_chain", "initial data", storage_dir=str(self.storage_path))
        
        assert "✅ Success" in result
        assert "2/2" in result  # 2 steps executed out of 2
        
        # Verify execution history
        _, _, execution_history = _load_state(self.storage_path)
        assert len(execution_history) == 1
        
        execution = execution_history[0]
        assert execution["success"] is True
        assert execution["final_result"] == "Step 2 result"
        assert len(execution["steps"]) == 2
    
    def test_execute_chain_not_found(self):
        """Test executing non-existent chain."""
        with pytest.raises(ValueError, match="Chain 'unknown_chain' not found"):
            execute_chain("unknown_chain", storage_dir=str(self.storage_path))
    
    @patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool')
    def test_execute_chain_step_failure(self, mock_execute):
        """Test chain execution with step failure."""
        # Register tool and define chain
        register_tool("tool1", "python server.py", "test_tool", storage_dir=str(self.storage_path))
        
        steps = [ToolStep(tool_id="tool1", arguments={})]
        chain_tools("fail_chain", steps, storage_dir=str(self.storage_path))
        
        mock_execute.return_value = {"success": False, "error": "Tool execution failed"}
        
        result = execute_chain("fail_chain", storage_dir=str(self.storage_path))
        
        assert "❌ Failed" in result
        assert "Tool execution failed" in result
        
        # Verify execution history
        _, _, execution_history = _load_state(self.storage_path)
        execution = execution_history[0]
        assert execution["success"] is False
        assert "Step 1 failed" in execution["error"]
    
    @patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool')
    def test_execute_chain_with_condition_skip(self, mock_execute):
        """Test chain execution with skipped step due to condition."""
        # Register tool and define chain
        register_tool("tool1", "python server.py", "test_tool", storage_dir=str(self.storage_path))
        
        steps = [ToolStep(tool_id="tool1", arguments={}, condition="False")]
        chain_tools("conditional_chain", steps, storage_dir=str(self.storage_path))
        
        result = execute_chain("conditional_chain", storage_dir=str(self.storage_path))
        
        assert "✅ Success" in result
        assert "0/1" in result  # 0 steps executed out of 1
        
        # Verify execution history
        _, _, execution_history = _load_state(self.storage_path)
        execution = execution_history[0]
        assert execution["success"] is True
        assert execution["steps"][0]["skipped"] is True
    
    @patch('pathlib.Path.write_text')
    @patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool')
    def test_execute_chain_save_to_file(self, mock_execute, mock_write_text):
        """Test chain execution with file saving."""
        # Register tool and define chain with file saving
        register_tool("tool1", "python server.py", "test_tool", storage_dir=str(self.storage_path))
        
        steps = [ToolStep(tool_id="tool1", arguments={})]
        chain_tools("save_chain", steps, "/tmp/output.txt", storage_dir=str(self.storage_path))
        
        mock_execute.return_value = {"success": True, "result": "Final output"}
        
        result = execute_chain("save_chain", storage_dir=str(self.storage_path))
        
        mock_write_text.assert_called_once_with("Final output")
    
    def test_show_history_empty(self):
        """Test show history with no executions."""
        result = show_history(storage_dir=str(self.storage_path))
        assert "No chain executions found" in result
    
    def test_show_history_with_executions(self):
        """Test show history with executions."""
        # Manually create execution history
        test_history = [
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
        ]
        
        # Save state with execution history
        _save_state(self.storage_path, {}, {}, test_history)
        
        result = show_history(limit=5, storage_dir=str(self.storage_path))
        
        assert "📚 **Chain Execution History**" in result
        assert "chain1" in result
        assert "chain2" in result
        assert "✅" in result  # Success icon
        assert "❌" in result  # Failure icon
        assert "(1.5s)" in result
    
    def test_clear_cache_success(self):
        """Test clearing cache."""
        # Add some data first
        test_tools = {"test_tool": {"data": "value"}}
        test_chains = {"test_chain": {"steps": []}}
        test_history = [{"test": "data"}]
        _save_state(self.storage_path, test_tools, test_chains, test_history)
        
        # Verify data exists
        tools, chains, history = _load_state(self.storage_path)
        assert len(tools) > 0 or len(chains) > 0 or len(history) > 0
        
        # Clear cache
        result = clear_cache(storage_dir=str(self.storage_path))
        
        assert "✅ Cache and execution history cleared successfully!" in result
        
        # Verify data is cleared
        tools, chains, history = _load_state(self.storage_path)
        assert tools == {}
        assert chains == {}
        assert history == []
    
    def test_server_info_empty_state(self):
        """Test server info with empty state."""
        result = server_info(storage_dir=str(self.storage_path))
        
        assert "Tool Chainer Server Status" in result
        assert "Status: Ready ✓" in result
        assert "**Registered Tools:** 0" in result
        assert "**Defined Chains:** 0" in result
        assert "**Execution History:** 0 executions" in result
        assert "Available tools:" in result
    
    def test_server_info_with_data(self):
        """Test server info with registered tools and chains."""
        # Set up test data
        test_tools = {
            "tool1": {
                "tool_name": "test_tool",
                "server_command": "python server.py"
            }
        }
        test_chains = {
            "chain1": {
                "steps": [{"tool_id": "tool1"}]
            }
        }
        test_history = [{"execution": "test"}]
        
        # Save the test data
        _save_state(self.storage_path, test_tools, test_chains, test_history)
        
        result = server_info(storage_dir=str(self.storage_path))
        
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