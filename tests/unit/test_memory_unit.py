"""Unit tests for memory management module."""
import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from mcp_handley_lab.common.memory import AgentMemory, MemoryManager, Message


class TestMessage:
    """Test Message model."""

    def test_message_creation(self):
        """Test basic message creation."""
        msg = Message(
            role="user",
            content="Hello",
            timestamp=datetime.now(),
            tokens=10,
            cost=0.001,
        )
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tokens == 10
        assert msg.cost == 0.001

    def test_message_optional_fields(self):
        """Test message with optional fields."""
        msg = Message(role="assistant", content="Hi there", timestamp=datetime.now())
        assert msg.role == "assistant"
        assert msg.content == "Hi there"
        assert msg.tokens is None
        assert msg.cost is None


class TestAgentMemory:
    """Test AgentMemory model."""

    def test_agent_creation(self):
        """Test basic agent creation."""
        agent = AgentMemory(name="test_agent", created_at=datetime.now())
        assert agent.name == "test_agent"
        assert agent.personality is None
        assert len(agent.messages) == 0
        assert agent.total_tokens == 0
        assert agent.total_cost == 0.0

    def test_agent_with_personality(self):
        """Test agent with personality."""
        agent = AgentMemory(
            name="helpful_agent",
            personality="You are helpful",
            created_at=datetime.now(),
        )
        assert agent.personality == "You are helpful"

    def test_add_message(self):
        """Test adding messages to agent."""
        agent = AgentMemory(name="test", created_at=datetime.now())

        agent.add_message("user", "Hello", tokens=5, cost=0.001)

        assert len(agent.messages) == 1
        assert agent.messages[0].role == "user"
        assert agent.messages[0].content == "Hello"
        assert agent.total_tokens == 5
        assert agent.total_cost == 0.001

        agent.add_message("assistant", "Hi", tokens=3, cost=0.0005)

        assert len(agent.messages) == 2
        assert agent.total_tokens == 8
        assert agent.total_cost == 0.0015

    def test_clear_history(self):
        """Test clearing conversation history."""
        agent = AgentMemory(name="test", created_at=datetime.now())
        agent.add_message("user", "Hello", tokens=5, cost=0.001)

        assert len(agent.messages) == 1
        assert agent.total_tokens == 5
        assert agent.total_cost == 0.001

        agent.clear_history()

        assert len(agent.messages) == 0
        assert agent.total_tokens == 0
        assert agent.total_cost == 0.0

    def test_get_history(self):
        """Test getting conversation history in generic format."""
        agent = AgentMemory(name="test", created_at=datetime.now())
        agent.add_message("user", "Hello")
        agent.add_message("assistant", "Hi there")

        history = agent.get_history()

        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hi there"

    def test_get_stats(self):
        """Test getting agent statistics."""
        created_time = datetime.now()
        agent = AgentMemory(
            name="test_agent", personality="helpful", created_at=created_time
        )
        agent.add_message("user", "Hello", tokens=5, cost=0.001)

        stats = agent.get_stats()

        assert stats["name"] == "test_agent"
        assert stats["created_at"] == created_time.isoformat()
        assert stats["message_count"] == 1
        assert stats["total_tokens"] == 5
        assert stats["total_cost"] == 0.001
        assert stats["personality"] == "helpful"

    def test_get_response_valid_index(self):
        """Test getting response by valid index."""
        agent = AgentMemory(name="test", created_at=datetime.now())
        agent.add_message("user", "Hello")
        agent.add_message("assistant", "Hi there")

        # Test default (-1, last message)
        assert agent.get_response() == "Hi there"
        assert agent.get_response(-1) == "Hi there"

        # Test first message
        assert agent.get_response(0) == "Hello"

        # Test second message
        assert agent.get_response(1) == "Hi there"

    def test_get_response_invalid_index(self):
        """Test getting response by invalid index."""
        agent = AgentMemory(name="test", created_at=datetime.now())
        agent.add_message("user", "Hello")

        # Out of range index should raise IndexError for fail-fast behavior
        with pytest.raises(IndexError):
            agent.get_response(10)

        with pytest.raises(IndexError):
            agent.get_response(-10)

    def test_get_response_empty_messages(self):
        """Test getting response from empty message list - should raise IndexError."""
        agent = AgentMemory(name="test", created_at=datetime.now())

        with pytest.raises(
            IndexError, match="Cannot get response: agent has no message history"
        ):
            agent.get_response()

        with pytest.raises(
            IndexError, match="Cannot get response: agent has no message history"
        ):
            agent.get_response(0)


