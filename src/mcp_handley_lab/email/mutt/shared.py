"""Core mutt email functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

from mcp_handley_lab.email.mutt.tool import _compose_email
from mcp_handley_lab.shared.models import OperationResult


def send(
    to: str = "",
    subject: str = "",
    body: str = "",
    cc: str | None = None,
    bcc: str | None = None,
    attachments: list[str] | None = None,
    message_id: str | None = None,
    mode: str = "compose",
    reply_all: bool = False,
    thread_context: int = 5,
) -> OperationResult:
    """Send an email via Mutt.

    Supports compose (new), reply, and forward modes. For replying, prefer using
    'reply' mode with a message_id to maintain thread context - the full conversation
    thread will be included in quotes. All emails open in Mutt for user sign-off
    before sending.

    Args:
        to: Recipient address. Prefer 'Firstname Lastname <email>' format.
            Required for compose/forward, auto-populated for reply.
        subject: The subject line of the email.
        body: Email body text. For reply/forward, added above quoted/forwarded content.
        cc: Carbon copy address. Prefer 'Firstname Lastname <email>' format.
        bcc: Blind carbon copy address. Prefer 'Firstname Lastname <email>' format.
        attachments: A list of local file paths to attach to the email.
        message_id: For reply/forward: the notmuch message ID of the email to reply to
            or forward. Supports abbreviated IDs.
        mode: Email mode: 'compose' (new email), 'reply', or 'forward'.
        reply_all: For reply mode: if True, reply to all recipients (To and Cc).
        thread_context: For reply mode: number of previous thread messages to include
            (0 to disable, -1 for all).

    Returns:
        OperationResult with send status and details.
    """
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
