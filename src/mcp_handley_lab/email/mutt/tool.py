"""Mutt tool for interactive email composition via MCP."""

import os
import shlex
import tempfile

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


def _get_msmtp_log_size() -> int:
    """Get current size of msmtp log file."""
    log_path = os.path.expanduser("~/.msmtp.log")
    try:
        return os.path.getsize(log_path) if os.path.exists(log_path) else 0
    except OSError:
        return 0


def _parse_msmtp_log_entry(log_line: str) -> dict:
    """Parse an msmtp log entry to extract detailed information.

    Example log line:
    Aug 23 09:16:33 host=smtp.office365.com tls=on auth=on user=wh260@cam.ac.uk
    from=wh260@cam.ac.uk recipients=wh260@cam.ac.uk,cc@example.com,bcc@example.com
    mailsize=273 smtpstatus=250 smtpmsg='250 2.0.0 OK <aKj2OhY87X3qWDJs@maxwell> [Hostname=...]'
    exitcode=EX_OK
    """
    data = {}

    # Extract timestamp (first 15 chars typically)
    if len(log_line) >= 15:
        data["timestamp"] = log_line[:15].strip()

    # Extract key=value pairs
    import re

    # Extract recipients (can be comma-separated)
    recipients_match = re.search(r"recipients=([^\s]+)", log_line)
    if recipients_match:
        recipients_str = recipients_match.group(1)
        data["all_recipients"] = recipients_str.split(",")

    # Extract from address
    from_match = re.search(r"from=([^\s]+)", log_line)
    if from_match:
        data["from"] = from_match.group(1)

    # Extract mail size
    size_match = re.search(r"mailsize=(\d+)", log_line)
    if size_match:
        data["mail_size_bytes"] = int(size_match.group(1))

    # Extract SMTP status code
    status_match = re.search(r"smtpstatus=(\d+)", log_line)
    if status_match:
        data["smtp_status_code"] = status_match.group(1)

    # Extract SMTP message (including message ID)
    msg_match = re.search(r"smtpmsg='([^']+)'", log_line)
    if msg_match:
        smtp_msg = msg_match.group(1)
        data["smtp_message"] = smtp_msg

        # Try to extract message ID from SMTP response
        msg_id_match = re.search(r"<([^>]+)>", smtp_msg)
        if msg_id_match:
            data["message_id"] = msg_id_match.group(1)

    # Extract error message if present
    error_match = re.search(r"errormsg='([^']+)'", log_line)
    if error_match:
        data["error_message"] = error_match.group(1)

    # Extract exit code
    exit_match = re.search(r"exitcode=(\w+)", log_line)
    if exit_match:
        data["exit_code"] = exit_match.group(1)

    # Extract host
    host_match = re.search(r"host=([^\s]+)", log_line)
    if host_match:
        data["smtp_host"] = host_match.group(1)

    return data


def _check_recent_send() -> tuple[bool, bool, dict]:
    """Check if a recent send occurred and extract detailed information.

    Returns:
        (send_occurred, send_successful, data_dict)
    """
    log_path = os.path.expanduser("~/.msmtp.log")
    try:
        if not os.path.exists(log_path):
            return False, False, {}

        with open(log_path) as f:
            lines = f.readlines()
            if not lines:
                return False, False, {}

            # Get the last line (most recent entry)
            last_line = lines[-1].strip()
            if not last_line:
                return False, False, {}

            # Check if it contains exitcode info (indicates a send attempt)
            if "exitcode=" in last_line:
                # Parse the log entry for detailed data
                data = _parse_msmtp_log_entry(last_line)

                # Check if it was successful (EX_OK = 0)
                send_successful = "exitcode=EX_OK" in last_line
                return True, send_successful, data

        return False, False, {}
    except OSError:
        return False, False, {}


def _execute_mutt_interactive(
    mutt_cmd: list[str],
    window_title: str = "Mutt",
) -> tuple[int, str, dict]:
    """Execute mutt command interactively and determine send status.

    Returns:
        (exit_code, status, data) where status is "success", "error", or "cancelled"
    """
    log_size_before = _get_msmtp_log_size()

    command_str = shlex.join(mutt_cmd)
    _, exit_code = launch_interactive(command_str, window_title=window_title, wait=True)

    log_size_after = _get_msmtp_log_size()

    # If log size increased, check the recent send status
    if log_size_after > log_size_before:
        send_occurred, send_successful, data = _check_recent_send()
        if send_occurred:
            return exit_code, "success" if send_successful else "error", data

    # No new log entry means user cancelled/quit without sending
    if exit_code == 0:
        return exit_code, "cancelled", {}
    else:
        # Non-zero exit code is an error regardless
        return exit_code, "error", {"exit_code": exit_code}


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

        mutt_cmd = _build_mutt_command(
            to=None,  # Already in draft file
            subject=None,  # Already in draft file
            cc=None,  # Already in draft file
            bcc=None,  # Already in draft file
            attachments=attachments,
            temp_file_path=temp_file_path,
            in_reply_to=None,  # Already in draft file
            references=None,  # Already in draft file
        )

        window_title = f"Mutt: {subject or 'New Email'}"
        exit_code, status, data = _execute_mutt_interactive(
            mutt_cmd, window_title=window_title
        )
    else:
        mutt_cmd = _build_mutt_command(
            to=to,
            subject=subject,
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            in_reply_to=in_reply_to,
            references=references,
        )

        window_title = f"Mutt: {subject or 'New Email'}"
        exit_code, status, data = _execute_mutt_interactive(
            mutt_cmd, window_title=window_title
        )

    attachment_info = f" with {len(attachments)} attachment(s)" if attachments else ""

    if status == "success":
        return OperationResult(
            status="success",
            message=f"Email sent successfully: {to}{attachment_info}",
            data=data,
        )
    elif status == "cancelled":
        return OperationResult(
            status="cancelled",
            message=f"Email composition cancelled: {to}{attachment_info}",
            data=data,
        )
    else:  # status == "error"
        return OperationResult(
            status="error",
            message=f"Email sending failed: {to}{attachment_info} (exit code: {exit_code})",
            data=data,
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
    attachments: list[str] = Field(
        default=None, description="A list of local file paths to attach to the email."
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
        bcc=None,
        subject=reply_subject,
        body=complete_reply_body,
        attachments=attachments,
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
    attachments: list[str] = Field(
        default=None, description="A list of local file paths to attach to the email."
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
        cc=None,
        bcc=None,
        subject=forward_subject,
        body=complete_forward_body,
        attachments=attachments,
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
    description="""Opens Mutt in interactive terminal focused on specific folder. Full functionality available for reading, replying, and managing emails within that mailbox."""
)
def open_folder(
    folder: str = Field(
        ...,
        description="The name of the mail folder to open (e.g., '=INBOX'). Use 'list_folders' to see available options.",
    ),
) -> OperationResult:
    """Open mutt with a specific folder."""
    mutt_cmd = _build_mutt_command(folder=folder)
    window_title = f"Mutt: {folder}"
    exit_code, status, data = _execute_mutt_interactive(
        mutt_cmd, window_title=window_title
    )

    if status == "success":
        return OperationResult(
            status="success",
            message=f"Folder session completed with email sent: {folder}",
            data=data,
        )
    elif status == "cancelled":
        return OperationResult(
            status="cancelled", message=f"Folder session closed: {folder}", data=data
        )
    else:  # status == "error"
        return OperationResult(
            status="error",
            message=f"Folder session failed: {folder} (exit code: {exit_code})",
            data=data,
        )


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
