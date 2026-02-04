"""Render Visio diagrams to PNG images or PDF using libreoffice.

Thin wrappers around the common render utilities,
with Visio-specific terminology (pages vs slides).
"""

from mcp_handley_lab.microsoft.common.render import (
    convert_to_pdf,
    render_pages_to_images,
)


def render_to_pdf(file_path: str) -> bytes:
    """Render a Visio diagram to PDF.

    Args:
        file_path: Path to the Visio file (.vsdx, .vsdm)

    Returns:
        PDF file contents as bytes
    """
    return convert_to_pdf(file_path)


def render_to_images(
    file_path: str,
    pages: list[int],
    dpi: int = 150,
) -> list[tuple[int, bytes]]:
    """Render Visio pages to PNG images.

    Args:
        file_path: Path to the Visio file (.vsdx, .vsdm)
        pages: List of 1-based page numbers to render
        dpi: Resolution in dots per inch (72-300, default: 150)

    Returns:
        List of (page_number, png_bytes) tuples
    """
    return render_pages_to_images(file_path, pages, dpi=dpi)
