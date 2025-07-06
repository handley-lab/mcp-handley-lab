"""Generic knowledge manager with YAML storage and TinyDB queries."""
import re
from datetime import datetime
from typing import Any

import jmespath
from tinydb import Query, TinyDB
from tinydb.storages import MemoryStorage

from .models import Entity
from .semantic_search import OptionalSemanticSearch
from .storage import GlobalLocalYAMLStorage


class GenericKnowledgeManager:
    """Generic knowledge management with YAML files and TinyDB queries."""

    def __init__(self, local_storage_dir: str = ".mcp_handley_lab"):
        self.storage = GlobalLocalYAMLStorage(local_storage_dir)
        self.db = TinyDB(storage=MemoryStorage)
        self.semantic_search = OptionalSemanticSearch(local_storage_dir + "/knowledge")
        self._load_entities_to_db()

    def _load_entities_to_db(self):
        """Load all entities from YAML files into TinyDB for fast queries."""
        self.db.truncate()
        entities = self.storage.load_all_entities()

        for entity_id, entity in entities.items():
            doc = entity.model_dump()
            doc["_entity_id"] = entity_id
            doc["_scope"] = self.storage.get_entity_scope(entity_id)
            self.db.insert(doc)

    def _sync_entity_to_db(self, entity: Entity, scope: str):
        """Sync a single entity to the in-memory database."""
        doc = entity.model_dump()
        doc["_entity_id"] = entity.id
        doc["_scope"] = scope

        # Update if exists, insert if new
        if self.db.search(Query()._entity_id == entity.id):
            self.db.update(doc, Query()._entity_id == entity.id)
        else:
            self.db.insert(doc)

    def create_entity(
        self,
        entity_type: str,
        properties: dict[str, Any] = None,
        tags: list[str] = None,
        content: str = "",
        scope: str = "local",
    ) -> str:
        """Create a new generic entity."""
        entity = Entity(
            type=entity_type,
            properties=properties or {},
            tags=tags or [],
            content=content,
        )

        success = self.storage.save_entity(entity, scope)
        if success:
            self._sync_entity_to_db(entity, scope)
            self.semantic_search.add_entity(entity)
            return entity.id
        else:
            raise RuntimeError(f"Failed to save entity {entity.id}")

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get an entity by ID."""
        return self.storage.load_entity(entity_id)

    def update_entity(
        self,
        entity_id: str,
        properties: dict[str, Any] = None,
        tags: list[str] = None,
        content: str = None,
    ) -> bool:
        """Update an existing entity."""
        entity = self.storage.load_entity(entity_id)
        if not entity:
            return False

        if properties is not None:
            entity.properties.update(properties)
        if tags is not None:
            entity.tags = tags
        if content is not None:
            entity.content = content

        entity.updated_at = datetime.now()

        scope = self.storage.get_entity_scope(entity_id) or "local"
        success = self.storage.save_entity(entity, scope)

        if success:
            self._sync_entity_to_db(entity, scope)
            self.semantic_search.update_entity(entity)

        return success

    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity."""
        success = self.storage.delete_entity(entity_id)
        if success:
            self.db.remove(Query()._entity_id == entity_id)
            self.semantic_search.remove_entity(entity_id)
        return success

    def get_entity_scope(self, entity_id: str) -> str | None:
        """Get the scope (global or local) of an entity."""
        return self.storage.get_entity_scope(entity_id)

    def list_entities(
        self, entity_type: str = None, tags: list[str] = None, scope: str = None
    ) -> list[Entity]:
        """List entities with optional filtering."""
        query_conditions = []

        if entity_type:
            query_conditions.append(Query().type == entity_type)
        if scope:
            query_conditions.append(Query()._scope == scope)
        if tags:
            # Entity must have any of the specified tags
            query_conditions.append(Query().tags.any(tags))

        # Combine all conditions with AND
        if query_conditions:
            combined_query = query_conditions[0]
            for condition in query_conditions[1:]:
                combined_query = combined_query & condition
            results = self.db.search(combined_query)
        else:
            results = self.db.all()

        # Convert back to Entity objects
        entities = []
        for doc in results:
            doc.pop("_entity_id")
            doc.pop("_scope", None)

            # Parse datetime fields
            if "created_at" in doc and isinstance(doc["created_at"], str):
                doc["created_at"] = datetime.fromisoformat(doc["created_at"])
            if "updated_at" in doc and isinstance(doc["updated_at"], str):
                doc["updated_at"] = datetime.fromisoformat(doc["updated_at"])

            entities.append(Entity(**doc))

        return entities

    def query_entities_jmespath(self, jmespath_query: str) -> list[dict[str, Any]]:
        """Query entities using JMESPath expressions."""
        all_docs = self.db.all()
        try:
            result = jmespath.search(jmespath_query, all_docs)
            return result if isinstance(result, list) else [result] if result else []
        except Exception as e:
            raise ValueError(f"Invalid JMESPath query: {e}") from e

    def search_entities_text(self, query: str) -> list[Entity]:
        """Search entities by text across content, properties, and tags."""
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

        # Convert to Entity objects
        entities = []
        for doc in all_matches.values():
            doc.pop("_entity_id")
            doc.pop("_scope", None)

            # Parse datetime fields
            if "created_at" in doc and isinstance(doc["created_at"], str):
                doc["created_at"] = datetime.fromisoformat(doc["created_at"])
            if "updated_at" in doc and isinstance(doc["updated_at"], str):
                doc["updated_at"] = datetime.fromisoformat(doc["updated_at"])

            entities.append(Entity(**doc))

        return entities

    def search_entities_semantic(
        self,
        query: str,
        n_results: int = 10,
        entity_type: str = None,
        tags: list[str] = None,
    ) -> list[Entity]:
        """Search entities using semantic similarity (requires ChromaDB)."""
        similar_ids = self.semantic_search.search_similar(
            query, n_results, entity_type, tags
        )
        entities = []

        for entity_id, similarity_score in similar_ids:
            entity = self.get_entity(entity_id)
            if entity:
                # Add similarity score as metadata (not persisted)
                entity._similarity_score = similarity_score
                entities.append(entity)

        return entities

    def get_entities_by_property(
        self, property_name: str, property_value: Any
    ) -> list[Entity]:
        """Get entities with a specific property value."""
        # Search for entities with the specified property value
        results = self.db.search(Query().properties[property_name] == property_value)

        # Convert to Entity objects
        entities = []
        for doc in results:
            doc.pop("_entity_id")
            doc.pop("_scope", None)

            # Parse datetime fields
            if "created_at" in doc and isinstance(doc["created_at"], str):
                doc["created_at"] = datetime.fromisoformat(doc["created_at"])
            if "updated_at" in doc and isinstance(doc["updated_at"], str):
                doc["updated_at"] = datetime.fromisoformat(doc["updated_at"])

            entities.append(Entity(**doc))

        return entities

    def get_linked_entities(self, entity_id: str) -> list[Entity]:
        """Get entities that this entity links to."""
        entity = self.get_entity(entity_id)
        if not entity:
            return []

        linked_ids = entity.get_linked_entities()
        linked_entities = []

        for linked_id in linked_ids:
            linked_entity = self.get_entity(linked_id)
            if linked_entity:
                linked_entities.append(linked_entity)

        return linked_entities

    def get_entities_linking_to(self, target_entity_id: str) -> list[Entity]:
        """Get entities that link to the specified entity."""
        all_entities = self.list_entities()
        linking_entities = []

        for entity in all_entities:
            if target_entity_id in entity.get_linked_entities():
                linking_entities.append(entity)

        return linking_entities

    def get_entity_types(self) -> list[str]:
        """Get all unique entity types."""
        all_docs = self.db.all()
        types = {doc.get("type") for doc in all_docs if doc.get("type")}
        return sorted(types)

    def get_all_tags(self) -> list[str]:
        """Get all unique tags across all entities."""
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
        entities = list(self.storage.load_all_entities().values())
        self.semantic_search.rebuild_index(entities)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the knowledge base."""
        all_docs = self.db.all()

        # Count by type
        type_counts = {}
        for doc in all_docs:
            entity_type = doc.get("type", "unknown")
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1

        # Count by scope
        scope_counts = {}
        for doc in all_docs:
            scope = doc.get("_scope", "unknown")
            scope_counts[scope] = scope_counts.get(scope, 0) + 1

        return {
            "total_entities": len(all_docs),
            "entity_types": type_counts,
            "scopes": scope_counts,
            "unique_tags": len(self.get_all_tags()),
            "semantic_search": self.semantic_search.get_stats(),
            "storage_dirs": {
                "global": str(self.storage.global_storage.entities_dir),
                "local": str(self.storage.local_storage.entities_dir),
            },
        }
