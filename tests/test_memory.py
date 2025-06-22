"""Unit tests for memory management system."""
import json
import tempfile
from datetime import datetime
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from mcp_framework.common.memory import Message, AgentMemory, MemoryManager, memory_manager


class TestMessage:
    """Test cases for Message model."""
    
    def test_message_creation(self):
        """Test message creation with all fields."""
        timestamp = datetime.now()
        message = Message(
            role="user",
            content="Hello",
            timestamp=timestamp,
            tokens=10,
            cost=0.01
        )
        
        assert message.role == "user"
        assert message.content == "Hello"
        assert message.timestamp == timestamp
        assert message.tokens == 10
        assert message.cost == 0.01
    
    def test_message_optional_fields(self):
        """Test message creation with optional fields."""
        timestamp = datetime.now()
        message = Message(
            role="assistant",
            content="Hi there",
            timestamp=timestamp
        )
        
        assert message.role == "assistant"
        assert message.content == "Hi there"
        assert message.tokens is None
        assert message.cost is None


class TestAgentMemory:
    """Test cases for AgentMemory model."""
    
    @pytest.fixture
    def sample_agent(self):
        """Create a sample agent for testing."""
        return AgentMemory(
            name="test_agent",
            personality="Helpful assistant",
            created_at=datetime(2025, 1, 1, 12, 0, 0)
        )
    
    def test_agent_creation(self, sample_agent):
        """Test agent creation."""
        assert sample_agent.name == "test_agent"
        assert sample_agent.personality == "Helpful assistant"
        assert sample_agent.created_at == datetime(2025, 1, 1, 12, 0, 0)
        assert sample_agent.messages == []
        assert sample_agent.total_tokens == 0
        assert sample_agent.total_cost == 0.0
    
    def test_add_message(self, sample_agent):
        """Test adding messages to agent memory."""
        sample_agent.add_message("user", "Hello", tokens=5, cost=0.01)
        sample_agent.add_message("assistant", "Hi there", tokens=8, cost=0.02)
        
        assert len(sample_agent.messages) == 2
        assert sample_agent.messages[0].role == "user"
        assert sample_agent.messages[0].content == "Hello"
        assert sample_agent.messages[1].role == "assistant"
        assert sample_agent.messages[1].content == "Hi there"
        assert sample_agent.total_tokens == 13
        assert sample_agent.total_cost == 0.03
    
    def test_clear_history(self, sample_agent):
        """Test clearing agent history."""
        sample_agent.add_message("user", "Hello", tokens=5, cost=0.01)
        sample_agent.add_message("assistant", "Hi", tokens=3, cost=0.005)
        
        sample_agent.clear_history()
        
        assert sample_agent.messages == []
        assert sample_agent.total_tokens == 0
        assert sample_agent.total_cost == 0.0
    
    def test_get_conversation_history_no_personality(self, sample_agent):
        """Test getting conversation history without personality."""
        sample_agent.personality = None
        sample_agent.add_message("user", "Hello")
        sample_agent.add_message("assistant", "Hi there")
        
        history = sample_agent.get_conversation_history()
        
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hello"}
        assert history[1] == {"role": "assistant", "content": "Hi there"}
    
    def test_get_conversation_history_with_personality(self, sample_agent):
        """Test getting conversation history with personality."""
        sample_agent.add_message("user", "Hello")
        sample_agent.add_message("assistant", "Hi there")
        
        history = sample_agent.get_conversation_history()
        
        assert len(history) == 3
        assert history[0] == {"role": "system", "content": "Helpful assistant"}
        assert history[1] == {"role": "user", "content": "Hello"}
        assert history[2] == {"role": "assistant", "content": "Hi there"}
    
    def test_get_stats(self, sample_agent):
        """Test getting agent statistics."""
        sample_agent.add_message("user", "Hello", tokens=5, cost=0.01)
        sample_agent.add_message("assistant", "Hi", tokens=3, cost=0.005)
        
        stats = sample_agent.get_stats()
        
        assert stats["name"] == "test_agent"
        assert stats["created_at"] == "2025-01-01T12:00:00"
        assert stats["message_count"] == 2
        assert stats["total_tokens"] == 8
        assert stats["total_cost"] == 0.015
        assert stats["personality"] == "Helpful assistant"


