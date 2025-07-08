"""Generic MCP tools for notes management."""
from typing import Any

from mcp.server.fastmcp import FastMCP

from .manager import NotesManager
from .models import Note

# Initialize the FastMCP server
mcp = FastMCP("Notes")

# Global manager instance - can be overridden by persistent server
_manager: NotesManager = None


def set_manager(manager: NotesManager) -> None:
    """Set the global manager instance (used by persistent server)."""
    global _manager
    _manager = manager


def get_manager() -> NotesManager:
    """Get or create the notes manager instance."""
    global _manager
    if _manager is not None:
        return _manager

    _ensure_server_running()
    return NotesManager()


def _ensure_server_running():
    """Start server if not running."""
    import socket
    import subprocess

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("127.0.0.1", 8000))
    sock.close()

    if result == 0:
        return

    subprocess.Popen(
        ["mcp-notes-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


@mcp.tool()
def create_note(
    path: str,
    title: str,
    properties: dict[str, Any] = {},
    tags: list[str] = [],
    content: str = "",
    scope: str = "local",
    slug: str = "",
) -> str:
    """Create a new note.

    Args:
        path: Directory path for the note (e.g., "person", "person/researcher/phd")
        title: Human-readable title for the note
        properties: Dictionary of structured properties
        tags: List of tags for categorization
        content: Unstructured text content/description
        scope: Storage scope - "global" (shared) or "local" (project-specific)
        slug: Custom slug (auto-generated from title if not provided)

    Returns:
        The UUID of the created note
    """
    if scope not in ("global", "local"):
        raise ValueError("Scope must be 'global' or 'local'")

    manager = get_manager()
    return manager.create_note(
        path, title, properties or None, tags or None, content, scope, slug or None
    )


@mcp.tool()
def get_note(note_id: str) -> Note:
    """Get a note by its UUID or type/slug identifier.

    Args:
        note_id: UUID, type/slug (e.g. 'person/david-yallup'), or just slug

    Returns:
        Note data as a dictionary, or None if not found
    """
    manager = get_manager()
    note = manager.get_note_by_identifier(note_id)
    if note is None:
        raise ValueError(f"Note not found: {note_id}")
    return note


@mcp.tool()
def update_note(
    note_id: str,
    properties: dict[str, Any] = {},
    tags: list[str] = [],
    content: str = "",
) -> str:
    """Update an existing note.

    Args:
        note_id: The unique identifier of the note
        properties: Dictionary of properties to update/add
        tags: New list of tags (replaces existing)
        content: New content (replaces existing)

    Returns:
        Confirmation message
    """
    manager = get_manager()
    manager.update_note(
        note_id,
        title=None,
        properties=properties or None,
        tags=tags or None,
        content=content or None,
    )
    return f"Note {note_id} updated successfully"


@mcp.tool()
def delete_note(note_id: str) -> bool:
    """Delete an note.

    Args:
        note_id: The unique identifier of the note

    Returns:
        True if deletion succeeded, False otherwise
    """
    manager = get_manager()
    return manager.delete_note(note_id)


@mcp.tool()
def find(
    text: str = "",
    tags: list[str] = [],
    properties: dict[str, Any] = {},
    scope: str = "",
    semantic: bool = False,
    n_results: int = 10,
) -> list[dict[str, Any]]:
    """Find notes with multiple filtering options.

    Args:
        text: Text to search for in content, properties, and tags
        tags: Filter by notes having any of these tags
        properties: Filter by property key-value pairs (e.g., {"status": "current"})
        scope: Filter by scope ("global" or "local")
        semantic: Use semantic/vector search instead of text search (requires text)
        n_results: Maximum results for semantic search

    Returns:
        List of matching note dictionaries
    """
    manager = get_manager()
    notes = manager.find(
        text or None,
        tags or None,
        properties or None,
        scope or None,
        semantic,
        n_results,
    )

    results = []
    for note in notes:
        note_dict = note.model_dump()
        # Include similarity score for semantic search results
        if semantic and hasattr(note, "_similarity_score"):
            note_dict["similarity_score"] = note._similarity_score
        results.append(note_dict)

    return results


@mcp.tool()
def extract_data(jmespath_query: str) -> Any:
    """Extract data from notes using JMESPath expressions for flexible data processing.

    Args:
        jmespath_query: JMESPath expression (e.g., "length(@)", "[0].title", "[?properties.status == 'current']")

    Returns:
        Extracted data - could be int, string, list, dict, etc.
    """
    manager = get_manager()
    return manager.extract_data(jmespath_query)


@mcp.tool()
def get_related_notes(
    note_id: str, relationship: str = "supervisors"
) -> list[dict[str, Any]]:
    """Get notes related to this note through a specific relationship.

    Args:
        note_id: UUID or identifier of the source note
        relationship: Property name containing related note UUIDs (e.g., "supervisors", "students")

    Returns:
        List of related note dictionaries
    """
    manager = get_manager()
    notes = manager.get_related_notes(note_id, relationship)
    return [note.model_dump() for note in notes]


@mcp.tool()
def get_linked_notes(note_id: str) -> list[dict[str, Any]]:
    """Get notes that the specified note links to.

    Args:
        note_id: The note ID to find links from

    Returns:
        List of linked note dictionaries
    """
    manager = get_manager()
    # Resolve note_id to UUID first
    note = manager.get_note_by_identifier(note_id)
    if not note:
        return []

    notes = manager.get_linked_notes(note.id)
    return [note.model_dump() for note in notes]


@mcp.tool()
def get_notes_linking_to(target_note_id: str) -> list[dict[str, Any]]:
    """Get notes that link to the specified note.

    Args:
        target_note_id: The note ID to find links to

    Returns:
        List of notes that link to the target
    """
    manager = get_manager()
    # Resolve target_note_id to UUID first
    note = manager.get_note_by_identifier(target_note_id)
    if not note:
        return []

    notes = manager.get_notes_linking_to(note.id)
    return [note.model_dump() for note in notes]


@mcp.tool()
def get_note_paths() -> list[str]:
    """Get all unique note paths in the notes database.

    Returns:
        Sorted list of note paths
    """
    manager = get_manager()
    return manager.get_note_paths()


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
    return f"Notes database refreshed. Loaded {stats['total_notes']} notes."


@mcp.tool()
def get_note_scope(note_id: str) -> str:
    """Get the scope (global or local) of an note.

    Args:
        note_id: The unique identifier of the note

    Returns:
        "global", "local", or None if note not found
    """
    manager = get_manager()
    scope = manager.get_note_scope(note_id)
    if scope is None:
        raise ValueError(f"Note not found: {note_id}")
    return scope


# Resource for browsing notes
@mcp.resource("notes://notes")
def list_notes_resource() -> str:
    """Browse all notes in the notes database."""
    manager = get_manager()
    notes = manager.list_notes()

    lines = ["# Notes Database\n"]

    for note in notes:
        scope = manager.get_note_scope(note.id) or "unknown"
        tag_str = f" [{', '.join(note.tags)}]" if note.tags else ""
        lines.append(f"- **{note.title}** ({scope}){tag_str}")

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
                note.content[:100] + "..." if len(note.content) > 100 else note.content
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
        f"**Total Notes:** {stats['total_notes']}\n",
        f"**Unique Tags:** {stats['unique_tags']}\n",
        f"**Unique Paths:** {stats['unique_paths']}\n",
    ]

    lines.append("\n## Storage Scopes\n")
    for scope, count in sorted(stats["scopes"].items()):
        lines.append(f"- {scope}: {count}")

    lines.append("\n## Storage Locations\n")
    for scope, path in stats["storage_dirs"].items():
        lines.append(f"- {scope}: {path}")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
