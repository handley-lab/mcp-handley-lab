"""Mutt aliases tool for managing email address book via MCP."""
from pathlib import Path

from mcp_handley_lab.email.common import mcp
from mcp_handley_lab.shared.models import OperationResult, ServerInfo


def _run_command(cmd: list[str], input_text: str = None, cwd: str = None) -> str:
    """Run a shell command and return output."""
    from mcp_handley_lab.common.process import run_command

    input_bytes = input_text.encode() if input_text else None
    stdout, stderr = run_command(cmd, input_data=input_bytes)
    return stdout.decode().strip()


def _get_all_contacts(config_file: str = None) -> list[str]:
    """Get all contacts from mutt address book."""
    alias_file = get_mutt_alias_file(config_file)
    if not alias_file.exists():
        return []

    contacts = []
    with open(alias_file) as f:
        for line in f:
            if line.startswith("alias "):
                contacts.append(line.strip())

    return contacts


def _find_contact_fuzzy(
    query: str, max_results: int = 5, config_file: str = None
) -> list[str]:
    """Find contacts using fzf-style fuzzy matching."""
    from pyfzf.pyfzf import FzfPrompt

    contacts = _get_all_contacts(config_file)
    if not contacts:
        return []

    fzf = FzfPrompt()
    matches = fzf.prompt(contacts, f'--filter="{query}" --no-sort')

    if matches:
        return [m for m in matches[:max_results] if m.startswith("alias ")]
    else:
        return []


def get_mutt_alias_file(config_file: str = None) -> Path:
    """Get mutt alias file path from mutt configuration."""
    cmd = ["mutt", "-Q", "alias_file"]
    if config_file:
        cmd.extend(["-F", config_file])
    result = _run_command(cmd)
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
) -> OperationResult:
    """Find contacts using fuzzy matching."""

    if not query:
        raise ValueError("Search query is required")

    matches = _find_contact_fuzzy(query, max_results, config_file)

    if not matches:
        return OperationResult(
            status="success", message=f"No contacts found matching '{query}'"
        )

    result = f"Fuzzy matches for '{query}':\n" + "\n".join(
        f"- {match}" for match in matches
    )
    return OperationResult(status="success", message=result)


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
        return OperationResult(status="error", message="No mutt alias file found")

    with open(alias_file) as f:
        lines = f.readlines()

    target_line = f"alias {clean_alias} "
    filtered_lines = [line for line in lines if not line.startswith(target_line)]

    if len(filtered_lines) == len(lines):
        fuzzy_matches = _find_contact_fuzzy(
            alias, max_results=5, config_file=config_file
        )
        if not fuzzy_matches:
            return OperationResult(
                status="error", message=f"Contact '{clean_alias}' not found"
            )
        elif len(fuzzy_matches) == 1:
            fuzzy_alias = fuzzy_matches[0].split()[1]
            target_line = f"alias {fuzzy_alias} "
            filtered_lines = [
                line for line in lines if not line.startswith(target_line)
            ]
            clean_alias = fuzzy_alias
        else:
            matches_str = "\n".join(f"- {match}" for match in fuzzy_matches)
            return OperationResult(
                status="error",
                message=f"Multiple matches found for '{alias}':\n{matches_str}\n\nPlease be more specific.",
            )

    with open(alias_file, "w") as f:
        f.writelines(filtered_lines)

    return OperationResult(status="success", message=f"Removed contact: {clean_alias}")


@mcp.tool(
    description="Checks Mutt Aliases Tool server status and mutt command availability."
)
def server_info() -> ServerInfo:
    """Get server status and mutt version."""
    result = _run_command(["mutt", "-v"])
    version_lines = result.split("\n")
    version_line = version_lines[0] if version_lines else "Unknown version"

    return ServerInfo(
        name="Mutt Aliases Tool",
        version="1.0.0",
        status="active",
        capabilities=["add_contact", "find_contact", "remove_contact"],
        dependencies={"mutt": version_line},
    )
