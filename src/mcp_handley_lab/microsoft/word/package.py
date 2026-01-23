"""WordPackage - Word-specific OPC package."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import BinaryIO

from lxml import etree

from mcp_handley_lab.microsoft.opc import OpcPackage
from mcp_handley_lab.microsoft.word.constants import CT, RT, qn


class WordPackage(OpcPackage):
    """Word-specific OPC package.

    Extends OpcPackage with Word-specific convenience properties
    and document creation.
    """

    # Common image types that may not be in mimetypes database
    _IMAGE_TYPES = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "tiff": "image/tiff",
        "tif": "image/tiff",
        "webp": "image/webp",
        "svg": "image/svg+xml",
        "emf": "image/x-emf",
        "wmf": "image/x-wmf",
    }

    # === Convenience Properties ===

    def get_optional_xml(self, path: str) -> etree._Element | None:
        """Get XML part if it exists, else None."""
        return self.get_xml(path) if self.has_part(path) else None

    @property
    def document_xml(self) -> etree._Element:
        return self.get_xml("/word/document.xml")

    @property
    def styles_xml(self) -> etree._Element | None:
        return self.get_optional_xml("/word/styles.xml")

    @property
    def numbering_xml(self) -> etree._Element | None:
        return self.get_optional_xml("/word/numbering.xml")

    @property
    def settings_xml(self) -> etree._Element | None:
        return self.get_optional_xml("/word/settings.xml")

    @property
    def comments_xml(self) -> etree._Element | None:
        return self.get_optional_xml("/word/comments.xml")

    @property
    def footnotes_xml(self) -> etree._Element | None:
        return self.get_optional_xml("/word/footnotes.xml")

    @property
    def endnotes_xml(self) -> etree._Element | None:
        return self.get_optional_xml("/word/endnotes.xml")

    @property
    def body(self) -> etree._Element:
        return self.document_xml.find(qn("w:body"))

    # === Factory Methods ===

    @classmethod
    def open(cls, file: str | Path | BinaryIO) -> WordPackage:
        """Open a .docx file."""
        pkg = cls()
        if isinstance(file, str | Path):
            with open(file, "rb") as f:
                pkg._load_from_stream(f)
        else:
            pkg._load_from_stream(file)
        return pkg

    def _reload_from_file(self, path: str | Path) -> None:
        """Reload package contents from file after external modification.

        Used for operations like footnotes that require saving to disk
        and then continuing with batch operations.
        """
        # Clear existing state
        self._xml.clear()
        self._bytes.clear()
        self._rels.clear()
        self._dirty_xml.clear()
        self._dirty_rels.clear()
        # Reload from file
        with open(path, "rb") as f:
            self._load_from_stream(f)

    @classmethod
    def new(cls) -> WordPackage:
        """Create a new empty Word document."""
        pkg = cls()
        pkg._create_minimal_document()
        return pkg

    def _create_minimal_document(self) -> None:
        """Create minimal valid Word document structure.

        Creates document.xml, styles.xml, settings.xml, and core.xml
        for a document that reliably opens in Microsoft Word.
        """
        w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

        # Document XML
        doc_nsmap = {None: w_ns, "r": r_ns}
        document = etree.Element(qn("w:document"), nsmap=doc_nsmap)
        body = etree.SubElement(document, qn("w:body"))
        p = etree.SubElement(body, qn("w:p"))
        etree.SubElement(p, qn("w:r"))

        # Section properties with page size and margins
        sectPr = body.find(qn("w:sectPr"))
        if sectPr is None:
            sectPr = etree.SubElement(body, qn("w:sectPr"))
        pgSz = etree.SubElement(sectPr, qn("w:pgSz"))
        pgSz.set(qn("w:w"), "12240")  # 8.5 inches in twips
        pgSz.set(qn("w:h"), "15840")  # 11 inches in twips
        pgMar = etree.SubElement(sectPr, qn("w:pgMar"))
        pgMar.set(qn("w:top"), "1440")  # 1 inch
        pgMar.set(qn("w:right"), "1440")
        pgMar.set(qn("w:bottom"), "1440")
        pgMar.set(qn("w:left"), "1440")
        pgMar.set(qn("w:header"), "720")  # 0.5 inch
        pgMar.set(qn("w:footer"), "720")
        pgMar.set(qn("w:gutter"), "0")

        self._xml["/word/document.xml"] = document
        self._bytes["/word/document.xml"] = b""
        self._dirty_xml.add("/word/document.xml")
        self._content_types["/word/document.xml"] = CT.WML_DOCUMENT_MAIN

        # Styles XML (minimal)
        styles_nsmap = {None: w_ns}
        styles = etree.Element(qn("w:styles"), nsmap=styles_nsmap)
        # Add Normal style
        normal = etree.SubElement(styles, qn("w:style"))
        normal.set(qn("w:type"), "paragraph")
        normal.set(qn("w:styleId"), "Normal")
        normal.set(qn("w:default"), "1")
        name_el = etree.SubElement(normal, qn("w:name"))
        name_el.set(qn("w:val"), "Normal")
        self._xml["/word/styles.xml"] = styles
        self._bytes["/word/styles.xml"] = b""
        self._dirty_xml.add("/word/styles.xml")
        self._content_types["/word/styles.xml"] = CT.WML_STYLES

        # Settings XML (minimal)
        settings = etree.Element(qn("w:settings"), nsmap=styles_nsmap)
        self._xml["/word/settings.xml"] = settings
        self._bytes["/word/settings.xml"] = b""
        self._dirty_xml.add("/word/settings.xml")
        self._content_types["/word/settings.xml"] = CT.WML_SETTINGS

        # Core properties (docProps/core.xml)
        ns_cp = (
            "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
        )
        ns_dc = "http://purl.org/dc/elements/1.1/"
        ns_dcterms = "http://purl.org/dc/terms/"
        ns_xsi = "http://www.w3.org/2001/XMLSchema-instance"
        core_nsmap = {"cp": ns_cp, "dc": ns_dc, "dcterms": ns_dcterms, "xsi": ns_xsi}
        core = etree.Element(f"{{{ns_cp}}}coreProperties", nsmap=core_nsmap)
        etree.SubElement(core, f"{{{ns_dc}}}title")
        etree.SubElement(core, f"{{{ns_dc}}}creator")
        etree.SubElement(core, f"{{{ns_cp}}}revision").text = "1"
        self._xml["/docProps/core.xml"] = core
        self._bytes["/docProps/core.xml"] = b""
        self._dirty_xml.add("/docProps/core.xml")
        self._content_types["/docProps/core.xml"] = CT.OPC_CORE_PROPERTIES

        # Package relationships
        self._pkg_rels.add(RT.OFFICE_DOCUMENT, "word/document.xml")
        self._pkg_rels.add(RT.CORE_PROPERTIES, "docProps/core.xml")

        # Document relationships to styles and settings
        doc_rels = self.get_rels("/word/document.xml")
        doc_rels.add(RT.STYLES, "styles.xml")
        doc_rels.add(RT.SETTINGS, "settings.xml")
        self._dirty_rels.add("/word/document.xml")

    # === Image Helpers ===

    def add_image(self, image_bytes: bytes, ext: str = "png") -> str:
        """Add image to package and return rId from document.xml."""
        ext = ext.lower().lstrip(".")
        content_type, _ = mimetypes.guess_type(f"file.{ext}")
        if not content_type:
            content_type = self._IMAGE_TYPES.get(ext)
            if not content_type:
                raise ValueError(f"Unknown image extension: {ext!r}")

        # Find next image number
        n = 1
        while self.has_part(f"/word/media/image{n}.{ext}"):
            n += 1

        partname = f"/word/media/image{n}.{ext}"
        self.set_bytes(partname, image_bytes)
        self._content_types.add_default(ext, content_type)

        # Add relationship from document.xml
        target = f"media/image{n}.{ext}"
        return self.relate_to("/word/document.xml", target, RT.IMAGE)
