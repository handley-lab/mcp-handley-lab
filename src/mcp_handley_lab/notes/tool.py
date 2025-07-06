"""Generic MCP tools for notes management."""
from typing import Any

from mcp.server.fastmcp import FastMCP

from .manager import NotesManager

# Initialize the FastMCP server
mcp = FastMCP("Notes")

# Global manager instance - can be overridden by persistent server
_manager: NotesManager | None = None


def get_manager() -> NotesManager:
    """Get or create the notes manager instance.

    For stdio mode: Creates a new manager each time (stateless)
    For HTTP mode: Uses the persistent server's manager (stateful)
    """
    global _manager
    if _manager is None:
        _manager = NotesManager()
    return _manager


def set_manager(manager: NotesManager) -> None:
    """Set the global manager instance (used by persistent server)."""
    global _manager
    _manager = manager


@mcp.tool()
def create_note(
    note_type: str,
    properties: dict[str, Any] = None,
    tags: list[str] = None,
    content: str = "",
    scope: str = "local",
) -> str:
    """Create a new note.

    Args:
        note_type: Type of note (e.g., "person", "project", "attic_item", "idea")
        properties: Dictionary of structured properties
        tags: List of tags for categorization
        content: Unstructured text content/description
        scope: Storage scope - "global" (shared) or "local" (project-specific)

    Returns:
        The ID of the created note
    """
    if scope not in ("global", "local"):
        raise ValueError("Scope must be 'global' or 'local'")

    manager = get_manager()
    return manager.create_note(note_type, properties, tags, content, scope)


@mcp.tool()
def get_note(entity_id: str) -> dict[str, Any] | None:
    """Get an note by its ID.

    Args:
        entity_id: The unique identifier of the note

    Returns:
        Note data as a dictionary, or None if not found
    """
    manager = get_manager()
    note = manager.get_note(entity_id)
    return note.model_dump() if note else None


@mcp.tool()
def update_note(
    entity_id: str,
    properties: dict[str, Any] = None,
    tags: list[str] = None,
    content: str = None,
) -> bool:
    """Update an existing note.

    Args:
        entity_id: The unique identifier of the note
        properties: Dictionary of properties to update/add
        tags: New list of tags (replaces existing)
        content: New content (replaces existing)

    Returns:
        True if update succeeded, False otherwise
    """
    manager = get_manager()
    return manager.update_note(entity_id, properties, tags, content)


@mcp.tool()
def delete_note(entity_id: str) -> bool:
    """Delete an note.

    Args:
        entity_id: The unique identifier of the note

    Returns:
        True if deletion succeeded, False otherwise
    """
    manager = get_manager()
    return manager.delete_note(entity_id)


@mcp.tool()
def list_entities(
    note_type: str = None, tags: list[str] = None, scope: str = None
) -> list[dict[str, Any]]:
    """List notes with optional filtering.

    Args:
        note_type: Filter by note type
        tags: Filter by notes having any of these tags
        scope: Filter by scope ("global" or "local")

    Returns:
        List of note dictionaries
    """
    manager = get_manager()
    notes = manager.list_entities(note_type, tags, scope)
    return [note.model_dump() for note in notes]


@mcp.tool()
def search_entities(query: str) -> list[dict[str, Any]]:
    """Search notes by text across content, properties, and tags.

    Args:
        query: Text to search for

    Returns:
        List of matching note dictionaries
    """
    manager = get_manager()
    notes = manager.search_entities_text(query)
    return [note.model_dump() for note in notes]


@mcp.tool()
def search_entities_semantic(
    query: str, n_results: int = 10, note_type: str = None, tags: list[str] = None
) -> list[dict[str, Any]]:
    """Search notes using semantic similarity (requires ChromaDB).

    Args:
        query: Text query for semantic similarity
        n_results: Maximum number of results to return
        note_type: Filter by note type
        tags: Filter by notes having any of these tags

    Returns:
        List of note dictionaries with similarity scores
    """
    manager = get_manager()
    notes = manager.search_entities_semantic(query, n_results, note_type, tags)

    results = []
    for note in notes:
        entity_dict = note.model_dump()
        # Add similarity score if available
        if hasattr(note, "_similarity_score"):
            entity_dict["similarity_score"] = note._similarity_score
        results.append(entity_dict)

    return results


@mcp.tool()
def query_entities(jmespath_query: str) -> Any:
    """Query notes using JMESPath expressions for structured queries.

    Args:
        jmespath_query: JMESPath expression (e.g., "[?type=='person'].properties.name")

    Returns:
        Query results (can be any data structure: strings, numbers, arrays, objects, etc.)
    """
    manager = get_manager()
    return manager.query_entities_jmespath(jmespath_query)


