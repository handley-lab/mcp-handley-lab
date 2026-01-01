"""Word document manipulation.

Provides read() and edit() MCP tools for Word documents (.docx).
Pure OOXML implementation - no python-docx dependency.
"""

from mcp_handley_lab.microsoft.word.package import WordPackage

__all__ = ["WordPackage"]
