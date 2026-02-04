"""Document properties operations.

Contains functions for:
- Core properties (title, author, created, modified, revision)
- Custom properties (user-defined metadata in docProps/custom.xml)

Uses common helpers from microsoft.common.properties and returns Word-specific models.
"""

from __future__ import annotations

from mcp_handley_lab.microsoft.common.properties import (
    delete_custom_property as _delete_custom_property,
)
from mcp_handley_lab.microsoft.common.properties import (
    get_core_properties as _get_core_properties,
)
from mcp_handley_lab.microsoft.common.properties import (
    get_custom_properties as _get_custom_properties,
)
from mcp_handley_lab.microsoft.common.properties import (
    set_core_properties as _set_core_properties,
)
from mcp_handley_lab.microsoft.common.properties import (
    set_custom_property as _set_custom_property,
)
from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.models import CustomPropertyInfo, DocumentMeta

# =============================================================================
# Core Properties
# =============================================================================


def get_document_meta(pkg) -> DocumentMeta:
    """Extract document metadata from core properties and custom properties.

    Args:
        pkg: WordPackage
    """
    # Get core properties via common helper
    core = _get_core_properties(pkg)

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
        title=core["title"],
        author=core["author"],
        created=core["created"],
        modified=core["modified"],
        revision=core["revision"],
        sections=sections,
        custom_properties=custom_props,
    )


def set_document_meta(pkg, **kwargs) -> None:
    """Update document core properties. Only updates non-None values.

    Args:
        pkg: WordPackage
        **kwargs: Properties to update (title, author, subject, keywords, category, comments)
    """
    _set_core_properties(pkg, **kwargs)


# =============================================================================
# Custom Properties
# =============================================================================


def get_custom_properties(pkg) -> list[CustomPropertyInfo]:
    """Get all custom document properties from docProps/custom.xml.

    Args:
        pkg: WordPackage
    """
    props = _get_custom_properties(pkg)
    return [
        CustomPropertyInfo(name=p["name"], value=p["value"], type=p["type"])
        for p in props
    ]


def set_custom_property(pkg, name: str, value: str, prop_type: str = "string") -> None:
    """Set or update a custom document property.

    Args:
        pkg: WordPackage
        name: Property name (must be unique)
        value: Property value as string
        prop_type: One of "string", "int", "bool", "datetime", "float"
    """
    _set_custom_property(pkg, name, value, prop_type)


def delete_custom_property(pkg, name: str) -> None:
    """Delete a custom document property.

    Args:
        pkg: WordPackage
        name: Property name to delete

    Raises:
        KeyError: If property not found.
    """
    _delete_custom_property(pkg, name)
