"""Document property operations for Visio.

Thin wrappers around common property functions for use in the edit dispatcher.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp_handley_lab.microsoft.common.properties import (
    delete_custom_property as _delete_custom,
)
from mcp_handley_lab.microsoft.common.properties import (
    set_core_properties as _set_core,
)
from mcp_handley_lab.microsoft.common.properties import (
    set_custom_property as _set_custom,
)

if TYPE_CHECKING:
    from mcp_handley_lab.microsoft.visio.package import VisioPackage


def set_property(pkg: VisioPackage, name: str, value: str) -> None:
    """Set a core document property (title, author, etc.)."""
    _set_core(pkg, **{name: value})


def set_custom_property(
    pkg: VisioPackage, name: str, value: Any, prop_type: str = "string"
) -> None:
    """Set a custom document property."""
    _set_custom(pkg, name, value, prop_type)


def delete_custom_property(pkg: VisioPackage, name: str) -> None:
    """Delete a custom document property.

    Raises:
        KeyError: If property not found.
    """
    _delete_custom(pkg, name)
