"""Text run management for handling fragmented text across XML runs.

Handles the common problem in OOXML where text like `{{name}}` is split across
multiple runs:
    <w:r><w:t>{{</w:t></w:r><w:r><w:t>name</w:t></w:r><w:r><w:t>}}</w:t></w:r>

This module provides utilities for both Word (w:p/w:r/w:t) and PowerPoint
(a:p/a:r/a:t) text elements.
"""

from __future__ import annotations

from lxml import etree


def _get_text_elements(
    paragraph: etree._Element, ns: str, text_tag: str
) -> list[etree._Element]:
    """Get all text elements from a paragraph.

    Args:
        paragraph: The paragraph element (w:p or a:p)
        ns: Namespace URI for the text elements
        text_tag: Tag name for text elements (t)

    Returns:
        List of text elements in document order.
    """
    t_qn = f"{{{ns}}}{text_tag}"
    return list(paragraph.iter(t_qn))


def get_paragraph_text(
    paragraph: etree._Element,
    ns: str,
    text_tag: str = "t",
) -> str:
    """Concatenate all text elements in a paragraph.

    Args:
        paragraph: The paragraph element (w:p or a:p)
        ns: Namespace URI (Word: w14, PowerPoint: DrawingML)
        text_tag: Tag name for text elements (default "t")

    Returns:
        Full text content of the paragraph.
    """
    texts = _get_text_elements(paragraph, ns, text_tag)
    return "".join(t.text or "" for t in texts)


_XML_SPACE_ATTR = "{http://www.w3.org/XML/1998/namespace}space"


def _set_text_with_space_preserve(text_el: etree._Element, new_text: str) -> None:
    """Set text element content, managing xml:space='preserve' attribute.

    Leading/trailing whitespace requires xml:space="preserve" to be retained.
    Removes the attribute if no longer needed.
    """
    text_el.text = new_text
    needs_preserve = new_text and (new_text[0].isspace() or new_text[-1].isspace())
    if needs_preserve:
        text_el.set(_XML_SPACE_ATTR, "preserve")
    elif _XML_SPACE_ATTR in text_el.attrib:
        del text_el.attrib[_XML_SPACE_ATTR]


def replace_in_paragraph(
    paragraph: etree._Element,
    search: str,
    replace: str,
    ns: str,
    text_tag: str = "t",
    match_case: bool = True,
) -> int:
    """Replace text in a paragraph, handling fragmented runs.

    This handles the case where `search` spans multiple text elements.
    Strategy: Collect all text, find matches, then distribute back across runs.

    Args:
        paragraph: The paragraph element (w:p or a:p)
        search: Text to search for
        replace: Replacement text
        ns: Namespace URI
        text_tag: Tag name for text elements (default "t")
        match_case: If True (default), search is case-sensitive. If False,
            performs case-insensitive search.

    Returns:
        Number of replacements made.
    """
    import re

    texts = _get_text_elements(paragraph, ns, text_tag)
    if not texts:
        return 0

    # Build concatenated text and track boundaries
    full_text = ""
    boundaries = []  # (start_idx, end_idx, text_element)
    for t in texts:
        content = t.text or ""
        start = len(full_text)
        end = start + len(content)
        boundaries.append((start, end, t))
        full_text += content

    if match_case:
        if search not in full_text:
            return 0
        # Perform replacement
        new_full_text = full_text.replace(search, replace)
        count = full_text.count(search)
    else:
        # Case-insensitive replacement
        pattern = re.compile(re.escape(search), re.IGNORECASE)
        matches = pattern.findall(full_text)
        if not matches:
            return 0
        new_full_text = pattern.sub(replace, full_text)
        count = len(matches)

    # Redistribute text back to elements
    _redistribute_text(texts, boundaries, new_full_text)

    return count


def _redistribute_text(
    texts: list[etree._Element],
    boundaries: list[tuple[int, int, etree._Element]],
    new_text: str,
) -> None:
    """Redistribute replaced text back to text elements.

    Uses a simple correctness-first strategy: fill each element with up to its
    original length of characters from the new text, then put any remainder
    in the last element. This preserves run boundaries where possible while
    being deterministic and correct.
    """
    if not texts:
        return

    # Simple approach: distribute new text by original element lengths
    # Each element gets at most its original character count
    cursor = 0
    for i, (orig_start, orig_end, t_el) in enumerate(boundaries):
        orig_len = orig_end - orig_start
        is_last = i == len(boundaries) - 1

        if is_last:
            # Last element gets all remaining text
            segment = new_text[cursor:]
        else:
            # Non-last elements get at most their original length
            segment = new_text[cursor : cursor + orig_len]
            cursor += len(segment)

        _set_text_with_space_preserve(t_el, segment)


# Word-specific namespace
NS_WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def get_word_paragraph_text(paragraph: etree._Element) -> str:
    """Get full text from a Word paragraph (w:p)."""
    return get_paragraph_text(paragraph, NS_WORD, "t")


def replace_in_word_paragraph(
    paragraph: etree._Element,
    search: str,
    replace: str,
    match_case: bool = True,
) -> int:
    """Replace text in a Word paragraph, handling fragmented runs."""
    return replace_in_paragraph(
        paragraph, search, replace, NS_WORD, "t", match_case=match_case
    )


# PowerPoint/DrawingML-specific namespace
NS_DRAWINGML = "http://schemas.openxmlformats.org/drawingml/2006/main"


def get_ppt_paragraph_text(paragraph: etree._Element) -> str:
    """Get full text from a PowerPoint paragraph (a:p)."""
    return get_paragraph_text(paragraph, NS_DRAWINGML, "t")


def replace_in_ppt_paragraph(
    paragraph: etree._Element,
    search: str,
    replace: str,
    match_case: bool = True,
) -> int:
    """Replace text in a PowerPoint paragraph, handling fragmented runs."""
    return replace_in_paragraph(
        paragraph, search, replace, NS_DRAWINGML, "t", match_case=match_case
    )
