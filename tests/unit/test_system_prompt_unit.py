"""Simplified unit tests for system prompt functionality."""
import tempfile
from unittest.mock import Mock, patch

from mcp_handley_lab.llm.memory import MemoryManager


class TestSystemPromptMemoryOperations:
    """Test system prompt operations in memory management."""

    def test_agent_creation_with_system_prompt(self):
        """Test that agents are created with system prompts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            # Create agent with system prompt
            agent = manager.create_agent("test_agent", "You are helpful")

            assert agent.system_prompt == "You are helpful"
            assert manager.get_agent("test_agent").system_prompt == "You are helpful"

    def test_agent_creation_without_system_prompt(self):
        """Test that agents can be created without system prompts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            # Create agent without system prompt
            agent = manager.create_agent("test_agent")

            assert agent.system_prompt is None
            assert manager.get_agent("test_agent").system_prompt is None

    def test_system_prompt_update_and_persistence(self):
        """Test that system prompt updates are persisted."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            # Create agent with initial system prompt
            agent = manager.create_agent("test_agent", "Original prompt")
            assert agent.system_prompt == "Original prompt"

            # Update system prompt
            agent.system_prompt = "Updated prompt"
            manager._save_agent(agent)

            # Verify update persisted
            updated_agent = manager.get_agent("test_agent")
            assert updated_agent.system_prompt == "Updated prompt"

    def test_system_prompt_file_persistence(self):
        """Test that system prompts are saved to and loaded from disk."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create first manager and agent
            manager1 = MemoryManager(temp_dir)
            manager1.create_agent("persistent_agent", "Persistent system prompt")

            # Verify file contains system prompt
            agent_file = manager1.agents_dir / "persistent_agent.json"
            assert agent_file.exists()

            import json

            agent_data = json.loads(agent_file.read_text())
            assert agent_data["system_prompt"] == "Persistent system prompt"

            # Create second manager (simulates restart)
            manager2 = MemoryManager(temp_dir)

            # Verify agent and system prompt were loaded
            loaded_agent = manager2.get_agent("persistent_agent")
            assert loaded_agent is not None
            assert loaded_agent.system_prompt == "Persistent system prompt"

    def test_system_prompt_stats(self):
        """Test that system prompts appear in agent statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            # Create agent with system prompt
            agent = manager.create_agent("test_agent", "Test system prompt")
            agent.add_message("user", "Hello", tokens=5, cost=0.001)

            stats = agent.get_stats()
            assert stats["system_prompt"] == "Test system prompt"
            assert stats["name"] == "test_agent"
            assert stats["message_count"] == 1

    def test_empty_system_prompt(self):
        """Test handling of empty system prompts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            # Create agent with empty system prompt
            agent = manager.create_agent("test_agent", "")
            assert agent.system_prompt == ""

            # Verify stats show empty prompt
            stats = agent.get_stats()
            assert stats["system_prompt"] == ""

    def test_none_system_prompt(self):
        """Test handling of None system prompts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            # Create agent with None system prompt
            agent = manager.create_agent("test_agent", None)
            assert agent.system_prompt is None

            # Verify stats show None prompt
            stats = agent.get_stats()
            assert stats["system_prompt"] is None


class TestSystemPromptSharedLogic:
    """Test system prompt handling in shared request processing."""

    @patch("mcp_handley_lab.llm.shared.calculate_cost", return_value=0.001)
    @patch("mcp_handley_lab.llm.shared.handle_agent_memory")
    def test_system_prompt_extracted_from_kwargs(
        self, mock_handle_memory, mock_calculate_cost
    ):
        """Test that system_prompt is extracted from kwargs and passed to generation function."""
        from mcp_handley_lab.llm.shared import process_llm_request

        mock_generation_func = Mock(
            return_value={
                "text": "Test response",
                "input_tokens": 10,
                "output_tokens": 5,
            }
        )

        mock_mcp = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_memory = MemoryManager(temp_dir)

            with patch("mcp_handley_lab.llm.shared.memory_manager", temp_memory), patch(
                "mcp_handley_lab.llm.shared.get_session_id",
                return_value="session_123",
            ):
                process_llm_request(
                    prompt="Test prompt",
                    output_file="-",
                    agent_name="test_agent",
                    model="gemini-2.5-flash",  # Use real model to avoid pricing issues
                    provider="gemini",  # Use real provider
                    generation_func=mock_generation_func,
                    mcp_instance=mock_mcp,
                    system_prompt="You are helpful",
                )

                # Verify generation function was called with system_instruction
                mock_generation_func.assert_called_once()
                call_kwargs = mock_generation_func.call_args[1]
                assert call_kwargs["system_instruction"] == "You are helpful"

    @patch("mcp_handley_lab.llm.shared.calculate_cost", return_value=0.001)
    @patch("mcp_handley_lab.llm.shared.handle_agent_memory")
    def test_system_prompt_creates_new_agent(
        self, mock_handle_memory, mock_calculate_cost
    ):
        """Test that new agents are created with provided system prompt."""
        from mcp_handley_lab.llm.shared import process_llm_request

        mock_generation_func = Mock(
            return_value={
                "text": "Test response",
                "input_tokens": 10,
                "output_tokens": 5,
            }
        )

        mock_mcp = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_memory = MemoryManager(temp_dir)

            with patch("mcp_handley_lab.llm.shared.memory_manager", temp_memory), patch(
                "mcp_handley_lab.llm.shared.get_session_id",
                return_value="session_123",
            ):
                process_llm_request(
                    prompt="Test prompt",
                    output_file="-",
                    agent_name="new_agent",
                    model="gemini-2.5-flash",
                    provider="gemini",
                    generation_func=mock_generation_func,
                    mcp_instance=mock_mcp,
                    system_prompt="You are a helpful assistant",
                )

                # Verify agent was created with system prompt
                agent = temp_memory.get_agent("new_agent")
                assert agent is not None
                assert agent.system_prompt == "You are a helpful assistant"

    @patch("mcp_handley_lab.llm.shared.calculate_cost", return_value=0.001)
    @patch("mcp_handley_lab.llm.shared.handle_agent_memory")
    def test_system_prompt_updates_existing_agent(
        self, mock_handle_memory, mock_calculate_cost
    ):
        """Test that existing agent's system prompt is updated."""
        from mcp_handley_lab.llm.shared import process_llm_request

        mock_generation_func = Mock(
            return_value={
                "text": "Test response",
                "input_tokens": 10,
                "output_tokens": 5,
            }
        )

        mock_mcp = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_memory = MemoryManager(temp_dir)

            # Create agent with initial system prompt
            agent = temp_memory.create_agent("existing_agent", "Original prompt")
            assert agent.system_prompt == "Original prompt"

            with patch("mcp_handley_lab.llm.shared.memory_manager", temp_memory), patch(
                "mcp_handley_lab.llm.shared.get_session_id",
                return_value="session_123",
            ):
                process_llm_request(
                    prompt="Test prompt",
                    output_file="-",
                    agent_name="existing_agent",
                    model="gemini-2.5-flash",
                    provider="gemini",
                    generation_func=mock_generation_func,
                    mcp_instance=mock_mcp,
                    system_prompt="Updated prompt",
                )

                # Verify agent's system prompt was updated
                updated_agent = temp_memory.get_agent("existing_agent")
                assert updated_agent.system_prompt == "Updated prompt"
