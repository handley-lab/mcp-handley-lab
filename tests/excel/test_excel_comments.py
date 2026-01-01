"""Tests for Excel comments operations."""

import io

import pytest

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.ops.comments import (
    add_comment,
    delete_comment,
    get_comment,
    list_comments,
    update_comment,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestListComments:
    """Tests for list_comments."""

    def test_list_comments_empty(self) -> None:
        """New sheet has no comments."""
        pkg = ExcelPackage.new()

        comments = list_comments(pkg, "Sheet1")

        assert comments == []

    def test_list_comments_after_add(self) -> None:
        """List comments returns added comments."""
        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "Test comment")

        comments = list_comments(pkg, "Sheet1")

        assert len(comments) == 1
        assert comments[0].ref == "A1"
        assert comments[0].text == "Test comment"

    def test_list_comments_multiple(self) -> None:
        """List multiple comments."""
        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "First comment")
        add_comment(pkg, "Sheet1", "B2", "Second comment")
        add_comment(pkg, "Sheet1", "C3", "Third comment")

        comments = list_comments(pkg, "Sheet1")

        assert len(comments) == 3
        refs = {c.ref for c in comments}
        assert refs == {"A1", "B2", "C3"}


class TestGetComment:
    """Tests for get_comment."""

    def test_get_comment_exists(self) -> None:
        """Get existing comment."""
        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "Test comment", author="Alice")

        comment = get_comment(pkg, "Sheet1", "A1")

        assert comment is not None
        assert comment.ref == "A1"
        assert comment.text == "Test comment"
        assert comment.author == "Alice"

    def test_get_comment_not_found(self) -> None:
        """Get non-existent comment returns None."""
        pkg = ExcelPackage.new()

        comment = get_comment(pkg, "Sheet1", "A1")

        assert comment is None

    def test_get_comment_case_insensitive(self) -> None:
        """Cell ref is case insensitive."""
        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "Test")

        comment = get_comment(pkg, "Sheet1", "a1")

        assert comment is not None
        assert comment.ref == "A1"


class TestAddComment:
    """Tests for add_comment."""

    def test_add_comment_simple(self) -> None:
        """Add simple comment."""
        pkg = ExcelPackage.new()

        comment = add_comment(pkg, "Sheet1", "A1", "Hello world")

        assert comment.ref == "A1"
        assert comment.text == "Hello world"
        assert comment.author == "Author"  # default

    def test_add_comment_with_author(self) -> None:
        """Add comment with custom author."""
        pkg = ExcelPackage.new()

        comment = add_comment(pkg, "Sheet1", "B2", "My note", author="Bob")

        assert comment.author == "Bob"

    def test_add_comment_creates_parts(self) -> None:
        """Adding comment creates comments.xml and VML drawing."""
        pkg = ExcelPackage.new()

        add_comment(pkg, "Sheet1", "A1", "Test")

        # Should have comments part
        comments_found = False
        vml_found = False
        for partname in pkg.iter_partnames():
            if "comments" in partname:
                comments_found = True
            if "vmlDrawing" in partname:
                vml_found = True

        assert comments_found
        assert vml_found

    def test_add_comment_adds_legacy_drawing_ref(self) -> None:
        """Adding comment adds legacyDrawing reference to sheet."""
        pkg = ExcelPackage.new()

        add_comment(pkg, "Sheet1", "A1", "Test")

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        legacy_drawing = sheet_xml.find(qn("x:legacyDrawing"))
        assert legacy_drawing is not None
        assert legacy_drawing.get(qn("r:id")) is not None

    def test_add_comment_multiple_same_author(self) -> None:
        """Multiple comments from same author share author entry."""
        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "First", author="Alice")
        add_comment(pkg, "Sheet1", "B2", "Second", author="Alice")

        comments = list_comments(pkg, "Sheet1")
        assert len(comments) == 2
        assert all(c.author == "Alice" for c in comments)

    def test_add_comment_multiple_authors(self) -> None:
        """Multiple comments from different authors."""
        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "From Alice", author="Alice")
        add_comment(pkg, "Sheet1", "B2", "From Bob", author="Bob")

        comments = list_comments(pkg, "Sheet1")
        authors = {c.author for c in comments}
        assert authors == {"Alice", "Bob"}

    def test_add_comment_has_id(self) -> None:
        """CommentInfo has content-addressed ID."""
        pkg = ExcelPackage.new()

        comment = add_comment(pkg, "Sheet1", "A1", "Test")

        assert comment.id is not None
        assert comment.id.startswith("comment_")

    def test_add_comment_whitespace_preserved(self) -> None:
        """Comments with leading/trailing whitespace preserved."""
        pkg = ExcelPackage.new()

        add_comment(pkg, "Sheet1", "A1", "  spaces around  ")

        got = get_comment(pkg, "Sheet1", "A1")
        assert got.text == "  spaces around  "

    def test_add_comment_persists(self) -> None:
        """Comment persists through save/load."""
        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "Persistent comment", author="Tester")

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        comments = list_comments(pkg2, "Sheet1")
        assert len(comments) == 1
        assert comments[0].text == "Persistent comment"
        assert comments[0].author == "Tester"


