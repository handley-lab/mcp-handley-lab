"""Generic OPC (Open Packaging Conventions) constants.

Only package-level namespaces, content types, and relationship types.
Format-specific constants (Word, Excel) live in their respective modules.
"""


class CT:
    """Content type constants - generic OPC only."""

    # Package-level
    OPC_CORE_PROPERTIES = "application/vnd.openxmlformats-package.core-properties+xml"
    OPC_RELATIONSHIPS = "application/vnd.openxmlformats-package.relationships+xml"
    OPC_CUSTOM_PROPERTIES = (
        "application/vnd.openxmlformats-officedocument.custom-properties+xml"
    )
    OPC_EXTENDED_PROPERTIES = (
        "application/vnd.openxmlformats-officedocument.extended-properties+xml"
    )

    # Generic XML
    XML = "application/xml"

    # DrawingML charts (shared across formats)
    CHART = "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"

    # Images (shared across formats)
    PNG = "image/png"
    JPEG = "image/jpeg"
    GIF = "image/gif"
    TIFF = "image/tiff"
    BMP = "image/bmp"


class RT:
    """Relationship type constants - generic OPC only."""

    # Package-level
    CORE_PROPERTIES = (
        "http://schemas.openxmlformats.org/package/2006/relationships/"
        "metadata/core-properties"
    )
    EXTENDED_PROPERTIES = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
        "extended-properties"
    )
    CUSTOM_PROPERTIES = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
        "custom-properties"
    )
    OFFICE_DOCUMENT = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
        "officeDocument"
    )

    # Shared across formats
    IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    THEME = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
    CHART = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
    PACKAGE = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/package"
    )


# Default content types by extension (shared across formats)
DEFAULT_CONTENT_TYPES = {
    "rels": CT.OPC_RELATIONSHIPS,
    "xml": CT.XML,
    "png": CT.PNG,
    "jpeg": CT.JPEG,
    "jpg": CT.JPEG,
    "gif": CT.GIF,
    "tiff": CT.TIFF,
    "tif": CT.TIFF,
    "bmp": CT.BMP,
}
