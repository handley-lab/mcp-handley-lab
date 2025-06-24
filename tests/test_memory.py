"""Unit tests for memory management system."""
import json
import tempfile
from datetime import datetime
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from mcp_handley_lab.common.memory import Message, AgentMemory, MemoryManager, memory_manager


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
        assert history[0] == {"role": "user", "content": [{"text": "Hello"}]}
        assert history[1] == {"role": "model", "content": [{"text": "Hi there"}]}
    
    def test_get_conversation_history_with_personality(self, sample_agent):
        """Test getting conversation history with personality."""
        sample_agent.add_message("user", "Hello")
        sample_agent.add_message("assistant", "Hi there")
        
        history = sample_agent.get_conversation_history()
        
        # Personality is now handled in the tool, not in memory
        # So we should only see the user/assistant messages  
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": [{"text": "Hello"}]}
        assert history[1] == {"role": "model", "content": [{"text": "Hi there"}]}
    
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
    
    def test_get_response_empty(self, sample_agent):
        """Test getting response from empty agent."""
        result = sample_agent.get_response()
        assert result is None
    
    def test_get_response_last_message(self, sample_agent):
        """Test getting last message."""
        sample_agent.add_message("user", "Hello")
        sample_agent.add_message("assistant", "Hi there")
        
        result = sample_agent.get_response()
        assert result == "Hi there"
    
    def test_get_response_specific_index(self, sample_agent):
        """Test getting message by specific index."""
        sample_agent.add_message("user", "Hello")
        sample_agent.add_message("assistant", "Hi there")
        sample_agent.add_message("user", "How are you?")
        
        result = sample_agent.get_response(0)
        assert result == "Hello"
        
        result = sample_agent.get_response(1)
        assert result == "Hi there"
        
        result = sample_agent.get_response(2)
        assert result == "How are you?"
    
    def test_get_response_negative_index(self, sample_agent):
        """Test getting message with negative index."""
        sample_agent.add_message("user", "Hello")
        sample_agent.add_message("assistant", "Hi there")
        sample_agent.add_message("user", "How are you?")
        
        result = sample_agent.get_response(-1)
        assert result == "How are you?"
        
        result = sample_agent.get_response(-2)
        assert result == "Hi there"
    
    def test_get_response_out_of_bounds(self, sample_agent):
        """Test getting message with out of bounds index."""
        sample_agent.add_message("user", "Hello")
        
        result = sample_agent.get_response(5)
        assert result is None
        
        result = sample_agent.get_response(-5)
        assert result is None


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
        assert memory_mgr.agents_dir == Path(temp_storage) / "agents"
        assert memory_mgr._agents == {}
        assert memory_mgr.agents_dir.exists()
    
    def test_create_agent(self, memory_mgr):
        """Test creating a new agent."""
        agent = memory_mgr.create_agent("test_agent", "Test personality")
        
        assert agent.name == "test_agent"
        assert agent.personality == "Test personality"
        assert "test_agent" in memory_mgr._agents
        agent_file = memory_mgr._get_agent_file("test_agent")
        assert agent_file.exists()
    
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
        """Test loading corrupted agent file is skipped."""
        # Create agent first
        memory_mgr.create_agent("test_agent")
        
        # Write corrupted JSON to agent file
        agent_file = memory_mgr._get_agent_file("test_agent")
        agent_file.write_text("invalid json")
        
        # Create new manager - should skip corrupted file
        new_mgr = MemoryManager(storage_dir=str(memory_mgr.storage_dir))
        
        assert new_mgr.get_agent("test_agent") is None
    
    def test_load_missing_directory(self, temp_storage):
        """Test loading when agents directory doesn't exist."""
        # Create manager with fresh directory
        new_mgr = MemoryManager(storage_dir=temp_storage)
        
        assert new_mgr._agents == {}
        assert new_mgr.agents_dir.exists()
    
    def test_load_agents_no_directory(self, temp_storage):
        """Test _load_agents when directory doesn't exist yet."""
        # Create manager but remove agents directory after creation
        mgr = MemoryManager(storage_dir=temp_storage)
        mgr.agents_dir.rmdir()  # Remove the directory
        
        # Call _load_agents directly on empty directory
        mgr._load_agents()
        
        # Should handle gracefully - no agents loaded
        assert mgr._agents == {}
    
    def test_delete_agent_removes_file(self, memory_mgr):
        """Test deleting agent removes the file."""
        memory_mgr.create_agent("test_agent")
        agent_file = memory_mgr._get_agent_file("test_agent")
        assert agent_file.exists()
        
        success = memory_mgr.delete_agent("test_agent")
        
        assert success is True
        assert not agent_file.exists()
    
    def test_get_agent_file(self, memory_mgr):
        """Test getting agent file path."""
        agent_file = memory_mgr._get_agent_file("test_agent")
        expected_path = memory_mgr.agents_dir / "test_agent.json"
        assert agent_file == expected_path
    
    def test_save_agent_method(self, memory_mgr):
        """Test the _save_agent method."""
        agent = memory_mgr.create_agent("test_agent", "Test personality")
        agent.add_message("user", "Hello", tokens=5, cost=0.01)
        
        # Save agent directly
        memory_mgr._save_agent(agent)
        
        # Verify file content
        agent_file = memory_mgr._get_agent_file("test_agent")
        with open(agent_file) as f:
            data = json.load(f)
        
        assert data["name"] == "test_agent"
        assert data["personality"] == "Test personality"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "Hello"
    
    def test_multiple_agents_individual_files(self, memory_mgr):
        """Test that multiple agents get individual files."""
        agent1 = memory_mgr.create_agent("agent1", "First agent")
        agent2 = memory_mgr.create_agent("agent2", "Second agent")
        
        file1 = memory_mgr._get_agent_file("agent1")
        file2 = memory_mgr._get_agent_file("agent2")
        
        assert file1.exists()
        assert file2.exists()
        assert file1 != file2
        
        # Verify file contents are different
        with open(file1) as f:
            data1 = json.load(f)
        with open(file2) as f:
            data2 = json.load(f)
        
        assert data1["name"] == "agent1"
        assert data2["name"] == "agent2"
        assert data1["personality"] == "First agent"
        assert data2["personality"] == "Second agent"
    
    def test_get_response_success(self, memory_mgr):
        """Test getting response from agent via manager."""
        agent = memory_mgr.create_agent("test_agent")
        agent.add_message("user", "Hello")
        agent.add_message("assistant", "Hi there")
        
        result = memory_mgr.get_response("test_agent")
        assert result == "Hi there"
    
    def test_get_response_with_index(self, memory_mgr):
        """Test getting response with specific index via manager."""
        agent = memory_mgr.create_agent("test_agent")
        agent.add_message("user", "Hello")
        agent.add_message("assistant", "Hi there")
        
        result = memory_mgr.get_response("test_agent", 0)
        assert result == "Hello"
        
        result = memory_mgr.get_response("test_agent", 1)
        assert result == "Hi there"
    
    def test_get_response_nonexistent_agent(self, memory_mgr):
        """Test getting response from non-existent agent."""
        result = memory_mgr.get_response("nonexistent")
        assert result is None


