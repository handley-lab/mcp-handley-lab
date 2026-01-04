"""Email content extraction module.

Provides robust email body extraction that never silently loses content.
"""

import re
from email.message import EmailMessage

import ftfy

from mcp_handley_lab.email.extraction.html_converter import html_to_markdown
from mcp_handley_lab.email.extraction.mime_extractor import extract_mime_parts
from mcp_handley_lab.email.extraction.models import (
    EmailBodySegment,
    EmailPartInfo,
    ExtractionResult,
)
from mcp_handley_lab.email.extraction.quote_detector import segment_email_content

__all__ = [
    "extract_email_content",
    "ExtractionResult",
    "EmailPartInfo",
    "EmailBodySegment",
]


def extract_email_content(
    msg: EmailMessage,
    segment_quotes: bool = False,
    sender_email: str = "",
) -> ExtractionResult:
    """
    Extract email content with full preservation.

    Pipeline:
    1. MIME extraction (explicit part iteration)
    2. Raw preservation (store original)
    3. HTML→Markdown (link-preserving)
    4. Quote segmentation (optional, non-destructive)
    5. Encoding fixes (ftfy only)
    6. Conservative whitespace (preserve structure)

    Args:
        msg: Parsed EmailMessage object
        segment_quotes: If True, populate segments field with quote detection
        sender_email: Sender email for signature detection (if segment_quotes=True)

    Returns:
        ExtractionResult with all extracted content and metadata
    """
    # Step 1: MIME extraction
    plain_content, html_content, parts_manifest, warnings = extract_mime_parts(msg)

    # Collect attachments from manifest (consistent format: "filename (content_type)")
    attachments = [
        f"{p.filename} ({p.content_type})"
        for p in parts_manifest
        if p.filename and p.disposition == "attachment"
    ]

    # Determine body format and raw content
    # body_raw = decoded source of selected body part (plain or HTML)
    # body_html_raw = original HTML (always present if HTML was available)
    if plain_content:
        body_format = "text"
        body_raw = plain_content
        body_html_raw = html_content  # Preserve HTML even if we have plain
    elif html_content:
        body_format = "html"
        body_raw = html_content  # Raw is the HTML source for HTML-only emails
        body_html_raw = html_content
    else:
        body_format = "empty"
        body_raw = ""
        body_html_raw = ""

    # Step 2: Convert to markdown
    if body_format == "html":
        body_markdown = html_to_markdown(html_content)
    else:
        body_markdown = plain_content

    # Step 3: Encoding fixes (ftfy)
    if body_markdown:
        body_markdown = ftfy.fix_text(body_markdown)

    # Step 4: Conservative whitespace normalization
    if body_markdown:
        body_markdown = normalize_whitespace_safe(body_markdown)

    # Step 5: Quote segmentation (optional)
    segments: list[EmailBodySegment] = []
    if segment_quotes and body_markdown:
        segments = segment_email_content(body_markdown, sender_email)

    # Find selected part
    selected_part = next(
        (p for p in parts_manifest if p.is_selected_body),
        None,
    )

    return ExtractionResult(
        body_markdown=body_markdown,
        body_raw=body_raw,
        body_html_raw=body_html_raw,
        body_format=body_format,
        selected_part=selected_part,
        parts_manifest=parts_manifest,
        attachments=attachments,
        segments=segments,
        extraction_warnings=warnings,
    )


def normalize_whitespace_safe(text: str) -> str:
    """
    Conservative whitespace normalization that preserves structure.

    DO:
    - Collapse 3+ consecutive blank lines to 2 blank lines
    - Remove trailing whitespace from lines
    - Normalize line endings (CRLF → LF)
    - Ensure single trailing newline

    DO NOT:
    - Collapse horizontal whitespace (breaks tables/code)
    - Remove leading indentation (breaks structure)
    - Reflow or wrap text (alters formatting)
    """
    if not text:
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove trailing whitespace from each line (but preserve leading)
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)

    # Collapse 3+ consecutive blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Ensure single trailing newline
    text = text.strip() + "\n"

    return text
