"""Microsoft Excel (.xlsx) support via SpreadsheetML."""

from mcp_handley_lab.microsoft.excel.package import ExcelPackage
from mcp_handley_lab.microsoft.excel.shared import edit, read

__all__ = ["ExcelPackage", "read", "edit"]
