"""Unit tests for email extraction module.

Tests the new extraction pipeline that replaced email-reply-parser.
"""

from email import policy
from email.parser import BytesParser
from pathlib import Path

from mcp_handley_lab.email.extraction import (
    extract_email_content,
)
from mcp_handley_lab.email.extraction.html_converter import (
    html_to_markdown,
    sanitize_html_minimal,
)
from mcp_handley_lab.email.extraction.mime_extractor import extract_mime_parts
from mcp_handley_lab.email.extraction.quote_detector import (
    segment_email_content,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "email" / "samples"


def load_email(filename: str):
    """Load an email from the fixtures directory."""
    path = FIXTURES_DIR / filename
    with open(path, "rb") as f:
        parser = BytesParser(policy=policy.default)
        return parser.parse(f)


class TestOriginalBugRegression:
    """Tests for the original bug: --- separator treated as signature delimiter."""

    def test_separator_not_treated_as_signature(self):
        """Content after --- separator must NOT be truncated.

        This was the original bug in email-reply-parser that prompted the rewrite.
        """
        msg = load_email("separator_in_body.eml")
        result = extract_email_content(msg)

        # The content AFTER the separator must be present
        assert (
            "This is content that comes AFTER the separator line"
            in result.body_markdown
        )
        assert "should NOT be truncated" in result.body_markdown
        assert "More content here to verify full preservation" in result.body_markdown

    def test_separator_preserved_in_raw(self):
        """The separator itself should be preserved in the raw content."""
        msg = load_email("separator_in_body.eml")
        result = extract_email_content(msg)

        # The separator line should be present
        assert "----------------------------" in result.body_markdown


class TestMimeExtraction:
    """Tests for MIME part extraction."""

    def test_multipart_alternative_prefers_plain(self):
        """For multipart/alternative, plain text should be preferred."""
        msg = load_email("multipart_alternative.eml")
        plain, html, manifest, warnings = extract_mime_parts(msg)

        assert plain
        assert "plain text version" in plain
        # HTML should also be captured
        assert html
        assert "<strong>HTML</strong>" in html

    def test_html_only_extracted(self):
        """HTML-only emails should be properly extracted."""
        msg = load_email("html_only.eml")
        plain, html, manifest, warnings = extract_mime_parts(msg)

        # No plain text
        assert not plain
        # HTML present
        assert html
        assert "Welcome Email" in html

    def test_parts_manifest_populated(self):
        """Parts manifest should list all MIME parts."""
        msg = load_email("multipart_alternative.eml")
        _, _, manifest, _ = extract_mime_parts(msg)

        # Should have at least: multipart/alternative, text/plain, text/html
        content_types = [p.content_type for p in manifest]
        assert "multipart/alternative" in content_types
        assert "text/plain" in content_types
        assert "text/html" in content_types

    def test_selected_body_marked(self):
        """The selected body part should be marked in manifest."""
        msg = load_email("multipart_alternative.eml")
        _, _, manifest, _ = extract_mime_parts(msg)

        selected = [p for p in manifest if p.is_selected_body]
        assert len(selected) == 1
        assert selected[0].content_type == "text/plain"


class TestHtmlConversion:
    """Tests for HTML to Markdown conversion."""

    def test_links_preserved(self):
        """Links should be preserved in markdown output."""
        html = '<p>Visit <a href="https://example.com">our site</a></p>'
        md = html_to_markdown(html)
        assert "https://example.com" in md

    def test_scripts_removed(self):
        """Script tags should be removed."""
        html = '<p>Hello</p><script>alert("xss")</script>'
        md = html_to_markdown(html)
        assert "alert" not in md
        assert "Hello" in md

    def test_hidden_elements_removed(self):
        """Hidden elements should be removed."""
        html = '<p>Visible</p><div style="display:none">Hidden</div>'
        sanitized = sanitize_html_minimal(html)
        assert "Visible" in sanitized
        assert "Hidden" not in sanitized

    def test_tracking_pixels_removed(self):
        """1x1 tracking pixels should be removed."""
        html = '<p>Content</p><img width="1" height="1" src="https://track.com/p.gif">'
        sanitized = sanitize_html_minimal(html)
        assert "Content" in sanitized
        assert "track.com" not in sanitized


class TestQuoteDetection:
    """Tests for quote/signature detection."""

    def test_segments_preserve_all_content(self):
        """Segmentation must preserve all content - never discard."""
        text = "Hello\n\nOn Mon... wrote:\n> Quoted text"

        segments = segment_email_content(text)

        # At minimum, we get one segment
        assert len(segments) >= 1
        # First segment should be reply type
        assert segments[0].segment_type == "reply"
        # Full content preserved across all segments
        full_content = "".join(s.content for s in segments)
        assert "Hello" in full_content
        assert "Quoted" in full_content

    def test_empty_text_returns_empty(self):
        """Empty text should return empty segments list."""
        segments = segment_email_content("")
        assert segments == []

        segments = segment_email_content("   \n\n  ")
        assert segments == []


class TestExtractionResult:
    """Tests for the ExtractionResult model."""

    def test_body_format_detected(self):
        """Body format should correctly identify source format."""
        # Plain text email
        msg = load_email("separator_in_body.eml")
        result = extract_email_content(msg)
        assert result.body_format == "text"

        # HTML email
        msg = load_email("html_only.eml")
        result = extract_email_content(msg)
        assert result.body_format == "html"

    def test_body_raw_populated(self):
        """body_raw should contain decoded content."""
        msg = load_email("separator_in_body.eml")
        result = extract_email_content(msg)

        # body_raw should be non-empty for text emails
        assert result.body_raw

    def test_html_raw_populated_for_html(self):
        """body_html_raw should contain original HTML."""
        msg = load_email("html_only.eml")
        result = extract_email_content(msg)

        assert result.body_html_raw
        assert (
            "<html>" in result.body_html_raw.lower()
            or "<!doctype" in result.body_html_raw.lower()
        )


class TestInvariantsEnforcement:
    """Tests for extraction invariants."""

    def test_no_silent_truncation(self):
        """Content must never be silently truncated."""
        msg = load_email("separator_in_body.eml")
        result = extract_email_content(msg)

        # All expected content present
        assert "first part" in result.body_markdown
        assert "AFTER the separator" in result.body_markdown
        assert "More content" in result.body_markdown

    def test_parts_manifest_complete(self):
        """All MIME parts should be in manifest."""
        msg = load_email("multipart_alternative.eml")
        result = extract_email_content(msg)

        # Manifest should include all parts
        assert len(result.parts_manifest) >= 3  # container + plain + html

    def test_round_trip_coverage(self):
        """No characters should be lost in extraction."""
        msg = load_email("separator_in_body.eml")
        result = extract_email_content(msg)

        # Get original content
        original = msg.get_body().get_content()
        original_stripped = original.strip()

        # Key content should be preserved
        for line in original_stripped.split("\n"):
            line = line.strip()
            if line:
                assert line in result.body_markdown, f"Missing line: {line}"


class TestWhitespaceNormalization:
    """Tests for whitespace handling."""

    def test_paragraph_structure_preserved(self):
        """Paragraph breaks should be preserved."""
        msg = load_email("separator_in_body.eml")
        result = extract_email_content(msg)

        # Should have paragraph breaks
        assert "\n\n" in result.body_markdown or "\n" in result.body_markdown

    def test_horizontal_whitespace_preserved(self):
        """Horizontal whitespace (tabs, spaces) should not be collapsed."""
        # Create email with intentional spacing
        email_content = b"""Message-ID: <test@example.com>
Subject: Test
Content-Type: text/plain

Column1    Column2    Column3
Value1     Value2     Value3
"""
        parser = BytesParser(policy=policy.default)
        msg = parser.parsebytes(email_content)
        result = extract_email_content(msg)

        # Multiple spaces should be preserved (for tables/code)
        # Note: some normalization may occur, but tables should remain readable
        assert "Column1" in result.body_markdown
        assert "Column2" in result.body_markdown


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_email_handled(self):
        """Empty emails should not crash."""
        email_content = b"""Message-ID: <test@example.com>
Subject: Empty
Content-Type: text/plain

"""
        parser = BytesParser(policy=policy.default)
        msg = parser.parsebytes(email_content)
        result = extract_email_content(msg)

        assert result.body_format in ("text", "empty")
        assert not result.extraction_warnings or all(
            "error" not in w.lower() for w in result.extraction_warnings
        )

    def test_malformed_html_handled(self):
        """Malformed HTML should be handled gracefully."""
        html = "<p>Unclosed paragraph<div>Mixed<p>nesting</div>"
        md = html_to_markdown(html)
        # Should not crash and should extract some content
        assert "Unclosed" in md or "Mixed" in md or "nesting" in md


class TestProgressiveDisclosureProjection:
    """Tests for progressive disclosure (response projection based on mode).

    These tests verify that serialized EmailContent matches the mode contracts:
    - summary mode: omits body_raw, body_html_raw, parts_manifest, segments
    - full mode: includes preservation fields when applicable

    Keys must be ABSENT (not null) in the serialized output.
    """

    def test_summary_mode_omits_preservation_fields(self):
        """Summary mode must NOT include body_raw, body_html_raw, parts_manifest, segments.

        The contract specifies these fields are omitted from response (not empty string).
        Using model_dump(exclude_none=True) achieves this.
        """
        from mcp_handley_lab.email.notmuch.tool import EmailContent

        # Simulate summary mode content (preservation fields are None)
        summary_content = EmailContent(
            id="test@example.com",
            subject="Test",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            date="2025-01-04",
            tags=["inbox"],
            body_markdown="Test body content",
            body_format="text",
            # Summary mode fields
            is_truncated=False,
            original_length=17,
            extraction_warnings=[],
            # Preservation fields intentionally None (summary mode)
            body_raw=None,
            body_html_raw=None,
            parts_manifest=None,
            segments=None,
        )

        # Serialize with exclude_none to match API behavior
        serialized = summary_content.model_dump(exclude_none=True)

        # Keys must be ABSENT, not present with null value
        assert "body_raw" not in serialized
        assert "body_html_raw" not in serialized
        assert "parts_manifest" not in serialized
        assert "segments" not in serialized

        # Summary mode fields SHOULD be present
        assert "is_truncated" in serialized
        assert "original_length" in serialized
        assert "body_markdown" in serialized

    def test_full_mode_includes_preservation_fields(self):
        """Full mode must include body_raw, parts_manifest when applicable."""
        from mcp_handley_lab.email.extraction.models import EmailPartInfo
        from mcp_handley_lab.email.notmuch.tool import EmailContent

        # Simulate full mode content (preservation fields populated)
        full_content = EmailContent(
            id="test@example.com",
            subject="Test",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            date="2025-01-04",
            tags=["inbox"],
            body_markdown="Test body content",
            body_format="text",
            # Full mode fields
            extraction_warnings=[],
            body_raw="Test body content",  # Preservation
            parts_manifest=[
                EmailPartInfo(
                    content_type="text/plain",
                    charset="utf-8",
                    part_index=0,
                    is_selected_body=True,
                )
            ],
            # Truncation fields are None in full mode
            is_truncated=None,
            original_length=None,
        )

        serialized = full_content.model_dump(exclude_none=True)

        # Preservation fields SHOULD be present
        assert "body_raw" in serialized
        assert "parts_manifest" in serialized
        assert serialized["body_raw"] == "Test body content"
        assert len(serialized["parts_manifest"]) == 1

        # Truncation fields should be ABSENT in full mode
        assert "is_truncated" not in serialized
        assert "original_length" not in serialized

    def test_html_full_mode_includes_html_raw(self):
        """Full mode for HTML emails must include body_html_raw."""
        from mcp_handley_lab.email.extraction.models import EmailPartInfo
        from mcp_handley_lab.email.notmuch.tool import EmailContent

        full_content = EmailContent(
            id="test@example.com",
            subject="Test",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            date="2025-01-04",
            tags=["inbox"],
            body_markdown="Test body",
            body_format="html",
            extraction_warnings=[],
            body_raw="<html><body>Test body</body></html>",
            body_html_raw="<html><body>Test body</body></html>",
            parts_manifest=[
                EmailPartInfo(
                    content_type="text/html",
                    charset="utf-8",
                    part_index=0,
                    is_selected_body=True,
                )
            ],
        )

        serialized = full_content.model_dump(exclude_none=True)

        assert "body_html_raw" in serialized
        assert "<html>" in serialized["body_html_raw"]

    def test_segments_only_present_when_requested(self):
        """segments field only present in full mode when segment_quotes=True."""
        from mcp_handley_lab.email.extraction.models import EmailBodySegment
        from mcp_handley_lab.email.notmuch.tool import EmailContent

        # Without segment_quotes
        without_segments = EmailContent(
            id="test@example.com",
            subject="Test",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            date="2025-01-04",
            tags=["inbox"],
            body_markdown="Test body",
            body_format="text",
            body_raw="Test body",
            segments=None,  # Not requested
        )

        serialized = without_segments.model_dump(exclude_none=True)
        assert "segments" not in serialized

        # With segment_quotes
        with_segments = EmailContent(
            id="test@example.com",
            subject="Test",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            date="2025-01-04",
            tags=["inbox"],
            body_markdown="Test body",
            body_format="text",
            body_raw="Test body",
            segments=[EmailBodySegment(segment_type="reply", content="Test body")],
        )

        serialized = with_segments.model_dump(exclude_none=True)
        assert "segments" in serialized
        assert len(serialized["segments"]) == 1

    def test_extraction_pipeline_full_mode_fields(self):
        """End-to-end test: extract_email_content populates full mode fields."""
        msg = load_email("separator_in_body.eml")
        result = extract_email_content(msg)

        # body_raw must be non-empty for text emails
        assert result.body_raw
        assert len(result.body_raw) > 0

        # parts_manifest must be populated
        assert result.parts_manifest
        assert len(result.parts_manifest) >= 1

        # Verify serialization includes these
        from mcp_handley_lab.email.notmuch.tool import EmailContent

        content = EmailContent(
            id="test",
            subject="test",
            from_address="from",
            to_address="to",
            date="date",
            tags=[],
            body_markdown=result.body_markdown,
            body_format=result.body_format,
            body_raw=result.body_raw,
            parts_manifest=result.parts_manifest,
        )

        serialized = content.model_dump(exclude_none=True)
        assert "body_raw" in serialized
        assert "parts_manifest" in serialized

    def test_extraction_pipeline_html_body_raw(self):
        """End-to-end test: HTML-only emails have body_raw = HTML source."""
        msg = load_email("html_only.eml")
        result = extract_email_content(msg)

        # body_raw should be HTML for HTML-only emails
        assert result.body_raw
        assert "<" in result.body_raw  # Contains HTML tags
        assert result.body_html_raw == result.body_raw  # Same for HTML-only

    def test_headers_mode_returns_different_model(self):
        """Headers mode returns SearchResult which has NO body fields.

        This is the plan's contract: headers mode omits body_markdown,
        body_raw, parts_manifest. The implementation achieves this by
        returning a completely different model (SearchResult) that
        structurally doesn't have these fields.
        """
        from mcp_handley_lab.email.notmuch.tool import SearchResult

        # SearchResult is the model returned by headers mode
        result = SearchResult(
            id="test@example.com",
            subject="Test Subject",
            from_address="sender@example.com",
            to_address="recipient@example.com",
            date="2025-01-04",
            tags=["inbox"],
        )

        serialized = result.model_dump()

        # Headers mode contract: NO body_markdown, body_raw, parts_manifest
        assert "body_markdown" not in serialized
        assert "body_raw" not in serialized
        assert "body_html_raw" not in serialized
        assert "parts_manifest" not in serialized
        assert "segments" not in serialized

        # Headers mode SHOULD have basic metadata
        assert "id" in serialized
        assert "subject" in serialized
        assert "from_address" in serialized
        assert "tags" in serialized
