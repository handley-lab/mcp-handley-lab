"""Word-specific namespaces, content types, and relationship types."""

from mcp_handley_lab.microsoft.opc.constants import CT as OPC_CT
from mcp_handley_lab.microsoft.opc.constants import RT as OPC_RT

# Word namespace mapping
NSMAP = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "b": "http://schemas.openxmlformats.org/officeDocument/2006/bibliography",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "ds": "http://schemas.openxmlformats.org/officeDocument/2006/customXml",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "mo": "http://schemas.microsoft.com/office/mac/office/2008/main",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "o": "urn:schemas-microsoft-com:office:office",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "v": "urn:schemas-microsoft-com:vml",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w10": "urn:schemas-microsoft-com:office:word",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "wne": "http://schemas.microsoft.com/office/word/2006/wordml",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "wp14": "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing",
    "wpc": "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    "wpg": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "wpi": "http://schemas.microsoft.com/office/word/2010/wordprocessingInk",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "xml": "http://www.w3.org/XML/1998/namespace",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

# Reverse mapping for prefix lookup
PFXMAP = {v: k for k, v in NSMAP.items()}


def qn(tag: str) -> str:
    """Convert namespace-prefixed tag to Clark notation.

    Example: qn("w:p") -> "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
    """
    prefix, local = tag.split(":", 1)
    return f"{{{NSMAP[prefix]}}}{local}"


class CT(OPC_CT):
    """Content type constants - Word-specific."""

    # Word-specific
    WML_DOCUMENT_MAIN = (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document.main+xml"
    )
    WML_COMMENTS = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
    )
    WML_COMMENTS_EXTENDED = (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.commentsExtended+xml"
    )
    WML_ENDNOTES = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"
    )
    WML_FOOTNOTES = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"
    )
    WML_HEADER = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"
    )
    WML_FOOTER = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"
    )
    WML_NUMBERING = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"
    )
    WML_SETTINGS = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"
    )
    WML_STYLES = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"
    )
    WML_FONT_TABLE = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"
    )
    WML_WEB_SETTINGS = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.webSettings+xml"
    )

    # CustomXml (for bibliography sources, etc.)
    CUSTOM_XML = "application/vnd.openxmlformats-officedocument.customXml+xml"
    CUSTOM_XML_PROPS = (
        "application/vnd.openxmlformats-officedocument.customXmlProperties+xml"
    )


class RT(OPC_RT):
    """Relationship type constants - Word-specific."""

    # Word-specific
    COMMENTS = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
    )
    COMMENTS_EXTENDED = (
        "http://schemas.microsoft.com/office/2011/relationships/commentsExtended"
    )
    ENDNOTES = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes"
    )
    FOOTNOTES = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes"
    )
    HEADER = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header"
    )
    FOOTER = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer"
    )
    HYPERLINK = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
    )
    NUMBERING = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering"
    )
    SETTINGS = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings"
    )
    STYLES = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
    )
    FONT_TABLE = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable"
    )
    WEB_SETTINGS = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
        "webSettings"
    )

    # CustomXml (for bibliography sources, etc.)
    CUSTOM_XML = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXml"
    )
    CUSTOM_XML_PROPS = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
        "customXmlProps"
    )
