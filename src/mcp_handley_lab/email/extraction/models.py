"""Data models for email extraction."""

from typing import Literal

from pydantic import BaseModel, Field


class EmailPartInfo(BaseModel):
    """Metadata about a MIME part."""

    content_type: str = Field(..., description="MIME content type (e.g., text/plain)")
    charset: str = Field(default="utf-8", description="Character encoding")
    transfer_encoding: str = Field(
        default="", description="Transfer encoding (base64, quoted-printable, etc.)"
    )
    disposition: str = Field(
        default="", description="Content disposition (inline, attachment, or empty)"
    )
    filename: str = Field(default="", description="Filename if attachment")
    size_bytes: int = Field(default=0, description="Size of decoded content in bytes")
    part_index: int = Field(default=0, description="Position in MIME tree walk")
    is_selected_body: bool = Field(
        default=False, description="True if this part was chosen as body"
    )


class EmailBodySegment(BaseModel):
    """A segment of email body content from quote detection."""

    segment_type: Literal["reply", "quoted", "signature", "disclaimer"] = Field(
        ..., description="Type of content segment"
    )
    content: str = Field(..., description="The text content of this segment")


class ExtractionResult(BaseModel):
    """Internal result from email extraction (before mode projection)."""

    # Body content
    body_markdown: str = Field(default="", description="Processed body as markdown")
    body_raw: str = Field(default="", description="Raw decoded text before processing")
    body_html_raw: str = Field(default="", description="Raw HTML if source was HTML")
    body_format: str = Field(
        default="text", description="Source format: 'text', 'html', or 'empty'"
    )

    # MIME structure
    selected_part: EmailPartInfo | None = Field(
        default=None, description="The MIME part selected as body"
    )
    parts_manifest: list[EmailPartInfo] = Field(
        default_factory=list, description="All MIME parts in the message"
    )
    attachments: list[str] = Field(
        default_factory=list, description="Attachment filenames"
    )

    # Quote detection
    segments: list[EmailBodySegment] = Field(
        default_factory=list, description="Segmented content from quote detection"
    )

    # Metadata
    extraction_warnings: list[str] = Field(
        default_factory=list, description="Non-fatal issues during extraction"
    )
