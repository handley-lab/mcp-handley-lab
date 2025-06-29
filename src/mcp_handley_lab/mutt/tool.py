"""Mutt tool for interactive email composition via MCP."""
import subprocess
import tempfile
import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from ..common.terminal import launch_interactive

mcp = FastMCP("Mutt Tool")


@mcp.tool(description="""Compose and send an email using mutt with interactive editing.

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
```""")
def compose_email(
    to: str,
    subject: str = "",
    cc: str = None,
    bcc: str = None,
    initial_body: str = "",
    attachments: list[str] = None,
    auto_send: bool = False
) -> str:
    """Compose an email using mutt's interactive interface."""
    
    # Build mutt command
    mutt_cmd = ['mutt']
    
    # Enable autoedit to skip recipient confirmation prompts
    mutt_cmd.extend(['-e', 'set autoedit'])
    
    # Add auto-send if requested (WARNING: sends without review!)
    if auto_send:
        # Set postpone=no so mutt doesn't ask about postponing
        mutt_cmd.extend(['-e', 'set postpone=no'])
    
    if subject:
        mutt_cmd.extend(['-s', subject])
    
    if cc:
        mutt_cmd.extend(['-c', cc])
        
    if bcc:
        mutt_cmd.extend(['-b', bcc])
    
    # If there's initial body content, create a temp file and add -i flag
    temp_file = None
    if initial_body:
        fd, temp_file = tempfile.mkstemp(suffix='.txt', text=True)
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(initial_body)
            mutt_cmd.extend(['-i', temp_file])
        except:
            if temp_file:
                os.unlink(temp_file)
            raise
    
    # Add attachments if provided (must come after other options but before recipient)
    if attachments:
        # Validate attachment files exist
        for attachment in attachments:
            if not os.path.exists(attachment):
                raise FileNotFoundError(f"Attachment file not found: {attachment}")
        
        # Add -a flag once, then all attachment files, then --
        mutt_cmd.append('-a')
        mutt_cmd.extend(attachments)
        mutt_cmd.append('--')
    
    # Add recipient (must be last)
    mutt_cmd.append(to)
    
    try:
        if auto_send:
            # For auto-send, use mutt non-interactively with stdin
            mutt_cmd_str = ' '.join(f"'{arg}'" if ' ' in arg else arg for arg in mutt_cmd)
            body_content = initial_body if initial_body else "Automated email"
            
            # Try to add signature for auto-send
            try:
                # Check if there's a signature file configured in mutt
                sig_result = subprocess.run(['mutt', '-Q', 'signature'], capture_output=True, text=True)
                if sig_result.returncode == 0 and 'signature=' in sig_result.stdout:
                    sig_path = sig_result.stdout.split('=', 1)[1].strip().strip('"')
                    # Expand ~ to home directory if needed
                    if sig_path.startswith('~'):
                        sig_path = os.path.expanduser(sig_path)
                    
                    if os.path.exists(sig_path):
                        with open(sig_path, 'r') as f:
                            signature = f.read().strip()
                        if signature:
                            body_content += f"\n\n{signature}"
            except Exception:
                # If signature detection fails, continue without it
                pass
            
            # Send via stdin (non-interactive)
            process = subprocess.run(
                mutt_cmd_str, 
                input=body_content, 
                shell=True, 
                text=True, 
                capture_output=True
            )
            
            if process.returncode != 0:
                raise RuntimeError(f"Failed to send email: {process.stderr}")
                
            attachment_info = f" with {len(attachments)} attachment(s)" if attachments else ""
            return f"Email sent automatically: {to}{attachment_info}"
        else:
            # Interactive mode - launch mutt interactively
            mutt_cmd_str = ' '.join(f"'{arg}'" if ' ' in arg else arg for arg in mutt_cmd)
            window_title = f"Mutt: {subject or 'New Email'}"
            result = launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)
            
            attachment_info = f" with {len(attachments)} attachment(s)" if attachments else ""
            return f"Email composition completed: {to}{attachment_info}"
        
    finally:
        # Clean up temp file if created
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)


@mcp.tool(description="""Open mutt's main interface for reading and managing emails.

Launches the full mutt interface where you can:
- Read and reply to emails
- Navigate folders
- Search and filter messages
- Manage your email workflow

Uses your existing mutt configuration and folder setup.""")
def open_mutt() -> str:
    """Open mutt's main interface."""
    
    # Launch mutt interactively
    result = launch_interactive('mutt', window_title='Mutt', wait=True)
    
    return "Mutt session completed"


