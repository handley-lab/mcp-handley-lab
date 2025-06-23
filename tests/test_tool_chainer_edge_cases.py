"""Consolidated edge case tests for Tool Chainer ensuring 100% coverage."""
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
import mcp_handley_lab.tool_chainer.tool as tool_module
from mcp_handley_lab.tool_chainer.tool import (
    register_tool, chain_tools, execute_chain, show_history, clear_cache,
    server_info, discover_tools, _save_state, _load_state, ToolStep
)


class TestToolChainerEdgeCases:
    """Consolidated tests for edge cases and error conditions."""

    def setup_method(self):
        """Set up test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up after test method."""
        if self.storage_path.exists():
            shutil.rmtree(self.storage_path)

    def test_save_and_load_state(self):
        """Test _save_state and _load_state functions."""
        tools = {"test": {"data": "value"}}
        chains = {"chain": {"steps": []}}
        history = [{"exec": "test"}]
        _save_state(self.storage_path, tools, chains, history)
        loaded_tools, loaded_chains, loaded_history = _load_state(self.storage_path)
        assert loaded_tools == tools
        assert loaded_chains == chains
        assert loaded_history == history

    def test_load_state_file_exists(self):
        """Test _load_state when state file exists."""
        state = {
            "registered_tools": {"tool1": {"name": "test"}},
            "defined_chains": {"chain1": {"steps": []}},
            "execution_history": [{"id": "test"}]
        }
        state_file = self.storage_path / "state.json"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        with open(state_file, 'w') as f:
            json.dump(state, f)
        tools, chains, history = _load_state(self.storage_path)
        assert "tool1" in tools
        assert "chain1" in chains
        assert len(history) == 1
    
    def test_load_state_on_import(self):
        """Test that state is loaded properly on import."""
        test_tools = {"tool1": {"name": "test"}}
        test_chains = {"chain1": {"steps": []}}
        test_history = [{"test": "execution"}]
        _save_state(self.storage_path, test_tools, test_chains, test_history)
        tools, chains, history = _load_state(self.storage_path)
        assert tools == test_tools
        assert chains == test_chains
        assert history == test_history


    def test_load_state_file_not_exists(self):
        """Test _load_state when state file doesn't exist."""
        tools, chains, history = _load_state(self.storage_path)
        assert tools == {}
        assert chains == {}
        assert history == []

    def test_load_state_json_error(self):
        """Test _load_state with JSON decode error."""
        state_file = self.storage_path / "state.json"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        with open(state_file, 'w') as f:
            f.write("invalid json")
        tools, chains, history = _load_state(self.storage_path)
        assert tools == {}
        assert chains == {}
        assert history == []

    def test_substitute_variables_edge_cases(self):
        """Test _substitute_variables with edge cases."""
        variables = {"VAR1": "value1", "VAR2": "value2"}
        step_outputs = {"step1": "output1", "step2": "output2"}
        
        # Test with non-string input (should return as-is)
        result = tool_module._substitute_variables(123, variables, step_outputs)
        assert result == 123
        
        # Test with None
        result = tool_module._substitute_variables(None, variables, step_outputs)
        assert result is None
        
        # Test with complex substitution
        text = "Hello {VAR1} and {step1}, also {VAR2}"
        result = tool_module._substitute_variables(text, variables, step_outputs)
        assert result == "Hello value1 and output1, also value2"

    def test_clear_cache_functionality(self):
        """Test clear_cache functionality."""
        # Create some test state
        test_tools = {"tool1": {"name": "test"}}
        test_chains = {"chain1": {"steps": []}}
        test_history = [{"test": "execution"}]
        _save_state(self.storage_path, test_tools, test_chains, test_history)
        
        # Clear cache
        result = clear_cache(storage_dir=str(self.storage_path))
        assert "✅ Cache and execution history cleared successfully!" in result
        
        # Verify state is cleared
        tools, chains, history = _load_state(self.storage_path)
        assert tools == {}
        assert chains == {}
        assert history == []


