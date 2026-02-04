"""Visio package wrapper extending OpcPackage."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import BinaryIO

from lxml import etree

from mcp_handley_lab.microsoft.opc.package import OpcPackage
from mcp_handley_lab.microsoft.visio.constants import (
    CT,
    NS_REL,
    NS_VISIO_2012,
    RT,
    findall_v,
)


class VisioPackage(OpcPackage):
    """Visio-specific OPC package wrapper.

    Provides convenience properties and methods for working with .vsdx files.
    All part paths are resolved via the OPC relationship graph, not hardcoded.
    """

    def __init__(self) -> None:
        super().__init__()
        self._document_path: str | None = None
        self._pages_path: str | None = None
        self._masters_path: str | None = None
        self._page_paths: list[tuple[int, str, str]] | None = None
        self._master_paths: list[tuple[int, str, str]] | None = None

    @property
    def document_path(self) -> str:
        """Resolve document.xml via RT.DOCUMENT from package rels."""
        if self._document_path is None:
            pkg_rels = self.get_pkg_rels()
            rid = pkg_rels.rId_for_reltype(RT.DOCUMENT)
            if rid is None:
                raise ValueError("No document relationship found in package")
            target = pkg_rels.target_for_rId(rid)
            self._document_path = target if target.startswith("/") else "/" + target
        return self._document_path

    @property
    def document_xml(self) -> etree._Element:
        """Get the document.xml root element."""
        return self.get_xml(self.document_path)

    @property
    def pages_path(self) -> str | None:
        """Resolve pages.xml via RT.PAGES from document rels."""
        if self._pages_path is None:
            doc_rels = self.get_rels(self.document_path)
            rid = doc_rels.rId_for_reltype(RT.PAGES)
            if rid is None:
                return None
            self._pages_path = self.resolve_rel_target(self.document_path, rid)
        return self._pages_path

    @property
    def masters_path(self) -> str | None:
        """Resolve masters.xml via RT.MASTERS from document rels."""
        if self._masters_path is None:
            doc_rels = self.get_rels(self.document_path)
            rid = doc_rels.rId_for_reltype(RT.MASTERS)
            if rid is None:
                return None
            self._masters_path = self.resolve_rel_target(self.document_path, rid)
        return self._masters_path

    def get_page_paths(self) -> list[tuple[int, str, str]]:
        """Get ordered list of (page_number, rId, partname) tuples.

        Page order is determined by Page elements in pages.xml.
        """
        if self._page_paths is not None:
            return self._page_paths

        pages_path = self.pages_path
        if pages_path is None:
            self._page_paths = []
            return self._page_paths

        pages_xml = self.get_xml(pages_path)
        pages_rels = self.get_rels(pages_path)

        # Build rId -> partname mapping for PAGE relationships
        rid_to_path: dict[str, str] = {}
        for rid, rel in pages_rels.items():
            if rel.reltype == RT.PAGE:
                rid_to_path[rid] = self.resolve_rel_target(pages_path, rid)

        # Parse Page elements from pages.xml to get order and rId mapping
        result = []
        page_els = findall_v(pages_xml, "Page")
        for idx, page_el in enumerate(page_els, start=1):
            # r:id attribute (standard OPC relationship reference)
            rid = page_el.get(f"{{{NS_REL}}}id")
            if rid and rid in rid_to_path:
                result.append((idx, rid, rid_to_path[rid]))

        self._page_paths = result
        return self._page_paths

    def get_page_xml(self, page_num: int) -> etree._Element:
        """Get page XML by 1-based page number."""
        for num, _rid, partname in self.get_page_paths():
            if num == page_num:
                return self.get_xml(partname)
        raise KeyError(f"Page {page_num} not found")

    def get_page_partname(self, page_num: int) -> str:
        """Get page partname by 1-based page number."""
        for num, _rid, partname in self.get_page_paths():
            if num == page_num:
                return partname
        raise KeyError(f"Page {page_num} not found")

    def mark_page_dirty(self, page_num: int) -> None:
        """Mark a page as modified so it will be serialized on save.

        Convenience wrapper around mark_xml_dirty(get_page_partname(page_num)).
        """
        self.mark_xml_dirty(self.get_page_partname(page_num))

    def get_pages_xml(self) -> etree._Element | None:
        """Get the pages.xml root element."""
        pages_path = self.pages_path
        if pages_path is None:
            return None
        return self.get_xml(pages_path)

    def get_masters_xml(self) -> etree._Element | None:
        """Get the masters.xml root element."""
        masters_path = self.masters_path
        if masters_path is None:
            return None
        return self.get_xml(masters_path)

    def get_master_paths(self) -> list[tuple[int, str, str]]:
        """Get list of (master_id, rId, partname) tuples for masters."""
        if self._master_paths is not None:
            return self._master_paths

        masters_path = self.masters_path
        if masters_path is None:
            self._master_paths = []
            return self._master_paths

        masters_xml = self.get_xml(masters_path)
        masters_rels = self.get_rels(masters_path)

        # Build rId -> partname mapping
        rid_to_path: dict[str, str] = {}
        for rid, rel in masters_rels.items():
            if rel.reltype == RT.MASTER:
                rid_to_path[rid] = self.resolve_rel_target(masters_path, rid)

        result = []
        master_els = findall_v(masters_xml, "Master")
        for master_el in master_els:
            master_id_str = master_el.get("ID")
            if master_id_str is None:
                continue
            master_id = int(master_id_str)
            rid = master_el.get(f"{{{NS_REL}}}id")
            if rid and rid in rid_to_path:
                result.append((master_id, rid, rid_to_path[rid]))

        self._master_paths = result
        return self._master_paths

    def get_master_xml(self, master_id: int) -> etree._Element | None:
        """Get master XML by master ID."""
        for mid, _rid, partname in self.get_master_paths():
            if mid == master_id:
                return self.get_xml(partname)
        return None

    @classmethod
    def new(cls) -> VisioPackage:
        """Create a new blank Visio document with one empty page.

        Builds a minimal valid .vsdx in memory with:
        - document.xml (empty VisioDocument)
        - pages/pages.xml with one 8.5x11 page
        - pages/page1.xml with empty Shapes container
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            # Content Types
            ct_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            ct_xml += '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            ct_xml += f'<Override PartName="/visio/document.xml" ContentType="{CT.VSD_DOCUMENT}"/>'
            ct_xml += f'<Override PartName="/visio/pages/pages.xml" ContentType="{CT.VSD_PAGES}"/>'
            ct_xml += f'<Override PartName="/visio/pages/page1.xml" ContentType="{CT.VSD_PAGE}"/>'
            ct_xml += '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            ct_xml += '<Default Extension="xml" ContentType="application/xml"/>'
            ct_xml += "</Types>"
            z.writestr("[Content_Types].xml", ct_xml)

            # Package rels
            pkg_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            pkg_rels += '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            pkg_rels += f'<Relationship Id="rId1" Type="{RT.DOCUMENT}" Target="visio/document.xml"/>'
            pkg_rels += "</Relationships>"
            z.writestr("_rels/.rels", pkg_rels)

            # Document.xml
            doc = etree.Element(f"{{{NS_VISIO_2012}}}VisioDocument")
            z.writestr(
                "visio/document.xml",
                etree.tostring(doc, xml_declaration=True, encoding="UTF-8"),
            )

            # Document rels -> pages
            doc_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            doc_rels += '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            doc_rels += (
                f'<Relationship Id="rId1" Type="{RT.PAGES}" Target="pages/pages.xml"/>'
            )
            doc_rels += "</Relationships>"
            z.writestr("visio/_rels/document.xml.rels", doc_rels)

            # Pages.xml with one page
            pages = etree.Element(f"{{{NS_VISIO_2012}}}Pages")
            page_el = etree.SubElement(
                pages,
                f"{{{NS_VISIO_2012}}}Page",
                ID="0",
                Name="Page-1",
                NameU="Page-1",
                attrib={f"{{{NS_REL}}}id": "rId1"},
            )
            page_sheet = etree.SubElement(page_el, f"{{{NS_VISIO_2012}}}PageSheet")
            etree.SubElement(
                page_sheet, f"{{{NS_VISIO_2012}}}Cell", N="PageWidth", V="8.5", U="IN"
            )
            etree.SubElement(
                page_sheet, f"{{{NS_VISIO_2012}}}Cell", N="PageHeight", V="11", U="IN"
            )
            z.writestr(
                "visio/pages/pages.xml",
                etree.tostring(pages, xml_declaration=True, encoding="UTF-8"),
            )

            # Pages rels
            pages_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            pages_rels += '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            pages_rels += (
                f'<Relationship Id="rId1" Type="{RT.PAGE}" Target="page1.xml"/>'
            )
            pages_rels += "</Relationships>"
            z.writestr("visio/pages/_rels/pages.xml.rels", pages_rels)

            # Page1.xml with empty Shapes container
            page_contents = etree.Element(f"{{{NS_VISIO_2012}}}PageContents")
            etree.SubElement(page_contents, f"{{{NS_VISIO_2012}}}Shapes")
            z.writestr(
                "visio/pages/page1.xml",
                etree.tostring(page_contents, xml_declaration=True, encoding="UTF-8"),
            )

        buf.seek(0)
        return cls.open(buf)

    @classmethod
    def open(cls, file: str | Path | BinaryIO) -> VisioPackage:
        """Open an existing Visio file.

        Supports .vsdx and .vsdm files. Rejects legacy .vsd format.
        """
        if isinstance(file, str | Path):
            path = Path(file)
            suffix = path.suffix.lower()
            if suffix == ".vsd":
                raise ValueError(
                    "Legacy .vsd format is not supported. "
                    "Convert to .vsdx using Visio or LibreOffice first."
                )
            if suffix not in (".vsdx", ".vsdm", ".vssx", ".vstx", ".vssm", ".vstm"):
                raise ValueError(
                    f"Unsupported file format: {suffix}. "
                    "Expected .vsdx, .vsdm, .vssx, or .vstx."
                )

        pkg = cls()
        if isinstance(file, str | Path):
            with open(file, "rb") as f:
                pkg._load_from_stream(f)
        else:
            pkg._load_from_stream(file)
        return pkg

    def invalidate_caches(self) -> None:
        """Clear cached values after modifications."""
        self._document_path = None
        self._page_paths = None
        self._master_paths = None
        self._pages_path = None
        self._masters_path = None
