"""Generic notes manager with YAML storage and TinyDB queries."""
import re
from datetime import datetime
from typing import Any

import jmespath
from tinydb import Query, TinyDB
from tinydb.storages import MemoryStorage

from .models import Note
from .semantic_search import OptionalSemanticSearch
from .storage import GlobalLocalYAMLStorage


class NotesManager:
    """Generic notes management with YAML files and TinyDB queries."""

    def __init__(self, local_storage_dir: str = ".mcp_handley_lab"):
        self.storage = GlobalLocalYAMLStorage(local_storage_dir)
        self.db = TinyDB(storage=MemoryStorage)
        self.semantic_search = OptionalSemanticSearch(local_storage_dir + "/notes")
        self._load_entities_to_db()
        # Build initial semantic search index
        notes = list(self.storage.load_all_entities().values())
        self.semantic_search.rebuild_index(notes)

    def _load_entities_to_db(self):
        """Load all notes from YAML files into TinyDB for fast queries."""
        self.db.truncate()
        notes = self.storage.load_all_entities()

        for entity_id, note in notes.items():
            doc = note.model_dump()
            doc["_entity_id"] = entity_id
            doc["_scope"] = self.storage.get_note_scope(entity_id)
            self.db.insert(doc)

    def _sync_entity_to_db(self, note: Note, scope: str):
        """Sync a single note to the in-memory database."""
        doc = note.model_dump()
        doc["_entity_id"] = note.id
        doc["_scope"] = scope

        # Update if exists, insert if new
        if self.db.search(Query()._entity_id == note.id):
            self.db.update(doc, Query()._entity_id == note.id)
        else:
            self.db.insert(doc)

    def create_note(
        self,
        note_type: str,
        properties: dict[str, Any] = None,
        tags: list[str] = None,
        content: str = "",
        scope: str = "local",
    ) -> str:
        """Create a new note."""
        note = Note(
            type=note_type,
            properties=properties or {},
            tags=tags or [],
            content=content,
        )

        success = self.storage.save_note(note, scope)
        if success:
            self._sync_entity_to_db(note, scope)
            self.semantic_search.add_entity(note)
            return note.id
        else:
            raise RuntimeError(f"Failed to save note {note.id}")

    def get_note(self, entity_id: str) -> Note | None:
        """Get an note by ID."""
        return self.storage.load_entity(entity_id)

    def update_note(
        self,
        entity_id: str,
        properties: dict[str, Any] = None,
        tags: list[str] = None,
        content: str = None,
    ) -> bool:
        """Update an existing note."""
        note = self.storage.load_entity(entity_id)
        if not note:
            return False

        if properties is not None:
            note.properties.update(properties)
        if tags is not None:
            note.tags = tags
        if content is not None:
            note.content = content

        note.updated_at = datetime.now()

        scope = self.storage.get_note_scope(entity_id) or "local"
        success = self.storage.save_note(note, scope)

        if success:
            self._sync_entity_to_db(note, scope)
            self.semantic_search.update_note(note)

        return success

    def delete_note(self, entity_id: str) -> bool:
        """Delete an note."""
        success = self.storage.delete_note(entity_id)
        if success:
            self.db.remove(Query()._entity_id == entity_id)
            self.semantic_search.remove_entity(entity_id)
        return success

    def get_note_scope(self, entity_id: str) -> str | None:
        """Get the scope (global or local) of an note."""
        return self.storage.get_note_scope(entity_id)

    def list_entities(
        self, note_type: str = None, tags: list[str] = None, scope: str = None
    ) -> list[Note]:
        """List notes with optional filtering."""
        query_conditions = []

        if note_type:
            query_conditions.append(Query().type == note_type)
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

        # Convert back to Note objects
        notes = []
        for doc in results:
            doc.pop("_entity_id")
            doc.pop("_scope", None)

            # Parse datetime fields
            if "created_at" in doc and isinstance(doc["created_at"], str):
                doc["created_at"] = datetime.fromisoformat(doc["created_at"])
            if "updated_at" in doc and isinstance(doc["updated_at"], str):
                doc["updated_at"] = datetime.fromisoformat(doc["updated_at"])

            notes.append(Note(**doc))

        return notes

    def query_entities_jmespath(self, jmespath_query: str) -> list[dict[str, Any]]:
        """Query notes using JMESPath expressions."""
        all_docs = self.db.all()
        try:
            result = jmespath.search(jmespath_query, all_docs)
            return result if isinstance(result, list) else [result] if result else []
        except Exception as e:
            raise ValueError(f"Invalid JMESPath query: {e}") from e

    def search_entities_text(self, query: str) -> list[Note]:
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
            all_matches[match["_entity_id"]] = match

        # Convert to Note objects
        notes = []
        for doc in all_matches.values():
            doc.pop("_entity_id")
            doc.pop("_scope", None)

            # Parse datetime fields
            if "created_at" in doc and isinstance(doc["created_at"], str):
                doc["created_at"] = datetime.fromisoformat(doc["created_at"])
            if "updated_at" in doc and isinstance(doc["updated_at"], str):
                doc["updated_at"] = datetime.fromisoformat(doc["updated_at"])

            notes.append(Note(**doc))

        return notes

    def search_entities_semantic(
        self,
        query: str,
        n_results: int = 10,
        note_type: str = None,
        tags: list[str] = None,
    ) -> list[Note]:
        """Search notes using semantic similarity (requires ChromaDB)."""
        similar_ids = self.semantic_search.search_similar(
            query, n_results, note_type, tags
        )
        notes = []

        for entity_id, similarity_score in similar_ids:
            note = self.get_note(entity_id)
            if note:
                # Add similarity score as metadata (not persisted)
                note._similarity_score = similarity_score
                notes.append(note)

        return notes

    def get_entities_by_property(
        self, property_name: str, property_value: Any
    ) -> list[Note]:
        """Get notes with a specific property value."""
        # Search for notes with the specified property value
        results = self.db.search(Query().properties[property_name] == property_value)

        # Convert to Note objects
        notes = []
        for doc in results:
            doc.pop("_entity_id")
            doc.pop("_scope", None)

            # Parse datetime fields
            if "created_at" in doc and isinstance(doc["created_at"], str):
                doc["created_at"] = datetime.fromisoformat(doc["created_at"])
            if "updated_at" in doc and isinstance(doc["updated_at"], str):
                doc["updated_at"] = datetime.fromisoformat(doc["updated_at"])

            notes.append(Note(**doc))

        return notes

    def get_linked_entities(self, entity_id: str) -> list[Note]:
        """Get notes that this note links to."""
        note = self.get_note(entity_id)
        if not note:
            return []

        linked_ids = note.get_linked_entities()
        linked_entities = []

        for linked_id in linked_ids:
            linked_entity = self.get_note(linked_id)
            if linked_entity:
                linked_entities.append(linked_entity)

        return linked_entities

    def get_entities_linking_to(self, target_note_id: str) -> list[Note]:
        """Get notes that link to the specified note."""
        all_entities = self.list_entities()
        linking_entities = []

        for note in all_entities:
            if target_note_id in note.get_linked_entities():
                linking_entities.append(note)

        return linking_entities

    def get_note_types(self) -> list[str]:
        """Get all unique note types."""
        all_docs = self.db.all()
        types = {doc.get("type") for doc in all_docs if doc.get("type")}
        return sorted(types)

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
        self._load_entities_to_db()
        # Rebuild semantic search index
        notes = list(self.storage.load_all_entities().values())
        self.semantic_search.rebuild_index(notes)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the notes database."""
        all_docs = self.db.all()

        # Count by type
        type_counts = {}
        for doc in all_docs:
            note_type = doc.get("type", "unknown")
            type_counts[note_type] = type_counts.get(note_type, 0) + 1

        # Count by scope
        scope_counts = {}
        for doc in all_docs:
            scope = doc.get("_scope", "unknown")
            scope_counts[scope] = scope_counts.get(scope, 0) + 1

        return {
            "total_entities": len(all_docs),
            "note_types": type_counts,
            "scopes": scope_counts,
            "unique_tags": len(self.get_all_tags()),
            "semantic_search": self.semantic_search.get_stats(),
            "storage_dirs": {
                "global": str(self.storage.global_storage.entities_dir),
                "local": str(self.storage.local_storage.entities_dir),
            },
        }
