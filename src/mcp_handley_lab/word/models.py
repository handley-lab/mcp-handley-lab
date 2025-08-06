"""Pydantic models for Word documents tool."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class WordComment(BaseModel):
    """Word document comment with context."""
    
    comment_id: str = Field(..., description="Unique identifier for the comment.")
    author: str = Field(..., description="Author of the comment.")
    date: str = Field(..., description="Date when the comment was created.")
    text: str = Field(..., description="Text content of the comment.")
    referenced_text: str = Field(..., description="Text that the comment references.")
    paragraph_context: str = Field(..., description="Full paragraph containing the referenced text.")
    reply_to: str | None = Field(default=None, description="ID of parent comment if this is a reply.")


class TrackedChange(BaseModel):
    """Tracked change in Word document."""
    
    change_id: str = Field(..., description="Unique identifier for the tracked change.")
    type: Literal["insertion", "deletion", "formatting"] = Field(..., description="Type of change made.")
    author: str = Field(..., description="Author who made the change.")
    date: str = Field(..., description="Date when the change was made.")
    original_text: str = Field(..., description="Original text before the change.")
    changed_text: str = Field(..., description="New text after the change.")
    accepted: bool = Field(default=False, description="Whether the change has been accepted.")


class DocumentMetadata(BaseModel):
    """Word document metadata."""
    
    filename: str = Field(..., description="Name of the document file.")
    title: str = Field(default="", description="Document title from properties.")
    author: str = Field(default="", description="Document author from properties.")
    subject: str = Field(default="", description="Document subject from properties.")
    created: str = Field(default="", description="Document creation date.")
    modified: str = Field(default="", description="Last modification date.")
    word_count: int = Field(default=0, description="Number of words in the document.")
    page_count: int = Field(default=0, description="Number of pages in the document.")
    paragraph_count: int = Field(default=0, description="Number of paragraphs in the document.")
    format_version: str = Field(default="", description="Document format version (.doc, .docx, etc.).")


class DocumentStructure(BaseModel):
    """Document structure analysis."""
    
    headings: list[dict[str, str]] = Field(default_factory=list, description="List of headings with level and text.")
    sections: list[str] = Field(default_factory=list, description="List of section titles.")
    tables: int = Field(default=0, description="Number of tables in the document.")
    images: int = Field(default=0, description="Number of images in the document.")
    hyperlinks: int = Field(default=0, description="Number of hyperlinks in the document.")
    footnotes: int = Field(default=0, description="Number of footnotes in the document.")


class CommentExtractionResult(BaseModel):
    """Result of comment extraction operation."""
    
    success: bool = Field(..., description="Whether the comment extraction succeeded.")
    document_path: str = Field(..., description="Path to the analyzed document.")
    comments: list[WordComment] = Field(..., description="List of extracted comments.")
    total_comments: int = Field(..., description="Total number of comments found.")
    unique_authors: list[str] = Field(..., description="List of unique comment authors.")
    message: str = Field(..., description="Status message about the extraction.")
    metadata: DocumentMetadata = Field(..., description="Document metadata.")


class TrackedChangesResult(BaseModel):
    """Result of tracked changes extraction."""
    
    success: bool = Field(..., description="Whether the tracked changes extraction succeeded.")
    document_path: str = Field(..., description="Path to the analyzed document.")
    changes: list[TrackedChange] = Field(..., description="List of tracked changes.")
    total_changes: int = Field(..., description="Total number of tracked changes.")
    unique_authors: list[str] = Field(..., description="List of unique change authors.")
    pending_changes: int = Field(..., description="Number of unaccepted changes.")
    message: str = Field(..., description="Status message about the extraction.")


class ConversionResult(BaseModel):
    """Result of document conversion operation."""
    
    success: bool = Field(..., description="Whether the conversion succeeded.")
    input_path: str = Field(..., description="Path to the input document.")
    output_path: str = Field(..., description="Path to the converted output document.")
    input_format: str = Field(..., description="Format of the input document.")
    output_format: str = Field(..., description="Format of the output document.")
    file_size_bytes: int = Field(..., description="Size of the output file in bytes.")
    conversion_time_ms: int = Field(default=0, description="Time taken for conversion in milliseconds.")
    message: str = Field(..., description="Status message about the conversion.")
    warnings: list[str] = Field(default_factory=list, description="Any warnings during conversion.")


class DocumentAnalysisResult(BaseModel):
    """Comprehensive document analysis result."""
    
    success: bool = Field(..., description="Whether the analysis succeeded.")
    document_path: str = Field(..., description="Path to the analyzed document.")
    metadata: DocumentMetadata = Field(..., description="Document metadata.")
    structure: DocumentStructure = Field(..., description="Document structure analysis.")
    has_comments: bool = Field(..., description="Whether the document contains comments.")
    has_tracked_changes: bool = Field(..., description="Whether the document has tracked changes.")
    message: str = Field(..., description="Status message about the analysis.")


class FormatDetectionResult(BaseModel):
    """Result of document format detection."""
    
    file_path: str = Field(..., description="Path to the analyzed file.")
    detected_format: Literal["docx", "doc", "xml", "unknown"] = Field(..., description="Detected file format.")
    is_valid: bool = Field(..., description="Whether the file is a valid Word document.")
    format_version: str = Field(default="", description="Specific format version if detectable.")
    can_process: bool = Field(..., description="Whether this tool can process the format.")
    message: str = Field(..., description="Status message about format detection.")