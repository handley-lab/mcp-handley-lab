"""Mutt tool for interactive email composition via MCP."""

import os
import shlex
import tempfile
from pathlib import Path

from pydantic import Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.common.terminal import launch_interactive
from mcp_handley_lab.email.common import mcp
from mcp_handley_lab.shared.models import OperationResult, ServerInfo


def _execute_mutt_command(cmd: list[str], input_text: str = None) -> str:
    """Execute mutt command and return output."""
    input_bytes = input_text.encode() if input_text else None
    stdout, stderr = run_command(cmd, input_data=input_bytes)
    return stdout.decode().strip()


def _query_mutt_var(var: str) -> str | None:
    """Query a mutt configuration variable.

    Args:
        var: The variable name to query

    Returns:
        The variable value or None if not found
    """
    try:
        result = _execute_mutt_command(["mutt", "-Q", var])
        if "=" in result:
            return result.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return None


def _mailbox_exists(path: str, allow_inbox_root: bool = False) -> bool:
    """Check if a mailbox path exists.

    Args:
        path: The mailbox path to check
        allow_inbox_root: If True, also check if path is a Maildir root (for INBOX special case)

    Returns:
        True if the mailbox exists
    """
    p = Path(os.path.expanduser(path))

    # Check if it's a regular directory
    if p.exists() and p.is_dir():
        # Check if it's a Maildir (has cur, new, tmp subdirs)
        is_maildir = all((p / subdir).exists() for subdir in ["cur", "new", "tmp"])

        # For INBOX, we allow either a folder called INBOX or the account root itself
        if allow_inbox_root and path.endswith("INBOX"):
            # Check parent directory as potential account root
            parent = p.parent
            if all((parent / subdir).exists() for subdir in ["cur", "new", "tmp"]):
                return True

        return is_maildir or p.exists()

    return False


def _find_account_folders(folder_root: str, mailbox: str) -> list[tuple[str, str]]:
    """Find all account folders containing a specific mailbox.

    Args:
        folder_root: The root mail folder path
        mailbox: The mailbox name to find (e.g., "INBOX")

    Returns:
        List of tuples (account_name, full_path)
    """
    root = Path(os.path.expanduser(folder_root))
    candidates = []

    if not root.exists():
        return candidates

    # Look for account directories
    for account_dir in root.iterdir():
        if account_dir.is_dir():
            # Check for mailbox within account
            mailbox_path = account_dir / mailbox

            if mailbox == "INBOX":
                # Special case: INBOX might be the account root itself
                if all(
                    (account_dir / subdir).exists() for subdir in ["cur", "new", "tmp"]
                ):
                    candidates.append((account_dir.name, str(account_dir)))
                elif mailbox_path.exists() and mailbox_path.is_dir():
                    candidates.append((account_dir.name, str(mailbox_path)))
            elif mailbox_path.exists() and mailbox_path.is_dir():
                candidates.append((account_dir.name, str(mailbox_path)))

    return candidates


