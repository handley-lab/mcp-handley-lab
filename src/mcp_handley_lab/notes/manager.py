"""Generic notes manager with YAML storage and TinyDB queries."""
from datetime import datetime
from typing import Any

import jmespath
from tinydb import Query, TinyDB
from tinydb.storages import MemoryStorage

from .models import Note
from .semantic_search import SemanticSearchManager
from .storage import GlobalLocalYAMLStorage


class NotesManager:
    """Generic notes management with YAML files and TinyDB queries."""

    def __init__(self, local_storage_dir: str = ".mcp_handley_lab"):
        self.storage = GlobalLocalYAMLStorage(local_storage_dir)
        self.db = TinyDB(storage=MemoryStorage)
        self._semantic_search: SemanticSearchManager | None = None
        self._semantic_storage_dir = local_storage_dir + "/notes"
        self._load_notes_to_db()

    def _get_semantic_search(self) -> SemanticSearchManager:
        """Lazy-load semantic search manager to avoid startup delays."""
        if self._semantic_search is None:
            print("Initializing semantic search (ChromaDB) for the first time...")
            self._semantic_search = SemanticSearchManager(self._semantic_storage_dir)
            notes = list(self.storage.load_all_notes().values())
            self._semantic_search.rebuild_index(notes)
            print(f"Semantic search initialized with {len(notes)} notes.")
        return self._semantic_search

    def _load_notes_to_db(self):
        """Load all notes from YAML files into TinyDB for fast queries."""
        self.db.truncate()
        notes = self.storage.load_all_notes()

        for note_id, note in notes.items():
            doc = note.model_dump()
            doc["_note_id"] = note_id
            doc["_scope"] = self.storage.get_note_scope(note_id)
            self.db.insert(doc)

    def _sync_note_to_db(self, note: Note, scope: str):
        """Sync a single note to the in-memory database."""
        doc = note.model_dump()
        doc["_note_id"] = note.id
        doc["_scope"] = scope

        if self.db.search(Query()._note_id == note.id):
            self.db.update(doc, Query()._note_id == note.id)
        else:
            self.db.insert(doc)

    def _generate_slug(self, title: str) -> str:
        """Generate a URL-friendly slug from title."""
        import re

        slug = re.sub(r"[^a-z0-9]+", "-", title.lower())
        slug = slug.strip("-")
        return slug

    def _ensure_unique_slug(self, path: str, base_slug: str, scope: str) -> str:
        """Ensure slug is unique within the given path and scope."""
        slug = base_slug
        counter = 1

        while True:
            existing = self.storage.load_note_by_slug(path, slug)
            if not existing:
                return slug

            counter += 1
            slug = f"{base_slug}-{counter}"

    def create_note(
        self,
        path: str,
        title: str,
        properties: dict[str, Any] = None,
        tags: list[str] = None,
        content: str = "",
        scope: str = "local",
        slug: str = None,
    ) -> str:
        """Create a new note.

        Args:
            path: Directory path for the note (e.g., 'person', 'person/researcher/phd')
            title: Human-readable title
            properties: Additional structured properties
            tags: List of tags for categorization
            content: Unstructured content
            scope: 'global' or 'local' storage
            slug: Custom slug (auto-generated from title if not provided)
        """
        note = Note(
            title=title,
            properties=properties or {},
            tags=tags or [],
            content=content,
        )

        if not slug:
            slug = self._generate_slug(title)

        slug = self._ensure_unique_slug(path, slug, scope)

        self.storage.save_note(note, scope, path, slug)
        self._sync_note_to_db(note, scope)
        if self._semantic_search is not None:
            self._semantic_search.add_note(note)
        return note.id

    def get_note(self, note_id: str) -> Note | None:
        """Get a note by UUID."""
        return self.storage.load_note(note_id)

    def get_note_by_slug(self, path: str, slug: str) -> Note | None:
        """Get a note by its path and slug."""
        return self.storage.load_note_by_slug(path, slug)

    def get_note_by_identifier(self, identifier: str) -> Note | None:
        """Get a note by UUID or type/slug identifier.

        Args:
            identifier: Either a UUID or 'type/slug' format
        """
        if len(identifier) == 36 and identifier.count("-") == 4:
            return self.get_note(identifier)

        if "/" in identifier:
            parts = identifier.rsplit("/", 1)
            if len(parts) == 2:
                return self.get_note_by_slug(parts[0], parts[1])

        all_notes = self.list_notes()
        for note in all_notes:
            file_path = self.storage._find_file_by_uuid(note.id)
            if file_path and file_path.stem == identifier:
                return note

        return None

    def update_note(
        self,
        note_id: str,
        title: str = None,
        properties: dict[str, Any] = None,
        tags: list[str] = None,
        content: str = None,
    ) -> None:
        """Update an existing note."""
        note = self.storage.load_note(note_id)
        if not note:
            raise ValueError(f"Note with ID {note_id} not found")

        if title is not None:
            note.title = title
        if properties is not None:
            note.properties.update(properties)
        if tags is not None:
            note.tags = tags
        if content is not None:
            note.content = content

        note.updated_at = datetime.now()

        scope = self.storage.get_note_scope(note_id) or "local"
        self.storage.save_note(note, scope)
        self._sync_note_to_db(note, scope)
        if self._semantic_search is not None:
            self._semantic_search.update_note(note)

    def delete_note(self, note_id: str) -> bool:
        """Delete a note."""
        success = self.storage.delete_note(note_id)
        if success:
            self.db.remove(Query()._note_id == note_id)
            if self._semantic_search is not None:
                self._semantic_search.remove_note(note_id)
        return success

    def get_note_scope(self, note_id: str) -> str | None:
        """Get the scope (global or local) of an note."""
        return self.storage.get_note_scope(note_id)

    def list_notes(self, tags: list[str] = None, scope: str = None) -> list[Note]:
        """List notes with optional filtering."""
        query_conditions = []
        if scope:
            query_conditions.append(Query()._scope == scope)
        if tags:
            query_conditions.append(Query().tags.any(tags))

        if query_conditions:
            combined_query = query_conditions[0]
            for condition in query_conditions[1:]:
                combined_query = combined_query & condition
            results = self.db.search(combined_query)
        else:
            results = self.db.all()

        notes = []
        for doc in results:
            note_id = doc.get("_note_id")
            if note_id:
                note = self.storage.load_note(note_id)
                if note:
                    notes.append(note)

        return notes

    def extract_data(self, jmespath_query: str) -> list[dict[str, Any]]:
        """Extract data from notes using JMESPath expressions."""
        all_docs = self.db.all()
        result = jmespath.search(jmespath_query, all_docs)

        if isinstance(result, list):
            return result
        elif result is not None:
            return [result]
        else:
            return []

    def _search_semantic(
        self,
        query: str,
        n_results: int = 10,
        tags: list[str] = None,
    ) -> list[Note]:
        """Search notes using semantic similarity (requires ChromaDB)."""
        semantic_search = self._get_semantic_search()
        similar_ids = semantic_search.search_similar(query, n_results, tags)
        notes = []

        for note_id, similarity_score in similar_ids:
            note = self.get_note(note_id)
            if note:
                note._similarity_score = similarity_score
                notes.append(note)

        return notes

    def find(
        self,
        text: str = None,
        tags: list[str] = None,
        properties: dict[str, Any] = None,
        scope: str = None,
        semantic: bool = False,
        n_results: int = 10,
    ) -> list[Note]:
        """Find notes with multiple filtering options.

        Args:
            text: Text to search for in content, properties, and tags
            tags: Filter by notes having any of these tags
            properties: Filter by property key-value pairs
            scope: Filter by scope ("global" or "local")
            semantic: Use semantic/vector search instead of text search
            n_results: Maximum results for semantic search

        Returns:
            List of matching Note objects
        """
        if semantic:
            if not text:
                raise ValueError("Semantic search requires a text query")
            return self._search_semantic(text, n_results, tags)

        query_conditions = []

        if scope:
            query_conditions.append(Query()._scope == scope)

        if tags:
            query_conditions.append(Query().tags.any(tags))

        if properties:
            for key, value in properties.items():
                query_conditions.append(Query().properties[key] == value)

        if query_conditions:
            combined_query = query_conditions[0]
            for condition in query_conditions[1:]:
                combined_query = combined_query & condition
            results = self.db.search(combined_query)
        else:
            results = self.db.all()

        if text:
            text_lower = text.lower()
            filtered_results = []

            for doc in results:
                if text_lower in doc.get("content", "").lower():
                    filtered_results.append(doc)
                    continue

                tags_list = doc.get("tags", [])
                if any(text_lower in tag.lower() for tag in tags_list):
                    filtered_results.append(doc)
                    continue

                properties_dict = doc.get("properties", {})
                for value in properties_dict.values():
                    if isinstance(value, str) and text_lower in value.lower():
                        filtered_results.append(doc)
                        break

            results = filtered_results

        notes = []
        for doc in results:
            note_id = doc.get("_note_id")
            if note_id:
                note = self.storage.load_note(note_id)
                if note:
                    notes.append(note)

        return notes

    def get_related_notes(
        self, note_id: str, relationship: str = "supervisors"
    ) -> list[Note]:
        """Get notes related to this note through a specific relationship.

        Args:
            note_id: UUID or identifier of the source note
            relationship: Property name containing related note UUIDs

        Returns:
            List of related Note objects
        """
        note = self.get_note_by_identifier(note_id)
        if not note:
            return []

        related_uuids = note.properties.get(relationship, [])
        if not isinstance(related_uuids, list):
            related_uuids = [related_uuids]
        related_notes = []
        for uuid in related_uuids:
            if isinstance(uuid, str):
                related_note = self.get_note(uuid)
                if related_note:
                    related_notes.append(related_note)

        return related_notes

    def get_notes_by_property(
        self, property_name: str, property_value: Any
    ) -> list[Note]:
        """Get notes with a specific property value."""
        results = self.db.search(Query().properties[property_name] == property_value)
        notes = []
        for doc in results:
            note_id = doc.get("_note_id")
            if note_id:
                note = self.storage.load_note(note_id)
                if note:
                    notes.append(note)

        return notes

    def get_linked_notes(self, note_id: str) -> list[Note]:
        """Get notes that this note links to."""
        note = self.get_note(note_id)
        linked_ids = note.get_linked_notes()
        linked_notes = []

        for linked_id in linked_ids:
            linked_note = self.get_note(linked_id)
            linked_notes.append(linked_note)

        return linked_notes

    def get_notes_linking_to(self, target_note_id: str) -> list[Note]:
        """Get notes that link to the specified note."""
        all_notes = self.list_notes()
        linking_notes = []

        for note in all_notes:
            if target_note_id in note.get_linked_notes():
                linking_notes.append(note)

        return linking_notes

    def get_note_paths(self) -> list[str]:
        """Get all unique note paths by scanning filesystem."""
        paths = set()
        for yaml_file in self.storage.local_storage.notes_dir.rglob("*.yaml"):
            relative_path = yaml_file.relative_to(self.storage.local_storage.notes_dir)
            dir_path = str(relative_path.parent)
            if dir_path and dir_path != ".":
                paths.add(dir_path)

        for yaml_file in self.storage.global_storage.notes_dir.rglob("*.yaml"):
            relative_path = yaml_file.relative_to(self.storage.global_storage.notes_dir)
            dir_path = str(relative_path.parent)
            if dir_path and dir_path != ".":
                paths.add(dir_path)

        return sorted(paths)

    def get_all_tags(self) -> list[str]:
        """Get all unique tags across all notes."""
        all_docs = self.db.all()
        all_tags = set()

        for doc in all_docs:
            tags = doc.get("tags", [])
            if isinstance(tags, list):
                all_tags.update(tags)

        return sorted(all_tags)

    def refresh_from_files(self):
        """Refresh the in-memory database from YAML files."""
        self._load_notes_to_db()
        if self._semantic_search is not None:
            notes = list(self.storage.load_all_notes().values())
            self._semantic_search.rebuild_index(notes)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the notes database."""
        all_docs = self.db.all()

        scope_counts = {}
        for doc in all_docs:
            scope = doc.get("_scope", "unknown")
            scope_counts[scope] = scope_counts.get(scope, 0) + 1

        stats = {
            "total_notes": len(all_docs),
            "scopes": scope_counts,
            "unique_tags": len(self.get_all_tags()),
            "unique_paths": len(self.get_note_paths()),
            "storage_dirs": {
                "global": str(self.storage.global_storage.notes_dir),
                "local": str(self.storage.local_storage.notes_dir),
            },
        }

        # Only include semantic search stats if it's initialized
        if self._semantic_search is not None:
            stats["semantic_search"] = self._semantic_search.get_collection_stats()
        else:
            stats["semantic_search"] = {"status": "not_initialized"}

        return stats