@mcp.tool(description="""Reply to an email using mutt.

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
```""")
def reply_to_email(
    message_id: str,
    reply_all: bool = False,
    initial_body: str = ""
) -> str:
    """Reply to an email using mutt's reply functionality."""
    
    # Build mutt command for replying
    mutt_cmd = ['mutt']
    
    # Enable autoedit to skip prompts
    mutt_cmd.extend(['-e', 'set autoedit'])
    
    # Add reply mode
    if reply_all:
        mutt_cmd.extend(['-e', 'set reply_to_all=yes'])
    else:
        mutt_cmd.extend(['-e', 'set reply_to_all=no'])
    
    # If there's initial body content, create temp file
    temp_file = None
    if initial_body:
        fd, temp_file = tempfile.mkstemp(suffix='.txt', text=True)
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(initial_body)
            mutt_cmd.extend(['-i', temp_file])
        except:
            if temp_file:
                os.unlink(temp_file)
            raise
    
    # Add message ID to reply to
    mutt_cmd.extend(['-H', f'id:{message_id}'])
    
    try:
        # Launch mutt interactively
        mutt_cmd_str = ' '.join(f"'{arg}'" if ' ' in arg else arg for arg in mutt_cmd)
        window_title = f"Mutt Reply: {message_id[:20]}..."
        result = launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)
        
        reply_type = "Reply to all" if reply_all else "Reply"
        return f"{reply_type} completed for message: {message_id}"
        
    finally:
        # Clean up temp file
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)


@mcp.tool(description="""Forward an email using mutt.

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
```""")
def forward_email(
    message_id: str,
    to: str = "",
    initial_body: str = ""
) -> str:
    """Forward an email using mutt's forward functionality."""
    
    # Build mutt command for forwarding
    mutt_cmd = ['mutt']
    
    # Enable autoedit to skip prompts
    mutt_cmd.extend(['-e', 'set autoedit'])
    
    # If there's initial body content, create temp file
    temp_file = None
    if initial_body:
        fd, temp_file = tempfile.mkstemp(suffix='.txt', text=True)
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(initial_body)
            mutt_cmd.extend(['-i', temp_file])
        except:
            if temp_file:
                os.unlink(temp_file)
            raise
    
    # Add forward flag and message ID
    mutt_cmd.extend(['-f', f'id:{message_id}'])
    
    # Add recipient if specified
    if to:
        mutt_cmd.append(to)
    
    try:
        # Launch mutt interactively
        mutt_cmd_str = ' '.join(f"'{arg}'" if ' ' in arg else arg for arg in mutt_cmd)
        window_title = f"Mutt Forward: {message_id[:20]}..."
        result = launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)
        
        return f"Forward completed for message: {message_id}"
        
    finally:
        # Clean up temp file
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)


@mcp.tool(description="""Move or delete emails using mutt operations.

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
```""")
def move_email(
    message_id: str = None,
    message_ids: list[str] = None,
    destination: str = "Trash"
) -> str:
    """Move or delete emails by moving them to specified folder."""
    
    if not message_id and not message_ids:
        raise ValueError("Must specify either message_id or message_ids")
    
    # Prepare message list
    if message_id:
        messages = [message_id]
    else:
        messages = message_ids
    
    # Use mutt's save command to move messages
    # This requires mutt scripting approach
    script_commands = []
    
    for msg_id in messages:
        # Tag the message and save it to destination folder
        script_commands.extend([
            f'<search>id:{msg_id}<enter>',
            '<tag-message>',
            f'<tag-prefix><save-message>={destination}<enter>',
            '<untag-pattern>.*<enter>'
        ])
    
    # Create temporary mutt script
    fd, script_file = tempfile.mkstemp(suffix='.muttrc', text=True)
    try:
        with os.fdopen(fd, 'w') as f:
            # Write commands to execute
            f.write(''.join(f'push "{cmd}"\n' for cmd in script_commands))
            f.write('push "<quit>"\n')
        
        # Run mutt with the script
        mutt_cmd = ['mutt', '-F', script_file]
        result = subprocess.run(mutt_cmd, capture_output=True, text=True)
        
        action = "Deleted" if destination.lower() == "trash" else f"Moved to {destination}"
        count = len(messages)
        return f"{action} {count} message(s) successfully"
        
    except Exception as e:
        raise RuntimeError(f"Failed to move messages: {e}")
    finally:
        if os.path.exists(script_file):
            os.unlink(script_file)


@mcp.tool(description="""List available mailboxes/folders in mutt configuration.

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
```""")
def list_folders() -> str:
    """List available mailboxes from mutt configuration."""
    
    try:
        # Use mutt to query mailboxes configuration
        result = subprocess.run(['mutt', '-Q', 'mailboxes'], capture_output=True, text=True)
        
        if result.returncode != 0:
            return "Could not retrieve mailbox list from mutt configuration"
        
        # Parse mailboxes output
        mailboxes_line = result.stdout.strip()
        if not mailboxes_line or 'mailboxes=' not in mailboxes_line:
            return "No mailboxes configured in mutt"
        
        # Extract mailbox names (basic parsing)
        folders_part = mailboxes_line.split('mailboxes=', 1)[1].strip('"')
        folders = [f.strip() for f in folders_part.split() if f.strip()]
        
        if not folders:
            return "No mailboxes found in configuration"
        
        return "Available mailboxes:\n" + "\n".join(f"- {folder}" for folder in folders)
        
    except Exception as e:
        return f"Error retrieving folder list: {e}"


