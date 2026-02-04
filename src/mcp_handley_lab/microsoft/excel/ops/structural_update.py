"""Structural update operations for Excel.

Updates dependent structures when rows/columns are inserted or deleted:
- AutoFilter references
- ConditionalFormatting sqref
- DataValidation sqref
- Dimension ref
- Tables (ref and autoFilter ref)
- Defined names (formulas)
- Charts (series formulas)
- Pivot table cache source references
"""

from __future__ import annotations

import re

from mcp_handley_lab.microsoft.excel.constants import RT, qn
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index,
    make_cell_ref,
    parse_cell_ref,
    parse_range_ref,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    get_sheet_path as _get_sheet_path,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage

# Chart namespace
_NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"


def _qn_c(tag: str) -> str:
    """Clark notation for chart namespace."""
    return f"{{{_NS_C}}}{tag}"


def update_dependent_structures_after_insert(
    pkg: ExcelPackage,
    sheet_name: str,
    index: int,
    count: int,
    is_row: bool,
) -> None:
    """Update dependent structures after row/column insertion.

    Args:
        pkg: Excel package
        sheet_name: Sheet where insertion occurred
        index: 1-based row/column index where insertion started
        count: Number of rows/columns inserted
        is_row: True for row insertion, False for column insertion
    """
    _update_sheet_structures(pkg, sheet_name, index, count, is_row, is_delete=False)
    _update_tables(pkg, sheet_name, index, count, is_row, is_delete=False)
    _update_defined_names(pkg, sheet_name, index, count, is_row, is_delete=False)
    _update_charts(pkg, sheet_name, index, count, is_row, is_delete=False)
    _update_pivot_cache_refs(pkg, sheet_name, index, count, is_row, is_delete=False)


def update_dependent_structures_after_delete(
    pkg: ExcelPackage,
    sheet_name: str,
    index: int,
    count: int,
    is_row: bool,
) -> None:
    """Update dependent structures after row/column deletion.

    Args:
        pkg: Excel package
        sheet_name: Sheet where deletion occurred
        index: 1-based row/column index where deletion started
        count: Number of rows/columns deleted
        is_row: True for row deletion, False for column deletion
    """
    _update_sheet_structures(pkg, sheet_name, index, count, is_row, is_delete=True)
    _update_tables(pkg, sheet_name, index, count, is_row, is_delete=True)
    _update_defined_names(pkg, sheet_name, index, count, is_row, is_delete=True)
    _update_charts(pkg, sheet_name, index, count, is_row, is_delete=True)
    _update_pivot_cache_refs(pkg, sheet_name, index, count, is_row, is_delete=True)


def _shift_range_ref(
    range_ref: str,
    index: int,
    count: int,
    is_row: bool,
    is_delete: bool,
) -> str | None:
    """Shift a range reference after insert/delete.

    Returns updated ref, or None if range is completely deleted.

    Raises:
        ValueError: If range_ref is malformed.
    """
    start_ref, end_ref = parse_range_ref(range_ref)

    s_col, s_row, s_col_abs, s_row_abs = parse_cell_ref(start_ref)
    e_col, e_row, e_col_abs, e_row_abs = parse_cell_ref(end_ref)

    s_col_idx = column_letter_to_index(s_col)
    e_col_idx = column_letter_to_index(e_col)

    if is_row:
        if is_delete:
            # Check if range is completely within deleted rows
            if s_row >= index and e_row < index + count:
                return None  # Entire range deleted
            # Shift start if at or after deletion
            if s_row >= index + count:
                s_row -= count
            elif s_row >= index:
                s_row = index  # Range starts in deleted area
            # Shift end if after deletion
            if e_row >= index + count:
                e_row -= count
            elif e_row >= index:
                e_row = max(s_row, index - 1)  # Truncate to before deleted area
        else:
            # Insert: shift if at or after insertion point
            if s_row >= index:
                s_row += count
            if e_row >= index:
                e_row += count
    else:
        if is_delete:
            # Check if range is completely within deleted columns
            if s_col_idx >= index and e_col_idx < index + count:
                return None  # Entire range deleted
            # Shift start if at or after deletion
            if s_col_idx >= index + count:
                s_col_idx -= count
            elif s_col_idx >= index:
                s_col_idx = index  # Range starts in deleted area
            # Shift end if after deletion
            if e_col_idx >= index + count:
                e_col_idx -= count
            elif e_col_idx >= index:
                e_col_idx = max(s_col_idx, index - 1)  # Truncate
        else:
            # Insert: shift if at or after insertion point
            if s_col_idx >= index:
                s_col_idx += count
            if e_col_idx >= index:
                e_col_idx += count

    # Rebuild reference
    new_start = make_cell_ref(s_col_idx, s_row, col_abs=s_col_abs, row_abs=s_row_abs)
    new_end = make_cell_ref(e_col_idx, e_row, col_abs=e_col_abs, row_abs=e_row_abs)
    return f"{new_start}:{new_end}"


