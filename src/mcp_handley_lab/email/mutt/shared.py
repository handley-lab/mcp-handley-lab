"""Core mutt email functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

import re
import tempfile
from email import policy
from email.parser import Parser
from pathlib import Path

from mcp_handley_lab.email.mutt import direct as direct_mod
from mcp_handley_lab.shared.models import OperationResult


def _load_body_file(path: str) -> tuple[str, dict[str, str]]:
    """Load email content from a file, parsing RFC822 headers if present.

    If the file starts with RFC822 headers (e.g. To:, Subject:) followed by
    a blank line, headers are extracted and returned separately. Otherwise
    the entire file content is returned as body text.

    Returns:
        (body_text, headers_dict) where headers_dict may contain:
        to, subject, cc, bcc keys.
    """
    content = Path(path).read_text(encoding="utf-8")

    # Check if file has RFC822 headers: must have a blank line separator
    # and start with a known email header keyword
    known_headers = {"to", "subject", "cc", "bcc", "from", "date", "reply-to"}
    lines = content.splitlines()
    has_blank_line = any(line.strip() == "" for line in lines[1:])
    first_key = (
        lines[0].split(":", 1)[0].strip().lower() if lines and ":" in lines[0] else ""
    )
    if has_blank_line and first_key in known_headers:
        msg = Parser(policy=policy.default).parsestr(content)
        headers = {}
        for key, param in [
            ("to", "To"),
            ("subject", "Subject"),
            ("cc", "Cc"),
            ("bcc", "Bcc"),
        ]:
            value = msg.get(param)
            if value:
                headers[key] = value
        if msg.is_multipart():
            part = msg.get_body(preferencelist=("plain",))
            body = part.get_content() if part else ""
        else:
            body = msg.get_content()
        return body, headers

    return content, {}


def _dispatch(
    draft: bool,
    account: str,
    **email_kwargs,
) -> OperationResult:
    """Route to draft save or interactive Mutt."""
    if draft:
        return direct_mod.save_draft(account=account, **email_kwargs)
    from mcp_handley_lab.email.mutt.tool import _compose_email

    return _compose_email(account=account, **email_kwargs)


def send(
    to: str = "",
    subject: str = "",
    body: str = "",
    body_file: str = "",
    cc: str | None = None,
    bcc: str | None = None,
    attachments: list[str] | None = None,
    message_id: str | None = None,
    mode: str = "compose",
    reply_all: bool = False,
    thread_context: int = 5,
    draft: bool = False,
    draft_id: str = "",
    account: str = "",
    confirmation_code: str = "",
) -> OperationResult:
    """Send an email via Mutt or save as draft for programmatic approval.

    Supports compose (new), reply, and forward modes. For replying, prefer using
    'reply' mode with a message_id to maintain thread context.

    When draft=True, saves email as a draft instead of opening Mutt. Use
    mode='send_draft' to send, 'discard_draft' to delete, 'list_drafts' to list.

    Args:
        to: Recipient address. Prefer 'Firstname Lastname <email>' format.
        subject: The subject line of the email.
        body: Email body text. For reply/forward, added above quoted/forwarded content.
        body_file: Path to file containing email body. Mutually exclusive with body.
        cc: Carbon copy address.
        bcc: Blind carbon copy address.
        attachments: A list of local file paths to attach to the email.
        message_id: For reply/forward: the notmuch message ID.
        mode: Email mode: 'compose', 'reply', 'forward', 'send_draft',
            'discard_draft', or 'list_drafts'.
        reply_all: For reply mode: if True, reply to all recipients.
        thread_context: For reply mode: number of previous thread messages to include.
        draft: Save as draft instead of opening Mutt.
        draft_id: Draft ID for send_draft/discard_draft modes.
        account: msmtp account name for draft From address. Uses default if empty.
        confirmation_code: For send_draft: verification code from save_draft.

    Returns:
        OperationResult with send status and details.
    """
    # Draft lifecycle modes
    if mode == "send_draft":
        if not draft_id:
            raise ValueError("'draft_id' is required for send_draft mode")
        return direct_mod.send_draft(draft_id, confirmation_code)
    if mode == "discard_draft":
        if not draft_id:
            raise ValueError("'draft_id' is required for discard_draft mode")
        return direct_mod.discard_draft(draft_id)
    if mode == "list_drafts":
        return direct_mod.list_drafts()
    if mode == "read_draft":
        if not draft_id:
            raise ValueError("'draft_id' is required for read_draft mode")
        return direct_mod.read_draft(draft_id)

    if body and body_file:
        raise ValueError("'body' and 'body_file' are mutually exclusive")

    if body_file:
        file_body, file_headers = _load_body_file(body_file)
        body = file_body
        # File headers are defaults — explicit params override
        if not to and "to" in file_headers:
            to = file_headers["to"]
        if not subject and "subject" in file_headers:
            subject = file_headers["subject"]
        if cc is None and "cc" in file_headers:
            cc = file_headers["cc"]
        if bcc is None and "bcc" in file_headers:
            bcc = file_headers["bcc"]

    if mode == "compose":
        if not to:
            raise ValueError("'to' is required for compose mode")
        return _dispatch(
            draft=draft,
            account=account,
            to=to,
            subject=subject,
            cc=cc or "",
            bcc=bcc or "",
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

        return _dispatch(
            draft=draft,
            account=account,
            to=reply_to,
            cc=reply_cc or "",
            bcc=bcc or "",
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

        # Extract original attachments to temp dir for forwarding
        with tempfile.TemporaryDirectory(prefix="mcp-fwd-") as tmpdir:
            tmpdir_path = Path(tmpdir)
            original_attachments = []
            for part in raw_msg.walk():
                if part.get_content_disposition() != "attachment":
                    continue
                if part_filename := part.get_filename():
                    clean_filename = re.sub(
                        r'[\\/*?:"<>|]', "_", Path(part_filename).name
                    )
                    file_path = tmpdir_path / clean_filename
                    counter = 1
                    stem, suffix = file_path.stem, file_path.suffix
                    while file_path.exists():
                        file_path = tmpdir_path / f"{stem}_{counter}{suffix}"
                        counter += 1
                    if payload := part.get_payload(decode=True):
                        file_path.write_bytes(payload)
                        original_attachments.append(str(file_path))

            all_attachments = original_attachments + (attachments or [])

            return _dispatch(
                draft=draft,
                account=account,
                to=to,
                cc=cc or "",
                bcc=bcc or "",
                subject=forward_subject,
                body=complete_forward_body,
                attachments=all_attachments or None,
            )

    else:
        raise ValueError(
            f"Unknown mode: {mode}. Use 'compose', 'reply', 'forward', "
            "'send_draft', 'discard_draft', 'list_drafts', or 'read_draft'."
        )
