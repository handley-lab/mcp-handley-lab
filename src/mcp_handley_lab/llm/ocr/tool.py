"""OCR Tool for document text extraction via MCP.

Provides high-accuracy OCR using Mistral's OCR model.
Supports PDFs, images, PPTX, and DOCX files.
"""

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("OCR Tool")


@mcp.tool(
    description="Extract text from documents using Mistral OCR. "
    "Supports PDFs, images (PNG, JPG), PPTX, and DOCX. "
    "Returns: {status, pages, output_file?, message}. Full OCR JSON saved to output_file if provided."
)
def process(
    document_path: str = Field(
        ...,
        description="Path to document file or URL. Supports PDF, images, PPTX, DOCX.",
    ),
    output_file: str = Field(
        default="",
        description="File path to save full OCR results as JSON. Empty means no file output.",
    ),
    include_images: bool = Field(
        default=False,
        description="Include base64-encoded images with bounding boxes in output.",
    ),
) -> dict[str, Any]:
    """Process document with Mistral OCR for text extraction."""
    from mcp_handley_lab.llm.registry import get_adapter

    adapter = get_adapter("mistral", "ocr")
    result = adapter(document_path, include_images)

    pages = result.get("pages", [])
    response: dict[str, Any] = {
        "status": "success",
        "pages": len(pages),
        "message": f"OCR complete. {len(pages)} page(s) extracted.",
    }

    if output_file:
        Path(output_file).write_text(json.dumps(result, indent=2))
        response["output_file"] = output_file
        response["message"] += f" Full results saved to {output_file}"

    return response
