"""Unit tests for memory management module."""

import json
from pathlib import Path

import pytest

from mcp_handley_lab.llm.memory import (
    AgentMemory,
    GlobalMemoryManager,
    encode_project_path,
    validate_agent_name,
)


class TestPathEncoding:
    """Test path encoding functions."""

    def test_encode_simple_path(self):
        """Test encoding a simple Unix path."""
        result = encode_project_path(Path("/home/will/project"))
        assert result == "-home-will-project"

    def test_encode_handles_resolve(self, tmp_path):
        """Test that paths are resolved before encoding."""
        # Create a subdirectory
        sub = tmp_path / "foo"
        sub.mkdir()

        # Encode with relative path components
        relative = tmp_path / "foo" / ".." / "foo"
        result = encode_project_path(relative)

        # Should be same as resolved path
        expected = encode_project_path(sub)
        assert result == expected


class TestValidateAgentName:
    """Test agent name validation."""

    def test_valid_names(self):
        """Test valid agent names don't raise."""
        for name in ["session", "my_agent", "agent-1", "test.name", "Agent123"]:
            validate_agent_name(name)  # Should not raise

    def test_empty_name_raises(self):
        """Test empty name raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_agent_name("")

    def test_invalid_chars_raises(self):
        """Test names with invalid characters raise ValueError."""
        for name in ["../evil", "agent/name", "name with space", "name@email"]:
            with pytest.raises(ValueError, match="Invalid agent name"):
                validate_agent_name(name)

    def test_dot_prefix_raises(self):
        """Test names starting with dot raise ValueError."""
        for name in [".hidden", "..parent"]:
            with pytest.raises(ValueError, match="cannot start with a dot"):
                validate_agent_name(name)


class TestAgentMemory:
    """Test AgentMemory class."""

    def test_agent_creation(self, tmp_path):
        """Test basic agent creation."""
        agents_dir = tmp_path / "agents"
        agent = AgentMemory("test_agent", agents_dir)

        assert agent.name == "test_agent"
        assert agent.system_prompt is None
        assert len(agent.messages) == 0

    def test_add_message(self, tmp_path):
        """Test adding messages to agent."""
        agents_dir = tmp_path / "agents"
        agent = AgentMemory("test", agents_dir)

        agent.add_message("user", "Hello", input_tokens=5, cost=0.001)

        assert len(agent.messages) == 1
        assert agent.messages[0]["role"] == "user"
        assert agent.messages[0]["content"] == "Hello"

        agent.add_message("assistant", "Hi", output_tokens=3, cost=0.0005)

        assert len(agent.messages) == 2

    def test_add_message_with_provider(self, tmp_path):
        """Test adding messages with provider attribution."""
        agents_dir = tmp_path / "agents"
        agent = AgentMemory("test", agents_dir)

        agent.add_message(
            "assistant",
            "Response",
            input_tokens=10,
            output_tokens=20,
            cost=0.01,
            provider="openai",
            model="gpt-4o",
        )

        msg = agent.messages[0]
        assert msg["usage"]["provider"] == "openai"
        assert msg["usage"]["model"] == "gpt-4o"
        assert msg["usage"]["input_tokens"] == 10
        assert msg["usage"]["output_tokens"] == 20
        assert msg["usage"]["cost"] == 0.01

    def test_clear_history(self, tmp_path):
        """Test clearing conversation history."""
        agents_dir = tmp_path / "agents"
        agent = AgentMemory("test", agents_dir)
        agent.add_message("user", "Hello")

        assert len(agent.messages) == 1

        agent.clear_history()

        assert len(agent.messages) == 0

    def test_get_history(self, tmp_path):
        """Test getting conversation history in generic format."""
        agents_dir = tmp_path / "agents"
        agent = AgentMemory("test", agents_dir)
        agent.add_message("user", "Hello")
        agent.add_message("assistant", "Hi there")

        history = agent.get_history()

        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hi there"

    def test_get_stats(self, tmp_path):
        """Test getting agent statistics."""
        agents_dir = tmp_path / "agents"
        agent = AgentMemory("test_agent", agents_dir)
        agent.system_prompt = "helpful"
        agent.add_message("user", "Hello", input_tokens=5, cost=0.001)

        stats = agent.get_stats()

        assert stats["name"] == "test_agent"
        assert stats["created_at"] is not None  # Derived from first message
        assert stats["message_count"] == 1
        assert stats["total_input_tokens"] == 5
        assert stats["total_cost"] == 0.001
        assert stats["system_prompt"] == "helpful"

    def test_get_response_valid_index(self, tmp_path):
        """Test getting response by valid index (assistant messages only)."""
        agents_dir = tmp_path / "agents"
        agent = AgentMemory("test", agents_dir)
        agent.add_message("user", "Hello")
        agent.add_message("assistant", "Hi there")
        agent.add_message("user", "How are you?")
        agent.add_message("assistant", "I'm fine!")

        # Test default (-1, last assistant message)
        assert agent.get_response() == "I'm fine!"
        assert agent.get_response(-1) == "I'm fine!"

        # Test first assistant message (index 0)
        assert agent.get_response(0) == "Hi there"

        # Test second-to-last assistant message
        assert agent.get_response(-2) == "Hi there"

    def test_get_response_empty_raises(self, tmp_path):
        """Test getting response from empty message list raises IndexError."""
        agents_dir = tmp_path / "agents"
        agent = AgentMemory("test", agents_dir)

        with pytest.raises(
            IndexError, match="Cannot get response: agent has no assistant responses"
        ):
            agent.get_response()

    def test_get_response_no_assistant_messages_raises(self, tmp_path):
        """Test getting response when only user messages exist raises IndexError."""
        agents_dir = tmp_path / "agents"
        agent = AgentMemory("test", agents_dir)
        agent.add_message("user", "Hello")
        agent.add_message("user", "Anyone there?")

        with pytest.raises(
            IndexError, match="Cannot get response: agent has no assistant responses"
        ):
            agent.get_response()

    def test_persistence_jsonl(self, tmp_path):
        """Test that messages are persisted to JSONL file."""
        agents_dir = tmp_path / "agents"
        agent = AgentMemory("test", agents_dir)
        agent.add_message("user", "Hello")
        agent.add_message("assistant", "Hi")

        # Check file exists
        jsonl_file = agents_dir / "test.jsonl"
        assert jsonl_file.exists()

        # Check JSONL content
        lines = jsonl_file.read_text().strip().split("\n")
        assert len(lines) == 2

        for line in lines:
            event = json.loads(line)
            assert event["type"] == "message"
            assert event["v"] == 1
            assert "uuid" in event
            assert "timestamp" in event

    def test_load_from_jsonl(self, tmp_path):
        """Test loading agent from existing JSONL file."""
        agents_dir = tmp_path / "agents"

        # Create agent and add messages
        agent1 = AgentMemory("test", agents_dir)
        agent1.add_message("user", "Hello")
        agent1.add_message("assistant", "Hi")

        # Create new agent instance (simulates restart)
        agent2 = AgentMemory("test", agents_dir)

        assert len(agent2.messages) == 2
        assert agent2.messages[0]["content"] == "Hello"
        assert agent2.messages[1]["content"] == "Hi"


class TestGlobalMemoryManager:
    """Test GlobalMemoryManager class."""

    def test_memory_manager_creation(self, tmp_path, monkeypatch):
        """Test memory manager creation."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        assert manager.cwd == tmp_path
        project_dir = manager._project_dir
        assert project_dir.exists()
        assert (project_dir / "project.json").exists()

    def test_create_agent(self, tmp_path, monkeypatch):
        """Test creating a new agent."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        agent = manager.create_agent("test_agent", "helpful system prompt")

        assert agent.name == "test_agent"
        assert agent.system_prompt == "helpful system prompt"

    def test_get_agent_exists(self, tmp_path, monkeypatch):
        """Test getting existing agent."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        manager.create_agent("test_agent")
        retrieved_agent = manager.get_agent("test_agent")

        assert retrieved_agent is not None
        assert retrieved_agent.name == "test_agent"

    def test_get_agent_not_exists(self, tmp_path, monkeypatch):
        """Test getting non-existing agent."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        agent = manager.get_agent("nonexistent")

        assert agent is None

    def test_list_agents(self, tmp_path, monkeypatch):
        """Test listing all agents."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        assert len(manager.list_agents()) == 0

        manager.create_agent("agent1")
        manager.create_agent("agent2")

        agents = manager.list_agents()
        assert len(agents) == 2
        names = [a.name for a in agents]
        assert "agent1" in names
        assert "agent2" in names

    def test_delete_agent(self, tmp_path, monkeypatch):
        """Test deleting agent."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        manager.create_agent("test_agent")
        agent_file = manager._agents_dir / "test_agent.jsonl"

        # Add a message so file gets created
        manager.add_message("test_agent", "user", "Hello")
        assert agent_file.exists()

        manager.delete_agent("test_agent")
        assert not agent_file.exists()

    def test_add_message_creates_agent(self, tmp_path, monkeypatch):
        """Test add_message creates agent if not exists."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        # Agent doesn't exist yet
        assert manager.get_agent("new_agent") is None

        # add_message should auto-create
        manager.add_message(
            "new_agent",
            "user",
            "Hello",
            input_tokens=5,
            provider="gemini",
            model="gemini-2.5-pro",
        )

        agent = manager.get_agent("new_agent")
        assert agent is not None
        assert len(agent.messages) == 1

    def test_clear_agent_history(self, tmp_path, monkeypatch):
        """Test clearing agent history."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        manager.create_agent("test_agent")
        manager.add_message("test_agent", "user", "Hello")

        agent = manager.get_agent("test_agent")
        assert len(agent.messages) == 1

        manager.clear_agent_history("test_agent")
        assert len(agent.messages) == 0

    def test_get_response(self, tmp_path, monkeypatch):
        """Test getting response from agent (assistant messages only)."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        manager.create_agent("test_agent")
        manager.add_message("test_agent", "user", "Hello")
        manager.add_message("test_agent", "assistant", "Hi there")
        manager.add_message("test_agent", "user", "How are you?")
        manager.add_message("test_agent", "assistant", "I'm fine!")

        # Default: last assistant response
        response = manager.get_response("test_agent")
        assert response == "I'm fine!"

        # Index 0: first assistant response
        response = manager.get_response("test_agent", 0)
        assert response == "Hi there"

    def test_get_response_nonexistent_raises(self, tmp_path, monkeypatch):
        """Test getting response from non-existing agent raises."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        with pytest.raises(ValueError, match="not found"):
            manager.get_response("nonexistent")

    def test_project_metadata(self, tmp_path, monkeypatch):
        """Test project metadata is created and updated."""
        monkeypatch.setenv("MCP_HANDLEY_LAB_MEMORY_DIR", str(tmp_path))
        manager = GlobalMemoryManager(tmp_path)

        metadata_file = manager._project_dir / "project.json"
        assert metadata_file.exists()

        data = json.loads(metadata_file.read_text())
        assert "original_path" in data
        assert "created_at" in data
        assert "last_used_at" in data
        assert "schema_version" in data
