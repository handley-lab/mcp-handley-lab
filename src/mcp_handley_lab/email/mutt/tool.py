"""Mutt tool for interactive email composition via MCP."""
import os
import tempfile

from mcp_handley_lab.common.terminal import launch_interactive
from mcp_handley_lab.email.common import mcp
from mcp_handley_lab.shared.models import OperationResult, ServerInfo


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
) -> OperationResult:
    """Compose an email using mutt's interactive interface."""

    mutt_cmd = ["mutt"]

    mutt_cmd.extend(["-e", "set autoedit"])

    if auto_send:
        mutt_cmd.extend(["-e", "set postpone=no"])

    if subject:
        mutt_cmd.extend(["-s", subject])

    if cc:
        mutt_cmd.extend(["-c", cc])

    if bcc:
        mutt_cmd.extend(["-b", bcc])

    if attachments:
        mutt_cmd.append("-a")
        mutt_cmd.extend(attachments)
        mutt_cmd.append("--")

    mutt_cmd.append(to)

    if initial_body:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=True
        ) as temp_f:
            temp_f.write(initial_body)
            temp_f.flush()

            mutt_cmd.extend(["-i", temp_f.name])

            if auto_send:
                mutt_cmd_str = " ".join(
                    f"'{arg}'" if " " in arg else arg for arg in mutt_cmd
                )
                body_content = initial_body if initial_body else "Automated email"

                sig_result = _run_command(["mutt", "-Q", "signature"])
                if "signature=" in sig_result:
                    sig_path = sig_result.split("=", 1)[1].strip().strip('"')
                    if sig_path.startswith("~"):
                        sig_path = os.path.expanduser(sig_path)

                    try:
                        with open(sig_path) as f:
                            signature = f.read().strip()
                        if signature:
                            body_content += f"\n\n{signature}"
                    except FileNotFoundError:
                        pass

                mutt_cmd = mutt_cmd_str.split()
                _run_command(mutt_cmd, input_text=body_content)

                attachment_info = (
                    f" with {len(attachments)} attachment(s)" if attachments else ""
                )
                return OperationResult(
                    status="success",
                    message=f"Email sent automatically: {to}{attachment_info}",
                )
            else:
                mutt_cmd_str = " ".join(
                    f"'{arg}'" if " " in arg else arg for arg in mutt_cmd
                )
                window_title = f"Mutt: {subject or 'New Email'}"
                launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

                attachment_info = (
                    f" with {len(attachments)} attachment(s)" if attachments else ""
                )
                return OperationResult(
                    status="success",
                    message=f"Email composition completed: {to}{attachment_info}",
                )
    else:
        if auto_send:
            mutt_cmd_str = " ".join(
                f"'{arg}'" if " " in arg else arg for arg in mutt_cmd
            )
            body_content = "Automated email"

            sig_result = _run_command(["mutt", "-Q", "signature"])
            if "signature=" in sig_result:
                sig_path = sig_result.split("=", 1)[1].strip().strip('"')
                if sig_path.startswith("~"):
                    sig_path = os.path.expanduser(sig_path)

                try:
                    with open(sig_path) as f:
                        signature = f.read().strip()
                    if signature:
                        body_content += f"\n\n{signature}"
                except FileNotFoundError:
                    pass

            mutt_cmd = mutt_cmd_str.split()
            _run_command(mutt_cmd, input_text=body_content)

            attachment_info = (
                f" with {len(attachments)} attachment(s)" if attachments else ""
            )
            return OperationResult(
                status="success",
                message=f"Email sent automatically: {to}{attachment_info}",
            )
        else:
            mutt_cmd_str = " ".join(
                f"'{arg}'" if " " in arg else arg for arg in mutt_cmd
            )
            window_title = f"Mutt: {subject or 'New Email'}"
            launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

            attachment_info = (
                f" with {len(attachments)} attachment(s)" if attachments else ""
            )
            return OperationResult(
                status="success",
                message=f"Email composition completed: {to}{attachment_info}",
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
    """Reply to an email using mutt's reply functionality."""

    mutt_cmd = ["mutt"]

    mutt_cmd.extend(["-e", "set autoedit"])

    if reply_all:
        mutt_cmd.extend(["-e", "set reply_to_all=yes"])
    else:
        mutt_cmd.extend(["-e", "set reply_to_all=no"])

    mutt_cmd.extend(["-H", f"id:{message_id}"])

    if initial_body:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=True
        ) as temp_f:
            temp_f.write(initial_body)
            temp_f.flush()

            mutt_cmd.extend(["-i", temp_f.name])

            mutt_cmd_str = " ".join(
                f"'{arg}'" if " " in arg else arg for arg in mutt_cmd
            )
            window_title = f"Mutt Reply: {message_id[:20]}..."
            launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

            reply_type = "Reply to all" if reply_all else "Reply"
            return OperationResult(
                status="success",
                message=f"{reply_type} completed for message: {message_id}",
            )
    else:
        mutt_cmd_str = " ".join(f"'{arg}'" if " " in arg else arg for arg in mutt_cmd)
        window_title = f"Mutt Reply: {message_id[:20]}..."
        launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

        reply_type = "Reply to all" if reply_all else "Reply"
        return OperationResult(
            status="success",
            message=f"{reply_type} completed for message: {message_id}",
        )