@mcp.tool()
def get_entities_by_property(
    property_name: str, property_value: Any
) -> list[dict[str, Any]]:
    """Get notes with a specific property value.

    Args:
        property_name: Name of the property
        property_value: Value to match

    Returns:
        List of matching note dictionaries
    """
    manager = get_manager()
    notes = manager.get_entities_by_property(property_name, property_value)
    return [note.model_dump() for note in notes]


@mcp.tool()
def get_linked_entities(entity_id: str) -> list[dict[str, Any]]:
    """Get notes that the specified note links to.

    Args:
        entity_id: The note ID to find links from

    Returns:
        List of linked note dictionaries
    """
    manager = get_manager()
    notes = manager.get_linked_entities(entity_id)
    return [note.model_dump() for note in notes]


@mcp.tool()
def get_entities_linking_to(target_note_id: str) -> list[dict[str, Any]]:
    """Get notes that link to the specified note.

    Args:
        target_note_id: The note ID to find links to

    Returns:
        List of notes that link to the target
    """
    manager = get_manager()
    notes = manager.get_entities_linking_to(target_note_id)
    return [note.model_dump() for note in notes]


@mcp.tool()
def get_note_types() -> list[str]:
    """Get all unique note types in the notes database.

    Returns:
        Sorted list of note types
    """
    manager = get_manager()
    return manager.get_note_types()


@mcp.tool()
def get_all_tags() -> list[str]:
    """Get all unique tags across all notes.

    Returns:
        Sorted list of tags
    """
    manager = get_manager()
    return manager.get_all_tags()


@mcp.tool()
def get_notes_stats() -> dict[str, Any]:
    """Get statistics about the notes database.

    Returns:
        Dictionary with statistics (counts, types, etc.)
    """
    manager = get_manager()
    return manager.get_stats()


@mcp.tool()
def refresh_notes_database() -> str:
    """Refresh the in-memory database from YAML files.

    Returns:
        Confirmation message
    """
    manager = get_manager()
    manager.refresh_from_files()
    stats = manager.get_stats()
    return f"Notes database refreshed. Loaded {stats['total_entities']} notes."


@mcp.tool()
def get_note_scope(entity_id: str) -> str | None:
    """Get the scope (global or local) of an note.

    Args:
        entity_id: The unique identifier of the note

    Returns:
        "global", "local", or None if note not found
    """
    manager = get_manager()
    return manager.get_note_scope(entity_id)


# Resource for browsing notes
@mcp.resource("notes://notes")
def list_entities_resource() -> str:
    """Browse all notes in the notes database."""
    manager = get_manager()
    notes = manager.list_entities()

    if not notes:
        return "No notes found in the notes database."

    lines = ["# Notes Database Entities\n"]

    # Group by type
    by_type = {}
    for note in notes:
        note_type = note.type
        if note_type not in by_type:
            by_type[note_type] = []
        by_type[note_type].append(note)

    for note_type, type_entities in sorted(by_type.items()):
        lines.append(f"## {note_type.title()} ({len(type_entities)})\n")

        for note in type_entities:
            scope = manager.get_note_scope(note.id) or "unknown"
            tag_str = f" [{', '.join(note.tags)}]" if note.tags else ""
            lines.append(f"- **{note.id}** ({scope}){tag_str}")

            # Show key properties
            if note.properties:
                key_props = []
                for key, value in list(note.properties.items())[:3]:  # Show first 3
                    if isinstance(value, str) and len(value) < 50:
                        key_props.append(f"{key}: {value}")
                if key_props:
                    lines.append(f"  - {'; '.join(key_props)}")

            # Show content preview
            if note.content:
                preview = (
                    note.content[:100] + "..."
                    if len(note.content) > 100
                    else note.content
                )
                lines.append(f"  - {preview}")

            lines.append("")

    return "\n".join(lines)


@mcp.resource("notes://stats")
def notes_stats_resource() -> str:
    """View notes database statistics."""
    manager = get_manager()
    stats = manager.get_stats()

    lines = [
        "# Notes Database Statistics\n",
        f"**Total Entities:** {stats['total_entities']}\n",
        f"**Unique Tags:** {stats['unique_tags']}\n",
        "## Note Types\n",
    ]

    for note_type, count in sorted(stats["note_types"].items()):
        lines.append(f"- {note_type}: {count}")

    lines.append("\n## Storage Scopes\n")
    for scope, count in sorted(stats["scopes"].items()):
        lines.append(f"- {scope}: {count}")

    lines.append("\n## Storage Locations\n")
    for scope, path in stats["storage_dirs"].items():
        lines.append(f"- {scope}: {path}")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
