"""Field insertion operations for Word documents.

Contains functions for:
- Generic Word field insertion (PAGE, NUMPAGES, DATE, etc.)
- Citation fields (CITATION)
- Bibliography fields (BIBLIOGRAPHY)
"""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.ops.core import _make_run_with


def insert_field(
    p_el: etree._Element,
    field_code: str,
    display_text: str = "",
    *,
    uppercase: bool = True,
    placeholder: str = "1",
) -> None:
    """Insert a Word field into a paragraph.

    Creates proper OXML field structure with separate runs for each part:
    begin, instruction, separator, result, and end markers.
    Supports any Word field code (PAGE, NUMPAGES, DATE, TIME, AUTHOR, etc.).

    CRITICAL: Sets xml:space="preserve" on instrText for proper field parsing.

    Args:
        p_el: w:p element
        field_code: Word field code (e.g., 'PAGE', 'NUMPAGES', 'DATE')
        display_text: Display text (unused, kept for API compatibility)
        uppercase: If True (default), uppercases field_code. Set False for case-sensitive
            fields like bookmark names in cross-references.
        placeholder: Default result text shown before field updates.
    """
    code = field_code.strip().upper() if uppercase else field_code

    # Run 1: Field begin
    fld_char_begin = etree.Element(qn("w:fldChar"))
    fld_char_begin.set(qn("w:fldCharType"), "begin")
    p_el.append(_make_run_with(fld_char_begin))

    # Run 2: Field instruction
    instr_text = etree.Element(qn("w:instrText"))
    instr_text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instr_text.text = f" {code} "
    p_el.append(_make_run_with(instr_text))

    # Run 3: Field separator
    fld_char_sep = etree.Element(qn("w:fldChar"))
    fld_char_sep.set(qn("w:fldCharType"), "separate")
    p_el.append(_make_run_with(fld_char_sep))

    # Run 4: Result text (placeholder shown before field updates)
    text_elem = etree.Element(qn("w:t"))
    text_elem.text = display_text or placeholder
    p_el.append(_make_run_with(text_elem))

    # Run 5: Field end
    fld_char_end = etree.Element(qn("w:fldChar"))
    fld_char_end.set(qn("w:fldCharType"), "end")
    p_el.append(_make_run_with(fld_char_end))


def insert_citation(
    p_el: etree._Element,
    tag: str,
    display_text: str = "",
    locale: int = 1033,
) -> None:
    """Insert a CITATION field into a paragraph.

    Args:
        p_el: w:p element
        tag: Source tag (e.g., 'Smith2020')
        display_text: Display text for the citation (e.g., '(Smith, 2020)')
        locale: Locale code (default 1033 = English US)
    """
    # CITATION field code format: CITATION "Tag" \l locale
    field_code = f'CITATION "{tag}" \\l {locale}'
    insert_field(
        p_el, field_code, display_text, uppercase=False, placeholder=f"({tag})"
    )


def insert_bibliography(p_el: etree._Element) -> None:
    """Insert a BIBLIOGRAPHY field into a paragraph.

    Args:
        p_el: w:p element
    """
    insert_field(
        p_el,
        "BIBLIOGRAPHY",
        placeholder="Bibliography entries appear here after field update",
    )
