"""Unit tests for the knowledge management system."""
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp_handley_lab.notes.manager import KnowledgeManager
from mcp_handley_lab.notes.models import (
    KnowledgeEntry,
    PersonEntry,
    ProjectEntry,
    TimeSpan,
)


class TestTimeSpan:
    """Test TimeSpan model functionality."""

    def test_timespan_creation(self):
        """Test creating a TimeSpan."""
        start = date(2020, 1, 1)
        end = date(2023, 12, 31)
        timespan = TimeSpan(start=start, end=end)

        assert timespan.start == start
        assert timespan.end == end

    def test_timespan_no_end(self):
        """Test creating a TimeSpan without end date."""
        start = date(2020, 1, 1)
        timespan = TimeSpan(start=start)

        assert timespan.start == start
        assert timespan.end is None

    def test_is_active_within_range(self):
        """Test checking if timespan is active within date range."""
        timespan = TimeSpan(start=date(2020, 1, 1), end=date(2023, 12, 31))

        assert timespan.is_active(date(2021, 6, 15))  # Within range
        assert not timespan.is_active(date(2019, 12, 31))  # Before start
        assert not timespan.is_active(date(2024, 1, 1))  # After end

    def test_is_active_no_end_date(self):
        """Test checking if timespan is active when no end date."""
        timespan = TimeSpan(start=date(2020, 1, 1))

        assert timespan.is_active(date(2021, 6, 15))  # After start
        assert timespan.is_active(date(2024, 1, 1))  # Way after start
        assert not timespan.is_active(date(2019, 12, 31))  # Before start

    def test_is_active_default_today(self):
        """Test checking if timespan is active using today's date."""
        with patch("mcp_handley_lab.knowledge.models.date") as mock_date:
            mock_date.today.return_value = date(2023, 6, 15)

            timespan = TimeSpan(start=date(2020, 1, 1), end=date(2024, 12, 31))
            assert timespan.is_active()  # Should be active on 2023-06-15


class TestKnowledgeEntry:
    """Test KnowledgeEntry model functionality."""

    def test_knowledge_entry_creation(self):
        """Test creating a basic knowledge entry."""
        entry = KnowledgeEntry(
            type="note",
            name="Test Note",
            data={"content": "This is a test note"},
            tags=["test", "example"],
        )

        assert entry.type == "note"
        assert entry.name == "Test Note"
        assert entry.data["content"] == "This is a test note"
        assert "test" in entry.tags
        assert "example" in entry.tags
        assert isinstance(entry.id, str)
        assert len(entry.id) > 0

    def test_get_set_field(self):
        """Test getting and setting fields."""
        entry = KnowledgeEntry(type="test", name="Test Entry")

        # Test getting non-existent field
        assert entry.get_field("nonexistent") is None
        assert entry.get_field("nonexistent", "default") == "default"

        # Test setting and getting field
        entry.set_field("test_field", "test_value")
        assert entry.get_field("test_field") == "test_value"

    def test_tag_operations(self):
        """Test tag-related operations."""
        entry = KnowledgeEntry(type="test", name="Test Entry", tags=["initial"])

        # Test has_tag
        assert entry.has_tag("initial")
        assert not entry.has_tag("nonexistent")

        # Test add_tag
        entry.add_tag("new_tag")
        assert entry.has_tag("new_tag")
        assert "new_tag" in entry.tags

        # Test adding duplicate tag (should not duplicate)
        entry.add_tag("initial")
        assert entry.tags.count("initial") == 1


