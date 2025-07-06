"""Tests for the CLI discovery module."""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from mcp_handley_lab.cli.discovery import (
    get_available_tools,
    get_tool_info_from_cache,
    get_tool_info,
    discover_all_tools,
    get_tool_with_aliases
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
    
    @patch('importlib.resources.files')
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
                                    "filter": {"type": "string", "default": "."}
                                },
                                "required": ["data"]
                            }
                        }
                    }
                }
            }
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
    
    @patch('importlib.resources.files')
    def test_get_tool_info_from_cache_file_not_found(self, mock_files):
        """Test cache loading when file doesn't exist."""
        mock_file = Mock()
        mock_file.is_file.return_value = False
        mock_files.return_value.__truediv__.return_value = mock_file
        
        result = get_tool_info_from_cache()
        
        assert result == {}
    
    @patch('importlib.resources.files')
    def test_get_tool_info_from_cache_invalid_json(self, mock_files):
        """Test cache loading with invalid JSON."""
        mock_file = Mock()
        mock_file.is_file.return_value = True
        mock_file.read_text.return_value = "invalid json"
        mock_files.return_value.__truediv__.return_value = mock_file
        
        result = get_tool_info_from_cache()
        
        assert result == {}
    
    @patch('importlib.resources.read_text')
    @patch('importlib.resources.files')
    def test_get_tool_info_from_cache_python38_fallback(self, mock_files, mock_read_text):
        """Test cache loading with Python 3.8 fallback."""
        # Simulate Python 3.8 by making files() raise ImportError
        mock_files.side_effect = ImportError("files not available")
        
        mock_schema_data = {
            "tools": {
                "jq": {"name": "jq", "functions": {"query": {"name": "query"}}}
            }
        }
        mock_read_text.return_value = json.dumps(mock_schema_data)
        
        result = get_tool_info_from_cache()
        
        assert "jq" in result
        mock_read_text.assert_called_once_with("mcp_handley_lab", "tool_schemas.json")


class TestToolInfo:
    """Test tool information retrieval."""
    
    @patch('mcp_handley_lab.cli.discovery.get_tool_info_from_cache')
    def test_get_tool_info_cache_hit(self, mock_cache):
        """Test get_tool_info when cache has the tool."""
        mock_cache.return_value = {
            "jq": {
                "name": "jq",
                "functions": {
                    "query": {"description": "Query JSON"}
                }
            }
        }
        
        result = get_tool_info("jq", "mcp-jq")
        
        assert result is not None
        assert result["name"] == "jq"
        assert result["command"] == "mcp-jq"
        assert "query" in result["functions"]
    
    @patch('mcp_handley_lab.cli.discovery.get_tool_client')
    @patch('mcp_handley_lab.cli.discovery.get_tool_info_from_cache')
    def test_get_tool_info_cache_miss_rpc_success(self, mock_cache, mock_get_client):
        """Test get_tool_info when cache miss but RPC succeeds."""
        mock_cache.return_value = {}
        
        # Mock RPC client
        mock_client = Mock()
        mock_client.list_tools.return_value = [
            {"name": "query", "description": "Query JSON data"},
            {"name": "validate", "description": "Validate JSON"}
        ]
        mock_get_client.return_value = mock_client
        
        result = get_tool_info("jq", "mcp-jq")
        
        assert result is not None
        assert result["name"] == "jq"
        assert result["command"] == "mcp-jq"
        assert "query" in result["functions"]
        assert "validate" in result["functions"]
        assert result["functions"]["query"]["name"] == "query"
    
    @patch('mcp_handley_lab.cli.discovery.get_tool_client')
    @patch('mcp_handley_lab.cli.discovery.get_tool_info_from_cache')
    def test_get_tool_info_rpc_empty_response(self, mock_cache, mock_get_client):
        """Test get_tool_info when RPC returns empty list."""
        mock_cache.return_value = {}
        
        mock_client = Mock()
        mock_client.list_tools.return_value = []
        mock_get_client.return_value = mock_client
        
        result = get_tool_info("jq", "mcp-jq")
        
        assert result is None
    
    @patch('mcp_handley_lab.cli.discovery.get_tool_client')
    @patch('mcp_handley_lab.cli.discovery.get_tool_info_from_cache')
    def test_get_tool_info_rpc_exception(self, mock_cache, mock_get_client):
        """Test get_tool_info when RPC raises exception."""
        mock_cache.return_value = {}
        mock_get_client.side_effect = Exception("Connection failed")
        
        result = get_tool_info("jq", "mcp-jq")
        
        assert result is None


