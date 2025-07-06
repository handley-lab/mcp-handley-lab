"""Comprehensive tests for the notes management system."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp_handley_lab.notes.manager import NotesManager
from mcp_handley_lab.notes.models import Note
from mcp_handley_lab.notes.storage import GlobalLocalYAMLStorage, YAMLNoteStorage


class TestNote:
    """Test Note model functionality."""

    def test_entity_creation(self):
        """Test creating a basic note."""
        note = Note(
            type="person",
            properties={"name": "Alice", "email": "alice@example.com"},
            tags=["contact", "researcher"],
            content="Alice is a researcher working on AI.",
        )

        assert note.type == "person"
        assert note.properties["name"] == "Alice"
        assert note.properties["email"] == "alice@example.com"
        assert "contact" in note.tags
        assert "researcher" in note.tags
        assert note.content == "Alice is a researcher working on AI."
        assert isinstance(note.id, str)
        assert len(note.id) == 36  # UUID format

    def test_property_operations(self):
        """Test property get/set operations."""
        note = Note(type="test")

        # Test getting non-existent property
        assert note.get_property("nonexistent") is None
        assert note.get_property("nonexistent", "default") == "default"

        # Test setting and getting property
        note.set_property("test_prop", "test_value")
        assert note.get_property("test_prop") == "test_value"
        assert note.properties["test_prop"] == "test_value"

    def test_tag_operations(self):
        """Test tag-related operations."""
        note = Note(type="test", tags=["initial"])

        # Test has_tag
        assert note.has_tag("initial")
        assert not note.has_tag("nonexistent")

        # Test add_tag
        note.add_tag("new_tag")
        assert note.has_tag("new_tag")
        assert "new_tag" in note.tags

        # Test adding duplicate tag (should not duplicate)
        note.add_tag("initial")
        assert note.tags.count("initial") == 1

        # Test remove_tag
        note.remove_tag("initial")
        assert not note.has_tag("initial")
        assert "initial" not in note.tags

        # Test has_any_tags
        assert note.has_any_tags(["new_tag", "missing"])
        assert not note.has_any_tags(["missing1", "missing2"])

        # Test has_all_tags
        note.add_tag("another")
        assert note.has_all_tags(["new_tag", "another"])
        assert not note.has_all_tags(["new_tag", "missing"])

    def test_linked_entities(self):
        """Test note linking detection."""
        note = Note(
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

        linked_ids = note.get_linked_entities()
        assert "550e8400-e29b-41d4-a716-446655440000" in linked_ids
        assert "550e8400-e29b-41d4-a716-446655440001" in linked_ids
        assert "550e8400-e29b-41d4-a716-446655440002" in linked_ids
        assert "not-a-uuid" not in linked_ids
        assert len(linked_ids) == 3


class TestYAMLNoteStorage:
    """Test YAML note storage functionality."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield YAMLNoteStorage(temp_dir)

    def test_storage_initialization(self, temp_storage):
        """Test storage initialization."""
        assert temp_storage.entities_dir.exists()
        assert temp_storage.entities_dir.is_dir()

    def test_save_and_load_entity(self, temp_storage):
        """Test saving and loading an note."""
        note = Note(
            type="person",
            properties={"name": "Bob", "age": 30},
            tags=["friend"],
            content="Bob is a good friend.",
        )

        # Save note
        temp_storage.save_note(note)

        # Check file exists
        file_path = temp_storage._entity_file_path(note.id)
        assert file_path.exists()

        # Load note
        loaded_entity = temp_storage.load_entity(note.id)
        assert loaded_entity is not None
        assert loaded_entity.id == note.id
        assert loaded_entity.type == note.type
        assert loaded_entity.properties == note.properties
        assert loaded_entity.tags == note.tags
        assert loaded_entity.content == note.content

    def test_delete_note(self, temp_storage):
        """Test deleting an note."""
        note = Note(type="test", content="To be deleted")

        # Save then delete
        temp_storage.save_note(note)
        assert temp_storage.entity_exists(note.id)

        success = temp_storage.delete_note(note.id)
        assert success
        assert not temp_storage.entity_exists(note.id)

    def test_list_entity_ids(self, temp_storage):
        """Test listing note IDs."""
        # Initially empty
        assert temp_storage.list_entity_ids() == []

        # Add some notes
        entity1 = Note(type="test1")
        entity2 = Note(type="test2")

        temp_storage.save_note(entity1)
        temp_storage.save_note(entity2)

        entity_ids = temp_storage.list_entity_ids()
        assert len(entity_ids) == 2
        assert entity1.id in entity_ids
        assert entity2.id in entity_ids

    def test_load_all_entities(self, temp_storage):
        """Test loading all notes."""
        entity1 = Note(type="type1", content="First note")
        entity2 = Note(type="type2", content="Second note")

        temp_storage.save_note(entity1)
        temp_storage.save_note(entity2)

        all_entities = temp_storage.load_all_entities()
        assert len(all_entities) == 2
        assert entity1.id in all_entities
        assert entity2.id in all_entities
        assert all_entities[entity1.id].content == "First note"
        assert all_entities[entity2.id].content == "Second note"

    def test_backup_entity(self, temp_storage):
        """Test note backup functionality."""
        note = Note(type="test", content="Important data")
        temp_storage.save_note(note)

        success = temp_storage.backup_entity(note.id)
        assert success

        # Check backup file exists
        backup_files = list(temp_storage.entities_dir.glob(f"{note.id}.yaml.backup_*"))
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
        """Test that global and local notes are stored separately."""
        global_entity = Note(type="global_test", content="Global content")
        local_entity = Note(type="local_test", content="Local content")

        # Save to different scopes
        temp_storage.save_note(global_entity, "global")
        temp_storage.save_note(local_entity, "local")

        # Verify scope mappings
        assert temp_storage.get_note_scope(global_entity.id) == "global"
        assert temp_storage.get_note_scope(local_entity.id) == "local"

        # Verify both can be loaded
        loaded_global = temp_storage.load_entity(global_entity.id)
        loaded_local = temp_storage.load_entity(local_entity.id)

        assert loaded_global.content == "Global content"
        assert loaded_local.content == "Local content"

    def test_local_precedence(self, temp_storage):
        """Test that local notes take precedence over global."""
        entity_id = "test-precedence-id"

        # Create notes with same ID
        global_entity = Note(id=entity_id, type="test", content="Global version")
        local_entity = Note(id=entity_id, type="test", content="Local version")

        # Save global first, then local
        temp_storage.save_note(global_entity, "global")
        temp_storage.save_note(local_entity, "local")

        # Load should return local version
        loaded_entity = temp_storage.load_entity(entity_id)
        assert loaded_entity.content == "Local version"
        assert temp_storage.get_note_scope(entity_id) == "local"

    def test_list_all_entity_ids(self, temp_storage):
        """Test listing IDs from both storages."""
        global_entity = Note(type="global")
        local_entity = Note(type="local")

        temp_storage.save_note(global_entity, "global")
        temp_storage.save_note(local_entity, "local")

        all_ids = temp_storage.list_all_entity_ids()
        assert len(all_ids) == 2
        assert global_entity.id in all_ids
        assert local_entity.id in all_ids

    def test_scope_mapping_persistence(self, temp_storage):
        """Test that scope mappings persist across instances."""
        note = Note(type="test", content="Persistent test")
        temp_storage.save_note(note, "global")

        # Create new storage instance
        with patch(
            "pathlib.Path.home",
            return_value=temp_storage.global_storage.storage_dir.parent.parent,
        ):
            new_storage = GlobalLocalYAMLStorage(
                str(temp_storage.local_storage.storage_dir.parent)
            )

        # Should remember the scope
        assert new_storage.get_note_scope(note.id) == "global"
        loaded_entity = new_storage.load_entity(note.id)
        assert loaded_entity.content == "Persistent test"


