"""Word documents MCP tool for document conversion and analysis."""

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.shared.models import ServerInfo

from . import converter
from .models import (
    CommentExtractionResult,
    ConversionResult,
    DocumentAnalysisResult,
    FormatDetectionResult,
    TrackedChangesResult,
)
from .parser import WordDocumentParser
from .utils import detect_word_format

mcp = FastMCP("Word Documents Tool")


@mcp.tool(
    description="Detect Word document format and validate if processable. Supports .docx, .doc, and extracted XML structures."
)
def detect_format(
    file_path: str = Field(
        ...,
        description="Path to the Word document file to analyze.",
    ),
) -> FormatDetectionResult:
    """Detect Word document format and validate compatibility."""
    return detect_word_format(file_path)


@mcp.tool(
    description="Extract comments from Word document with referenced text context. Supports DOCX files and extracted XML structures."
)
def extract_comments(
    document_path: str = Field(
        ...,
        description="Path to the Word document (.docx) or extracted XML directory.",
    ),
) -> CommentExtractionResult:
    """Extract comments from Word document."""
    parser = WordDocumentParser(document_path)
    parser.load()

    comments = parser.extract_comments()
    unique_authors = list(dict.fromkeys(comment.author for comment in comments))
    metadata = parser.extract_metadata()

    return CommentExtractionResult(
        success=True,
        document_path=document_path,
        comments=comments,
        total_comments=len(comments),
        unique_authors=unique_authors,
        message=f"Successfully extracted {len(comments)} comments from {len(unique_authors)} authors",
        metadata=metadata,
    )


@mcp.tool(
    description="Extract tracked changes from Word document. Shows insertions, deletions, and formatting changes with author information."
)
def extract_tracked_changes(
    document_path: str = Field(
        ...,
        description="Path to the Word document (.docx) or extracted XML directory.",
    ),
) -> TrackedChangesResult:
    """Extract tracked changes from Word document."""
    parser = WordDocumentParser(document_path)
    parser.load()

    changes = parser.extract_tracked_changes()
    unique_authors = list(dict.fromkeys(change.author for change in changes))
    pending_changes = len([change for change in changes if not change.accepted])

    return TrackedChangesResult(
        success=True,
        document_path=document_path,
        changes=changes,
        total_changes=len(changes),
        unique_authors=unique_authors,
        pending_changes=pending_changes,
        message=f"Successfully extracted {len(changes)} tracked changes from {len(unique_authors)} authors ({pending_changes} pending)",
    )


@mcp.tool(
    description="Convert DOCX document to Markdown format using pandoc. Preserves formatting and structure where possible."
)
def docx_to_markdown(
    input_path: str = Field(
        ...,
        description="Path to the input DOCX file.",
    ),
    output_path: str = Field(
        default="",
        description="Path for the output Markdown file. If empty, uses input filename with .md extension.",
    ),
) -> ConversionResult:
    """Convert DOCX to Markdown using pandoc."""
    return converter.docx_to_markdown(input_path, output_path)


@mcp.tool(
    description="Convert Markdown document to DOCX format using pandoc. Creates a properly formatted Word document."
)
def markdown_to_docx(
    input_path: str = Field(
        ...,
        description="Path to the input Markdown file.",
    ),
    output_path: str = Field(
        default="",
        description="Path for the output DOCX file. If empty, uses input filename with .docx extension.",
    ),
) -> ConversionResult:
    """Convert Markdown to DOCX using pandoc."""
    return converter.markdown_to_docx(input_path, output_path)


@mcp.tool(
    description="Convert DOCX document to HTML format using pandoc. Maintains formatting and structure."
)
def docx_to_html(
    input_path: str = Field(
        ...,
        description="Path to the input DOCX file.",
    ),
    output_path: str = Field(
        default="",
        description="Path for the output HTML file. If empty, uses input filename with .html extension.",
    ),
) -> ConversionResult:
    """Convert DOCX to HTML using pandoc."""
    return converter.docx_to_html(input_path, output_path)


@mcp.tool(
    description="Convert DOCX document to plain text format using pandoc. Strips all formatting."
)
def docx_to_text(
    input_path: str = Field(
        ...,
        description="Path to the input DOCX file.",
    ),
    output_path: str = Field(
        default="",
        description="Path for the output text file. If empty, uses input filename with .txt extension.",
    ),
) -> ConversionResult:
    """Convert DOCX to plain text using pandoc."""
    return converter.docx_to_text(input_path, output_path)


@mcp.tool(
    description="Perform comprehensive analysis of Word document including metadata, structure, comments, and tracked changes."
)
def analyze_document(
    document_path: str = Field(
        ...,
        description="Path to the Word document (.docx) or extracted XML directory.",
    ),
) -> DocumentAnalysisResult:
    """Perform comprehensive Word document analysis."""
    parser = WordDocumentParser(document_path)
    parser.load()

    metadata = parser.extract_metadata()
    structure = parser.analyze_structure()
    comments = parser.extract_comments()
    tracked_changes = parser.extract_tracked_changes()

    return DocumentAnalysisResult(
        success=True,
        document_path=document_path,
        metadata=metadata,
        structure=structure,
        has_comments=len(comments) > 0,
        has_tracked_changes=len(tracked_changes) > 0,
        message=f"Successfully analyzed document: {len(comments)} comments, {len(tracked_changes)} tracked changes, {metadata.word_count} words",
    )


@mcp.tool(
    description="Get server information for the Word Documents Tool, including available functions and dependency status."
)
def server_info() -> ServerInfo:
    """Get Word Documents Tool server information without running external commands."""
    dependencies = {
        "pandoc": "required",
        "supported_inputs": ".docx, .doc, extracted XML",
        "supported_outputs": ".md, .html, .txt, .docx",
        "xml_parser": "Built-in xml.etree.ElementTree",
    }

    available_functions = [
        "detect_format",
        "extract_comments",
        "extract_tracked_changes",
        "docx_to_markdown",
        "markdown_to_docx",
        "docx_to_html",
        "docx_to_text",
        "analyze_document",
        "server_info",
        "check_dependencies",
    ]

    return ServerInfo(
        name="Word Documents Tool",
        version="1.0.0",
        status="active",
        capabilities=available_functions,
        dependencies=dependencies,
    )


@mcp.tool(
    description="Actively checks Word tool dependencies by running version commands."
)
def check_dependencies() -> str:
    """Actively tests Word tool dependencies by running external commands."""
    results = []

    try:
        import subprocess

        result = subprocess.run(
            ["pandoc", "--version"], capture_output=True, text=True, check=True
        )
        pandoc_version = (
            result.stdout.split("\n")[0].strip() if result.stdout else "Available"
        )
        results.append(f"✅ pandoc: {pandoc_version}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        results.append(f"❌ pandoc: {e}")

    return "\n".join(results)