@mcp.tool(
    description="""Opens Mutt in interactive terminal to forward specific email by message ID. Supports pre-populated recipient and initial commentary. Original message included per your configuration."""
)
def forward_email(
    message_id: str, to: str = "", initial_body: str = ""
) -> OperationResult:
    """Forward an email using mutt's forward functionality."""

    mutt_cmd = ["mutt"]

    mutt_cmd.extend(["-e", "set autoedit"])

    mutt_cmd.extend(["-f", f"id:{message_id}"])

    if to:
        mutt_cmd.append(to)

    if initial_body:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=True
        ) as temp_f:
            temp_f.write(initial_body)
            temp_f.flush()

            mutt_cmd.extend(["-i", temp_f.name])

            mutt_cmd_str = " ".join(
                f"'{arg}'" if " " in arg else arg for arg in mutt_cmd
            )
            window_title = f"Mutt Forward: {message_id[:20]}..."
            launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

            return OperationResult(
                status="success", message=f"Forward completed for message: {message_id}"
            )
    else:
        mutt_cmd_str = " ".join(f"'{arg}'" if " " in arg else arg for arg in mutt_cmd)
        window_title = f"Mutt Forward: {message_id[:20]}..."
        launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

        return OperationResult(
            status="success", message=f"Forward completed for message: {message_id}"
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

    with tempfile.NamedTemporaryFile(mode="w", suffix=".muttrc", delete=True) as temp_f:
        temp_f.write("".join(f'push "{cmd}"\n' for cmd in script_commands))
        temp_f.write('push "<quit>"\n')
        temp_f.flush()

        mutt_cmd = ["mutt", "-F", temp_f.name]
        _run_command(mutt_cmd)

        action = (
            "Deleted" if destination.lower() == "trash" else f"Moved to {destination}"
        )
        count = len(messages)
        return OperationResult(
            status="success", message=f"{action} {count} message(s) successfully"
        )


@mcp.tool(
    description="""Lists all configured mailboxes from Mutt configuration. Useful for discovering folder names for move_email operations and understanding your email folder structure."""
)
def list_folders() -> list[str]:
    """List available mailboxes from mutt configuration."""
    result = _run_command(["mutt", "-Q", "mailboxes"])

    mailboxes_line = result.strip()
    if not mailboxes_line or "mailboxes=" not in mailboxes_line:
        return []

    folders_part = mailboxes_line.split("mailboxes=", 1)[1].strip('"')
    folders = [f.strip() for f in folders_part.split() if f.strip()]

    return folders


@mcp.tool(
    description="""Opens Mutt in interactive terminal focused on specific folder. Full functionality available for reading, replying, and managing emails within that mailbox."""
)
def open_folder(folder: str) -> OperationResult:
    """Open mutt with a specific folder."""

    mutt_cmd = ["mutt", "-f", folder]

    mutt_cmd_str = " ".join(f"'{arg}'" if " " in arg else arg for arg in mutt_cmd)
    window_title = f"Mutt: {folder}"
    launch_interactive(mutt_cmd_str, window_title=window_title, wait=True)

    return OperationResult(status="success", message=f"Opened folder: {folder}")


@mcp.tool(description="Checks Mutt Tool server status and mutt command availability.")
def server_info() -> ServerInfo:
    """Get server status and mutt version."""
    result = _run_command(["mutt", "-v"])
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
