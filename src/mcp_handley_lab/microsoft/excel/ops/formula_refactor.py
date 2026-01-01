"""Formula refactoring operations for Excel.

Handles updating cell references when rows/columns are inserted or deleted.
Supports absolute ($A$1) and relative (A1) references, ranges (A1:B10),
and cross-sheet references (Sheet1!A1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.ops.core import (
    column_letter_to_index as _column_letter_to_index,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    index_to_column_letter as _index_to_column_letter,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


@dataclass
class CellRef:
    """Parsed cell reference."""

    sheet: str | None  # None means same sheet
    col: str  # Column letter(s)
    row: int  # Row number (1-based)
    col_abs: bool  # True if column is absolute ($A)
    row_abs: bool  # True if row is absolute ($1)

    def to_string(self) -> str:
        """Convert back to string reference."""
        col_str = f"${self.col}" if self.col_abs else self.col
        row_str = f"${self.row}" if self.row_abs else str(self.row)
        if self.sheet:
            # Determine if quoting is needed (spaces, special chars, leading digit)
            needs_quote = (
                " " in self.sheet
                or "'" in self.sheet
                or (self.sheet and self.sheet[0].isdigit())
            )
            if needs_quote:
                # Escape single quotes by doubling them
                safe_sheet = self.sheet.replace("'", "''")
                return f"'{safe_sheet}'!{col_str}{row_str}"
            return f"{self.sheet}!{col_str}{row_str}"
        return f"{col_str}{row_str}"


# Pattern to match cell references in formulas
# Handles: A1, $A$1, $A1, A$1, Sheet1!A1, 'Sheet Name'!A1, 'O''Brien'!A1
_CELL_REF_PATTERN = re.compile(
    r"(?:"
    r"(?:'((?:[^']|'')+)'|([A-Za-z_][A-Za-z0-9_]*))"  # Sheet name (quoted with '' escape, or unquoted)
    r"!)?"  # Sheet separator
    r"(\$?)([A-Za-z]{1,3})"  # Column with optional $
    r"(\$?)(\d+)"  # Row with optional $
)


def parse_formula_references(formula: str) -> list[CellRef]:
    """Extract all cell references from a formula.

    Args:
        formula: Excel formula (with or without leading =).

    Returns: List of CellRef objects for each reference found.
    """
    refs = []
    for match in _CELL_REF_PATTERN.finditer(formula):
        quoted_sheet, unquoted_sheet, col_abs, col, row_abs, row = match.groups()
        sheet = quoted_sheet or unquoted_sheet
        # Unescape doubled single quotes in sheet names
        if sheet and "''" in sheet:
            sheet = sheet.replace("''", "'")
        refs.append(
            CellRef(
                sheet=sheet,
                col=col.upper(),
                row=int(row),
                col_abs=bool(col_abs),
                row_abs=bool(row_abs),
            )
        )
    return refs


def shift_reference(
    ref: CellRef,
    row_delta: int = 0,
    col_delta: int = 0,
    target_sheet: str | None = None,
) -> CellRef | None:
    """Shift a cell reference by row and/or column delta (for copy/fill).

    This function simulates Excel's behavior when copying or filling formulas.
    Absolute references ($A$1) are NOT shifted, as they are anchored.
    For structural changes (insert/delete rows/cols), use update_formulas_after_insert/delete
    which shift all references including absolute ones.

    Args:
        ref: Original cell reference.
        row_delta: Rows to shift (positive = down, negative = up).
        col_delta: Columns to shift (positive = right, negative = left).
        target_sheet: Only shift if ref is on this sheet (None = current sheet refs only).

    Returns: New CellRef with shifted position, or None if ref becomes invalid (row < 1 or col < 1).
    """
    # Only shift refs on the target sheet (or current sheet if target is None)
    if target_sheet is not None and ref.sheet != target_sheet:
        return ref
    if target_sheet is None and ref.sheet is not None:
        return ref

    # Absolute refs don't shift
    new_row = ref.row
    new_col_idx = _column_letter_to_index(ref.col)

    if not ref.row_abs:
        new_row = ref.row + row_delta
    if not ref.col_abs:
        new_col_idx = new_col_idx + col_delta

    # Check for invalid refs
    if new_row < 1 or new_col_idx < 1:
        return None

    return CellRef(
        sheet=ref.sheet,
        col=_index_to_column_letter(new_col_idx),
        row=new_row,
        col_abs=ref.col_abs,
        row_abs=ref.row_abs,
    )


def shift_formula(
    formula: str,
    row_delta: int = 0,
    col_delta: int = 0,
    target_sheet: str | None = None,
) -> str:
    """Shift all references in a formula.

    Args:
        formula: Original formula.
        row_delta: Rows to shift.
        col_delta: Columns to shift.
        target_sheet: Only shift refs on this sheet.

    Returns: Formula with shifted references. References that become invalid
             (row/col < 1) are replaced with #REF!.
    """

    def replace_ref(match: re.Match) -> str:
        quoted_sheet, unquoted_sheet, col_abs, col, row_abs, row = match.groups()
        sheet = quoted_sheet or unquoted_sheet

        ref = CellRef(
            sheet=sheet,
            col=col.upper(),
            row=int(row),
            col_abs=bool(col_abs),
            row_abs=bool(row_abs),
        )

        shifted = shift_reference(ref, row_delta, col_delta, target_sheet)
        if shifted is None:
            return "#REF!"
        return shifted.to_string()

    return _CELL_REF_PATTERN.sub(replace_ref, formula)


def update_formulas_after_insert(
    pkg: ExcelPackage,
    sheet_name: str,
    index: int,
    count: int = 1,
    is_row: bool = True,
) -> int:
    """Update all formulas after inserting rows or columns.

    All formulas in the workbook that reference cells at or after the
    insertion point are shifted. This includes cross-sheet references.

    Args:
        pkg: Excel package.
        sheet_name: Sheet where insertion happened.
        index: 1-based row/column index where insertion started.
        count: Number of rows/columns inserted.
        is_row: True for row insertion, False for column insertion.

    Returns: Number of formulas updated.
    """
    updated = 0

    # Update formulas in all sheets
    for name, _rId, partname in pkg.get_sheet_paths():
        sheet_xml = pkg.get_xml(partname)
        sheet_data = sheet_xml.find(qn("x:sheetData"))
        if sheet_data is None:
            continue

        sheet_modified = False

        for row_el in sheet_data.findall(qn("x:row")):
            for cell_el in row_el.findall(qn("x:c")):
                formula_el = cell_el.find(qn("x:f"))
                if formula_el is None or formula_el.text is None:
                    continue

                formula = formula_el.text

                if name == sheet_name:
                    # We're on the target sheet - shift local refs only
                    new_formula = _shift_formula_for_insert(
                        formula, None, index, count, is_row
                    )
                else:
                    # We're on a different sheet - shift cross-sheet refs to target
                    new_formula = _shift_formula_for_insert(
                        formula, sheet_name, index, count, is_row
                    )

                if new_formula != formula:
                    formula_el.text = new_formula
                    updated += 1
                    sheet_modified = True

        if sheet_modified:
            pkg.mark_xml_dirty(partname)

    return updated


def _shift_formula_for_insert(
    formula: str,
    target_sheet: str | None,
    index: int,
    count: int,
    is_row: bool,
) -> str:
    """Shift formula references for an insertion."""

    def replace_ref(match: re.Match) -> str:
        quoted_sheet, unquoted_sheet, col_abs, col, row_abs, row = match.groups()
        sheet = quoted_sheet or unquoted_sheet

        # Check if this ref is on the target sheet
        if target_sheet is not None and sheet != target_sheet:
            return match.group(0)
        if target_sheet is None and sheet is not None:
            return match.group(0)

        row_num = int(row)
        col_idx = _column_letter_to_index(col.upper())

        # For structural changes (row/col insert), shift ALL refs at/after insertion point
        # Note: Absolute ($) means "don't shift when copied", not "don't shift on structure change"
        if is_row:
            if row_num >= index:
                row_num += count
        else:
            if col_idx >= index:
                col_idx += count

        # Reconstruct the reference - always use computed col_idx for column letters
        new_col_letters = _index_to_column_letter(col_idx)
        col_str = f"${new_col_letters}" if col_abs else new_col_letters
        row_str = f"${row_num}" if row_abs else str(row_num)

        if sheet:
            # Unescape for comparison, then re-escape for output
            unescaped_sheet = sheet.replace("''", "'") if "''" in sheet else sheet
            needs_quote = (
                " " in unescaped_sheet
                or "'" in unescaped_sheet
                or (unescaped_sheet and unescaped_sheet[0].isdigit())
            )
            if needs_quote:
                safe_sheet = unescaped_sheet.replace("'", "''")
                return f"'{safe_sheet}'!{col_str}{row_str}"
            return f"{unescaped_sheet}!{col_str}{row_str}"
        return f"{col_str}{row_str}"

    return _CELL_REF_PATTERN.sub(replace_ref, formula)


def update_formulas_after_delete(
    pkg: ExcelPackage,
    sheet_name: str,
    index: int,
    count: int = 1,
    is_row: bool = True,
) -> int:
    """Update all formulas after deleting rows or columns.

    All formulas in the workbook that reference cells at or after the
    deletion point are shifted. References to deleted cells become #REF!.

    Args:
        pkg: Excel package.
        sheet_name: Sheet where deletion happened.
        index: 1-based row/column index where deletion started.
        count: Number of rows/columns deleted.
        is_row: True for row deletion, False for column deletion.

    Returns: Number of formulas updated.
    """
    updated = 0

    # Update formulas in all sheets
    for name, _rId, partname in pkg.get_sheet_paths():
        sheet_xml = pkg.get_xml(partname)
        sheet_data = sheet_xml.find(qn("x:sheetData"))
        if sheet_data is None:
            continue

        sheet_modified = False

        for row_el in sheet_data.findall(qn("x:row")):
            for cell_el in row_el.findall(qn("x:c")):
                formula_el = cell_el.find(qn("x:f"))
                if formula_el is None or formula_el.text is None:
                    continue

                formula = formula_el.text

                if name == sheet_name:
                    # We're on the target sheet - shift local refs only
                    new_formula = _shift_formula_for_delete(
                        formula, None, index, count, is_row
                    )
                else:
                    # We're on a different sheet - shift cross-sheet refs to target
                    new_formula = _shift_formula_for_delete(
                        formula, sheet_name, index, count, is_row
                    )

                if new_formula != formula:
                    formula_el.text = new_formula
                    updated += 1
                    sheet_modified = True

        if sheet_modified:
            pkg.mark_xml_dirty(partname)

    return updated


def _shift_formula_for_delete(
    formula: str,
    target_sheet: str | None,
    index: int,
    count: int,
    is_row: bool,
) -> str:
    """Shift formula references for a deletion."""

    def replace_ref(match: re.Match) -> str:
        quoted_sheet, unquoted_sheet, col_abs, col, row_abs, row = match.groups()
        sheet = quoted_sheet or unquoted_sheet

        # Check if this ref is on the target sheet
        if target_sheet is not None and sheet != target_sheet:
            return match.group(0)
        if target_sheet is None and sheet is not None:
            return match.group(0)

        row_num = int(row)
        col_idx = _column_letter_to_index(col.upper())

        # Determine if this ref needs shifting or becomes invalid
        # For structural changes, both absolute and relative refs are affected
        if is_row:
            if row_num >= index and row_num < index + count:
                # Ref is in deleted range - always becomes #REF!
                return "#REF!"
            elif row_num >= index + count:
                # Shift ALL refs after deletion point
                row_num -= count
        else:
            if col_idx >= index and col_idx < index + count:
                # Ref is in deleted range - always becomes #REF!
                return "#REF!"
            elif col_idx >= index + count:
                # Shift ALL refs after deletion point
                col_idx -= count

        # Reconstruct the reference - always use computed col_idx for column letters
        new_col_letters = _index_to_column_letter(col_idx)
        col_str = f"${new_col_letters}" if col_abs else new_col_letters
        row_str = f"${row_num}" if row_abs else str(row_num)

        if sheet:
            # Unescape for comparison, then re-escape for output
            unescaped_sheet = sheet.replace("''", "'") if "''" in sheet else sheet
            needs_quote = (
                " " in unescaped_sheet
                or "'" in unescaped_sheet
                or (unescaped_sheet and unescaped_sheet[0].isdigit())
            )
            if needs_quote:
                safe_sheet = unescaped_sheet.replace("'", "''")
                return f"'{safe_sheet}'!{col_str}{row_str}"
            return f"{unescaped_sheet}!{col_str}{row_str}"
        return f"{col_str}{row_str}"

    return _CELL_REF_PATTERN.sub(replace_ref, formula)