class TestNotesManager:
    """Test NotesManager functionality."""

    @pytest.fixture
    def temp_manager(self):
        """Create a manager with temporary storage."""
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch("pathlib.Path.home", return_value=Path(temp_dir) / "home"),
        ):
            yield NotesManager(temp_dir)

    def test_manager_initialization(self, temp_manager):
        """Test manager initialization."""
        assert isinstance(temp_manager, NotesManager)
        assert temp_manager.storage is not None
        assert temp_manager.db is not None
        assert temp_manager.semantic_search is not None

    def test_create_note(self, temp_manager):
        """Test creating an note."""
        entity_id = temp_manager.create_note(
            note_type="person",
            properties={"name": "Charlie", "role": "developer"},
            tags=["team", "backend"],
            content="Charlie is a backend developer.",
            scope="local",
        )

        assert isinstance(entity_id, str)
        assert len(entity_id) == 36

        # Verify note was created
        note = temp_manager.get_note(entity_id)
        assert note is not None
        assert note.type == "person"
        assert note.properties["name"] == "Charlie"
        assert note.properties["role"] == "developer"
        assert "team" in note.tags
        assert "backend" in note.tags
        assert note.content == "Charlie is a backend developer."

    def test_update_note(self, temp_manager):
        """Test updating an note."""
        # Create note
        entity_id = temp_manager.create_note(
            "project", {"status": "planning"}, ["active"], "Initial project"
        )

        # Update note
        temp_manager.update_note(
            entity_id,
            properties={"status": "in_progress", "priority": "high"},
            tags=["active", "urgent"],
            content="Updated project description",
        )

        # Verify update
        note = temp_manager.get_note(entity_id)
        assert note.properties["status"] == "in_progress"
        assert note.properties["priority"] == "high"
        assert set(note.tags) == {"active", "urgent"}
        assert note.content == "Updated project description"

    def test_delete_note(self, temp_manager):
        """Test deleting an note."""
        entity_id = temp_manager.create_note("test", content="To be deleted")
        assert temp_manager.get_note(entity_id) is not None

        success = temp_manager.delete_note(entity_id)
        assert success
        assert temp_manager.get_note(entity_id) is None

    def test_list_entities(self, temp_manager):
        """Test listing notes with filtering."""
        # Create test notes
        temp_manager.create_note("person", {"name": "Alice"}, ["team", "frontend"])
        temp_manager.create_note("person", {"name": "Bob"}, ["team", "backend"])
        temp_manager.create_note("project", {"name": "Website"}, ["active"])

        # Test listing all notes
        all_entities = temp_manager.list_entities()
        assert len(all_entities) == 3

        # Test filtering by type
        people = temp_manager.list_entities(note_type="person")
        assert len(people) == 2
        assert all(e.type == "person" for e in people)

        projects = temp_manager.list_entities(note_type="project")
        assert len(projects) == 1
        assert projects[0].type == "project"

        # Test filtering by tags
        team_entities = temp_manager.list_entities(tags=["team"])
        assert len(team_entities) == 2

        frontend_entities = temp_manager.list_entities(tags=["frontend"])
        assert len(frontend_entities) == 1

    def test_search_entities_text(self, temp_manager):
        """Test text search across notes."""
        # Create test notes
        temp_manager.create_note(
            "person",
            {"name": "Alice Developer", "email": "alice@company.com"},
            ["developer"],
            "Alice is a senior developer specializing in frontend work.",
        )
        temp_manager.create_note(
            "project",
            {"name": "Mobile App", "tech": "React Native"},
            ["mobile", "app"],
            "A mobile application for iOS and Android.",
        )
        temp_manager.create_note(
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
        # Create test notes
        temp_manager.create_note("person", {"name": "Alice", "age": 30}, ["senior"])
        temp_manager.create_note("person", {"name": "Bob", "age": 25}, ["junior"])
        temp_manager.create_note("project", {"name": "Website", "budget": 50000})

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
        """Test getting notes by property value."""
        temp_manager.create_note("person", {"role": "developer", "name": "Alice"})
        temp_manager.create_note("person", {"role": "designer", "name": "Bob"})
        temp_manager.create_note("person", {"role": "developer", "name": "Charlie"})

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
        """Test note linking functionality."""
        # Create notes
        alice_id = temp_manager.create_note("person", {"name": "Alice"})
        bob_id = temp_manager.create_note("person", {"name": "Bob"})

        project_id = temp_manager.create_note(
            "project",
            {
                "name": "Team Project",
                "lead_id": alice_id,
                "team_ids": [alice_id, bob_id],
            },
        )

        # Test getting linked notes
        linked_entities = temp_manager.get_linked_entities(project_id)
        assert len(linked_entities) >= 2  # At least Alice and Bob

        linked_names = {e.properties["name"] for e in linked_entities}
        assert "Alice" in linked_names
        assert "Bob" in linked_names

        # Test getting notes linking to Alice
        linking_to_alice = temp_manager.get_entities_linking_to(alice_id)
        assert len(linking_to_alice) == 1
        assert linking_to_alice[0].properties["name"] == "Team Project"

    def test_get_note_types(self, temp_manager):
        """Test getting unique note types."""
        temp_manager.create_note("person", {"name": "Alice"})
        temp_manager.create_note("project", {"name": "Website"})
        temp_manager.create_note("idea", {"title": "New Feature"})
        temp_manager.create_note("person", {"name": "Bob"})  # Duplicate type

        types = temp_manager.get_note_types()
        assert len(types) == 3
        assert set(types) == {"idea", "person", "project"}  # Should be sorted

    def test_get_all_tags(self, temp_manager):
        """Test getting all unique tags."""
        temp_manager.create_note("person", tags=["team", "senior"])
        temp_manager.create_note("project", tags=["active", "urgent"])
        temp_manager.create_note("idea", tags=["team", "future"])  # Duplicate "team"

        tags = temp_manager.get_all_tags()
        assert len(tags) == 5
        assert set(tags) == {"active", "future", "senior", "team", "urgent"}

    def test_get_stats(self, temp_manager):
        """Test getting notes database statistics."""
        # Create test notes in different scopes
        temp_manager.create_note("person", scope="global")
        temp_manager.create_note("person", scope="local")
        temp_manager.create_note("project", scope="local")

        stats = temp_manager.get_stats()

        assert stats["total_entities"] == 3
        assert stats["note_types"]["person"] == 2
        assert stats["note_types"]["project"] == 1
        assert stats["scopes"]["global"] == 1
        assert stats["scopes"]["local"] == 2
        assert "semantic_search" in stats
        assert "storage_dirs" in stats

    def test_refresh_from_files(self, temp_manager):
        """Test refreshing from YAML files."""
        # Create note
        entity_id = temp_manager.create_note("test", {"value": "original"})

        # Manually modify the YAML file
        note = temp_manager.get_note(entity_id)
        note.properties["value"] = "modified"
        temp_manager.storage.save_note(note, "local")

        # Refresh from files
        temp_manager.refresh_from_files()

        # Verify the change is reflected
        updated_entity = temp_manager.get_note(entity_id)
        assert updated_entity.properties["value"] == "modified"

    def test_scope_operations(self, temp_manager):
        """Test scope-related operations."""
        # Create notes in different scopes
        global_id = temp_manager.create_note(
            "test", {"scope": "global"}, scope="global"
        )
        local_id = temp_manager.create_note("test", {"scope": "local"}, scope="local")

        # Verify scopes
        assert temp_manager.get_note_scope(global_id) == "global"
        assert temp_manager.get_note_scope(local_id) == "local"

        # Test listing by scope
        global_entities = temp_manager.list_entities(scope="global")
        local_entities = temp_manager.list_entities(scope="local")

        assert len(global_entities) == 1
        assert len(local_entities) == 1
        assert global_entities[0].properties["scope"] == "global"
        assert local_entities[0].properties["scope"] == "local"


@pytest.mark.integration
class TestNotesIntegration:
    """Integration tests for the notes system."""

    @pytest.fixture
    def real_manager(self):
        """Create a manager with real file system (in temp directory)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield NotesManager(temp_dir)

    def test_persistence_across_sessions(self, real_manager):
        """Test that data persists across manager instances."""
        # Create note in first session
        entity_id = real_manager.create_note(
            "persistent_test",
            {"data": "should persist"},
            ["persistence"],
            "This note should persist across sessions",
        )

        # Get storage directory
        storage_dir = str(real_manager.storage.local_storage.storage_dir.parent)

        # Create new manager instance (simulating restart)
        new_manager = NotesManager(storage_dir)

        # Verify note exists in new session
        loaded_entity = new_manager.get_note(entity_id)
        assert loaded_entity is not None
        assert loaded_entity.properties["data"] == "should persist"
        assert "persistence" in loaded_entity.tags

    def test_yaml_file_structure(self, real_manager):
        """Test that YAML files are created with correct structure."""
        entity_id = real_manager.create_note(
            "yaml_test",
            {"name": "Test Note", "count": 42},
            ["yaml", "test"],
            "This is a test note for YAML structure validation.",
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
        assert data["properties"]["name"] == "Test Note"
        assert data["properties"]["count"] == 42
        assert "yaml" in data["tags"]
        assert "test" in data["tags"]
        assert data["content"] == "This is a test note for YAML structure validation."
        assert "created_at" in data
        assert "updated_at" in data

    def test_concurrent_operations(self, real_manager):
        """Test basic concurrent-like operations."""
        # Create multiple notes rapidly
        entity_ids = []
        for i in range(10):
            entity_id = real_manager.create_note(
                f"type_{i % 3}",  # Mix of 3 different types
                {"index": i, "batch": "concurrent_test"},
                ["batch", f"index_{i}"],
                f"Note number {i} in concurrent test batch.",
            )
            entity_ids.append(entity_id)

        # Verify all notes were created
        assert len(entity_ids) == 10
        assert len(set(entity_ids)) == 10  # All unique

        # Verify all can be retrieved
        for i, entity_id in enumerate(entity_ids):
            note = real_manager.get_note(entity_id)
            assert note is not None
            assert note.properties["index"] == i
            assert note.properties["batch"] == "concurrent_test"

        # Test batch operations
        batch_entities = real_manager.get_entities_by_property(
            "batch", "concurrent_test"
        )
        assert len(batch_entities) == 10
