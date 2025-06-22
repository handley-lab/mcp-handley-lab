"""Test for Gemini LLM __main__ module."""
from unittest.mock import patch, MagicMock


def test_gemini_main():
    """Test the main entry point."""
    with patch('mcp_handley_lab.llm.gemini.tool.mcp') as mock_mcp:
        from mcp_handley_lab.llm.gemini.__main__ import main
        main()
        mock_mcp.run.assert_called_once()


def test_gemini_main_module():
    """Test running the module."""
    with patch('mcp_handley_lab.llm.gemini.tool.mcp') as mock_mcp:
        import runpy
        with patch('sys.argv', ['mcp_handley_lab.llm.gemini']):
            runpy.run_module('mcp_handley_lab.llm.gemini.__main__', run_name='__main__')
            mock_mcp.run.assert_called()