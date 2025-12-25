"""Mutt tool for interactive email composition via MCP."""

import builtins
import os
import shlex
import tempfile
from pathlib import Path

from pydantic import Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.common.terminal import launch_interactive
from mcp_handley_lab.email.common import mcp
from mcp_handley_lab.shared.models import OperationResult


def _execute_mutt_command(cmd: list[str], input_text: str = None) -> str:
    """Execute mutt command and return output."""
    input_bytes = input_text.encode() if input_text else None
    stdout, stderr = run_command(cmd, input_data=input_bytes)
    return stdout.decode().strip()


def _query_mutt_var(var: str) -> str | None:
    """Query a mutt configuration variable."""
    result = _execute_mutt_command(["mutt", "-Q", var])
    if "=" in result:
        return result.partition("=")[2].strip().strip('"')
    return None


MAILDIR_LEAFS = {"cur", "new", "tmp"}


def _is_maildir(path: Path) -> bool:
    """Check if a path is a valid Maildir directory."""
    return path.is_dir() and (path / "cur").is_dir()


def _find_account_folders(root: Path, mailbox: str) -> list[tuple[str, str]]:
    """Find all account folders containing a specific mailbox using shallow directory scan."""
    if not root.is_dir():
        return []

    candidates = []
    for account_dir in root.iterdir():
        if not account_dir.is_dir() or account_dir.name in MAILDIR_LEAFS:
            continue

        # Case 1: Mailbox is the account root itself (e.g., for INBOX)
        if mailbox == "INBOX" and _is_maildir(account_dir):
            candidates.append((account_dir.name, str(account_dir)))

        # Case 2: Mailbox is a subdirectory of the account
        mailbox_path = account_dir / mailbox
        if _is_maildir(mailbox_path):
            candidates.append((account_dir.name, str(mailbox_path)))

    return candidates


def _resolve_folder(folder: str) -> str:
    """Resolve a folder path with smart handling of = and + shortcuts."""
    if not folder:
        return ""

    # 1. Handle absolute paths and IMAP URLs - pass through
    if folder.startswith(("/", "imap://", "imaps://", "~")):
        return os.path.expanduser(folder)

    # 2. Get mutt's folder variable, with a sensible default
    folder_root = _query_mutt_var("folder") or "~/mail"
    folder_root_path = Path(os.path.expanduser(folder_root))

    # 3. Normalize folder name (e.g., "INBOX" -> "=INBOX")
    if not folder.startswith(("=", "+")):
        folder = f"={folder}"

    mailbox = folder[1:]

    # 4. Handle explicit paths like "Account/INBOX"
    if "/" in mailbox:
        absolute_path = folder_root_path / mailbox
        if _is_maildir(absolute_path):
            return str(absolute_path)
        raise ValueError(
            f"Folder '{absolute_path}' does not exist or is not a Maildir."
        )

    # 5. Handle ambiguous names like "INBOX" - find candidates
    # Check directly under folder_root first, as it's a common pattern for Sent, Drafts etc.
    direct_path = folder_root_path / mailbox
    if _is_maildir(direct_path):
        return str(direct_path)

    candidates = _find_account_folders(folder_root_path, mailbox)

    # 6. Resolve ambiguity using environment variable or count
    default_account = os.environ.get("MCP_EMAIL_DEFAULT_ACCOUNT")
    if default_account:
        for account_name, path in candidates:
            if account_name == default_account:
                return path

    if len(candidates) == 1:
        return candidates[0][1]

    if len(candidates) > 1:
        suggestions = [f"{name}/{mailbox}" for name, _ in candidates]
        raise ValueError(
            f"Ambiguous mailbox '{mailbox}'. Found in: {', '.join(suggestions)}. "
            f"Specify the full path (e.g., '{suggestions[0]}') or set MCP_EMAIL_DEFAULT_ACCOUNT."
        )

    # 7. No candidates found
    raise ValueError(
        f"Mailbox '{mailbox}' not found in '{folder_root_path}' or any accounts. "
        "Check available folders with 'list_folders'."
    )


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

        with builtins.open(log_path) as f:
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


