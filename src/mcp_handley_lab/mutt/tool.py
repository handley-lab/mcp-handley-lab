"""Mutt tool for interactive email composition via MCP."""
import os
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_handley_lab.common.terminal import launch_interactive

mcp = FastMCP("Mutt Tool")


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
    description="""Compose and send an email using mutt with interactive editing.

Opens mutt in compose mode with the specified recipient and subject. This allows you to:
- Use your existing mutt configuration (signatures, from addresses, etc.)
- Compose the email in your preferred editor
- Review and send or save as draft
- Attach files to the email

All your mutt settings will be automatically applied including:
- Real name from ~/.muttrc
- Signature from account-specific settings
- Proper from address based on folder hooks

Examples:
```python
# Basic email composition
compose_email(
    to="user@example.com",
    subject="Meeting follow-up"
)

# Email with CC and initial body
compose_email(
    to="user@example.com",
    cc="team@example.com",
    subject="Project update",
    initial_body="Hi team,\n\nHere's the latest update..."
)

# Email with attachments
compose_email(
    to="user@example.com",
    subject="Report and data",
    attachments=["/path/to/report.pdf", "/path/to/data.csv"],
    initial_body="Please find attached the report and data files."
)

# Auto-send email (WARNING: sends immediately without review!)
compose_email(
    to="user@example.com",
    subject="Automated notification",
    initial_body="This email was sent automatically.",
    auto_send=True
)
```"""
)
def compose_email(
    to: str,
    subject: str = "",
    cc: str = None,
    bcc: str = None,
    initial_body: str = "",
    attachments: list[str] = None,
    auto_send: bool = False,
) -> str:
    """Compose an email using mutt's interactive interface."""

    # Build mutt command
    mutt_cmd = ["mutt"]

    # Enable autoedit to skip recipient confirmation prompts
    mutt_cmd.extend(["-e", "set autoedit"])

    # Add auto-send if requested (WARNING: sends without review!)
    if auto_send:
        # Set postpone=no so mutt doesn't ask about postponing
        mutt_cmd.extend(["-e", "set postpone=no"])

    if subject:
        mutt_cmd.extend(["-s", subject])

    if cc:
        mutt_cmd.extend(["-c", cc])

    if bcc:
        mutt_cmd.extend(["-b", bcc])

    # Add attachments if provided (must come after other options but before recipient)
    if attachments:
        # Validate attachment files exist
        for attachment in attachments:
            if not os.path.exists(attachment):
                raise FileNotFoundError(f"Attachment file not found: {attachment}")

        # Add -a flag once, then all attachment files, then --
        mutt_cmd.append("-a")
        mutt_cmd.extend(attachments)
        mutt_cmd.append("--")

    # Add recipient (must be last)
    mutt_cmd.append(to)

    # Handle temp file creation and execution within its scope
    if initial_body:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=True
        ) as temp_f:
            temp_f.write(initial_body)
            temp_f.flush()  # Ensure content is written to disk

            # Add temp file to command
            mutt_cmd.extend(["-i", temp_f.name])

            if auto_send:
                # For auto-send, use mutt non-interactively with stdin
                mutt_cmd_str = " ".join(
                    f"'{arg}'" if " " in arg else arg for arg in mutt_cmd
                )
                body_content = initial_body if initial_body else "Automated email"

                # Try to add signature for auto-send
                # Check if there's a signature file configured in mutt
                sig_result = _run_command(["mutt", "-Q", "signature"])
                if "signature=" in sig_result:
                    sig_path = sig_result.split("=", 1)[1].strip().strip('"')
                    # Expand ~ to home directory if needed
                    if sig_path.startswith("~"):
                        sig_path = os.path.expanduser(sig_path)

                    if os.path.exists(sig_path):
                        with open(sig_path) as f:
                            signature = f.read().strip()
                        if signature:
                            body_content += f"\n\n{signature}"

                # Send via stdin (non-interactive)
                mutt_cmd = mutt_cmd_str.split()
                _run_command(mutt_cmd, input_text=body_content)

                attachment_info = (
                    f" with {len(attachments)} attachment(s)" if attachments else ""
                )
                return f"Email sent automatically: {to}{attachment_info}"
            else:
                # Interactive mode - launch mutt interactively
                mutt_cmd_str = " ".join(
                    f"'{arg}'" if " " in arg else arg for arg in mutt_cmd
                )
                window_title = f"Mutt: {subject or 'New Email'}"
                launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

                attachment_info = (
                    f" with {len(attachments)} attachment(s)" if attachments else ""
                )
                return f"Email composition completed: {to}{attachment_info}"
    else:
        # No initial body - execute without temp file
        if auto_send:
            # For auto-send, use mutt non-interactively with stdin
            mutt_cmd_str = " ".join(
                f"'{arg}'" if " " in arg else arg for arg in mutt_cmd
            )
            body_content = "Automated email"

            # Try to add signature for auto-send
            # Check if there's a signature file configured in mutt
            sig_result = _run_command(["mutt", "-Q", "signature"])
            if "signature=" in sig_result:
                sig_path = sig_result.split("=", 1)[1].strip().strip('"')
                # Expand ~ to home directory if needed
                if sig_path.startswith("~"):
                    sig_path = os.path.expanduser(sig_path)

                if os.path.exists(sig_path):
                    with open(sig_path) as f:
                        signature = f.read().strip()
                    if signature:
                        body_content += f"\n\n{signature}"

            # Send via stdin (non-interactive)
            mutt_cmd = mutt_cmd_str.split()
            _run_command(mutt_cmd, input_text=body_content)

            attachment_info = (
                f" with {len(attachments)} attachment(s)" if attachments else ""
            )
            return f"Email sent automatically: {to}{attachment_info}"
        else:
            # Interactive mode - launch mutt interactively
            mutt_cmd_str = " ".join(
                f"'{arg}'" if " " in arg else arg for arg in mutt_cmd
            )
            window_title = f"Mutt: {subject or 'New Email'}"
            launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

            attachment_info = (
                f" with {len(attachments)} attachment(s)" if attachments else ""
            )
            return f"Email composition completed: {to}{attachment_info}"


