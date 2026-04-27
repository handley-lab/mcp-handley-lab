"""Mutt tool for interactive email composition via MCP."""

import contextlib
import os
import shlex
import tempfile
import uuid
from pathlib import Path

from pydantic import Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.common.terminal import launch_interactive
from mcp_handley_lab.email.common import _list_accounts, mcp
from mcp_handley_lab.email.mutt.capture_utils import (
    CAPTURE_WARNING_DEFAULT,
    CAPTURE_WARNINGS,
    _build_smtp_dict,
    _check_recent_send,
    _extract_addr_specs,
    _find_captured_email,
    _get_msmtp_log_size,
    _parse_captured_email,
    _reject_header_injection,
)
from mcp_handley_lab.shared.models import OperationResult


def _execute_mutt_command(cmd: list[str], input_text: str | None = None) -> str:
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


def _build_mutt_command(
    to: str | None = None,
    subject: str = "",
    cc: str | None = None,
    bcc: str | None = None,
    attachments: list[str] | None = None,
    reply_all: bool = False,
    folder: str | None = None,
    temp_file_path: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
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
        send_occurred, send_successful, data = _check_recent_send(
            log_size_before, log_size_after
        )
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
    cc: str | None = None,
    bcc: str | None = None,
    body: str = "",
    attachments: list[str] | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
    account: str = "",
) -> OperationResult:
    """Internal implementation of email composition."""
    # Reject header injection in user-provided fields
    _reject_header_injection(to, "To")
    if subject:
        _reject_header_injection(subject, "Subject")
    if cc:
        _reject_header_injection(cc, "Cc")
    if bcc:
        _reject_header_injection(bcc, "Bcc")
    if in_reply_to:
        _reject_header_injection(in_reply_to, "In-Reply-To")
    if references:
        _reject_header_injection(references, "References")

    temp_file_path = None

    # Generate correlation ID for capture matching
    correlation_id = str(uuid.uuid4())

    # Always create a draft file to include the correlation ID header
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as temp_f:
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
        # Add correlation ID for capture matching
        temp_f.write(f"X-MCP-Correlation-Id: {correlation_id}\n")
        temp_f.write("\n")  # Empty line separates headers from body
        if body:
            temp_f.write(body)
            if not body.endswith("\n"):
                temp_f.write("\n")  # Ensure proper line ending
        temp_file_path = temp_f.name

    # Build recipients list for capture matching (normalize using getaddresses)
    recipients = _extract_addr_specs(to)
    if cc:
        recipients.extend(_extract_addr_specs(cc))

    # Build mutt command with draft file
    mutt_cmd = _build_mutt_command(
        attachments=attachments,
        temp_file_path=temp_file_path,
    )

    window_title = f"Mutt: {subject or 'New Email'}"
    try:
        exit_code, status, smtp_data = _execute_mutt_interactive(
            mutt_cmd, window_title=window_title
        )
    finally:
        # Clean up temp draft file (contains potentially sensitive content)
        if temp_file_path:
            with contextlib.suppress(OSError):
                Path(temp_file_path).unlink()

    attachment_info = f" with {len(attachments)} attachment(s)" if attachments else ""

    # Build response based on status
    if status == "success":
        send_status = "sent"

        # Try to find and parse captured email
        # Use msmtp log data for fallback matching (envelope recipients include Bcc)
        captured_path, capture_status, capture_reason = _find_captured_email(
            correlation_id,
            subject,
            recipients,  # draft To+Cc as fallback
            from_addr=smtp_data.get("from"),
            mail_size_bytes=smtp_data.get("mail_size_bytes"),
            envelope_recipients=smtp_data.get("all_recipients"),  # msmtp envelope
        )

        captured = None
        if captured_path:
            try:
                parsed = _parse_captured_email(captured_path)
                captured = {
                    "subject": parsed["subject"],
                    "to": parsed["to"],
                    "cc": parsed["cc"],
                    "body": parsed["body_text"],
                    "attachments": parsed["attachments"],
                }
                # Security: delete captured file after successful parsing
                with contextlib.suppress(OSError):
                    captured_path.unlink()
            except Exception:
                capture_status = "not_found"
                capture_reason = "parse_error"

        # Build lean response
        data = {
            "send_status": send_status,
            "smtp": _build_smtp_dict(smtp_data),
        }

        if captured:
            data["sent"] = captured
        else:
            warning_key = (
                capture_status if capture_status == "not_configured" else capture_reason
            )
            data["warning"] = CAPTURE_WARNINGS.get(warning_key, CAPTURE_WARNING_DEFAULT)

        return OperationResult(
            status="success",
            message=f"Email sent successfully: {to}{attachment_info}",
            data=data,
        )

    elif status == "cancelled":
        return OperationResult(
            status="cancelled",
            message=f"Email composition cancelled: {to}{attachment_info}",
            data={"send_status": "cancelled"},
        )

    else:  # status == "error"
        data = {
            "send_status": "failed",
            "smtp": _build_smtp_dict(smtp_data),
        }
        return OperationResult(
            status="error",
            message=f"Email sending failed: {to}{attachment_info} (exit code: {exit_code})",
            data=data,
        )