def _compose_email(
    to: str,
    subject: str = "",
    cc: str = None,
    bcc: str = None,
    body: str = "",
    attachments: list[str] = None,
    in_reply_to: str = None,
    references: str = None,
) -> OperationResult:
    """Internal implementation of email composition."""
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
    description="""Send an email via Mutt. Supports compose (new), reply, and forward modes. For replying, prefer using 'reply' mode with a message_id to maintain thread context - the full conversation thread will be included in quotes. All emails open in Mutt for user sign-off before sending."""
)
def send(
    to: str = Field(
        default="",
        description="Recipient email address. Required for compose/forward, auto-populated for reply.",
    ),
    subject: str = Field(default="", description="The subject line of the email."),
    body: str = Field(
        default="",
        description="Email body text. For reply/forward, added above quoted/forwarded content.",
    ),
    cc: str = Field(
        default=None, description="Email address for the 'Cc' (carbon copy) field."
    ),
    bcc: str = Field(
        default=None,
        description="Email address for the 'Bcc' (blind carbon copy) field.",
    ),
    attachments: list[str] = Field(
        default=None, description="A list of local file paths to attach to the email."
    ),
    message_id: str = Field(
        default=None,
        description="For reply/forward: the notmuch message ID of the email to reply to or forward.",
    ),
    mode: str = Field(
        default="compose",
        description="Email mode: 'compose' (new email), 'reply', or 'forward'.",
    ),
    reply_all: bool = Field(
        default=False,
        description="For reply mode: if True, reply to all recipients (To and Cc).",
    ),
    thread_context: int = Field(
        default=5,
        description="For reply mode: number of previous thread messages to include (0 to disable, -1 for all).",
    ),
) -> OperationResult:
    """Send an email using mutt's interactive interface."""
    if mode == "compose":
        if not to:
            raise ValueError("'to' is required for compose mode")
        return _compose_email(
            to=to,
            subject=subject,
            cc=cc,
            bcc=bcc,
            body=body,
            attachments=attachments,
        )

    elif mode == "reply":
        if not message_id:
            raise ValueError("'message_id' is required for reply mode")

        # Import notmuch functions to get original message data
        from mcp_handley_lab.email.notmuch.tool import (
            _get_message_from_raw_source,
            _get_thread_messages,
            _is_sent_message,
            _show_email,
        )

        # Get original message data
        result = _show_email(f"id:{message_id}")
        original_msg = result[0]
        raw_msg = _get_message_from_raw_source(message_id)

        # Extract reply data - for sent emails, reply to recipient; otherwise use Reply-To/From
        reply_to_header = raw_msg.get("Reply-To")
        if _is_sent_message(message_id):
            # Replying to my own sent email - use original recipient
            reply_to = original_msg.to_address
        else:
            # Normal reply - use Reply-To or From
            reply_to = reply_to_header if reply_to_header else original_msg.from_address

        # For reply-all, CC should be original To + original Cc recipients
        reply_cc = cc  # Start with user-provided cc
        if reply_all:
            cc_recipients = []
            if (
                original_msg.to_address
                and original_msg.to_address != "[Unknown Recipient]"
            ):
                cc_recipients.append(original_msg.to_address)
            original_cc = raw_msg.get("Cc")
            if original_cc:
                cc_recipients.append(original_cc)
            if cc_recipients:
                base_cc = cc + ", " if cc else ""
                reply_cc = base_cc + ", ".join(cc_recipients)

        # Build subject with Re: prefix
        original_subject = original_msg.subject
        reply_subject = (
            subject
            if subject
            else (
                f"Re: {original_subject}"
                if not original_subject.startswith("Re: ")
                else original_subject
            )
        )

        # Build threading headers
        in_reply_to = raw_msg.get("Message-ID")
        existing_references = raw_msg.get("References")
        references = (
            f"{existing_references} {in_reply_to}"
            if existing_references
            else in_reply_to
        )

        # Get thread context (excluding the message being replied to)
        max_msgs = None if thread_context < 0 else thread_context
        thread_messages = _get_thread_messages(message_id, max_messages=max_msgs)

        # Build thread history (older messages first)
        thread_parts = []
        for msg_date, from_addr, _subj, msg_body in thread_messages:
            separator = f"\n--- On {msg_date}, {from_addr} wrote ---\n"
            quoted = "\n".join(f"> {line}" for line in msg_body.splitlines())
            thread_parts.append(f"{separator}{quoted}")

        thread_history = "\n".join(thread_parts)

        # Build reply with immediate parent at top, then thread history
        reply_separator = f"On {original_msg.date}, {original_msg.from_address} wrote:"
        quoted_body_lines = [
            f"> {line}" for line in original_msg.body_markdown.splitlines()
        ]
        quoted_body = "\n".join(quoted_body_lines)

        if thread_history:
            complete_reply_body = (
                f"{body}\n\n{reply_separator}\n{quoted_body}\n\n--- Previous messages in thread ---{thread_history}"
                if body
                else f"{reply_separator}\n{quoted_body}\n\n--- Previous messages in thread ---{thread_history}"
            )
        else:
            complete_reply_body = (
                f"{body}\n\n{reply_separator}\n{quoted_body}"
                if body
                else f"{reply_separator}\n{quoted_body}"
            )

        return _compose_email(
            to=reply_to,
            cc=reply_cc,
            bcc=bcc,
            subject=reply_subject,
            body=complete_reply_body,
            attachments=attachments,
            in_reply_to=in_reply_to,
            references=references,
        )

    elif mode == "forward":
        if not message_id:
            raise ValueError("'message_id' is required for forward mode")

        # Import notmuch function to get original message data
        from mcp_handley_lab.email.notmuch.tool import (
            _get_message_from_raw_source,
            _show_email,
        )

        result = _show_email(f"id:{message_id}")
        original_msg = result[0]
        raw_msg = _get_message_from_raw_source(message_id)

        # Build forward subject with Fwd: prefix
        original_subject = original_msg.subject
        forward_subject = (
            subject
            if subject
            else (
                f"Fwd: {original_subject}"
                if not original_subject.startswith("Fwd: ")
                else original_subject
            )
        )

        # Build forward header block
        forward_intro = (
            f"----- Forwarded message from {original_msg.from_address} -----"
        )
        header_lines = [f"\nDate: {original_msg.date}"]
        header_lines.append(f"From: {original_msg.from_address}")
        if original_msg.to_address and original_msg.to_address != "[Unknown Recipient]":
            header_lines.append(f"To: {original_msg.to_address}")
        original_cc = raw_msg.get("Cc")
        if original_cc:
            header_lines.append(f"CC: {original_cc}")
        header_lines.append(f"Subject: {original_subject}")
        header_block = "\n".join(header_lines)

        # Build forward body
        forwarded_content = "\n".join(original_msg.body_markdown.splitlines())
        forward_trailer = "----- End forwarded message -----"

        complete_forward_body = (
            f"{body}\n\n{forward_intro}\n{header_block}\n\n{forwarded_content}\n\n{forward_trailer}"
            if body
            else f"{forward_intro}\n{header_block}\n\n{forwarded_content}\n\n{forward_trailer}"
        )

        return _compose_email(
            to=to,
            cc=cc,
            bcc=bcc,
            subject=forward_subject,
            body=complete_forward_body,
            attachments=attachments,
        )

    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'compose', 'reply', or 'forward'.")
