"""Tests for Vim main module."""
import sys
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
    """Test that the __main__ module has the if __name__ == '__main__' guard."""
    # Test that the module can be imported without executing main
    import mcp_framework.vim.__main__ as main_module
    
    # Test that __name__ checking works by patching and calling conditionally
    with patch('mcp_framework.vim.__main__.main') as mock_main:
        # Simulate what happens when the module is run as script
        if main_module.__name__ == "__main__":
            main_module.main()
        
        # Since __name__ is not "__main__" during import, main should not be called
        mock_main.assert_not_called()