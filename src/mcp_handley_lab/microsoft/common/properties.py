"""Common document properties operations for OPC packages.

Provides generic helpers for core properties (title, author, dates) and
custom properties (user-defined metadata). Works with any OPC-based package
(Word, Excel, PowerPoint).

Format-specific wrappers should use these helpers and return format-specific
models as needed.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lxml import etree

from mcp_handley_lab.microsoft.opc.constants import CT, RT

if TYPE_CHECKING:
    from mcp_handley_lab.microsoft.opc.package import OpcPackage

# Namespaces for properties
NS_CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
NS_DC = "http://purl.org/dc/elements/1.1/"
NS_DCTERMS = "http://purl.org/dc/terms/"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS_CUSTOM = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
NS_VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"

# Standard fmtid for custom properties
CUSTOM_PROPERTY_FMTID = "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}"

# Type mapping: user-friendly names to OOXML element names (both directions supported)
TYPE_MAP = {
    # User-friendly names
    "string": "lpwstr",
    "int": "i4",
    "datetime": "filetime",
    "float": "r8",
    # OOXML names (identity mappings + user-friendly aliases)
    "lpwstr": "lpwstr",
    "i4": "i4",
    "bool": "bool",
    "filetime": "filetime",
    "r8": "r8",
}


# =============================================================================
# Core Properties
# =============================================================================


def get_core_properties(pkg: OpcPackage) -> dict:
    """Extract core document properties from docProps/core.xml.

    Returns dict with keys: title, author, subject, keywords, category,
    comments, created, modified, revision, last_modified_by.
    All values are strings (empty if not present), except revision (int, 0 if not present).
    """
    result = {
        "title": "",
        "author": "",
        "subject": "",
        "keywords": "",
        "category": "",
        "comments": "",
        "created": "",
        "modified": "",
        "revision": 0,
        "last_modified_by": "",
    }

    if not pkg.has_part("/docProps/core.xml"):
        return result

    core_xml = pkg.get_xml("/docProps/core.xml")

    # Map XML elements to result keys
    mappings = [
        (f"{{{NS_DC}}}title", "title"),
        (f"{{{NS_DC}}}creator", "author"),
        (f"{{{NS_DC}}}subject", "subject"),
        (f"{{{NS_CP}}}keywords", "keywords"),
        (f"{{{NS_CP}}}category", "category"),
        (f"{{{NS_DC}}}description", "comments"),
        (f"{{{NS_DCTERMS}}}created", "created"),
        (f"{{{NS_DCTERMS}}}modified", "modified"),
        (f"{{{NS_CP}}}lastModifiedBy", "last_modified_by"),
    ]

    for tag, key in mappings:
        el = core_xml.find(tag)
        if el is not None and el.text:
            result[key] = el.text

    # Revision is an integer
    rev_el = core_xml.find(f"{{{NS_CP}}}revision")
    if rev_el is not None and rev_el.text and re.match(r"^\d+$", rev_el.text):
        result["revision"] = int(rev_el.text)

    return result


def _ensure_core_xml(pkg: OpcPackage) -> etree._Element:
    """Ensure docProps/core.xml exists and return it.

    Creates the part with relationship and content type if missing.
    """
    if pkg.has_part("/docProps/core.xml"):
        return pkg.get_xml("/docProps/core.xml")

    # Create new core.xml with all required namespaces
    core_nsmap = {
        "cp": NS_CP,
        "dc": NS_DC,
        "dcterms": NS_DCTERMS,
        "xsi": NS_XSI,
    }
    core = etree.Element(f"{{{NS_CP}}}coreProperties", nsmap=core_nsmap)

    # Create standard elements
    etree.SubElement(core, f"{{{NS_DC}}}title")
    etree.SubElement(core, f"{{{NS_DC}}}creator")
    etree.SubElement(core, f"{{{NS_DC}}}subject")
    etree.SubElement(core, f"{{{NS_DC}}}description")
    etree.SubElement(core, f"{{{NS_CP}}}keywords")
    etree.SubElement(core, f"{{{NS_CP}}}category")
    etree.SubElement(core, f"{{{NS_CP}}}lastModifiedBy")
    etree.SubElement(core, f"{{{NS_CP}}}revision").text = "1"

    # Create dcterms:created and dcterms:modified with xsi:type
    created = etree.SubElement(core, f"{{{NS_DCTERMS}}}created")
    created.set(f"{{{NS_XSI}}}type", "dcterms:W3CDTF")
    modified = etree.SubElement(core, f"{{{NS_DCTERMS}}}modified")
    modified.set(f"{{{NS_XSI}}}type", "dcterms:W3CDTF")

    # Set part with content type
    pkg.set_xml("/docProps/core.xml", core, CT.OPC_CORE_PROPERTIES)

    # Add package relationship if not already present
    pkg_rels = pkg.get_pkg_rels()
    if pkg_rels.rId_for_reltype(RT.CORE_PROPERTIES) is None:
        pkg.relate_from_package("docProps/core.xml", RT.CORE_PROPERTIES)

    return core


def set_core_properties(pkg: OpcPackage, **kwargs) -> None:
    """Update document core properties. Only updates non-None values.

    Supported keys: title, author, subject, keywords, category, comments,
    last_modified_by.

    Note: created/modified timestamps and revision are typically managed
    by the application, not set directly.
    """
    core_xml = _ensure_core_xml(pkg)

    # Mapping from kwargs to XML elements
    prop_map = {
        "title": f"{{{NS_DC}}}title",
        "author": f"{{{NS_DC}}}creator",
        "subject": f"{{{NS_DC}}}subject",
        "keywords": f"{{{NS_CP}}}keywords",
        "category": f"{{{NS_CP}}}category",
        "comments": f"{{{NS_DC}}}description",
        "last_modified_by": f"{{{NS_CP}}}lastModifiedBy",
    }

    for key, value in kwargs.items():
        if value is None:
            continue
        if key not in prop_map:
            raise ValueError(f"Unknown metadata key: {key}")

        tag = prop_map[key]
        el = core_xml.find(tag)
        if el is None:
            el = etree.SubElement(core_xml, tag)
        el.text = str(value)

    pkg.mark_xml_dirty("/docProps/core.xml")


# =============================================================================
# Custom Properties
# =============================================================================


def get_custom_properties(pkg: OpcPackage) -> list[dict]:
    """Get all custom document properties from docProps/custom.xml.

    Returns list of dicts with keys: name, value, type.
    Type is one of: "string", "int", "bool", "datetime", "float".
    """
    if not pkg.has_part("/docProps/custom.xml"):
        return []

    custom_xml = pkg.get_xml("/docProps/custom.xml")
    result = []

    for prop in custom_xml.findall(f"{{{NS_CUSTOM}}}property"):
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

        result.append({"name": name, "value": value, "type": prop_type})

    return result


def _ensure_custom_xml(pkg: OpcPackage) -> etree._Element:
    """Ensure docProps/custom.xml exists and return it.

    Creates the part with relationship and content type if missing.
    """
    if pkg.has_part("/docProps/custom.xml"):
        custom_xml = pkg.get_xml("/docProps/custom.xml")
        # Ensure relationship exists even if part exists
        pkg_rels = pkg.get_pkg_rels()
        if pkg_rels.rId_for_reltype(RT.CUSTOM_PROPERTIES) is None:
            pkg.relate_from_package("docProps/custom.xml", RT.CUSTOM_PROPERTIES)
        return custom_xml

    # Create new custom.xml
    custom_xml = etree.Element(
        f"{{{NS_CUSTOM}}}Properties",
        nsmap={None: NS_CUSTOM, "vt": NS_VT},
    )
    pkg.set_xml("/docProps/custom.xml", custom_xml, CT.OPC_CUSTOM_PROPERTIES)

    # Add package relationship
    pkg.relate_from_package("docProps/custom.xml", RT.CUSTOM_PROPERTIES)

    return custom_xml


def _format_datetime_value(value: datetime) -> str:
    """Format datetime value for filetime property.

    Args:
        value: Timezone-aware datetime object (required).

    Returns:
        UTC datetime string with Z suffix.

    Raises:
        TypeError: If value is not a datetime object.
        ValueError: If datetime is not timezone-aware.
    """
    if not isinstance(value, datetime):
        raise TypeError(
            f"filetime property requires datetime object, got {type(value).__name__}"
        )
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware for filetime property")
    # Convert to UTC and format with Z suffix
    utc_dt = value.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def set_custom_property(
    pkg: OpcPackage,
    name: str,
    value: str | datetime,
    prop_type: str = "lpwstr",
) -> None:
    """Set or update a custom document property.

    Args:
        pkg: OPC package
        name: Property name (must be unique)
        value: Property value (string for most types, datetime for filetime)
        prop_type: Property type - OOXML names: "lpwstr" (string), "i4" (int),
                   "bool", "filetime" (datetime), "r8" (float).
                   Also accepts user-friendly aliases: "string", "int", "datetime", "float".

    Raises:
        ValueError: If prop_type is not a recognized type.
        TypeError: If filetime type is used without a datetime object.
    """
    # Normalize type to OOXML element name
    if prop_type not in TYPE_MAP:
        raise ValueError(
            f"Unknown property type: {prop_type!r}. "
            f"Valid types: {', '.join(sorted(TYPE_MAP.keys()))}"
        )
    ooxml_type = TYPE_MAP[prop_type]
    value_tag = f"{{{NS_VT}}}{ooxml_type}"

    # Format value based on type
    if ooxml_type == "filetime":
        formatted_value = _format_datetime_value(value)
    else:
        formatted_value = str(value)

    custom_xml = _ensure_custom_xml(pkg)

    # Find existing property or calculate next pid
    existing = None
    max_pid = 1
    for prop in custom_xml.findall(f"{{{NS_CUSTOM}}}property"):
        pid_str = prop.get("pid", "1")
        if not pid_str.isdigit():
            prop_name = prop.get("name", "<unnamed>")
            raise ValueError(
                f"Malformed custom property pid '{pid_str}' on property '{prop_name}'"
            )
        pid = int(pid_str)
        if pid > max_pid:
            max_pid = pid
        if prop.get("name") == name:
            existing = prop

    if existing is not None:
        # Update existing property - remove old value element, preserve pid
        for child in list(existing):
            existing.remove(child)
        value_el = etree.SubElement(existing, value_tag)
        value_el.text = formatted_value
    else:
        # Add new property (pids start at 2)
        prop = etree.SubElement(custom_xml, f"{{{NS_CUSTOM}}}property")
        prop.set("fmtid", CUSTOM_PROPERTY_FMTID)
        prop.set("pid", str(max_pid + 1))
        prop.set("name", name)
        value_el = etree.SubElement(prop, value_tag)
        value_el.text = formatted_value

    pkg.mark_xml_dirty("/docProps/custom.xml")


def delete_custom_property(pkg: OpcPackage, name: str) -> None:
    """Delete a custom document property.

    Raises:
        KeyError: If property not found or custom.xml doesn't exist.
    """
    if not pkg.has_part("/docProps/custom.xml"):
        raise KeyError(f"Custom property not found: {name}")

    custom_xml = pkg.get_xml("/docProps/custom.xml")
    for prop in custom_xml.findall(f"{{{NS_CUSTOM}}}property"):
        if prop.get("name") == name:
            custom_xml.remove(prop)
            pkg.mark_xml_dirty("/docProps/custom.xml")
            return

    raise KeyError(f"Custom property not found: {name}")
