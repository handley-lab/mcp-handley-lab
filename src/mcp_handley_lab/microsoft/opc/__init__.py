"""Generic OPC (Open Packaging Conventions) layer.

Provides base classes for OOXML packages (.docx, .xlsx, .pptx).
"""

from mcp_handley_lab.microsoft.opc.constants import CT, DEFAULT_CONTENT_TYPES, RT
from mcp_handley_lab.microsoft.opc.content_types import ContentTypeMap
from mcp_handley_lab.microsoft.opc.package import OpcPackage
from mcp_handley_lab.microsoft.opc.relationships import Relationship, Relationships

__all__ = [
    "CT",
    "RT",
    "DEFAULT_CONTENT_TYPES",
    "ContentTypeMap",
    "OpcPackage",
    "Relationship",
    "Relationships",
]