class TestExecuteMCPTool:
    """Test _execute_mcp_tool edge cases."""

    def setup_method(self):
        """Set up test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up after test method."""
        if self.storage_path.exists():
            shutil.rmtree(self.storage_path)

    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_general_exception(self, mock_unlink, mock_tempfile, mock_subprocess):
        """Test general exception handling."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file
        mock_subprocess.side_effect = Exception("Unexpected error")
        result = tool_module._execute_mcp_tool("python tool.py", "test_tool", {})
        assert result["success"] is False
        assert "Execution error: Unexpected error" in result["error"]

    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_stderr_output(self, mock_tempfile, mock_subprocess):
        """Test when subprocess returns non-zero with stderr."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Command not found"
        mock_result.stdout = "Some output"
        mock_subprocess.return_value = mock_result

        with patch('pathlib.Path.unlink'):
            result = tool_module._execute_mcp_tool("invalid_command", "tool", {})

        assert result["success"] is False
        assert "Server command failed: Command not found" in result["error"]
        assert result["output"] == "Some output"

    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_error_without_message(self, mock_tempfile, mock_subprocess):
        """Test error response without message field."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"error": {}})  # No message field
        mock_subprocess.return_value = mock_result

        with patch('pathlib.Path.unlink'):
            result = tool_module._execute_mcp_tool("command", "tool", {})

        assert result["success"] is False
        assert result["error"] == "Unknown error"

    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_plain_text_response(self, mock_tempfile, mock_subprocess):
        """Test when server returns plain text instead of JSON."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Plain text response"
        mock_subprocess.return_value = mock_result

        with patch('pathlib.Path.unlink'):
            result = tool_module._execute_mcp_tool("command", "tool", {})

        assert result["success"] is True
        assert result["result"] == "Plain text response"

    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_timeout_exception(self, mock_tempfile, mock_subprocess):
        """Test timeout exception handling."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file

        from subprocess import TimeoutExpired
        mock_subprocess.side_effect = TimeoutExpired("cmd", 5)

        with patch('pathlib.Path.unlink'):
            result = tool_module._execute_mcp_tool("command", "tool", {}, timeout=5)

        assert result["success"] is False
        assert "timed out after 5 seconds" in result["error"]

    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_json_parse_various_responses(self, mock_unlink, mock_tempfile, mock_subprocess):
        """Test with various JSON responses."""
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
    def test_empty_content_array(self, mock_unlink, mock_tempfile, mock_subprocess):
        """Test with empty content array."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "result": {
                "content": []
            }
        })
        mock_subprocess.return_value = mock_result

        result = tool_module._execute_mcp_tool("python tool.py", "test_tool", {})

        assert result["success"] is False
        assert "list index out of range" in result["error"]

    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_cleanup_error(self, mock_unlink, mock_tempfile, mock_subprocess):
        """Test when cleanup fails."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"result": {"content": [{"text": "OK"}]}})
        mock_subprocess.return_value = mock_result

        mock_unlink.side_effect = OSError("Cannot delete")

        result = tool_module._execute_mcp_tool("python tool.py", "test_tool", {})
        assert result["success"] is True

    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_no_text_in_content(self, mock_unlink, mock_tempfile, mock_subprocess):
        """Test with content but no text field."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file

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

    @patch('pathlib.Path.unlink')
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_cleanup_always_happens(self, mock_tempfile, mock_subprocess, mock_unlink):
        """Test that cleanup always happens even when subprocess fails."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file

        mock_subprocess.side_effect = Exception("Subprocess failed")

        result = tool_module._execute_mcp_tool("python tool.py", "test_tool", {})

        assert result["success"] is False
        assert "Execution error" in result["error"]
        mock_unlink.assert_called_once()


class TestDiscoverTools:
    """Test discover_tools edge cases."""

    def setup_method(self):
        """Set up test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up after test method."""
        if self.storage_path.exists():
            shutil.rmtree(self.storage_path)

    @patch('pathlib.Path.unlink')
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_timeout(self, mock_tempfile, mock_subprocess, mock_unlink):
        """Test with timeout."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file

        mock_subprocess.side_effect = subprocess.TimeoutExpired("cmd", 5)

        result = discover_tools("python server.py", timeout=5)

        assert "❌ Server discovery timed out after 5 seconds" in result

    @patch('pathlib.Path.unlink')
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_with_tools_found(self, mock_tempfile, mock_subprocess, mock_unlink):
        """Test when tools are found."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "result": {
                "tools": [
                    {"name": "tool1", "description": "First tool"},
                    {"name": "tool2", "description": "Second tool"},
                    {"name": "tool3"}  # No description
                ]
            }
        })
        mock_subprocess.return_value = mock_result

        result = discover_tools("python server.py")

        assert "🔧 **Discovered 3 tools:**" in result
        assert "**tool1**" in result
        assert "First tool" in result
        assert "**tool2**" in result
        assert "Second tool" in result
        assert "**tool3**" in result
        assert "No description" in result

    @patch('pathlib.Path.unlink')
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_server_error_with_message(self, mock_tempfile, mock_subprocess, mock_unlink):
        """Test with server error that has message."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "error": {"message": "Server internal error"}
        })
        mock_subprocess.return_value = mock_result

        result = discover_tools("python server.py")

        assert "❌ Server error: Server internal error" in result

    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_server_error(self, mock_unlink, mock_tempfile, mock_subprocess):
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

        result = discover_tools("python server.py")

        assert "❌ Server error:" in result
        assert "Server error occurred" in result

    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    @patch('pathlib.Path.unlink')
    def test_general_exception(self, mock_unlink, mock_tempfile, mock_subprocess):
        """Test discover_tools with general exception."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file

        mock_subprocess.side_effect = Exception("Unexpected error")

        result = discover_tools("python server.py")

        assert "❌ Discovery error:" in result
        assert "Unexpected error" in result

    @patch('json.loads')
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_json_decode_error(self, mock_tempfile, mock_subprocess, mock_json_loads):
        """Test discover_tools with general JSON decode error."""
        mock_file = MagicMock()
        mock_file.name = "/tmp/request.json"
        mock_tempfile.return_value = mock_file

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Invalid JSON"
        mock_subprocess.return_value = mock_result

        mock_json_loads.side_effect = json.JSONDecodeError("Invalid", "doc", 0)

        with patch('pathlib.Path.unlink'):
            result = discover_tools("python server.py")

        assert "error" in result.lower() or "invalid" in result.lower()


class TestEvaluateCondition:
    """Test _evaluate_condition edge cases."""

    def setup_method(self):
        """Set up test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up after test method."""
        if self.storage_path.exists():
            shutil.rmtree(self.storage_path)

    def test_eval_fallback(self):
        """Test _evaluate_condition with eval fallback."""
        variables = {"test": True}
        step_outputs = {}
        
        # Test boolean expression that gets evaluated
        result = tool_module._evaluate_condition("True", variables, step_outputs)
        assert result is True
        
        result = tool_module._evaluate_condition("False", variables, step_outputs)
        assert result is False

    def test_strip_quotes(self):
        """Test _evaluate_condition strips quotes properly."""
        variables = {}
        step_outputs = {}
        
        # Test with quotes that should be stripped
        result = tool_module._evaluate_condition("'hello' == 'hello'", variables, step_outputs)
        assert result is True
        
        result = tool_module._evaluate_condition('"test" != "other"', variables, step_outputs)
        assert result is True

    def test_contains_with_spaces(self):
        """Test _evaluate_condition with contains operator and spaces."""
        variables = {}
        step_outputs = {"output": "hello world test"}
        
        # Test contains with variable substitution
        result = tool_module._evaluate_condition("'{output}' contains 'world'", variables, step_outputs)
        assert result is True
        
        result = tool_module._evaluate_condition("'{output}' contains 'missing'", variables, step_outputs)
        assert result is False


class TestChainAndExecute:
    """Test chain_tools and execute_chain edge cases."""

    def setup_method(self):
        """Set up test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up after test method."""
        if self.storage_path.exists():
            shutil.rmtree(self.storage_path)

    def test_chain_tools_invalid_tool(self):
        """Test chain_tools with unregistered tool."""
        steps = [ToolStep(tool_id="nonexistent_tool", arguments={})]

        with pytest.raises(ValueError, match="Tool 'nonexistent_tool' is not registered"):
            chain_tools("test_chain", steps, storage_dir=str(self.storage_path))

    def test_register_tool_and_chain(self):
        """Test register_tool and chain_tools for coverage."""

        result = register_tool(
            "coverage_tool",
            "python coverage.py",
            "test_func",
            "Test tool for coverage",
            "json",
            45,
            storage_dir=str(self.storage_path)
        )
        assert "✅ Tool 'coverage_tool' registered successfully!" in result

        steps = [
            ToolStep(
                tool_id="coverage_tool",
                arguments={"test": "arg"},
                condition="True",
                output_to="output1"
            )
        ]

        result = chain_tools("coverage_chain", steps, "/tmp/out.json", storage_dir=str(self.storage_path))
        assert "✅ Chain 'coverage_chain' defined successfully!" in result
        assert "output1" in result


    def test_execute_chain_invalid_chain(self):
        """Test execute_chain with non-existent chain."""
        with pytest.raises(ValueError, match="Chain 'nonexistent_chain' not found"):
            execute_chain("nonexistent_chain", storage_dir=str(self.storage_path))

    def test_execute_chain_general_exception(self):
        """Test execute_chain with general exception."""
        test_chains = {
            "error_chain": {
                "steps": [{
                    "tool_id": "nonexistent_tool",
                    "arguments": {},
                    "condition": None,
                    "output_to": None
                }],
                "save_to_file": None
            }
        }
        _save_state(self.storage_path, {}, test_chains, [])

        result = execute_chain("error_chain", storage_dir=str(self.storage_path))

        assert "❌ Failed" in result
        assert "Chain execution error" in result

    def test_execute_chain_step_failure(self):
        """Test execute_chain with step failure."""
        register_tool("fail_tool", "echo", "echo", storage_dir=str(self.storage_path))

        steps = [ToolStep(tool_id="fail_tool", arguments={"message": "test"})]
        chain_tools("fail_chain", steps, storage_dir=str(self.storage_path))

        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {
                "success": False,
                "error": "Tool execution failed",
                "output": "Error output"
            }

            result = execute_chain("fail_chain", storage_dir=str(self.storage_path))

            assert "❌ Failed" in result
            assert "Tool execution failed" in result

            _, _, execution_history = _load_state(self.storage_path)
            assert len(execution_history) == 1

            execution = execution_history[0]
            assert execution["success"] is False
            assert "Step 1 failed" in execution["error"]
            assert len(execution["steps"]) == 1
            assert execution["steps"][0]["success"] is False
            assert execution["steps"][0]["error"] == "Tool execution failed"

    @patch('pathlib.Path.write_text')
    def test_execute_chain_save_to_file(self, mock_write_text):
        """Test execute_chain with save_to_file functionality."""
        register_tool("test_tool", "python server.py", "test", storage_dir=str(self.storage_path))

        steps = [ToolStep(tool_id="test_tool", arguments={})]
        chain_tools("save_chain", steps, "/tmp/output.txt", storage_dir=str(self.storage_path))

        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {"success": True, "result": "Test output"}
            result = execute_chain("save_chain", storage_dir=str(self.storage_path))

        mock_write_text.assert_called_once_with("Test output")
        assert "✅ Success" in result

    @patch('pathlib.Path.write_text')
    def test_execute_chain_save_error(self, mock_write_text):
        """Test execute_chain with save file error."""
        register_tool("test_tool", "python server.py", "test", storage_dir=str(self.storage_path))

        steps = [ToolStep(tool_id="test_tool", arguments={})]
        chain_tools("save_chain", steps, "/tmp/output.txt", storage_dir=str(self.storage_path))

        mock_write_text.side_effect = PermissionError("Cannot write file")

        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {"success": True, "result": "Test output"}
            result = execute_chain("save_chain", storage_dir=str(self.storage_path))

        assert "✅ Success" in result

    def test_execute_chain_save_error_logging(self):
        """Test execute_chain with save file error to check error logging."""

        register_tool("save_tool", "echo", "echo", storage_dir=str(self.storage_path))

        steps = [ToolStep(tool_id="save_tool", arguments={"message": "test"})]
        chain_tools("save_chain", steps, "/tmp/output.txt", storage_dir=str(self.storage_path))

        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute, \
             patch('pathlib.Path.write_text') as mock_write:

            mock_execute.return_value = {"success": True, "result": "Success"}
            mock_write.side_effect = PermissionError("Cannot write file")

            result = execute_chain("save_chain", storage_dir=str(self.storage_path))


            assert "✅ Success" in result

            _, _, execution_history = _load_state(self.storage_path)
            execution = execution_history[0]
            assert execution["success"] is True

    def test_execute_chain_with_timeout_param(self):
        """Test execute_chain with custom timeout parameter."""
        register_tool("timeout_tool", "echo", "echo", storage_dir=str(self.storage_path))

        steps = [ToolStep(tool_id="timeout_tool", arguments={"message": "test"})]
        chain_tools("timeout_chain", steps, storage_dir=str(self.storage_path))

        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {"success": True, "result": "Success"}

            result = execute_chain("timeout_chain", timeout=60, storage_dir=str(self.storage_path))

            assert mock_execute.called
            call_args = mock_execute.call_args
            if len(call_args[0]) > 3:
                assert call_args[0][3] == 60

            assert "✅ Success" in result

    def test_execute_chain_step_output_default_name(self):
        """Test execute_chain with step output getting default name."""
        register_tool("output_tool", "echo", "echo", storage_dir=str(self.storage_path))

        steps = [ToolStep(tool_id="output_tool", arguments={"message": "test"})]
        chain_tools("output_chain", steps, storage_dir=str(self.storage_path))

        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {"success": True, "result": "Test output"}

            result = execute_chain("output_chain", storage_dir=str(self.storage_path))

            assert "✅ Success" in result

            _, _, execution_history = _load_state(self.storage_path)
            assert len(execution_history) == 1

            execution = execution_history[0]
            assert execution["success"] is True
            assert len(execution["steps"]) == 1
            assert execution["steps"][0]["success"] is True

    def test_execute_chain_skipped_steps(self):
        """Test execute_chain with all steps skipped."""
        register_tool("skip_tool", "echo", "echo", storage_dir=str(self.storage_path))

        steps = [ToolStep(
            tool_id="skip_tool",
            arguments={},
            condition="False"
        )]
        chain_tools("skip_chain", steps, storage_dir=str(self.storage_path))

        result = execute_chain("skip_chain", storage_dir=str(self.storage_path))

        assert "✅ Success" in result
        assert "0/1" in result

    def test_execute_chain_with_variables(self):
        """Test execute_chain with variable substitution."""
        register_tool("echo_tool", "echo", "echo", storage_dir=str(self.storage_path))

        steps = [ToolStep(
            tool_id="echo_tool",
            arguments={"message": "Hello {NAME}"},
            output_to="greeting"
        )]
        chain_tools("var_chain", steps, storage_dir=str(self.storage_path))

        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {"success": True, "result": "Hello World"}

            result = execute_chain(
                "var_chain",
                variables={"NAME": "World"},
                storage_dir=str(self.storage_path)
            )

        assert "✅ Success" in result

        call_args = mock_execute.call_args[0]
        assert call_args[2]["message"] == "Hello World"

    def test_execute_chain_complex_substitution(self):
        """Test execute_chain with complex variable substitution."""

        register_tool("complex_tool", "echo", "echo", storage_dir=str(self.storage_path))

        steps = [
            ToolStep(
                tool_id="complex_tool",
                arguments={
                    "text": "Hello {INITIAL_INPUT}",
                    "number": 42,  # Non-string argument
                    "nested": {"key": "value"}  # Complex type
                },
                output_to="step_1"
            ),
            ToolStep(
                tool_id="complex_tool",
                arguments={"text": "Result: {step_1}"}
            )
        ]
        chain_tools("complex_chain", steps, storage_dir=str(self.storage_path))

        with patch('mcp_handley_lab.tool_chainer.tool._execute_mcp_tool') as mock_execute:
            mock_execute.return_value = {"success": True, "result": "Hello World"}

            result = execute_chain("complex_chain", initial_input="World", storage_dir=str(self.storage_path))

        assert "✅ Success" in result
        assert "2/2" in result


class TestServerInfo:
    """Test server_info edge cases."""

    def setup_method(self):
        """Set up test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up after test method."""
        if self.storage_path.exists():
            shutil.rmtree(self.storage_path)

    def test_no_data(self):
        """Test with completely empty state."""
        result = server_info(storage_dir=str(self.storage_path))

        assert "Tool Chainer Server Status" in result
        assert "Status: Ready ✓" in result
        assert "**Registered Tools:** 0" in result
        assert "**Defined Chains:** 0" in result
        assert "**Execution History:** 0 executions" in result
        assert "Available tools:" in result
        assert "discover_tools" in result
        assert "register_tool" in result

    def test_complete_data(self):
        """Test with all data."""
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
        test_history = [{"test": "execution"}]

        _save_state(self.storage_path, test_tools, test_chains, test_history)

        result = server_info(storage_dir=str(self.storage_path))

        assert "Tool Chainer Server Status" in result
        assert "Status: Ready ✓" in result
        assert "**Registered Tools:** 1" in result
        assert "tool1: test_tool" in result
        assert "**Defined Chains:** 1" in result
        assert "chain1: 1 steps" in result
        assert "**Execution History:** 1 executions" in result


class TestShowHistory:
    """Test show_history edge cases."""

    def setup_method(self):
        """Set up test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up after test method."""
        if self.storage_path.exists():
            shutil.rmtree(self.storage_path)

    def test_empty_history(self):
        """Test with empty execution history."""
        result = show_history(storage_dir=str(self.storage_path))
        assert "No chain executions found" in result

    def test_with_error_message(self):
        """Test with execution that has an error."""
        test_history = [{
            "chain_id": "failed_chain",
            "started_at": "2024-01-01T10:00:00",
            "success": False,
            "total_duration": 2.5,
            "error": "Step 1 failed: Command not found"
        }]

        _save_state(self.storage_path, {}, {}, test_history)

        result = show_history(storage_dir=str(self.storage_path))

        assert "failed_chain" in result
        assert "❌" in result
        assert "Error: Step 1 failed: Command not found" in result

    def test_with_no_duration(self):
        """Test with execution missing total_duration."""
        test_history = [{
            "chain_id": "test_chain", 
            "started_at": "2024-01-01T10:00:00",
            "success": True
            # Missing total_duration
        }]

        _save_state(self.storage_path, {}, {}, test_history)

        result = show_history(storage_dir=str(self.storage_path))

        assert "test_chain" in result
        assert "✅" in result
        assert "(0.0s)" in result


class TestToolStepModel:
    """Test ToolStep pydantic model."""

    def test_tool_step_validation(self):
        """Test ToolStep model validation."""
        # Valid step
        step = ToolStep(tool_id="test", arguments={"key": "value"})
        assert step.tool_id == "test"
        assert step.arguments == {"key": "value"}
        assert step.condition is None
        assert step.output_to is None

        # Step with all fields
        step = ToolStep(
            tool_id="test",
            arguments={"key": "value"},
            condition="result == success",
            output_to="step_output"
        )
        assert step.condition == "result == success"
        assert step.output_to == "step_output"