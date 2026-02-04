"""Named range operations for Excel.

Named ranges (defined names) allow assigning names to cell references or formulas.
Names can be global (workbook-scoped) or local (sheet-scoped).
"""

from __future__ import annotations

import hashlib

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.models import NameInfo
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def _make_name_id(name: str, scope: str | None = None) -> str:
    """Generate content-addressed ID for a named range."""
    content = f"{name}:{scope or 'global'}"
    hash_val = hashlib.sha1(content.encode()).hexdigest()[:8]
    safe_name = name.replace(" ", "_")
    return f"name_{safe_name}_{hash_val}"


def _get_sheet_index(pkg: ExcelPackage, sheet_name: str) -> int:
    """Get 0-based sheet index by name."""
    for idx, (name, _rId, _partname) in enumerate(pkg.get_sheet_paths()):
        if name == sheet_name:
            return idx
    raise KeyError(f"Sheet not found: {sheet_name}")


def _get_sheet_name_by_index(pkg: ExcelPackage, idx: int) -> str:
    """Get sheet name by 0-based index."""
    return pkg.get_sheet_paths()[idx][0]


def list_names(pkg: ExcelPackage) -> list[NameInfo]:
    """List all defined names in the workbook.

    Returns: List of NameInfo for each defined name.
    """
    workbook = pkg.workbook_xml
    defined_names = workbook.find(qn("x:definedNames"))
    if defined_names is None:
        return []

    result = []
    for dn in defined_names.findall(qn("x:definedName")):
        name = dn.get("name", "")
        refers_to = dn.text or ""

        # Determine scope
        scope = None
        local_sheet_id = dn.get("localSheetId")
        if local_sheet_id is not None:
            if not local_sheet_id.isdigit():
                raise ValueError(
                    f"Invalid localSheetId '{local_sheet_id}' for definedName '{name}'"
                )
            scope = _get_sheet_name_by_index(pkg, int(local_sheet_id))

        comment = dn.get("comment")

        result.append(
            NameInfo(
                id=_make_name_id(name, scope),
                name=name,
                refers_to=refers_to,
                scope=scope,
                comment=comment,
            )
        )

    return result


def get_name(pkg: ExcelPackage, name: str, scope: str | None = None) -> NameInfo:
    """Get a defined name by name and optional scope.

    Args:
        pkg: Excel package.
        name: The defined name to look up.
        scope: Sheet name for local scope, or None for global.

    Returns: NameInfo for the matched name.
    Raises: KeyError if name not found.
    """
    for info in list_names(pkg):
        if info.name == name and info.scope == scope:
            return info
    scope_desc = f"in scope '{scope}'" if scope else "(global)"
    raise KeyError(f"Name not found: {name} {scope_desc}")


def create_name(
    pkg: ExcelPackage,
    name: str,
    refers_to: str,
    scope: str | None = None,
    comment: str | None = None,
) -> NameInfo:
    """Create a new defined name.

    Args:
        pkg: Excel package.
        name: Name to create (e.g., "MyRange", "TaxRate").
        refers_to: Formula or reference (e.g., "'Sheet1'!$A$1:$A$10", "=100*0.07").
        scope: Sheet name for local scope, or None for global (workbook) scope.
        comment: Optional comment/description for the name.

    Returns: NameInfo for the created name.
    """
    workbook = pkg.workbook_xml
    defined_names = workbook.find(qn("x:definedNames"))
    if defined_names is None:
        # Create definedNames element - should be after sheets, before calcPr
        defined_names = etree.Element(qn("x:definedNames"))
        sheets = workbook.find(qn("x:sheets"))
        if sheets is not None:
            idx = list(workbook).index(sheets) + 1
            workbook.insert(idx, defined_names)
        else:
            workbook.append(defined_names)

    # Create the definedName element
    dn = etree.SubElement(defined_names, qn("x:definedName"))
    dn.set("name", name)
    dn.text = refers_to

    if scope is not None:
        sheet_idx = _get_sheet_index(pkg, scope)
        dn.set("localSheetId", str(sheet_idx))

    if comment:
        dn.set("comment", comment)

    pkg.mark_xml_dirty(pkg.workbook_path)

    return NameInfo(
        id=_make_name_id(name, scope),
        name=name,
        refers_to=refers_to,
        scope=scope,
        comment=comment,
    )


def update_name(
    pkg: ExcelPackage,
    name: str,
    refers_to: str | None = None,
    scope: str | None = None,
    comment: str | None = None,
) -> NameInfo:
    """Update an existing defined name.

    Args:
        pkg: Excel package.
        name: Name to update.
        refers_to: New formula/reference (if provided).
        scope: Sheet name for local scope, or None for global.
        comment: New comment (if provided, use "" to clear).

    Returns: Updated NameInfo.
    Raises: KeyError if name not found.
    """
    workbook = pkg.workbook_xml
    defined_names = workbook.find(qn("x:definedNames"))
    if defined_names is None:
        raise KeyError(f"Name not found: {name}")

    # Find the name element
    target_sheet_id = None
    if scope is not None:
        target_sheet_id = str(_get_sheet_index(pkg, scope))

    for dn in defined_names.findall(qn("x:definedName")):
        if dn.get("name") != name:
            continue

        local_id = dn.get("localSheetId")
        if target_sheet_id is None and local_id is None:
            # Global match
            pass
        elif target_sheet_id is not None and local_id == target_sheet_id:
            # Local match
            pass
        else:
            continue

        # Found the match - update it
        if refers_to is not None:
            dn.text = refers_to

        if comment is not None:
            if comment:
                dn.set("comment", comment)
            elif "comment" in dn.attrib:
                del dn.attrib["comment"]

        pkg.mark_xml_dirty(pkg.workbook_path)

        return NameInfo(
            id=_make_name_id(name, scope),
            name=name,
            refers_to=dn.text or "",
            scope=scope,
            comment=dn.get("comment"),
        )

    scope_desc = f"in scope '{scope}'" if scope else "(global)"
    raise KeyError(f"Name not found: {name} {scope_desc}")


def delete_name(pkg: ExcelPackage, name: str, scope: str | None = None) -> None:
    """Delete a defined name.

    Args:
        pkg: Excel package.
        name: Name to delete.
        scope: Sheet name for local scope, or None for global.

    Raises: KeyError if name not found.
    """
    workbook = pkg.workbook_xml
    defined_names = workbook.find(qn("x:definedNames"))
    if defined_names is None:
        raise KeyError(f"Name not found: {name}")

    # Find the name element
    target_sheet_id = None
    if scope is not None:
        target_sheet_id = str(_get_sheet_index(pkg, scope))

    for dn in defined_names.findall(qn("x:definedName")):
        if dn.get("name") != name:
            continue

        local_id = dn.get("localSheetId")
        if target_sheet_id is None and local_id is None:
            # Global match
            pass
        elif target_sheet_id is not None and local_id == target_sheet_id:
            # Local match
            pass
        else:
            continue

        # Found the match - delete it
        defined_names.remove(dn)

        # Remove empty definedNames element
        if len(defined_names) == 0:
            workbook.remove(defined_names)

        pkg.mark_xml_dirty(pkg.workbook_path)
        return

    scope_desc = f"in scope '{scope}'" if scope else "(global)"
    raise KeyError(f"Name not found: {name} {scope_desc}")