# =============================================================================
# Tool Registration with Module-Level Description Injection
# =============================================================================

_SEND_DESCRIPTION = """Send an email via Mutt or save as draft for programmatic approval.

Modes: compose (new), reply, forward, send_draft, discard_draft, list_drafts, read_draft.
For reply/forward, use message_id from the read tool.

Draft workflow (for headless/WhatsApp use):
1. send(draft=True, to=..., subject=..., body=...) → returns draft_id + preview + confirmation_code
2. Present draft to user, wait for approval
3. send(mode='send_draft', draft_id=..., confirmation_code=...) → sends via msmtp
To read full draft: send(mode='read_draft', draft_id=...) → full body + headers + attachments
To discard: send(mode='discard_draft', draft_id=...)
To list pending: send(mode='list_drafts')

Interactive mode (default): Opens Mutt for user sign-off before sending."""


def _inject_accounts() -> None:
    """Inject available accounts into send description."""
    global _SEND_DESCRIPTION
    accounts = _list_accounts()
    if accounts:
        accounts_text = "\n".join(f"- {a}" for a in accounts)
        _SEND_DESCRIPTION += f"\n\nAvailable accounts:\n{accounts_text}"


_inject_accounts()


def send(
    to: str = Field(
        default="",
        description="Recipient address. Prefer 'Firstname Lastname <email>' format. Required for compose/forward, auto-populated for reply.",
    ),
    subject: str = Field(default="", description="The subject line of the email."),
    body: str = Field(
        default="",
        description="Email body text. For reply/forward, added above quoted/forwarded content.",
    ),
    body_file: str = Field(
        default="",
        description="Path to file containing email body. Supports RFC822 format (headers + blank line + body). "
        "File headers (To, Subject, Cc, Bcc) used as defaults unless overridden. Mutually exclusive with body.",
    ),
    cc: str = Field(
        default=None,
        description="Carbon copy address. Prefer 'Firstname Lastname <email>' format.",
    ),
    bcc: str = Field(
        default=None,
        description="Blind carbon copy address. Prefer 'Firstname Lastname <email>' format.",
    ),
    attachments: list[str] = Field(
        default=None, description="A list of local file paths to attach to the email."
    ),
    message_id: str = Field(
        default=None,
        description="For reply/forward: the notmuch message ID of the email to reply to or forward. Supports abbreviated IDs.",
    ),
    mode: str = Field(
        default="compose",
        description="Email mode: 'compose', 'reply', 'forward', 'send_draft', 'discard_draft', 'list_drafts', or 'read_draft'.",
    ),
    reply_all: bool = Field(
        default=False,
        description="For reply mode: if True, reply to all recipients (To and Cc).",
    ),
    thread_context: int = Field(
        default=5,
        description="For reply mode: number of previous thread messages to include (0 to disable, -1 for all).",
    ),
    draft: bool = Field(
        default=False,
        description="Save as draft for approval instead of opening Mutt. Returns draft_id and preview.",
    ),
    draft_id: str = Field(
        default="",
        description="Draft ID for send_draft/discard_draft modes.",
    ),
    account: str = Field(
        default="",
        description="msmtp account name to send from (e.g., 'Hermes', 'PolyChord'). "
        "Determines the From address and SMTP server. "
        "Defaults to msmtp default account.",
    ),
    confirmation_code: str = Field(
        default="",
        description="For send_draft: confirmation code returned by draft creation.",
    ),
) -> OperationResult:
    """Send an email or manage drafts."""
    from mcp_handley_lab.email.mutt.shared import send as _send

    return _send(
        to=to,
        subject=subject,
        body=body,
        body_file=body_file,
        cc=cc,
        bcc=bcc,
        attachments=attachments,
        message_id=message_id,
        mode=mode,
        reply_all=reply_all,
        thread_context=thread_context,
        draft=draft,
        draft_id=draft_id,
        account=account,
        confirmation_code=confirmation_code,
    )


mcp.add_tool(send, name="send", description=_SEND_DESCRIPTION)
