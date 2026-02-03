"""Tests for text fragmentation handling in find/replace and mail_merge.

These tests verify that placeholders split across multiple XML runs are
correctly handled (Risk A from the implementation plan).
"""

from __future__ import annotations

from lxml import etree

from mcp_handley_lab.microsoft.common.text import (
    NS_DRAWINGML,
    NS_WORD,
    _set_text_with_space_preserve,
    get_ppt_paragraph_text,
    get_word_paragraph_text,
    replace_in_ppt_paragraph,
    replace_in_word_paragraph,
)

# =============================================================================
# Word Paragraph Tests (w:p / w:r / w:t)
# =============================================================================


def _make_word_paragraph(run_texts: list[str]) -> etree._Element:
    """Create a Word paragraph with multiple runs, each containing text."""
    nsmap = {"w": NS_WORD}
    p = etree.Element(f"{{{NS_WORD}}}p", nsmap=nsmap)
    for text in run_texts:
        r = etree.SubElement(p, f"{{{NS_WORD}}}r")
        t = etree.SubElement(r, f"{{{NS_WORD}}}t")
        t.text = text
    return p


class TestWordFragmentedText:
    """Test find/replace with fragmented Word text."""

    def test_placeholder_split_across_two_runs(self):
        """{{name}} split as ['{{', 'name}}'] should be replaced."""
        p = _make_word_paragraph(["{{", "name}}"])
        assert get_word_paragraph_text(p) == "{{name}}"

        count = replace_in_word_paragraph(p, "{{name}}", "John")
        assert count == 1
        assert get_word_paragraph_text(p) == "John"

    def test_placeholder_split_across_three_runs(self):
        """{{name}} split as ['{{', 'name', '}}'] should be replaced."""
        p = _make_word_paragraph(["{{", "name", "}}"])
        assert get_word_paragraph_text(p) == "{{name}}"

        count = replace_in_word_paragraph(p, "{{name}}", "Alice")
        assert count == 1
        assert get_word_paragraph_text(p) == "Alice"

    def test_multiple_placeholders_both_fragmented(self):
        """Multiple fragmented placeholders in one paragraph."""
        p = _make_word_paragraph(
            ["Hello {{", "name", "}}, you have {{", "count", "}} messages."]
        )
        assert (
            get_word_paragraph_text(p) == "Hello {{name}}, you have {{count}} messages."
        )

        count = replace_in_word_paragraph(p, "{{name}}", "Bob")
        assert count == 1
        result = get_word_paragraph_text(p)
        assert "Bob" in result
        assert "{{count}}" in result

    def test_adjacent_replacements(self):
        """Multiple occurrences of same pattern."""
        p = _make_word_paragraph(["aa", "aa", "aa"])
        assert get_word_paragraph_text(p) == "aaaaaa"

        count = replace_in_word_paragraph(p, "aa", "X")
        assert count == 3
        assert get_word_paragraph_text(p) == "XXX"

    def test_replacement_longer_than_original(self):
        """Replace with longer text."""
        p = _make_word_paragraph(["{{", "x", "}}"])
        count = replace_in_word_paragraph(p, "{{x}}", "REPLACEMENT")
        assert count == 1
        assert get_word_paragraph_text(p) == "REPLACEMENT"

    def test_replacement_shorter_than_original(self):
        """Replace with shorter text."""
        p = _make_word_paragraph(["{{", "placeholder", "}}"])
        count = replace_in_word_paragraph(p, "{{placeholder}}", "Y")
        assert count == 1
        assert get_word_paragraph_text(p) == "Y"

    def test_replacement_empty(self):
        """Replace with empty string (deletion)."""
        p = _make_word_paragraph(["Before", "{{delete}}", "After"])
        count = replace_in_word_paragraph(p, "{{delete}}", "")
        assert count == 1
        assert get_word_paragraph_text(p) == "BeforeAfter"

    def test_no_match_returns_zero(self):
        """No matches returns zero and doesn't modify text."""
        p = _make_word_paragraph(["Hello", "World"])
        original = get_word_paragraph_text(p)

        count = replace_in_word_paragraph(p, "{{notfound}}", "X")
        assert count == 0
        assert get_word_paragraph_text(p) == original

    def test_preserves_text_in_single_run(self):
        """Simple case - single run, complete match."""
        p = _make_word_paragraph(["{{name}}"])
        count = replace_in_word_paragraph(p, "{{name}}", "Jane")
        assert count == 1
        assert get_word_paragraph_text(p) == "Jane"


# =============================================================================
# PowerPoint Paragraph Tests (a:p / a:r / a:t)
# =============================================================================


