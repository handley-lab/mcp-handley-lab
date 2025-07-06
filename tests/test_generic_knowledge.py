"""Comprehensive tests for the generic knowledge management system."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp_handley_lab.knowledge.generic_manager import GenericKnowledgeManager
from mcp_handley_lab.knowledge.models import Entity
from mcp_handley_lab.knowledge.storage import GlobalLocalYAMLStorage, YAMLEntityStorage


class TestEntity:
    """Test Entity model functionality."""

    def test_entity_creation(self):
        """Test creating a basic entity."""
        entity = Entity(
            type="person",
            properties={"name": "Alice", "email": "alice@example.com"},
            tags=["contact", "researcher"],
            content="Alice is a researcher working on AI.",
        )

        assert entity.type == "person"
        assert entity.properties["name"] == "Alice"
        assert entity.properties["email"] == "alice@example.com"
        assert "contact" in entity.tags
        assert "researcher" in entity.tags
        assert entity.content == "Alice is a researcher working on AI."
        assert isinstance(entity.id, str)
        assert len(entity.id) == 36  # UUID format

    def test_property_operations(self):
        """Test property get/set operations."""
        entity = Entity(type="test")

        # Test getting non-existent property
        assert entity.get_property("nonexistent") is None
        assert entity.get_property("nonexistent", "default") == "default"

        # Test setting and getting property
        entity.set_property("test_prop", "test_value")
        assert entity.get_property("test_prop") == "test_value"
        assert entity.properties["test_prop"] == "test_value"

    def test_tag_operations(self):
        """Test tag-related operations."""
        entity = Entity(type="test", tags=["initial"])

        # Test has_tag
        assert entity.has_tag("initial")
        assert not entity.has_tag("nonexistent")

        # Test add_tag
        entity.add_tag("new_tag")
        assert entity.has_tag("new_tag")
        assert "new_tag" in entity.tags

        # Test adding duplicate tag (should not duplicate)
        entity.add_tag("initial")
        assert entity.tags.count("initial") == 1

        # Test remove_tag
        entity.remove_tag("initial")
        assert not entity.has_tag("initial")
        assert "initial" not in entity.tags

        # Test has_any_tags
        assert entity.has_any_tags(["new_tag", "missing"])
        assert not entity.has_any_tags(["missing1", "missing2"])

        # Test has_all_tags
        entity.add_tag("another")
        assert entity.has_all_tags(["new_tag", "another"])
        assert not entity.has_all_tags(["new_tag", "missing"])

    def test_linked_entities(self):
        """Test entity linking detection."""
        entity = Entity(
            type="project",
            properties={
                "lead_id": "550e8400-e29b-41d4-a716-446655440000",
                "team_ids": [
                    "550e8400-e29b-41d4-a716-446655440001",
                    "550e8400-e29b-41d4-a716-446655440002",
                ],
                "description": "A great project",
                "invalid_id": "not-a-uuid",
            },
        )

        linked_ids = entity.get_linked_entities()
        assert "550e8400-e29b-41d4-a716-446655440000" in linked_ids
        assert "550e8400-e29b-41d4-a716-446655440001" in linked_ids
        assert "550e8400-e29b-41d4-a716-446655440002" in linked_ids
        assert "not-a-uuid" not in linked_ids
        assert len(linked_ids) == 3


class TestYAMLEntityStorage:
    """Test YAML entity storage functionality."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield YAMLEntityStorage(temp_dir)

    def test_storage_initialization(self, temp_storage):
        """Test storage initialization."""
        assert temp_storage.entities_dir.exists()
        assert temp_storage.entities_dir.is_dir()

    def test_save_and_load_entity(self, temp_storage):
        """Test saving and loading an entity."""
        entity = Entity(
            type="person",
            properties={"name": "Bob", "age": 30},
            tags=["friend"],
            content="Bob is a good friend.",
        )

        # Save entity
        success = temp_storage.save_entity(entity)
        assert success

        # Check file exists
        file_path = temp_storage._entity_file_path(entity.id)
        assert file_path.exists()

        # Load entity
        loaded_entity = temp_storage.load_entity(entity.id)
        assert loaded_entity is not None
        assert loaded_entity.id == entity.id
        assert loaded_entity.type == entity.type
        assert loaded_entity.properties == entity.properties
        assert loaded_entity.tags == entity.tags
        assert loaded_entity.content == entity.content

    def test_delete_entity(self, temp_storage):
        """Test deleting an entity."""
        entity = Entity(type="test", content="To be deleted")

        # Save then delete
        temp_storage.save_entity(entity)
        assert temp_storage.entity_exists(entity.id)

        success = temp_storage.delete_entity(entity.id)
        assert success
        assert not temp_storage.entity_exists(entity.id)

    def test_list_entity_ids(self, temp_storage):
        """Test listing entity IDs."""
        # Initially empty
        assert temp_storage.list_entity_ids() == []

        # Add some entities
        entity1 = Entity(type="test1")
        entity2 = Entity(type="test2")

        temp_storage.save_entity(entity1)
        temp_storage.save_entity(entity2)

        entity_ids = temp_storage.list_entity_ids()
        assert len(entity_ids) == 2
        assert entity1.id in entity_ids
        assert entity2.id in entity_ids

    def test_load_all_entities(self, temp_storage):
        """Test loading all entities."""
        entity1 = Entity(type="type1", content="First entity")
        entity2 = Entity(type="type2", content="Second entity")

        temp_storage.save_entity(entity1)
        temp_storage.save_entity(entity2)

        all_entities = temp_storage.load_all_entities()
        assert len(all_entities) == 2
        assert entity1.id in all_entities
        assert entity2.id in all_entities
        assert all_entities[entity1.id].content == "First entity"
        assert all_entities[entity2.id].content == "Second entity"

    def test_backup_entity(self, temp_storage):
        """Test entity backup functionality."""
        entity = Entity(type="test", content="Important data")
        temp_storage.save_entity(entity)

        success = temp_storage.backup_entity(entity.id)
        assert success

        # Check backup file exists
        backup_files = list(
            temp_storage.entities_dir.glob(f"{entity.id}.yaml.backup_*")
        )
        assert len(backup_files) == 1