@mcp.tool(
    description="""Open mutt's main interface for reading and managing emails.

Launches the full mutt interface where you can:
- Read and reply to emails
- Navigate folders
- Search and filter messages
- Manage your email workflow

Uses your existing mutt configuration and folder setup."""
)
def open_mutt() -> str:
    """Open mutt's main interface."""

    # Launch mutt interactively
    launch_interactive("mutt", window_title="Mutt", wait=True)

    return "Mutt session completed"


@mcp.tool(
    description="""Reply to an email using mutt.

Opens mutt in reply mode for a specific email. You can specify:
- Message ID or thread ID to reply to
- Whether to reply to all recipients
- Initial body content for the reply

Examples:
```python
# Reply to specific message
reply_to_email(
    message_id="20241201.123456@example.com",
    reply_all=False
)

# Reply to all with initial content
reply_to_email(
    message_id="20241201.123456@example.com",
    reply_all=True,
    initial_body="Thanks for the update. I'll review and get back to you."
)
```"""
)
def reply_to_email(
    message_id: str, reply_all: bool = False, initial_body: str = ""
) -> str:
    """Reply to an email using mutt's reply functionality."""

    # Build mutt command for replying
    mutt_cmd = ["mutt"]

    # Enable autoedit to skip prompts
    mutt_cmd.extend(["-e", "set autoedit"])

    # Add reply mode
    if reply_all:
        mutt_cmd.extend(["-e", "set reply_to_all=yes"])
    else:
        mutt_cmd.extend(["-e", "set reply_to_all=no"])

    # Add message ID to reply to
    mutt_cmd.extend(["-H", f"id:{message_id}"])

    # Handle temp file creation and execution within its scope
    if initial_body:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=True
        ) as temp_f:
            temp_f.write(initial_body)
            temp_f.flush()  # Ensure content is written to disk

            # Add temp file to command
            mutt_cmd.extend(["-i", temp_f.name])

            # Launch mutt interactively
            mutt_cmd_str = " ".join(
                f"'{arg}'" if " " in arg else arg for arg in mutt_cmd
            )
            window_title = f"Mutt Reply: {message_id[:20]}..."
            launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

            reply_type = "Reply to all" if reply_all else "Reply"
            return f"{reply_type} completed for message: {message_id}"
    else:
        # No initial body - execute without temp file
        mutt_cmd_str = " ".join(f"'{arg}'" if " " in arg else arg for arg in mutt_cmd)
        window_title = f"Mutt Reply: {message_id[:20]}..."
        launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

        reply_type = "Reply to all" if reply_all else "Reply"
        return f"{reply_type} completed for message: {message_id}"