def _resolve_folder(folder: str) -> tuple[str, list[str]]:
    """Resolve a folder path with smart handling of = and + shortcuts.

    Args:
        folder: The folder specification (e.g., "=INBOX", "+INBOX", "Hermes/INBOX", or full path)

    Returns:
        Tuple of (resolved_folder, extra_mutt_args)

    Raises:
        ValueError: If folder cannot be resolved or is ambiguous
    """
    if not folder:
        return "", []

    # Handle absolute paths and IMAP URLs - pass through
    if folder.startswith(("/", "imap://", "imaps://")):
        return folder, []

    # Handle tilde expansion
    if folder.startswith("~"):
        return os.path.expanduser(folder), []

    # Get mutt's folder variable
    folder_root = _query_mutt_var("folder")
    if not folder_root:
        folder_root = os.path.expanduser("~/mail")
    else:
        folder_root = os.path.expanduser(folder_root)

    # Handle = or + shortcuts
    if folder.startswith(("=", "+")):
        mailbox = folder[1:]

        # If it contains a slash, it's like =Hermes/INBOX - construct absolute path
        if "/" in mailbox:
            # Just construct the absolute path
            absolute_path = os.path.join(folder_root, mailbox)
            if Path(absolute_path).exists():
                return absolute_path, []
            else:
                raise ValueError(f"Folder '{absolute_path}' does not exist")

        # For single mailbox names like =INBOX, find in accounts
        # First check if the mailbox exists directly under folder root
        direct_path = os.path.join(folder_root, mailbox)
        if _mailbox_exists(direct_path, allow_inbox_root=(mailbox == "INBOX")):
            return direct_path, []

        # Find candidates in account subdirectories
        candidates = _find_account_folders(folder_root, mailbox)

        # Check for default account from environment
        default_account = os.environ.get("MCP_EMAIL_DEFAULT_ACCOUNT")
        if default_account:
            for account_name, path in candidates:
                if account_name == default_account:
                    return path, []

        # If exactly one candidate, use it
        if len(candidates) == 1:
            account_name, path = candidates[0]
            return path, []

        # Multiple candidates - error with suggestions
        if len(candidates) > 1:
            suggestions = [f"{name}/{mailbox}" for name, _ in candidates]
            raise ValueError(
                f"Multiple accounts contain {mailbox}: {', '.join(suggestions)}. "
                f"Please specify the account (e.g., '{suggestions[0]}') or set "
                f"MCP_EMAIL_DEFAULT_ACCOUNT environment variable."
            )

        # No candidates found
        raise ValueError(
            f"Mailbox '{mailbox}' not found. Check available folders with 'list_folders' "
            f"or specify full path."
        )

    # Handle account/mailbox format (e.g., "Hermes/INBOX")
    if "/" in folder:
        # Construct absolute path
        absolute_path = os.path.join(folder_root, folder)
        if Path(absolute_path).exists():
            return absolute_path, []
        else:
            raise ValueError(f"Folder '{absolute_path}' does not exist")

    # Single folder name - treat as =folder
    return _resolve_folder(f"={folder}")  # Recursive call with = prefix


# Function removed as auto_send functionality was removed


def _build_mutt_command(
    to: str = None,
    subject: str = "",
    cc: str = None,
    bcc: str = None,
    attachments: list[str] = None,
    reply_all: bool = False,
    folder: str = None,
    temp_file_path: str = None,
    in_reply_to: str = None,
    references: str = None,
) -> list[str]:
    """Build mutt command with proper arguments."""
    mutt_cmd = ["mutt"]

    if reply_all:
        mutt_cmd.extend(["-e", "set reply_to_all=yes"])

    if subject:
        mutt_cmd.extend(["-s", subject])

    if cc:
        mutt_cmd.extend(["-c", cc])

    if bcc:
        mutt_cmd.extend(["-b", bcc])

    if temp_file_path:
        mutt_cmd.extend(["-H", temp_file_path])

    if folder:
        mutt_cmd.extend(["-f", folder])

    if attachments:
        mutt_cmd.append("-a")
        mutt_cmd.extend(attachments)
        mutt_cmd.append("--")

    if in_reply_to:
        mutt_cmd.extend(["-e", f"my_hdr In-Reply-To: {in_reply_to}"])

    if references:
        mutt_cmd.extend(["-e", f"my_hdr References: {references}"])

    if to:
        mutt_cmd.append(to)

    return mutt_cmd


def _execute_mutt_interactive(
    mutt_cmd: list[str],
    window_title: str = "Mutt",
) -> None:
    """Execute mutt command interactively."""
    command_str = shlex.join(mutt_cmd)
    launch_interactive(command_str, window_title=window_title, wait=True)