class TestGlobalLocalYAMLStorage:
    """Test global/local YAML storage functionality."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage system."""
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch("pathlib.Path.home", return_value=Path(temp_dir) / "home"),
        ):
            yield GlobalLocalYAMLStorage(temp_dir)

    def test_global_local_separation(self, temp_storage):
        """Test that global and local entities are stored separately."""
        global_entity = Entity(type="global_test", content="Global content")
        local_entity = Entity(type="local_test", content="Local content")

        # Save to different scopes
        temp_storage.save_entity(global_entity, "global")
        temp_storage.save_entity(local_entity, "local")

        # Verify scope mappings
        assert temp_storage.get_entity_scope(global_entity.id) == "global"
        assert temp_storage.get_entity_scope(local_entity.id) == "local"

        # Verify both can be loaded
        loaded_global = temp_storage.load_entity(global_entity.id)
        loaded_local = temp_storage.load_entity(local_entity.id)

        assert loaded_global.content == "Global content"
        assert loaded_local.content == "Local content"

    def test_local_precedence(self, temp_storage):
        """Test that local entities take precedence over global."""
        entity_id = "test-precedence-id"

        # Create entities with same ID
        global_entity = Entity(id=entity_id, type="test", content="Global version")
        local_entity = Entity(id=entity_id, type="test", content="Local version")

        # Save global first, then local
        temp_storage.save_entity(global_entity, "global")
        temp_storage.save_entity(local_entity, "local")

        # Load should return local version
        loaded_entity = temp_storage.load_entity(entity_id)
        assert loaded_entity.content == "Local version"
        assert temp_storage.get_entity_scope(entity_id) == "local"

    def test_list_all_entity_ids(self, temp_storage):
        """Test listing IDs from both storages."""
        global_entity = Entity(type="global")
        local_entity = Entity(type="local")

        temp_storage.save_entity(global_entity, "global")
        temp_storage.save_entity(local_entity, "local")

        all_ids = temp_storage.list_all_entity_ids()
        assert len(all_ids) == 2
        assert global_entity.id in all_ids
        assert local_entity.id in all_ids

    def test_scope_mapping_persistence(self, temp_storage):
        """Test that scope mappings persist across instances."""
        entity = Entity(type="test", content="Persistent test")
        temp_storage.save_entity(entity, "global")

        # Create new storage instance
        with patch(
            "pathlib.Path.home",
            return_value=temp_storage.global_storage.storage_dir.parent.parent,
        ):
            new_storage = GlobalLocalYAMLStorage(
                str(temp_storage.local_storage.storage_dir.parent)
            )

        # Should remember the scope
        assert new_storage.get_entity_scope(entity.id) == "global"
        loaded_entity = new_storage.load_entity(entity.id)
        assert loaded_entity.content == "Persistent test"


