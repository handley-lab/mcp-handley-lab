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
        self.entities_dir = self.storage_dir / "notes"
        self.entities_dir.mkdir(parents=True, exist_ok=True)

        # Configure YAML with comment preservation
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.default_flow_style = False

    def _entity_file_path(self, entity_id: str) -> Path:
        """Get the file path for an note."""
        return self.entities_dir / f"{entity_id}.yaml"

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

    def save_note(self, note: Note) -> bool:
        """Save an note to a YAML file."""
        try:
            file_path = self._entity_file_path(note.id)
            data = self._serialize_entity(note)

            with open(file_path, "w") as f:
                self.yaml.dump(data, f)

            return True
        except Exception:
            return False

    def load_entity(self, entity_id: str) -> Note | None:
        """Load an note from its YAML file."""
        try:
            file_path = self._entity_file_path(entity_id)
            if not file_path.exists():
                return None

            with open(file_path) as f:
                data = self.yaml.load(f)

            return self._deserialize_entity(data)
        except Exception:
            return None

    def delete_note(self, entity_id: str) -> bool:
        """Delete an note's YAML file."""
        try:
            file_path = self._entity_file_path(entity_id)
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception:
            return False

    def list_entity_ids(self) -> list[str]:
        """List all note IDs (filenames without .yaml extension)."""
        try:
            return [f.stem for f in self.entities_dir.glob("*.yaml")]
        except Exception:
            return []

    def load_all_entities(self) -> dict[str, Note]:
        """Load all notes into memory."""
        notes = {}
        for entity_id in self.list_entity_ids():
            note = self.load_entity(entity_id)
            if note:
                notes[entity_id] = note
        return notes

    def entity_exists(self, entity_id: str) -> bool:
        """Check if an note file exists."""
        return self._entity_file_path(entity_id).exists()

    def backup_entity(self, entity_id: str) -> bool:
        """Create a backup of an note file."""
        try:
            file_path = self._entity_file_path(entity_id)
            if not file_path.exists():
                return False

            backup_path = file_path.with_suffix(
                f".yaml.backup_{int(datetime.now().timestamp())}"
            )
            backup_path.write_text(file_path.read_text())
            return True
        except Exception:
            return False


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
            try:
                with open(global_mapping_file) as f:
                    global_mappings = json.load(f)
                    for entity_id in global_mappings.get("notes", []):
                        self._entity_scopes[entity_id] = "global"
            except Exception:
                pass

        # Load local scope mappings
        local_mapping_file = self._scope_mapping_file("local")
        if local_mapping_file.exists():
            try:
                with open(local_mapping_file) as f:
                    local_mappings = json.load(f)
                    for entity_id in local_mappings.get("notes", []):
                        self._entity_scopes[entity_id] = "local"
            except Exception:
                pass

        # Sync with actual files (notes that exist but aren't in mappings)
        for entity_id in self.global_storage.list_entity_ids():
            if entity_id not in self._entity_scopes:
                self._entity_scopes[entity_id] = "global"

        for entity_id in self.local_storage.list_entity_ids():
            if entity_id not in self._entity_scopes:
                self._entity_scopes[entity_id] = "local"

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

    def save_note(self, note: Note, scope: str = "local") -> bool:
        """Save an note to the specified scope."""
        if scope not in ("global", "local"):
            raise ValueError("Scope must be 'global' or 'local'")

        storage = self.global_storage if scope == "global" else self.local_storage
        success = storage.save_note(note)

        if success:
            self._entity_scopes[note.id] = scope
            self._save_scope_mappings()

        return success

    def load_entity(self, entity_id: str) -> Note | None:
        """Load an note from appropriate storage (local takes precedence)."""
        # Check local first (takes precedence)
        note = self.local_storage.load_entity(entity_id)
        if note:
            self._entity_scopes[entity_id] = "local"
            return note

        # Check global
        note = self.global_storage.load_entity(entity_id)
        if note:
            self._entity_scopes[entity_id] = "global"
            return note

        return None

    def delete_note(self, entity_id: str) -> bool:
        """Delete an note from its appropriate storage."""
        scope = self._entity_scopes.get(entity_id)
        if not scope:
            # Try both storages if scope unknown
            success = self.local_storage.delete_note(entity_id)
            success = self.global_storage.delete_note(entity_id) or success
        else:
            storage = self.global_storage if scope == "global" else self.local_storage
            success = storage.delete_note(entity_id)

        if success and entity_id in self._entity_scopes:
            del self._entity_scopes[entity_id]
            self._save_scope_mappings()

        return success

    def get_note_scope(self, entity_id: str) -> str | None:
        """Get the scope of an note."""
        return self._entity_scopes.get(entity_id)

    def list_all_entity_ids(self) -> list[str]:
        """List all note IDs from both storages."""
        all_ids = set(self.global_storage.list_entity_ids())
        all_ids.update(self.local_storage.list_entity_ids())
        return list(all_ids)

    def load_all_entities(self) -> dict[str, Note]:
        """Load all notes from both storages (local takes precedence)."""
        notes = {}

        # Load global notes first
        global_entities = self.global_storage.load_all_entities()
        notes.update(global_entities)

        # Load local notes (overwrites global with same ID)
        local_entities = self.local_storage.load_all_entities()
        notes.update(local_entities)

        # Update scope mappings
        for entity_id, _entity in notes.items():
            if entity_id in local_entities:
                self._entity_scopes[entity_id] = "local"
            elif entity_id in global_entities:
                self._entity_scopes[entity_id] = "global"

        return notes
