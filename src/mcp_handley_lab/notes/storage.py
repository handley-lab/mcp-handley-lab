"""YAML-based note storage with file-per-note pattern."""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from .models import Note


class YAMLNoteStorage:
    """Manages YAML file storage with one note per file."""

    def __init__(self, storage_dir: str = ".mcp_handley_lab/notes"):
        self.storage_dir = Path(storage_dir)
        self.notes_dir = self.storage_dir / "notes"
        self.notes_dir.mkdir(parents=True, exist_ok=True)

        # Configure YAML with comment preservation
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.default_flow_style = False

    def _entity_file_path(
        self, note_id: str, note_type: str = None, slug: str = None
    ) -> Path:
        """Get the file path for a note.

        Args:
            note_id: UUID of the note
            note_type: Type directory (e.g., 'person', 'project')
            slug: Human-readable slug for filename
        """
        if note_type and slug:
            # Use type/slug.yaml structure
            type_dir = self.notes_dir / note_type
            type_dir.mkdir(parents=True, exist_ok=True)
            return type_dir / f"{slug}.yaml"
        else:
            # Fallback to UUID.yaml in root (for backward compatibility)
            return self.notes_dir / f"{note_id}.yaml"

    def _serialize_entity(self, note: Note) -> dict[str, Any]:
        """Convert Note to YAML-serializable dict."""
        data = note.model_dump()

        # Convert datetime objects to ISO strings
        if isinstance(data.get("created_at"), datetime):
            data["created_at"] = data["created_at"].isoformat()
        if isinstance(data.get("updated_at"), datetime):
            data["updated_at"] = data["updated_at"].isoformat()

        return data

    def _deserialize_entity(self, data: dict[str, Any]) -> Note:
        """Convert YAML dict to Note."""
        # Parse datetime fields
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])

        return Note(**data)

    def save_note(self, note: Note, note_type: str = None, slug: str = None) -> None:
        """Save a note to a YAML file.

        Args:
            note: The note to save
            note_type: Type directory (can be hierarchical like 'person/researcher')
            slug: Slug for filename (required for new notes)
        """
        # Determine file path
        if note_type and slug:
            file_path = self._entity_file_path(note.id, note_type, slug)
        elif note.file_path:
            # Update existing note at its current location
            file_path = self.notes_dir / note.file_path
        else:
            # Fallback to UUID.yaml
            file_path = self._entity_file_path(note.id)

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Inherit tags from filesystem path before saving
        if note_type and slug:
            relative_path = str(file_path.relative_to(self.notes_dir))
            note.inherit_path_tags(relative_path)

        data = self._serialize_entity(note)
        with open(file_path, "w") as f:
            self.yaml.dump(data, f)

    def load_note(self, note_id: str) -> Note | None:
        """Load a note from its YAML file by UUID."""
        # First try to find by UUID in index
        file_path = self._find_file_by_uuid(note_id)
        if not file_path:
            # Fallback to old UUID.yaml format
            file_path = self._entity_file_path(note_id)

        if not file_path.exists():
            return None

        with open(file_path) as f:
            data = self.yaml.load(f)

        note = self._deserialize_entity(data)
        # Inherit tags from filesystem path for consistency
        relative_path = str(file_path.relative_to(self.notes_dir))
        note.inherit_path_tags(relative_path)
        return note

    def load_note_by_slug(self, note_type: str, slug: str) -> Note | None:
        """Load a note by its type and slug."""
        file_path = self.notes_dir / note_type / f"{slug}.yaml"
        if not file_path.exists():
            return None

        with open(file_path) as f:
            data = self.yaml.load(f)

        note = self._deserialize_entity(data)
        # Inherit tags from filesystem path for consistency
        relative_path = str(file_path.relative_to(self.notes_dir))
        note.inherit_path_tags(relative_path)
        return note

    def _find_file_by_uuid(self, uuid: str) -> Path | None:
        """Find file path by UUID by scanning all YAML files."""
        for yaml_file in self.notes_dir.rglob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    data = self.yaml.load(f)
                if data and data.get("id") == uuid:
                    return yaml_file
            except Exception:
                continue
        return None

    def delete_note(self, note_id: str) -> bool:
        """Delete a note's YAML file."""
        # Find the actual file path
        file_path = self._find_file_by_uuid(note_id)
        if not file_path:
            # Try fallback path
            file_path = self._entity_file_path(note_id)

        if file_path and file_path.exists():
            file_path.unlink()
            return True
        return False

    def list_note_ids(self) -> list[str]:
        """List all note IDs by scanning YAML files."""
        ids = []
        for yaml_file in self.notes_dir.rglob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    data = self.yaml.load(f)
                if data and "id" in data:
                    ids.append(data["id"])
            except Exception:
                continue
        return ids

    def load_all_notes(self) -> dict[str, Note]:
        """Load all notes into memory."""
        notes = {}
        for yaml_file in self.notes_dir.rglob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    data = self.yaml.load(f)
                if data and "id" in data:
                    note = self._deserialize_entity(data)
                    # Inherit tags from filesystem path
                    relative_path = str(yaml_file.relative_to(self.notes_dir))
                    note.inherit_path_tags(relative_path)
                    notes[note.id] = note
            except Exception:
                continue
        return notes

    def entity_exists(self, note_id: str) -> bool:
        """Check if an note file exists."""
        # Try to find by UUID first
        file_path = self._find_file_by_uuid(note_id)
        if file_path and file_path.exists():
            return True
        # Fallback to old UUID.yaml format
        return self._entity_file_path(note_id).exists()

    def backup_entity(self, note_id: str) -> bool:
        """Create a backup of an note file."""
        # Find the actual file path by UUID
        file_path = self._find_file_by_uuid(note_id)
        if not file_path or not file_path.exists():
            # Fallback to old UUID.yaml format
            file_path = self._entity_file_path(note_id)
            if not file_path.exists():
                return False

        backup_path = file_path.with_suffix(
            f".yaml.backup_{int(datetime.now().timestamp())}"
        )
        backup_path.write_text(file_path.read_text())
        return True