@mcp.tool(description="""Open a specific mailbox/folder in mutt.

Launches mutt with a specific folder open for browsing and management.

Examples:
```python
# Open inbox
open_folder("INBOX")

# Open archive folder  
open_folder("Archive")

# Open project-specific folder
open_folder("Projects/GW")
```""")
def open_folder(folder: str) -> str:
    """Open mutt with a specific folder."""
    
    # Build mutt command to open specific folder
    mutt_cmd = ['mutt', '-f', folder]
    
    # Launch mutt interactively
    mutt_cmd_str = ' '.join(f"'{arg}'" if ' ' in arg else arg for arg in mutt_cmd)
    window_title = f"Mutt: {folder}"
    result = launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)
    
    return f"Opened folder: {folder}"


@mcp.tool(description="""Add contact to mutt address book.

Adds a new contact to mutt's alias system for easy addressing.

Examples:
```python
# Add individual contact
add_contact(
    alias="john",
    email="john.doe@example.com", 
    name="John Doe"
)

# Add group/project contacts
add_contact(
    alias="gw-team",
    email="alice@cam.ac.uk,bob@cam.ac.uk,carol@cam.ac.uk",
    name="GW Project Team"
)
```""")
def add_contact(
    alias: str,
    email: str,
    name: str = ""
) -> str:
    """Add a contact to mutt's address book."""
    
    # Validate inputs
    if not alias or not email:
        raise ValueError("Both alias and email are required")
    
    # Clean up alias (mutt aliases can't have spaces)
    clean_alias = alias.lower().replace(' ', '_').replace('-', '_')
    
    # Determine mutt alias file path
    alias_file = Path.home() / ".mutt" / "aliases"
    
    # Create alias entry
    if name:
        alias_line = f'alias {clean_alias} "{name}" <{email}>\n'
    else:
        alias_line = f'alias {clean_alias} {email}\n'
    
    try:
        # Append to alias file
        with open(alias_file, 'a') as f:
            f.write(alias_line)
        
        return f"Added contact: {clean_alias} ({name or email})"
        
    except Exception as e:
        raise RuntimeError(f"Failed to add contact: {e}")


@mcp.tool(description="""List contacts from mutt address book.

Shows all configured aliases/contacts that can be used for addressing emails.

Examples:
```python
# List all contacts
list_contacts()

# Filter contacts by pattern
list_contacts(pattern="gw")
```""")
def list_contacts(pattern: str = "") -> str:
    """List contacts from mutt address book."""
    
    alias_file = Path.home() / ".mutt" / "aliases"
    
    if not alias_file.exists():
        return "No mutt alias file found. Use add_contact() to create contacts."
    
    try:
        contacts = []
        with open(alias_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('alias ') and (not pattern or pattern.lower() in line.lower()):
                    contacts.append(line)
        
        if not contacts:
            filter_msg = f" matching '{pattern}'" if pattern else ""
            return f"No contacts found{filter_msg}"
        
        return "Mutt contacts:\n" + "\n".join(f"- {contact}" for contact in contacts)
        
    except Exception as e:
        return f"Error reading contacts: {e}"


@mcp.tool(description="""Remove contact from mutt address book.

Removes a contact by alias name from the address book.

Examples:
```python
# Remove specific contact
remove_contact("old_contact")
```""")
def remove_contact(alias: str) -> str:
    """Remove a contact from mutt's address book."""
    
    if not alias:
        raise ValueError("Alias is required")
    
    # Clean up alias to match what was stored
    clean_alias = alias.lower().replace(' ', '_').replace('-', '_')
    
    # Determine file path
    alias_file = Path.home() / ".mutt" / "aliases"
    
    if not alias_file.exists():
        return "No mutt alias file found"
    
    try:
        # Read current contents
        with open(alias_file, 'r') as f:
            lines = f.readlines()
        
        # Filter out the contact to remove
        target_line = f"alias {clean_alias} "
        filtered_lines = [line for line in lines if not line.startswith(target_line)]
        
        if len(filtered_lines) == len(lines):
            return f"Contact '{clean_alias}' not found"
        
        # Write back filtered contents
        with open(alias_file, 'w') as f:
            f.writelines(filtered_lines)
        
        return f"Removed contact: {clean_alias}"
        
    except Exception as e:
        raise RuntimeError(f"Failed to remove contact: {e}")


@mcp.tool(description="Checks Mutt Tool server status and mutt command availability. Returns mutt version information and available tool functions.")
def server_info() -> str:
    """Get server status and mutt version."""
    try:
        result = subprocess.run(['mutt', '-v'], capture_output=True, text=True)
        # Extract first line of version info
        version_lines = result.stdout.split('\n')
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
    except FileNotFoundError:
        raise RuntimeError("mutt command not found. Please install mutt.")