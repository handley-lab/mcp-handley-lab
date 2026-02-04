"""Visio Drawing ML constants: namespaces, content types, relationship types."""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.opc.constants import CT as OPC_CT
from mcp_handley_lab.microsoft.opc.constants import RT as OPC_RT

__all__ = ["NSMAP", "NS_REL", "NS_VISIO_2012", "qn", "find_v", "findall_v", "CT", "RT"]

# Visio namespace variants — real files may use either
NS_VISIO_2012 = "http://schemas.microsoft.com/office/visio/2012/main"
NS_VISIO_2011 = "http://schemas.microsoft.com/office/visio/2011/1/core"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# Superset NSMAP: both variants always available
NSMAP = {
    "v": NS_VISIO_2012,
    "v11": NS_VISIO_2011,
    "r": NS_REL,
}


def qn(tag: str) -> str:
    """Convert prefixed tag to Clark notation.

    Example: qn("v:Shape") -> "{http://schemas.microsoft.com/office/visio/2012/main}Shape"
    """
    if ":" not in tag:
        return tag
    prefix, local = tag.split(":", 1)
    ns = NSMAP.get(prefix)
    if ns is None:
        raise ValueError(f"Unknown namespace prefix: {prefix}")
    return f"{{{ns}}}{local}"


def find_v(parent: etree._Element, local_name: str) -> etree._Element | None:
    """Find child element trying both v12 and v11 namespaces."""
    el = parent.find(f"{{{NS_VISIO_2012}}}{local_name}")
    if el is None:
        el = parent.find(f"{{{NS_VISIO_2011}}}{local_name}")
    return el


def findall_v(parent: etree._Element, local_name: str) -> list[etree._Element]:
    """Find all child elements in both v12 and v11 namespaces."""
    els_2012 = parent.findall(f"{{{NS_VISIO_2012}}}{local_name}")
    els_2011 = parent.findall(f"{{{NS_VISIO_2011}}}{local_name}")
    return els_2012 + els_2011


class CT(OPC_CT):
    """Content types for Visio Drawing ML."""

    VSD_DOCUMENT = "application/vnd.ms-visio.drawing.main+xml"
    VSD_PAGES = "application/vnd.ms-visio.pages+xml"
    VSD_PAGE = "application/vnd.ms-visio.page+xml"
    VSD_MASTERS = "application/vnd.ms-visio.masters+xml"
    VSD_MASTER = "application/vnd.ms-visio.master+xml"
    VSD_COMMENTS = "application/vnd.ms-visio.comments+xml"
    VSD_WINDOWS = "application/vnd.ms-visio.windows+xml"
    # Macro-enabled variant
    VSDM_DOCUMENT = "application/vnd.ms-visio.drawing.macroEnabled.main+xml"


class RT(OPC_RT):
    """Relationship types for Visio (schemas.microsoft.com/visio/2010/relationships/)."""

    DOCUMENT = "http://schemas.microsoft.com/visio/2010/relationships/document"
    PAGES = "http://schemas.microsoft.com/visio/2010/relationships/pages"
    PAGE = "http://schemas.microsoft.com/visio/2010/relationships/page"
    MASTERS = "http://schemas.microsoft.com/visio/2010/relationships/masters"
    MASTER = "http://schemas.microsoft.com/visio/2010/relationships/master"
    COMMENTS = "http://schemas.microsoft.com/visio/2010/relationships/comments"
    WINDOWS = "http://schemas.microsoft.com/visio/2010/relationships/windows"
