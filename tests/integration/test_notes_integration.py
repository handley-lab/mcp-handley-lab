"""
Integration tests for the notes system using realistic mock data.

These tests verify end-to-end functionality using a comprehensive dataset
that represents a research lab's knowledge management system.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_handley_lab.notes.manager import NotesManager
from tests.fixtures.notes_fixtures import get_fixture_scopes, get_test_notes_data


class TestNotesIntegrationWithMockData:
    """Integration tests using realistic research lab data."""

    @pytest.fixture
    def populated_manager(self):
        """Create a notes manager populated with realistic test data."""
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "pathlib.Path.home", return_value=Path(temp_dir)
        ):
            # Create fresh manager with isolated storage
            manager = NotesManager(temp_dir + "/local")

            # Load test data
            notes = get_test_notes_data()
            scopes = get_fixture_scopes()

            # Directly save notes to storage to preserve IDs
            for note in notes:
                scope = "global" if note.id in scopes["global"] else "local"

                # Save directly to storage (bypasses UUID generation)
                manager.storage.save_note(note, scope)

                # Sync to in-memory database
                manager._sync_note_to_db(note, scope)

                # Add to semantic search
                manager._get_semantic_search().add_note(note)

            yield manager

    def test_data_loading_and_integrity(self, populated_manager):
        """Test that all mock data loads correctly with proper relationships."""
        # Verify total count
        all_notes = populated_manager.list_notes()
        assert len(all_notes) == 14  # Should match fixture count

        # Verify tag distribution
        stats = populated_manager.get_stats()

        # Count notes by their primary path tags
        person_notes = populated_manager.list_notes(tags=["person"])
        project_notes = populated_manager.list_notes(tags=["project"])
        paper_notes = populated_manager.list_notes(tags=["paper"])
        grant_notes = populated_manager.list_notes(tags=["grant"])
        equipment_notes = populated_manager.list_notes(tags=["equipment"])
        idea_notes = populated_manager.list_notes(tags=["idea"])
        meeting_notes = populated_manager.list_notes(tags=["meeting"])

        assert len(person_notes) == 4
        assert len(project_notes) == 3
        assert len(paper_notes) == 3
        assert len(grant_notes) == 1
        assert len(equipment_notes) == 1
        assert len(idea_notes) == 1
        assert len(meeting_notes) == 1

        # Verify scope distribution
        assert stats["scopes"]["global"] == 5
        assert stats["scopes"]["local"] == 9

    def test_semantic_search_research_scenarios(self, populated_manager):
        """Test semantic search with realistic research queries."""

        # Query 1: Looking for machine learning expertise
        ml_results = populated_manager._search_semantic(
            "machine learning expertise", n_results=5
        )

        # Should find Dr. Sarah Chen (genomics ML) and related projects
        ml_note_ids = [note.id for note in ml_results]
        assert "cbd05128-c5f2-4642-9e11-54b46eef4c8e" in ml_note_ids  # Dr. Sarah Chen

        # Verify similarity scores are reasonable
        assert all(note._similarity_score > 0.3 for note in ml_results)

        # Query 2: Climate modeling research
        climate_results = populated_manager._search_semantic(
            "climate modeling differential equations", n_results=5
        )

        # Should find climate-related content (flexible check)
        [note.id for note in climate_results]
        assert len(climate_results) >= 3
        assert any(
            "climate" in note.tags or "climate" in note.content.lower()
            for note in climate_results
        )

        # Query 3: Funding and grants
        funding_results = populated_manager._search_semantic(
            "research funding grant proposal", n_results=5
        )

        funding_ids = [note.id for note in funding_results]
        assert "da2f1400-fc96-42eb-abea-3ffe81bcafbc" in funding_ids  # NSF Grant

    def test_cross_reference_integrity(self, populated_manager):
        """Test that cross-references between notes work correctly."""

        # Get Neural ODEs project
        neural_odes_project = populated_manager.get_note(
            "9ea1e787-78f2-45e8-8b33-8df0e130beb8"
        )
        assert neural_odes_project is not None

        # Verify supervisor reference
        supervisor_id = neural_odes_project.properties["supervisor"]
        supervisor = populated_manager.get_note(supervisor_id)
        assert supervisor.properties["name"] == "Prof. Michael Johnson"

        # Verify collaborator references
        collaborator_ids = neural_odes_project.properties["collaborators"]
        collaborator = populated_manager.get_note(collaborator_ids[0])
        assert collaborator.properties["name"] == "Dr. Sarah Chen"

        # Verify related papers
        paper_ids = neural_odes_project.properties["related_papers"]
        paper = populated_manager.get_note(paper_ids[0])
        assert "paper" in paper.tags
        assert "neural" in paper.properties["title"].lower()

    def test_complex_jmespath_queries(self, populated_manager):
        """Test complex queries that span multiple note types."""

        # Find all active projects with their team sizes
        active_projects = populated_manager.extract_data(
            "[?contains(tags, 'project') && properties.status=='active'].{title: properties.title, team_size: properties.team_size}"
        )

        assert len(active_projects) >= 1
        for project in active_projects:
            assert "title" in project
            assert "team_size" in project

        # Find all people with machine learning expertise
        ml_experts = populated_manager.extract_data(
            "[?contains(tags, 'person') && contains(properties.expertise || `[]`, 'machine learning')].properties.name"
        )

        assert len(ml_experts) >= 1  # Should find ML experts
        assert "Dr. Sarah Chen" in ml_experts

        # Find published papers by journal
        published_papers = populated_manager.extract_data(
            "[?contains(tags, 'paper') && properties.status=='published'].{title: properties.title, journal: properties.journal}"
        )

        assert len(published_papers) >= 1

    def test_collaborative_network_analysis(self, populated_manager):
        """Test queries that analyze collaboration networks."""

        # Find all projects supervised by Prof. Johnson
        johnson_projects = populated_manager.get_notes_by_property(
            "supervisor", "320bd1c6-850f-4bbf-917e-ff7050723172"
        )

        assert len(johnson_projects) >= 1
        for project in johnson_projects:
            assert "project" in project.tags

        # Find equipment shared across projects
        shared_equipment = populated_manager.extract_data(
            "[?contains(tags, 'equipment') && length(properties.projects_using || `[]`) > `1`]"
        )

        # Should find GPU cluster used by multiple projects
        assert len(shared_equipment) >= 1

        # Find meeting notes about specific projects
        meeting_notes = populated_manager.find(text="neural ODEs")
        meeting_found = any("meeting" in note.tags for note in meeting_notes)
        assert meeting_found

    def test_research_pipeline_tracking(self, populated_manager):
        """Test tracking research from idea to publication."""

        # Find completed projects and their related papers
        completed_projects = populated_manager.list_notes(tags=["project"])

        completed = [
            p for p in completed_projects if p.properties.get("status") == "completed"
        ]

        assert len(completed) >= 1

        # For each completed project, check if there are related papers
        for project in completed:
            if "related_papers" in project.properties:
                paper_ids = project.properties["related_papers"]
                for paper_id in paper_ids:
                    paper = populated_manager.get_note(paper_id)
                    assert "paper" in paper.tags

        # Find funding sources for active research
        active_projects = [
            p for p in completed_projects if p.properties.get("status") == "active"
        ]

        for project in active_projects:
            # Should have funding information
            assert (
                "funding" in project.properties
                or "anticipated_start" in project.properties
            )

    def test_expertise_and_skills_discovery(self, populated_manager):
        """Test finding people by expertise and skills."""

        # Find differential equations experts
        de_experts = populated_manager.find(text="differential equations")
        expert_people = [note for note in de_experts if "person" in note.tags]

        assert len(expert_people) >= 1

        # Find genomics researchers
        genomics_researchers = populated_manager.find(text="genomics")
        genomics_people = [
            note for note in genomics_researchers if "person" in note.tags
        ]

        assert len(genomics_people) >= 1

        # Find students and their advisors
        students = populated_manager.extract_data(
            "[?contains(tags, 'person') && properties.role=='PhD Student']"
        )

        for student in students:
            if "advisor" in student["properties"]:
                advisor_id = student["properties"]["advisor"]
                advisor = populated_manager.get_note(advisor_id)
                assert "person" in advisor.tags
                assert advisor.properties["role"] in [
                    "Principal Investigator",
                    "Department Head",
                ]

    def test_resource_utilization_analysis(self, populated_manager):
        """Test analyzing resource usage across projects."""

        # Find all equipment and what projects use it
        equipment_notes = populated_manager.list_notes(tags=["equipment"])

        for equipment in equipment_notes:
            if "projects_using" in equipment.properties:
                project_ids = equipment.properties["projects_using"]

                # Verify each project reference is valid
                for project_id in project_ids:
                    project = populated_manager.get_note(project_id)
                    assert "project" in project.tags

        # Find grants and their funded projects
        grants = populated_manager.list_notes(tags=["grant"])

        for grant in grants:
            if "funded_projects" in grant.properties:
                project_ids = grant.properties["funded_projects"]

                # Verify funding relationships
                for project_id in project_ids:
                    project = populated_manager.get_note(project_id)
                    assert "project" in project.tags

    def test_publication_and_impact_tracking(self, populated_manager):
        """Test tracking publications and their relationships."""

        # Find all papers and their authors
        papers = populated_manager.list_notes(tags=["paper"])

        for paper in papers:
            authors = paper.properties.get("authors", [])

            # Verify author references are valid
            for author_id in authors:
                if isinstance(author_id, str) and len(author_id) == 36:  # UUID format
                    author = populated_manager.get_note(author_id)
                    assert "person" in author.tags

        # Find papers related to specific projects
        project_papers = populated_manager.extract_data(
            "[?contains(tags, 'paper') && properties.related_project].{title: properties.title, project: properties.related_project}"
        )

        for paper_info in project_papers:
            project = populated_manager.get_note(paper_info["project"])
            assert "project" in project.tags

        # Find papers by publication status
        published_papers = populated_manager.list_notes(tags=["paper"])
        published = [
            p for p in published_papers if p.properties.get("status") == "published"
        ]

        under_review = [
            p for p in published_papers if p.properties.get("status") == "under_review"
        ]

        accepted = [
            p for p in published_papers if p.properties.get("status") == "accepted"
        ]

        # Should have mix of publication statuses
        assert len(published) >= 1
        assert len(under_review) >= 1
        assert len(published) + len(under_review) + len(accepted) == len(papers)

    def test_semantic_clustering_and_similarity(self, populated_manager):
        """Test that semantically similar notes cluster together."""

        # Find notes similar to climate modeling
        climate_notes = populated_manager._search_semantic(
            "climate science atmospheric modeling", n_results=10
        )

        # Should find multiple related items
        assert len(climate_notes) >= 3

        # Check for expected tags in results (path-derived tags)
        tags_found = set()
        for note in climate_notes:
            tags_found.update(note.tags)
        expected_tags = {"person", "project", "paper"}

        # Should find people, projects, and papers related to climate
        assert len(tags_found.intersection(expected_tags)) >= 2

        # Test semantic similarity between related concepts
        ml_notes = populated_manager._search_semantic(
            "deep learning neural networks", n_results=5
        )

        genomics_notes = populated_manager._search_semantic(
            "genomics bioinformatics DNA", n_results=5
        )

        # Should find different but relevant results for each query
        ml_ids = {note.id for note in ml_notes}
        genomics_ids = {note.id for note in genomics_notes}

        # Some overlap expected (interdisciplinary research) but should be distinct
        overlap_ratio = len(ml_ids.intersection(genomics_ids)) / len(ml_ids)
        assert overlap_ratio < 0.8  # Not too much overlap

    def test_data_persistence_and_reload(self, populated_manager):
        """Test that data persists correctly when manager is reloaded."""

        # Get storage directory
        storage_dir = populated_manager.storage.local_storage.storage_dir.parent

        # Record some statistics before reload
        original_stats = populated_manager.get_stats()
        original_notes = populated_manager.list_notes()
        original_note_id = original_notes[0].id

        # Create new manager instance with the same storage directory and home patch
        with patch("pathlib.Path.home", return_value=storage_dir):
            new_manager = NotesManager(str(storage_dir) + "/local")

        # Verify data persisted
        new_stats = new_manager.get_stats()
        assert new_stats["total_notes"] == original_stats["total_notes"]
        # Note: In pure tag-based system, we don't artificially track "types"

        # Verify specific note still exists and is unchanged
        reloaded_note = new_manager.get_note(original_note_id)
        original_note = next(n for n in original_notes if n.id == original_note_id)

        # Note: No more artificial 'type' field in pure tag-based system
        assert reloaded_note.properties == original_note.properties
        assert reloaded_note.tags == original_note.tags
        assert reloaded_note.content == original_note.content