@mcp.tool(
    description="Opens Mutt to compose an email, using your full configuration (signatures, editor). Supports attachments and pre-filled body."
)
def compose(
    to: str = Field(
        ...,
        description="The primary recipient's email address (e.g., 'user@example.com').",
    ),
    subject: str = Field(default="", description="The subject line of the email."),
    cc: str = Field(
        default=None, description="Email address for the 'Cc' (carbon copy) field."
    ),
    bcc: str = Field(
        default=None,
        description="Email address for the 'Bcc' (blind carbon copy) field.",
    ),
    body: str = Field(
        default="", description="Text to pre-populate in the email body."
    ),
    attachments: list[str] = Field(
        default=None, description="A list of local file paths to attach to the email."
    ),
    in_reply_to: str = Field(
        default=None,
        description="The Message-ID of the email being replied to, for proper threading. Used by 'reply' tool.",
    ),
    references: str = Field(
        default=None,
        description="A space-separated list of Message-IDs for threading context. Used by 'reply' tool.",
    ),
) -> OperationResult:
    """Compose an email using mutt's interactive interface."""
    temp_file_path = None

    if body:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_f:
            # Create RFC822 email draft with headers
            temp_f.write(f"To: {to}\n")
            if subject:
                temp_f.write(f"Subject: {subject}\n")
            if cc:
                temp_f.write(f"Cc: {cc}\n")
            if bcc:
                temp_f.write(f"Bcc: {bcc}\n")
            if in_reply_to:
                temp_f.write(f"In-Reply-To: {in_reply_to}\n")
            if references:
                temp_f.write(f"References: {references}\n")
            temp_f.write("\n")  # Empty line separates headers from body
            temp_f.write(body)
            if not body.endswith("\n"):
                temp_f.write("\n")  # Ensure proper line ending
            temp_file_path = temp_f.name

    # Consolidate command building
    mutt_cmd = _build_mutt_command(
        to=to if not body else None,  # Pass None for args handled by draft file
        subject=subject if not body else None,
        cc=cc if not body else None,
        bcc=bcc if not body else None,
        attachments=attachments,
        temp_file_path=temp_file_path,
        in_reply_to=in_reply_to if not body else None,
        references=references if not body else None,
    )

    window_title = f"Mutt: {subject or 'New Email'}"
    launch_interactive(shlex.join(mutt_cmd), window_title=window_title, wait=True)

    attachment_info = f" with {len(attachments)} attachment(s)" if attachments else ""

    return OperationResult(
        status="success",
        message=f"Email composition completed: {to}{attachment_info}",
    )


@mcp.tool(
    description="""Opens Mutt in interactive terminal to reply to specific email by message ID. Supports reply-all mode and initial body text. Headers auto-populated from original message."""
)
def reply(
    message_id: str = Field(
        ..., description="The notmuch message ID of the email to reply to."
    ),
    reply_all: bool = Field(
        default=False,
        description="If True, reply to all recipients (To and Cc) of the original message.",
    ),
    body: str = Field(
        default="",
        description="Text to add to the top of the reply, above the quoted original message.",
    ),
) -> OperationResult:
    """Reply to an email using compose with extracted reply data."""

    # Import notmuch show to get original message data
    from mcp_handley_lab.email.notmuch.tool import _get_message_from_raw_source, show

    # Get original message data
    result = show(f"id:{message_id}")
    original_msg = result[0]
    raw_msg = _get_message_from_raw_source(message_id)

    # Extract reply data
    reply_to = original_msg.from_address
    reply_cc = original_msg.to_address if reply_all else None

    # Build subject with Re: prefix
    original_subject = original_msg.subject
    reply_subject = (
        f"Re: {original_subject}"
        if not original_subject.startswith("Re: ")
        else original_subject
    )

    # Build threading headers
    in_reply_to = raw_msg.get("Message-ID")
    existing_references = raw_msg.get("References")
    references = (
        f"{existing_references} {in_reply_to}" if existing_references else in_reply_to
    )

    # Build reply body
    reply_separator = f"On {original_msg.date}, {original_msg.from_address} wrote:"
    quoted_body_lines = [
        f"> {line}" for line in original_msg.body_markdown.splitlines()
    ]
    quoted_body = "\n".join(quoted_body_lines)

    # Combine user's body + separator + quoted original
    complete_reply_body = (
        f"{body}\n\n{reply_separator}\n{quoted_body}"
        if body
        else f"{reply_separator}\n{quoted_body}"
    )

    # Use compose with extracted data
    return compose(
        to=reply_to,
        cc=reply_cc,
        subject=reply_subject,
        body=complete_reply_body,
        in_reply_to=in_reply_to,
        references=references,
    )


