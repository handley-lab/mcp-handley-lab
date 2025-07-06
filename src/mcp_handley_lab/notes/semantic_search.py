"""ChromaDB semantic search integration for notes."""

import chromadb
from chromadb.config import Settings

from .models import Note


class SemanticSearchManager:
    """Manages semantic search using ChromaDB embeddings."""

    def __init__(self, storage_dir: str = ".mcp_handley_lab/notes"):
        self.client = chromadb.PersistentClient(
            path=f"{storage_dir}/chromadb",
            settings=Settings(anonymized_telemetry=False),
        )

        # Create or get collection for notes
        self.collection = self.client.get_or_create_collection(
            name="notes", metadata={"hnsw:space": "cosine"}
        )

    def add_note(self, note: Note) -> bool:
        """Add an note to the semantic search index."""
        # Combine content and key properties for embedding
        text_parts = []

        text_parts.append(note.content)

        # Add important string properties
        for key, value in note.properties.items():
            if isinstance(value, str):
                text_parts.append(f"{key}: {value}")

        # Add tags
        text_parts.append(f"Tags: {', '.join(note.tags)}")

        document_text = " | ".join(text_parts)

        # Metadata for filtering
        metadata = {
            "primary_tag": note.tags[0] if note.tags else "unknown",
            "tags": ",".join(note.tags),  # Convert list to comma-separated string
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

    def remove_note(self, note_id: str) -> bool:
        """Remove an note from the semantic search index."""
        self.collection.delete(ids=[note_id])
        return True

    def search_similar(
        self,
        query: str,
        n_results: int = 10,
        primary_tag: str = None,
        tags: list[str] = None,
    ) -> list[tuple[str, float]]:
        """Search for notes similar to the query text.

        Args:
            query: Text query for semantic similarity
            n_results: Maximum number of results to return
            primary_tag: Filter by primary tag (first tag)
            tags: Filter by notes having any of these tags

        Returns:
            List of tuples (note_id, similarity_score)
        """
        # Build where clause for filtering
        where_clause = {}
        where_and_clauses = []

        if primary_tag:
            where_and_clauses.append({"primary_tag": {"$eq": primary_tag}})

        if tags:
            # Note must have at least one of the specified tags (now comma-separated)
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
            note_ids = results["ids"][0]
            distances = (
                results["distances"][0]
                if results["distances"]
                else [0.0] * len(note_ids)
            )

            # Convert cosine distance to similarity score (1 - distance)
            similarities = [
                (note_id, 1.0 - distance)
                for note_id, distance in zip(note_ids, distances, strict=False)
            ]
            return similarities
        else:
            return []

    def get_collection_stats(self) -> dict[str, int]:
        """Get statistics about the semantic search collection."""
        count = self.collection.count()
        return {"total_notes": count}

    def rebuild_index(self, notes: list[Note]) -> None:
        """Rebuild the entire semantic search index."""
        # Re-add all notes (ChromaDB upsert will handle duplicates)
        for note in notes:
            self.add_note(note)

    def update_note(self, note: Note) -> bool:
        """Update an note in the semantic search index."""
        return self.add_note(note)  # upsert handles updates


# Alias for backwards compatibility
OptionalSemanticSearch = SemanticSearchManager
