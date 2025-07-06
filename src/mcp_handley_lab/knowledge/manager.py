"""Knowledge base management with JSON storage."""
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .models import KnowledgeEntry, PersonEntry, ProjectEntry


class KnowledgeManager:
    """Manages a personal knowledge base with global and local JSON storage."""

    def __init__(self, local_storage_dir: str = ".mcp_handley_lab"):
        # Global storage (shared across projects)
        self.global_storage_dir = Path.home() / ".mcp_handley_lab"
        self.global_knowledge_dir = self.global_storage_dir / "knowledge"
        self.global_knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.global_knowledge_file = self.global_knowledge_dir / "knowledge_base.json"

        # Local storage (project-specific)
        self.local_storage_dir = Path(local_storage_dir)
        self.local_knowledge_dir = self.local_storage_dir / "knowledge"
        self.local_knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.local_knowledge_file = self.local_knowledge_dir / "knowledge_base.json"

        self._entries: dict[str, KnowledgeEntry] = {}
        self._entry_scopes: dict[
            str, str
        ] = {}  # Track which scope each entry belongs to
        self._load_knowledge_bases()

    def _json_serializer(self, obj):
        """Custom JSON serializer for dates and datetime objects."""
        if isinstance(obj, date | datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def _load_knowledge_bases(self):
        """Load knowledge bases from both global and local JSON files."""
        # Load global knowledge base first
        self._load_knowledge_file(self.global_knowledge_file, scope="global")

        # Load local knowledge base (overwrites global entries with same ID)
        self._load_knowledge_file(self.local_knowledge_file, scope="local")

    def _load_knowledge_file(self, file_path: Path, scope: str):
        """Load a specific knowledge file."""
        if not file_path.exists():
            self._save_knowledge_file(file_path, scope)
            return

        try:
            with open(file_path) as f:
                data = json.load(f)

            for entry_data in data.get("entries", []):
                entry = self._deserialize_entry(entry_data)
                self._entries[entry.id] = entry
                self._entry_scopes[entry.id] = scope
        except (json.JSONDecodeError, Exception):
            # If file is corrupted, start fresh but keep backup
            backup_file = file_path.with_suffix(".json.backup")
            if file_path.exists():
                file_path.rename(backup_file)
            # Don't clear all entries, just skip this file

    def _deserialize_entry(self, data: dict) -> KnowledgeEntry:
        """Convert dictionary to appropriate KnowledgeEntry subclass."""
        # Parse datetime fields
        if "created_at" in data:
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])

        # Create appropriate subclass based on type
        entry_type = data.get("type", "")
        if entry_type == "person":
            return PersonEntry(**data)
        elif entry_type == "project":
            return ProjectEntry(**data)
        else:
            return KnowledgeEntry(**data)

    def _save_knowledge_file(self, file_path: Path, scope: str):
        """Save entries for a specific scope to its JSON file."""
        # Filter entries by scope
        scope_entries = [
            entry
            for entry_id, entry in self._entries.items()
            if self._entry_scopes.get(entry_id) == scope
        ]

        data = {
            "version": "1.0",
            "entries": [entry.model_dump() for entry in scope_entries],
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, default=self._json_serializer)

    def _save_all_knowledge_bases(self):
        """Save all knowledge bases to their respective files."""
        self._save_knowledge_file(self.global_knowledge_file, "global")
        self._save_knowledge_file(self.local_knowledge_file, "local")

    def create_entry(
        self,
        entry_type: str,
        name: str,
        data: dict[str, Any] = None,
        tags: list[str] = None,
        scope: str = "local",
    ) -> str:
        """Create a new knowledge entry in the specified scope (global or local)."""
        if data is None:
            data = {}
        if tags is None:
            tags = []
        if scope not in ("global", "local"):
            raise ValueError("Scope must be 'global' or 'local'")

        # Create appropriate entry type
        if entry_type == "person":
            entry = PersonEntry(type=entry_type, name=name, data=data, tags=tags)
        elif entry_type == "project":
            entry = ProjectEntry(type=entry_type, name=name, data=data, tags=tags)
        else:
            entry = KnowledgeEntry(type=entry_type, name=name, data=data, tags=tags)

        self._entries[entry.id] = entry
        self._entry_scopes[entry.id] = scope

        # Save to the appropriate scope file
        if scope == "global":
            self._save_knowledge_file(self.global_knowledge_file, "global")
        else:
            self._save_knowledge_file(self.local_knowledge_file, "local")

        return entry.id

    def get_entry(self, entry_id: str) -> KnowledgeEntry | None:
        """Get an entry by ID."""
        return self._entries.get(entry_id)

    def get_entry_scope(self, entry_id: str) -> str | None:
        """Get the scope (global or local) of an entry."""
        return self._entry_scopes.get(entry_id)

    def update_entry(
        self, entry_id: str, data: dict[str, Any] = None, tags: list[str] = None
    ) -> bool:
        """Update an existing entry."""
        entry = self._entries.get(entry_id)
        if not entry:
            return False

        if data is not None:
            entry.data.update(data)
        if tags is not None:
            entry.tags = tags

        entry.updated_at = datetime.now()

        # Save to the appropriate scope file
        scope = self._entry_scopes.get(entry_id, "local")
        if scope == "global":
            self._save_knowledge_file(self.global_knowledge_file, "global")
        else:
            self._save_knowledge_file(self.local_knowledge_file, "local")

        return True

    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry."""
        if entry_id in self._entries:
            # Get scope before deleting
            scope = self._entry_scopes.get(entry_id, "local")

            del self._entries[entry_id]
            del self._entry_scopes[entry_id]

            # Save to the appropriate scope file
            if scope == "global":
                self._save_knowledge_file(self.global_knowledge_file, "global")
            else:
                self._save_knowledge_file(self.local_knowledge_file, "local")

            return True
        return False

    def list_entries(
        self, entry_type: str = None, tags: list[str] = None
    ) -> list[KnowledgeEntry]:
        """List entries with optional filtering."""
        entries = list(self._entries.values())

        if entry_type:
            entries = [e for e in entries if e.type == entry_type]

        if tags:
            entries = [e for e in entries if any(tag in e.tags for tag in tags)]

        return entries

    def search_entries(self, query: str) -> list[KnowledgeEntry]:
        """Simple text search across entries."""
        query_lower = query.lower()
        results = []

        for entry in self._entries.values():
            # Search in name
            if query_lower in entry.name.lower():
                results.append(entry)
                continue

            # Search in tags
            if any(query_lower in tag.lower() for tag in entry.tags):
                results.append(entry)
                continue

            # Search in data values (string fields only)
            for value in entry.data.values():
                if isinstance(value, str) and query_lower in value.lower():
                    results.append(entry)
                    break
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and query_lower in item.lower():
                            results.append(entry)
                            break

        return results

    def get_people(
        self, active_only: bool = True, on_date: date = None
    ) -> list[PersonEntry]:
        """Get all people, optionally filtered by active status."""
        people = [e for e in self._entries.values() if isinstance(e, PersonEntry)]

        if active_only:
            if on_date is None:
                on_date = date.today()
            people = [p for p in people if p.get_current_roles(on_date)]

        return people

    def get_people_by_year(self, year: int) -> list[PersonEntry]:
        """Get all people who were active during a specific year."""
        people = [e for e in self._entries.values() if isinstance(e, PersonEntry)]
        return [p for p in people if p.was_active(year)]

    def get_people_by_role(self, role: str, year: int = None) -> list[PersonEntry]:
        """Get people by role, optionally in a specific year."""
        people = [e for e in self._entries.values() if isinstance(e, PersonEntry)]

        if year:
            people = [p for p in people if p.was_active(year)]

        result = []
        for person in people:
            if year:
                # Check if they had this role during the year
                year_start = date(year, 1, 1)
                year_end = date(year, 12, 31)
                for role_data in person.get_roles():
                    if role_data.get("role") == role:
                        role_start = (
                            date.fromisoformat(role_data["start"])
                            if isinstance(role_data["start"], str)
                            else role_data["start"]
                        )
                        role_end = None
                        if role_data.get("end"):
                            role_end = (
                                date.fromisoformat(role_data["end"])
                                if isinstance(role_data["end"], str)
                                else role_data["end"]
                            )

                        if role_start <= year_end and (
                            role_end is None or role_end >= year_start
                        ):
                            result.append(person)
                            break
            else:
                # Check current roles
                current_roles = person.get_current_roles()
                if any(r.get("role") == role for r in current_roles):
                    result.append(person)

        return result

    def get_emails(self, year: int = None) -> list[str]:
        """Get email addresses, optionally for people active in a specific year."""
        people = self.get_people_by_year(year) if year else self.get_people()

        emails = []
        for person in people:
            email = person.get_email()
            if email:
                emails.append(email)

        return emails

    def get_supervisees(self, supervisor_name: str) -> list[PersonEntry]:
        """Get all people supervised by a given person."""
        people = [e for e in self._entries.values() if isinstance(e, PersonEntry)]
        return [p for p in people if supervisor_name in p.get_supervisors()]

    def get_projects(self, active_only: bool = True) -> list[ProjectEntry]:
        """Get all projects, optionally filtered by active status."""
        projects = [e for e in self._entries.values() if isinstance(e, ProjectEntry)]

        if active_only:
            projects = [p for p in projects if p.is_active()]

        return projects

    def get_project_participants(self, project_name: str) -> list[PersonEntry]:
        """Get all people involved in a specific project."""
        people = [e for e in self._entries.values() if isinstance(e, PersonEntry)]
        return [p for p in people if project_name in p.get_projects()]
