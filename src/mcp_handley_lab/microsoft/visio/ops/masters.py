"""Master shape listing and resolution for Visio."""

from __future__ import annotations

from mcp_handley_lab.microsoft.visio.constants import findall_v
from mcp_handley_lab.microsoft.visio.models import MasterInfo
from mcp_handley_lab.microsoft.visio.package import VisioPackage


def resolve_master_name(pkg: VisioPackage) -> dict[int, str]:
    """Build mapping of master ID -> name from masters.xml.

    Returns empty dict if no masters are present.
    """
    masters_xml = pkg.get_masters_xml()
    if masters_xml is None:
        return {}

    result = {}
    for master_el in findall_v(masters_xml, "Master"):
        master_id_str = master_el.get("ID")
        if master_id_str is None:
            continue
        master_id = int(master_id_str)
        # Prefer NameU (universal), fall back to Name
        name = master_el.get("NameU") or master_el.get("Name")
        if name:
            result[master_id] = name

    return result


def list_masters(pkg: VisioPackage) -> list[MasterInfo]:
    """List all master shapes in the document.

    Returns MasterInfo for each master with ID, name, and shape count.
    """
    masters_xml = pkg.get_masters_xml()
    if masters_xml is None:
        return []

    master_paths = pkg.get_master_paths()
    path_by_id = {mid: partname for mid, _rid, partname in master_paths}

    results = []
    for master_el in findall_v(masters_xml, "Master"):
        master_id_str = master_el.get("ID")
        if master_id_str is None:
            continue
        master_id = int(master_id_str)

        name = master_el.get("Name")
        name_u = master_el.get("NameU")
        icon_size = master_el.get("IconSize")

        # Count shapes in master page
        shape_count = 0
        if master_id in path_by_id:
            master_xml = pkg.get_xml(path_by_id[master_id])
            shapes = findall_v(master_xml, "Shapes")
            if shapes:
                shape_count = len(findall_v(shapes[0], "Shape"))

        results.append(
            MasterInfo(
                master_id=master_id,
                name=name,
                name_u=name_u,
                icon_size=icon_size,
                shape_count=shape_count,
            )
        )

    return results
