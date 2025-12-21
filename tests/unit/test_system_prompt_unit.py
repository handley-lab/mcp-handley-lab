"""Simplified unit tests for system prompt functionality."""

import json
from unittest.mock import Mock, patch

from mcp_handley_lab.llm.memory import GlobalMemoryManager


class TestSystemPromptMemoryOperations:
    """Test system prompt operations in memory management."""

    def test_agent_creation_with_system_prompt(self, tmp_path, monkeypatch):
        """Test that agents are created with system prompts."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        # Create agent with system prompt
        agent = manager.create_agent("test_agent", "You are helpful")

        assert agent.system_prompt == "You are helpful"
        assert manager.get_agent("test_agent").system_prompt == "You are helpful"

    def test_agent_creation_without_system_prompt(self, tmp_path, monkeypatch):
        """Test that agents can be created without system prompts."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        # Create agent without system prompt
        agent = manager.create_agent("test_agent")

        assert agent.system_prompt is None
        assert manager.get_agent("test_agent").system_prompt is None

    def test_system_prompt_update_and_persistence(self, tmp_path, monkeypatch):
        """Test that system prompt updates are persisted via JSONL events."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        # Create agent with initial system prompt
        agent = manager.create_agent("test_agent", "Original prompt")
        assert agent.system_prompt == "Original prompt"

        # Update system prompt (auto-persisted via property setter)
        agent.system_prompt = "Updated prompt"

        # Verify update persisted in JSONL
        jsonl_file = manager._agents_dir / "test_agent.jsonl"
        lines = jsonl_file.read_text().strip().split("\n")

        # Should have system_prompt_set events
        events = [json.loads(line) for line in lines]
        prompt_events = [e for e in events if e["type"] == "system_prompt_set"]
        assert len(prompt_events) == 2
        assert prompt_events[0]["content"] == "Original prompt"
        assert prompt_events[1]["content"] == "Updated prompt"

    def test_system_prompt_file_persistence(self, tmp_path, monkeypatch):
        """Test that system prompts are loaded from JSONL on restart."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))

        # Create first manager and agent
        manager1 = GlobalMemoryManager(tmp_path)
        manager1.create_agent("persistent_agent", "Persistent system prompt")

        # Verify JSONL file contains system prompt event
        agent_file = manager1._agents_dir / "persistent_agent.jsonl"
        assert agent_file.exists()

        events = [
            json.loads(line) for line in agent_file.read_text().strip().split("\n")
        ]
        prompt_events = [e for e in events if e["type"] == "system_prompt_set"]
        assert len(prompt_events) == 1
        assert prompt_events[0]["content"] == "Persistent system prompt"

        # Create second manager (simulates restart) - need to clear cached manager
        from mcp_handley_lab.llm import memory

        memory._memory_manager = None

        manager2 = GlobalMemoryManager(tmp_path)

        # Verify agent and system prompt were loaded
        loaded_agent = manager2.get_agent("persistent_agent")
        assert loaded_agent is not None
        assert loaded_agent.system_prompt == "Persistent system prompt"

    def test_system_prompt_stats(self, tmp_path, monkeypatch):
        """Test that system prompts appear in agent statistics."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        # Create agent with system prompt
        agent = manager.create_agent("test_agent", "Test system prompt")
        agent.add_message("user", "Hello", input_tokens=5, cost=0.001)

        stats = agent.get_stats()
        assert stats["system_prompt"] == "Test system prompt"
        assert stats["name"] == "test_agent"
        assert stats["message_count"] == 1

    def test_empty_system_prompt(self, tmp_path, monkeypatch):
        """Test handling of empty system prompts."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        # Create agent with empty system prompt
        agent = manager.create_agent("test_agent", "")
        assert agent.system_prompt == ""

        # Verify stats show empty prompt
        stats = agent.get_stats()
        assert stats["system_prompt"] == ""

    def test_none_system_prompt(self, tmp_path, monkeypatch):
        """Test handling of None system prompts."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

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
        self, mock_handle_memory, mock_calculate_cost, tmp_path, monkeypatch
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

        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        temp_memory = GlobalMemoryManager(tmp_path)

        with (
            patch("mcp_handley_lab.llm.shared.memory_manager", temp_memory),
            patch(
                "mcp_handley_lab.llm.shared.get_session_id",
                return_value="session_123",
            ),
        ):
            process_llm_request(
                prompt="Test prompt",
                output_file="-",
                agent_name="test_agent",
                model="gemini-2.5-flash",
                provider="gemini",
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
        self, mock_handle_memory, mock_calculate_cost, tmp_path, monkeypatch
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

        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        temp_memory = GlobalMemoryManager(tmp_path)

        with (
            patch("mcp_handley_lab.llm.shared.memory_manager", temp_memory),
            patch(
                "mcp_handley_lab.llm.shared.get_session_id",
                return_value="session_123",
            ),
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
        self, mock_handle_memory, mock_calculate_cost, tmp_path, monkeypatch
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

        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        temp_memory = GlobalMemoryManager(tmp_path)

        # Create agent with initial system prompt
        agent = temp_memory.create_agent("existing_agent", "Original prompt")
        assert agent.system_prompt == "Original prompt"

        with (
            patch("mcp_handley_lab.llm.shared.memory_manager", temp_memory),
            patch(
                "mcp_handley_lab.llm.shared.get_session_id",
                return_value="session_123",
            ),
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
