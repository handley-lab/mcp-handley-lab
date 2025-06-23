"""Final test to reach exactly 100% coverage for Tool Chainer."""
import pytest
from unittest.mock import patch
import mcp_handley_lab.tool_chainer.tool as tool_module


class TestFinal1Percent:
    """Test to cover the final 1% for line 451."""
    
    @pytest.fixture(autouse=True)
    def reset_globals(self):
        """Reset global state."""
        tool_module.REGISTERED_TOOLS.clear()
        tool_module.DEFINED_CHAINS.clear()
        tool_module.EXECUTION_HISTORY.clear()
        yield
        tool_module.REGISTERED_TOOLS.clear()
        tool_module.DEFINED_CHAINS.clear()
        tool_module.EXECUTION_HISTORY.clear()
    
    def test_show_history_with_error_message(self):
        """Test show_history with execution that has an error - covers line 451."""
        tool_module.EXECUTION_HISTORY.append({
            "chain_id": "failed_chain",
            "started_at": "2024-01-01T10:00:00",
            "success": False,
            "total_duration": 2.5,
            "error": "Step 1 failed: Command not found"  # This triggers line 451
        })
        
        result = tool_module.show_history()
        
        assert "failed_chain" in result
        assert "❌" in result
        assert "Error: Step 1 failed: Command not found" in result  # Line 451 output