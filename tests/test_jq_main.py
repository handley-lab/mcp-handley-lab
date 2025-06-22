"""Test for jq __main__ module."""
from unittest.mock import patch, MagicMock

def test_jq_main():
    """Test the main entry point."""
    mock_mcp = MagicMock()
    
    with patch('mcp_framework.jq.__main__.mcp', mock_mcp):
        from mcp_framework.jq.__main__ import main
        main()
        mock_mcp.run.assert_called_once()

def test_jq_main_module():
    """Test running the module."""
    with patch('mcp_framework.jq.tool.mcp') as mock_mcp:
        import runpy
        with patch('sys.argv', ['mcp_framework.jq']):
            runpy.run_module('mcp_framework.jq.__main__', run_name='__main__')
            mock_mcp.run.assert_called()