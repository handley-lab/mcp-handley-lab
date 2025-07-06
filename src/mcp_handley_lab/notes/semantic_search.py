"""ChromaDB semantic search integration for notes."""

try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from .models import Note


class SemanticSearchManager:
    """Manages semantic search using ChromaDB embeddings."""

    def __init__(self, storage_dir: str = ".mcp_handley_lab/notes"):
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "ChromaDB not available. Install with: pip install chromadb"
            )

        self.client = chromadb.PersistentClient(
            path=f"{storage_dir}/chromadb",
            settings=Settings(anonymized_telemetry=False),
        )

        # Create or get collection for notes
        self.collection = self.client.get_or_create_collection(
            name="notes", metadata={"hnsw:space": "cosine"}
        )

    def add_entity(self, note: Note) -> bool:
        """Add an note to the semantic search index."""
        try:
            # Combine content and key properties for embedding
            text_parts = []

            if note.content:
                text_parts.append(note.content)

            # Add important string properties
            for key, value in note.properties.items():
                if isinstance(value, str) and len(value) > 0:
                    text_parts.append(f"{key}: {value}")

            # Add tags
            if note.tags:
                text_parts.append(f"Tags: {', '.join(note.tags)}")

            if not text_parts:
                text_parts = [f"Note of type {note.type}"]

            document_text = " | ".join(text_parts)

            # Metadata for filtering
            metadata = {
                "type": note.type,
                "tags": note.tags,
                "created_at": note.created_at.isoformat(),
                "updated_at": note.updated_at.isoformat(),
            }

            # Add key properties to metadata (string values only)
            for key, value in note.properties.items():
                if isinstance(value, str | int | float | bool):
                    metadata[f"prop_{key}"] = str(value)

            self.collection.upsert(
                ids=[note.id], documents=[document_text], metadatas=[metadata]
            )

            return True
        except Exception:
            return False

    def remove_entity(self, entity_id: str) -> bool:
        """Remove an note from the semantic search index."""
        try:
            self.collection.delete(ids=[entity_id])
            return True
        except Exception:
            return False

    def search_similar(
        self,
        query: str,
        n_results: int = 10,
        note_type: str = None,
        tags: list[str] = None,
    ) -> list[tuple[str, float]]:
        """Search for notes similar to the query text.

        Args:
            query: Text query for semantic similarity
            n_results: Maximum number of results to return
            note_type: Filter by note type
            tags: Filter by notes having any of these tags

        Returns:
            List of tuples (entity_id, similarity_score)
        """
        try:
            # Build where clause for filtering
            where_clause = {}
            where_and_clauses = []

            if note_type:
                where_and_clauses.append({"type": {"$eq": note_type}})

            if tags:
                # Note must have at least one of the specified tags
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

            # Extract note IDs and distances (convert to similarity scores)
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

    def rebuild_index(self, notes: list[Note]) -> bool:
        """Rebuild the entire semantic search index."""
        try:
            # Clear existing collection
            self.collection.delete()

            # Re-add all notes
            for note in notes:
                self.add_entity(note)

            return True
        except Exception:
            return False

    def update_note(self, note: Note) -> bool:
        """Update an note in the semantic search index."""
        return self.add_entity(note)  # upsert handles updates


class OptionalSemanticSearch:
    """Wrapper that gracefully handles ChromaDB unavailability."""

    def __init__(self, storage_dir: str = ".mcp_handley_lab/notes"):
        self.manager: SemanticSearchManager | None = None
        self.available = False

        if CHROMADB_AVAILABLE:
            try:
                self.manager = SemanticSearchManager(storage_dir)
                self.available = True
            except Exception:
                self.available = False

    def add_entity(self, note: Note) -> bool:
        """Add an note to semantic search if available."""
        if self.available and self.manager:
            return self.manager.add_entity(note)
        return True  # Return True to not break workflows

    def remove_entity(self, entity_id: str) -> bool:
        """Remove an note from semantic search if available."""
        if self.available and self.manager:
            return self.manager.remove_entity(entity_id)
        return True

    def search_similar(
        self,
        query: str,
        n_results: int = 10,
        note_type: str = None,
        tags: list[str] = None,
    ) -> list[tuple[str, float]]:
        """Search for similar notes if semantic search is available."""
        if self.available and self.manager:
            return self.manager.search_similar(query, n_results, note_type, tags)
        return []  # Return empty list if not available

    def update_note(self, note: Note) -> bool:
        """Update an note in semantic search if available."""
        if self.available and self.manager:
            return self.manager.update_note(note)
        return True

    def rebuild_index(self, notes: list[Note]) -> bool:
        """Rebuild semantic search index if available."""
        if self.available and self.manager:
            return self.manager.rebuild_index(notes)
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