@mcp.tool(
    description="""Forward an email using mutt.

Opens mutt in forward mode for a specific email with optional initial content.

Examples:
```python
# Forward email
forward_email(
    message_id="20241201.123456@example.com",
    to="team@example.com"
)

# Forward with comment
forward_email(
    message_id="20241201.123456@example.com",
    to="colleague@example.com",
    initial_body="FYI - thought you'd be interested in this discussion."
)
```"""
)
def forward_email(message_id: str, to: str = "", initial_body: str = "") -> str:
    """Forward an email using mutt's forward functionality."""

    # Build mutt command for forwarding
    mutt_cmd = ["mutt"]

    # Enable autoedit to skip prompts
    mutt_cmd.extend(["-e", "set autoedit"])

    # Add forward flag and message ID
    mutt_cmd.extend(["-f", f"id:{message_id}"])

    # Add recipient if specified
    if to:
        mutt_cmd.append(to)

    # Handle temp file creation and execution within its scope
    if initial_body:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=True
        ) as temp_f:
            temp_f.write(initial_body)
            temp_f.flush()  # Ensure content is written to disk

            # Add temp file to command
            mutt_cmd.extend(["-i", temp_f.name])

            # Launch mutt interactively
            mutt_cmd_str = " ".join(
                f"'{arg}'" if " " in arg else arg for arg in mutt_cmd
            )
            window_title = f"Mutt Forward: {message_id[:20]}..."
            launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

            return f"Forward completed for message: {message_id}"
    else:
        # No initial body - execute without temp file
        mutt_cmd_str = " ".join(f"'{arg}'" if " " in arg else arg for arg in mutt_cmd)
        window_title = f"Mutt Forward: {message_id[:20]}..."
        launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

        return f"Forward completed for message: {message_id}"


@mcp.tool(
    description="""Move or delete emails using mutt operations.

Supports moving emails between folders or deleting (moving to trash).

Examples:
```python
# Move to archive
move_email(
    message_id="20241201.123456@example.com",
    destination="Archive"
)

# Delete (move to trash)
move_email(
    message_id="20241201.123456@example.com",
    destination="Trash"
)

# Move multiple messages
move_email(
    message_ids=["id1@example.com", "id2@example.com"],
    destination="Projects/GW"
)
```"""
)
def move_email(
    message_id: str = None, message_ids: list[str] = None, destination: str = "Trash"
) -> str:
    """Move or delete emails by moving them to specified folder."""

    if not message_id and not message_ids:
        raise ValueError("Must specify either message_id or message_ids")

    # Prepare message list
    messages = [message_id] if message_id else message_ids

    # Use mutt's save command to move messages
    # This requires mutt scripting approach
    script_commands = []

    for msg_id in messages:
        # Tag the message and save it to destination folder
        script_commands.extend(
            [
                f"<search>id:{msg_id}<enter>",
                "<tag-message>",
                f"<tag-prefix><save-message>={destination}<enter>",
                "<untag-pattern>.*<enter>",
            ]
        )

    # Create temporary mutt script and execute within its scope
    with tempfile.NamedTemporaryFile(mode="w", suffix=".muttrc", delete=True) as temp_f:
        # Write commands to execute
        temp_f.write("".join(f'push "{cmd}"\n' for cmd in script_commands))
        temp_f.write('push "<quit>"\n')
        temp_f.flush()  # Ensure content is written to disk

        # Run mutt with the script while the file exists
        mutt_cmd = ["mutt", "-F", temp_f.name]
        _run_command(mutt_cmd)

        action = (
            "Deleted" if destination.lower() == "trash" else f"Moved to {destination}"
        )
        count = len(messages)
        return f"{action} {count} message(s) successfully"


