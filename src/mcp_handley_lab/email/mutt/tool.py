"""Mutt tool for interactive email composition via MCP."""
import os
import tempfile

from mcp_handley_lab.common.terminal import launch_interactive
from mcp_handley_lab.email.common import mcp


def _run_command(cmd: list[str], input_text: str = None, cwd: str = None) -> str:
    """Run a shell command and return output."""
    from mcp_handley_lab.common.process import run_command

    input_bytes = input_text.encode() if input_text else None
    stdout, stderr = run_command(cmd, input_data=input_bytes)
    return stdout.decode().strip()


@mcp.tool(
    description="Opens Mutt to compose an email, using your full configuration (signatures, editor). Supports attachments, pre-filled body, and an `auto_send` option that bypasses interactive review."
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
    description="""Opens Mutt main interface in interactive terminal for reading, searching, and organizing emails. Full access to your complete Mutt configuration and mailboxes."""
)
def open_mutt() -> str:
    """Open mutt's main interface."""

    # Launch mutt interactively
    launch_interactive("mutt", window_title="Mutt", wait=True)

    return "Mutt session completed"


@mcp.tool(
    description="""Opens Mutt in interactive terminal to reply to specific email by message ID. Supports reply-all mode and initial body text. Headers auto-populated from original message."""
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
    description="""Opens Mutt in interactive terminal to forward specific email by message ID. Supports pre-populated recipient and initial commentary. Original message included per your configuration."""
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
    description="""Moves emails between folders using Mutt scripting. Supports single message or batch operations by message ID(s). Default destination is Trash for deletion."""
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
    description="""Lists all configured mailboxes from Mutt configuration. Useful for discovering folder names for move_email operations and understanding your email folder structure."""
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
    description="""Opens Mutt in interactive terminal focused on specific folder. Full functionality available for reading, replying, and managing emails within that mailbox."""
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


@mcp.tool(description="Checks Mutt Tool server status and mutt command availability.")
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
- server_info: Get server status

Configuration: Uses your existing ~/.muttrc and account settings"""
