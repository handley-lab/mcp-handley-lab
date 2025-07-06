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
    description="""Adds a new contact or group to your Mutt address book (alias file).

Aliases are shortcuts that let you use a simple nickname (e.g., "gw-team") instead of typing full email addresses when composing mail. This tool supports adding both individual contacts and groups of contacts.

**Key Parameters:**
- `alias`: The short nickname for the contact or group (e.g., "john-doe", "project-team").
- `email`: The contact's full email address(es). For a group, provide a comma-separated list of emails OR a space-separated list of other aliases.
- `name`: (Optional) The full name of the contact or a description for the group.
- `config_file`: (Optional) Path to a custom mutt config file.

**Behavior:**
- The tool determines the correct path to your alias file from your Mutt configuration.
- It appends the new alias entry to the end of the file.

**Examples:**
```python
# Add an individual contact with a name.
add_contact(alias="john-doe", email="john.doe@example.com", name="John Doe")

# Add a group of people using their email addresses.
add_contact(
    alias="gw-team",
    email="alice@cam.ac.uk,bob@cam.ac.uk",
    name="Gravitational Wave Team"
)

# Create a new group composed of existing aliases.
add_contact(
    alias="all-students",
    email="john-doe jane-smith", # Note: space-separated aliases
    name="All Research Students"
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
    description="""Performs a fuzzy search within your Mutt address book to find contacts.

This is useful when you only remember part of a contact's alias or name. It uses `fzf`-style matching to find the closest matches.

**Key Parameters:**
- `query`: The partial name, alias, or email to search for.
- `max_results`: (Optional) The maximum number of matches to return. Defaults to 10.
- `config_file`: (Optional) Path to a custom mutt config file.

**Behavior:**
- Reads the entire alias file into memory.
- Filters the contacts using a non-interactive fuzzy matching algorithm.
- Returns a formatted string of the best matches.

**Examples:**
```python
# Find a contact when I only remember part of the alias.
find_contact(query="handley")
# Example Output:
# Fuzzy matches for 'handley':
# - alias will-handley-prof "Will Handley" <w.handley@cam.ac.uk>
# - alias mike-handley "Mike Handley" <m.handley@cam.ac.uk>

# Find a group alias.
find_contact(query="partiii")
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
    description="""Removes a contact from your Mutt address book, with support for fuzzy matching.

This tool first attempts to find and remove an exact match for the provided alias. If no exact match is found, it performs a fuzzy search.

**Key Parameters:**
- `alias`: The alias of the contact to remove.
- `config_file`: (Optional) Path to a custom mutt config file.

**Behavior:**
1.  **Exact Match:** The tool first searches for an alias that exactly matches the `alias` parameter. If found, it is removed.
2.  **Fuzzy Match:** If no exact match is found, it performs a fuzzy search.
    - If **one** unique fuzzy match is found, that contact is removed.
    - If **multiple** fuzzy matches are found, it returns a list of the matches and asks you to be more specific, preventing accidental deletion.
    - If **no** matches are found, it reports that the contact was not found.

**WARNING:** This action permanently modifies your address book file.

**Examples:**
```python
# Remove a contact with an exact alias.
remove_contact(alias="john-doe")

# Remove a contact using a partial, unique alias.
# If "lukas-h" uniquely matches "lukas-hergt", it will be removed.
remove_contact(alias="lukas-h")

# If the alias is ambiguous, it will prompt for clarification.
# remove_contact(alias="handley")
# Example Output:
# Multiple matches found for 'handley':
# - alias will-handley-prof ...
# - alias mike-handley ...
# Please be more specific.
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