"""Math equation (OMML) operations.

Contains functions for:
- Extracting text representation from OMML structures
- Determining equation complexity
- Building list of all equations in document

Pure OOXML implementation - works directly with lxml elements.
"""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.ops.core import (
    content_hash,
    count_occurrence,
    get_paragraph_text,
    iter_body_blocks,
    make_block_id,
    paragraph_kind_and_level,
    table_content_for_hash,
)

# =============================================================================
# Constants
# =============================================================================

# Math namespace
_MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_MATH_NSMAP = {"m": _MATH_NS}


# =============================================================================
# Equation Text Extraction
# =============================================================================


def _get_equation_text(omath) -> str:
    """Extract simplified text representation from OMML structure.

    Converts OMML elements to readable text:
    - m:f (fraction) -> (numerator)/(denominator)
    - m:sSup (superscript) -> base^exponent
    - m:sSub (subscript) -> base_subscript
    - m:rad (radical) -> sqrt(radicand) or nrt(degree, radicand)
    - m:nary (n-ary operator) -> sum, prod, int with limits
    - m:d (delimiter/parentheses) -> (content)
    - m:m (matrix) -> [a, b; c, d]
    - m:r (run) -> text content

    Container elements (e, num, den, sub, sup, deg, lim, oMath, oMathPara, fName)
    are handled by recursively processing their children.
    """
    # Container tags that just hold other content - recurse into children
    CONTAINER_TAGS = {
        "e",
        "num",
        "den",
        "sub",
        "sup",
        "deg",
        "lim",
        "oMath",
        "oMathPara",
        "fName",
    }

    parts = []

    for child in omath:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "r":
            # Math run - extract text from m:t
            for t in child.iter(f"{{{_MATH_NS}}}t"):
                if t.text:
                    parts.append(t.text)

        elif tag == "f":
            # Fraction: (num)/(den)
            num = child.find("m:num", namespaces=_MATH_NSMAP)
            den = child.find("m:den", namespaces=_MATH_NSMAP)
            num_text = _get_equation_text(num) if num is not None else "?"
            den_text = _get_equation_text(den) if den is not None else "?"
            parts.append(f"({num_text})/({den_text})")

        elif tag == "sSup":
            # Superscript: base^exp
            base = child.find("m:e", namespaces=_MATH_NSMAP)
            sup = child.find("m:sup", namespaces=_MATH_NSMAP)
            base_text = _get_equation_text(base) if base is not None else "?"
            sup_text = _get_equation_text(sup) if sup is not None else "?"
            parts.append(f"{base_text}^{sup_text}")

        elif tag == "sSub":
            # Subscript: base_sub
            base = child.find("m:e", namespaces=_MATH_NSMAP)
            sub = child.find("m:sub", namespaces=_MATH_NSMAP)
            base_text = _get_equation_text(base) if base is not None else "?"
            sub_text = _get_equation_text(sub) if sub is not None else "?"
            parts.append(f"{base_text}_{sub_text}")

        elif tag == "sSubSup":
            # Sub-superscript: base_sub^sup
            base = child.find("m:e", namespaces=_MATH_NSMAP)
            sub = child.find("m:sub", namespaces=_MATH_NSMAP)
            sup = child.find("m:sup", namespaces=_MATH_NSMAP)
            base_text = _get_equation_text(base) if base is not None else "?"
            sub_text = _get_equation_text(sub) if sub is not None else "?"
            sup_text = _get_equation_text(sup) if sup is not None else "?"
            parts.append(f"{base_text}_{sub_text}^{sup_text}")

        elif tag == "rad":
            # Radical: sqrt(x) or nrt(n, x)
            deg = child.find("m:deg", namespaces=_MATH_NSMAP)
            e = child.find("m:e", namespaces=_MATH_NSMAP)
            e_text = _get_equation_text(e) if e is not None else "?"
            if deg is not None:
                deg_text = _get_equation_text(deg)
                if deg_text and deg_text.strip():
                    parts.append(f"nrt({deg_text}, {e_text})")
                else:
                    parts.append(f"sqrt({e_text})")
            else:
                parts.append(f"sqrt({e_text})")

        elif tag == "nary":
            # N-ary operator (sum, product, integral)
            nary_pr = child.find("m:naryPr", namespaces=_MATH_NSMAP)
            chr_el = (
                nary_pr.find("m:chr", namespaces=_MATH_NSMAP)
                if nary_pr is not None
                else None
            )
            chr_val = chr_el.get(f"{{{_MATH_NS}}}val") if chr_el is not None else None

            # Map Unicode symbols to names
            op_map = {
                "\u2211": "sum",
                "\u220f": "prod",
                "\u222b": "int",
                "\u222c": "iint",
                "\u222d": "iiint",
            }
            op = op_map.get(chr_val, chr_val or "nary")

            sub = child.find("m:sub", namespaces=_MATH_NSMAP)
            sup = child.find("m:sup", namespaces=_MATH_NSMAP)
            e = child.find("m:e", namespaces=_MATH_NSMAP)

            sub_text = _get_equation_text(sub) if sub is not None else ""
            sup_text = _get_equation_text(sup) if sup is not None else ""
            e_text = _get_equation_text(e) if e is not None else "?"

            if sub_text or sup_text:
                parts.append(f"{op}({sub_text}..{sup_text})[{e_text}]")
            else:
                parts.append(f"{op}[{e_text}]")

        elif tag == "d":
            # Delimiter (parentheses, brackets, braces)
            d_pr = child.find("m:dPr", namespaces=_MATH_NSMAP)
            beg_chr = "("
            end_chr = ")"
            if d_pr is not None:
                beg_el = d_pr.find("m:begChr", namespaces=_MATH_NSMAP)
                end_el = d_pr.find("m:endChr", namespaces=_MATH_NSMAP)
                if beg_el is not None:
                    beg_chr = beg_el.get(f"{{{_MATH_NS}}}val") or "("
                if end_el is not None:
                    end_chr = end_el.get(f"{{{_MATH_NS}}}val") or ")"

            e = child.find("m:e", namespaces=_MATH_NSMAP)
            e_text = _get_equation_text(e) if e is not None else ""
            parts.append(f"{beg_chr}{e_text}{end_chr}")

        elif tag == "m":
            # Matrix
            rows = []
            for mr in child.findall("m:mr", namespaces=_MATH_NSMAP):
                row_parts = []
                for me in mr.findall("m:e", namespaces=_MATH_NSMAP):
                    row_parts.append(_get_equation_text(me))
                rows.append(", ".join(row_parts))
            parts.append("[" + "; ".join(rows) + "]")

        elif tag == "func":
            # Function: sin, cos, etc.
            fname = child.find("m:fName", namespaces=_MATH_NSMAP)
            e = child.find("m:e", namespaces=_MATH_NSMAP)
            fname_text = _get_equation_text(fname) if fname is not None else "f"
            e_text = _get_equation_text(e) if e is not None else ""
            parts.append(f"{fname_text}({e_text})")

        elif tag == "limLow":
            # Lower limit: lim_{x->0}
            e = child.find("m:e", namespaces=_MATH_NSMAP)
            lim = child.find("m:lim", namespaces=_MATH_NSMAP)
            e_text = _get_equation_text(e) if e is not None else ""
            lim_text = _get_equation_text(lim) if lim is not None else ""
            parts.append(f"{e_text}_{{{lim_text}}}")

        elif tag == "limUpp":
            # Upper limit
            e = child.find("m:e", namespaces=_MATH_NSMAP)
            lim = child.find("m:lim", namespaces=_MATH_NSMAP)
            e_text = _get_equation_text(e) if e is not None else ""
            lim_text = _get_equation_text(lim) if lim is not None else ""
            parts.append(f"{e_text}^{{{lim_text}}}")

        elif tag in CONTAINER_TAGS:
            # Container elements - recurse into their children
            parts.append(_get_equation_text(child))

        else:
            # Unknown structural element - recurse into children to find text
            child_text = _get_equation_text(child)
            if child_text:
                parts.append(child_text)

    return "".join(parts)


