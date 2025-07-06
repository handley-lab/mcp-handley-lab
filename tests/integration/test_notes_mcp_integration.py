"""
MCP integration tests for the notes system.

These tests verify that the notes MCP tool functions work correctly
when called directly (as Claude Code would call them).
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp_handley_lab.notes.tool import (
    create_note,
    delete_note,
    get_all_tags,
    get_linked_notes,
    get_note,
    get_note_scope,
    get_notes_by_property,
    get_notes_linking_to,
    get_notes_stats,
    list_notes,
    query_notes,
    refresh_notes_database,
    search_notes,
    search_notes_semantic,
    update_note,
)


class TestNotesMcpIntegration:
    """Test notes MCP tool functions with isolated storage."""

    @pytest.fixture
    def isolated_notes_storage(self):
        """Create isolated storage for notes testing."""
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "pathlib.Path.home", return_value=Path(temp_dir)
        ), patch("mcp_handley_lab.notes.tool.get_manager") as mock_get_manager:
            from mcp_handley_lab.notes.manager import NotesManager

            manager = NotesManager(temp_dir + "/local")
            mock_get_manager.return_value = manager
            yield temp_dir

    def test_note_lifecycle_mcp(self, isolated_notes_storage):
        """Test complete note lifecycle through MCP tool functions."""

        # Create a note
        note_id = create_note(
            path="person",
            title="Dr. Test User",
            properties={
                "name": "Dr. Test User",
                "email": "test@example.com",
                "expertise": ["testing", "integration"],
            },
            tags=["test"],
            content="Test person for MCP integration testing.",
            scope="local",
        )

        # Should return a UUID string
        assert isinstance(note_id, str)
        assert len(note_id) == 36  # UUID length

        # Get the note
        note_data = get_note(note_id=note_id)
        assert "person" in note_data["tags"]
        assert note_data["properties"]["name"] == "Dr. Test User"
        assert "testing" in note_data["properties"]["expertise"]
        assert "test" in note_data["tags"]

        # Update the note
        update_result = update_note(
            note_id=note_id,
            properties={"name": "Dr. Updated User", "role": "Senior Researcher"},
            tags=["test", "updated"],
            content="Updated content for testing.",
        )

        assert "updated successfully" in update_result.lower()

        # Verify update
        updated_note = get_note(note_id=note_id)
        assert updated_note["properties"]["name"] == "Dr. Updated User"
        assert updated_note["properties"]["role"] == "Senior Researcher"
        assert "updated" in updated_note["tags"]
        assert "person" in updated_note["tags"]
        assert updated_note["content"] == "Updated content for testing."

        # Delete the note
        delete_result = delete_note(note_id=note_id)
        assert delete_result is True

        # Verify deletion
        deleted_note = get_note(note_id=note_id)
        assert deleted_note is None

    def test_list_and_search_mcp(self, isolated_notes_storage):
        """Test listing and searching notes through MCP."""

        # Create test notes
        create_note(
            path="project",
            title="Machine Learning Research",
            properties={"title": "Machine Learning Research", "status": "active"},
            tags=["ml", "research", "active"],
            content="Developing new ML algorithms for data analysis.",
            scope="local",
        )

        create_note(
            path="paper",
            title="Neural Networks in Biology",
            properties={"title": "Neural Networks in Biology", "status": "published"},
            tags=["ml", "biology", "published"],
            content="Research paper on applying neural networks to biological data.",
            scope="global",
        )

        # List all notes
        all_notes = list_notes()
        assert len(all_notes) >= 2

        # List by tags
        projects = list_notes(tags=["project"])
        assert len(projects) == 1
        assert "project" in projects[0]["tags"]

        papers = list_notes(tags=["paper"])
        assert len(papers) == 1
        assert "paper" in papers[0]["tags"]

        # List by tags
        ml_notes = list_notes(tags=["ml"])
        assert len(ml_notes) == 2

        # List by scope
        local_notes = list_notes(scope="local")
        assert len(local_notes) >= 1

        global_notes = list_notes(scope="global")
        assert len(global_notes) >= 1

        # Text search
        search_results = search_notes(query="machine learning")
        assert len(search_results) >= 1

        neural_search = search_notes(query="neural networks")
        assert len(neural_search) >= 1

    def test_semantic_search_mcp(self, isolated_notes_storage):
        """Test semantic search through MCP (if ChromaDB available)."""

        # Create semantically related notes
        create_note(
            path="idea",
            title="Deep Learning for Climate",
            properties={"concept": "Deep Learning for Climate"},
            tags=["ai", "climate", "research"],
            content="Using deep neural networks to model climate change patterns and predict future scenarios.",
            scope="local",
        )

        create_note(
            path="project",
            title="Weather Prediction AI",
            properties={"title": "Weather Prediction AI"},
            tags=["ai", "weather", "prediction"],
            content="Machine learning system for accurate weather forecasting using atmospheric data.",
            scope="local",
        )

        try:
            # Test semantic search
            climate_results = search_notes_semantic(
                query="artificial intelligence weather climate", n_results=5
            )

            # Should find both related notes
            assert len(climate_results) >= 2

            # Results should have similarity scores
            for result in climate_results:
                assert "similarity_score" in result
                assert isinstance(result["similarity_score"], float)
                assert 0.0 <= result["similarity_score"] <= 1.0

        except Exception as e:
            if "chromadb" in str(e).lower():
                pytest.skip("ChromaDB not available for semantic search testing")
            else:
                raise

    def test_jmespath_queries_mcp(self, isolated_notes_storage):
        """Test JMESPath queries through MCP."""

        # Create structured test data
        create_note(
            path="person",
            title="Dr. Alice Smith",
            properties={
                "name": "Dr. Alice Smith",
                "role": "Principal Investigator",
                "expertise": ["machine learning", "data science"],
            },
            tags=["researcher"],
            content="Leading researcher in ML and data science.",
        )

        create_note(
            path="person",
            title="Bob Johnson",
            properties={
                "name": "Bob Johnson",
                "role": "PhD Student",
                "advisor": "Dr. Alice Smith",
            },
            tags=["student"],
            content="PhD student working on deep learning.",
        )

        # Query all people
        people = query_notes(
            jmespath_query="[?contains(tags, 'person')].properties.name"
        )
        assert len(people) >= 2
        assert "Dr. Alice Smith" in people
        assert "Bob Johnson" in people

        # Query researchers only
        researchers = query_notes(
            jmespath_query="[?contains(tags, 'person') && properties.role=='Principal Investigator']"
        )
        assert len(researchers) >= 1
        assert researchers[0]["properties"]["name"] == "Dr. Alice Smith"

        # Query by expertise
        ml_experts = query_notes(
            jmespath_query="[?contains(tags, 'person') && contains(properties.expertise || `[]`, 'machine learning')].properties.name"
        )
        assert "Dr. Alice Smith" in ml_experts

    def test_property_based_queries_mcp(self, isolated_notes_storage):
        """Test property-based queries through MCP."""

        # Create notes with specific properties
        create_note(
            path="project",
            title="Active Project",
            properties={"status": "active", "funding": "NSF Grant 12345"},
            tags=[],
            content="Active research project.",
        )

        create_note(
            path="project",
            title="Completed Project",
            properties={"status": "completed", "funding": "NSF Grant 12345"},
            tags=[],
            content="Completed research project.",
        )

        # Search by property value
        active_projects = get_notes_by_property(
            property_name="status", property_value="active"
        )
        assert len(active_projects) >= 1
        assert active_projects[0]["properties"]["status"] == "active"

        # Search by funding source
        nsf_projects = get_notes_by_property(
            property_name="funding", property_value="NSF Grant 12345"
        )
        assert len(nsf_projects) >= 2

    def test_cross_references_mcp(self, isolated_notes_storage):
        """Test cross-reference functionality through MCP."""

        # Create a person note
        person_id = create_note(
            path="person",
            title="Dr. Cross Reference",
            properties={"name": "Dr. Cross Reference"},
            content="Person for testing cross-references.",
        )

        # Create a project that references the person
        project_id = create_note(
            path="project",
            title="Referenced Project",
            properties={
                "title": "Referenced Project",
                "lead": person_id,  # Cross-reference
            },
            content=f"Project led by [[{person_id}]].",  # Content reference
        )

        # Test linked notes (what this note links to)
        linked = get_linked_notes(note_id=project_id)
        linked_ids = [note["id"] for note in linked]
        assert person_id in linked_ids

        # Test notes linking to (what links to this note)
        linking_to = get_notes_linking_to(target_note_id=person_id)
        linking_ids = [note["id"] for note in linking_to]
        assert project_id in linking_ids

    def test_metadata_functions_mcp(self, isolated_notes_storage):
        """Test metadata and stats functions through MCP."""

        # Create diverse notes
        create_note(
            path="person",
            title="AI Researcher",
            tags=["researcher", "ml"],
            content="AI researcher.",
        )
        create_note(
            path="project",
            title="ML Project",
            tags=["ml", "active"],
            content="ML project.",
        )
        create_note(
            path="paper",
            title="ML Paper",
            tags=["published", "ml"],
            content="ML paper.",
        )

        # Test stats
        stats = get_notes_stats()
        assert "total_notes" in stats
        assert "scopes" in stats
        assert stats["total_notes"] >= 3

        # Test all tags
        tags = get_all_tags()
        assert "ml" in tags
        assert "researcher" in tags
        assert "active" in tags
        assert "published" in tags

    def test_scope_management_mcp(self, isolated_notes_storage):
        """Test scope management through MCP."""

        # Create global note
        global_id = create_note(
            path="person",
            title="Global Person",
            properties={"name": "Global Person"},
            scope="global",
        )

        # Create local note
        local_id = create_note(
            path="person",
            title="Local Person",
            properties={"name": "Local Person"},
            scope="local",
        )

        # Test scope retrieval
        global_scope = get_note_scope(note_id=global_id)
        assert global_scope == "global"

        local_scope = get_note_scope(note_id=local_id)
        assert local_scope == "local"

        # Test scope filtering
        global_notes = list_notes(scope="global")
        global_ids = [note["id"] for note in global_notes]
        assert global_id in global_ids

        local_notes = list_notes(scope="local")
        local_ids = [note["id"] for note in local_notes]
        assert local_id in local_ids

    def test_database_refresh_mcp(self, isolated_notes_storage):
        """Test database refresh functionality through MCP."""

        # Create a note
        create_note(
            path="test",
            title="Refresh Test",
            properties={"refresh_test": True},
            content="Test note for refresh functionality.",
        )

        # Refresh the database
        refresh_result = refresh_notes_database()
        assert "refreshed" in refresh_result.lower()

        # Verify note still exists after refresh
        test_notes = list_notes(tags=["test"])
        assert len(test_notes) >= 1

        refresh_note = None
        for note in test_notes:
            if note["properties"].get("refresh_test"):
                refresh_note = note
                break

        assert refresh_note is not None
        assert refresh_note["content"] == "Test note for refresh functionality."

    def test_error_handling_mcp(self, isolated_notes_storage):
        """Test error handling in MCP functions."""

        # Test getting non-existent note
        result = get_note(note_id="non-existent-id")
        assert result is None

        # Test deleting non-existent note
        delete_result = delete_note(note_id="non-existent-id")
        assert delete_result is False

        # Test updating non-existent note
        try:
            update_note(note_id="non-existent-id", properties={"test": "value"})
            raise AssertionError("Should have raised an error")
        except ValueError as e:
            assert "not found" in str(e).lower()

        # Test invalid scope
        try:
            create_note(path="test", title="Test", scope="invalid_scope")
            raise AssertionError("Should have raised an error")
        except ValueError as e:
            assert "scope" in str(e).lower()
