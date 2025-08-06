"""Utility functions for Word documents processing."""

import mimetypes
import zipfile
from pathlib import Path

from .models import FormatDetectionResult


def detect_word_format(file_path: str) -> FormatDetectionResult:
    """Detect Word document format and validate if processable."""
    file_path_obj = Path(file_path)
    
    if not file_path_obj.exists():
        return FormatDetectionResult(
            file_path=file_path,
            detected_format="unknown",
            is_valid=False,
            can_process=False,
            message=f"File not found: {file_path}"
        )
    
    # Check file extension first
    suffix = file_path_obj.suffix.lower()
    
    # Check MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    
    # Detect DOCX format (ZIP-based OpenXML)
    if suffix == '.docx' or mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Check for required DOCX structure
                required_files = ['[Content_Types].xml', 'word/document.xml']
                if all(f in zip_file.namelist() for f in required_files):
                    return FormatDetectionResult(
                        file_path=file_path,
                        detected_format="docx",
                        is_valid=True,
                        format_version="OpenXML",
                        can_process=True,
                        message="Valid DOCX document detected"
                    )
        except (zipfile.BadZipFile, FileNotFoundError):
            pass
    
    # Detect DOC format (older binary format)
    if suffix == '.doc' or mime_type == 'application/msword':
        try:
            # Check for OLE header signature
            with open(file_path, 'rb') as f:
                header = f.read(8)
                if header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
                    return FormatDetectionResult(
                        file_path=file_path,
                        detected_format="doc",
                        is_valid=True,
                        format_version="Binary DOC",
                        can_process=True,
                        message="Valid DOC document detected"
                    )
        except (IOError, OSError):
            pass
    
    # Check if it's a directory with extracted DOCX XML files
    if file_path_obj.is_dir():
        word_dir = file_path_obj / "word"
        if (word_dir / "document.xml").exists() and (file_path_obj / "[Content_Types].xml").exists():
            return FormatDetectionResult(
                file_path=file_path,
                detected_format="xml",
                is_valid=True,
                format_version="Extracted DOCX XML",
                can_process=True,
                message="Valid extracted DOCX XML structure detected"
            )
    
    # Check if it's a standalone document.xml file
    if file_path_obj.name == "document.xml" and file_path_obj.exists():
        return FormatDetectionResult(
            file_path=file_path,
            detected_format="xml",
            is_valid=True,
            format_version="DOCX document.xml",
            can_process=True,
            message="Valid DOCX document.xml file detected"
        )
    
    return FormatDetectionResult(
        file_path=file_path,
        detected_format="unknown",
        is_valid=False,
        can_process=False,
        message="Unrecognized or invalid Word document format"
    )


def is_word_document(file_path: str) -> bool:
    """Quick check if file is a processable Word document."""
    result = detect_word_format(file_path)
    return result.can_process


def get_document_extension(file_path: str) -> str:
    """Get the appropriate file extension for a document path."""
    return Path(file_path).suffix.lower()