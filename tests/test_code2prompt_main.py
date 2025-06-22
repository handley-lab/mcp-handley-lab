"""Test for code2prompt __main__ module."""
from unittest.mock import patch, MagicMock

def test_code2prompt_main():
    """Test the main entry point."""
    mock_mcp = MagicMock()
    
    with patch('mcp_handley_lab.code2prompt.__main__.mcp', mock_mcp):
        from mcp_handley_lab.code2prompt.__main__ import main
        main()
        mock_mcp.run.assert_called_once()

def test_code2prompt_main_module():
    """Test running the module."""
    with patch('mcp_handley_lab.code2prompt.tool.mcp') as mock_mcp:
        import runpy
        with patch('sys.argv', ['mcp_handley_lab.code2prompt']):
            runpy.run_module('mcp_handley_lab.code2prompt.__main__', run_name='__main__')
            mock_mcp.run.assert_called()