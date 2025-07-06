"""Generic notes manager with YAML storage and TinyDB queries."""
import re
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
        self.semantic_search = SemanticSearchManager(local_storage_dir + "/notes")
        self._load_notes_to_db()
        # Build initial semantic search index
        notes = list(self.storage.load_all_notes().values())
        self.semantic_search.rebuild_index(notes)

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

        # Update if exists, insert if new
        if self.db.search(Query()._note_id == note.id):
            self.db.update(doc, Query()._note_id == note.id)
        else:
            self.db.insert(doc)

    def _generate_slug(self, title: str) -> str:
        """Generate a URL-friendly slug from title."""
        import re

        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower())
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        return slug

    def _ensure_unique_slug(self, path: str, base_slug: str, scope: str) -> str:
        """Ensure slug is unique within the given path and scope."""
        slug = base_slug
        counter = 1

        while True:
            # Check if this slug already exists
            existing = self.storage.load_note_by_slug(path, slug)
            if not existing:
                return slug

            # Try with suffix
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

        # Generate slug if not provided
        if not slug:
            slug = self._generate_slug(title)

        # Ensure slug is unique within this path
        slug = self._ensure_unique_slug(path, slug, scope)

        self.storage.save_note(note, scope, path, slug)
        self._sync_note_to_db(note, scope)
        self.semantic_search.add_note(note)
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
        # Check if it looks like a UUID
        if len(identifier) == 36 and identifier.count("-") == 4:
            return self.get_note(identifier)

        # Try to parse as path/slug
        if "/" in identifier:
            parts = identifier.rsplit("/", 1)  # Split on last / to handle deep paths
            if len(parts) == 2:
                return self.get_note_by_slug(parts[0], parts[1])

        # Try as just slug in all paths (search all directories)
        all_notes = self.list_notes()
        for note in all_notes:
            # Compute slug from filesystem path
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
        self.storage.save_note(note, scope)  # Saves to existing location
        self._sync_note_to_db(note, scope)
        self.semantic_search.update_note(note)

    def delete_note(self, note_id: str) -> bool:
        """Delete a note."""
        success = self.storage.delete_note(note_id)
        if success:
            self.db.remove(Query()._note_id == note_id)
            self.semantic_search.remove_note(note_id)
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
            # Note must have any of the specified tags
            query_conditions.append(Query().tags.any(tags))

        # Combine all conditions with AND
        if query_conditions:
            combined_query = query_conditions[0]
            for condition in query_conditions[1:]:
                combined_query = combined_query & condition
            results = self.db.search(combined_query)
        else:
            results = self.db.all()

        # Convert back to Note objects and reload from storage to get current filesystem info
        notes = []
        for doc in results:
            note_id = doc.get("_note_id")
            if note_id:
                # Load from storage to get current filesystem-derived info
                note = self.storage.load_note(note_id)
                if note:
                    notes.append(note)

        return notes

    def query_notes_jmespath(self, jmespath_query: str) -> list[dict[str, Any]]:
        """Query notes using JMESPath expressions."""
        all_docs = self.db.all()
        result = jmespath.search(jmespath_query, all_docs)
        return result if isinstance(result, list) else [result] if result else []

    def search_notes_text(self, query: str) -> list[Note]:
        """Search notes by text across content, properties, and tags."""
        query_lower = query.lower()

        # Search in content
        content_matches = self.db.search(
            Query().content.matches(
                f".*{re.escape(query_lower)}.*", flags=re.IGNORECASE
            )
        )

        # Search in tags (case-insensitive)
        tag_matches = self.db.search(
            Query().tags.any(lambda tag: query_lower in tag.lower())
        )

        # Search in properties (string values only)
        property_matches = []
        for doc in self.db.all():
            for _key, value in doc.get("properties", {}).items():
                if isinstance(value, str) and query_lower in value.lower():
                    property_matches.append(doc)
                    break

        # Combine and deduplicate results
        all_matches = {}
        for match in content_matches + tag_matches + property_matches:
            all_matches[match["_note_id"]] = match

        # Convert to Note objects by loading from storage
        notes = []
        for doc in all_matches.values():
            note_id = doc.get("_note_id")
            if note_id:
                # Load from storage to get current filesystem-derived info
                note = self.storage.load_note(note_id)
                if note:
                    notes.append(note)

        return notes

    def search_notes_semantic(
        self,
        query: str,
        n_results: int = 10,
        tags: list[str] = None,
    ) -> list[Note]:
        """Search notes using semantic similarity (requires ChromaDB)."""
        similar_ids = self.semantic_search.search_similar(query, n_results, tags)
        notes = []

        for note_id, similarity_score in similar_ids:
            note = self.get_note(note_id)
            if note:
                # Add similarity score as metadata (not persisted)
                note._similarity_score = similarity_score
                notes.append(note)

        return notes

    def get_notes_by_property(
        self, property_name: str, property_value: Any
    ) -> list[Note]:
        """Get notes with a specific property value."""
        # Search for notes with the specified property value
        results = self.db.search(Query().properties[property_name] == property_value)

        # Convert to Note objects by loading from storage
        notes = []
        for doc in results:
            note_id = doc.get("_note_id")
            if note_id:
                # Load from storage to get current filesystem-derived info
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
        # Scan the filesystem for directories containing YAML files
        for yaml_file in self.storage.local_storage.notes_dir.rglob("*.yaml"):
            relative_path = yaml_file.relative_to(self.storage.local_storage.notes_dir)
            dir_path = str(relative_path.parent)
            if dir_path and dir_path != ".":
                paths.add(dir_path)

        # Also scan global storage
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
        # Rebuild semantic search index
        notes = list(self.storage.load_all_notes().values())
        self.semantic_search.rebuild_index(notes)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the notes database."""
        all_docs = self.db.all()

        # No need for artificial primary tag counting - just count scopes

        # Count by scope
        scope_counts = {}
        for doc in all_docs:
            scope = doc.get("_scope", "unknown")
            scope_counts[scope] = scope_counts.get(scope, 0) + 1

        return {
            "total_notes": len(all_docs),
            "scopes": scope_counts,
            "unique_tags": len(self.get_all_tags()),
            "unique_paths": len(self.get_note_paths()),
            "semantic_search": self.semantic_search.get_collection_stats(),
            "storage_dirs": {
                "global": str(self.storage.global_storage.notes_dir),
                "local": str(self.storage.local_storage.notes_dir),
            },
        }
