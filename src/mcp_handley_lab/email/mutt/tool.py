"""Mutt tool for interactive email composition via MCP."""

import builtins
import contextlib
import os
import shlex
import tempfile
import time
import uuid
from email import policy
from email.parser import BytesParser, HeaderParser
from email.utils import getaddresses
from pathlib import Path

from pydantic import Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.common.terminal import launch_interactive
from mcp_handley_lab.email.common import mcp
from mcp_handley_lab.shared.models import OperationResult

# Capture directory for msmtp wrapper
CAPTURE_DIR = (
    Path(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")))
    / "mcp-email"
    / "captured"
)
# Per plan: retain captured files for 5 min on failure for debugging,
# delete immediately on successful parsing
CAPTURE_MAX_AGE_SECONDS = 300  # 5 minutes (cleanup old/orphaned files)
CAPTURE_RETRY_SECONDS = 5  # Wait up to 5s for captured file
CAPTURE_RETRY_INTERVAL = 0.2  # Check every 200ms

# Warnings shown only when capture fails (keyed by status or reason)
CAPTURE_WARNINGS = {
    "not_configured": """WARNING: Capture not configured. The body shown is the DRAFT, not what was actually sent.
To capture actual sent content, create ~/.local/bin/mcp-msmtp-capture:
  #!/bin/sh
  umask 077
  CAPDIR="${XDG_STATE_HOME:-$HOME/.local/state}/mcp-email/captured"
  mkdir -p "$CAPDIR"
  tee "$CAPDIR/$(date +%Y%m%dT%H%M%S).$$.eml" | exec msmtp "$@"
Then update mutt: set sendmail = "mcp-msmtp-capture -a <account>" """,
    "ambiguous": "WARNING: Multiple captured messages match; cannot determine which was sent. Body shown is DRAFT.",
    "parse_error": "WARNING: Captured message found but failed to parse. Body shown is DRAFT.",
    "timeout": "WARNING: No matching captured message found. Body shown is DRAFT.",
}
CAPTURE_WARNING_DEFAULT = (
    "WARNING: Could not capture sent content. Body shown is DRAFT."
)


def _build_smtp_dict(data: dict) -> dict:
    """Build normalized smtp structure from msmtp log data."""
    return {
        "message_id": data.get("message_id", ""),
        "recipients": data.get("all_recipients", []),
        "mail_size_bytes": data.get("mail_size_bytes", 0),
        "status_code": data.get("smtp_status_code", ""),
    }


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


def _cleanup_old_captures() -> None:
    """Delete captured email files older than CAPTURE_MAX_AGE_SECONDS."""
    if not CAPTURE_DIR.exists():
        return
    now = time.time()
    for eml_file in CAPTURE_DIR.glob("*.eml"):
        try:
            if now - eml_file.stat().st_mtime > CAPTURE_MAX_AGE_SECONDS:
                eml_file.unlink()
        except OSError:
            pass  # File may have been deleted already


def _extract_addr_specs(header_value: str) -> list[str]:
    """Extract normalized email addresses from an RFC822 header value.

    Uses email.utils.getaddresses() for proper RFC822 parsing (handles
    quoted names, groups, encoded words). Returns lowercase addr-specs only.
    """
    if not header_value:
        return []
    parsed = getaddresses([header_value])
    return [addr.lower() for _name, addr in parsed if addr]


def _scan_captured_headers(path: Path) -> dict:
    """Scan only headers of a captured .eml file for matching purposes.

    Fast, lightweight scan that reads only headers (stops at blank line).
    Uses HeaderParser which doesn't parse body/attachments.
    Returns dict with: correlation_id, subject, from, to, cc, file_size
    """
    # Read only header portion (up to first blank line)
    header_bytes = []
    with builtins.open(path, "rb") as f:
        for line in f:
            if line in (b"\r\n", b"\n"):
                break
            header_bytes.append(line)
    headers_text = b"".join(header_bytes).decode("utf-8", errors="replace")

    # Parse headers only (no body processing)
    msg = HeaderParser(policy=policy.default).parsestr(headers_text)

    return {
        "correlation_id": msg.get("X-MCP-Correlation-Id", ""),
        "subject": msg.get("Subject", ""),
        "from": _extract_addr_specs(msg.get("From", "")),
        "to": _extract_addr_specs(msg.get("To", "")),
        "cc": _extract_addr_specs(msg.get("Cc", "")),
        "file_size": path.stat().st_size,
    }


def _parse_captured_email(path: Path) -> dict:
    """Parse a captured .eml file and extract relevant fields.

    Full parse including body and attachments. Only call for the selected file.
    Returns dict with: subject, to, cc, from, body_text, attachments
    """
    with builtins.open(path, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)

    result = {
        "subject": msg.get("Subject", ""),
        "to": _extract_addr_specs(msg.get("To", "")),
        "cc": _extract_addr_specs(msg.get("Cc", "")),
        "from": _extract_addr_specs(msg.get("From", "")),
        "correlation_id": msg.get("X-MCP-Correlation-Id", ""),
        "body_text": "",
        "attachments": [],
    }

    # Extract body and attachments
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = part.get("Content-Disposition", "")

            if "attachment" in content_disposition:
                # Attachment - extract metadata only
                filename = part.get_filename() or "unnamed"
                try:
                    payload = part.get_payload(decode=True)
                    size = len(payload) if payload else 0
                except Exception:
                    size = 0
                result["attachments"].append(
                    {
                        "filename": filename,
                        "content_type": content_type,
                        "size_bytes": size,
                    }
                )
            elif content_type == "text/plain" and not result["body_text"]:
                # First text/plain part is the body
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        result["body_text"] = payload.decode(charset)
                    except (UnicodeDecodeError, LookupError):
                        result["body_text"] = payload.decode("utf-8", errors="replace")
    else:
        # Simple message
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                result["body_text"] = payload.decode(charset)
            except (UnicodeDecodeError, LookupError):
                result["body_text"] = payload.decode("utf-8", errors="replace")

    return result


def _find_captured_email(
    correlation_id: str,
    subject: str,
    draft_recipients: list[str],
    from_addr: str | None = None,
    mail_size_bytes: int | None = None,
    envelope_recipients: list[str] | None = None,
) -> tuple[Path | None, str, str]:
    """Find a captured email file by correlation ID or fallback matching.

    Primary match: X-MCP-Correlation-Id header
    Fallback: subject + recipients + from + approximate size (within 20%)

    Args:
        correlation_id: UUID for primary matching
        subject: Email subject for fallback
        draft_recipients: To+Cc from draft (used if envelope_recipients unavailable)
        from_addr: From address from msmtp log
        mail_size_bytes: Message size from msmtp log
        envelope_recipients: All recipients from msmtp log (To+Cc+Bcc)

    Returns: (path or None, status, reason)
    - status is one of: captured, not_configured, not_found
    - reason provides detail for not_found cases (ambiguous, timeout, etc.)
    """
    if not CAPTURE_DIR.exists():
        return None, "not_configured", ""

    # Clean up old captures first
    _cleanup_old_captures()

    # Use msmtp envelope recipients if available, else fall back to draft To/Cc
    # Normalize to lowercase addr-specs
    if envelope_recipients:
        expected_recipients = {r.lower() for r in envelope_recipients}
    else:
        expected_recipients = {r.lower() for r in draft_recipients}

    # Retry loop to handle filesystem sync delays
    deadline = time.time() + CAPTURE_RETRY_SECONDS

    while time.time() < deadline:
        candidates = []
        now = time.time()

        for eml_file in CAPTURE_DIR.glob("*.eml"):
            try:
                mtime = eml_file.stat().st_mtime
                # Only consider files from last 60 seconds
                if now - mtime > 60:
                    continue

                # Use lightweight header scan (no body/attachment parsing)
                headers = _scan_captured_headers(eml_file)

                # Primary match: correlation ID
                if correlation_id and headers.get("correlation_id") == correlation_id:
                    return eml_file, "captured", ""

                # Fallback match: subject + recipients + from + size
                parsed_recipients = set(headers.get("to", []) + headers.get("cc", []))

                subject_match = headers.get("subject", "") == subject

                # Recipient matching: captured To+Cc should be subset of envelope recipients
                # (Bcc won't appear in captured headers but is in envelope_recipients)
                recipients_match = parsed_recipients <= expected_recipients

                # From match (if provided)
                from_match = True
                if from_addr:
                    parsed_from = headers.get("from", [])
                    from_match = from_addr.lower() in parsed_from

                # Size match (within 20% tolerance, if provided)
                size_match = True
                if mail_size_bytes and mail_size_bytes > 0:
                    file_size = headers.get("file_size", 0)
                    tolerance = mail_size_bytes * 0.2
                    size_match = abs(file_size - mail_size_bytes) <= tolerance

                if subject_match and recipients_match and from_match and size_match:
                    candidates.append(eml_file)

            except (OSError, ValueError):
                continue  # Skip unreadable files

        # If we have exactly one fallback match, use it
        if len(candidates) == 1:
            return candidates[0], "captured", ""

        # Multiple matches = ambiguous (per plan: return not_found with note)
        if len(candidates) > 1:
            return None, "not_found", "ambiguous"

        # No matches yet, wait and retry
        time.sleep(CAPTURE_RETRY_INTERVAL)

    # Timeout reached
    return None, "not_found", "timeout"


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
        return os.path.getsize(log_path)
    except FileNotFoundError:
        return 0  # No log file yet - first email


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

    Only call after confirming log file exists and grew (via _get_msmtp_log_size).

    Returns:
        (send_occurred, send_successful, data_dict)
    """
    log_path = os.path.expanduser("~/.msmtp.log")
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


@mcp.tool(
    description="""Send an email via Mutt. Supports compose (new), reply, and forward modes. For replying, prefer using 'reply' mode with a message_id to maintain thread context - the full conversation thread will be included in quotes. All emails open in Mutt for user sign-off before sending."""
)
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
            _resolve_message_id,
            _show_email,
        )

        # Resolve abbreviated message ID
        message_id = _resolve_message_id(message_id)

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
            _resolve_message_id,
            _show_email,
        )

        # Resolve abbreviated message ID
        message_id = _resolve_message_id(message_id)

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
