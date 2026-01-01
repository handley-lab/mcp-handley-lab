"""Document properties operations.

Contains functions for:
- Core properties (title, author, created, modified, revision)
- Custom properties (user-defined metadata in docProps/custom.xml)
"""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.models import CustomPropertyInfo, DocumentMeta

# Namespaces for properties
_NS_CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_NS_DC = "http://purl.org/dc/elements/1.1/"
_NS_DCTERMS = "http://purl.org/dc/terms/"
_NS_CUSTOM = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
_NS_VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"

# =============================================================================
# Core Properties
# =============================================================================


def get_document_meta(pkg) -> DocumentMeta:
    """Extract document metadata from core properties and custom properties.

    Args:
        pkg: WordPackage
    """
    title = author = created = modified = ""
    revision = 0

    if pkg.has_part("/docProps/core.xml"):
        core_xml = pkg.get_xml("/docProps/core.xml")

        # Title from dc:title
        title_el = core_xml.find(f"{{{_NS_DC}}}title")
        if title_el is not None and title_el.text:
            title = title_el.text

        # Author from dc:creator
        author_el = core_xml.find(f"{{{_NS_DC}}}creator")
        if author_el is not None and author_el.text:
            author = author_el.text

        # Created from dcterms:created
        created_el = core_xml.find(f"{{{_NS_DCTERMS}}}created")
        if created_el is not None and created_el.text:
            created = created_el.text

        # Modified from dcterms:modified
        modified_el = core_xml.find(f"{{{_NS_DCTERMS}}}modified")
        if modified_el is not None and modified_el.text:
            modified = modified_el.text

        # Revision from cp:revision
        rev_el = core_xml.find(f"{{{_NS_CP}}}revision")
        if rev_el is not None and rev_el.text:
            revision = int(rev_el.text)

    # Count sections from document.xml
    sections = 0
    body = pkg.body
    # Section breaks in paragraphs
    for p in body.findall(qn("w:p")):
        pPr = p.find(qn("w:pPr"))
        if pPr is not None and pPr.find(qn("w:sectPr")) is not None:
            sections += 1
    # Final section (w:body/w:sectPr)
    if body.find(qn("w:sectPr")) is not None:
        sections += 1

    custom_props = get_custom_properties(pkg)

    return DocumentMeta(
        title=title,
        author=author,
        created=created,
        modified=modified,
        revision=revision,
        sections=sections,
        custom_properties=custom_props,
    )


def _create_core_xml(pkg) -> None:
    """Create core.xml part with relationship and content type.

    Used defensively when setting metadata on docs that lack core.xml.
    """
    from mcp_handley_lab.microsoft.word.constants import CT, RT

    ns_xsi = "http://www.w3.org/2001/XMLSchema-instance"
    core_nsmap = {
        "cp": _NS_CP,
        "dc": _NS_DC,
        "dcterms": _NS_DCTERMS,
        "xsi": ns_xsi,
    }
    core = etree.Element(f"{{{_NS_CP}}}coreProperties", nsmap=core_nsmap)
    # Create all elements that set_document_meta or get_document_meta might use
    etree.SubElement(core, f"{{{_NS_DC}}}title")
    etree.SubElement(core, f"{{{_NS_DC}}}creator")
    etree.SubElement(core, f"{{{_NS_DC}}}subject")
    etree.SubElement(core, f"{{{_NS_DC}}}description")
    etree.SubElement(core, f"{{{_NS_CP}}}keywords")
    etree.SubElement(core, f"{{{_NS_CP}}}category")
    etree.SubElement(core, f"{{{_NS_CP}}}lastModifiedBy")
    etree.SubElement(core, f"{{{_NS_CP}}}revision").text = "1"

    # Set part with content type
    pkg.set_xml("/docProps/core.xml", core, CT.OPC_CORE_PROPERTIES)

    # Add package relationship if not already present (avoid duplicates on corrupt docs)
    pkg_rels = pkg.get_pkg_rels()
    if pkg_rels.rId_for_reltype(RT.CORE_PROPERTIES) is None:
        pkg.relate_from_package("docProps/core.xml", RT.CORE_PROPERTIES)


