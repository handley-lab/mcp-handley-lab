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


def _prepare_body_with_signature(initial_body: str = "") -> str:
    """Prepare email body with signature if configured."""
    body_content = initial_body or "Automated email"

    sig_result = _execute_mutt_command(["mutt", "-Q", "signature"])
    sig_path = sig_result.split("=", 1)[1].strip().strip('"')
    sig_path = os.path.expanduser(sig_path) if sig_path.startswith("~") else sig_path

    with open(sig_path) as f:
        signature = f.read().strip()

    return body_content + f"\n\n{signature}" if signature else body_content


def _build_mutt_command(
    to: str = None,
    subject: str = "",
    cc: str = None,
    bcc: str = None,
    attachments: list[str] = None,
    auto_send: bool = False,
    reply_all: bool = False,
    folder: str = None,
    temp_file_path: str = None,
    in_reply_to: str = None,
    references: str = None,
) -> list[str]:
    """Build mutt command with proper arguments."""
    mutt_cmd = ["mutt"]

    if auto_send:
        mutt_cmd.extend(["-e", "set postpone=no"])

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


def _execute_mutt_interactive_or_auto(
    mutt_cmd: list[str],
    auto_send: bool = False,
    body_content: str = "",
    window_title: str = "Mutt",
) -> None:
    """Execute mutt command either interactively or automatically."""
    if auto_send:
        _execute_mutt_command(mutt_cmd, input_text=body_content)
    else:
        command_str = shlex.join(mutt_cmd)
        launch_interactive(command_str, window_title=window_title, wait=True)


@mcp.tool(
    description="Opens Mutt to compose an email, using your full configuration (signatures, editor). Supports attachments, pre-filled body, and an `auto_send` option that bypasses interactive review."
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
    initial_body: str = Field(
        default="", description="Text to pre-populate in the email body."
    ),
    attachments: list[str] = Field(
        default=None, description="A list of local file paths to attach to the email."
    ),
    auto_send: bool = Field(
        default=False,
        description="If True, sends the email automatically without opening the interactive Mutt editor. A signature will be appended if configured. WARNING: Only use with explicit user permission as this bypasses review.",
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

    if initial_body:
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
            temp_f.write(initial_body)
            if not initial_body.endswith("\n"):
                temp_f.write("\n")  # Ensure proper line ending
            temp_file_path = temp_f.name

        mutt_cmd = _build_mutt_command(
            to=None,  # Already in draft file
            subject=None,  # Already in draft file
            cc=None,  # Already in draft file
            bcc=None,  # Already in draft file
            attachments=attachments,
            auto_send=auto_send,
            temp_file_path=temp_file_path,
            in_reply_to=None,  # Already in draft file
            references=None,  # Already in draft file
        )

        body_content = _prepare_body_with_signature(initial_body) if auto_send else ""
        window_title = f"Mutt: {subject or 'New Email'}"

        _execute_mutt_interactive_or_auto(
            mutt_cmd, auto_send, body_content, window_title
        )

        # Only delete temp file if auto_send (mutt finished using it)
        if auto_send:
            os.unlink(temp_file_path)
    else:
        mutt_cmd = _build_mutt_command(
            to=to,
            subject=subject,
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            auto_send=auto_send,
            in_reply_to=in_reply_to,
            references=references,
        )

        body_content = _prepare_body_with_signature() if auto_send else ""
        window_title = f"Mutt: {subject or 'New Email'}"

        _execute_mutt_interactive_or_auto(
            mutt_cmd, auto_send, body_content, window_title
        )

    attachment_info = f" with {len(attachments)} attachment(s)" if attachments else ""
    action = "sent automatically" if auto_send else "composition completed"

    return OperationResult(
        status="success",
        message=f"Email {action}: {to}{attachment_info}",
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
    initial_body: str = Field(
        default="",
        description="Text to add to the top of the reply, above the quoted original message.",
    ),
    auto_send: bool = Field(
        default=False,
        description="If True, sends the reply automatically without opening the interactive Mutt editor. WARNING: Only use with explicit user permission as this bypasses review.",
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
        f"{initial_body}\n\n{reply_separator}\n{quoted_body}"
        if initial_body
        else f"{reply_separator}\n{quoted_body}"
    )

    # Use compose with extracted data
    return compose(
        to=reply_to,
        cc=reply_cc,
        subject=reply_subject,
        initial_body=complete_reply_body,
        in_reply_to=in_reply_to,
        references=references,
        auto_send=auto_send,
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
    initial_body: str = Field(
        default="",
        description="Commentary to add to the top of the email, above the forwarded message.",
    ),
    auto_send: bool = Field(
        default=False,
        description="If True, sends the forward automatically without opening the interactive Mutt editor. WARNING: Only use with explicit user permission as this bypasses review.",
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
        f"{initial_body}\n\n{forward_intro}\n{forwarded_content}\n{forward_trailer}"
        if initial_body
        else f"{forward_intro}\n{forwarded_content}\n{forward_trailer}"
    )

    # Use compose with extracted data (no threading headers for forwards)
    return compose(
        to=to,
        subject=forward_subject,
        initial_body=complete_forward_body,
        auto_send=auto_send,
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
    _execute_mutt_interactive_or_auto(mutt_cmd, window_title=window_title)

    return OperationResult(status="success", message=f"Opened folder: {folder}")


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