class TestGenericKnowledgeManager:
    """Test GenericKnowledgeManager functionality."""

    @pytest.fixture
    def temp_manager(self):
        """Create a manager with temporary storage."""
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch("pathlib.Path.home", return_value=Path(temp_dir) / "home"),
        ):
            yield GenericKnowledgeManager(temp_dir)

    def test_manager_initialization(self, temp_manager):
        """Test manager initialization."""
        assert isinstance(temp_manager, GenericKnowledgeManager)
        assert temp_manager.storage is not None
        assert temp_manager.db is not None
        assert temp_manager.semantic_search is not None

    def test_create_entity(self, temp_manager):
        """Test creating an entity."""
        entity_id = temp_manager.create_entity(
            entity_type="person",
            properties={"name": "Charlie", "role": "developer"},
            tags=["team", "backend"],
            content="Charlie is a backend developer.",
            scope="local",
        )

        assert isinstance(entity_id, str)
        assert len(entity_id) == 36

        # Verify entity was created
        entity = temp_manager.get_entity(entity_id)
        assert entity is not None
        assert entity.type == "person"
        assert entity.properties["name"] == "Charlie"
        assert entity.properties["role"] == "developer"
        assert "team" in entity.tags
        assert "backend" in entity.tags
        assert entity.content == "Charlie is a backend developer."

    def test_update_entity(self, temp_manager):
        """Test updating an entity."""
        # Create entity
        entity_id = temp_manager.create_entity(
            "project", {"status": "planning"}, ["active"], "Initial project"
        )

        # Update entity
        success = temp_manager.update_entity(
            entity_id,
            properties={"status": "in_progress", "priority": "high"},
            tags=["active", "urgent"],
            content="Updated project description",
        )
        assert success

        # Verify update
        entity = temp_manager.get_entity(entity_id)
        assert entity.properties["status"] == "in_progress"
        assert entity.properties["priority"] == "high"
        assert set(entity.tags) == {"active", "urgent"}
        assert entity.content == "Updated project description"

    def test_delete_entity(self, temp_manager):
        """Test deleting an entity."""
        entity_id = temp_manager.create_entity("test", content="To be deleted")
        assert temp_manager.get_entity(entity_id) is not None

        success = temp_manager.delete_entity(entity_id)
        assert success
        assert temp_manager.get_entity(entity_id) is None

    def test_list_entities(self, temp_manager):
        """Test listing entities with filtering."""
        # Create test entities
        temp_manager.create_entity("person", {"name": "Alice"}, ["team", "frontend"])
        temp_manager.create_entity("person", {"name": "Bob"}, ["team", "backend"])
        temp_manager.create_entity("project", {"name": "Website"}, ["active"])

        # Test listing all entities
        all_entities = temp_manager.list_entities()
        assert len(all_entities) == 3

        # Test filtering by type
        people = temp_manager.list_entities(entity_type="person")
        assert len(people) == 2
        assert all(e.type == "person" for e in people)

        projects = temp_manager.list_entities(entity_type="project")
        assert len(projects) == 1
        assert projects[0].type == "project"

        # Test filtering by tags
        team_entities = temp_manager.list_entities(tags=["team"])
        assert len(team_entities) == 2

        frontend_entities = temp_manager.list_entities(tags=["frontend"])
        assert len(frontend_entities) == 1

    def test_search_entities_text(self, temp_manager):
        """Test text search across entities."""
        # Create test entities
        temp_manager.create_entity(
            "person",
            {"name": "Alice Developer", "email": "alice@company.com"},
            ["developer"],
            "Alice is a senior developer specializing in frontend work.",
        )
        temp_manager.create_entity(
            "project",
            {"name": "Mobile App", "tech": "React Native"},
            ["mobile", "app"],
            "A mobile application for iOS and Android.",
        )
        temp_manager.create_entity(
            "idea",
            {"title": "AI Assistant"},
            ["ai", "future"],
            "Idea for an AI-powered assistant for developers.",
        )

        # Search by content
        results = temp_manager.search_entities_text("frontend")
        assert len(results) == 1
        assert results[0].properties["name"] == "Alice Developer"

        # Search by property
        results = temp_manager.search_entities_text("React Native")
        assert len(results) == 1
        assert results[0].properties["name"] == "Mobile App"

        # Search by tag
        results = temp_manager.search_entities_text("ai")
        assert len(results) == 1
        assert results[0].properties["title"] == "AI Assistant"

        # Case insensitive search
        results = temp_manager.search_entities_text("MOBILE")
        assert len(results) == 1

    def test_query_entities_jmespath(self, temp_manager):
        """Test JMESPath queries."""
        # Create test entities
        temp_manager.create_entity("person", {"name": "Alice", "age": 30}, ["senior"])
        temp_manager.create_entity("person", {"name": "Bob", "age": 25}, ["junior"])
        temp_manager.create_entity("project", {"name": "Website", "budget": 50000})

        # Query for all person names
        results = temp_manager.query_entities_jmespath(
            "[?type=='person'].properties.name"
        )
        assert len(results) == 2
        assert "Alice" in results
        assert "Bob" in results

        # Query for senior people
        results = temp_manager.query_entities_jmespath("[?contains(tags, 'senior')]")
        assert len(results) == 1
        assert results[0]["properties"]["name"] == "Alice"

    def test_get_entities_by_property(self, temp_manager):
        """Test getting entities by property value."""
        temp_manager.create_entity("person", {"role": "developer", "name": "Alice"})
        temp_manager.create_entity("person", {"role": "designer", "name": "Bob"})
        temp_manager.create_entity("person", {"role": "developer", "name": "Charlie"})

        # Get all developers
        developers = temp_manager.get_entities_by_property("role", "developer")
        assert len(developers) == 2
        developer_names = {e.properties["name"] for e in developers}
        assert developer_names == {"Alice", "Charlie"}

        # Get designers
        designers = temp_manager.get_entities_by_property("role", "designer")
        assert len(designers) == 1
        assert designers[0].properties["name"] == "Bob"

    def test_linked_entities(self, temp_manager):
        """Test entity linking functionality."""
        # Create entities
        alice_id = temp_manager.create_entity("person", {"name": "Alice"})
        bob_id = temp_manager.create_entity("person", {"name": "Bob"})

        project_id = temp_manager.create_entity(
            "project",
            {
                "name": "Team Project",
                "lead_id": alice_id,
                "team_ids": [alice_id, bob_id],
            },
        )

        # Test getting linked entities
        linked_entities = temp_manager.get_linked_entities(project_id)
        assert len(linked_entities) >= 2  # At least Alice and Bob

        linked_names = {e.properties["name"] for e in linked_entities}
        assert "Alice" in linked_names
        assert "Bob" in linked_names

        # Test getting entities linking to Alice
        linking_to_alice = temp_manager.get_entities_linking_to(alice_id)
        assert len(linking_to_alice) == 1
        assert linking_to_alice[0].properties["name"] == "Team Project"

    def test_get_entity_types(self, temp_manager):
        """Test getting unique entity types."""
        temp_manager.create_entity("person", {"name": "Alice"})
        temp_manager.create_entity("project", {"name": "Website"})
        temp_manager.create_entity("idea", {"title": "New Feature"})
        temp_manager.create_entity("person", {"name": "Bob"})  # Duplicate type

        types = temp_manager.get_entity_types()
        assert len(types) == 3
        assert set(types) == {"idea", "person", "project"}  # Should be sorted

    def test_get_all_tags(self, temp_manager):
        """Test getting all unique tags."""
        temp_manager.create_entity("person", tags=["team", "senior"])
        temp_manager.create_entity("project", tags=["active", "urgent"])
        temp_manager.create_entity("idea", tags=["team", "future"])  # Duplicate "team"

        tags = temp_manager.get_all_tags()
        assert len(tags) == 4
        assert set(tags) == {"active", "future", "senior", "team", "urgent"}

    def test_get_stats(self, temp_manager):
        """Test getting knowledge base statistics."""
        # Create test entities in different scopes
        temp_manager.create_entity("person", scope="global")
        temp_manager.create_entity("person", scope="local")
        temp_manager.create_entity("project", scope="local")

        stats = temp_manager.get_stats()

        assert stats["total_entities"] == 3
        assert stats["entity_types"]["person"] == 2
        assert stats["entity_types"]["project"] == 1
        assert stats["scopes"]["global"] == 1
        assert stats["scopes"]["local"] == 2
        assert "semantic_search" in stats
        assert "storage_dirs" in stats

    def test_refresh_from_files(self, temp_manager):
        """Test refreshing from YAML files."""
        # Create entity
        entity_id = temp_manager.create_entity("test", {"value": "original"})

        # Manually modify the YAML file
        entity = temp_manager.get_entity(entity_id)
        entity.properties["value"] = "modified"
        temp_manager.storage.save_entity(entity, "local")

        # Refresh from files
        temp_manager.refresh_from_files()

        # Verify the change is reflected
        updated_entity = temp_manager.get_entity(entity_id)
        assert updated_entity.properties["value"] == "modified"

    def test_scope_operations(self, temp_manager):
        """Test scope-related operations."""
        # Create entities in different scopes
        global_id = temp_manager.create_entity(
            "test", {"scope": "global"}, scope="global"
        )
        local_id = temp_manager.create_entity("test", {"scope": "local"}, scope="local")

        # Verify scopes
        assert temp_manager.get_entity_scope(global_id) == "global"
        assert temp_manager.get_entity_scope(local_id) == "local"

        # Test listing by scope
        global_entities = temp_manager.list_entities(scope="global")
        local_entities = temp_manager.list_entities(scope="local")

        assert len(global_entities) == 1
        assert len(local_entities) == 1
        assert global_entities[0].properties["scope"] == "global"
        assert local_entities[0].properties["scope"] == "local"