def _shift_sqref(
    sqref: str,
    index: int,
    count: int,
    is_row: bool,
    is_delete: bool,
) -> str | None:
    """Shift a sqref (space-separated list of ranges) after insert/delete.

    Returns updated sqref, or None if all ranges deleted.
    """
    parts = sqref.split()
    updated_parts = []

    for part in parts:
        # Check if it's a range (contains :) or single cell
        if ":" in part:
            new_part = _shift_range_ref(part, index, count, is_row, is_delete)
        else:
            # Single cell reference
            col, row, col_abs, row_abs = parse_cell_ref(part)
            col_idx = column_letter_to_index(col)

            if is_row:
                if is_delete:
                    if index <= row < index + count:
                        continue  # Cell deleted
                    if row >= index + count:
                        row -= count
                else:
                    if row >= index:
                        row += count
            else:
                if is_delete:
                    if index <= col_idx < index + count:
                        continue  # Cell deleted
                    if col_idx >= index + count:
                        col_idx -= count
                else:
                    if col_idx >= index:
                        col_idx += count

            new_part = make_cell_ref(col_idx, row, col_abs=col_abs, row_abs=row_abs)

        if new_part:
            updated_parts.append(new_part)

    return " ".join(updated_parts) if updated_parts else None


def _update_sheet_structures(
    pkg: ExcelPackage,
    sheet_name: str,
    index: int,
    count: int,
    is_row: bool,
    is_delete: bool,
) -> None:
    """Update sheet-level structures: autoFilter, conditionalFormatting, dataValidations, dimension."""
    sheet_path = _get_sheet_path(pkg, sheet_name)
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    modified = False

    # Update dimension ref
    dimension = sheet_xml.find(qn("x:dimension"))
    if dimension is not None:
        dim_ref = dimension.get("ref", "")
        if dim_ref:
            new_dim = _shift_range_ref(dim_ref, index, count, is_row, is_delete)
            if new_dim and new_dim != dim_ref:
                dimension.set("ref", new_dim)
                modified = True

    # Update autoFilter ref
    autofilter = sheet_xml.find(qn("x:autoFilter"))
    if autofilter is not None:
        af_ref = autofilter.get("ref", "")
        if af_ref:
            new_af = _shift_range_ref(af_ref, index, count, is_row, is_delete)
            if new_af:
                if new_af != af_ref:
                    autofilter.set("ref", new_af)
                    modified = True
            else:
                # Range completely deleted - remove autoFilter
                sheet_xml.remove(autofilter)
                modified = True

    # Update conditionalFormatting sqref
    for cf in sheet_xml.findall(qn("x:conditionalFormatting")):
        sqref = cf.get("sqref", "")
        if sqref:
            new_sqref = _shift_sqref(sqref, index, count, is_row, is_delete)
            if new_sqref:
                if new_sqref != sqref:
                    cf.set("sqref", new_sqref)
                    modified = True
            else:
                # All ranges deleted - remove conditionalFormatting
                sheet_xml.remove(cf)
                modified = True

    # Update dataValidations
    data_validations = sheet_xml.find(qn("x:dataValidations"))
    if data_validations is not None:
        validations_to_remove = []
        for dv in data_validations.findall(qn("x:dataValidation")):
            sqref = dv.get("sqref", "")
            if sqref:
                new_sqref = _shift_sqref(sqref, index, count, is_row, is_delete)
                if new_sqref:
                    if new_sqref != sqref:
                        dv.set("sqref", new_sqref)
                        modified = True
                else:
                    validations_to_remove.append(dv)

        for dv in validations_to_remove:
            data_validations.remove(dv)
            modified = True

        # Update count or remove empty container
        remaining = len(data_validations.findall(qn("x:dataValidation")))
        if remaining == 0:
            sheet_xml.remove(data_validations)
        else:
            data_validations.set("count", str(remaining))

    if modified:
        pkg.mark_xml_dirty(sheet_path)


def _update_tables(
    pkg: ExcelPackage,
    sheet_name: str,
    index: int,
    count: int,
    is_row: bool,
    is_delete: bool,
) -> None:
    """Update table references in the affected sheet."""
    for name, _rId, partname in pkg.get_sheet_paths():
        if name != sheet_name:
            continue

        sheet_rels = pkg.get_rels(partname)
        for rel in sheet_rels.all_for_reltype(RT.TABLE):
            table_path = pkg.resolve_rel_target(partname, rel.rId)
            if not pkg.has_part(table_path):
                continue

            table_xml = pkg.get_xml(table_path)
            modified = False

            # Update table ref
            table_ref = table_xml.get("ref", "")
            if table_ref:
                new_ref = _shift_range_ref(table_ref, index, count, is_row, is_delete)
                if new_ref and new_ref != table_ref:
                    table_xml.set("ref", new_ref)
                    modified = True

                    # Also update autoFilter inside table
                    table_af = table_xml.find(qn("x:autoFilter"))
                    if table_af is not None:
                        table_af.set("ref", new_ref)

            if modified:
                pkg.mark_xml_dirty(table_path)


