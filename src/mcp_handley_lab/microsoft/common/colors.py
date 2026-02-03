"""Color parsing utilities for Office theme colors.

Parses DrawingML color scheme elements to extract base theme colors.
"""

from __future__ import annotations

from lxml import etree

# DrawingML namespace
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _qn(tag: str) -> str:
    """Qualify tag with DrawingML namespace."""
    return f"{{{NS_A}}}{tag}"


def _extract_color_value(color_el: etree._Element) -> str | None:
    """Extract hex color value from a color element.

    Handles:
    - a:srgbClr val="RRGGBB"
    - a:sysClr lastClr="RRGGBB"

    Returns: Hex color string like "RRGGBB" or None if not found.
    """
    # Try srgbClr first (explicit RGB)
    srgb = color_el.find(_qn("srgbClr"))
    if srgb is not None:
        val = srgb.get("val")
        if val:
            return val.upper()

    # Try sysClr (system color with cached value)
    sys_clr = color_el.find(_qn("sysClr"))
    if sys_clr is not None:
        # lastClr contains the resolved color value
        last_clr = sys_clr.get("lastClr")
        if last_clr:
            return last_clr.upper()
        # Fallback to val which is the system color name
        # (we can't resolve system colors without Windows API)

    return None


def parse_theme_colors(theme_xml: etree._Element) -> dict[str, str]:
    """Parse theme colors from a DrawingML theme element.

    Args:
        theme_xml: Root element of theme1.xml (a:theme)

    Returns:
        Dict mapping color scheme names to hex values:
        {
            "dk1": "000000",      # Dark 1 (typically black/dark text)
            "lt1": "FFFFFF",      # Light 1 (typically white/light background)
            "dk2": "1F497D",      # Dark 2 (accent dark)
            "lt2": "EEECE1",      # Light 2 (accent light)
            "accent1": "4F81BD",  # Accent 1
            "accent2": "C0504D",  # Accent 2
            "accent3": "9BBB59",  # Accent 3
            "accent4": "8064A2",  # Accent 4
            "accent5": "4BACC6",  # Accent 5
            "accent6": "F79646",  # Accent 6
            "hlink": "0000FF",    # Hyperlink
            "folHlink": "800080", # Followed hyperlink
        }
    """
    result: dict[str, str] = {}

    # Navigate to a:themeElements/a:clrScheme
    theme_elements = theme_xml.find(_qn("themeElements"))
    if theme_elements is None:
        return result

    clr_scheme = theme_elements.find(_qn("clrScheme"))
    if clr_scheme is None:
        return result

    # Standard color scheme element names
    color_names = [
        "dk1",
        "lt1",
        "dk2",
        "lt2",
        "accent1",
        "accent2",
        "accent3",
        "accent4",
        "accent5",
        "accent6",
        "hlink",
        "folHlink",
    ]

    for color_name in color_names:
        color_el = clr_scheme.find(_qn(color_name))
        if color_el is not None:
            hex_val = _extract_color_value(color_el)
            if hex_val:
                result[color_name] = hex_val

    return result


def get_theme_colors_from_package(
    pkg, main_part_path: str, theme_rel_type: str
) -> dict[str, str]:
    """Get theme colors from a package by following relationships.

    Args:
        pkg: OpcPackage instance (Word, PowerPoint, Excel)
        main_part_path: Path to main document (e.g., /ppt/presentation.xml)
        theme_rel_type: Relationship type for theme

    Returns:
        Dict of color scheme name -> hex value, or empty dict if no theme.
    """
    rels = pkg.get_rels(main_part_path)
    rid = rels.rId_for_reltype(theme_rel_type)
    if rid is None:
        return {}

    theme_path = pkg.resolve_rel_target(main_part_path, rid)
    theme_xml = pkg.get_xml(theme_path)
    return parse_theme_colors(theme_xml)
