"""Core utilities for Visio operations.

Cell extraction, section parsing, and shape key management.
All XML lookups use find_v/findall_v for dual-namespace compatibility.
"""

from __future__ import annotations

from typing import Any

from lxml import etree

from mcp_handley_lab.microsoft.visio.constants import find_v, findall_v


def get_cell_value(parent: etree._Element, cell_name: str) -> str | None:
    """Get the V (value) attribute of a singleton Cell by name.

    Searches for <Cell N="cell_name"> under parent and returns its V attribute.
    """
    for cell in findall_v(parent, "Cell"):
        if cell.get("N") == cell_name:
            return cell.get("V")
    return None


def get_cell_formula(parent: etree._Element, cell_name: str) -> str | None:
    """Get the F (formula) attribute of a singleton Cell by name."""
    for cell in findall_v(parent, "Cell"):
        if cell.get("N") == cell_name:
            return cell.get("F")
    return None


def get_cell_unit(parent: etree._Element, cell_name: str) -> str | None:
    """Get the U (unit) attribute of a singleton Cell by name."""
    for cell in findall_v(parent, "Cell"):
        if cell.get("N") == cell_name:
            return cell.get("U")
    return None


def get_all_cells(parent: etree._Element) -> list[dict[str, str | None]]:
    """Get all singleton Cell elements under parent.

    Returns list of dicts with keys: name, value, formula, unit.
    """
    results = []
    for cell in findall_v(parent, "Cell"):
        results.append(
            {
                "name": cell.get("N"),
                "value": cell.get("V"),
                "formula": cell.get("F"),
                "unit": cell.get("U"),
            }
        )
    return results


def get_section_rows(parent: etree._Element, section_name: str) -> list[dict[str, Any]]:
    """Get all rows from a named Section.

    Returns list of row dicts, each with:
    - index: Row IX attribute (int or None)
    - name: Row N attribute (str or None)
    - cells: dict mapping cell N -> {value, formula, unit}
    """
    results = []
    for section in findall_v(parent, "Section"):
        if section.get("N") != section_name:
            continue
        for row in findall_v(section, "Row"):
            row_data: dict[str, Any] = {
                "index": int(row.get("IX")) if row.get("IX") else None,
                "name": row.get("N"),
                "cells": {},
            }
            for cell in findall_v(row, "Cell"):
                cell_name = cell.get("N")
                if cell_name:
                    row_data["cells"][cell_name] = {
                        "value": cell.get("V"),
                        "formula": cell.get("F"),
                        "unit": cell.get("U"),
                    }
            results.append(row_data)
    return results


def get_cell_float(parent: etree._Element, cell_name: str) -> float | None:
    """Get cell value as float, returning None if cell missing.

    Raises ValueError if cell exists but value is not numeric.
    """
    val = get_cell_value(parent, cell_name)
    if val is None:
        return None
    return float(val)  # Let ValueError propagate for malformed data


def make_shape_key(page_num: int, shape_id: int) -> str:
    """Create shape key for targeting: page_num:shape_id."""
    return f"{page_num}:{shape_id}"


def parse_shape_key(shape_key: str) -> tuple[int, int]:
    """Parse shape key into (page_num, shape_id)."""
    parts = shape_key.split(":")
    return (int(parts[0]), int(parts[1]))


def extract_shape_text(shape_el: etree._Element) -> str | None:
    """Extract plain text from a shape's Text element.

    Visio shapes store text in <Text><cp/><tp/>characters...</Text>.
    Text content is the concatenation of all text nodes (tail text of child
    elements + direct text of the Text element).
    """
    text_el = find_v(shape_el, "Text")
    if text_el is None:
        return None

    # Collect all text: the element's own text + tail text of children
    parts = []
    if text_el.text:
        parts.append(text_el.text)
    for child in text_el:
        if child.tail:
            parts.append(child.tail)

    text = "".join(parts).strip()
    return text if text else None
