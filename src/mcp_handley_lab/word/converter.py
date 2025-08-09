"""Document conversion functions for Word documents."""

import subprocess
import time
from pathlib import Path
from typing import Literal

from .models import ConversionResult
from .utils import detect_word_format


def _run_pandoc(
    input_path: Path,
    output_path: Path,
    from_format: str,
    to_format: Literal["markdown", "docx", "html", "plain"],
) -> ConversionResult:
    """Run pandoc conversion and return result."""
    cmd = [
        "pandoc",
        str(input_path),
        "-f",
        from_format,
        "-t",
        to_format,
        "-o",
        str(output_path),
    ]

    try:
        start_time = time.time()
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        end_time = time.time()

        return ConversionResult(
            success=True,
            input_path=str(input_path),
            output_path=str(output_path),
            input_format=from_format,
            output_format=to_format if to_format != "plain" else "text",
            file_size_bytes=output_path.stat().st_size,
            conversion_time_ms=int((end_time - start_time) * 1000),
            message=f"Successfully converted {from_format} to {to_format}",
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "Pandoc not found. Please install pandoc to use conversion features."
        ) from e
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Pandoc conversion failed: {e.stderr}") from e


def docx_to_markdown(input_path: str, output_path: str = "") -> ConversionResult:
    """Convert DOCX to Markdown using pandoc."""
    input_p = Path(input_path)
    if not detect_word_format(input_path).can_process:
        raise ValueError(f"Input file is not a processable Word document: {input_path}")
    output_p = Path(output_path) if output_path else input_p.with_suffix(".md")
    return _run_pandoc(input_p, output_p, "docx", "markdown")


def markdown_to_docx(input_path: str, output_path: str = "") -> ConversionResult:
    """Convert Markdown to DOCX using pandoc."""
    input_p = Path(input_path)
    if not input_p.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    output_p = Path(output_path) if output_path else input_p.with_suffix(".docx")
    return _run_pandoc(input_p, output_p, "markdown", "docx")


def docx_to_html(input_path: str, output_path: str = "") -> ConversionResult:
    """Convert DOCX to HTML using pandoc."""
    input_p = Path(input_path)
    if not detect_word_format(input_path).can_process:
        raise ValueError(f"Input file is not a processable Word document: {input_path}")
    output_p = Path(output_path) if output_path else input_p.with_suffix(".html")
    return _run_pandoc(input_p, output_p, "docx", "html")


def docx_to_text(input_path: str, output_path: str = "") -> ConversionResult:
    """Convert DOCX to plain text using pandoc."""
    input_p = Path(input_path)
    if not detect_word_format(input_path).can_process:
        raise ValueError(f"Input file is not a processable Word document: {input_path}")
    output_p = Path(output_path) if output_path else input_p.with_suffix(".txt")
    return _run_pandoc(input_p, output_p, "docx", "plain")