class TestDiscoverAllTools:
    """Test discovering all tools."""
    
    @patch('mcp_handley_lab.cli.discovery.get_tool_info')
    def test_discover_all_tools(self, mock_get_tool_info):
        """Test discover_all_tools functionality."""
        # Mock tool info for different tools
        def mock_tool_info_side_effect(tool_name, command):
            if tool_name == "jq":
                return {
                    "name": "jq",
                    "command": command,
                    "functions": {"query": {"description": "Query"}}
                }
            elif tool_name == "vim":
                return {
                    "name": "vim", 
                    "command": command,
                    "functions": {"edit": {"description": "Edit"}}
                }
            return None
        
        mock_get_tool_info.side_effect = mock_tool_info_side_effect
        
        result = discover_all_tools()
        
        assert isinstance(result, dict)
        assert "jq" in result
        assert "vim" in result
        
        # Check that display_name is added
        assert result["jq"]["display_name"] == "jq"
        assert result["vim"]["display_name"] == "vim"
    
    @patch('mcp_handley_lab.cli.discovery.get_tool_info')
    def test_discover_all_tools_some_fail(self, mock_get_tool_info):
        """Test discover_all_tools when some tools fail to introspect."""
        def mock_tool_info_side_effect(tool_name, command):
            if tool_name == "jq":
                return {
                    "name": "jq",
                    "command": command,
                    "functions": {"query": {"description": "Query"}}
                }
            return None  # Other tools fail
        
        mock_get_tool_info.side_effect = mock_tool_info_side_effect
        
        result = discover_all_tools()
        
        # Should only contain successfully introspected tools
        assert "jq" in result
        # Failed tools should not be included
        failing_tools = ["vim", "arxiv", "nonexistent"]
        for tool in failing_tools:
            if tool in result:  # Some tools might not be in available_tools
                pytest.fail(f"Failed tool {tool} should not be in result")


class TestAliases:
    """Test tool aliases functionality."""
    
    @patch('mcp_handley_lab.cli.discovery.get_aliases')
    @patch('mcp_handley_lab.cli.discovery.discover_all_tools')
    def test_get_tool_with_aliases(self, mock_discover, mock_get_aliases):
        """Test get_tool_with_aliases functionality."""
        mock_discover.return_value = {
            "jq": {
                "name": "jq",
                "functions": {"query": {"description": "Query"}}
            }
        }
        
        mock_get_aliases.return_value = {
            "json": "jq",  # Alias "json" points to "jq"
            "nonexistent": "missing"  # Alias to non-existent tool
        }
        
        result = get_tool_with_aliases()
        
        # Original tool should be present
        assert "jq" in result
        
        # Valid alias should be added
        assert "json" in result
        assert result["json"]["display_name"] == "json"
        assert result["json"]["is_alias"] is True
        assert result["json"]["target_tool"] == "jq"
        
        # Invalid alias should not be added
        assert "nonexistent" not in result
    
    @patch('mcp_handley_lab.cli.discovery.get_aliases')
    @patch('mcp_handley_lab.cli.discovery.discover_all_tools')
    def test_get_tool_with_aliases_no_aliases(self, mock_discover, mock_get_aliases):
        """Test get_tool_with_aliases with no aliases configured."""
        mock_discover.return_value = {
            "jq": {"name": "jq", "functions": {"query": {}}}
        }
        mock_get_aliases.return_value = {}
        
        result = get_tool_with_aliases()
        
        assert "jq" in result
        assert len(result) == 1
        assert "is_alias" not in result["jq"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])