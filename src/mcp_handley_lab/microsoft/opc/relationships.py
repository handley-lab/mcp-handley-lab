"""Relationship management for OPC packages."""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_REL_NSMAP = {"rel": _REL_NS}


@dataclass(frozen=True)
class Relationship:
    """Single relationship entry."""

    rId: str  # noqa: N815 (standard OOXML term)
    reltype: str
    target: str
    is_external: bool = False


class Relationships(dict):
    """Collection of relationships, keyed by rId.

    Manages rId generation and provides lookup methods.
    """

    def __init__(self, base_uri: str = "") -> None:
        super().__init__()
        self._base_uri = base_uri  # e.g., "/word" for document.xml.rels

    @property
    def _next_rId(self) -> str:
        """Generate next available rId. Reuses gaps in numbering."""
        for n in range(1, len(self) + 2):
            candidate = f"rId{n}"
            if candidate not in self:
                return candidate
        raise RuntimeError("rId generation overflow")

    def add(self, reltype: str, target: str, is_external: bool = False) -> str:
        """Add relationship and return its rId."""
        rId = self._next_rId
        self[rId] = Relationship(rId, reltype, target, is_external)
        return rId

    def get_or_add(self, reltype: str, target: str, is_external: bool = False) -> str:
        """Get existing rId for target or create new relationship."""
        for rel in self.values():
            if rel.target == target and rel.reltype == reltype:
                return rel.rId
        return self.add(reltype, target, is_external)

    def target_for_rId(self, rId: str) -> str | None:
        """Get target path for rId."""
        rel = self.get(rId)
        return rel.target if rel else None

    def rId_for_reltype(self, reltype: str) -> str | None:
        """Get first rId matching relationship type."""
        for rel in self.values():
            if rel.reltype == reltype:
                return rel.rId
        return None

    def all_for_reltype(self, reltype: str) -> list[Relationship]:
        """Get all relationships matching a relationship type."""
        return [rel for rel in self.values() if rel.reltype == reltype]

    def remove(self, rId: str) -> bool:
        """Remove relationship by rId. Returns True if removed."""
        if rId in self:
            del self[rId]
            return True
        return False

    @classmethod
    def from_xml(cls, xml_bytes: bytes, base_uri: str = "") -> Relationships:
        """Parse .rels file."""
        rels = cls(base_uri)
        root = etree.fromstring(xml_bytes)
        for rel_el in root.findall("rel:Relationship", _REL_NSMAP):
            rId = rel_el.get("Id")
            reltype = rel_el.get("Type")
            target = rel_el.get("Target")
            is_external = rel_el.get("TargetMode") == "External"
            if rId and reltype and target:
                rels[rId] = Relationship(rId, reltype, target, is_external)
        return rels

    def to_xml(self) -> bytes:
        """Serialize to .rels XML."""
        root = etree.Element(f"{{{_REL_NS}}}Relationships", nsmap={None: _REL_NS})
        for rel in sorted(self.values(), key=lambda r: r.rId):
            attrs = {"Id": rel.rId, "Type": rel.reltype, "Target": rel.target}
            if rel.is_external:
                attrs["TargetMode"] = "External"
            etree.SubElement(root, f"{{{_REL_NS}}}Relationship", **attrs)
        return etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=True
        )
