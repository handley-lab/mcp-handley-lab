"""Comprehensive unit tests for Tool Chainer functionality."""
import pytest
import tempfile
import json
import subprocess
import time
from unittest.mock import patch, Mock, mock_open, MagicMock
from pathlib import Path

from mcp_handley_lab.tool_chainer.tool import (
    register_tool, chain_tools, execute_chain, discover_tools, ToolStep,
    _load_state, _save_state, _execute_mcp_tool, _substitute_variables, 
    _evaluate_condition, show_history, clear_cache, server_info
)


@pytest.fixture
def temp_storage_dir():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class TestExecuteMcpTool:
    """Test MCP tool execution with subprocess handling."""
    
    @patch('subprocess.Popen')
    def test_execute_mcp_tool_success(self, mock_popen):
        """Test successful MCP tool execution."""
        # Mock successful subprocess
        mock_process = Mock()
        mock_process.communicate.return_value = (
            '{"result": {"content": [{"text": "Success response"}]}}\n',
            ""
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        result = _execute_mcp_tool(
            server_command="python -m test",
            tool_name="test_tool",
            arguments={"input": "test"},
            timeout=30
        )
        
        assert result["success"] is True
        assert result["result"] == "Success response"
        mock_popen.assert_called_once()
    
    @patch('subprocess.Popen')
    def test_execute_mcp_tool_server_error(self, mock_popen):
        """Test MCP tool execution with server error."""
        mock_process = Mock()
        mock_process.communicate.return_value = (
            "Server output",
            "Error message"
        )
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        result = _execute_mcp_tool(
            server_command="python -m test",
            tool_name="test_tool",
            arguments={"input": "test"}
        )
        
        assert result["success"] is False
        assert "Server command failed" in result["error"]
        assert "Error message" in result["error"]
    
    @patch('subprocess.Popen')
    def test_execute_mcp_tool_invalid_response_format(self, mock_popen):
        """Test MCP tool execution with invalid response format."""
        mock_process = Mock()
        mock_process.communicate.return_value = ("", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        result = _execute_mcp_tool(
            server_command="python -m test",
            tool_name="test_tool",
            arguments={"input": "test"}
        )
        
        assert result["success"] is False
        assert "Invalid response format" in result["error"]
    
    @patch('subprocess.Popen')
    def test_execute_mcp_tool_json_parse_error(self, mock_popen):
        """Test MCP tool execution with JSON parse error."""
        mock_process = Mock()
        mock_process.communicate.return_value = (
            "Invalid JSON response\n",
            ""
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        result = _execute_mcp_tool(
            server_command="python -m test",
            tool_name="test_tool",
            arguments={"input": "test"}
        )
        
        assert result["success"] is False
        assert "Failed to parse server response" in result["error"]
    
    @patch('subprocess.Popen')
    def test_execute_mcp_tool_timeout(self, mock_popen):
        """Test MCP tool execution timeout."""
        mock_process = Mock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired("test", 1)
        mock_popen.return_value = mock_process
        
        result = _execute_mcp_tool(
            server_command="python -m test",
            tool_name="test_tool",
            arguments={"input": "test"},
            timeout=1
        )
        
        assert result["success"] is False
        assert "Tool execution timed out" in result["error"]
        mock_process.kill.assert_called_once()
        mock_process.wait.assert_called_once()
    
    @patch('subprocess.Popen')
    def test_execute_mcp_tool_mcp_error_response(self, mock_popen):
        """Test MCP tool execution with MCP error in response."""
        mock_process = Mock()
        mock_process.communicate.return_value = (
            '{"error": {"message": "Tool not found"}}\n',
            ""
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        result = _execute_mcp_tool(
            server_command="python -m test",
            tool_name="test_tool",
            arguments={"input": "test"}
        )
        
        assert result["success"] is False
        assert result["error"] == "Tool not found"
    
    @patch('subprocess.Popen')
    def test_execute_mcp_tool_simple_result(self, mock_popen):
        """Test MCP tool execution with simple result format."""
        mock_process = Mock()
        mock_process.communicate.return_value = (
            '{"result": "Simple string result"}\n',
            ""
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        result = _execute_mcp_tool(
            server_command="python -m test",
            tool_name="test_tool",
            arguments={"input": "test"}
        )
        
        assert result["success"] is True
        assert result["result"] == "Simple string result"
    
    @patch('subprocess.Popen')
    def test_execute_mcp_tool_dict_result(self, mock_popen):
        """Test MCP tool execution with dict result format."""
        mock_process = Mock()
        mock_process.communicate.return_value = (
            '{"result": {"data": "complex", "status": "ok"}}\n',
            ""
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        result = _execute_mcp_tool(
            server_command="python -m test",
            tool_name="test_tool",
            arguments={"input": "test"}
        )
        
        assert result["success"] is True
        assert "{'data': 'complex', 'status': 'ok'}" in result["result"]
    
    @patch('subprocess.Popen')
    def test_execute_mcp_tool_exception(self, mock_popen):
        """Test MCP tool execution with unexpected exception."""
        mock_popen.side_effect = Exception("Unexpected error")
        
        result = _execute_mcp_tool(
            server_command="python -m test",
            tool_name="test_tool",
            arguments={"input": "test"}
        )
        
        assert result["success"] is False
        assert "Execution error: Unexpected error" in result["error"]


class TestVariableSubstitution:
    """Test variable substitution logic."""
    
    def test_substitute_variables_basic(self):
        """Test basic variable substitution."""
        text = "Hello {name}, your score is {score}"
        variables = {"name": "Alice", "score": "95"}
        step_outputs = {}
        
        result = _substitute_variables(text, variables, step_outputs)
        assert result == "Hello Alice, your score is 95"
    
    def test_substitute_variables_step_outputs(self):
        """Test substitution with step outputs."""
        text = "Previous result: {step1}, current input: {input}"
        variables = {"input": "test_data"}
        step_outputs = {"step1": "success"}
        
        result = _substitute_variables(text, variables, step_outputs)
        assert result == "Previous result: success, current input: test_data"
    
    def test_substitute_variables_special_keys(self):
        """Test substitution with special INITIAL_INPUT key."""
        text = "Initial: {INITIAL_INPUT}, step: {step1}"
        variables = {"INITIAL_INPUT": "start_value"}
        step_outputs = {"step1": "result1"}
        
        result = _substitute_variables(text, variables, step_outputs)
        assert result == "Initial: start_value, step: result1"
    
    def test_substitute_variables_missing_variable(self):
        """Test substitution with missing variable."""
        text = "Hello {name}, missing: {missing}"
        variables = {"name": "Alice"}
        step_outputs = {}
        
        result = _substitute_variables(text, variables, step_outputs)
        assert result == "Hello Alice, missing: {missing}"  # Unchanged
    
    def test_substitute_variables_nested(self):
        """Test substitution with nested braces."""
        text = "Config: {config}, data: {{inner: {value}}}"
        variables = {"config": "prod", "value": "123"}
        step_outputs = {}
        
        result = _substitute_variables(text, variables, step_outputs)
        assert result == "Config: prod, data: {{inner: 123}}"
    
    def test_substitute_variables_complex_values(self):
        """Test substitution with complex variable values."""
        text = "Result: {result}, data: {data}"
        variables = {"data": '{"key": "value"}'}
        step_outputs = {"result": "Status: OK\nTime: 123"}
        
        result = _substitute_variables(text, variables, step_outputs)
        assert "Status: OK\nTime: 123" in result
        assert '{"key": "value"}' in result


class TestConditionEvaluation:
    """Test condition evaluation logic."""
    
    def test_evaluate_condition_contains(self):
        """Test condition evaluation with 'contains' operator."""
        variables = {"result": "Operation completed successfully"}
        
        assert _evaluate_condition("{result} contains 'success'", variables) is True
        assert _evaluate_condition("{result} contains 'failed'", variables) is False
    
    def test_evaluate_condition_not_contains(self):
        """Test condition evaluation with 'not contains' operator."""
        variables = {"result": "Operation completed successfully"}
        
        assert _evaluate_condition("{result} not contains 'failed'", variables) is True
        assert _evaluate_condition("{result} not contains 'success'", variables) is False
    
    def test_evaluate_condition_equals(self):
        """Test condition evaluation with equals operator."""
        variables = {"status": "completed", "count": "5"}
        
        assert _evaluate_condition("{status} == 'completed'", variables) is True
        assert _evaluate_condition("{status} == 'failed'", variables) is False
        assert _evaluate_condition("{count} == '5'", variables) is True
    
    def test_evaluate_condition_not_equals(self):
        """Test condition evaluation with not equals operator."""
        variables = {"status": "completed", "error_count": "0"}
        
        assert _evaluate_condition("{status} != 'failed'", variables) is True
        assert _evaluate_condition("{status} != 'completed'", variables) is False
        assert _evaluate_condition("{error_count} != '0'", variables) is False
    
    def test_evaluate_condition_invalid_syntax(self):
        """Test condition evaluation with invalid syntax."""
        variables = {"result": "test"}
        
        # Invalid condition should return False
        assert _evaluate_condition("invalid condition syntax", variables) is False
        assert _evaluate_condition("{result} invalid operator 'test'", variables) is False
    
    def test_evaluate_condition_missing_variable(self):
        """Test condition evaluation with missing variable."""
        variables = {"result": "test"}
        
        # Missing variable should make condition False
        assert _evaluate_condition("{missing} == 'test'", variables) is False
    
    def test_evaluate_condition_empty(self):
        """Test condition evaluation with empty condition."""
        variables = {"result": "test"}
        
        # Empty condition should return True (no restriction)
        assert _evaluate_condition("", variables) is True
        assert _evaluate_condition(None, variables) is True


class TestDiscoverTools:
    """Test tool discovery functionality."""
    
    @patch('subprocess.Popen')
    def test_discover_tools_success(self, mock_popen):
        """Test successful tool discovery."""
        mock_process = Mock()
        mock_process.communicate.return_value = (
            '{"result": [{"name": "tool1", "description": "Test tool 1"}, {"name": "tool2", "description": "Test tool 2"}]}\n',
            ""
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        result = discover_tools("python -m test_server")
        
        assert "Discovered 2 tools" in result
        assert "tool1" in result
        assert "tool2" in result
    
    @patch('subprocess.Popen')
    def test_discover_tools_timeout(self, mock_popen):
        """Test tool discovery timeout."""
        mock_process = Mock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired("test", 5)
        mock_popen.return_value = mock_process
        
        result = discover_tools("python -m test_server", timeout=5)
        
        assert "Discovery timed out" in result
        mock_process.kill.assert_called_once()
    
    @patch('subprocess.Popen')
    def test_discover_tools_server_error(self, mock_popen):
        """Test tool discovery with server error."""
        mock_process = Mock()
        mock_process.communicate.return_value = ("", "Server error message")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        result = discover_tools("python -m test_server")
        
        assert "Failed to start server" in result
    
    @patch('subprocess.Popen')
    def test_discover_tools_invalid_response(self, mock_popen):
        """Test tool discovery with invalid response."""
        mock_process = Mock()
        mock_process.communicate.return_value = ("Invalid JSON", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        result = discover_tools("python -m test_server")
        
        assert "Failed to parse response" in result


class TestAdvancedChainExecution:
    """Test advanced chain execution scenarios."""
    
    def test_load_state_new_directory(self, temp_storage_dir):
        """Test loading state from new directory."""
        registered_tools, defined_chains, execution_history = _load_state(temp_storage_dir)
        
        assert registered_tools == {}
        assert defined_chains == {}
        assert execution_history == []
        assert temp_storage_dir.exists()
    
    def test_load_state_existing_file(self, temp_storage_dir):
        """Test loading state from existing file."""
        # Create state file
        state_file = temp_storage_dir / "state.json"
        state_data = {
            "registered_tools": {"tool1": {"command": "test"}},
            "defined_chains": {"chain1": {"steps": []}},
            "execution_history": [{"id": "test"}]
        }
        state_file.write_text(json.dumps(state_data))
        
        registered_tools, defined_chains, execution_history = _load_state(temp_storage_dir)
        
        assert registered_tools == {"tool1": {"command": "test"}}
        assert defined_chains == {"chain1": {"steps": []}}
        assert execution_history == [{"id": "test"}]
    
    def test_load_state_corrupted_file(self, temp_storage_dir):
        """Test loading state from corrupted file."""
        # Create corrupted state file
        state_file = temp_storage_dir / "state.json"
        state_file.write_text("Invalid JSON")
        
        registered_tools, defined_chains, execution_history = _load_state(temp_storage_dir)
        
        # Should return empty state on corruption
        assert registered_tools == {}
        assert defined_chains == {}
        assert execution_history == []
    
    def test_save_state_success(self, temp_storage_dir):
        """Test successful state saving."""
        registered_tools = {"tool1": {"command": "test"}}
        defined_chains = {"chain1": {"steps": []}}
        execution_history = [{"id": "test"}]
        
        _save_state(temp_storage_dir, registered_tools, defined_chains, execution_history)
        
        state_file = temp_storage_dir / "state.json"
        assert state_file.exists()
        
        with open(state_file) as f:
            saved_state = json.load(f)
        
        assert saved_state["registered_tools"] == registered_tools
        assert saved_state["defined_chains"] == defined_chains
        assert saved_state["execution_history"] == execution_history
    
    @patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool')
    def test_execute_chain_with_conditions(self, mock_execute, temp_storage_dir):
        """Test chain execution with conditional steps."""
        # Mock tool execution
        mock_execute.side_effect = [
            {"success": True, "result": "Operation completed successfully"},
            {"success": True, "result": "Backup created"}
        ]
        
        # Register tools first
        register_tool(
            tool_id="primary_tool",
            server_command="python -m primary",
            tool_name="execute",
            storage_dir=temp_storage_dir
        )
        register_tool(
            tool_id="backup_tool", 
            server_command="python -m backup",
            tool_name="create",
            storage_dir=temp_storage_dir
        )
        
        # Create chain with conditions
        chain_tools(
            chain_id="conditional_chain",
            steps=[
                ToolStep(
                    tool_id="primary_tool",
                    arguments={"action": "process"},
                    output_to="primary_result"
                ),
                ToolStep(
                    tool_id="backup_tool",
                    arguments={"data": "{primary_result}"},
                    condition="{primary_result} contains 'success'"
                )
            ],
            storage_dir=temp_storage_dir
        )
        
        # Execute chain
        result = execute_chain("conditional_chain", storage_dir=temp_storage_dir)
        
        assert "Chain executed successfully" in result
        assert mock_execute.call_count == 2  # Both steps should execute
    
    @patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool')
    def test_execute_chain_condition_false(self, mock_execute, temp_storage_dir):
        """Test chain execution with false condition."""
        # Mock tool execution
        mock_execute.return_value = {"success": True, "result": "Operation failed"}
        
        # Register tools
        register_tool(
            tool_id="primary_tool",
            server_command="python -m primary", 
            tool_name="execute",
            storage_dir=temp_storage_dir
        )
        register_tool(
            tool_id="backup_tool",
            server_command="python -m backup",
            tool_name="create", 
            storage_dir=temp_storage_dir
        )
        
        # Create chain with condition that will be false
        chain_tools(
            chain_id="conditional_chain",
            steps=[
                ToolStep(
                    tool_id="primary_tool",
                    arguments={"action": "process"},
                    output_to="primary_result"
                ),
                ToolStep(
                    tool_id="backup_tool",
                    arguments={"data": "{primary_result}"},
                    condition="{primary_result} contains 'success'"  # Will be false
                )
            ],
            storage_dir=temp_storage_dir
        )
        
        # Execute chain
        result = execute_chain("conditional_chain", storage_dir=temp_storage_dir)
        
        assert "Chain executed successfully" in result
        assert mock_execute.call_count == 1  # Only first step should execute
    
    @patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool')
    def test_execute_chain_tool_failure(self, mock_execute, temp_storage_dir):
        """Test chain execution with tool failure."""
        # Mock tool failure
        mock_execute.return_value = {"success": False, "error": "Tool execution failed"}
        
        # Register tool
        register_tool(
            tool_id="failing_tool",
            server_command="python -m failing",
            tool_name="execute",
            storage_dir=temp_storage_dir
        )
        
        # Create simple chain
        chain_tools(
            chain_id="failing_chain",
            steps=[
                ToolStep(
                    tool_id="failing_tool",
                    arguments={"action": "process"}
                )
            ],
            storage_dir=temp_storage_dir
        )
        
        # Execute chain
        result = execute_chain("failing_chain", storage_dir=temp_storage_dir)
        
        assert "❌ Failed" in result
        assert "Tool execution failed" in result


class TestHistoryAndCacheManagement:
    """Test history and cache management functions."""
    
    def test_show_history_empty(self, temp_storage_dir):
        """Test showing history when empty."""
        result = show_history(storage_dir=temp_storage_dir)
        
        assert "No chain executions found" in result
    
    def test_show_history_with_data(self, temp_storage_dir):
        """Test showing history with execution data."""
        # Create some execution history
        execution_history = [
            {
                "chain_id": "test_chain",
                "timestamp": "2024-01-01T12:00:00",
                "success": True,
                "duration": 5.5
            },
            {
                "chain_id": "another_chain", 
                "timestamp": "2024-01-01T13:00:00",
                "success": False,
                "error": "Failed to execute"
            }
        ]
        
        # Save state with history
        _save_state(temp_storage_dir, {}, {}, execution_history)
        
        result = show_history(storage_dir=temp_storage_dir)
        
        assert "test_chain" in result
        assert "another_chain" in result
        assert "✅" in result  # Success indicator
        assert "❌" in result  # Failure indicator
        assert "5.5s" in result
    
    def test_show_history_with_limit(self, temp_storage_dir):
        """Test showing history with limit."""
        # Create multiple history entries
        execution_history = [
            {"chain_id": f"chain_{i}", "timestamp": f"2024-01-0{i}T12:00:00", "success": True}
            for i in range(1, 6)
        ]
        
        _save_state(temp_storage_dir, {}, {}, execution_history)
        
        result = show_history(limit=2, storage_dir=temp_storage_dir)
        
        # Should only show last 2 entries
        assert result.count("chain_") == 2
        assert "chain_5" in result
        assert "chain_4" in result
        assert "chain_1" not in result
    
    def test_clear_cache_success(self, temp_storage_dir):
        """Test successful cache clearing."""
        # Create some state
        state_file = temp_storage_dir / "state.json"
        state_file.write_text('{"test": "data"}')
        
        result = clear_cache(storage_dir=temp_storage_dir)
        
        assert "Cache cleared successfully" in result
        assert not state_file.exists()
    
    def test_clear_cache_no_files(self, temp_storage_dir):
        """Test cache clearing when no files exist."""
        result = clear_cache(storage_dir=temp_storage_dir)
        
        assert "Cache cleared successfully" in result


class TestServerInfo:
    """Test server info functionality."""
    
    def test_server_info_empty_state(self, temp_storage_dir):
        """Test server info with empty state."""
        result = server_info(storage_dir=temp_storage_dir)
        
        assert "Tool Chainer Server Status" in result
        assert "**Registered Tools:** 0" in result
        assert "**Defined Chains:** 0" in result
        assert "Execution History: 0 entries" in result
    
    def test_server_info_with_data(self, temp_storage_dir):
        """Test server info with existing data."""
        # Create state with data
        registered_tools = {
            "tool1": {"server_command": "python -m tool1", "tool_name": "execute"},
            "tool2": {"server_command": "python -m tool2", "tool_name": "process"}
        }
        defined_chains = {
            "chain1": {"steps": [{"tool_id": "tool1"}]},
            "chain2": {"steps": [{"tool_id": "tool2"}]}
        }
        execution_history = [{"chain_id": "chain1"}, {"chain_id": "chain2"}]
        
        _save_state(temp_storage_dir, registered_tools, defined_chains, execution_history)
        
        result = server_info(storage_dir=temp_storage_dir)
        
        assert "**Registered Tools:** 2" in result
        assert "tool1" in result
        assert "tool2" in result
        assert "**Defined Chains:** 2" in result
        assert "chain1" in result
        assert "chain2" in result
        assert "Execution History: 2 entries" in result


class TestErrorHandling:
    """Test comprehensive error handling."""
    
    def test_register_tool_missing_fields(self, temp_storage_dir):
        """Test registering tool with missing required fields."""
        with pytest.raises(ValueError, match="Tool ID is required"):
            register_tool(
                tool_id="",
                server_command="",
                tool_name="",
                storage_dir=temp_storage_dir
            )
    
    def test_execute_chain_nonexistent_chain(self, temp_storage_dir):
        """Test executing non-existent chain."""
        with pytest.raises(ValueError, match="Chain 'nonexistent_chain' not found"):
            execute_chain("nonexistent_chain", storage_dir=temp_storage_dir)
    
    def test_execute_chain_nonexistent_tool(self, temp_storage_dir):
        """Test executing chain with non-existent tool."""
        # Create chain with non-existent tool
        chain_tools(
            chain_id="invalid_chain",
            steps=[
                ToolStep(
                    tool_id="nonexistent_tool",
                    arguments={"test": "data"}
                )
            ],
            storage_dir=temp_storage_dir
        )
        
        result = execute_chain("invalid_chain", storage_dir=temp_storage_dir)
        
        assert "Tool 'nonexistent_tool' not found" in result
    
    @patch('mcp_handley_lab.tool_chainer.tool._save_state')
    def test_execute_chain_save_error(self, mock_save_state, temp_storage_dir):
        """Test chain execution with save error."""
        # Allow first few saves to succeed, then fail later ones
        call_count = 0
        
        original_save_state = mock_save_state._mock_wraps or mock_save_state._mock_side_effect
        
        def save_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # Allow first two saves (register_tool and chain_tools)
                # Call the real function to actually save state
                storage_path, registered_tools, defined_chains, execution_history = args
                storage_path.mkdir(parents=True, exist_ok=True)
                state = {
                    "registered_tools": registered_tools,
                    "defined_chains": defined_chains,
                    "execution_history": execution_history
                }
                import json
                with open(storage_path / "state.json", "w") as f:
                    json.dump(state, f, indent=2, default=str)
                return None
            else:
                raise Exception("Save failed")
        
        mock_save_state.side_effect = save_side_effect
        
        # Register tool first
        register_tool(
            tool_id="test_tool",
            server_command="python -m test",
            tool_name="execute",
            storage_dir=temp_storage_dir
        )
        
        # This should still complete despite save error
        chain_tools(
            chain_id="test_chain",
            steps=[ToolStep(tool_id="test_tool", arguments={})],
            storage_dir=temp_storage_dir
        )
        
        # The chain should be defined even if save fails
        result = server_info(storage_dir=temp_storage_dir)
        assert "test_chain" in result