class TestMemoryManager:
    """Test MemoryManager class."""

    def test_memory_manager_creation(self):
        """Test memory manager creation with temp directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)
            assert manager.storage_dir == Path(temp_dir)
            assert manager.agents_dir == Path(temp_dir) / "agents"
            assert manager.agents_dir.exists()

    def test_create_agent(self):
        """Test creating a new agent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            agent = manager.create_agent("test_agent", "helpful personality")

            assert agent.name == "test_agent"
            assert agent.personality == "helpful personality"
            assert "test_agent" in manager._agents

            # Check file was created
            agent_file = manager.agents_dir / "test_agent.json"
            assert agent_file.exists()

    def test_create_duplicate_agent(self):
        """Test creating duplicate agent raises error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            manager.create_agent("test_agent")

            with pytest.raises(ValueError, match="Agent 'test_agent' already exists"):
                manager.create_agent("test_agent")

    def test_get_agent_exists(self):
        """Test getting existing agent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            created_agent = manager.create_agent("test_agent")
            retrieved_agent = manager.get_agent("test_agent")

            assert retrieved_agent is not None
            assert retrieved_agent.name == "test_agent"
            assert retrieved_agent is created_agent

    def test_get_agent_not_exists(self):
        """Test getting non-existing agent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            agent = manager.get_agent("nonexistent")

            assert agent is None

    def test_list_agents(self):
        """Test listing all agents."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            assert len(manager.list_agents()) == 0

            agent1 = manager.create_agent("agent1")
            agent2 = manager.create_agent("agent2")

            agents = manager.list_agents()
            assert len(agents) == 2
            assert agent1 in agents
            assert agent2 in agents

    def test_delete_agent_exists(self):
        """Test deleting existing agent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            manager.create_agent("test_agent")
            agent_file = manager.agents_dir / "test_agent.json"
            assert agent_file.exists()

            manager.delete_agent("test_agent")  # No return value on success
            assert "test_agent" not in manager._agents
            assert not agent_file.exists()

    def test_delete_agent_not_exists(self):
        """Test deleting non-existing agent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
                manager.delete_agent("nonexistent")

    def test_add_message_to_agent(self):
        """Test adding message to agent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            agent = manager.create_agent("test_agent")
            manager.add_message("test_agent", "user", "Hello", tokens=5, cost=0.001)

            assert len(agent.messages) == 1
            assert agent.messages[0].content == "Hello"

    def test_add_message_to_nonexistent_agent(self):
        """Test adding message to non-existing agent does nothing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            # Should not raise error
            manager.add_message("nonexistent", "user", "Hello")

    def test_clear_agent_history_exists(self):
        """Test clearing history of existing agent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            agent = manager.create_agent("test_agent")
            manager.add_message("test_agent", "user", "Hello")

            assert len(agent.messages) == 1

            manager.clear_agent_history("test_agent")  # No return value on success
            assert len(agent.messages) == 0

    def test_clear_agent_history_not_exists(self):
        """Test clearing history of non-existing agent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
                manager.clear_agent_history("nonexistent")

    def test_get_response_from_agent(self):
        """Test getting response from agent via manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            manager.create_agent("test_agent")
            manager.add_message("test_agent", "user", "Hello")
            manager.add_message("test_agent", "assistant", "Hi there")

            # Test getting last message
            response = manager.get_response("test_agent")
            assert response == "Hi there"

            # Test getting first message
            response = manager.get_response("test_agent", 0)
            assert response == "Hello"

    def test_get_response_from_nonexistent_agent(self):
        """Test getting response from non-existing agent."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(temp_dir)

            with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
                manager.get_response("nonexistent")

    def test_load_agents_from_disk(self):
        """Test loading agents from disk on initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create manager and agent
            manager1 = MemoryManager(temp_dir)
            manager1.create_agent("persistent_agent", "persistent personality")
            manager1.add_message("persistent_agent", "user", "Hello")

            # Create new manager instance (simulates restart)
            manager2 = MemoryManager(temp_dir)

            # Check agent was loaded
            loaded_agent = manager2.get_agent("persistent_agent")
            assert loaded_agent is not None
            assert loaded_agent.name == "persistent_agent"
            assert loaded_agent.personality == "persistent personality"
            assert len(loaded_agent.messages) == 1
            assert loaded_agent.messages[0].content == "Hello"

    def test_load_agents_corrupted_file(self):
        """Test loading agents with corrupted JSON file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agents_dir = Path(temp_dir) / "agents"
            agents_dir.mkdir()

            # Create corrupted JSON file
            corrupted_file = agents_dir / "corrupted.json"
            corrupted_file.write_text("invalid json content")

            # Should raise an error for corrupted file
            with pytest.raises(
                (ValueError, json.JSONDecodeError)
            ):  # ValidationError from Pydantic
                MemoryManager(temp_dir)

    def test_load_agents_no_agents_dir(self):
        """Test loading agents when agents directory doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Don't create agents directory
            manager = MemoryManager(temp_dir)
            # Should create the directory during init, but then delete it to test the early return
            manager.agents_dir.rmdir()

            # This should trigger the early return in _load_agents
            manager._load_agents()
            assert len(manager.list_agents()) == 0
