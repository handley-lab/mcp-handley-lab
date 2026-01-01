"""Print settings operations for Excel.

Page setup, margins, print area, print titles, and page breaks.
"""

from __future__ import annotations

import re

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.ops.core import get_sheet_path as _get_sheet_path
from mcp_handley_lab.microsoft.excel.ops.core import insert_sheet_element
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def _get_sheet_local_id(pkg: ExcelPackage, sheet_name: str) -> int:
    """Get 0-based local sheet ID for use in definedNames."""
    for i, (name, _rId, _partname) in enumerate(pkg.get_sheet_paths()):
        if name == sheet_name:
            return i
    raise KeyError(f"Sheet not found: {sheet_name}")


def set_print_area(pkg: ExcelPackage, sheet_name: str, range_ref: str) -> None:
    """Set the print area for a sheet.

    Args:
        sheet_name: Name of the sheet.
        range_ref: Range reference (e.g., "A1:D10").
    """
    workbook = pkg.workbook_xml

    # Find or create definedNames element
    defined_names = workbook.find(qn("x:definedNames"))
    if defined_names is None:
        # Insert after sheets element
        sheets = workbook.find(qn("x:sheets"))
        if sheets is not None:
            idx = list(workbook).index(sheets)
            defined_names = etree.Element(qn("x:definedNames"))
            workbook.insert(idx + 1, defined_names)
        else:
            defined_names = etree.SubElement(workbook, qn("x:definedNames"))

    # Get local sheet ID
    local_sheet_id = _get_sheet_local_id(pkg, sheet_name)

    # Remove existing print area for this sheet
    for name_el in defined_names.findall(qn("x:definedName")):
        if name_el.get("name") == "_xlnm.Print_Area" and name_el.get(
            "localSheetId"
        ) == str(local_sheet_id):
            defined_names.remove(name_el)
            break

    # Create new print area definition
    # Format: 'SheetName'!$A$1:$D$10
    escaped_name = sheet_name.replace("'", "''")
    formula = f"'{escaped_name}'!{_make_absolute_ref(range_ref)}"

    name_el = etree.SubElement(
        defined_names,
        qn("x:definedName"),
        name="_xlnm.Print_Area",
        localSheetId=str(local_sheet_id),
    )
    name_el.text = formula

    pkg.mark_xml_dirty(pkg.workbook_path)


def get_print_area(pkg: ExcelPackage, sheet_name: str) -> str | None:
    """Get the print area for a sheet.

    Returns: Range reference string, or None if no print area set.
    """
    workbook = pkg.workbook_xml
    defined_names = workbook.find(qn("x:definedNames"))
    if defined_names is None:
        return None

    local_sheet_id = _get_sheet_local_id(pkg, sheet_name)

    for name_el in defined_names.findall(qn("x:definedName")):
        if name_el.get("name") == "_xlnm.Print_Area" and name_el.get(
            "localSheetId"
        ) == str(local_sheet_id):
            # Extract just the range part from 'SheetName'!$A$1:$D$10
            text = name_el.text or ""
            if "!" in text:
                return text.split("!", 1)[1]
            return text

    return None


def clear_print_area(pkg: ExcelPackage, sheet_name: str) -> None:
    """Clear the print area for a sheet."""
    workbook = pkg.workbook_xml
    defined_names = workbook.find(qn("x:definedNames"))
    if defined_names is None:
        return

    local_sheet_id = _get_sheet_local_id(pkg, sheet_name)

    for name_el in defined_names.findall(qn("x:definedName")):
        if name_el.get("name") == "_xlnm.Print_Area" and name_el.get(
            "localSheetId"
        ) == str(local_sheet_id):
            defined_names.remove(name_el)
            pkg.mark_xml_dirty(pkg.workbook_path)
            break


