"""[Content_Types].xml handling."""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.opc.constants import DEFAULT_CONTENT_TYPES

_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_CT_NSMAP = {"ct": _CT_NS}


class ContentTypeMap:
    """Maps partnames to content types.

    Uses two strategies:
    1. Defaults: Extension-based (e.g., .png -> image/png)
    2. Overrides: Partname-based (e.g., /word/document.xml -> specific type)
    """

    def __init__(self, defaults: dict[str, str] | None = None) -> None:
        self._defaults: dict[str, str] = (
            dict(defaults) if defaults else dict(DEFAULT_CONTENT_TYPES)
        )
        self._overrides: dict[str, str] = {}

    def __getitem__(self, partname: str) -> str:
        """Get content type for partname."""
        if partname in self._overrides:
            return self._overrides[partname]
        ext = partname.rsplit(".", 1)[-1].lower()
        if ext in self._defaults:
            return self._defaults[ext]
        return "application/octet-stream"

    def __setitem__(self, partname: str, content_type: str) -> None:
        """Set content type override for partname."""
        self._overrides[partname] = content_type

    def add_default(self, ext: str, content_type: str) -> None:
        """Add extension default if not present."""
        if ext not in self._defaults:
            self._defaults[ext] = content_type

    def drop_override(self, partname: str) -> None:
        """Remove content type override for partname."""
        self._overrides.pop(partname, None)

    @classmethod
    def from_xml(cls, xml_bytes: bytes) -> ContentTypeMap:
        """Parse [Content_Types].xml."""
        ct_map = cls()
        root = etree.fromstring(xml_bytes)
        for default in root.findall("ct:Default", _CT_NSMAP):
            ext = default.get("Extension")
            content_type = default.get("ContentType")
            if ext and content_type:
                ct_map._defaults[ext] = content_type
        for override in root.findall("ct:Override", _CT_NSMAP):
            partname = override.get("PartName")
            content_type = override.get("ContentType")
            if partname and content_type:
                ct_map._overrides[partname] = content_type
        return ct_map

    def to_xml(self) -> bytes:
        """Serialize to [Content_Types].xml."""
        root = etree.Element(f"{{{_CT_NS}}}Types", nsmap={None: _CT_NS})
        for ext, ct in sorted(self._defaults.items()):
            etree.SubElement(
                root, f"{{{_CT_NS}}}Default", Extension=ext, ContentType=ct
            )
        for partname, ct in sorted(self._overrides.items()):
            etree.SubElement(
                root, f"{{{_CT_NS}}}Override", PartName=partname, ContentType=ct
            )
        return etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=True
        )
