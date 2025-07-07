"""Tests for the CLI discovery module."""
import json
from unittest.mock import Mock, patch

import pytest
from mcp_handley_lab.cli.discovery import (
    get_available_tools,
    get_tool_info,
    get_tool_info_from_cache,
)


class TestAvailableTools:
    """Test available tools discovery."""

    def test_get_available_tools(self):
        """Test get_available_tools returns expected structure."""
        tools = get_available_tools()

        assert isinstance(tools, dict)

        # Check for expected core tools
        expected_tools = ["jq", "vim", "arxiv", "gemini", "openai", "code2prompt"]
        for tool in expected_tools:
            assert tool in tools
            assert tools[tool].startswith("mcp-")

        # Verify specific mappings
        assert tools["jq"] == "mcp-jq"
        assert tools["vim"] == "mcp-vim"
        assert tools["arxiv"] == "mcp-arxiv"

    def test_get_available_tools_immutable(self):
        """Test that get_available_tools returns consistent results."""
        tools1 = get_available_tools()
        tools2 = get_available_tools()

        assert tools1 == tools2


class TestCacheSystem:
    """Test the tool schema cache system."""

    @patch("importlib.resources.files")
    def test_get_tool_info_from_cache_success(self, mock_files):
        """Test successful cache loading."""
        # Mock the cache file
        mock_schema_data = {
            "version": "1.0",
            "tools": {
                "jq": {
                    "name": "jq",
                    "functions": {
                        "query": {
                            "name": "query",
                            "description": "Query JSON data",
                            "inputSchema": {
                                "properties": {
                                    "data": {"type": "string"},
                                    "filter": {"type": "string", "default": "."},
                                },
                                "required": ["data"],
                            },
                        }
                    },
                }
            },
        }

        mock_file = Mock()
        mock_file.is_file.return_value = True
        mock_file.read_text.return_value = json.dumps(mock_schema_data)

        mock_files.return_value.__truediv__.return_value = mock_file

        result = get_tool_info_from_cache()

        assert isinstance(result, dict)
        assert "jq" in result
        assert result["jq"]["name"] == "jq"
        assert "query" in result["jq"]["functions"]

    @patch("importlib.resources.files")
    def test_get_tool_info_from_cache_file_not_found(self, mock_files):
        """Test cache loading when file doesn't exist."""
        mock_file = Mock()
        mock_file.is_file.return_value = False
        mock_files.return_value.__truediv__.return_value = mock_file

        result = get_tool_info_from_cache()

        assert result == {}

    @patch("importlib.resources.files")
    def test_get_tool_info_from_cache_invalid_json(self, mock_files):
        """Test cache loading with invalid JSON."""
        mock_file = Mock()
        mock_file.is_file.return_value = True
        mock_file.read_text.return_value = "invalid json"
        mock_files.return_value.__truediv__.return_value = mock_file

        result = get_tool_info_from_cache()

        assert result == {}

    @patch("importlib.resources.files")
    def test_get_tool_info_from_cache_import_error(self, mock_files):
        """Test cache loading with import error."""
        # Simulate import error
        mock_files.side_effect = ImportError("files not available")

        result = get_tool_info_from_cache()

        # Should return empty dict when import fails
        assert result == {}


class TestToolInfo:
    """Test tool information retrieval."""

    @patch("mcp_handley_lab.cli.discovery.get_tool_info_from_cache")
    def test_get_tool_info_cache_hit(self, mock_cache):
        """Test get_tool_info when cache has the tool."""
        mock_cache.return_value = {
            "jq": {"name": "jq", "functions": {"query": {"description": "Query JSON"}}}
        }

        result = get_tool_info("jq", "mcp-jq")

        assert result is not None
        assert result["name"] == "jq"
        assert result["command"] == "mcp-jq"
        assert "query" in result["functions"]

    @patch("mcp_handley_lab.cli.discovery.get_tool_client")
    @patch("mcp_handley_lab.cli.discovery.get_tool_info_from_cache")
    def test_get_tool_info_cache_miss_rpc_success(self, mock_cache, mock_get_client):
        """Test get_tool_info when cache miss but RPC succeeds."""
        mock_cache.return_value = {}

        # Mock RPC client
        mock_client = Mock()
        mock_client.list_tools.return_value = [
            {"name": "query", "description": "Query JSON data"},
            {"name": "validate", "description": "Validate JSON"},
        ]
        mock_get_client.return_value = mock_client

        result = get_tool_info("jq", "mcp-jq")

        assert result is not None
        assert result["name"] == "jq"
        assert result["command"] == "mcp-jq"
        assert "query" in result["functions"]
        assert "validate" in result["functions"]
        assert result["functions"]["query"]["name"] == "query"

    @patch("mcp_handley_lab.cli.discovery.get_tool_client")
    @patch("mcp_handley_lab.cli.discovery.get_tool_info_from_cache")
    def test_get_tool_info_rpc_empty_response(self, mock_cache, mock_get_client):
        """Test get_tool_info when RPC returns empty list."""
        mock_cache.return_value = {}

        mock_client = Mock()
        mock_client.list_tools.return_value = []
        mock_get_client.return_value = mock_client

        result = get_tool_info("jq", "mcp-jq")

        assert result is None

    @patch("mcp_handley_lab.cli.discovery.get_tool_client")
    @patch("mcp_handley_lab.cli.discovery.get_tool_info_from_cache")
    def test_get_tool_info_rpc_exception(self, mock_cache, mock_get_client):
        """Test get_tool_info when RPC raises exception."""
        mock_cache.return_value = {}
        mock_get_client.side_effect = Exception("Connection failed")

        result = get_tool_info("jq", "mcp-jq")

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
