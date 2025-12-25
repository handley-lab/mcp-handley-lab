"""Mutt aliases tool for managing email address book via MCP."""

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp


class Contact(BaseModel):
    """Contact information."""

    alias: str
    email: str
    name: str = ""


class ContactResult(BaseModel):
    """Result of contact operation."""

    action: str
    message: str
    matches: list[Contact] = Field(default_factory=list)


def _parse_alias_line(line: str) -> Contact:
    """Parse a mutt alias line into a Contact object."""
    line = line.strip()
    if not line.startswith("alias "):
        raise ValueError(f"Invalid alias line: {line}")

    match = re.match(r'alias\s+(\S+)\s+"([^"]+)"\s*<([^>]+)>', line)
    if match:
        alias, name, email = match.groups()
        return Contact(alias=alias, email=email, name=name)

    match = re.match(r"alias\s+(\S+)\s+(\S+)", line)
    if match:
        alias, email = match.groups()
        name = line.split("#", 1)[1].strip() if "#" in line else ""
        return Contact(alias=alias, email=email, name=name)

    raise ValueError(f"Could not parse alias line: {line}")


def _get_alias_file(config_file: str = "") -> Path:
    """Get mutt alias file path from mutt configuration."""
    cmd = ["mutt", "-Q", "alias_file"]
    if config_file:
        cmd.extend(["-F", config_file])

    stdout, _ = run_command(cmd)
    result = stdout.decode().strip()
    path = result.split("=")[1].strip("\"'")
    if path.startswith("~"):
        path = str(Path.home()) + path[1:]
    return Path(path)


def _get_all_contacts(config_file: str = "") -> list[Contact]:
    """Get all contacts from mutt address book."""
    alias_file = _get_alias_file(config_file)

    try:
        content = alias_file.read_text()
    except FileNotFoundError:
        return []

    contacts = []
    for line in content.splitlines():
        if line.strip().startswith("alias "):
            contacts.append(_parse_alias_line(line))
    return contacts


def _find_contacts(
    query: str, max_results: int, config_file: str = ""
) -> list[Contact]:
    """Find contacts using simple fuzzy matching."""
    contacts = _get_all_contacts(config_file)
    query_lower = query.lower()

    matches = [
        c
        for c in contacts
        if query_lower in c.alias.lower()
        or query_lower in c.email.lower()
        or query_lower in c.name.lower()
    ]
    return matches[:max_results]


@mcp.tool(
    description="""Manage Mutt address book contacts. Actions: 'find' (search), 'add' (create), 'remove' (delete). Find uses fuzzy matching on alias/name/email."""
)
def contacts(
    action: Literal["find", "add", "remove"] = Field(
        ...,
        description="Action: 'find' (search contacts), 'add' (create contact), 'remove' (delete contact).",
    ),
    query: str = Field(
        default="",
        description="For 'find': search term. For 'add'/'remove': the alias.",
    ),
    email: str = Field(
        default="",
        description="For 'add': the email address.",
    ),
    name: str = Field(
        default="",
        description="For 'add': optional display name.",
    ),
    max_results: int = Field(
        default=10,
        description="For 'find': maximum results to return.",
        gt=0,
    ),
    config_file: str = Field(
        default="",
        description="Optional path to mutt config file.",
    ),
) -> ContactResult:
    """Unified contact management."""
    if action == "find":
        if not query:
            raise ValueError("Query required for find action")
        matches = _find_contacts(query, max_results, config_file)
        return ContactResult(
            action="find",
            message=f"Found {len(matches)} contact(s)",
            matches=matches,
        )

    if action == "add":
        if not query or not email:
            raise ValueError("Alias (query) and email required for add action")

        alias = query.lower()
        alias_file = _get_alias_file(config_file)

        if "@" in email:
            line = (
                f'alias {alias} "{name}" <{email}>\n'
                if name
                else f"alias {alias} {email}\n"
            )
        else:
            line = (
                f"alias {alias} {email}  # {name}\n"
                if name
                else f"alias {alias} {email}\n"
            )

        alias_file.parent.mkdir(parents=True, exist_ok=True)
        with open(alias_file, "a") as f:
            f.write(line)

        return ContactResult(
            action="add",
            message=f"Added contact: {alias}",
            matches=[Contact(alias=alias, email=email, name=name)],
        )

    if action == "remove":
        if not query:
            raise ValueError("Alias (query) required for remove action")

        alias = query.lower()
        alias_file = _get_alias_file(config_file)

        # Let FileNotFoundError propagate if file doesn't exist
        lines = alias_file.read_text().splitlines(keepends=True)
        target = f"alias {alias} "
        filtered = [line for line in lines if not line.strip().startswith(target)]

        if len(filtered) == len(lines):
            # Try fuzzy match
            matches = _find_contacts(alias, 5, config_file)
            if not matches:
                raise ValueError(f"Contact '{alias}' not found")
            if len(matches) > 1:
                names = ", ".join(m.alias for m in matches)
                raise ValueError(f"Multiple matches: {names}. Be more specific.")
            alias = matches[0].alias
            target = f"alias {alias} "
            filtered = [line for line in lines if not line.strip().startswith(target)]

        alias_file.write_text("".join(filtered))
        return ContactResult(action="remove", message=f"Removed contact: {alias}")

    raise ValueError(f"Unknown action: {action}")