class GlobalLocalYAMLStorage:
    """Manages both global and local YAML note storage."""

    def __init__(self, local_storage_dir: str = ".mcp_handley_lab"):
        # Global storage (shared across projects)
        global_dir = Path.home() / ".mcp_handley_lab"
        self.global_storage = YAMLNoteStorage(str(global_dir))

        # Local storage (project-specific)
        local_dir = Path(local_storage_dir)
        self.local_storage = YAMLNoteStorage(str(local_dir))

        self._entity_scopes: dict[str, str] = {}
        self._load_scope_mappings()

    def _scope_mapping_file(self, scope: str) -> Path:
        """Get the scope mapping file path."""
        if scope == "global":
            return self.global_storage.storage_dir / "scope_mapping.json"
        else:
            return self.local_storage.storage_dir / "scope_mapping.json"

    def _load_scope_mappings(self):
        """Load note scope mappings from both storages."""
        # Load global scope mappings
        global_mapping_file = self._scope_mapping_file("global")
        if global_mapping_file.exists():
            with open(global_mapping_file) as f:
                global_mappings = json.load(f)
                for note_id in global_mappings.get("notes", []):
                    self._entity_scopes[note_id] = "global"

        # Load local scope mappings
        local_mapping_file = self._scope_mapping_file("local")
        if local_mapping_file.exists():
            with open(local_mapping_file) as f:
                local_mappings = json.load(f)
                for note_id in local_mappings.get("notes", []):
                    self._entity_scopes[note_id] = "local"

        # Sync with actual files (notes that exist but aren't in mappings)
        for note_id in self.global_storage.list_note_ids():
            if note_id not in self._entity_scopes:
                self._entity_scopes[note_id] = "global"

        for note_id in self.local_storage.list_note_ids():
            if note_id not in self._entity_scopes:
                self._entity_scopes[note_id] = "local"

    def _save_scope_mappings(self):
        """Save note scope mappings to both files."""
        global_entities = [
            eid for eid, scope in self._entity_scopes.items() if scope == "global"
        ]
        local_entities = [
            eid for eid, scope in self._entity_scopes.items() if scope == "local"
        ]

        # Save global mappings
        global_mapping_file = self._scope_mapping_file("global")
        global_mapping_file.parent.mkdir(parents=True, exist_ok=True)
        with open(global_mapping_file, "w") as f:
            json.dump({"notes": global_entities}, f, indent=2)

        # Save local mappings
        local_mapping_file = self._scope_mapping_file("local")
        local_mapping_file.parent.mkdir(parents=True, exist_ok=True)
        with open(local_mapping_file, "w") as f:
            json.dump({"notes": local_entities}, f, indent=2)

    def save_note(
        self, note: Note, scope: str = "local", note_type: str = None, slug: str = None
    ) -> None:
        """Save a note to the specified scope.

        Args:
            note: The note to save
            scope: 'global' or 'local' storage
            note_type: Type directory (required for new notes)
            slug: Slug for filename (required for new notes)
        """
        if scope not in ("global", "local"):
            raise ValueError("Scope must be 'global' or 'local'")

        storage = self.global_storage if scope == "global" else self.local_storage
        storage.save_note(note, note_type, slug)
        self._entity_scopes[note.id] = scope
        self._save_scope_mappings()

    def load_note(self, note_id: str) -> Note | None:
        """Load a note from appropriate storage (local takes precedence)."""
        # Check local first (takes precedence)
        note = self.local_storage.load_note(note_id)
        if note:
            self._entity_scopes[note_id] = "local"
            return note

        # Check global
        note = self.global_storage.load_note(note_id)
        if note:
            self._entity_scopes[note_id] = "global"
            return note

        return None

    def load_note_by_slug(self, note_type: str, slug: str) -> Note | None:
        """Load a note by type and slug (local takes precedence)."""
        # Check local first
        note = self.local_storage.load_note_by_slug(note_type, slug)
        if note:
            self._entity_scopes[note.id] = "local"
            return note

        # Check global
        note = self.global_storage.load_note_by_slug(note_type, slug)
        if note:
            self._entity_scopes[note.id] = "global"
            return note

        return None

    def delete_note(self, note_id: str) -> bool:
        """Delete an note from its appropriate storage."""
        scope = self._entity_scopes.get(note_id)
        if not scope:
            # Try both storages if scope unknown
            success = self.local_storage.delete_note(note_id)
            success = self.global_storage.delete_note(note_id) or success
        else:
            storage = self.global_storage if scope == "global" else self.local_storage
            success = storage.delete_note(note_id)

        if success and note_id in self._entity_scopes:
            del self._entity_scopes[note_id]
            self._save_scope_mappings()

        return success

    def get_note_scope(self, note_id: str) -> str | None:
        """Get the scope of an note."""
        return self._entity_scopes.get(note_id)

    def list_all_note_ids(self) -> list[str]:
        """List all note IDs from both storages."""
        all_ids = set(self.global_storage.list_note_ids())
        all_ids.update(self.local_storage.list_note_ids())
        return list(all_ids)

    def load_all_notes(self) -> dict[str, Note]:
        """Load all notes from both storages (local takes precedence)."""
        notes = {}

        # Load global notes first
        global_entities = self.global_storage.load_all_notes()
        notes.update(global_entities)

        # Load local notes (overwrites global with same ID)
        local_entities = self.local_storage.load_all_notes()
        notes.update(local_entities)

        # Update scope mappings
        for note_id, _entity in notes.items():
            if note_id in local_entities:
                self._entity_scopes[note_id] = "local"
            elif note_id in global_entities:
                self._entity_scopes[note_id] = "global"

        return notes