class TestMemoryManagerExportImport:
    """Test cases for export/import functionality."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def memory_mgr(self, temp_storage):
        """Create memory manager with temporary storage."""
        return MemoryManager(storage_dir=temp_storage)
    
    def test_export_agent_success(self, memory_mgr):
        """Test successful agent export."""
        agent = memory_mgr.create_agent("test_agent", "Export test")
        memory_mgr.add_message("test_agent", "user", "Hello", tokens=5, cost=0.01)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            export_path = f.name
        
        try:
            success = memory_mgr.export_agent("test_agent", export_path)
            assert success is True
            
            # Verify exported content
            with open(export_path) as f:
                data = json.load(f)
            
            assert data["name"] == "test_agent"
            assert data["personality"] == "Export test"
            assert len(data["messages"]) == 1
            assert data["messages"][0]["content"] == "Hello"
        finally:
            Path(export_path).unlink()
    
    def test_export_nonexistent_agent(self, memory_mgr):
        """Test exporting non-existent agent returns False."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            export_path = f.name
        
        try:
            success = memory_mgr.export_agent("nonexistent", export_path)
            assert success is False
        finally:
            if Path(export_path).exists():
                Path(export_path).unlink()
    
    def test_export_agent_invalid_path(self, memory_mgr):
        """Test exporting to invalid path returns False."""
        memory_mgr.create_agent("test_agent")
        
        # Try to export to invalid path (directory that doesn't exist)
        success = memory_mgr.export_agent("test_agent", "/nonexistent/path/agent.json")
        assert success is False
    
    def test_import_agent_success(self, memory_mgr):
        """Test successful agent import."""
        # Create export data
        agent_data = {
            "name": "imported_agent",
            "personality": "Imported personality",
            "created_at": "2025-01-01T12:00:00",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                    "timestamp": "2025-01-01T12:01:00",
                    "tokens": 5,
                    "cost": 0.01
                }
            ],
            "total_tokens": 5,
            "total_cost": 0.01
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(agent_data, f)
            import_path = f.name
        
        try:
            success = memory_mgr.import_agent(import_path)
            assert success is True
            
            # Verify imported agent
            agent = memory_mgr.get_agent("imported_agent")
            assert agent is not None
            assert agent.name == "imported_agent"
            assert agent.personality == "Imported personality"
            assert len(agent.messages) == 1
            assert agent.messages[0].content == "Hello"
            assert agent.total_tokens == 5
            assert agent.total_cost == 0.01
        finally:
            Path(import_path).unlink()
    
    def test_import_agent_overwrite_false(self, memory_mgr):
        """Test importing existing agent without overwrite returns False."""
        memory_mgr.create_agent("existing_agent")
        
        agent_data = {
            "name": "existing_agent",
            "personality": "New personality",
            "created_at": "2025-01-01T12:00:00",
            "messages": [],
            "total_tokens": 0,
            "total_cost": 0.0
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(agent_data, f)
            import_path = f.name
        
        try:
            success = memory_mgr.import_agent(import_path, overwrite=False)
            assert success is False
            
            # Original agent should be unchanged
            agent = memory_mgr.get_agent("existing_agent")
            assert agent.personality is None  # Original had no personality
        finally:
            Path(import_path).unlink()
    
    def test_import_agent_overwrite_true(self, memory_mgr):
        """Test importing existing agent with overwrite."""
        memory_mgr.create_agent("existing_agent", "Original personality")
        
        agent_data = {
            "name": "existing_agent",
            "personality": "New personality",
            "created_at": "2025-01-01T12:00:00",
            "messages": [],
            "total_tokens": 0,
            "total_cost": 0.0
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(agent_data, f)
            import_path = f.name
        
        try:
            success = memory_mgr.import_agent(import_path, overwrite=True)
            assert success is True
            
            # Agent should be updated
            agent = memory_mgr.get_agent("existing_agent")
            assert agent.personality == "New personality"
        finally:
            Path(import_path).unlink()
    
    def test_import_agent_invalid_file(self, memory_mgr):
        """Test importing invalid file returns False."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json")
            import_path = f.name
        
        try:
            success = memory_mgr.import_agent(import_path)
            assert success is False
        finally:
            Path(import_path).unlink()
    
    def test_import_agent_missing_file(self, memory_mgr):
        """Test importing missing file returns False."""
        success = memory_mgr.import_agent("/nonexistent/file.json")
        assert success is False
    
    def test_import_agent_creates_file(self, memory_mgr):
        """Test that importing agent creates individual file."""
        agent_data = {
            "name": "file_test_agent",
            "personality": "File test",
            "created_at": "2025-01-01T12:00:00",
            "messages": [],
            "total_tokens": 0,
            "total_cost": 0.0
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(agent_data, f)
            import_path = f.name
        
        try:
            success = memory_mgr.import_agent(import_path)
            assert success is True
            
            # Check that individual file was created
            agent_file = memory_mgr._get_agent_file("file_test_agent")
            assert agent_file.exists()
        finally:
            Path(import_path).unlink()


class TestGlobalMemoryManager:
    """Test the global memory manager instance."""
    
    def test_global_memory_manager_exists(self):
        """Test that global memory manager instance exists."""
        assert memory_manager is not None
        assert isinstance(memory_manager, MemoryManager)