# =============================================================================
# Equation Analysis
# =============================================================================


def _get_equation_complexity(omath) -> str:
    """Determine the complexity of a math equation."""
    # Check for complex elements
    has_matrix = omath.find(".//m:m", namespaces=_MATH_NSMAP) is not None
    has_nary = omath.find(".//m:nary", namespaces=_MATH_NSMAP) is not None
    has_fraction = omath.find(".//m:f", namespaces=_MATH_NSMAP) is not None
    has_radical = omath.find(".//m:rad", namespaces=_MATH_NSMAP) is not None
    has_script = (
        omath.find(".//m:sSup", namespaces=_MATH_NSMAP) is not None
        or omath.find(".//m:sSub", namespaces=_MATH_NSMAP) is not None
        or omath.find(".//m:sSubSup", namespaces=_MATH_NSMAP) is not None
    )

    if has_matrix:
        return "matrix"
    if has_nary or (has_fraction and has_radical):
        return "complex"
    if has_fraction:
        return "fraction"
    if has_script or has_radical:
        return "simple"
    return "simple"


def _extract_equations_from_paragraph(
    p_el: etree._Element, block_id: str, equation_hash_counts: dict[str, int]
) -> list[dict]:
    """Extract all equations from a paragraph element.

    Pure OOXML: Takes w:p element.
    """
    equations = []
    for omath in p_el.iter(f"{{{_MATH_NS}}}oMath"):
        text = _get_equation_text(omath)
        eq_hash = content_hash(text)
        occurrence = equation_hash_counts.get(eq_hash, 0)
        equation_hash_counts[eq_hash] = occurrence + 1
        eq_id = f"equation_{eq_hash}_{occurrence}"
        complexity = _get_equation_complexity(omath)
        equations.append(
            {
                "id": eq_id,
                "text": text,
                "block_id": block_id,
                "complexity": complexity,
            }
        )
    return equations


