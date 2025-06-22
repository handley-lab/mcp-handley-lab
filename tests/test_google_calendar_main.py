"""Tests for Google Calendar main module."""
import sys
import runpy
from unittest.mock import patch


def test_google_calendar_main_module():
    """Test that the Google Calendar main module can be imported and run."""
    # Test importing the main module
    import mcp_handley_lab.google_calendar.__main__ as main_module
    
    # Test that main function exists
    assert hasattr(main_module, 'main')
    assert callable(main_module.main)
    
    # Test running main with mocked mcp
    with patch('mcp_handley_lab.google_calendar.__main__.mcp') as mock_mcp:
        result = main_module.main()
        
        mock_mcp.run.assert_called_once()


def test_google_calendar_main_script_entry():
    """Test running the module as a script."""
    with patch('mcp_handley_lab.google_calendar.tool.mcp') as mock_mcp:
        import runpy
        with patch('sys.argv', ['mcp_handley_lab.google_calendar']):
            runpy.run_module('mcp_handley_lab.google_calendar.__main__', run_name='__main__')
            mock_mcp.run.assert_called()