def set_print_titles(
    pkg: ExcelPackage,
    sheet_name: str,
    rows: str | None = None,
    cols: str | None = None,
) -> None:
    """Set print titles (rows/columns to repeat on each page).

    Args:
        sheet_name: Name of the sheet.
        rows: Row range to repeat (e.g., "1:2" for first two rows).
        cols: Column range to repeat (e.g., "A:B" for first two columns).
    """
    if not rows and not cols:
        clear_print_titles(pkg, sheet_name)
        return

    workbook = pkg.workbook_xml

    # Find or create definedNames element
    defined_names = workbook.find(qn("x:definedNames"))
    if defined_names is None:
        sheets = workbook.find(qn("x:sheets"))
        if sheets is not None:
            idx = list(workbook).index(sheets)
            defined_names = etree.Element(qn("x:definedNames"))
            workbook.insert(idx + 1, defined_names)
        else:
            defined_names = etree.SubElement(workbook, qn("x:definedNames"))

    local_sheet_id = _get_sheet_local_id(pkg, sheet_name)

    # Remove existing print titles for this sheet
    for name_el in defined_names.findall(qn("x:definedName")):
        if name_el.get("name") == "_xlnm.Print_Titles" and name_el.get(
            "localSheetId"
        ) == str(local_sheet_id):
            defined_names.remove(name_el)
            break

    # Build formula
    escaped_name = sheet_name.replace("'", "''")
    parts = []
    if rows:
        # Convert "1:2" to "'Sheet'!$1:$2"
        parts.append(f"'{escaped_name}'!${rows.replace(':', ':$')}")
    if cols:
        # Convert "A:B" to "'Sheet'!$A:$B"
        parts.append(f"'{escaped_name}'!${cols.replace(':', ':$')}")

    formula = ",".join(parts)

    name_el = etree.SubElement(
        defined_names,
        qn("x:definedName"),
        name="_xlnm.Print_Titles",
        localSheetId=str(local_sheet_id),
    )
    name_el.text = formula

    pkg.mark_xml_dirty(pkg.workbook_path)


def get_print_titles(pkg: ExcelPackage, sheet_name: str) -> dict | None:
    """Get print titles for a sheet.

    Returns: Dictionary with 'rows' and 'cols' keys, or None if not set.
    """
    workbook = pkg.workbook_xml
    defined_names = workbook.find(qn("x:definedNames"))
    if defined_names is None:
        return None

    local_sheet_id = _get_sheet_local_id(pkg, sheet_name)

    for name_el in defined_names.findall(qn("x:definedName")):
        if name_el.get("name") == "_xlnm.Print_Titles" and name_el.get(
            "localSheetId"
        ) == str(local_sheet_id):
            text = name_el.text or ""
            result = {"rows": None, "cols": None}

            # Parse formula like "'Sheet'!$1:$2,'Sheet'!$A:$B"
            for part in text.split(","):
                if "!" in part:
                    ref = part.split("!", 1)[1].replace("$", "")
                    # Check if row range (digits only) or column range (letters only)
                    if ref and ref[0].isdigit():
                        result["rows"] = ref
                    elif ref and ref[0].isalpha():
                        result["cols"] = ref

            return result

    return None


def clear_print_titles(pkg: ExcelPackage, sheet_name: str) -> None:
    """Clear print titles for a sheet."""
    workbook = pkg.workbook_xml
    defined_names = workbook.find(qn("x:definedNames"))
    if defined_names is None:
        return

    local_sheet_id = _get_sheet_local_id(pkg, sheet_name)

    for name_el in defined_names.findall(qn("x:definedName")):
        if name_el.get("name") == "_xlnm.Print_Titles" and name_el.get(
            "localSheetId"
        ) == str(local_sheet_id):
            defined_names.remove(name_el)
            pkg.mark_xml_dirty(pkg.workbook_path)
            break


