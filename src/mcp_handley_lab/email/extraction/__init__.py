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


def _normalize_line(s: str) -> str:
    """Collapse whitespace and lowercase for content comparison."""
    return re.sub(r"\s+", " ", s.strip().lower())


def _meaningful_lines(text: str, min_len: int = 8) -> list[str]:
    """Extract normalized non-trivial lines from text."""
    return [
        _normalize_line(line)
        for line in text.splitlines()
        if line.strip() and len(line.strip()) >= min_len
    ]


def _content_coverage(source_lines: list[str], target_text: str) -> float:
    """Fraction of source lines found as substrings in target text."""
    if not source_lines:
        return 1.0
    target_norm = _normalize_line(target_text)
    found = sum(1 for line in source_lines if line in target_norm)
    return found / len(source_lines)


def _merge_markdown(plain_md: str, html_md: str) -> str:
    """Merge plain-only content into HTML markdown when they differ."""
    html_lines_set = set(_meaningful_lines(html_md))
    html_norm = _normalize_line(html_md)
    plain_only = [
        line
        for line in plain_md.splitlines()
        if line.strip()
        and len(line.strip()) >= 8
        and _normalize_line(line) not in html_lines_set
        and _normalize_line(line) not in html_norm
    ]
    if not plain_only:
        return html_md
    return html_md.rstrip() + "\n\n---\n\n" + "\n".join(plain_only) + "\n"


def extract_email_content(
    msg: EmailMessage,
    segment_quotes: bool = False,
    sender_email: str = "",
) -> ExtractionResult:
    """
    Extract email content with full preservation.

    Pipeline:
    1. MIME extraction (explicit part iteration)
    2. Convert both plain and HTML to markdown, pick richer or merge
    3. Encoding fixes (ftfy only)
    4. Conservative whitespace (preserve structure)
    5. Quote segmentation (optional, non-destructive)

    Args:
        msg: Parsed EmailMessage object
        segment_quotes: If True, populate segments field with quote detection
        sender_email: Sender email for signature detection (if segment_quotes=True)

    Returns:
        ExtractionResult with all extracted content and metadata
    """
    plain_content, html_content, parts_manifest, warnings = extract_mime_parts(msg)

    attachments = [
        f"{p.filename} ({p.content_type})"
        for p in parts_manifest
        if p.filename and p.disposition == "attachment"
    ]

    plain_md = plain_content or ""
    html_md = html_to_markdown(html_content) if html_content else ""

    if plain_md and html_md:
        plain_lines = _meaningful_lines(plain_md)
        coverage = _content_coverage(plain_lines, html_md)
        if coverage >= 0.9:
            # HTML contains (nearly) all plain content — use richer HTML
            body_markdown = html_md
            body_format = "html"
        else:
            # Genuinely different — merge plain-only content into HTML
            body_markdown = _merge_markdown(plain_md, html_md)
            body_format = "html"
    elif html_md:
        body_markdown = html_md
        body_format = "html"
    elif plain_md:
        body_markdown = plain_md
        body_format = "text"
    else:
        body_markdown = ""
        body_format = "empty"

    body_raw = html_content if body_format == "html" else (plain_content or "")
    body_html_raw = html_content or ""

    if parts_manifest:
        wanted_type = "text/html" if body_format == "html" else "text/plain"
        selected_found = False
        for p in parts_manifest:
            if (
                not selected_found
                and p.content_type == wanted_type
                and p.disposition != "attachment"
            ):
                p.is_selected_body = True
                selected_found = True
            else:
                p.is_selected_body = False

    if body_markdown:
        body_markdown = ftfy.fix_text(body_markdown)

    if body_markdown:
        body_markdown = normalize_whitespace_safe(body_markdown)

    segments: list[EmailBodySegment] = []
    if segment_quotes and body_markdown:
        segments = segment_email_content(body_markdown, sender_email)

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

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)

    text = re.sub(r"\n{3,}", "\n\n", text)

    text = text.strip() + "\n"

    return text