# =============================================================================
# Main Equation Builder
# =============================================================================


def build_equations(pkg) -> list[dict]:
    """Build list of all math equations (OMML) in the document.

    Args:
        pkg: WordPackage
    """
    equations: list[dict] = []
    equation_hash_counts: dict[str, int] = {}

    # Use iter_body_blocks to match build_blocks() block ID computation
    for kind, p_el in iter_body_blocks(pkg):
        if kind == "paragraph":
            # Use SAME logic as build_blocks for block_id
            block_type, _ = paragraph_kind_and_level(p_el)
            text = get_paragraph_text(p_el)
            occurrence = count_occurrence(pkg, block_type, text, p_el)
            block_id = make_block_id(block_type, text, occurrence)

            equations.extend(
                _extract_equations_from_paragraph(p_el, block_id, equation_hash_counts)
            )

        elif kind == "table":
            # Compute table's block_id
            tbl_el = p_el  # In table case, p_el is actually tbl_el
            table_content = table_content_for_hash(tbl_el)
            occurrence = count_occurrence(pkg, "table", table_content, tbl_el)
            table_block_id = make_block_id("table", table_content, occurrence)

            # Search all cells for equations with hierarchical block_id
            visited_cells: set = set()  # Track processed cell elements (merged cells)
            rows = tbl_el.findall(qn("w:tr"))
            for r_idx, tr in enumerate(rows):
                cells = tr.findall(qn("w:tc"))
                for c_idx, tc in enumerate(cells):
                    # Skip if we've already processed this cell (handles merged cells)
                    if tc in visited_cells:
                        continue
                    visited_cells.add(tc)

                    paras = tc.findall(qn("w:p"))
                    for p_idx, para_el in enumerate(paras):
                        hier_block_id = f"{table_block_id}#r{r_idx}c{c_idx}/p{p_idx}"
                        equations.extend(
                            _extract_equations_from_paragraph(
                                para_el, hier_block_id, equation_hash_counts
                            )
                        )

    return equations