def _make_ppt_paragraph(run_texts: list[str]) -> etree._Element:
    """Create a PowerPoint paragraph with multiple runs, each containing text."""
    nsmap = {"a": NS_DRAWINGML}
    p = etree.Element(f"{{{NS_DRAWINGML}}}p", nsmap=nsmap)
    for text in run_texts:
        r = etree.SubElement(p, f"{{{NS_DRAWINGML}}}r")
        t = etree.SubElement(r, f"{{{NS_DRAWINGML}}}t")
        t.text = text
    return p


class TestPPTFragmentedText:
    """Test find/replace with fragmented PowerPoint text."""

    def test_placeholder_split_across_two_runs(self):
        """{{title}} split across runs should be replaced."""
        p = _make_ppt_paragraph(["{{", "title}}"])
        assert get_ppt_paragraph_text(p) == "{{title}}"

        count = replace_in_ppt_paragraph(p, "{{title}}", "Slide 1")
        assert count == 1
        assert get_ppt_paragraph_text(p) == "Slide 1"

    def test_placeholder_split_across_three_runs(self):
        """{{title}} split as ['{{', 'title', '}}'] should be replaced."""
        p = _make_ppt_paragraph(["{{", "title", "}}"])
        count = replace_in_ppt_paragraph(p, "{{title}}", "My Presentation")
        assert count == 1
        assert get_ppt_paragraph_text(p) == "My Presentation"

    def test_multiple_replacements(self):
        """Multiple occurrences in PPT paragraph."""
        p = _make_ppt_paragraph(["{{x}}", " and ", "{{x}}"])
        count = replace_in_ppt_paragraph(p, "{{x}}", "Y")
        assert count == 2
        assert get_ppt_paragraph_text(p) == "Y and Y"


# =============================================================================
# xml:space="preserve" Attribute Tests
# =============================================================================


class TestXmlSpacePreserve:
    """Test xml:space='preserve' attribute handling."""

    def test_adds_preserve_for_leading_space(self):
        """Leading space requires xml:space='preserve'."""
        t = etree.Element("t")
        _set_text_with_space_preserve(t, " hello")
        assert t.text == " hello"
        assert t.get("{http://www.w3.org/XML/1998/namespace}space") == "preserve"

    def test_adds_preserve_for_trailing_space(self):
        """Trailing space requires xml:space='preserve'."""
        t = etree.Element("t")
        _set_text_with_space_preserve(t, "hello ")
        assert t.text == "hello "
        assert t.get("{http://www.w3.org/XML/1998/namespace}space") == "preserve"

    def test_removes_preserve_when_not_needed(self):
        """Remove xml:space='preserve' when no longer needed."""
        t = etree.Element("t")
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = " old "

        _set_text_with_space_preserve(t, "new")
        assert t.text == "new"
        assert "{http://www.w3.org/XML/1998/namespace}space" not in t.attrib

    def test_no_preserve_for_no_whitespace(self):
        """No xml:space='preserve' for text without leading/trailing whitespace."""
        t = etree.Element("t")
        _set_text_with_space_preserve(t, "hello")
        assert t.text == "hello"
        assert "{http://www.w3.org/XML/1998/namespace}space" not in t.attrib

    def test_preserve_for_empty_string(self):
        """Empty string doesn't need xml:space='preserve'."""
        t = etree.Element("t")
        _set_text_with_space_preserve(t, "")
        assert t.text == ""
        assert "{http://www.w3.org/XML/1998/namespace}space" not in t.attrib


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases in text redistribution."""

    def test_empty_paragraph(self):
        """Empty paragraph returns zero."""
        p = _make_word_paragraph([])
        count = replace_in_word_paragraph(p, "{{x}}", "Y")
        assert count == 0

    def test_empty_runs(self):
        """Paragraph with empty runs."""
        p = _make_word_paragraph(["", "{{name}}", ""])
        count = replace_in_word_paragraph(p, "{{name}}", "X")
        assert count == 1
        assert get_word_paragraph_text(p) == "X"

    def test_very_fragmented(self):
        """Each character in its own run."""
        p = _make_word_paragraph(list("{{name}}"))
        assert get_word_paragraph_text(p) == "{{name}}"

        count = replace_in_word_paragraph(p, "{{name}}", "Y")
        assert count == 1
        assert get_word_paragraph_text(p) == "Y"

    def test_overlapping_pattern_search(self):
        """Pattern that could overlap with itself."""
        p = _make_word_paragraph(["aaa", "a"])
        # "aaaa" contains "aa" twice (positions 0-1 and 2-3)
        # Python str.replace does non-overlapping replacement, so:
        # "aaaa".replace("aa", "X") == "XX"
        count = replace_in_word_paragraph(p, "aa", "X")
        assert count == 2
        assert get_word_paragraph_text(p) == "XX"