def set_page_margins(
    pkg: ExcelPackage,
    sheet_name: str,
    left: float | None = None,
    right: float | None = None,
    top: float | None = None,
    bottom: float | None = None,
    header: float | None = None,
    footer: float | None = None,
) -> None:
    """Set page margins for a sheet.

    Args:
        sheet_name: Name of the sheet.
        left: Left margin in inches.
        right: Right margin in inches.
        top: Top margin in inches.
        bottom: Bottom margin in inches.
        header: Header margin in inches.
        footer: Footer margin in inches.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    # Find or create pageMargins at correct position
    margins = sheet_xml.find(qn("x:pageMargins"))
    if margins is None:
        margins = etree.Element(qn("x:pageMargins"))
        # Set defaults if creating new element
        margins.set("left", "0.7")
        margins.set("right", "0.7")
        margins.set("top", "0.75")
        margins.set("bottom", "0.75")
        margins.set("header", "0.3")
        margins.set("footer", "0.3")
        insert_sheet_element(sheet_xml, "pageMargins", margins)

    # Update specified margins
    if left is not None:
        margins.set("left", str(left))
    if right is not None:
        margins.set("right", str(right))
    if top is not None:
        margins.set("top", str(top))
    if bottom is not None:
        margins.set("bottom", str(bottom))
    if header is not None:
        margins.set("header", str(header))
    if footer is not None:
        margins.set("footer", str(footer))

    pkg.mark_xml_dirty(sheet_path)


def get_page_margins(pkg: ExcelPackage, sheet_name: str) -> dict | None:
    """Get page margins for a sheet.

    Returns: Dictionary of margins, or None if not set.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    margins = sheet_xml.find(qn("x:pageMargins"))
    if margins is None:
        return None

    return {
        "left": float(margins.get("left", "0.7")),
        "right": float(margins.get("right", "0.7")),
        "top": float(margins.get("top", "0.75")),
        "bottom": float(margins.get("bottom", "0.75")),
        "header": float(margins.get("header", "0.3")),
        "footer": float(margins.get("footer", "0.3")),
    }


def set_page_orientation(
    pkg: ExcelPackage, sheet_name: str, landscape: bool = False
) -> None:
    """Set page orientation for a sheet.

    Args:
        sheet_name: Name of the sheet.
        landscape: True for landscape, False for portrait.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    # Find or create pageSetup at correct position
    page_setup = sheet_xml.find(qn("x:pageSetup"))
    if page_setup is None:
        page_setup = etree.Element(qn("x:pageSetup"))
        insert_sheet_element(sheet_xml, "pageSetup", page_setup)

    page_setup.set("orientation", "landscape" if landscape else "portrait")

    pkg.mark_xml_dirty(sheet_path)


def get_page_orientation(pkg: ExcelPackage, sheet_name: str) -> str:
    """Get page orientation for a sheet.

    Returns: "portrait" or "landscape".
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    page_setup = sheet_xml.find(qn("x:pageSetup"))
    if page_setup is None:
        return "portrait"

    return page_setup.get("orientation", "portrait")


def set_page_size(pkg: ExcelPackage, sheet_name: str, paper_size: int) -> None:
    """Set page/paper size for a sheet.

    Args:
        sheet_name: Name of the sheet.
        paper_size: Paper size code (1=Letter, 9=A4, 5=Legal, etc.)

    Common paper sizes:
        1 = Letter (8.5" x 11")
        5 = Legal (8.5" x 14")
        9 = A4 (210mm x 297mm)
        11 = A5 (148mm x 210mm)
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    page_setup = sheet_xml.find(qn("x:pageSetup"))
    if page_setup is None:
        page_setup = etree.Element(qn("x:pageSetup"))
        insert_sheet_element(sheet_xml, "pageSetup", page_setup)

    page_setup.set("paperSize", str(paper_size))

    pkg.mark_xml_dirty(sheet_path)


def get_page_size(pkg: ExcelPackage, sheet_name: str) -> int:
    """Get paper size for a sheet.

    Returns: Paper size code (1=Letter, 9=A4).
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    page_setup = sheet_xml.find(qn("x:pageSetup"))
    if page_setup is None:
        return 1  # Default to Letter

    return int(page_setup.get("paperSize", "1"))