@mcp.tool(
    description="""List available mailboxes/folders in mutt configuration.

Shows all configured mailboxes that can be accessed through mutt.

Examples:
```python
# List all folders
list_folders()

# Output shows folders like:
# - INBOX
# - Sent Items
# - Archive
# - Trash
# - Projects/GW
```"""
)
def list_folders() -> str:
    """List available mailboxes from mutt configuration."""
    # Use mutt to query mailboxes configuration
    result = _run_command(["mutt", "-Q", "mailboxes"])

    # Note: _run_command already handles errors and returns just the output

    # Parse mailboxes output
    mailboxes_line = result.strip()
    if not mailboxes_line or "mailboxes=" not in mailboxes_line:
        return "No mailboxes configured in mutt"

    # Extract mailbox names (basic parsing)
    folders_part = mailboxes_line.split("mailboxes=", 1)[1].strip('"')
    folders = [f.strip() for f in folders_part.split() if f.strip()]

    if not folders:
        return "No mailboxes found in configuration"

    return "Available mailboxes:\n" + "\n".join(f"- {folder}" for folder in folders)


@mcp.tool(
    description="""Open a specific mailbox/folder in mutt.

Launches mutt with a specific folder open for browsing and management.

Examples:
```python
# Open inbox
open_folder("INBOX")

# Open archive folder
open_folder("Archive")

# Open project-specific folder
open_folder("Projects/GW")
```"""
)
def open_folder(folder: str) -> str:
    """Open mutt with a specific folder."""

    # Build mutt command to open specific folder
    mutt_cmd = ["mutt", "-f", folder]

    # Launch mutt interactively
    mutt_cmd_str = " ".join(f"'{arg}'" if " " in arg else arg for arg in mutt_cmd)
    window_title = f"Mutt: {folder}"
    launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

    return f"Opened folder: {folder}"


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
    description="""List contacts from mutt address book.

Shows all configured aliases/contacts that can be used for addressing emails.

Examples:
```python
# List all contacts
list_contacts()

# Filter contacts by pattern
list_contacts(pattern="gw")
```"""
)
def list_contacts(pattern: str = "", config_file: str = None) -> str:
    """List contacts from mutt address book."""

    alias_file = get_mutt_alias_file(config_file)

    if not alias_file.exists():
        return "No mutt alias file found. Use add_contact() to create contacts."

    contacts = []
    with open(alias_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("alias ") and (
                not pattern or pattern.lower() in line.lower()
            ):
                contacts.append(line)

    if not contacts:
        filter_msg = f" matching '{pattern}'" if pattern else ""
        return f"No contacts found{filter_msg}"

    return "Mutt contacts:\n" + "\n".join(f"- {contact}" for contact in contacts)


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
    description="""Interactive contact selection using fzf fuzzy finder.

Opens fzf interface for interactive contact selection. Much more powerful than text-based search.

Examples:
```python
# Interactive contact picker
select_contact()

# Start with a query
select_contact("handley")
```"""
)
def select_contact(query: str = "", config_file: str = None) -> str:
    """Interactive contact selection using fzf."""
    from pyfzf.pyfzf import FzfPrompt

    contacts = _get_all_contacts(config_file)
    if not contacts:
        return "No contacts found in address book"

    fzf = FzfPrompt()
    selection = fzf.prompt(
        contacts,
        f'--query="{query}" --height=40% --preview="echo {{}}" --preview-window=right:30%',
    )

    if selection:
        return f"Selected contact:\n{selection}"
    else:
        return "No contact selected"


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
    description="Checks Mutt Tool server status and mutt command availability. Returns mutt version information and available tool functions."
)
def server_info() -> str:
    """Get server status and mutt version."""
    result = _run_command(["mutt", "-v"])
    # Extract first line of version info
    version_lines = result.split("\n")
    version_line = version_lines[0] if version_lines else "Unknown version"

    return f"""Mutt Tool Server Status
======================
Status: Connected and ready
Mutt Version: {version_line}

Available tools:
- compose_email: Compose and send emails interactively
- open_mutt: Open mutt's main interface
- reply_to_email: Reply to emails with optional reply-all
- forward_email: Forward emails with optional comments
- move_email: Move/delete emails between folders
- list_folders: Show available mailboxes
- open_folder: Open specific mailbox in mutt
- add_contact: Add contacts to address book
- list_contacts: Show address book entries
- remove_contact: Remove contacts from address book
- server_info: Get server status

Configuration: Uses your existing ~/.muttrc and account settings"""
