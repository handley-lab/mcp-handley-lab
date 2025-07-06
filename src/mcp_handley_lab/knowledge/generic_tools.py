"""Generic MCP tools for knowledge management."""
from typing import Any

from mcp.server.fastmcp import FastMCP

from .generic_manager import GenericKnowledgeManager

# Initialize the FastMCP server
mcp = FastMCP("Generic Knowledge")

# Global manager instance
_manager: GenericKnowledgeManager | None = None


def get_manager() -> GenericKnowledgeManager:
    """Get or create the knowledge manager instance."""
    global _manager
    if _manager is None:
        _manager = GenericKnowledgeManager()
    return _manager


@mcp.tool()
def create_entity(
    entity_type: str,
    properties: dict[str, Any] = None,
    tags: list[str] = None,
    content: str = "",
    scope: str = "local",
) -> str:
    """Create a new knowledge entity.

    Args:
        entity_type: Type of entity (e.g., "person", "project", "attic_item", "idea")
        properties: Dictionary of structured properties
        tags: List of tags for categorization
        content: Unstructured text content/description
        scope: Storage scope - "global" (shared) or "local" (project-specific)

    Returns:
        The ID of the created entity
    """
    if scope not in ("global", "local"):
        raise ValueError("Scope must be 'global' or 'local'")

    manager = get_manager()
    return manager.create_entity(entity_type, properties, tags, content, scope)


@mcp.tool()
def get_entity(entity_id: str) -> dict[str, Any] | None:
    """Get an entity by its ID.

    Args:
        entity_id: The unique identifier of the entity

    Returns:
        Entity data as a dictionary, or None if not found
    """
    manager = get_manager()
    entity = manager.get_entity(entity_id)
    return entity.model_dump() if entity else None


@mcp.tool()
def update_entity(
    entity_id: str,
    properties: dict[str, Any] = None,
    tags: list[str] = None,
    content: str = None,
) -> bool:
    """Update an existing entity.

    Args:
        entity_id: The unique identifier of the entity
        properties: Dictionary of properties to update/add
        tags: New list of tags (replaces existing)
        content: New content (replaces existing)

    Returns:
        True if update succeeded, False otherwise
    """
    manager = get_manager()
    return manager.update_entity(entity_id, properties, tags, content)


@mcp.tool()
def delete_entity(entity_id: str) -> bool:
    """Delete an entity.

    Args:
        entity_id: The unique identifier of the entity

    Returns:
        True if deletion succeeded, False otherwise
    """
    manager = get_manager()
    return manager.delete_entity(entity_id)


@mcp.tool()
def list_entities(
    entity_type: str = None, tags: list[str] = None, scope: str = None
) -> list[dict[str, Any]]:
    """List entities with optional filtering.

    Args:
        entity_type: Filter by entity type
        tags: Filter by entities having any of these tags
        scope: Filter by scope ("global" or "local")

    Returns:
        List of entity dictionaries
    """
    manager = get_manager()
    entities = manager.list_entities(entity_type, tags, scope)
    return [entity.model_dump() for entity in entities]


@mcp.tool()
def search_entities(query: str) -> list[dict[str, Any]]:
    """Search entities by text across content, properties, and tags.

    Args:
        query: Text to search for

    Returns:
        List of matching entity dictionaries
    """
    manager = get_manager()
    entities = manager.search_entities_text(query)
    return [entity.model_dump() for entity in entities]


@mcp.tool()
def search_entities_semantic(
    query: str, n_results: int = 10, entity_type: str = None, tags: list[str] = None
) -> list[dict[str, Any]]:
    """Search entities using semantic similarity (requires ChromaDB).

    Args:
        query: Text query for semantic similarity
        n_results: Maximum number of results to return
        entity_type: Filter by entity type
        tags: Filter by entities having any of these tags

    Returns:
        List of entity dictionaries with similarity scores
    """
    manager = get_manager()
    entities = manager.search_entities_semantic(query, n_results, entity_type, tags)

    results = []
    for entity in entities:
        entity_dict = entity.model_dump()
        # Add similarity score if available
        if hasattr(entity, "_similarity_score"):
            entity_dict["similarity_score"] = entity._similarity_score
        results.append(entity_dict)

    return results


@mcp.tool()
def query_entities(jmespath_query: str) -> list[dict[str, Any]]:
    """Query entities using JMESPath expressions for structured queries.

    Args:
        jmespath_query: JMESPath expression (e.g., "[?type=='person'].properties.name")

    Returns:
        Query results
    """
    manager = get_manager()
    return manager.query_entities_jmespath(jmespath_query)