def set_scale(pkg: ExcelPackage, sheet_name: str, scale: int) -> None:
    """Set print scale percentage.

    Args:
        sheet_name: Name of the sheet.
        scale: Scale percentage (10-400).
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    page_setup = sheet_xml.find(qn("x:pageSetup"))
    if page_setup is None:
        page_setup = etree.Element(qn("x:pageSetup"))
        insert_sheet_element(sheet_xml, "pageSetup", page_setup)

    # Remove fit-to-page settings when setting explicit scale
    page_setup.attrib.pop("fitToWidth", None)
    page_setup.attrib.pop("fitToHeight", None)

    page_setup.set("scale", str(max(10, min(400, scale))))

    pkg.mark_xml_dirty(sheet_path)


def set_fit_to_page(
    pkg: ExcelPackage,
    sheet_name: str,
    width: int | None = 1,
    height: int | None = 0,
) -> None:
    """Set fit-to-page printing.

    Args:
        sheet_name: Name of the sheet.
        width: Number of pages wide (0 = as many as needed).
        height: Number of pages tall (0 = as many as needed).
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    page_setup = sheet_xml.find(qn("x:pageSetup"))
    if page_setup is None:
        page_setup = etree.Element(qn("x:pageSetup"))
        insert_sheet_element(sheet_xml, "pageSetup", page_setup)

    # Remove scale when using fit-to-page
    page_setup.attrib.pop("scale", None)

    if width is not None:
        page_setup.set("fitToWidth", str(width))
    if height is not None:
        page_setup.set("fitToHeight", str(height))

    pkg.mark_xml_dirty(sheet_path)


def get_scale(pkg: ExcelPackage, sheet_name: str) -> int | None:
    """Get print scale percentage.

    Returns: Scale percentage, or None if not set (or using fit-to-page).
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    page_setup = sheet_xml.find(qn("x:pageSetup"))
    if page_setup is None:
        return None

    scale = page_setup.get("scale")
    return int(scale) if scale else None


def get_fit_to_page(pkg: ExcelPackage, sheet_name: str) -> dict | None:
    """Get fit-to-page settings.

    Returns: Dictionary with 'width' and 'height' keys, or None if not set.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    page_setup = sheet_xml.find(qn("x:pageSetup"))
    if page_setup is None:
        return None

    fit_width = page_setup.get("fitToWidth")
    fit_height = page_setup.get("fitToHeight")

    if fit_width is None and fit_height is None:
        return None

    return {
        "width": int(fit_width) if fit_width else None,
        "height": int(fit_height) if fit_height else None,
    }


def add_row_page_break(pkg: ExcelPackage, sheet_name: str, row: int) -> None:
    """Add a horizontal page break before a row.

    Args:
        sheet_name: Name of the sheet.
        row: Row number (1-based) where break occurs before.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    row_breaks = sheet_xml.find(qn("x:rowBreaks"))
    if row_breaks is None:
        row_breaks = etree.Element(qn("x:rowBreaks"))
        row_breaks.set("count", "0")
        row_breaks.set("manualBreakCount", "0")
        insert_sheet_element(sheet_xml, "rowBreaks", row_breaks)

    # Check if break already exists
    for brk in row_breaks.findall(qn("x:brk")):
        if int(brk.get("id", "0")) == row:
            return  # Break already exists

    # Add break
    brk = etree.SubElement(row_breaks, qn("x:brk"))
    brk.set("id", str(row))
    brk.set("max", "16383")  # Maximum column
    brk.set("man", "1")  # Manual break

    # Update counts
    count = len(row_breaks.findall(qn("x:brk")))
    row_breaks.set("count", str(count))
    row_breaks.set("manualBreakCount", str(count))

    pkg.mark_xml_dirty(sheet_path)


def add_column_page_break(pkg: ExcelPackage, sheet_name: str, col: int) -> None:
    """Add a vertical page break before a column.

    Args:
        sheet_name: Name of the sheet.
        col: Column number (1-based, e.g., 1=A, 2=B) where break occurs before.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    col_breaks = sheet_xml.find(qn("x:colBreaks"))
    if col_breaks is None:
        col_breaks = etree.Element(qn("x:colBreaks"))
        col_breaks.set("count", "0")
        col_breaks.set("manualBreakCount", "0")
        insert_sheet_element(sheet_xml, "colBreaks", col_breaks)

    # Check if break already exists
    for brk in col_breaks.findall(qn("x:brk")):
        if int(brk.get("id", "0")) == col:
            return  # Break already exists

    # Add break
    brk = etree.SubElement(col_breaks, qn("x:brk"))
    brk.set("id", str(col))
    brk.set("max", "1048575")  # Maximum row
    brk.set("man", "1")  # Manual break

    # Update counts
    count = len(col_breaks.findall(qn("x:brk")))
    col_breaks.set("count", str(count))
    col_breaks.set("manualBreakCount", str(count))

    pkg.mark_xml_dirty(sheet_path)


