"""Tests for Vim main module."""
import sys
import runpy
from unittest.mock import patch


def test_vim_main_module():
    """Test that the Vim main module can be imported and run."""
    # Test importing the main module
    import mcp_framework.vim.__main__ as main_module
    
    # Test that main function exists
    assert hasattr(main_module, 'main')
    assert callable(main_module.main)
    
    # Test running main with mocked mcp
    with patch('mcp_framework.vim.__main__.mcp') as mock_mcp:
        result = main_module.main()
        
        mock_mcp.run.assert_called_once()


def test_vim_main_script_entry():
    """Test running the module as a script."""
    with patch('mcp_framework.vim.tool.mcp') as mock_mcp:
        import runpy
        with patch('sys.argv', ['mcp_framework.vim']):
            runpy.run_module('mcp_framework.vim.__main__', run_name='__main__')
            mock_mcp.run.assert_called()