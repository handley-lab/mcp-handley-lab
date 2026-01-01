"""Excel-specific constants (SpreadsheetML namespaces, content types, relationship types).

Extends generic OPC constants with Excel-specific values.
"""

from mcp_handley_lab.microsoft.opc.constants import CT as OPC_CT
from mcp_handley_lab.microsoft.opc.constants import RT as OPC_RT

# SpreadsheetML namespaces
NSMAP = {
    "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "x14": "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main",
    "x14ac": "http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac",
    "x15": "http://schemas.microsoft.com/office/spreadsheetml/2010/11/main",
    "xr": "http://schemas.microsoft.com/office/spreadsheetml/2014/revision",
    "xr2": "http://schemas.microsoft.com/office/spreadsheetml/2015/revision2",
    "xr3": "http://schemas.microsoft.com/office/spreadsheetml/2016/revision3",
    "xr6": "http://schemas.microsoft.com/office/spreadsheetml/2014/revision6",
    "xr10": "http://schemas.microsoft.com/office/spreadsheetml/2014/revision10",
}


def qn(tag: str) -> str:
    """Convert namespace-prefixed tag to Clark notation.

    Example: qn("x:worksheet") -> "{http://schemas.openxmlformats.org/.../main}worksheet"
    """
    prefix, local = tag.split(":", 1)
    return f"{{{NSMAP[prefix]}}}{local}"


class CT(OPC_CT):
    """Content type constants for SpreadsheetML."""

    # Main workbook parts
    SML_SHEET_MAIN = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
    )
    SML_SHEET_MAIN_MACRO = "application/vnd.ms-excel.sheet.macroEnabled.main+xml"
    SML_TEMPLATE_MAIN = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.template.main+xml"
    )

    # Sheet parts
    SML_WORKSHEET = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
    )
    SML_CHARTSHEET = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.chartsheet+xml"
    )
    SML_DIALOGSHEET = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.dialogsheet+xml"
    )
    SML_MACROSHEET = "application/vnd.ms-excel.macrosheet+xml"

    # Shared parts
    SML_SHARED_STRINGS = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"
    )
    SML_STYLES = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"
    )
    SML_THEME = "application/vnd.openxmlformats-officedocument.theme+xml"

    # Table/pivot parts
    SML_TABLE = "application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"
    SML_PIVOT_TABLE = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml"
    )
    SML_PIVOT_CACHE_DEF = "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheDefinition+xml"
    SML_PIVOT_CACHE_REC = "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheRecords+xml"

    # Comments/drawings
    SML_COMMENTS = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.comments+xml"
    )
    SML_CALC_CHAIN = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.calcChain+xml"
    )

    # External links
    SML_EXTERNAL_LINK = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.externalLink+xml"
    )
    SML_CONNECTIONS = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.connections+xml"
    )


class RT(OPC_RT):
    """Relationship type constants for SpreadsheetML."""

    # Workbook relationships
    WORKSHEET = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    )
    CHARTSHEET = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chartsheet"
    )
    DIALOGSHEET = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/dialogsheet"
    MACROSHEET = "http://schemas.microsoft.com/office/2006/relationships/xlMacrosheet"

    # Shared resources
    SHARED_STRINGS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings"
    STYLES = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
    )
    THEME = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"

    # Table/pivot
    TABLE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/table"
    PIVOT_TABLE = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotTable"
    )
    PIVOT_CACHE_DEF = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheDefinition"
    PIVOT_CACHE_REC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheRecords"

    # Comments/drawings
    COMMENTS = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
    )
    CALC_CHAIN = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/calcChain"
    )
    VML_DRAWING = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing"
    )
    DRAWING = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
    )

    # External links
    EXTERNAL_LINK = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLink"
    EXTERNAL_LINK_PATH = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLinkPath"

    # Printer settings
    PRINTER_SETTINGS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/printerSettings"
