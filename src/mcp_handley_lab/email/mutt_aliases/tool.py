"""Mutt aliases tool for managing email address book via MCP."""

import re
from pathlib import Path

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp
from mcp_handley_lab.shared.models import (
    MuttContact,
    MuttContactSearchResult,
    OperationResult,
    ServerInfo,
)


def _parse_alias_line(line: str) -> MuttContact:
    """Parse a mutt alias line into a MuttContact object."""
    line = line.strip()
    if not line.startswith("alias "):
        raise ValueError(f"Invalid alias line: {line}")

    # Match: alias nickname "Name" <email> or alias nickname email
    match = re.match(r'alias\s+(\S+)\s+"([^"]+)"\s*<([^>]+)>', line)
    if match:
        alias, name, email = match.groups()
        return MuttContact(alias=alias, email=email, name=name)

    # Match: alias nickname email (simple format)
    match = re.match(r"alias\s+(\S+)\s+(\S+)", line)
    if match:
        alias, email = match.groups()
        # Extract name from comment if present
        name = ""
        if "#" in line:
            name = line.split("#", 1)[1].strip()
        return MuttContact(alias=alias, email=email, name=name)

    raise ValueError(f"Could not parse alias line: {line}")


def _get_all_contacts(config_file: str = None) -> list[MuttContact]:
    """Get all contacts from mutt address book."""
    alias_file = get_mutt_alias_file(config_file)
    if not alias_file.exists():
        return []

    contacts = []
    with open(alias_file) as f:
        for line in f:
            line = line.strip()
            if line and line.startswith("alias "):
                contact = _parse_alias_line(line)
                contacts.append(contact)

    return contacts


def _find_contact_fuzzy(
    query: str, max_results: int = 5, config_file: str = None
) -> list[MuttContact]:
    """Find contacts using simple fuzzy matching."""
    contacts = _get_all_contacts(config_file)
    if not contacts:
        return []

    query_lower = query.lower()
    matches = []

    for contact in contacts:
        if (
            query_lower in contact.alias.lower()
            or query_lower in contact.email.lower()
            or query_lower in contact.name.lower()
        ):
            matches.append(contact)

    return matches[:max_results]


def get_mutt_alias_file(config_file: str = None) -> Path:
    """Get mutt alias file path from mutt configuration."""
    cmd = ["mutt", "-Q", "alias_file"]
    if config_file:
        cmd.extend(["-F", config_file])

    stdout, stderr = run_command(cmd)
    result = stdout.decode().strip()
    path = result.split("=")[1].strip("\"'")
    if path.startswith("~"):
        path = str(Path.home()) + path[1:]
    return Path(path)


@mcp.tool(
    description="""Adds contact or group to Mutt address book. Creates nickname shortcuts for email addresses. Supports individual contacts and groups with comma-separated emails or space-separated aliases."""
)
def add_contact(
    alias: str, email: str, name: str = "", config_file: str = None
) -> OperationResult:
    """Add a contact to mutt's address book."""

    if not alias or not email:
        raise ValueError("Both alias and email are required")

    clean_alias = alias.lower()
    alias_file = get_mutt_alias_file(config_file)

    if "@" in email:
        if name:
            alias_line = f'alias {clean_alias} "{name}" <{email}>\n'
        else:
            alias_line = f"alias {clean_alias} {email}\n"
    else:
        if name:
            alias_line = f"alias {clean_alias} {email}  # {name}\n"
        else:
            alias_line = f"alias {clean_alias} {email}\n"

    with open(alias_file, "a") as f:
        f.write(alias_line)

    return OperationResult(
        status="success", message=f"Added contact: {clean_alias} ({name or email})"
    )


@mcp.tool(
    description="""Searches Mutt address book with fuzzy matching. Finds contacts by partial alias, name, or email using fzf-style algorithm."""
)
def find_contact(
    query: str, max_results: int = 10, config_file: str = None
) -> MuttContactSearchResult:
    """Find contacts using fuzzy matching."""

    if not query:
        raise ValueError("Search query is required")

    matches = _find_contact_fuzzy(query, max_results, config_file)

    return MuttContactSearchResult(
        query=query, matches=matches, total_found=len(matches)
    )


@mcp.tool(
    description="""Removes contact from Mutt address book with fuzzy matching. Tries exact match first, then fuzzy. Prevents accidental deletion with multiple matches."""
)
def remove_contact(alias: str, config_file: str = None) -> OperationResult:
    """Remove a contact from mutt's address book."""

    if not alias:
        raise ValueError("Alias is required")

    clean_alias = alias.lower()
    alias_file = get_mutt_alias_file(config_file)

    if not alias_file.exists():
        raise FileNotFoundError("No mutt alias file found")

    with open(alias_file) as f:
        lines = f.readlines()

    target_line = f"alias {clean_alias} "
    filtered_lines = [line for line in lines if not line.startswith(target_line)]

    if len(filtered_lines) == len(lines):
        fuzzy_matches = _find_contact_fuzzy(
            alias, max_results=5, config_file=config_file
        )
        if not fuzzy_matches:
            raise ValueError(f"Contact '{clean_alias}' not found")
        elif len(fuzzy_matches) == 1:
            fuzzy_alias = fuzzy_matches[0].alias
            target_line = f"alias {fuzzy_alias} "
            filtered_lines = [
                line for line in lines if not line.startswith(target_line)
            ]
            clean_alias = fuzzy_alias
        else:
            matches_str = ", ".join(match.alias for match in fuzzy_matches)
            raise ValueError(
                f"Multiple matches found for '{alias}': {matches_str}. Please be more specific."
            )

    with open(alias_file, "w") as f:
        f.writelines(filtered_lines)

    return OperationResult(status="success", message=f"Removed contact: {clean_alias}")


@mcp.tool(
    description="Checks Mutt Aliases Tool server status and mutt command availability."
)
def server_info() -> ServerInfo:
    """Get server status and mutt version."""
    stdout, stderr = run_command(["mutt", "-v"])
    result = stdout.decode().strip()
    version_lines = result.split("\n")
    version_line = version_lines[0] if version_lines else "Unknown version"

    return ServerInfo(
        name="Mutt Aliases Tool",
        version="1.0.0",
        status="active",
        capabilities=["add_contact", "find_contact", "remove_contact"],
        dependencies={"mutt": version_line},
    )
