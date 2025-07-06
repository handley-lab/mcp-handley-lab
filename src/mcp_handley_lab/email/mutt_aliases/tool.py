"""Mutt aliases tool for managing email address book via MCP."""
from pathlib import Path

from mcp_handley_lab.email.common import mcp


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
    # Use fzf non-interactive filter mode (without --print-query)
    matches = fzf.prompt(contacts, f'--filter="{query}" --no-sort')

    # Check if matches exist and return them
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
    # Parse: alias_file="~/.mutt/addressbook"
    path = result.split("=")[1].strip("\"'")
    # Expand ~ to home directory
    if path.startswith("~"):
        path = str(Path.home()) + path[1:]
    return Path(path)


@mcp.tool(
    description="""Add contact to mutt address book.

Adds a new contact to mutt's alias system for easy addressing.

Examples:
```python
# Add individual contact
add_contact(
    alias="john",
    email="john.doe@example.com",
    name="John Doe"
)

# Add group with email addresses
add_contact(
    alias="gw-team",
    email="alice@cam.ac.uk,bob@cam.ac.uk,carol@cam.ac.uk",
    name="GW Project Team"
)

# Add group with existing aliases
add_contact(
    alias="my-students",
    email="alice-smith bob-jones carol-white",  # Space-separated aliases
    name="My Research Students"
)
```"""
)
def add_contact(alias: str, email: str, name: str = "", config_file: str = None) -> str:
    """Add a contact to mutt's address book."""

    # Validate inputs
    if not alias or not email:
        raise ValueError("Both alias and email are required")

    # Use alias as-is (your addressbook uses consistent hyphen format)
    clean_alias = alias.lower()

    # Get mutt alias file path from configuration
    alias_file = get_mutt_alias_file(config_file)

    # Determine alias format based on email content
    if "@" in email:
        # Email addresses - use email format
        if name:
            alias_line = f'alias {clean_alias} "{name}" <{email}>\n'
        else:
            alias_line = f"alias {clean_alias} {email}\n"
    else:
        # Space-separated aliases - use alias group format
        if name:
            alias_line = f"alias {clean_alias} {email}  # {name}\n"
        else:
            alias_line = f"alias {clean_alias} {email}\n"

    # Append to alias file
    with open(alias_file, "a") as f:
        f.write(alias_line)

    return f"Added contact: {clean_alias} ({name or email})"


@mcp.tool(
    description="""Find contacts using fuzzy matching.

Searches for contacts using fuzzy string matching, useful when you remember part of a name.

Examples:
```python
# Find contacts with partial names
find_contact("lhergt")      # Finds lukas-hergt
find_contact("handley")     # Finds will-handley-*, mike-handley-*, etc.
find_contact("partiii")     # Finds partiii groups
```"""
)
def find_contact(query: str, max_results: int = 10, config_file: str = None) -> str:
    """Find contacts using fuzzy matching."""

    if not query:
        raise ValueError("Search query is required")

    matches = _find_contact_fuzzy(query, max_results, config_file)

    if not matches:
        return f"No contacts found matching '{query}'"

    return f"Fuzzy matches for '{query}':\n" + "\n".join(
        f"- {match}" for match in matches
    )


@mcp.tool(
    description="""Remove contact from mutt address book with fuzzy matching.

Removes a contact by alias name. If exact match not found, shows fuzzy matches.

Examples:
```python
# Remove exact contact
remove_contact("lukas-hergt")

# Fuzzy matching helps with partial names
remove_contact("lhergt")  # Will find lukas-hergt
```"""
)
def remove_contact(alias: str, config_file: str = None) -> str:
    """Remove a contact from mutt's address book."""

    if not alias:
        raise ValueError("Alias is required")

    # Use alias as-is for exact match first
    clean_alias = alias.lower()

    # Determine file path
    alias_file = get_mutt_alias_file(config_file)

    if not alias_file.exists():
        return "No mutt alias file found"

    # Read current contents
    with open(alias_file) as f:
        lines = f.readlines()

    # Try exact match first
    target_line = f"alias {clean_alias} "
    filtered_lines = [line for line in lines if not line.startswith(target_line)]

    if len(filtered_lines) == len(lines):
        # No exact match, try fuzzy matching
        fuzzy_matches = _find_contact_fuzzy(
            alias, max_results=5, config_file=config_file
        )
        if not fuzzy_matches:
            return f"Contact '{clean_alias}' not found"
        elif len(fuzzy_matches) == 1:
            # Single fuzzy match, remove it
            fuzzy_alias = fuzzy_matches[0].split()[
                1
            ]  # Extract alias from "alias name ..."
            target_line = f"alias {fuzzy_alias} "
            filtered_lines = [
                line for line in lines if not line.startswith(target_line)
            ]
            clean_alias = fuzzy_alias  # Update for return message
        else:
            # Multiple matches, ask user to be more specific
            matches_str = "\n".join(f"- {match}" for match in fuzzy_matches)
            return f"Multiple matches found for '{alias}':\n{matches_str}\n\nPlease be more specific."

    # Write back filtered contents
    with open(alias_file, "w") as f:
        f.writelines(filtered_lines)

    return f"Removed contact: {clean_alias}"


@mcp.tool(
    description="Checks Mutt Aliases Tool server status and mutt command availability. Returns mutt version information and available alias functions."
)
def server_info() -> str:
    """Get server status and mutt version."""
    result = _run_command(["mutt", "-v"])
    # Extract first line of version info
    version_lines = result.split("\n")
    version_line = version_lines[0] if version_lines else "Unknown version"

    return f"""Mutt Aliases Tool Server Status
===============================
Status: Connected and ready
Mutt Version: {version_line}

Available tools:
- add_contact: Add contacts to mutt address book
- find_contact: Find contacts using fuzzy matching
- remove_contact: Remove contacts from address book
- server_info: Get server status

Configuration: Uses mutt's alias_file setting from ~/.muttrc"""