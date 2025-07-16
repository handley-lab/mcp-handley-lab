"""Mutt tool for interactive email composition via MCP."""

import os
import shlex
import tempfile

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
    if "signature=" in sig_result:
        sig_path = sig_result.split("=", 1)[1].strip().strip('"')
        if sig_path.startswith("~"):
            sig_path = os.path.expanduser(sig_path)

        with open(sig_path) as f:
            signature = f.read().strip()
        if signature:
            body_content += f"\n\n{signature}"

    return body_content


def _build_mutt_command(
    to: str = None,
    subject: str = "",
    cc: str = None,
    bcc: str = None,
    attachments: list[str] = None,
    auto_send: bool = False,
    message_id: str = None,
    reply_all: bool = False,
    is_forward: bool = False,
    folder: str = None,
    temp_file_path: str = None,
    in_reply_to: str = None,
    references: str = None,
) -> list[str]:
    """Build mutt command with proper arguments."""
    mutt_cmd = ["mutt"]

    mutt_cmd.extend(["-e", "set autoedit"])

    if auto_send:
        mutt_cmd.extend(["-e", "set postpone=no"])

    if reply_all:
        mutt_cmd.extend(["-e", "set reply_to_all=yes"])
    elif message_id and not is_forward:
        mutt_cmd.extend(["-e", "set reply_to_all=no"])

    if subject:
        mutt_cmd.extend(["-s", subject])

    if cc:
        mutt_cmd.extend(["-c", cc])

    if bcc:
        mutt_cmd.extend(["-b", bcc])

    if temp_file_path:
        mutt_cmd.extend(["-i", temp_file_path])

    if message_id:
        if is_forward:
            mutt_cmd.extend(["-f", f"id:{message_id}"])
        else:
            mutt_cmd.extend(["-H", f"id:{message_id}"])

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
def compose_email(
    to: str,
    subject: str = "",
    cc: str = None,
    bcc: str = None,
    initial_body: str = "",
    attachments: list[str] = None,
    auto_send: bool = False,
    in_reply_to: str = None,
    references: str = None,
) -> OperationResult:
    """Compose an email using mutt's interactive interface."""

    if initial_body:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_f:
            temp_f.write(initial_body)
            temp_file_path = temp_f.name

        try:
            mutt_cmd = _build_mutt_command(
                to=to,
                subject=subject,
                cc=cc,
                bcc=bcc,
                attachments=attachments,
                auto_send=auto_send,
                temp_file_path=temp_file_path,
                in_reply_to=in_reply_to,
                references=references,
            )

            body_content = (
                _prepare_body_with_signature(initial_body) if auto_send else ""
            )
            window_title = f"Mutt: {subject or 'New Email'}"

            _execute_mutt_interactive_or_auto(
                mutt_cmd, auto_send, body_content, window_title
            )
        finally:
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
    description="""Opens Mutt main interface in interactive terminal for reading, searching, and organizing emails. Full access to your complete Mutt configuration and mailboxes."""
)
def open_mutt() -> OperationResult:
    """Open mutt's main interface."""
    launch_interactive("mutt", window_title="Mutt", wait=True)
    return OperationResult(status="success", message="Mutt session completed")


@mcp.tool(
    description="""Opens Mutt in interactive terminal to reply to specific email by message ID. Supports reply-all mode and initial body text. Headers auto-populated from original message."""
)
def reply_to_email(
    message_id: str, reply_all: bool = False, initial_body: str = ""
) -> OperationResult:
    """Reply to an email using compose_email with extracted reply data."""

    # Import notmuch show to get original message data
    from mcp_handley_lab.email.notmuch.tool import _get_message_from_raw_source, show

    # Get original message data
    try:
        result = show(f"id:{message_id}")
        if not result:
            raise ValueError(f"Message not found: {message_id}")

        original_msg = result[0]
        raw_msg = _get_message_from_raw_source(message_id)

        # Extract reply data
        reply_to = original_msg.from_address
        reply_cc = original_msg.to_address if reply_all else None

        # Build subject with Re: prefix
        original_subject = original_msg.subject
        if original_subject.startswith("Re: "):
            reply_subject = original_subject
        else:
            reply_subject = f"Re: {original_subject}"

        # Build threading headers
        in_reply_to = raw_msg.get("Message-ID")
        existing_references = raw_msg.get("References")
        if existing_references:
            references = f"{existing_references} {in_reply_to}"
        else:
            references = in_reply_to

        # Build reply body
        reply_separator = f"On {original_msg.date}, {original_msg.from_address} wrote:"
        quoted_body_lines = []
        for line in original_msg.body_markdown.split("\n"):
            quoted_body_lines.append(f"> {line}")
        quoted_body = "\n".join(quoted_body_lines)

        # Combine user's body + separator + quoted original
        if initial_body:
            complete_reply_body = f"{initial_body}\n\n{reply_separator}\n{quoted_body}"
        else:
            complete_reply_body = f"{reply_separator}\n{quoted_body}"

        # Use compose_email with extracted data
        return compose_email(
            to=reply_to,
            cc=reply_cc,
            subject=reply_subject,
            initial_body=complete_reply_body,
            in_reply_to=in_reply_to,
            references=references,
        )

    except Exception as e:
        return OperationResult(
            status="error", message=f"Failed to reply to message {message_id}: {str(e)}"
        )