class TestPersonEntry:
    """Test PersonEntry specialized functionality."""

    def test_person_entry_creation(self):
        """Test creating a PersonEntry."""
        person = PersonEntry(
            type="person",
            name="John Doe",
            data={
                "email": "john@example.com",
                "roles": [
                    {"role": "phd", "start": "2020-01-01", "end": "2023-12-31"},
                    {"role": "postdoc", "start": "2024-01-01"},
                ],
            },
        )

        assert person.type == "person"
        assert person.name == "John Doe"
        assert person.get_email() == "john@example.com"

    def test_get_roles(self):
        """Test getting roles."""
        person = PersonEntry(
            type="person",
            name="Jane Doe",
            data={
                "roles": [
                    {"role": "phd", "start": "2020-01-01", "end": "2023-12-31"},
                    {"role": "postdoc", "start": "2024-01-01"},
                ]
            },
        )

        roles = person.get_roles()
        assert len(roles) == 2
        assert roles[0]["role"] == "phd"
        assert roles[1]["role"] == "postdoc"

    def test_get_current_roles(self):
        """Test getting current roles."""
        person = PersonEntry(
            type="person",
            name="Current Person",
            data={
                "roles": [
                    {"role": "phd", "start": "2020-01-01", "end": "2023-12-31"},
                    {"role": "postdoc", "start": "2024-01-01"},
                ]
            },
        )

        # Test with specific date during PhD
        current_roles = person.get_current_roles(date(2022, 6, 15))
        assert len(current_roles) == 1
        assert current_roles[0]["role"] == "phd"

        # Test with specific date during postdoc
        current_roles = person.get_current_roles(date(2024, 6, 15))
        assert len(current_roles) == 1
        assert current_roles[0]["role"] == "postdoc"

    def test_was_active(self):
        """Test checking if person was active during a year."""
        person = PersonEntry(
            type="person",
            name="Historic Person",
            data={
                "roles": [
                    {"role": "phd", "start": "2020-01-01", "end": "2023-12-31"},
                    {"role": "postdoc", "start": "2024-01-01", "end": "2025-12-31"},
                ]
            },
        )

        assert person.was_active(2021)  # During PhD
        assert person.was_active(2023)  # End of PhD
        assert person.was_active(2024)  # Start of postdoc
        assert not person.was_active(2019)  # Before all roles
        assert not person.was_active(2026)  # After all roles

    def test_get_supervisors(self):
        """Test getting supervisors."""
        person = PersonEntry(
            type="person",
            name="Student",
            data={"supervisors": ["Prof. Smith", "Dr. Jones"]},
        )

        supervisors = person.get_supervisors()
        assert "Prof. Smith" in supervisors
        assert "Dr. Jones" in supervisors

    def test_get_projects(self):
        """Test getting projects."""
        person = PersonEntry(
            type="person",
            name="Researcher",
            data={"projects": ["Project A", "Project B"]},
        )

        projects = person.get_projects()
        assert "Project A" in projects
        assert "Project B" in projects


class TestProjectEntry:
    """Test ProjectEntry specialized functionality."""

    def test_project_entry_creation(self):
        """Test creating a ProjectEntry."""
        project = ProjectEntry(
            type="project",
            name="Test Project",
            data={
                "start_date": "2023-01-01",
                "end_date": "2024-12-31",
                "participants": ["Alice", "Bob"],
                "status": "active",
            },
        )

        assert project.type == "project"
        assert project.name == "Test Project"

    def test_get_participants(self):
        """Test getting project participants."""
        project = ProjectEntry(
            type="project",
            name="Team Project",
            data={"participants": ["Alice", "Bob", "Charlie"]},
        )

        participants = project.get_participants()
        assert len(participants) == 3
        assert "Alice" in participants
        assert "Bob" in participants
        assert "Charlie" in participants

    def test_get_timespan(self):
        """Test getting project timespan."""
        project = ProjectEntry(
            type="project",
            name="Timed Project",
            data={"start_date": "2023-01-01", "end_date": "2024-12-31"},
        )

        timespan = project.get_timespan()
        assert timespan is not None
        assert timespan.start == date(2023, 1, 1)
        assert timespan.end == date(2024, 12, 31)

    def test_get_timespan_no_dates(self):
        """Test getting timespan when no dates provided."""
        project = ProjectEntry(
            type="project", name="Undated Project", data={"status": "active"}
        )

        timespan = project.get_timespan()
        assert timespan is None

    def test_is_active_by_timespan(self):
        """Test checking if project is active based on timespan."""
        project = ProjectEntry(
            type="project",
            name="Active Project",
            data={"start_date": "2023-01-01", "end_date": "2025-12-31"},
        )

        assert project.is_active(date(2024, 6, 15))  # Within timespan
        assert not project.is_active(date(2022, 12, 31))  # Before start
        assert not project.is_active(date(2026, 1, 1))  # After end

    def test_is_active_by_status(self):
        """Test checking if project is active based on status."""
        project = ProjectEntry(
            type="project", name="Status Project", data={"status": "active"}
        )

        assert project.is_active()  # Active status

        project.data["status"] = "completed"
        assert not project.is_active()  # Completed status


