"""Generic note models for the notes management system."""
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Note(BaseModel):
    """A note that can represent any type of information.

    Pure data model - filesystem organization is handled by storage layer.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str  # Human-readable title for the note
    properties: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    content: str = ""  # Unstructured text for descriptions, notes, etc.
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def get_property(self, key: str, default: Any = None) -> Any:
        """Get a property value, returning default if not found."""
        return self.properties.get(key, default)

    def set_property(self, key: str, value: Any) -> None:
        """Set a property value and update timestamp."""
        self.properties[key] = value
        self.updated_at = datetime.now()

    def has_tag(self, tag: str) -> bool:
        """Check if this note has a specific tag."""
        return tag in self.tags

    def add_tag(self, tag: str) -> None:
        """Add a tag to this note."""
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.now()

    def remove_tag(self, tag: str) -> None:
        """Remove a tag from this note."""
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.now()

    def has_any_tags(self, tags: list[str]) -> bool:
        """Check if this note has any of the specified tags."""
        return any(tag in self.tags for tag in tags)

    def has_all_tags(self, tags: list[str]) -> bool:
        """Check if this note has all of the specified tags."""
        return all(tag in self.tags for tag in tags)

    def inherit_path_tags(self, file_path: str) -> None:
        """Inherit hierarchical tags from filesystem path."""
        from pathlib import Path

        path = Path(file_path)
        path_tags = []
        for part in path.parent.parts:
            if part not in (".", "notes", ""):
                path_tags.append(part)

        for i, tag in enumerate(path_tags):
            if tag not in self.tags:
                self.tags.insert(i, tag)

        if path_tags:
            self.updated_at = datetime.now()

    def get_linked_notes(self) -> list[str]:
        """Get list of note IDs this note links to via pkm: scheme."""

        linked_ids = []

        # Look for UUID references in properties
        for value in self.properties.values():
            if isinstance(value, str):
                if self._looks_like_uuid(value):
                    linked_ids.append(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and self._looks_like_uuid(item):
                        linked_ids.append(item)

        return list(set(linked_ids))

    def _looks_like_uuid(self, value: str) -> bool:
        """Simple heuristic to detect UUID-like strings."""
        return (
            len(value) == 36
            and value.count("-") == 4
            and all(c.isalnum() or c == "-" for c in value)
        )