@pytest.mark.integration
class TestGenericKnowledgeIntegration:
    """Integration tests for the generic knowledge system."""

    @pytest.fixture
    def real_manager(self):
        """Create a manager with real file system (in temp directory)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield GenericKnowledgeManager(temp_dir)

    def test_persistence_across_sessions(self, real_manager):
        """Test that data persists across manager instances."""
        # Create entity in first session
        entity_id = real_manager.create_entity(
            "persistent_test",
            {"data": "should persist"},
            ["persistence"],
            "This entity should persist across sessions",
        )

        # Get storage directory
        storage_dir = str(real_manager.storage.local_storage.storage_dir.parent)

        # Create new manager instance (simulating restart)
        new_manager = GenericKnowledgeManager(storage_dir)

        # Verify entity exists in new session
        loaded_entity = new_manager.get_entity(entity_id)
        assert loaded_entity is not None
        assert loaded_entity.properties["data"] == "should persist"
        assert "persistence" in loaded_entity.tags

    def test_yaml_file_structure(self, real_manager):
        """Test that YAML files are created with correct structure."""
        entity_id = real_manager.create_entity(
            "yaml_test",
            {"name": "Test Entity", "count": 42},
            ["yaml", "test"],
            "This is a test entity for YAML structure validation.",
        )

        # Check that YAML file exists
        yaml_file = real_manager.storage.local_storage._entity_file_path(entity_id)
        assert yaml_file.exists()

        # Read and verify YAML structure
        from ruamel.yaml import YAML

        yaml = YAML()

        with open(yaml_file) as f:
            data = yaml.load(f)

        assert data["id"] == entity_id
        assert data["type"] == "yaml_test"
        assert data["properties"]["name"] == "Test Entity"
        assert data["properties"]["count"] == 42
        assert "yaml" in data["tags"]
        assert "test" in data["tags"]
        assert data["content"] == "This is a test entity for YAML structure validation."
        assert "created_at" in data
        assert "updated_at" in data

    def test_concurrent_operations(self, real_manager):
        """Test basic concurrent-like operations."""
        # Create multiple entities rapidly
        entity_ids = []
        for i in range(10):
            entity_id = real_manager.create_entity(
                f"type_{i % 3}",  # Mix of 3 different types
                {"index": i, "batch": "concurrent_test"},
                ["batch", f"index_{i}"],
                f"Entity number {i} in concurrent test batch.",
            )
            entity_ids.append(entity_id)

        # Verify all entities were created
        assert len(entity_ids) == 10
        assert len(set(entity_ids)) == 10  # All unique

        # Verify all can be retrieved
        for i, entity_id in enumerate(entity_ids):
            entity = real_manager.get_entity(entity_id)
            assert entity is not None
            assert entity.properties["index"] == i
            assert entity.properties["batch"] == "concurrent_test"

        # Test batch operations
        batch_entities = real_manager.get_entities_by_property(
            "batch", "concurrent_test"
        )
        assert len(batch_entities) == 10