def set_document_meta(pkg, **kwargs) -> None:
    """Update document core properties. Only updates non-None values.

    Args:
        pkg: WordPackage
        **kwargs: Properties to update (title, author, etc.)
    """
    if not pkg.has_part("/docProps/core.xml"):
        _create_core_xml(pkg)

    core_xml = pkg.get_xml("/docProps/core.xml")

    # Mapping from kwargs to XML elements
    prop_map = {
        "title": (f"{{{_NS_DC}}}title", None),
        "author": (f"{{{_NS_DC}}}creator", None),
        "subject": (f"{{{_NS_DC}}}subject", None),
        "keywords": (f"{{{_NS_CP}}}keywords", None),
        "category": (f"{{{_NS_CP}}}category", None),
        "comments": (f"{{{_NS_DC}}}description", None),
    }

    for key, value in kwargs.items():
        if value is None:
            continue
        if key not in prop_map:
            raise ValueError(f"Unknown metadata key: {key}")

        tag, _ = prop_map[key]
        el = core_xml.find(tag)
        if el is None:
            el = etree.SubElement(core_xml, tag)
        el.text = str(value)

    pkg.mark_xml_dirty("/docProps/core.xml")


# =============================================================================
# Custom Properties
# =============================================================================


def _parse_custom_property(prop) -> CustomPropertyInfo:
    """Parse a single custom property element."""
    name = prop.get("name", "")
    value = ""
    prop_type = "string"

    for child in prop:
        local_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if local_tag == "lpwstr":
            value = child.text or ""
            prop_type = "string"
        elif local_tag == "i4":
            value = child.text or "0"
            prop_type = "int"
        elif local_tag == "bool":
            value = child.text or "false"
            prop_type = "bool"
        elif local_tag == "filetime":
            value = child.text or ""
            prop_type = "datetime"
        elif local_tag == "r8":
            value = child.text or "0.0"
            prop_type = "float"
        break

    return CustomPropertyInfo(name=name, value=value, type=prop_type)


def get_custom_properties(pkg) -> list[CustomPropertyInfo]:
    """Get all custom document properties from docProps/custom.xml.

    Args:
        pkg: WordPackage
    """
    if not pkg.has_part("/docProps/custom.xml"):
        return []

    custom_xml = pkg.get_xml("/docProps/custom.xml")
    return [
        _parse_custom_property(prop)
        for prop in custom_xml.findall(f"{{{_NS_CUSTOM}}}property")
    ]


def set_custom_property(pkg, name: str, value: str, prop_type: str = "string") -> None:
    """Set or update a custom document property.

    Args:
        pkg: WordPackage
        name: Property name (must be unique)
        value: Property value as string
        prop_type: One of "string", "int", "bool", "datetime", "float"
    """
    # Type to element tag mapping
    type_map = {
        "string": f"{{{_NS_VT}}}lpwstr",
        "int": f"{{{_NS_VT}}}i4",
        "bool": f"{{{_NS_VT}}}bool",
        "datetime": f"{{{_NS_VT}}}filetime",
        "float": f"{{{_NS_VT}}}r8",
    }
    value_tag = type_map.get(prop_type, type_map["string"])

    # Create or update custom.xml
    if pkg.has_part("/docProps/custom.xml"):
        custom_xml = pkg.get_xml("/docProps/custom.xml")
    else:
        # Create new custom.xml
        custom_xml = etree.Element(
            f"{{{_NS_CUSTOM}}}Properties",
            nsmap={None: _NS_CUSTOM, "vt": _NS_VT},
        )
        pkg.set_xml(
            "/docProps/custom.xml",
            custom_xml,
            "application/vnd.openxmlformats-officedocument.custom-properties+xml",
        )
        # Add package relationship
        pkg.relate_from_package(
            "docProps/custom.xml",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties",
        )

    # Find existing property or create new
    existing = None
    max_pid = 1
    for prop in custom_xml.findall(f"{{{_NS_CUSTOM}}}property"):
        pid = int(prop.get("pid", "1"))
        if pid > max_pid:
            max_pid = pid
        if prop.get("name") == name:
            existing = prop

    if existing is not None:
        # Update existing property
        for child in list(existing):
            existing.remove(child)
        value_el = etree.SubElement(existing, value_tag)
        value_el.text = value
    else:
        # Add new property
        prop = etree.SubElement(custom_xml, f"{{{_NS_CUSTOM}}}property")
        prop.set("fmtid", "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}")
        prop.set("pid", str(max_pid + 1))
        prop.set("name", name)
        value_el = etree.SubElement(prop, value_tag)
        value_el.text = value

    pkg.mark_xml_dirty("/docProps/custom.xml")


def delete_custom_property(pkg, name: str) -> bool:
    """Delete a custom document property.

    Args:
        pkg: WordPackage
        name: Property name to delete

    Returns:
        True if property was found and deleted, False if not found
    """
    if not pkg.has_part("/docProps/custom.xml"):
        return False

    custom_xml = pkg.get_xml("/docProps/custom.xml")
    for prop in custom_xml.findall(f"{{{_NS_CUSTOM}}}property"):
        if prop.get("name") == name:
            custom_xml.remove(prop)
            pkg.mark_xml_dirty("/docProps/custom.xml")
            return True

    return False