class TestDeleteComment:
    """Tests for delete_comment."""

    def test_delete_comment(self) -> None:
        """Delete existing comment."""
        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "To delete")

        delete_comment(pkg, "Sheet1", "A1")

        assert get_comment(pkg, "Sheet1", "A1") is None

    def test_delete_comment_not_found(self) -> None:
        """Delete non-existent comment raises KeyError."""
        pkg = ExcelPackage.new()

        with pytest.raises(KeyError, match="No comment"):
            delete_comment(pkg, "Sheet1", "A1")

    def test_delete_comment_preserves_others(self) -> None:
        """Deleting one comment preserves others."""
        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "Keep")
        add_comment(pkg, "Sheet1", "B2", "Delete")
        add_comment(pkg, "Sheet1", "C3", "Keep")

        delete_comment(pkg, "Sheet1", "B2")

        comments = list_comments(pkg, "Sheet1")
        assert len(comments) == 2
        refs = {c.ref for c in comments}
        assert refs == {"A1", "C3"}

    def test_delete_last_comment_cleans_up(self) -> None:
        """Deleting last comment removes comments part."""
        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "Only one")

        delete_comment(pkg, "Sheet1", "A1")

        # No comments parts should remain
        for partname in pkg.iter_partnames():
            assert "comments" not in partname.lower()

    def test_delete_last_comment_cleans_up_relationships(self) -> None:
        """Deleting last comment removes relationships to avoid orphans."""
        from mcp_handley_lab.microsoft.excel.constants import RT

        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "Only one")

        # Get sheet path and verify relationships exist
        sheet_path = None
        for name, _rId, partname in pkg.get_sheet_paths():
            if name == "Sheet1":
                sheet_path = partname
                break

        rels = pkg.get_rels(sheet_path)
        assert rels.rId_for_reltype(RT.COMMENTS) is not None
        assert rels.rId_for_reltype(RT.VML_DRAWING) is not None

        delete_comment(pkg, "Sheet1", "A1")

        # Relationships should be cleaned up
        rels = pkg.get_rels(sheet_path)
        assert rels.rId_for_reltype(RT.COMMENTS) is None
        assert rels.rId_for_reltype(RT.VML_DRAWING) is None


class TestUpdateComment:
    """Tests for update_comment."""

    def test_update_comment(self) -> None:
        """Update comment text."""
        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "Original", author="Author")

        result = update_comment(pkg, "Sheet1", "A1", "Updated")

        assert result.text == "Updated"
        assert result.author == "Author"  # author preserved
        assert result.ref == "A1"

    def test_update_comment_get_reflects_change(self) -> None:
        """get_comment returns updated text."""
        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "Original")

        update_comment(pkg, "Sheet1", "A1", "New text")

        comment = get_comment(pkg, "Sheet1", "A1")
        assert comment.text == "New text"

    def test_update_comment_not_found(self) -> None:
        """Update non-existent comment raises KeyError."""
        pkg = ExcelPackage.new()

        with pytest.raises(KeyError, match="No comment"):
            update_comment(pkg, "Sheet1", "A1", "New text")

    def test_update_comment_persists(self) -> None:
        """Updated comment persists through save/load."""
        pkg = ExcelPackage.new()
        add_comment(pkg, "Sheet1", "A1", "Original")
        update_comment(pkg, "Sheet1", "A1", "Modified")

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        comment = get_comment(pkg2, "Sheet1", "A1")
        assert comment.text == "Modified"


class TestCommentInfo:
    """Tests for CommentInfo model."""

    def test_comment_info_fields(self) -> None:
        """CommentInfo has expected fields."""
        pkg = ExcelPackage.new()

        comment = add_comment(pkg, "Sheet1", "A1", "Test", author="Alice")

        assert comment.id is not None
        assert comment.ref == "A1"
        assert comment.text == "Test"
        assert comment.author == "Alice"
