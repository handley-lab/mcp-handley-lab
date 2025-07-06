"""ChromaDB semantic search integration for knowledge entities."""

try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from .models import Entity


class SemanticSearchManager:
    """Manages semantic search using ChromaDB embeddings."""

    def __init__(self, storage_dir: str = ".mcp_handley_lab/knowledge"):
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "ChromaDB not available. Install with: pip install chromadb"
            )

        self.client = chromadb.PersistentClient(
            path=f"{storage_dir}/chromadb",
            settings=Settings(anonymized_telemetry=False),
        )

        # Create or get collection for entities
        self.collection = self.client.get_or_create_collection(
            name="entities", metadata={"hnsw:space": "cosine"}
        )

    def add_entity(self, entity: Entity) -> bool:
        """Add an entity to the semantic search index."""
        try:
            # Combine content and key properties for embedding
            text_parts = []

            if entity.content:
                text_parts.append(entity.content)

            # Add important string properties
            for key, value in entity.properties.items():
                if isinstance(value, str) and len(value) > 0:
                    text_parts.append(f"{key}: {value}")

            # Add tags
            if entity.tags:
                text_parts.append(f"Tags: {', '.join(entity.tags)}")

            if not text_parts:
                text_parts = [f"Entity of type {entity.type}"]

            document_text = " | ".join(text_parts)

            # Metadata for filtering
            metadata = {
                "type": entity.type,
                "tags": entity.tags,
                "created_at": entity.created_at.isoformat(),
                "updated_at": entity.updated_at.isoformat(),
            }

            # Add key properties to metadata (string values only)
            for key, value in entity.properties.items():
                if isinstance(value, str | int | float | bool):
                    metadata[f"prop_{key}"] = str(value)

            self.collection.upsert(
                ids=[entity.id], documents=[document_text], metadatas=[metadata]
            )

            return True
        except Exception:
            return False

    def remove_entity(self, entity_id: str) -> bool:
        """Remove an entity from the semantic search index."""
        try:
            self.collection.delete(ids=[entity_id])
            return True
        except Exception:
            return False

    def search_similar(
        self,
        query: str,
        n_results: int = 10,
        entity_type: str = None,
        tags: list[str] = None,
    ) -> list[tuple[str, float]]:
        """Search for entities similar to the query text.

        Args:
            query: Text query for semantic similarity
            n_results: Maximum number of results to return
            entity_type: Filter by entity type
            tags: Filter by entities having any of these tags

        Returns:
            List of tuples (entity_id, similarity_score)
        """
        try:
            # Build where clause for filtering
            where_clause = {}
            where_and_clauses = []

            if entity_type:
                where_and_clauses.append({"type": {"$eq": entity_type}})

            if tags:
                # Entity must have at least one of the specified tags
                tag_conditions = []
                for tag in tags:
                    tag_conditions.append({"tags": {"$contains": tag}})
                if len(tag_conditions) == 1:
                    where_and_clauses.append(tag_conditions[0])
                else:
                    where_and_clauses.append({"$or": tag_conditions})

            if where_and_clauses:
                if len(where_and_clauses) == 1:
                    where_clause = where_and_clauses[0]
                else:
                    where_clause = {"$and": where_and_clauses}

            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_clause if where_clause else None,
            )

            # Extract entity IDs and distances (convert to similarity scores)
            if results["ids"] and len(results["ids"]) > 0:
                entity_ids = results["ids"][0]
                distances = (
                    results["distances"][0]
                    if results["distances"]
                    else [0.0] * len(entity_ids)
                )

                # Convert cosine distance to similarity score (1 - distance)
                similarities = [
                    (entity_id, 1.0 - distance)
                    for entity_id, distance in zip(entity_ids, distances, strict=False)
                ]
                return similarities
            else:
                return []

        except Exception:
            return []

    def get_collection_stats(self) -> dict[str, int]:
        """Get statistics about the semantic search collection."""
        try:
            count = self.collection.count()
            return {"total_entities": count}
        except Exception:
            return {"total_entities": 0}

    def rebuild_index(self, entities: list[Entity]) -> bool:
        """Rebuild the entire semantic search index."""
        try:
            # Clear existing collection
            self.collection.delete()

            # Re-add all entities
            for entity in entities:
                self.add_entity(entity)

            return True
        except Exception:
            return False

    def update_entity(self, entity: Entity) -> bool:
        """Update an entity in the semantic search index."""
        return self.add_entity(entity)  # upsert handles updates


class OptionalSemanticSearch:
    """Wrapper that gracefully handles ChromaDB unavailability."""

    def __init__(self, storage_dir: str = ".mcp_handley_lab/knowledge"):
        self.manager: SemanticSearchManager | None = None
        self.available = False

        if CHROMADB_AVAILABLE:
            try:
                self.manager = SemanticSearchManager(storage_dir)
                self.available = True
            except Exception:
                self.available = False

    def add_entity(self, entity: Entity) -> bool:
        """Add an entity to semantic search if available."""
        if self.available and self.manager:
            return self.manager.add_entity(entity)
        return True  # Return True to not break workflows

    def remove_entity(self, entity_id: str) -> bool:
        """Remove an entity from semantic search if available."""
        if self.available and self.manager:
            return self.manager.remove_entity(entity_id)
        return True

    def search_similar(
        self,
        query: str,
        n_results: int = 10,
        entity_type: str = None,
        tags: list[str] = None,
    ) -> list[tuple[str, float]]:
        """Search for similar entities if semantic search is available."""
        if self.available and self.manager:
            return self.manager.search_similar(query, n_results, entity_type, tags)
        return []  # Return empty list if not available

    def update_entity(self, entity: Entity) -> bool:
        """Update an entity in semantic search if available."""
        if self.available and self.manager:
            return self.manager.update_entity(entity)
        return True

    def rebuild_index(self, entities: list[Entity]) -> bool:
        """Rebuild semantic search index if available."""
        if self.available and self.manager:
            return self.manager.rebuild_index(entities)
        return True

    def get_stats(self) -> dict[str, any]:
        """Get semantic search statistics."""
        if self.available and self.manager:
            return {"available": True, **self.manager.get_collection_stats()}
        else:
            return {
                "available": False,
                "reason": "ChromaDB not installed or failed to initialize",
            }