def remove_row_page_break(pkg: ExcelPackage, sheet_name: str, row: int) -> None:
    """Remove a horizontal page break before a row.

    Args:
        sheet_name: Name of the sheet.
        row: Row number (1-based) where break was set.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    row_breaks = sheet_xml.find(qn("x:rowBreaks"))
    if row_breaks is None:
        return

    for brk in row_breaks.findall(qn("x:brk")):
        if int(brk.get("id", "0")) == row:
            row_breaks.remove(brk)

            # Update counts
            count = len(row_breaks.findall(qn("x:brk")))
            row_breaks.set("count", str(count))
            row_breaks.set("manualBreakCount", str(count))

            # Remove empty rowBreaks element
            if count == 0:
                sheet_xml.remove(row_breaks)

            pkg.mark_xml_dirty(sheet_path)
            return


def remove_column_page_break(pkg: ExcelPackage, sheet_name: str, col: int) -> None:
    """Remove a vertical page break before a column.

    Args:
        sheet_name: Name of the sheet.
        col: Column number (1-based) where break was set.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    col_breaks = sheet_xml.find(qn("x:colBreaks"))
    if col_breaks is None:
        return

    for brk in col_breaks.findall(qn("x:brk")):
        if int(brk.get("id", "0")) == col:
            col_breaks.remove(brk)

            # Update counts
            count = len(col_breaks.findall(qn("x:brk")))
            col_breaks.set("count", str(count))
            col_breaks.set("manualBreakCount", str(count))

            # Remove empty colBreaks element
            if count == 0:
                sheet_xml.remove(col_breaks)

            pkg.mark_xml_dirty(sheet_path)
            return


def list_page_breaks(pkg: ExcelPackage, sheet_name: str) -> dict:
    """List all page breaks for a sheet.

    Returns: Dictionary with 'rows' and 'cols' lists of break positions.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)

    result = {"rows": [], "cols": []}

    row_breaks = sheet_xml.find(qn("x:rowBreaks"))
    if row_breaks is not None:
        for brk in row_breaks.findall(qn("x:brk")):
            result["rows"].append(int(brk.get("id", "0")))

    col_breaks = sheet_xml.find(qn("x:colBreaks"))
    if col_breaks is not None:
        for brk in col_breaks.findall(qn("x:brk")):
            result["cols"].append(int(brk.get("id", "0")))

    return result


def clear_page_breaks(pkg: ExcelPackage, sheet_name: str) -> None:
    """Clear all page breaks for a sheet."""
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    sheet_path = _get_sheet_path(pkg, sheet_name)

    for el_name in ["rowBreaks", "colBreaks"]:
        el = sheet_xml.find(qn(f"x:{el_name}"))
        if el is not None:
            sheet_xml.remove(el)
            pkg.mark_xml_dirty(sheet_path)


def _make_absolute_ref(range_ref: str) -> str:
    """Convert a range reference to absolute format (add $ signs).

    Examples:
        A1 -> $A$1
        A1:B2 -> $A$1:$B$2
        A:B -> $A:$B
        1:2 -> $1:$2
    """

    def add_dollars(cell_ref: str) -> str:
        # Handle row-only (1:2) or column-only (A:B) references
        if cell_ref.isdigit():
            return f"${cell_ref}"

        # Handle column-only
        if cell_ref.isalpha():
            return f"${cell_ref}"

        # Handle full cell reference like A1
        match = re.match(r"^([A-Za-z]+)(\d+)$", cell_ref)
        if match:
            return f"${match.group(1)}${match.group(2)}"

        return cell_ref

    if ":" in range_ref:
        start, end = range_ref.split(":", 1)
        return f"{add_dollars(start)}:{add_dollars(end)}"
    return add_dollars(range_ref)
