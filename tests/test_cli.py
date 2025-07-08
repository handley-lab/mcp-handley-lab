"""Tests for the MCP CLI module."""
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner
from mcp_handley_lab.cli.discovery import (
    get_available_tools,
    get_tool_info,
)
from mcp_handley_lab.cli.main import cli
from mcp_handley_lab.cli.rpc_client import MCPToolClient


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_cli_help(self):
        """Test global CLI help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "mcp-cli - Unified command-line interface for MCP tools" in result.output
        assert "--list-tools" in result.output
        assert "arxiv --help" in result.output

    def test_cli_no_args(self):
        """Test CLI with no arguments shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code == 0
        assert "command-line interface for MCP tools" in result.output

    def test_list_tools(self):
        """Test --list-tools functionality."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--list-tools"])

        assert result.exit_code == 0
        assert "Available tools:" in result.output
        assert "jq" in result.output
        assert "vim" in result.output
        assert "Total:" in result.output

    def test_config_options(self):
        """Test configuration-related options."""
        runner = CliRunner()

        # Test --config
        result = runner.invoke(cli, ["--config"])
        assert result.exit_code == 0
        assert "Configuration file:" in result.output

        # Test --show-completion
        result = runner.invoke(cli, ["--show-completion"])
        assert result.exit_code == 0
        assert "completion" in result.output.lower()


class TestToolSpecificHelp:
    """Test tool-specific help functionality."""

    @patch("mcp_handley_lab.cli.main.get_tool_info")
    def test_tool_help(self, mock_get_tool_info):
        """Test tool-specific help (mcp-cli jq --help)."""
        # Mock tool info
        mock_get_tool_info.return_value = {
            "name": "jq",
            "command": "mcp-jq",
            "functions": {
                "query": {
                    "name": "query",
                    "description": "Query JSON data",
                    "inputSchema": {
                        "properties": {
                            "data": {"type": "string", "description": "JSON data"},
                            "filter": {"type": "string", "default": "."},
                        },
                        "required": ["data"],
                    },
                },
                "validate": {
                    "name": "validate",
                    "description": "Validate JSON syntax",
                    "inputSchema": {"properties": {}, "required": []},
                },
            },
        }

        runner = CliRunner()
        result = runner.invoke(cli, ["jq", "--help"])

        assert result.exit_code == 0
        assert "jq" in result.output
        assert "FUNCTIONS" in result.output
        assert "query" in result.output
        assert "validate" in result.output
        assert "EXAMPLES" in result.output


class TestToolExecution:
    """Test tool execution functionality."""

    @patch("mcp_handley_lab.cli.main.get_tool_client")
    @patch("mcp_handley_lab.cli.main.get_tool_info")
    def test_tool_execution_with_named_params(
        self, mock_get_tool_info, mock_get_tool_client
    ):
        """Test tool execution with named parameters."""
        # Mock tool info
        mock_get_tool_info.return_value = {
            "name": "jq",
            "command": "mcp-jq",
            "functions": {
                "query": {
                    "inputSchema": {
                        "properties": {
                            "data": {"type": "string"},
                            "filter": {"type": "string", "default": "."},
                        },
                        "required": ["data"],
                    }
                }
            },
        }

        # Mock RPC client
        mock_client = Mock()
        mock_client.call_tool.return_value = {
            "jsonrpc": "2.0",
            "result": {"content": [{"type": "text", "text": '"value"'}]},
        }
        mock_get_tool_client.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(
            cli, ["jq", "query", 'data={"test":"value"}', "filter=.test"]
        )

        assert result.exit_code == 0
        # The output now includes the full JSON structure with escaped quotes
        assert '\\"value\\"' in result.output

        # Verify the client was called with correct parameters
        mock_client.call_tool.assert_called_once_with(
            "query", {"data": '{"test":"value"}', "filter": ".test"}
        )

    @patch("mcp_handley_lab.cli.main.get_tool_client")
    @patch("mcp_handley_lab.cli.main.get_tool_info")
    def test_tool_execution_with_positional_params(
        self, mock_get_tool_info, mock_get_tool_client
    ):
        """Test tool execution with positional parameters."""
        # Mock tool info
        mock_get_tool_info.return_value = {
            "name": "jq",
            "command": "mcp-jq",
            "functions": {
                "query": {
                    "inputSchema": {
                        "properties": {
                            "data": {"type": "string"},
                            "filter": {"type": "string", "default": "."},
                        },
                        "required": ["data"],
                    }
                }
            },
        }

        # Mock RPC client
        mock_client = Mock()
        mock_client.call_tool.return_value = {
            "jsonrpc": "2.0",
            "result": {"content": [{"type": "text", "text": '"value"'}]},
        }
        mock_get_tool_client.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["jq", "query", '{"test":"value"}', ".test"])

        assert result.exit_code == 0
        # The output now includes the full JSON structure with escaped quotes
        assert '\\"value\\"' in result.output

        # Verify the client was called with positional parameters mapped correctly
        mock_client.call_tool.assert_called_once_with(
            "query", {"data": '{"test":"value"}', "filter": ".test"}
        )

    @patch("mcp_handley_lab.cli.main.get_tool_client")
    @patch("mcp_handley_lab.cli.main.get_tool_info")
    def test_tool_execution_json_output(self, mock_get_tool_info, mock_get_tool_client):
        """Test tool execution with JSON output format."""
        mock_get_tool_info.return_value = {
            "name": "jq",
            "command": "mcp-jq",
            "functions": {
                "query": {
                    "inputSchema": {
                        "properties": {"data": {"type": "string"}},
                        "required": ["data"],
                    }
                }
            },
        }

        mock_client = Mock()
        mock_client.call_tool.return_value = {
            "jsonrpc": "2.0",
            "result": {"content": [{"type": "text", "text": '"value"'}]},
        }
        mock_get_tool_client.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(
            cli, ["jq", "query", 'data={"test":"value"}', "--json-output"]
        )

        assert result.exit_code == 0
        # Should output the full JSON result
        parsed_output = json.loads(result.output.strip())
        assert "content" in parsed_output

    def test_tool_execution_with_params_from_json(self):
        """Test tool execution with parameters from JSON file."""
        # Create temporary JSON file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"data": '{"test":"value"}', "filter": ".test"}, f)
            json_file = f.name

        try:
            with patch(
                "mcp_handley_lab.cli.main.get_tool_info"
            ) as mock_get_tool_info, patch(
                "mcp_handley_lab.cli.main.get_tool_client"
            ) as mock_get_tool_client:
                mock_get_tool_info.return_value = {
                    "name": "jq",
                    "command": "mcp-jq",
                    "functions": {
                        "query": {
                            "inputSchema": {
                                "properties": {
                                    "data": {"type": "string"},
                                    "filter": {"type": "string"},
                                },
                                "required": ["data"],
                            }
                        }
                    },
                }

                mock_client = Mock()
                mock_client.call_tool.return_value = {
                    "jsonrpc": "2.0",
                    "result": {"content": [{"type": "text", "text": '"value"'}]},
                }
                mock_get_tool_client.return_value = mock_client

                runner = CliRunner()
                result = runner.invoke(
                    cli, ["jq", "query", "--params-from-json", json_file]
                )

                assert result.exit_code == 0
                mock_client.call_tool.assert_called_once_with(
                    "query", {"data": '{"test":"value"}', "filter": ".test"}
                )
        finally:
            Path(json_file).unlink()


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_nonexistent_tool(self):
        """Test handling of nonexistent tool."""
        runner = CliRunner()
        result = runner.invoke(cli, ["nonexistent", "function"])

        assert result.exit_code == 1
        assert "Tool 'nonexistent' not found" in result.output

    @patch("mcp_handley_lab.cli.main.get_tool_info")
    def test_nonexistent_function(self, mock_get_tool_info):
        """Test handling of nonexistent function."""
        mock_get_tool_info.return_value = {
            "name": "jq",
            "functions": {"query": {"description": "Query"}},
        }

        runner = CliRunner()
        result = runner.invoke(cli, ["jq", "nonexistent"])

        assert result.exit_code == 1
        assert "Function 'nonexistent' not found in jq" in result.output

    @patch("mcp_handley_lab.cli.main.get_tool_client")
    @patch("mcp_handley_lab.cli.main.get_tool_info")
    def test_tool_execution_error(self, mock_get_tool_info, mock_get_tool_client):
        """Test handling of tool execution errors."""
        mock_get_tool_info.return_value = {
            "name": "jq",
            "command": "mcp-jq",
            "functions": {
                "query": {
                    "inputSchema": {
                        "properties": {"data": {"type": "string"}},
                        "required": ["data"],
                    }
                }
            },
        }

        # Mock RPC error response
        mock_client = Mock()
        mock_client.call_tool.return_value = {
            "jsonrpc": "2.0",
            "error": {"message": "Invalid JSON", "code": -1},
        }
        mock_get_tool_client.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["jq", "query", "data=invalid"])

        assert result.exit_code == 1
        assert "Error: Invalid JSON" in result.output

    def test_tool_without_function(self):
        """Test tool name without function name."""
        runner = CliRunner()
        result = runner.invoke(cli, ["jq"])

        assert result.exit_code == 1
        assert "Usage: mcp-cli jq <function>" in result.output
        assert "Use 'mcp-cli jq --help'" in result.output


class TestDiscovery:
    """Test tool discovery functionality."""

    def test_get_available_tools(self):
        """Test get_available_tools returns expected tools."""
        tools = get_available_tools()

        assert isinstance(tools, dict)
        assert "jq" in tools
        assert "vim" in tools
        assert "arxiv" in tools
        assert tools["jq"] == "mcp-jq"

    @patch("mcp_handley_lab.cli.discovery.get_tool_info_from_cache")
    def test_get_tool_info_cache_hit(self, mock_cache):
        """Test get_tool_info when cache hit."""
        mock_cache.return_value = {
            "jq": {"name": "jq", "functions": {"query": {"description": "Query"}}}
        }

        result = get_tool_info("jq", "mcp-jq")

        assert result is not None
        assert result["name"] == "jq"
        assert result["command"] == "mcp-jq"
        assert "query" in result["functions"]

    @patch("mcp_handley_lab.cli.discovery.get_tool_client")
    @patch("mcp_handley_lab.cli.discovery.get_tool_info_from_cache")
    def test_get_tool_info_cache_miss_rpc_success(self, mock_cache, mock_get_client):
        """Test get_tool_info when cache miss but RPC success."""
        mock_cache.return_value = {}

        mock_client = Mock()
        mock_client.list_tools.return_value = [
            {"name": "query", "description": "Query JSON"}
        ]
        mock_get_client.return_value = mock_client

        result = get_tool_info("jq", "mcp-jq")

        assert result is not None
        assert result["name"] == "jq"
        assert result["command"] == "mcp-jq"
        assert "query" in result["functions"]

    @patch("mcp_handley_lab.cli.discovery.get_tool_client")
    @patch("mcp_handley_lab.cli.discovery.get_tool_info_from_cache")
    def test_get_tool_info_complete_failure(self, mock_cache, mock_get_client):
        """Test get_tool_info when both cache and RPC fail."""
        mock_cache.return_value = {}
        mock_get_client.side_effect = Exception("RPC failed")

        result = get_tool_info("jq", "mcp-jq")

        assert result is None


class TestRPCClient:
    """Test RPC client functionality."""

    def test_mcp_tool_client_init(self):
        """Test MCPToolClient initialization."""
        client = MCPToolClient("test-tool", "mcp-test")

        assert client.tool_name == "test-tool"
        assert client.command == "mcp-test"
        assert client.process is None

    @patch("subprocess.Popen")
    def test_client_start_process(self, mock_popen):
        """Test starting the MCP process."""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.stdin.write = Mock()
        mock_process.stdin.flush = Mock()
        mock_process.stdout.readline.return_value = (
            '{"jsonrpc": "2.0", "id": 1, "result": {}}'
        )
        mock_popen.return_value = mock_process

        client = MCPToolClient("test", "mcp-test")
        result = client.start_tool_server()

        assert result is True
        assert client.process == mock_process
        mock_popen.assert_called_once()

    def test_client_cleanup(self):
        """Test client cleanup."""
        client = MCPToolClient("test", "mcp-test")
        mock_process = Mock()
        client.process = mock_process

        client.cleanup()

        mock_process.terminate.assert_called_once()
        assert client.process is None


if __name__ == "__main__":
    pytest.main([__file__])