@mcp.tool()
def get_entities_by_property(
    property_name: str, property_value: Any
) -> list[dict[str, Any]]:
    """Get entities with a specific property value.

    Args:
        property_name: Name of the property
        property_value: Value to match

    Returns:
        List of matching entity dictionaries
    """
    manager = get_manager()
    entities = manager.get_entities_by_property(property_name, property_value)
    return [entity.model_dump() for entity in entities]


@mcp.tool()
def get_linked_entities(entity_id: str) -> list[dict[str, Any]]:
    """Get entities that the specified entity links to.

    Args:
        entity_id: The entity ID to find links from

    Returns:
        List of linked entity dictionaries
    """
    manager = get_manager()
    entities = manager.get_linked_entities(entity_id)
    return [entity.model_dump() for entity in entities]


@mcp.tool()
def get_entities_linking_to(target_entity_id: str) -> list[dict[str, Any]]:
    """Get entities that link to the specified entity.

    Args:
        target_entity_id: The entity ID to find links to

    Returns:
        List of entities that link to the target
    """
    manager = get_manager()
    entities = manager.get_entities_linking_to(target_entity_id)
    return [entity.model_dump() for entity in entities]


@mcp.tool()
def get_entity_types() -> list[str]:
    """Get all unique entity types in the knowledge base.

    Returns:
        Sorted list of entity types
    """
    manager = get_manager()
    return manager.get_entity_types()


@mcp.tool()
def get_all_tags() -> list[str]:
    """Get all unique tags across all entities.

    Returns:
        Sorted list of tags
    """
    manager = get_manager()
    return manager.get_all_tags()


@mcp.tool()
def get_knowledge_stats() -> dict[str, Any]:
    """Get statistics about the knowledge base.

    Returns:
        Dictionary with statistics (counts, types, etc.)
    """
    manager = get_manager()
    return manager.get_stats()


@mcp.tool()
def refresh_knowledge_base() -> str:
    """Refresh the in-memory database from YAML files.

    Returns:
        Confirmation message
    """
    manager = get_manager()
    manager.refresh_from_files()
    stats = manager.get_stats()
    return f"Knowledge base refreshed. Loaded {stats['total_entities']} entities."


@mcp.tool()
def get_entity_scope(entity_id: str) -> str | None:
    """Get the scope (global or local) of an entity.

    Args:
        entity_id: The unique identifier of the entity

    Returns:
        "global", "local", or None if entity not found
    """
    manager = get_manager()
    return manager.get_entity_scope(entity_id)


# Resource for browsing entities
@mcp.resource("knowledge://entities")
def list_entities_resource() -> str:
    """Browse all entities in the knowledge base."""
    manager = get_manager()
    entities = manager.list_entities()

    if not entities:
        return "No entities found in the knowledge base."

    lines = ["# Knowledge Base Entities\n"]

    # Group by type
    by_type = {}
    for entity in entities:
        entity_type = entity.type
        if entity_type not in by_type:
            by_type[entity_type] = []
        by_type[entity_type].append(entity)

    for entity_type, type_entities in sorted(by_type.items()):
        lines.append(f"## {entity_type.title()} ({len(type_entities)})\n")

        for entity in type_entities:
            scope = manager.get_entity_scope(entity.id) or "unknown"
            tag_str = f" [{', '.join(entity.tags)}]" if entity.tags else ""
            lines.append(f"- **{entity.id}** ({scope}){tag_str}")

            # Show key properties
            if entity.properties:
                key_props = []
                for key, value in list(entity.properties.items())[:3]:  # Show first 3
                    if isinstance(value, str) and len(value) < 50:
                        key_props.append(f"{key}: {value}")
                if key_props:
                    lines.append(f"  - {'; '.join(key_props)}")

            # Show content preview
            if entity.content:
                preview = (
                    entity.content[:100] + "..."
                    if len(entity.content) > 100
                    else entity.content
                )
                lines.append(f"  - {preview}")

            lines.append("")

    return "\n".join(lines)


@mcp.resource("knowledge://stats")
def knowledge_stats_resource() -> str:
    """View knowledge base statistics."""
    manager = get_manager()
    stats = manager.get_stats()

    lines = [
        "# Knowledge Base Statistics\n",
        f"**Total Entities:** {stats['total_entities']}\n",
        f"**Unique Tags:** {stats['unique_tags']}\n",
        "## Entity Types\n",
    ]

    for entity_type, count in sorted(stats["entity_types"].items()):
        lines.append(f"- {entity_type}: {count}")

    lines.append("\n## Storage Scopes\n")
    for scope, count in sorted(stats["scopes"].items()):
        lines.append(f"- {scope}: {count}")

    lines.append("\n## Storage Locations\n")
    for scope, path in stats["storage_dirs"].items():
        lines.append(f"- {scope}: {path}")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