class TestMemoryManager:
    """Test cases for MemoryManager."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def memory_mgr(self, temp_storage):
        """Create memory manager with temporary storage."""
        return MemoryManager(storage_dir=temp_storage)
    
    def test_memory_manager_initialization(self, memory_mgr, temp_storage):
        """Test memory manager initialization."""
        assert memory_mgr.storage_dir == Path(temp_storage)
        assert memory_mgr.agents_file == Path(temp_storage) / "agents.json"
        assert memory_mgr._agents == {}
    
    def test_create_agent(self, memory_mgr):
        """Test creating a new agent."""
        agent = memory_mgr.create_agent("test_agent", "Test personality")
        
        assert agent.name == "test_agent"
        assert agent.personality == "Test personality"
        assert "test_agent" in memory_mgr._agents
        assert memory_mgr.agents_file.exists()
    
    def test_create_duplicate_agent(self, memory_mgr):
        """Test creating duplicate agent raises error."""
        memory_mgr.create_agent("test_agent")
        
        with pytest.raises(ValueError, match="Agent 'test_agent' already exists"):
            memory_mgr.create_agent("test_agent")
    
    def test_get_agent(self, memory_mgr):
        """Test getting an existing agent."""
        created_agent = memory_mgr.create_agent("test_agent")
        retrieved_agent = memory_mgr.get_agent("test_agent")
        
        assert retrieved_agent == created_agent
        assert retrieved_agent.name == "test_agent"
    
    def test_get_nonexistent_agent(self, memory_mgr):
        """Test getting non-existent agent returns None."""
        agent = memory_mgr.get_agent("nonexistent")
        assert agent is None
    
    def test_list_agents(self, memory_mgr):
        """Test listing all agents."""
        agent1 = memory_mgr.create_agent("agent1")
        agent2 = memory_mgr.create_agent("agent2")
        
        agents = memory_mgr.list_agents()
        
        assert len(agents) == 2
        assert agent1 in agents
        assert agent2 in agents
    
    def test_delete_agent(self, memory_mgr):
        """Test deleting an agent."""
        memory_mgr.create_agent("test_agent")
        
        success = memory_mgr.delete_agent("test_agent")
        
        assert success is True
        assert "test_agent" not in memory_mgr._agents
        assert memory_mgr.get_agent("test_agent") is None
    
    def test_delete_nonexistent_agent(self, memory_mgr):
        """Test deleting non-existent agent returns False."""
        success = memory_mgr.delete_agent("nonexistent")
        assert success is False
    
    def test_add_message(self, memory_mgr):
        """Test adding message to agent."""
        memory_mgr.create_agent("test_agent")
        
        memory_mgr.add_message("test_agent", "user", "Hello", tokens=5, cost=0.01)
        
        agent = memory_mgr.get_agent("test_agent")
        assert len(agent.messages) == 1
        assert agent.messages[0].content == "Hello"
        assert agent.total_tokens == 5
        assert agent.total_cost == 0.01
    
    def test_add_message_nonexistent_agent(self, memory_mgr):
        """Test adding message to non-existent agent does nothing."""
        memory_mgr.add_message("nonexistent", "user", "Hello")
        # Should not raise error, just do nothing
    
    def test_clear_agent_history(self, memory_mgr):
        """Test clearing agent history."""
        memory_mgr.create_agent("test_agent")
        memory_mgr.add_message("test_agent", "user", "Hello", tokens=5, cost=0.01)
        
        success = memory_mgr.clear_agent_history("test_agent")
        
        assert success is True
        agent = memory_mgr.get_agent("test_agent")
        assert len(agent.messages) == 0
        assert agent.total_tokens == 0
        assert agent.total_cost == 0.0
    
    def test_clear_nonexistent_agent_history(self, memory_mgr):
        """Test clearing non-existent agent history returns False."""
        success = memory_mgr.clear_agent_history("nonexistent")
        assert success is False
    
    def test_save_and_load_agents(self, memory_mgr):
        """Test saving and loading agents from disk."""
        # Create and populate agent
        agent = memory_mgr.create_agent("test_agent", "Test personality")
        memory_mgr.add_message("test_agent", "user", "Hello", tokens=5, cost=0.01)
        
        # Create new manager with same storage
        new_mgr = MemoryManager(storage_dir=str(memory_mgr.storage_dir))
        
        # Check agent was loaded
        loaded_agent = new_mgr.get_agent("test_agent")
        assert loaded_agent is not None
        assert loaded_agent.name == "test_agent"
        assert loaded_agent.personality == "Test personality"
        assert len(loaded_agent.messages) == 1
        assert loaded_agent.messages[0].content == "Hello"
        assert loaded_agent.total_tokens == 5
        assert loaded_agent.total_cost == 0.01
    
    def test_load_corrupted_file(self, memory_mgr):
        """Test loading corrupted agents file starts fresh."""
        # Write corrupted JSON
        memory_mgr.agents_file.write_text("invalid json")
        
        # Create new manager - should start fresh
        new_mgr = MemoryManager(storage_dir=str(memory_mgr.storage_dir))
        
        assert new_mgr._agents == {}
    
    def test_load_missing_file(self, memory_mgr):
        """Test loading when file doesn't exist."""
        # Remove file if it exists
        if memory_mgr.agents_file.exists():
            memory_mgr.agents_file.unlink()
        
        # Create new manager - should start fresh
        new_mgr = MemoryManager(storage_dir=str(memory_mgr.storage_dir))
        
        assert new_mgr._agents == {}


class TestGlobalMemoryManager:
    """Test the global memory manager instance."""
    
    def test_global_memory_manager_exists(self):
        """Test that global memory manager instance exists."""
        assert memory_manager is not None
        assert isinstance(memory_manager, MemoryManager)