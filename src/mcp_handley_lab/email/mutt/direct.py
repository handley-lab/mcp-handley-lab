"""Direct (non-interactive) email composition: MIME construction, draft storage, msmtp piping.

Used for programmatic email sending.
with a two-step draft/approve workflow.
"""

import contextlib
import mimetypes
import os
import secrets
import subprocess
import time
import uuid
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from mcp_handley_lab.email.common import _get_account_config
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

DRAFTS_DIR = (
    Path(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")))
    / "mcp-email"
    / "drafts"
)
DRAFT_MAX_AGE_SECONDS = 3600  # 1 hour


def build_mime_message(
    to: str,
    subject: str,
    body: str,
    from_addr: str,
    cc: str = "",
    bcc: str = "",
    in_reply_to: str = "",
    references: str = "",
    attachments: list[str] | None = None,
    correlation_id: str = "",
) -> EmailMessage:
    """Construct a complete RFC822 MIME message."""
    # Validate headers
    _reject_header_injection(to, "To")
    _reject_header_injection(subject, "Subject")
    _reject_header_injection(from_addr, "From")
    if cc:
        _reject_header_injection(cc, "Cc")
    if bcc:
        _reject_header_injection(bcc, "Bcc")
    if in_reply_to:
        _reject_header_injection(in_reply_to, "In-Reply-To")
    if references:
        _reject_header_injection(references, "References")

    msg = EmailMessage()

    msg.set_content(body)
    if attachments:
        for filepath in attachments:
            path = Path(filepath)
            file_data = path.read_bytes()
            mime_type, _ = mimetypes.guess_type(str(path))
            if mime_type:
                maintype, subtype = mime_type.split("/", 1)
            else:
                maintype, subtype = "application", "octet-stream"
            msg.add_attachment(
                file_data,
                maintype=maintype,
                subtype=subtype,
                filename=path.name,
            )

    # Set headers after content (EmailMessage requires content first)
    msg["From"] = from_addr
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    if correlation_id:
        msg["X-MCP-Correlation-Id"] = correlation_id

    return msg


def save_draft(
    to: str,
    subject: str = "",
    body: str = "",
    cc: str = "",
    bcc: str = "",
    in_reply_to: str = "",
    references: str = "",
    attachments: list[str] | None = None,
    account: str = "",
) -> OperationResult:
    """Save an email as a draft for approval before sending.

    Returns OperationResult with draft_id, account, and preview
    (preview includes from, to, subject, body, confirmation_code).
    """
    # Resolve from address
    config = _get_account_config(account)
    from_addr = config["from"]
    resolved_account = config["account"]

    # Generate IDs
    draft_id = _generate_draft_id()
    correlation_id = str(uuid.uuid4())
    confirmation_code = secrets.token_hex(3)  # 6 hex chars

    # Build MIME message (attachment read errors are surfaced as OperationResult)
    try:
        msg = build_mime_message(
            to=to,
            subject=subject,
            body=body,
            from_addr=from_addr,
            cc=cc,
            bcc=bcc,
            in_reply_to=in_reply_to,
            references=references,
            attachments=attachments,
            correlation_id=correlation_id,
        )
    except (FileNotFoundError, PermissionError, OSError) as exc:
        return OperationResult(
            status="error",
            message=f"Failed to read attachment: {exc}",
        )

    # Store confirmation code in a custom header (stripped before sending)
    msg["X-MCP-Confirmation-Code"] = confirmation_code
    msg["X-MCP-Account"] = resolved_account

    # Save to drafts directory
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(DRAFTS_DIR, 0o700)
    draft_path = DRAFTS_DIR / f"{draft_id}.eml"
    draft_path.write_bytes(msg.as_bytes())
    draft_path.chmod(0o600)

    # Cleanup expired drafts
    _cleanup_expired_drafts()

    # Build preview (full body for approval; truncated at 20k for safety)
    max_body = 20000
    attachment_names = [Path(a).name for a in attachments] if attachments else []
    preview = {
        "from": from_addr,
        "to": to,
        "subject": subject,
        "body": body[:max_body] + ("..." if len(body) > max_body else ""),
        "confirmation_code": confirmation_code,
    }
    if cc:
        preview["cc"] = cc
    if bcc:
        preview["bcc"] = bcc
    if attachment_names:
        preview["attachments"] = attachment_names

    return OperationResult(
        status="success",
        message="Draft saved. Present to user for approval before sending.",
        data={
            "draft_id": draft_id,
            "account": resolved_account,
            "preview": preview,
        },
    )


def send_draft(draft_id: str, confirmation_code: str = "") -> OperationResult:
    """Send a previously saved draft via msmtp.

    Args:
        draft_id: Draft ID returned by save_draft.
        confirmation_code: If provided, must match the code from save_draft.
    """
    draft_path = DRAFTS_DIR / f"{draft_id}.eml"
    if not draft_path.exists():
        raise ValueError(
            f"Draft '{draft_id}' not found. It may have expired (1 hour TTL) or been discarded."
        )

    # Check expiry
    age = time.time() - draft_path.stat().st_mtime
    if age > DRAFT_MAX_AGE_SECONDS:
        draft_path.unlink(missing_ok=True)
        raise ValueError(
            f"Draft '{draft_id}' has expired ({age:.0f}s old, max {DRAFT_MAX_AGE_SECONDS}s)."
        )

    email_bytes = draft_path.read_bytes()

    # Parse headers for verification and matching
    from email import policy
    from email.parser import BytesParser

    msg = BytesParser(policy=policy.default).parsebytes(email_bytes)

    # Verify confirmation code if provided
    if confirmation_code:
        stored_code = msg.get("X-MCP-Confirmation-Code", "")
        if stored_code != confirmation_code:
            raise ValueError("Confirmation code does not match. Send aborted.")

    # Extract matching data (including Bcc for recipient matching)
    correlation_id = msg.get("X-MCP-Correlation-Id", "")
    subject = msg.get("Subject", "")
    account = msg.get("X-MCP-Account", "")
    recipients = _extract_addr_specs(msg.get("To", ""))
    if msg.get("Cc"):
        recipients.extend(_extract_addr_specs(msg["Cc"]))
    if msg.get("Bcc"):
        recipients.extend(_extract_addr_specs(msg["Bcc"]))

    # Strip internal headers and Bcc before sending
    for header in ("X-MCP-Confirmation-Code", "X-MCP-Account", "Bcc"):
        if msg.get(header):
            del msg[header]
    send_bytes = msg.as_bytes()

    # Record msmtp log position
    log_size_before = _get_msmtp_log_size()

    # Send via mcp-msmtp-capture → msmtp
    # mcp-msmtp-capture (capture.py) passes all argv[1:] directly to msmtp
    # Account is always resolved at draft creation time (save_draft), so the
    # --read-envelope-from fallback only applies if X-MCP-Account was absent.
    cmd = ["mcp-msmtp-capture"]
    if account:
        cmd.extend(["-a", account, "-t"])
    else:
        cmd.extend(["--read-envelope-from", "-t"])

    try:
        result = subprocess.run(cmd, input=send_bytes, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        return OperationResult(
            status="error",
            message="msmtp timed out after 120 seconds",
            data={"send_status": "failed", "smtp": {}},
        )

    log_size_after = _get_msmtp_log_size()

    # Check send status
    smtp_data = {}
    if log_size_after > log_size_before:
        send_occurred, send_successful, smtp_data = _check_recent_send(
            log_size_before, log_size_after
        )
    else:
        send_occurred = False
        send_successful = False

    # Subprocess return code is authoritative
    if result.returncode != 0:
        stderr_text = result.stderr.decode(errors="replace").strip()
        return OperationResult(
            status="error",
            message=f"msmtp failed (exit {result.returncode}): {stderr_text}",
            data={"send_status": "failed", "smtp": _build_smtp_dict(smtp_data)},
        )

    # Process succeeded but SMTP may have reported failure
    if send_occurred and not send_successful:
        return OperationResult(
            status="error",
            message=f"SMTP delivery failed for draft '{draft_id}'",
            data={"send_status": "failed", "smtp": _build_smtp_dict(smtp_data)},
        )

    # Success path — find captured email

    captured_path, capture_status, capture_reason = _find_captured_email(
        correlation_id,
        subject,
        recipients,
        from_addr=smtp_data.get("from"),
        mail_size_bytes=smtp_data.get("mail_size_bytes"),
        envelope_recipients=smtp_data.get("all_recipients"),
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
            with contextlib.suppress(OSError):
                captured_path.unlink()
        except Exception:
            capture_status = "not_found"
            capture_reason = "parse_error"

    # If no log evidence available, note that delivery is unverified
    send_status = "sent" if send_occurred else "sent_unverified"

    data = {
        "send_status": send_status,
        "smtp": _build_smtp_dict(smtp_data),
    }
    if not send_occurred:
        data["warning"] = (
            "msmtp log not available; SMTP acceptance could not be verified."
        )
    if captured:
        data["sent"] = captured
    elif send_occurred:
        warning_key = (
            capture_status if capture_status == "not_configured" else capture_reason
        )
        data["warning"] = CAPTURE_WARNINGS.get(warning_key, CAPTURE_WARNING_DEFAULT)

    # Delete draft when msmtp log confirms successful delivery (exitcode=EX_OK).
    # For sent_unverified (no log evidence), draft is retained for debugging/retries.
    if send_occurred:
        draft_path.unlink(missing_ok=True)

    to_addr = msg.get("To", draft_id)
    if send_occurred:
        return OperationResult(
            status="success",
            message=f"Email sent successfully: {to_addr}",
            data=data,
        )
    return OperationResult(
        status="warning",
        message=f"Email sent (unverified): {to_addr}",
        data=data,
    )


def read_draft(draft_id: str) -> OperationResult:
    """Read a draft's full content for review before sending.

    Returns OperationResult with from, to, cc, bcc, subject, body, attachments.
    """
    draft_path = DRAFTS_DIR / f"{draft_id}.eml"
    if not draft_path.exists():
        raise ValueError(
            f"Draft '{draft_id}' not found. It may have expired (1 hour TTL) or been discarded."
        )

    from email import policy
    from email.parser import BytesParser

    msg = BytesParser(policy=policy.default).parsebytes(draft_path.read_bytes())

    # Extract body
    if msg.is_multipart():
        part = msg.get_body(preferencelist=("plain",))
        body_text = part.get_content() if part else ""
    else:
        body_text = msg.get_content()

    # Extract attachment metadata
    attachments = []
    if msg.is_multipart():
        for part in msg.iter_attachments():
            filename = part.get_filename() or "unnamed"
            try:
                payload = part.get_payload(decode=True)
                size = len(payload) if payload else 0
            except Exception:
                size = 0
            attachments.append(
                {
                    "filename": filename,
                    "content_type": part.get_content_type(),
                    "size_bytes": size,
                }
            )

    draft_data = {
        "draft_id": draft_id,
        "from": msg.get("From", ""),
        "to": msg.get("To", ""),
        "subject": msg.get("Subject", ""),
        "body": body_text,
    }
    if msg.get("Cc"):
        draft_data["cc"] = msg["Cc"]
    if msg.get("Bcc"):
        draft_data["bcc"] = msg["Bcc"]
    if attachments:
        draft_data["attachments"] = attachments

    return OperationResult(
        status="success",
        message=f"Draft '{draft_id}' content.",
        data=draft_data,
    )


def discard_draft(draft_id: str) -> OperationResult:
    """Delete a saved draft."""
    draft_path = DRAFTS_DIR / f"{draft_id}.eml"
    if draft_path.exists():
        draft_path.unlink()
        return OperationResult(
            status="success",
            message=f"Draft '{draft_id}' discarded.",
        )
    return OperationResult(
        status="warning",
        message=f"Draft '{draft_id}' not found (may have already expired or been discarded).",
    )


def list_drafts() -> OperationResult:
    """List all pending drafts with their previews."""
    _cleanup_expired_drafts()

    if not DRAFTS_DIR.exists():
        return OperationResult(
            status="success",
            message="No drafts.",
            data={"drafts": []},
        )

    from email import policy
    from email.parser import HeaderParser

    drafts = []
    for eml_file in sorted(DRAFTS_DIR.glob("*.eml")):
        try:
            # Read only headers
            header_bytes = []
            with open(eml_file, "rb") as f:
                for line in f:
                    if line in (b"\r\n", b"\n"):
                        break
                    header_bytes.append(line)
            headers_text = b"".join(header_bytes).decode("utf-8", errors="replace")
            msg = HeaderParser(policy=policy.default).parsestr(headers_text)

            age = time.time() - eml_file.stat().st_mtime
            drafts.append(
                {
                    "draft_id": eml_file.stem,
                    "from": msg.get("From", ""),
                    "to": msg.get("To", ""),
                    "subject": msg.get("Subject", ""),
                    "age_seconds": round(age),
                }
            )
        except (OSError, ValueError):
            continue

    return OperationResult(
        status="success",
        message=f"{len(drafts)} draft(s) pending.",
        data={"drafts": drafts},
    )


def _generate_draft_id() -> str:
    """Generate a unique 12-char hex draft ID, retrying on collision."""
    for _ in range(10):
        draft_id = uuid.uuid4().hex[:12]
        if not (DRAFTS_DIR / f"{draft_id}.eml").exists():
            return draft_id
    raise RuntimeError("Failed to generate unique draft ID after 10 attempts")


def _cleanup_expired_drafts() -> None:
    """Delete draft files older than DRAFT_MAX_AGE_SECONDS."""
    if not DRAFTS_DIR.exists():
        return
    now = time.time()
    for eml_file in DRAFTS_DIR.glob("*.eml"):
        try:
            if now - eml_file.stat().st_mtime > DRAFT_MAX_AGE_SECONDS:
                eml_file.unlink()
        except OSError:
            pass
