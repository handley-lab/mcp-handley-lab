"""Tests for __main__.py entry point."""
import pytest
import sys
from unittest.mock import patch, Mock
from pathlib import Path

from mcp_handley_lab.__main__ import get_available_tools, show_help, main


def test_get_available_tools():
    """Test discovery of available tools."""
    tools = get_available_tools()
    
    # Should find at least some of our known tools
    assert "jq" in tools
    assert "vim" in tools
    assert "llm.gemini" in tools
    assert "llm.openai" in tools
    assert "tool_chainer" in tools
    
    # Should be sorted
    assert tools == sorted(tools)


@patch('builtins.print')
def test_show_help(mock_print):
    """Test help message display."""
    show_help()
    
    # Check that print was called with expected content
    calls = [str(call) for call in mock_print.call_args_list]
    all_output = ' '.join(calls)
    
    assert "Usage: python -m mcp_handley_lab" in all_output
    assert "Available tools:" in all_output
    assert "Examples:" in all_output


@patch('builtins.print')
@patch('sys.exit')
def test_main_no_args(mock_exit, mock_print):
    """Test main with no arguments shows help."""
    with patch('sys.argv', ['mcp_handley_lab']):
        main()
    
    mock_exit.assert_called_once_with(0)
    # Verify help was shown
    calls = [str(call) for call in mock_print.call_args_list]
    all_output = ' '.join(calls)
    assert "Usage: python -m mcp_handley_lab" in all_output


@patch('builtins.print')
@patch('sys.exit')
def test_main_help_flag(mock_exit, mock_print):
    """Test main with --help flag."""
    with patch('sys.argv', ['mcp_handley_lab', '--help']):
        main()
    
    mock_exit.assert_called_once_with(0)


@patch('importlib.import_module')
def test_main_tool_success(mock_import):
    """Test successful tool execution."""
    # Mock the tool module with MCP instance
    mock_module = Mock()
    mock_mcp = Mock()
    mock_module.mcp = mock_mcp
    mock_import.return_value = mock_module
    
    with patch('sys.argv', ['mcp_handley_lab', 'jq']):
        main()
    
    mock_import.assert_called_with("mcp_handley_lab.jq.tool")
    mock_mcp.run.assert_called_once()


@patch('builtins.print')
@patch('sys.exit')
def test_main_tool_not_found(mock_exit, mock_print):
    """Test main with non-existent tool."""
    with patch('sys.argv', ['mcp_handley_lab', 'nonexistent']):
        main()
    
    mock_exit.assert_called_once_with(1)
    # Check error message was printed
    calls = [str(call) for call in mock_print.call_args_list]
    all_output = ' '.join(calls)
    assert "Tool 'nonexistent' not found" in all_output


@patch('importlib.import_module')
@patch('builtins.print')
@patch('sys.exit')
def test_main_tool_no_mcp(mock_exit, mock_print, mock_import):
    """Test tool without MCP instance."""
    # Mock module without mcp attribute
    mock_module = Mock()
    del mock_module.mcp  # Ensure no mcp attribute
    mock_import.return_value = mock_module
    
    with patch('sys.argv', ['mcp_handley_lab', 'jq']):
        main()
    
    mock_exit.assert_called_once_with(1)
    calls = [str(call) for call in mock_print.call_args_list]
    all_output = ' '.join(calls)
    assert "does not have an MCP server instance" in all_output


@patch('importlib.import_module')
@patch('builtins.print')
@patch('sys.exit')
def test_main_tool_exception(mock_exit, mock_print, mock_import):
    """Test tool that raises an exception."""
    # Mock tool that raises exception during run
    mock_module = Mock()
    mock_mcp = Mock()
    mock_mcp.run.side_effect = RuntimeError("Test error")
    mock_module.mcp = mock_mcp
    mock_import.return_value = mock_module
    
    with patch('sys.argv', ['mcp_handley_lab', 'jq']):
        main()
    
    mock_exit.assert_called_once_with(1)
    calls = [str(call) for call in mock_print.call_args_list]
    all_output = ' '.join(calls)
    assert "Error running tool 'jq'" in all_output
    assert "Test error" in all_output