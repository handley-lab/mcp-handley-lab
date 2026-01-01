"""OpcPackage - generic Open Packaging Conventions package.

Base class for all OOXML packages (.docx, .xlsx, .pptx).
Provides generic part API without format-specific logic.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from posixpath import basename, dirname, normpath
from typing import BinaryIO

from lxml import etree

from mcp_handley_lab.microsoft.opc.content_types import ContentTypeMap
from mcp_handley_lab.microsoft.opc.relationships import Relationships


class OpcPackage:
    """In-memory representation of an OPC package.

    Provides general part API:
    - get_xml(partname) / set_xml(partname, root) - XML parts
    - get_bytes(partname) / set_bytes(partname, data) - binary parts
    - get_rels(partname) - relationships for any part
    - relate_to(partname, target, reltype) - add relationship from any part

    Uses dirty tracking to minimize serialization on save.
    """

    def __init__(self, defaults: dict[str, str] | None = None) -> None:
        self._bytes: dict[str, bytes] = {}  # Original bytes from ZIP
        self._xml: dict[str, etree._Element] = {}  # Parsed XML (lazy)
        self._dirty_xml: set[str] = set()  # Partnames with modified XML
        self._dirty_bytes: set[str] = set()  # Partnames with new/modified bytes
        self._content_types = ContentTypeMap(defaults)
        self._pkg_rels = Relationships()  # /_rels/.rels
        self._part_rels: dict[str, Relationships] = {}  # partname -> Relationships
        self._dirty_rels: set[str] = set()  # Partnames with modified relationships

    # === General Part API ===

    def get_xml(self, partname: str) -> etree._Element:
        """Get parsed XML for any part. Caches the parse."""
        if partname in self._xml:
            return self._xml[partname]
        self._xml[partname] = etree.fromstring(self._bytes[partname])
        return self._xml[partname]

    def set_xml(
        self, partname: str, root: etree._Element, content_type: str = ""
    ) -> None:
        """Set XML for a part. Marks as dirty for save."""
        self._xml[partname] = root
        self._dirty_xml.add(partname)
        if partname not in self._bytes:
            self._bytes[partname] = b""  # Placeholder for new parts
        if content_type:
            self._content_types[partname] = content_type

    def get_bytes(self, partname: str) -> bytes:
        """Get raw bytes for any part."""
        return self._bytes[partname]

    def set_bytes(self, partname: str, data: bytes, content_type: str = "") -> None:
        """Set bytes for a part. Marks as dirty."""
        self._bytes[partname] = data
        self._dirty_bytes.add(partname)
        if content_type:
            self._content_types[partname] = content_type

    def mark_xml_dirty(self, partname: str) -> None:
        """Mark an XML part as modified so it will be serialized on save.

        Use after in-place modification of elements returned by get_xml().
        """
        if partname not in self._xml:
            raise ValueError(f"Part not parsed as XML: {partname}")
        self._dirty_xml.add(partname)

    def has_part(self, partname: str) -> bool:
        """Check if part exists."""
        return partname in self._bytes

    def iter_partnames(self) -> Iterator[str]:
        """Iterate all partnames."""
        return iter(self._bytes.keys())

    def get_content_type(self, partname: str) -> str:
        """Get content type for a part."""
        return self._content_types[partname]

    def drop_part(self, partname: str) -> None:
        """Remove a part and its relationships."""
        self._bytes.pop(partname, None)
        self._xml.pop(partname, None)
        self._part_rels.pop(partname, None)
        self._dirty_xml.discard(partname)
        self._dirty_bytes.discard(partname)
        self._dirty_rels.discard(partname)
        self._content_types.drop_override(partname)

    # === Relationships API ===

    def get_pkg_rels(self) -> Relationships:
        """Get package-level relationships (/_rels/.rels)."""
        return self._pkg_rels

    def relate_from_package(
        self, target: str, reltype: str, *, is_external: bool = False
    ) -> str:
        """Add relationship from package root. Returns rId."""
        return self._pkg_rels.get_or_add(reltype, target, is_external)

    def get_rels(self, partname: str) -> Relationships:
        """Get relationships for any part. Creates empty if not exists."""
        if partname not in self._part_rels:
            rels_path = self._rels_path_for(partname)
            if rels_path in self._bytes:
                base_uri = dirname(partname)
                self._part_rels[partname] = Relationships.from_xml(
                    self._bytes[rels_path], base_uri
                )
            else:
                self._part_rels[partname] = Relationships(dirname(partname))
        return self._part_rels[partname]

    def relate_to(
        self,
        source_partname: str,
        target: str,
        reltype: str,
        *,
        is_external: bool = False,
    ) -> str:
        """Add relationship from source part to target. Returns rId."""
        rels = self.get_rels(source_partname)
        rId = rels.get_or_add(reltype, target, is_external)
        self._dirty_rels.add(source_partname)
        return rId

    def remove_rel(self, source_partname: str, rId: str) -> bool:
        """Remove relationship by rId from source part. Returns True if removed."""
        rels = self.get_rels(source_partname)
        if rels.remove(rId):
            self._dirty_rels.add(source_partname)
            return True
        return False

    def resolve_rel_target(self, partname: str, rId: str) -> str:
        """Resolve rId to absolute partname.

        Handles relative paths (e.g., "media/image1.png" from /word/document.xml).
        Returns normalized absolute partname starting with "/".
        """
        rels = self.get_rels(partname)
        rel = rels.get(rId)
        if not rel:
            raise KeyError(f"Relationship {rId} not found in {partname}")
        if rel.is_external:
            return rel.target  # External URL, return as-is
        # Internal: resolve relative to source part's directory
        base_uri = dirname(partname)
        resolved = normpath(f"{base_uri}/{rel.target}")
        # Ensure leading slash for absolute OPC partname
        if not resolved.startswith("/"):
            resolved = "/" + resolved
        return resolved

    # === Loading ===

    @classmethod
    def open(cls, file: str | Path | BinaryIO) -> OpcPackage:
        """Open an OPC package file."""
        pkg = cls()
        if isinstance(file, str | Path):
            with open(file, "rb") as f:
                pkg._load_from_stream(f)
        else:
            pkg._load_from_stream(file)
        return pkg

    def _load_from_stream(self, stream: BinaryIO) -> None:
        """Load package contents from stream."""
        with zipfile.ZipFile(stream, "r") as z:
            for name in z.namelist():
                partname = f"/{name}" if not name.startswith("/") else name
                self._bytes[partname] = z.read(name)

        # Parse content types
        if "/[Content_Types].xml" in self._bytes:
            self._content_types = ContentTypeMap.from_xml(
                self._bytes["/[Content_Types].xml"]
            )

        # Parse package relationships
        if "/_rels/.rels" in self._bytes:
            self._pkg_rels = Relationships.from_xml(self._bytes["/_rels/.rels"])

    # === Saving ===

    def save(self, file: str | Path | BinaryIO) -> None:
        """Save package to file. Uses atomic write for file paths."""
        stream = BytesIO()

        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
            # Write content types
            z.writestr("[Content_Types].xml", self._content_types.to_xml())

            # Write package relationships
            if self._pkg_rels:
                z.writestr("_rels/.rels", self._pkg_rels.to_xml())

            # Collect all .rels paths we'll write from _part_rels
            rels_to_write = {self._rels_path_for(pn) for pn in self._part_rels}

            # Write all parts
            for partname in self._bytes:
                # Skip content types and pkg rels (already written)
                if partname in ("/[Content_Types].xml", "/_rels/.rels"):
                    continue
                # Skip original .rels if we have modified version
                if partname in rels_to_write:
                    continue

                membername = partname.lstrip("/")

                # Only serialize XML if dirty; otherwise keep original bytes
                if partname in self._dirty_xml:
                    xml_bytes = etree.tostring(
                        self._xml[partname],
                        xml_declaration=True,
                        encoding="UTF-8",
                        standalone=True,
                    )
                    z.writestr(membername, xml_bytes)
                else:
                    z.writestr(membername, self._bytes[partname])

            # Write part relationships (only if dirty or new)
            for partname, rels in self._part_rels.items():
                if not rels:
                    continue
                rels_path = self._rels_path_for(partname)
                if partname in self._dirty_rels or rels_path not in self._bytes:
                    # Dirty or new: serialize
                    z.writestr(rels_path.lstrip("/"), rels.to_xml())
                elif rels_path in self._bytes:
                    # Unchanged: write original bytes
                    z.writestr(rels_path.lstrip("/"), self._bytes[rels_path])

        # Atomic write for file paths
        if isinstance(file, str | Path):
            file_path = Path(file)
            fd, temp_path = tempfile.mkstemp(
                suffix=file_path.suffix or ".pkg", dir=file_path.parent
            )
            try:
                os.write(fd, stream.getvalue())
                os.close(fd)
                os.replace(temp_path, file_path)
            except Exception:
                os.close(fd)
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        else:
            file.write(stream.getvalue())

    @staticmethod
    def _rels_path_for(partname: str) -> str:
        """Compute .rels path: /word/document.xml -> /word/_rels/document.xml.rels"""
        parent = dirname(partname)
        name = basename(partname)
        return f"{parent}/_rels/{name}.rels"
