"""Core utilities for Excel operations.

Cell addressing, ID generation, and common helpers.
"""

from __future__ import annotations

import hashlib
import re


def column_letter_to_index(col: str) -> int:
    """Convert column letter(s) to 1-based index.

    Examples: A -> 1, Z -> 26, AA -> 27, AZ -> 52
    """
    result = 0
    for char in col.upper():
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result


def index_to_column_letter(idx: int) -> str:
    """Convert 1-based column index to letter(s).

    Examples: 1 -> A, 26 -> Z, 27 -> AA, 52 -> AZ
    """
    result = []
    while idx > 0:
        idx, remainder = divmod(idx - 1, 26)
        result.append(chr(ord("A") + remainder))
    return "".join(reversed(result))


_CELL_REF_PATTERN = re.compile(r"^(\$?)([A-Za-z]+)(\$?)(\d+)$")


def parse_cell_ref(ref: str) -> tuple[str, int, bool, bool]:
    """Parse cell reference like 'A1', '$B$2', 'AA10'.

    Returns: (column_letter, row_number, col_absolute, row_absolute)
    """
    match = _CELL_REF_PATTERN.match(ref)
    if not match:
        raise ValueError(f"Invalid cell reference: {ref}")
    col_abs, col, row_abs, row = match.groups()
    return col.upper(), int(row), bool(col_abs), bool(row_abs)


def make_cell_ref(
    col: str | int, row: int, *, col_abs: bool = False, row_abs: bool = False
) -> str:
    """Create cell reference string.

    Args:
        col: Column letter(s) or 1-based index
        row: Row number (1-based)
        col_abs: If True, prefix column with $
        row_abs: If True, prefix row with $

    Returns: Cell reference like 'A1', '$B$2'
    """
    if isinstance(col, int):
        col = index_to_column_letter(col)
    col_prefix = "$" if col_abs else ""
    row_prefix = "$" if row_abs else ""
    return f"{col_prefix}{col.upper()}{row_prefix}{row}"


_RANGE_REF_PATTERN = re.compile(r"^([A-Za-z$]+\d+):([A-Za-z$]+\d+)$")


def parse_range_ref(ref: str) -> tuple[str, str]:
    """Parse range reference like 'A1:C5'.

    Returns: (start_ref, end_ref)
    """
    match = _RANGE_REF_PATTERN.match(ref)
    if not match:
        raise ValueError(f"Invalid range reference: {ref}")
    return match.group(1), match.group(2)


def make_range_ref(start: str, end: str) -> str:
    """Create range reference from two cell refs."""
    return f"{start}:{end}"


# === Content-addressed IDs ===


def _hash_content(content: str) -> str:
    """Generate short hash from content for ID uniqueness."""
    return hashlib.sha1(content.encode()).hexdigest()[:8]


def make_cell_id(
    sheet_name: str, cell_ref: str, content: str = "", ordinal: int = 0
) -> str:
    """Generate content-addressed ID for a cell.

    Format: cell_<sheet>_<ref>_<hash>_<ordinal>
    """
    content_hash = _hash_content(f"{sheet_name}:{cell_ref}:{content}")
    safe_sheet = sheet_name.replace(" ", "_")
    return f"cell_{safe_sheet}_{cell_ref}_{content_hash}_{ordinal}"


def make_range_id(sheet_name: str, range_ref: str, ordinal: int = 0) -> str:
    """Generate content-addressed ID for a range.

    Format: range_<sheet>_<ref>_<hash>_<ordinal>
    """
    content_hash = _hash_content(f"{sheet_name}:{range_ref}")
    safe_sheet = sheet_name.replace(" ", "_")
    safe_range = range_ref.replace(":", "")
    return f"range_{safe_sheet}_{safe_range}_{content_hash}_{ordinal}"


def make_sheet_id(sheet_name: str, ordinal: int = 0) -> str:
    """Generate content-addressed ID for a sheet.

    Format: sheet_<name>_<hash>_<ordinal>
    """
    content_hash = _hash_content(sheet_name)
    safe_sheet = sheet_name.replace(" ", "_")
    return f"sheet_{safe_sheet}_{content_hash}_{ordinal}"


def make_table_id(table_name: str, ordinal: int = 0) -> str:
    """Generate content-addressed ID for a table.

    Format: table_<name>_<hash>_<ordinal>
    """
    content_hash = _hash_content(table_name)
    safe_name = table_name.replace(" ", "_")
    return f"table_{safe_name}_{content_hash}_{ordinal}"
