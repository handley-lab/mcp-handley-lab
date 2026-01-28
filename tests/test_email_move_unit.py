"""Unit tests for email move smart folder matching functionality."""

from pathlib import Path

import pytest

from mcp_handley_lab.email.notmuch.tool import _find_smart_destination


class TestFindSmartDestination:
    """Test the smart folder matching logic."""

    def test_empty_source_files_raises_error(self):
        """Should raise ValueError for empty source files."""
        with pytest.raises(ValueError, match="No source files provided"):
            _find_smart_destination([], Path("/mail"), "Archive")

    def test_exact_match_found(self, tmp_path):
        """Should return exact match when folder exists."""
        # Setup: create folder structure
        account_path = tmp_path / "Hermes"
        account_path.mkdir()
        archive_path = account_path / "Archive"
        archive_path.mkdir()
        (account_path / "INBOX").mkdir()

        # Create a mock source file
        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "Archive")

        assert result == archive_path

    def test_case_insensitive_mapping_trash_to_bin(self, tmp_path):
        """Should map 'Trash' to folders containing 'bin'."""
        # Setup: Gmail-style folder structure
        account_path = tmp_path / "Gmail"
        account_path.mkdir()
        bin_path = account_path / "[Google Mail].Bin"
        bin_path.mkdir()
        (account_path / "INBOX").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "Trash")

        assert result == bin_path

    def test_case_insensitive_mapping_archive_variations(self, tmp_path):
        """Should find archive folders with various naming patterns."""
        account_path = tmp_path / "Hermes"
        account_path.mkdir()
        archive_path = account_path / "Archive.2024"  # Contains 'archive'
        archive_path.mkdir()
        (account_path / "INBOX").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "Archive")

        assert result == archive_path

    def test_sent_folder_mapping(self, tmp_path):
        """Should map 'Sent' to folders containing 'sent'."""
        account_path = tmp_path / "Hermes"
        account_path.mkdir()
        sent_path = account_path / "Sent Items"
        sent_path.mkdir()
        (account_path / "INBOX").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "Sent")

        assert result == sent_path

    def test_drafts_folder_mapping(self, tmp_path):
        """Should map 'Drafts' to folders containing 'draft'."""
        account_path = tmp_path / "Gmail"
        account_path.mkdir()
        drafts_path = account_path / "[Gmail].Drafts"
        drafts_path.mkdir()
        (account_path / "INBOX").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "Drafts")

        assert result == drafts_path

    def test_spam_folder_mapping(self, tmp_path):
        """Should map 'Spam' to folders containing 'spam' or 'junk'."""
        account_path = tmp_path / "Hermes"
        account_path.mkdir()
        spam_path = account_path / "Junk Email"
        spam_path.mkdir()
        (account_path / "INBOX").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "Spam")

        assert result == spam_path

    def test_root_level_email_handling(self, tmp_path):
        """Should handle emails directly in maildir root."""
        archive_path = tmp_path / "Archive"
        archive_path.mkdir()

        # Email directly in root/cur/
        source_file = str(tmp_path / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "Archive")

        assert result == archive_path

    def test_no_match_raises_helpful_error(self, tmp_path):
        """Should raise FileNotFoundError with available folders when no match."""
        account_path = tmp_path / "Hermes"
        account_path.mkdir()
        (account_path / "INBOX").mkdir()
        (account_path / "Sent Items").mkdir()
        (account_path / "Drafts").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        with pytest.raises(FileNotFoundError) as exc_info:
            _find_smart_destination([source_file], tmp_path, "NonExistent")

        error_msg = str(exc_info.value)
        assert (
            "No existing folder matching 'NonExistent' found in account 'Hermes'"
            in error_msg
        )
        assert "Available folders:" in error_msg
        assert "INBOX" in error_msg
        assert "Sent Items" in error_msg

    def test_relative_to_error_propagates(self, tmp_path):
        """Should let relative_to() ValueError propagate with original message."""
        # Source file outside maildir_root should raise ValueError from relative_to()
        source_file = "/completely/different/path/test.eml"

        with pytest.raises(ValueError) as exc_info:
            _find_smart_destination([source_file], tmp_path, "Archive")

        # Should be the original pathlib error, not a custom message
        assert "is not in the subpath of" in str(
            exc_info.value
        ) or "does not start with" in str(exc_info.value)

    def test_multiple_matching_folders_returns_first_found(self, tmp_path):
        """Should return first matching folder when multiple exist."""
        account_path = tmp_path / "Hermes"
        account_path.mkdir()
        # Create multiple archive folders - should match first one found by iterdir()
        (account_path / "Archive.2023").mkdir()
        (account_path / "Archive.2024").mkdir()
        (account_path / "INBOX").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "Archive")

        # Should match one of the archive folders (iterdir() order is not guaranteed)
        assert result.name in ["Archive.2023", "Archive.2024"]
        assert result.parent == account_path

    def test_ignores_non_directory_files(self, tmp_path):
        """Should ignore regular files when looking for folder matches."""
        account_path = tmp_path / "Hermes"
        account_path.mkdir()
        (account_path / "INBOX").mkdir()

        # Create a file (not directory) that would match
        (account_path / "Archive.txt").touch()

        # Create the actual directory we want
        archive_dir = account_path / "Archive.backup"
        archive_dir.mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "Archive")

        # Should find the directory, not the file
        assert result == archive_dir

    def test_explicit_account_folder_path(self, tmp_path):
        """Should resolve explicit Account/Folder paths directly."""
        # Setup: create folder structure
        account_path = tmp_path / "Hermes"
        account_path.mkdir()
        archive_path = account_path / "Archive"
        archive_path.mkdir()
        (account_path / "INBOX").mkdir()

        # Create a different account with different Archive
        other_account = tmp_path / "Gmail"
        other_account.mkdir()
        other_archive = other_account / "Archive"
        other_archive.mkdir()
        (other_account / "INBOX").mkdir()

        # Source file in Gmail, but explicitly request Hermes/Archive
        source_file = str(other_account / "INBOX" / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "Hermes/Archive")

        assert result == archive_path

    def test_explicit_path_not_found_error(self, tmp_path):
        """Should raise helpful error when explicit Account/Folder path doesn't exist."""
        account_path = tmp_path / "Hermes"
        account_path.mkdir()
        (account_path / "INBOX").mkdir()
        (account_path / "Sent").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        with pytest.raises(FileNotFoundError) as exc_info:
            _find_smart_destination([source_file], tmp_path, "Hermes/NonExistent")

        error_msg = str(exc_info.value)
        assert "Explicit path 'Hermes/NonExistent' not found" in error_msg
        assert "Available folders in 'Hermes':" in error_msg
        assert "INBOX" in error_msg

    def test_expanded_aliases_sent_items(self, tmp_path):
        """Should match 'Sent Items' folder using 'sent' alias."""
        account_path = tmp_path / "Outlook"
        account_path.mkdir()
        sent_path = account_path / "Sent Items"
        sent_path.mkdir()
        (account_path / "INBOX").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "sent")

        assert result == sent_path

    def test_expanded_aliases_deleted_items(self, tmp_path):
        """Should match 'Deleted Items' folder using 'trash' alias."""
        account_path = tmp_path / "Outlook"
        account_path.mkdir()
        deleted_path = account_path / "Deleted Items"
        deleted_path.mkdir()
        (account_path / "INBOX").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "trash")

        assert result == deleted_path

    def test_expanded_aliases_all_mail(self, tmp_path):
        """Should match 'All Mail' folder using 'archive' alias."""
        account_path = tmp_path / "Gmail"
        account_path.mkdir()
        all_mail_path = account_path / "[Gmail].All Mail"
        all_mail_path.mkdir()
        (account_path / "INBOX").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "archive")

        assert result == all_mail_path

    def test_input_normalization(self, tmp_path):
        """Should normalize whitespace and multiple slashes in destination path."""
        account_path = tmp_path / "Hermes"
        account_path.mkdir()
        archive_path = account_path / "Archive"
        archive_path.mkdir()
        (account_path / "INBOX").mkdir()

        # Source file in same account for cleaner test
        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        # Test with extra whitespace and slashes
        result = _find_smart_destination(
            [source_file], tmp_path, "  Hermes//Archive/  "
        )

        assert result == archive_path

    def test_path_traversal_rejected(self, tmp_path):
        """Should reject path traversal attempts."""
        account_path = tmp_path / "Hermes"
        account_path.mkdir()
        (account_path / "INBOX").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        with pytest.raises(ValueError) as exc_info:
            _find_smart_destination([source_file], tmp_path, "../Hermes/Archive")

        assert "Invalid destination folder path" in str(exc_info.value)

    def test_absolute_path_rejected(self, tmp_path):
        """Should reject absolute paths."""
        account_path = tmp_path / "Hermes"
        account_path.mkdir()
        (account_path / "INBOX").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        with pytest.raises(ValueError) as exc_info:
            _find_smart_destination([source_file], tmp_path, "/tmp/Archive")

        assert "Invalid destination folder path" in str(exc_info.value)

    def test_tilde_path_rejected(self, tmp_path):
        """Should reject tilde-prefixed paths."""
        account_path = tmp_path / "Hermes"
        account_path.mkdir()
        (account_path / "INBOX").mkdir()

        source_file = str(account_path / "INBOX" / "cur" / "test.eml")

        with pytest.raises(ValueError) as exc_info:
            _find_smart_destination([source_file], tmp_path, "~/mail/Archive")

        assert "Invalid destination folder path" in str(exc_info.value)

    def test_root_level_alias_matching(self, tmp_path):
        """Should match aliases for root-level maildir source files."""
        # Setup: root-level maildir with Archive folder using Gmail naming
        (tmp_path / "cur").mkdir()
        all_mail_path = tmp_path / "[Gmail].All Mail"
        all_mail_path.mkdir()

        # Source file at root level (cur/test.eml, not Account/INBOX/cur/test.eml)
        source_file = str(tmp_path / "cur" / "test.eml")

        result = _find_smart_destination([source_file], tmp_path, "archive")

        assert result == all_mail_path
