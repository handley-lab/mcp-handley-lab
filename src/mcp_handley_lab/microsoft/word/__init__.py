"""Word document manipulation.

Provides read(), render(), edit(), and create() functions for Word documents (.docx).
Pure OOXML implementation - no python-docx dependency.

Usage:
    from mcp_handley_lab.microsoft.word import read, edit, create, render

    # Read document outline
    result = read(file_path="doc.docx", scope="outline")

    # Edit document
    result = edit(
        file_path="doc.docx",
        ops='[{"op": "replace", "target_id": "paragraph_abc_0", "content_data": "New text"}]'
    )

    # Create new document
    result = create(file_path="new.docx", content_type="heading", content_data="Title", heading_level=1)

    # Render document to images
    images = render(file_path="doc.docx", pages=[1, 2], output="png")
"""

from mcp_handley_lab.microsoft.word.package import WordPackage
from mcp_handley_lab.microsoft.word.shared import create, edit, read, render

__all__ = ["WordPackage", "read", "edit", "create", "render"]
