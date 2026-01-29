"""PowerPoint (PresentationML) constants: namespaces, content types, relationship types."""

from mcp_handley_lab.microsoft.common.constants import EMU_PER_INCH
from mcp_handley_lab.microsoft.opc.constants import CT as OPC_CT
from mcp_handley_lab.microsoft.opc.constants import RT as OPC_RT

# Re-export EMU_PER_INCH for backwards compatibility
__all__ = ["EMU_PER_INCH", "NSMAP", "qn", "CT", "RT"]

# PresentationML namespace map
NSMAP = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "p14": "http://schemas.microsoft.com/office/powerpoint/2010/main",
    "p15": "http://schemas.microsoft.com/office/powerpoint/2012/main",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
}


def qn(tag: str) -> str:
    """Convert prefixed tag to Clark notation.

    Example: qn("p:sld") -> "{http://schemas.openxmlformats.org/.../main}sld"
    """
    if ":" not in tag:
        return tag
    prefix, local = tag.split(":", 1)
    ns = NSMAP.get(prefix)
    if ns is None:
        raise ValueError(f"Unknown namespace prefix: {prefix}")
    return f"{{{ns}}}{local}"


class CT(OPC_CT):
    """Content types for PresentationML parts."""

    # Main presentation
    PML_PRESENTATION_MAIN = "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
    PML_PRESENTATION_MACRO = (
        "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml"
    )
    PML_TEMPLATE_MAIN = (
        "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"
    )

    # Slides
    PML_SLIDE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
    PML_SLIDE_LAYOUT = (
        "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"
    )
    PML_SLIDE_MASTER = (
        "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"
    )

    # Notes
    PML_NOTES_SLIDE = (
        "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"
    )
    PML_NOTES_MASTER = (
        "application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"
    )
    PML_HANDOUT_MASTER = (
        "application/vnd.openxmlformats-officedocument.presentationml.handoutMaster+xml"
    )

    # Properties
    PML_PRES_PROPS = (
        "application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"
    )
    PML_VIEW_PROPS = (
        "application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"
    )
    PML_TABLE_STYLES = (
        "application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"
    )

    # Theme
    THEME = "application/vnd.openxmlformats-officedocument.theme+xml"

    # Comments
    PML_COMMENTS = (
        "application/vnd.openxmlformats-officedocument.presentationml.comments+xml"
    )
    PML_COMMENT_AUTHORS = "application/vnd.openxmlformats-officedocument.presentationml.commentAuthors+xml"


class RT(OPC_RT):
    """Relationship types for PresentationML."""

    # Main document
    OFFICE_DOCUMENT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"

    # Slides
    SLIDE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
    SLIDE_LAYOUT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
    SLIDE_MASTER = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster"

    # Notes
    NOTES_SLIDE = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"
    )
    NOTES_MASTER = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster"
    HANDOUT_MASTER = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/handoutMaster"

    # Properties
    PRES_PROPS = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps"
    )
    VIEW_PROPS = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps"
    )
    TABLE_STYLES = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles"

    # Theme
    THEME = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"

    # Media
    IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    VIDEO = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/video"
    AUDIO = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/audio"

    # Other
    HYPERLINK = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
    )
    COMMENTS = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
    )
    COMMENT_AUTHORS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentAuthors"