@mcp.tool(
    description="""Opens Mutt in interactive terminal to forward specific email by message ID. Supports pre-populated recipient and initial commentary. Original message included per your configuration."""
)
def forward(
    message_id: str = Field(
        ..., description="The notmuch message ID of the email to forward."
    ),
    to: str = Field(
        default="",
        description="The recipient's email address for the forwarded message. If empty, Mutt will prompt for it.",
    ),
    body: str = Field(
        default="",
        description="Commentary to add to the top of the email, above the forwarded message.",
    ),
) -> OperationResult:
    """Forward an email using compose with extracted forward data."""

    # Import notmuch show to get original message data

    from mcp_handley_lab.email.notmuch.tool import show

    # Get original message data
    result = show(f"id:{message_id}")
    original_msg = result[0]

    # Build forward subject with Fwd: prefix
    original_subject = original_msg.subject
    forward_subject = (
        f"Fwd: {original_subject}"
        if not original_subject.startswith("Fwd: ")
        else original_subject
    )

    # Use original message content with normalized line endings
    forwarded_content = "\n".join(original_msg.body_markdown.splitlines())

    # Build forward body using mutt's configured format
    forward_intro = f"----- Forwarded message from {original_msg.from_address} -----"
    forward_trailer = "----- End forwarded message -----"

    # Combine user's body + intro + original message + trailer
    complete_forward_body = (
        f"{body}\n\n{forward_intro}\n{forwarded_content}\n{forward_trailer}"
        if body
        else f"{forward_intro}\n{forwarded_content}\n{forward_trailer}"
    )

    # Use compose with extracted data (no threading headers for forwards)
    return compose(
        to=to,
        subject=forward_subject,
        body=complete_forward_body,
    )


@mcp.tool(
    description="""Lists all configured mailboxes from Mutt configuration. Useful for discovering folder names for move operations and understanding your email folder structure."""
)
def list_folders() -> list[str]:
    """List available mailboxes from mutt configuration."""
    result = _execute_mutt_command(["mutt", "-Q", "mailboxes"])

    if not result or "mailboxes=" not in result:
        return []

    folders_part = result.split("mailboxes=", 1)[1].strip('"')
    folders = [f.strip() for f in folders_part.split() if f.strip()]

    return folders


@mcp.tool(
    description="""Opens Mutt in interactive terminal focused on specific folder. Full functionality available for reading, replying, and managing emails within that mailbox. Supports smart folder resolution for shortcuts like =INBOX."""
)
def open_folder(
    folder: str = Field(
        default=None,
        description="The mail folder to open. Examples: '=INBOX' (auto-detects account), 'Hermes/INBOX', '~/mail/Hermes/INBOX', or blank for default inbox. Use 'list_folders' to see all options.",
    ),
) -> OperationResult:
    """Open mutt with a specific folder."""
    try:
        if folder:
            # Resolve folder with smart handling
            resolved_folder, extra_args = _resolve_folder(folder)

            # Build mutt command with resolved folder and any extra args
            mutt_cmd = ["mutt"] + extra_args
            if resolved_folder:
                mutt_cmd.extend(["-f", resolved_folder])

            window_title = f"Mutt: {folder}"
        else:
            # No folder specified - open default inbox
            mutt_cmd = ["mutt"]
            window_title = "Mutt: Inbox"

        _execute_mutt_interactive(mutt_cmd, window_title=window_title)

        return OperationResult(
            status="success",
            message=f"Opened {'folder: ' + folder if folder else 'default inbox'}",
        )
    except ValueError as e:
        return OperationResult(status="error", message=str(e))


@mcp.tool(description="Checks Mutt Tool server status and mutt command availability.")
def server_info() -> ServerInfo:
    """Get server status and mutt version."""
    result = _execute_mutt_command(["mutt", "-v"])
    version_lines = result.split("\n")
    version_line = version_lines[0] if version_lines else "Unknown version"

    return ServerInfo(
        name="Mutt Tool",
        version=version_line,
        status="active",
        capabilities=[
            "compose",
            "reply",
            "forward",
            "move",
            "list_folders",
            "open_folder",
            "server_info",
        ],
        dependencies={"mutt": version_line},
    )
