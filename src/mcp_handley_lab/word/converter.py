"""Document conversion functions for Word documents."""

import subprocess
import tempfile
import time
from pathlib import Path

from .models import ConversionResult
from .utils import detect_word_format


class WordConverter:
    """Handles conversion between Word documents and other formats."""
    
    @staticmethod
    def docx_to_markdown(input_path: str, output_path: str = "") -> ConversionResult:
        """Convert DOCX to Markdown using pandoc."""
        input_path_obj = Path(input_path)
        
        # Validate input
        format_result = detect_word_format(input_path)
        if not format_result.can_process:
            return ConversionResult(
                success=False,
                input_path=input_path,
                output_path="",
                input_format=format_result.detected_format,
                output_format="markdown",
                file_size_bytes=0,
                message=f"Cannot process input file: {format_result.message}"
            )
        
        # Determine output path
        if not output_path:
            output_path = str(input_path_obj.with_suffix('.md'))
        
        output_path_obj = Path(output_path)
        
        try:
            start_time = time.time()
            
            # Use pandoc for conversion (per CLAUDE.md quick reference)
            cmd = [
                "pandoc",
                str(input_path_obj),
                "-t", "markdown",
                "-o", str(output_path_obj)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            end_time = time.time()
            conversion_time = int((end_time - start_time) * 1000)
            
            # Get output file size
            file_size = output_path_obj.stat().st_size if output_path_obj.exists() else 0
            
            return ConversionResult(
                success=True,
                input_path=input_path,
                output_path=str(output_path_obj),
                input_format=format_result.detected_format,
                output_format="markdown",
                file_size_bytes=file_size,
                conversion_time_ms=conversion_time,
                message=f"Successfully converted DOCX to Markdown"
            )
            
        except subprocess.CalledProcessError as e:
            return ConversionResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                input_format=format_result.detected_format,
                output_format="markdown",
                file_size_bytes=0,
                message=f"Pandoc conversion failed: {e.stderr}"
            )
        except FileNotFoundError:
            return ConversionResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                input_format=format_result.detected_format,
                output_format="markdown",
                file_size_bytes=0,
                message="Pandoc not found. Please install pandoc to use conversion features."
            )
    
    @staticmethod
    def markdown_to_docx(input_path: str, output_path: str = "") -> ConversionResult:
        """Convert Markdown to DOCX using pandoc."""
        input_path_obj = Path(input_path)
        
        if not input_path_obj.exists():
            return ConversionResult(
                success=False,
                input_path=input_path,
                output_path="",
                input_format="markdown",
                output_format="docx",
                file_size_bytes=0,
                message=f"Input file not found: {input_path}"
            )
        
        # Determine output path
        if not output_path:
            output_path = str(input_path_obj.with_suffix('.docx'))
        
        output_path_obj = Path(output_path)
        
        try:
            start_time = time.time()
            
            # Use pandoc for conversion (reverse of docx_to_markdown)
            cmd = [
                "pandoc",
                str(input_path_obj),
                "-f", "markdown",
                "-t", "docx",
                "-o", str(output_path_obj)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            end_time = time.time()
            conversion_time = int((end_time - start_time) * 1000)
            
            # Get output file size
            file_size = output_path_obj.stat().st_size if output_path_obj.exists() else 0
            
            return ConversionResult(
                success=True,
                input_path=input_path,
                output_path=str(output_path_obj),
                input_format="markdown",
                output_format="docx",
                file_size_bytes=file_size,
                conversion_time_ms=conversion_time,
                message="Successfully converted Markdown to DOCX"
            )
            
        except subprocess.CalledProcessError as e:
            return ConversionResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                input_format="markdown",
                output_format="docx",
                file_size_bytes=0,
                message=f"Pandoc conversion failed: {e.stderr}"
            )
        except FileNotFoundError:
            return ConversionResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                input_format="markdown",
                output_format="docx",
                file_size_bytes=0,
                message="Pandoc not found. Please install pandoc to use conversion features."
            )
    
    @staticmethod
    def docx_to_html(input_path: str, output_path: str = "") -> ConversionResult:
        """Convert DOCX to HTML using pandoc."""
        input_path_obj = Path(input_path)
        
        # Validate input
        format_result = detect_word_format(input_path)
        if not format_result.can_process:
            return ConversionResult(
                success=False,
                input_path=input_path,
                output_path="",
                input_format=format_result.detected_format,
                output_format="html",
                file_size_bytes=0,
                message=f"Cannot process input file: {format_result.message}"
            )
        
        # Determine output path
        if not output_path:
            output_path = str(input_path_obj.with_suffix('.html'))
        
        output_path_obj = Path(output_path)
        
        try:
            start_time = time.time()
            
            # Use pandoc for conversion
            cmd = [
                "pandoc",
                str(input_path_obj),
                "-t", "html",
                "-o", str(output_path_obj)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            end_time = time.time()
            conversion_time = int((end_time - start_time) * 1000)
            
            # Get output file size
            file_size = output_path_obj.stat().st_size if output_path_obj.exists() else 0
            
            return ConversionResult(
                success=True,
                input_path=input_path,
                output_path=str(output_path_obj),
                input_format=format_result.detected_format,
                output_format="html",
                file_size_bytes=file_size,
                conversion_time_ms=conversion_time,
                message="Successfully converted DOCX to HTML"
            )
            
        except subprocess.CalledProcessError as e:
            return ConversionResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                input_format=format_result.detected_format,
                output_format="html",
                file_size_bytes=0,
                message=f"Pandoc conversion failed: {e.stderr}"
            )
        except FileNotFoundError:
            return ConversionResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                input_format=format_result.detected_format,
                output_format="html",
                file_size_bytes=0,
                message="Pandoc not found. Please install pandoc to use conversion features."
            )
    
    @staticmethod
    def docx_to_text(input_path: str, output_path: str = "") -> ConversionResult:
        """Convert DOCX to plain text using pandoc."""
        input_path_obj = Path(input_path)
        
        # Validate input
        format_result = detect_word_format(input_path)
        if not format_result.can_process:
            return ConversionResult(
                success=False,
                input_path=input_path,
                output_path="",
                input_format=format_result.detected_format,
                output_format="text",
                file_size_bytes=0,
                message=f"Cannot process input file: {format_result.message}"
            )
        
        # Determine output path
        if not output_path:
            output_path = str(input_path_obj.with_suffix('.txt'))
        
        output_path_obj = Path(output_path)
        
        try:
            start_time = time.time()
            
            # Use pandoc for conversion
            cmd = [
                "pandoc",
                str(input_path_obj),
                "-t", "plain",
                "-o", str(output_path_obj)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            end_time = time.time()
            conversion_time = int((end_time - start_time) * 1000)
            
            # Get output file size
            file_size = output_path_obj.stat().st_size if output_path_obj.exists() else 0
            
            return ConversionResult(
                success=True,
                input_path=input_path,
                output_path=str(output_path_obj),
                input_format=format_result.detected_format,
                output_format="text",
                file_size_bytes=file_size,
                conversion_time_ms=conversion_time,
                message="Successfully converted DOCX to plain text"
            )
            
        except subprocess.CalledProcessError as e:
            return ConversionResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                input_format=format_result.detected_format,
                output_format="text",
                file_size_bytes=0,
                message=f"Pandoc conversion failed: {e.stderr}"
            )
        except FileNotFoundError:
            return ConversionResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                input_format=format_result.detected_format,
                output_format="text",
                file_size_bytes=0,
                message="Pandoc not found. Please install pandoc to use conversion features."
            )