class TestKnowledgeManager:
    """Test KnowledgeManager functionality."""

    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def manager(self, temp_storage, monkeypatch):
        """Create a KnowledgeManager with temporary storage."""
        # Mock home directory to use temp storage for global storage
        monkeypatch.setattr("pathlib.Path.home", lambda: Path(temp_storage) / "home")
        return KnowledgeManager(local_storage_dir=temp_storage)

    def test_manager_initialization(self, manager):
        """Test KnowledgeManager initialization."""
        assert isinstance(manager, KnowledgeManager)
        assert manager.global_knowledge_dir.exists()
        assert manager.local_knowledge_dir.exists()
        assert manager.global_knowledge_file.exists()
        assert manager.local_knowledge_file.exists()

    def test_create_entry(self, manager):
        """Test creating an entry."""
        entry_id = manager.create_entry(
            entry_type="person",
            name="Test Person",
            data={"email": "test@example.com"},
            tags=["test"],
        )

        assert isinstance(entry_id, str)
        assert len(entry_id) > 0

        # Verify entry was created
        entry = manager.get_entry(entry_id)
        assert entry is not None
        assert entry.name == "Test Person"
        assert entry.type == "person"
        assert entry.data["email"] == "test@example.com"
        assert "test" in entry.tags

    def test_update_entry(self, manager):
        """Test updating an entry."""
        # Create entry
        entry_id = manager.create_entry("note", "Test Note", {"content": "original"})

        # Update entry
        success = manager.update_entry(
            entry_id, {"content": "updated", "author": "test"}
        )
        assert success

        # Verify update
        entry = manager.get_entry(entry_id)
        assert entry.data["content"] == "updated"
        assert entry.data["author"] == "test"

    def test_delete_entry(self, manager):
        """Test deleting an entry."""
        # Create entry
        entry_id = manager.create_entry("note", "To Delete")
        assert manager.get_entry(entry_id) is not None

        # Delete entry
        success = manager.delete_entry(entry_id)
        assert success

        # Verify deletion
        assert manager.get_entry(entry_id) is None

    def test_list_entries(self, manager):
        """Test listing entries with filtering."""
        # Create test entries
        manager.create_entry("person", "Person 1", tags=["group1"])
        manager.create_entry("person", "Person 2", tags=["group2"])
        manager.create_entry("project", "Project 1", tags=["group1"])

        # Test listing all entries
        all_entries = manager.list_entries()
        assert len(all_entries) == 3

        # Test filtering by type
        people = manager.list_entries(entry_type="person")
        assert len(people) == 2

        projects = manager.list_entries(entry_type="project")
        assert len(projects) == 1

        # Test filtering by tags
        group1_entries = manager.list_entries(tags=["group1"])
        assert len(group1_entries) == 2

    def test_search_entries(self, manager):
        """Test searching entries."""
        # Create test entries
        manager.create_entry("person", "Alice Smith", {"email": "alice@test.com"})
        manager.create_entry("person", "Bob Jones", {"email": "bob@example.com"})
        manager.create_entry(
            "project", "Machine Learning", {"description": "AI research"}
        )

        # Search by name
        results = manager.search_entries("Alice")
        assert len(results) == 1
        assert results[0].name == "Alice Smith"

        # Search by email domain
        results = manager.search_entries("test.com")
        assert len(results) == 1
        assert results[0].name == "Alice Smith"

        # Search by project description
        results = manager.search_entries("AI")
        assert len(results) == 1
        assert results[0].name == "Machine Learning"

    def test_get_people(self, manager):
        """Test getting people with filtering."""
        # Create test people
        manager.create_entry(
            "person",
            "Current Person",
            {"roles": [{"role": "postdoc", "start": "2023-01-01"}]},
        )
        manager.create_entry(
            "person",
            "Past Person",
            {"roles": [{"role": "phd", "start": "2020-01-01", "end": "2023-12-31"}]},
        )

        # Test getting all people
        all_people = manager.get_people(active_only=False)
        assert len(all_people) == 2

        # Test getting only active people
        active_people = manager.get_people(active_only=True)
        assert len(active_people) == 1
        assert active_people[0].name == "Current Person"

    def test_get_people_by_year(self, manager):
        """Test getting people by year."""
        # Create test people
        manager.create_entry(
            "person",
            "Person 2020-2023",
            {"roles": [{"role": "phd", "start": "2020-01-01", "end": "2023-12-31"}]},
        )
        manager.create_entry(
            "person",
            "Person 2024+",
            {"roles": [{"role": "postdoc", "start": "2024-01-01"}]},
        )

        # Test year 2022 (during first person's PhD)
        people_2022 = manager.get_people_by_year(2022)
        assert len(people_2022) == 1
        assert people_2022[0].name == "Person 2020-2023"

        # Test year 2024 (second person's postdoc)
        people_2024 = manager.get_people_by_year(2024)
        assert len(people_2024) == 1
        assert people_2024[0].name == "Person 2024+"

    def test_get_emails(self, manager):
        """Test getting email addresses."""
        # Create people with emails
        manager.create_entry(
            "person",
            "Person 1",
            {
                "email": "person1@test.com",
                "roles": [{"role": "postdoc", "start": "2023-01-01"}],
            },
        )
        manager.create_entry(
            "person",
            "Person 2",
            {
                "email": "person2@test.com",
                "roles": [{"role": "phd", "start": "2020-01-01", "end": "2022-12-31"}],
            },
        )

        # Test getting all emails
        all_emails = manager.get_emails()
        assert len(all_emails) == 1  # Only active person
        assert "person1@test.com" in all_emails

        # Test getting emails for specific year
        emails_2021 = manager.get_emails(year=2021)
        assert len(emails_2021) == 1
        assert "person2@test.com" in emails_2021

    def test_persistence(self, temp_storage, monkeypatch):
        """Test that data persists between manager instances."""
        # Mock home directory
        monkeypatch.setattr("pathlib.Path.home", lambda: Path(temp_storage) / "home")

        # Create first manager and add data
        manager1 = KnowledgeManager(local_storage_dir=temp_storage)
        entry_id = manager1.create_entry(
            "person", "Persistent Person", {"test": "data"}
        )

        # Create second manager and verify data exists
        manager2 = KnowledgeManager(local_storage_dir=temp_storage)
        entry = manager2.get_entry(entry_id)

        assert entry is not None
        assert entry.name == "Persistent Person"
        assert entry.data["test"] == "data"

    def test_json_serialization(self, manager):
        """Test JSON serialization with dates."""
        # Create entry with date data
        entry_id = manager.create_entry(
            "person",
            "Date Person",
            {"roles": [{"role": "phd", "start": "2020-01-01", "end": "2023-12-31"}]},
        )

        # Verify the entry was saved and loaded correctly
        entry = manager.get_entry(entry_id)
        assert entry is not None

        # Check that dates in roles are properly handled
        roles = entry.get_roles()
        assert len(roles) == 1
        assert roles[0]["start"] == "2020-01-01"
        assert roles[0]["end"] == "2023-12-31"

    def test_global_local_scopes(self, manager):
        """Test creating entries in global and local scopes."""
        # Create global entry
        global_id = manager.create_entry(
            "person", "Global Person", {"email": "global@test.com"}, scope="global"
        )

        # Create local entry
        local_id = manager.create_entry(
            "person", "Local Person", {"email": "local@test.com"}, scope="local"
        )

        # Verify scopes
        assert manager.get_entry_scope(global_id) == "global"
        assert manager.get_entry_scope(local_id) == "local"

        # Verify entries exist
        assert manager.get_entry(global_id) is not None
        assert manager.get_entry(local_id) is not None

    def test_scope_precedence(self, temp_storage, monkeypatch):
        """Test that local entries override global entries with same ID."""
        # Mock home directory
        monkeypatch.setattr("pathlib.Path.home", lambda: Path(temp_storage) / "home")

        # Create first manager and add global entry
        manager1 = KnowledgeManager(local_storage_dir=temp_storage)
        global_entry = manager1.create_entry(
            "person", "Global Name", {"data": "global"}, scope="global"
        )

        # Manually create local entry with same ID to test precedence
        from mcp_handley_lab.notes.models import PersonEntry

        local_entry = PersonEntry(
            id=global_entry,  # Same ID as global entry
            type="person",
            name="Local Name",
            data={"data": "local"},
        )
        manager1._entries[global_entry] = local_entry
        manager1._entry_scopes[global_entry] = "local"
        manager1._save_knowledge_file(manager1.local_knowledge_file, "local")

        # Create new manager and verify local takes precedence
        manager2 = KnowledgeManager(local_storage_dir=temp_storage)
        entry = manager2.get_entry(global_entry)
        assert entry.name == "Local Name"
        assert entry.data["data"] == "local"
        assert manager2.get_entry_scope(global_entry) == "local"

    def test_separate_file_storage(self, manager):
        """Test that global and local entries are stored in separate files."""
        # Create entries in both scopes
        manager.create_entry("note", "Global Note", scope="global")
        manager.create_entry("note", "Local Note", scope="local")

        # Check that files exist and contain appropriate entries
        import json

        # Check global file
        with open(manager.global_knowledge_file) as f:
            global_data = json.load(f)
        global_entries = global_data["entries"]
        assert len(global_entries) == 1
        assert global_entries[0]["name"] == "Global Note"

        # Check local file
        with open(manager.local_knowledge_file) as f:
            local_data = json.load(f)
        local_entries = local_data["entries"]
        assert len(local_entries) == 1
        assert local_entries[0]["name"] == "Local Note"

    def test_scope_validation(self, manager):
        """Test that invalid scopes are rejected."""
        with pytest.raises(ValueError, match="Scope must be 'global' or 'local'"):
            manager.create_entry("note", "Test Note", scope="invalid")

    def test_update_preserves_scope(self, manager):
        """Test that updating an entry preserves its scope."""
        # Create global entry
        global_id = manager.create_entry("note", "Global Note", scope="global")

        # Update the entry
        manager.update_entry(global_id, {"updated": "yes"})

        # Verify scope is preserved
        assert manager.get_entry_scope(global_id) == "global"

        # Verify update worked
        entry = manager.get_entry(global_id)
        assert entry.data["updated"] == "yes"

    def test_delete_removes_from_correct_scope(self, manager):
        """Test that deleting an entry removes it from the correct scope file."""
        # Create entries in both scopes
        global_id = manager.create_entry("note", "Global Note", scope="global")
        manager.create_entry("note", "Local Note", scope="local")

        # Delete global entry
        manager.delete_entry(global_id)

        # Verify global file is empty but local file still has entry
        import json

        with open(manager.global_knowledge_file) as f:
            global_data = json.load(f)
        assert len(global_data["entries"]) == 0

        with open(manager.local_knowledge_file) as f:
            local_data = json.load(f)
        assert len(local_data["entries"]) == 1
        assert local_data["entries"][0]["name"] == "Local Note"
