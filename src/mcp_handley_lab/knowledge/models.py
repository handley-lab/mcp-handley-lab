"""Data models for the knowledge management system."""
from datetime import date, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TimeSpan(BaseModel):
    """A time period with start and optional end date."""

    start: date
    end: date | None = None

    def is_active(self, on_date: date | None = None) -> bool:
        """Check if this timespan is active on a given date (default: today)."""
        if on_date is None:
            on_date = date.today()

        if on_date < self.start:
            return False
        if self.end is not None and on_date > self.end:
            return False
        return True


class KnowledgeEntry(BaseModel):
    """A generic knowledge entry that can represent any type of information."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str  # e.g., "person", "project", "note", "contact"
    name: str
    data: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def get_field(self, field_name: str, default: Any = None) -> Any:
        """Get a field from the data dictionary."""
        return self.data.get(field_name, default)

    def set_field(self, field_name: str, value: Any) -> None:
        """Set a field in the data dictionary."""
        self.data[field_name] = value
        self.updated_at = datetime.now()

    def has_tag(self, tag: str) -> bool:
        """Check if this entry has a specific tag."""
        return tag in self.tags

    def add_tag(self, tag: str) -> None:
        """Add a tag to this entry."""
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.now()


class PersonEntry(KnowledgeEntry):
    """Specialized entry for people with role and timespan handling."""

    def __init__(self, **data):
        super().__init__(**data)
        if self.type != "person":
            self.type = "person"

    def get_roles(self) -> list[dict]:
        """Get all roles for this person."""
        return self.data.get("roles", [])

    def get_current_roles(self, on_date: date | None = None) -> list[dict]:
        """Get roles that are active on a given date."""
        if on_date is None:
            on_date = date.today()

        current_roles = []
        for role_data in self.get_roles():
            if "start" in role_data:
                timespan = TimeSpan(
                    start=date.fromisoformat(role_data["start"])
                    if isinstance(role_data["start"], str)
                    else role_data["start"],
                    end=date.fromisoformat(role_data["end"])
                    if role_data.get("end") and isinstance(role_data["end"], str)
                    else role_data.get("end"),
                )
                if timespan.is_active(on_date):
                    current_roles.append(role_data)

        return current_roles

    def was_active(self, year: int) -> bool:
        """Check if this person was active during a given year."""
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)

        for role_data in self.get_roles():
            if "start" in role_data:
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

                # Check if role overlaps with the year
                if role_start <= year_end and (
                    role_end is None or role_end >= year_start
                ):
                    return True

        return False

    def get_email(self) -> str | None:
        """Get the email address for this person."""
        return self.data.get("email")

    def get_supervisors(self) -> list[str]:
        """Get list of supervisor names/IDs."""
        return self.data.get("supervisors", [])

    def get_projects(self) -> list[str]:
        """Get list of project names/IDs this person is involved in."""
        return self.data.get("projects", [])


class ProjectEntry(KnowledgeEntry):
    """Specialized entry for projects."""

    def __init__(self, **data):
        super().__init__(**data)
        if self.type != "project":
            self.type = "project"

    def get_participants(self) -> list[str]:
        """Get list of participant names/IDs."""
        return self.data.get("participants", [])

    def get_timespan(self) -> TimeSpan | None:
        """Get the project timespan if available."""
        start_date = self.data.get("start_date")
        end_date = self.data.get("end_date")

        if start_date:
            start = (
                date.fromisoformat(start_date)
                if isinstance(start_date, str)
                else start_date
            )
            end = None
            if end_date:
                end = (
                    date.fromisoformat(end_date)
                    if isinstance(end_date, str)
                    else end_date
                )
            return TimeSpan(start=start, end=end)

        return None

    def is_active(self, on_date: date | None = None) -> bool:
        """Check if this project is active on a given date."""
        timespan = self.get_timespan()
        if timespan:
            return timespan.is_active(on_date)

        # If no timespan, check status
        status = self.data.get("status", "").lower()
        return status in ["active", "ongoing", "current"]