@mcp.tool(
    description="""Opens Mutt in interactive terminal to forward specific email by message ID. Supports pre-populated recipient and initial commentary. Original message included per your configuration."""
)
def forward_email(
    message_id: str, to: str = "", initial_body: str = ""
) -> OperationResult:
    """Forward an email using compose_email with extracted forward data."""

    # Import notmuch show to get original message data
    import re

    from mcp_handley_lab.email.notmuch.tool import show

    # Get original message data
    try:
        result = show(f"id:{message_id}")
        if not result:
            raise ValueError(f"Message not found: {message_id}")

        original_msg = result[0]

        # Build forward subject with Fwd: prefix
        original_subject = original_msg.subject
        if original_subject.startswith("Fwd: "):
            forward_subject = original_subject
        else:
            forward_subject = f"Fwd: {original_subject}"

        # Strip signature from forwarded content to prevent duplication
        forwarded_content = original_msg.body_markdown

        # Read user's signature file to strip it from forwarded content
        try:
            import os

            sig_path = os.path.expanduser("~/.mutt/hermes_signature")
            with open(sig_path) as f:
                signature = f.read().strip()

            # Remove signature if it appears at the end of the forwarded content
            signature_pattern = f"--\\s*\\n{re.escape(signature)}"
            forwarded_content = re.sub(
                signature_pattern + r"\s*$", "", forwarded_content, flags=re.MULTILINE
            )

        except (OSError, FileNotFoundError):
            # If signature file not found, continue without stripping
            pass

        # Build forward body using mutt's configured format
        forward_intro = (
            f"----- Forwarded message from {original_msg.from_address} -----"
        )
        forward_trailer = "----- End forwarded message -----"

        # Combine user's body + intro + original message + trailer
        if initial_body:
            complete_forward_body = f"{initial_body}\n\n{forward_intro}\n{forwarded_content}\n{forward_trailer}"
        else:
            complete_forward_body = (
                f"{forward_intro}\n{forwarded_content}\n{forward_trailer}"
            )

        # Use compose_email with extracted data (no threading headers for forwards)
        return compose_email(
            to=to, subject=forward_subject, initial_body=complete_forward_body
        )

    except Exception as e:
        return OperationResult(
            status="error", message=f"Failed to forward message {message_id}: {str(e)}"
        )


@mcp.tool(
    description="""Moves emails between folders using Mutt scripting. Supports single message or batch operations by message ID(s). Default destination is Trash for deletion."""
)
def move_email(
    message_id: str = None, message_ids: list[str] = None, destination: str = "Trash"
) -> OperationResult:
    """Move or delete emails by moving them to specified folder."""

    if not message_id and not message_ids:
        raise ValueError("Must specify either message_id or message_ids")

    messages = [message_id] if message_id else message_ids

    script_commands = []
    for msg_id in messages:
        script_commands.extend(
            [
                f"<search>id:{msg_id}<enter>",
                "<tag-message>",
                f"<tag-prefix><save-message>={destination}<enter>",
                "<untag-pattern>.*<enter>",
            ]
        )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".muttrc", delete=False
    ) as temp_f:
        temp_f.write("".join(f'push "{cmd}"\n' for cmd in script_commands))
        temp_f.write('push "<quit>"\n')
        temp_file_path = temp_f.name

    try:
        _execute_mutt_command(["mutt", "-F", temp_file_path])
    finally:
        os.unlink(temp_file_path)

    action = "Deleted" if destination.lower() == "trash" else f"Moved to {destination}"
    count = len(messages)
    return OperationResult(
        status="success", message=f"{action} {count} message(s) successfully"
    )


@mcp.tool(
    description="""Lists all configured mailboxes from Mutt configuration. Useful for discovering folder names for move_email operations and understanding your email folder structure."""
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
def open_folder(folder: str) -> OperationResult:
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
            "compose_email",
            "open_mutt",
            "reply_to_email",
            "forward_email",
            "move_email",
            "list_folders",
            "open_folder",
            "server_info",
        ],
        dependencies={"mutt": version_line},
    )
