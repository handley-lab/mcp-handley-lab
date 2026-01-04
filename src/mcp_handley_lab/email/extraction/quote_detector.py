"""Quote and signature detection using simple heuristics.

Segments email content into reply, quoted, and signature parts.
NEVER discards content - just labels it.
"""

import re

from mcp_handley_lab.email.extraction.models import EmailBodySegment

# Pattern for quote attribution lines like "On Mon, Jan 1, 2025 at 10:00 AM John wrote:"
ATTRIBUTION_PATTERN = re.compile(
    r"^On .+wrote:?\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# Pattern for signature delimiters
SIGNATURE_PATTERN = re.compile(
    r"^--\s*$",  # Standard signature delimiter: "-- " or "--"
    re.MULTILINE,
)


def segment_email_content(
    text: str,
    sender_email: str = "",
) -> list[EmailBodySegment]:
    """
    Segment email into reply, quoted, and signature parts.

    Uses simple heuristics:
    - Lines starting with > are quoted
    - "On ... wrote:" introduces quoted section
    - "-- " starts signature

    SEGMENTS rather than STRIPS - caller decides what to display.

    Args:
        text: The email body text
        sender_email: Optional sender email (unused, kept for API compatibility)

    Returns:
        List of EmailBodySegment with segment_type indicating each part.
    """
    if not text or not text.strip():
        return []

    segments: list[EmailBodySegment] = []

    # Split off signature first (standard "-- " delimiter)
    signature_match = SIGNATURE_PATTERN.search(text)
    main_text = text
    signature_text = ""

    if signature_match:
        main_text = text[: signature_match.start()]
        signature_text = text[signature_match.end() :].strip()

    # Find quoted section (starts with attribution or > lines)
    reply_text = main_text
    quoted_text = ""

    attribution_match = ATTRIBUTION_PATTERN.search(main_text)
    if attribution_match:
        reply_text = main_text[: attribution_match.start()].strip()
        quoted_text = main_text[attribution_match.start() :].strip()

    # Build segments
    if reply_text:
        segments.append(EmailBodySegment(segment_type="reply", content=reply_text))

    if quoted_text:
        segments.append(EmailBodySegment(segment_type="quoted", content=quoted_text))

    if signature_text:
        segments.append(
            EmailBodySegment(segment_type="signature", content=signature_text)
        )

    # If no segments created, return full content as reply
    if not segments:
        segments.append(EmailBodySegment(segment_type="reply", content=text))

    return segments
