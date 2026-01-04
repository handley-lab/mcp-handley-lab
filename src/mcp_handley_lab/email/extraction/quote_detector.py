"""Quote and signature detection using talon.

Segments email content into reply, quoted, and signature parts.
NEVER discards content - just labels it.
"""

import contextlib

from mcp_handley_lab.email.extraction.models import EmailBodySegment

# Try to import talon, gracefully degrade if not available
try:
    from talon import quotations
    from talon import signature as talon_signature

    TALON_AVAILABLE = True
except ImportError:
    TALON_AVAILABLE = False


def segment_email_content(
    text: str,
    sender_email: str = "",
) -> list[EmailBodySegment]:
    """
    Segment email into reply, quoted, and signature parts.

    Uses talon library for intelligent detection.
    SEGMENTS rather than STRIPS - caller decides what to display.

    Args:
        text: The email body text
        sender_email: Optional sender email for signature detection

    Returns:
        List of EmailBodySegment with segment_type indicating each part.
        If talon unavailable, returns single "reply" segment with full content.
    """
    if not text or not text.strip():
        return []

    if not TALON_AVAILABLE:
        # Graceful degradation: return everything as reply
        return [EmailBodySegment(segment_type="reply", content=text)]

    segments: list[EmailBodySegment] = []

    # Extract reply vs quoted
    try:
        reply_text, quoted_text = quotations.extract_from(text, "text/plain")
    except Exception:
        # If extraction fails, treat as single reply
        reply_text = text
        quoted_text = None

    # Detect signature in reply
    main_text = reply_text or text
    signature_text = ""

    if sender_email:
        with contextlib.suppress(Exception):
            main_text, signature_text = talon_signature.extract(
                reply_text or text, sender=sender_email
            )

    # Build segments
    if main_text and main_text.strip():
        segments.append(EmailBodySegment(segment_type="reply", content=main_text))

    if quoted_text and quoted_text.strip():
        segments.append(EmailBodySegment(segment_type="quoted", content=quoted_text))

    if signature_text and signature_text.strip():
        segments.append(
            EmailBodySegment(segment_type="signature", content=signature_text)
        )

    # If no segments created, return full content as reply
    if not segments:
        segments.append(EmailBodySegment(segment_type="reply", content=text))

    return segments
