"""Unit tests to complete agent tool coverage."""
from unittest.mock import patch

import pytest
from mcp_handley_lab.llm.agent.tool import (
    agent_stats,
    get_response,
    list_agents,
    server_info,
)


class TestAgentToolCoverage:
    """Tests to achieve 100% coverage for agent tool."""

    @patch("mcp_handley_lab.llm.agent.tool.memory_manager")
    def test_list_agents_empty(self, mock_memory_manager):
        """Test list_agents when no agents exist (line 31)."""
        mock_memory_manager.list_agents.return_value = []

        result = list_agents()

        assert "No agents found" in result
        assert "create_agent()" in result

    @patch("mcp_handley_lab.llm.agent.tool.memory_manager")
    def test_agent_stats_not_found(self, mock_memory_manager):
        """Test agent_stats with non-existent agent (line 55)."""
        mock_memory_manager.get_agent.return_value = None

        with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
            agent_stats("nonexistent")

    @patch("mcp_handley_lab.llm.agent.tool.memory_manager")
    def test_agent_stats_long_message_truncation(self, mock_memory_manager):
        """Test message truncation in agent_stats (line 79)."""

        class MockMessage:
            def __init__(self, role, content):
                self.role = role
                self.content = content

        class MockAgent:
            def __init__(self):
                # Create a message longer than 100 characters
                long_content = "x" * 150  # 150 chars
                self.messages = [MockMessage("user", long_content)]

            def get_stats(self):
                return {
                    "name": "test_agent",
                    "created_at": "2024-01-01T00:00:00",
                    "message_count": 1,
                    "total_tokens": 50,
                    "total_cost": 0.005,
                    "personality": None,
                }

        mock_agent = MockAgent()
        mock_memory_manager.get_agent.return_value = mock_agent

        result = agent_stats("test_agent")

        # Should contain truncated message (97 chars + "...")
        assert "x" * 97 + "..." in result

    @patch("mcp_handley_lab.llm.agent.tool.memory_manager")
    def test_get_response_delegation(self, mock_memory_manager):
        """Test get_response delegates to memory_manager (line 126)."""
        mock_memory_manager.get_response.return_value = "Test response"

        result = get_response("test_agent", 0)

        mock_memory_manager.get_response.assert_called_once_with("test_agent", 0)
        assert result == "Test response"

    @patch("mcp_handley_lab.llm.agent.tool.memory_manager")
    def test_server_info_formatting(self, mock_memory_manager):
        """Test server_info returns formatted status (lines 132-134)."""
        mock_memory_manager.list_agents.return_value = []

        result = server_info()

        assert "Agent Tool Server Status" in result
        assert "Total Agents: 0" in result
        assert "Available tools:" in result
        assert "create_agent" in result
