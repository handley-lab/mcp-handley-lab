"""Generic note models for the notes management system."""
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Note(BaseModel):
    """A note that can represent any type of information.

    The type is derived from the filesystem path (parent directory).
    The slug is derived from the filename.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str  # Human-readable title for the note
    properties: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    content: str = ""  # Unstructured text for descriptions, notes, etc.
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Runtime-derived fields (not stored in YAML)
    _type: str | None = None
    _slug: str | None = None
    _file_path: str | None = None

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

    @property
    def type(self) -> str | None:
        """Get the primary note type (most specific directory in path)."""
        return self._type

    @property
    def path_tags(self) -> list[str]:
        """Get all path-derived tags in hierarchical order."""
        if not self._file_path:
            return []
        from pathlib import Path

        path = Path(self._file_path)
        return [part for part in path.parent.parts if part not in (".", "notes", "")]

    @property
    def slug(self) -> str | None:
        """Get the note slug derived from filename."""
        return self._slug

    @property
    def file_path(self) -> str | None:
        """Get the file path where this note is stored."""
        return self._file_path

    def set_derived_fields(self, file_path: str) -> None:
        """Set filesystem-derived fields from file path and inherit path tags."""
        from pathlib import Path

        path = Path(file_path)
        self._file_path = file_path
        self._slug = path.stem  # filename without extension

        # Extract all directory components as hierarchical tags
        path_tags = []
        for part in path.parent.parts:
            if part not in (".", "notes", ""):  # Skip root/notes directories
                path_tags.append(part)

        # Set type as the first (most specific) directory
        self._type = path_tags[0] if path_tags else None

        # Add path tags to existing tags (avoid duplicates, maintain hierarchy)
        # Insert path tags at the beginning in order: most general to most specific
        for i, tag in enumerate(path_tags):
            if tag not in self.tags:
                self.tags.insert(i, tag)

        # Update timestamp since we're modifying tags
        if path_tags:
            self.updated_at = datetime.now()

    def get_linked_entities(self) -> list[str]:
        """Get list of note IDs this note links to via pkm: scheme."""
        import re

        linked_ids = []

        # Look for pkm:uuid links in content
        pkm_pattern = r"pkm:([a-f0-9-]{36})"
        content_matches = re.findall(pkm_pattern, self.content)
        linked_ids.extend(content_matches)

        # Look for UUID references in properties
        for value in self.properties.values():
            if isinstance(value, str):
                if self._looks_like_uuid(value):
                    linked_ids.append(value)
                # Also check for pkm: links in string properties
                prop_matches = re.findall(pkm_pattern, value)
                linked_ids.extend(prop_matches)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        if self._looks_like_uuid(item):
                            linked_ids.append(item)
                        # Check for pkm: links in list items
                        item_matches = re.findall(pkm_pattern, item)
                        linked_ids.extend(item_matches)

        return list(set(linked_ids))  # Remove duplicates

    def _looks_like_uuid(self, value: str) -> bool:
        """Simple heuristic to detect UUID-like strings."""
        return (
            len(value) == 36
            and value.count("-") == 4
            and all(c.isalnum() or c == "-" for c in value)
        )