def _update_defined_names(
    pkg: ExcelPackage,
    sheet_name: str,
    index: int,
    count: int,
    is_row: bool,
    is_delete: bool,
) -> None:
    """Update defined names that reference the affected sheet."""
    workbook = pkg.workbook_xml
    defined_names = workbook.find(qn("x:definedNames"))
    if defined_names is None:
        return

    modified = False

    # Pattern to match sheet!ref in formulas
    # Handles: Sheet1!A1:B10, 'Sheet Name'!$A$1:$B$10
    pattern = re.compile(
        r"(?:'([^']+)'|([A-Za-z_][A-Za-z0-9_]*))"  # Sheet name (quoted or unquoted)
        r"!"
        r"(\$?[A-Za-z]+\$?\d+(?::\$?[A-Za-z]+\$?\d+)?)"  # Cell or range ref
    )

    for dn in defined_names.findall(qn("x:definedName")):
        formula = dn.text
        if not formula:
            continue

        def replace_ref(match: re.Match) -> str:
            quoted_sheet, unquoted_sheet, ref = match.groups()
            ref_sheet = quoted_sheet or unquoted_sheet

            # Only update if this reference is to the affected sheet
            if ref_sheet != sheet_name:
                return match.group(0)

            # Determine if it's a range or single cell
            if ":" in ref:
                new_ref = _shift_range_ref(ref, index, count, is_row, is_delete)
            else:
                new_ref = _shift_sqref(ref, index, count, is_row, is_delete)

            if new_ref is None:
                return "#REF!"

            # Reconstruct with proper quoting
            if " " in ref_sheet or "'" in ref_sheet:
                safe_sheet = ref_sheet.replace("'", "''")
                return f"'{safe_sheet}'!{new_ref}"
            return f"{ref_sheet}!{new_ref}"

        new_formula = pattern.sub(replace_ref, formula)
        if new_formula != formula:
            dn.text = new_formula
            modified = True

    if modified:
        pkg.mark_xml_dirty(pkg.workbook_path)


def _update_charts(
    pkg: ExcelPackage,
    sheet_name: str,
    index: int,
    count: int,
    is_row: bool,
    is_delete: bool,
) -> None:
    """Update chart series formulas that reference the affected sheet."""
    # Find all chart parts
    for part_path in pkg.iter_partnames():
        if "/xl/charts/chart" not in part_path:
            continue

        chart_xml = pkg.get_xml(part_path)
        modified = False

        # Pattern for sheet references in chart formulas
        pattern = re.compile(
            r"(?:'([^']+)'|([A-Za-z_][A-Za-z0-9_]*))"
            r"!"
            r"(\$?[A-Za-z]+\$?\d+(?::\$?[A-Za-z]+\$?\d+)?)"
        )

        # Find all <c:f> elements (formula references in charts)
        for f_elem in chart_xml.iter(_qn_c("f")):
            if f_elem.text is None:
                continue

            formula = f_elem.text

            def replace_ref(match: re.Match) -> str:
                quoted_sheet, unquoted_sheet, ref = match.groups()
                ref_sheet = quoted_sheet or unquoted_sheet

                if ref_sheet != sheet_name:
                    return match.group(0)

                if ":" in ref:
                    new_ref = _shift_range_ref(ref, index, count, is_row, is_delete)
                else:
                    new_ref = _shift_sqref(ref, index, count, is_row, is_delete)

                if new_ref is None:
                    return "#REF!"

                if " " in ref_sheet or "'" in ref_sheet:
                    safe_sheet = ref_sheet.replace("'", "''")
                    return f"'{safe_sheet}'!{new_ref}"
                return f"{ref_sheet}!{new_ref}"

            new_formula = pattern.sub(replace_ref, formula)
            if new_formula != formula:
                f_elem.text = new_formula
                modified = True

        if modified:
            pkg.mark_xml_dirty(part_path)


def _update_pivot_cache_refs(
    pkg: ExcelPackage,
    sheet_name: str,
    index: int,
    count: int,
    is_row: bool,
    is_delete: bool,
) -> None:
    """Update pivot cache worksheetSource references."""
    # Find all pivot cache definition parts
    for part_path in pkg.iter_partnames():
        if "/xl/pivotCache/pivotCacheDefinition" not in part_path:
            continue

        cache_xml = pkg.get_xml(part_path)
        cache_source = cache_xml.find(qn("x:cacheSource"))
        if cache_source is None:
            continue

        ws_source = cache_source.find(qn("x:worksheetSource"))
        if ws_source is None:
            continue

        # Check if this cache references our sheet
        source_sheet = ws_source.get("sheet", "")
        source_ref = ws_source.get("ref", "")

        if source_sheet != sheet_name or not source_ref:
            continue

        # Update the reference
        new_ref = _shift_range_ref(source_ref, index, count, is_row, is_delete)
        if new_ref and new_ref != source_ref:
            ws_source.set("ref", new_ref)
            pkg.mark_xml_dirty(part_path)
