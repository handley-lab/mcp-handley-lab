"""Integration tests for email move functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp_handley_lab.email.common import mcp


class TestEmailMoveIntegration:
    """Integration tests for the email move tool."""

    @pytest.fixture
    def mock_maildir(self):
        """Create a temporary maildir structure for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            maildir = Path(tmpdir)

            # Create Hermes account structure
            hermes = maildir / "Hermes"
            (hermes / "INBOX" / "cur").mkdir(parents=True)
            (hermes / "INBOX" / "new").mkdir(parents=True)
            (hermes / "INBOX" / "tmp").mkdir(parents=True)
            (hermes / "Archive" / "cur").mkdir(parents=True)
            (hermes / "Archive" / "new").mkdir(parents=True)
            (hermes / "Archive" / "tmp").mkdir(parents=True)

            # Create Gmail account structure
            gmail = maildir / "Gmail"
            (gmail / "INBOX" / "cur").mkdir(parents=True)
            (gmail / "INBOX" / "new").mkdir(parents=True)
            (gmail / "INBOX" / "tmp").mkdir(parents=True)
            (gmail / "[Google Mail].Bin" / "cur").mkdir(parents=True)
            (gmail / "[Google Mail].Bin" / "new").mkdir(parents=True)
            (gmail / "[Google Mail].Bin" / "tmp").mkdir(parents=True)

            yield maildir

    @pytest.fixture
    def sample_emails(self, mock_maildir):
        """Create sample email files in the mock maildir."""
        # Create sample emails in Hermes/INBOX
        hermes_email1 = mock_maildir / "Hermes" / "INBOX" / "cur" / "test1.eml"
        hermes_email2 = mock_maildir / "Hermes" / "INBOX" / "cur" / "test2.eml"
        hermes_email1.write_text(
            "From: test@example.com\nSubject: Test 1\n\nHello World 1"
        )
        hermes_email2.write_text(
            "From: test@example.com\nSubject: Test 2\n\nHello World 2"
        )

        # Create sample email in Gmail/INBOX
        gmail_email = mock_maildir / "Gmail" / "INBOX" / "cur" / "test3.eml"
        gmail_email.write_text(
            "From: gmail@example.com\nSubject: Gmail Test\n\nGmail Hello"
        )

        return {
            "hermes_email1": str(hermes_email1),
            "hermes_email2": str(hermes_email2),
            "gmail_email": str(gmail_email),
        }

    @patch("mcp_handley_lab.email.notmuch.tool.run_command")
    @patch("mcp_handley_lab.email.notmuch.tool.new")
    async def test_move_hermes_inbox_to_archive(
        self, mock_new, mock_run_command, mock_maildir, sample_emails
    ):
        """Test moving emails from Hermes INBOX to Archive."""
        # Mock notmuch commands
        mock_run_command.side_effect = [
            # notmuch search --output=files query
            (
                f"{sample_emails['hermes_email1']}\n{sample_emails['hermes_email2']}\n".encode(),
                b"",
            ),
            # notmuch config get database.path
            (str(mock_maildir).encode(), b""),
        ]

        # Call the move function via MCP
        _, result = await mcp.call_tool(
            "move",
            {
                "message_ids": ["msg1@hermes.com", "msg2@hermes.com"],
                "destination_folder": "Archive",
            },
        )

        # Verify the result structure
        assert "message_ids" in result
        assert "destination_folder" in result
        assert "moved_files_count" in result
        assert "status" in result

        assert result["message_ids"] == ["msg1@hermes.com", "msg2@hermes.com"]
        assert result["destination_folder"] == "Archive"
        assert result["moved_files_count"] == 2
        assert "Successfully moved 2 email(s) to 'Archive'" in result["status"]

        # Verify emails were moved to correct location
        archive_new_dir = mock_maildir / "Hermes" / "Archive" / "new"
        moved_files = list(archive_new_dir.glob("*.eml"))
        assert len(moved_files) == 2

        # Verify original files no longer exist
        assert not Path(sample_emails["hermes_email1"]).exists()
        assert not Path(sample_emails["hermes_email2"]).exists()

        # Verify notmuch new was called to update index
        mock_new.assert_called_once()

    @patch("mcp_handley_lab.email.notmuch.tool.run_command")
    @patch("mcp_handley_lab.email.notmuch.tool.new")
    async def test_move_gmail_inbox_to_trash(
        self, mock_new, mock_run_command, mock_maildir, sample_emails
    ):
        """Test moving Gmail email to trash (should find [Google Mail].Bin)."""
        mock_run_command.side_effect = [
            # notmuch search --output=files query
            (f"{sample_emails['gmail_email']}\n".encode(), b""),
            # notmuch config get database.path
            (str(mock_maildir).encode(), b""),
        ]

        _, result = await mcp.call_tool(
            "move",
            {"message_ids": ["gmail_msg@gmail.com"], "destination_folder": "Trash"},
        )

        assert result["moved_files_count"] == 1
        assert "Successfully moved 1 email(s) to 'Trash'" in result["status"]

        # Verify email moved to Gmail's Bin folder
        bin_new_dir = mock_maildir / "Gmail" / "[Google Mail].Bin" / "new"
        moved_files = list(bin_new_dir.glob("*.eml"))
        assert len(moved_files) == 1

        # Verify original file no longer exists
        assert not Path(sample_emails["gmail_email"]).exists()

    @patch("mcp_handley_lab.email.notmuch.tool.run_command")
    async def test_move_to_nonexistent_folder_raises_error(
        self, mock_run_command, mock_maildir, sample_emails
    ):
        """Test that moving to nonexistent folder raises helpful error."""
        from mcp.server.fastmcp.exceptions import ToolError

        mock_run_command.side_effect = [
            # notmuch search --output=files query
            (f"{sample_emails['hermes_email1']}\n".encode(), b""),
            # notmuch config get database.path
            (str(mock_maildir).encode(), b""),
        ]

        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "move",
                {
                    "message_ids": ["msg1@hermes.com"],
                    "destination_folder": "NonExistent",
                },
            )

        error_msg = str(exc_info.value)
        assert (
            "No existing folder matching 'NonExistent' found in account 'Hermes'"
            in error_msg
        )
        assert "Available folders:" in error_msg

    @patch("mcp_handley_lab.email.notmuch.tool.run_command")
    async def test_move_no_emails_found_raises_error(
        self, mock_run_command, mock_maildir
    ):
        """Test that no matching emails raises FileNotFoundError."""
        from mcp.server.fastmcp.exceptions import ToolError

        mock_run_command.side_effect = [
            # notmuch search --output=files returns empty
            (b"", b""),
        ]

        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "move",
                {
                    "message_ids": ["nonexistent@example.com"],
                    "destination_folder": "Archive",
                },
            )

        assert "No email files found for the given message IDs" in str(exc_info.value)

    async def test_move_empty_message_ids_raises_error(self):
        """Test that empty message_ids list raises validation error."""
        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "move", {"message_ids": [], "destination_folder": "Archive"}
            )

        assert "List should have at least 1 item" in str(exc_info.value)

    @patch("mcp_handley_lab.email.notmuch.tool.run_command")
    @patch("mcp_handley_lab.email.notmuch.tool.new")
    async def test_move_handles_partial_success(
        self, mock_new, mock_run_command, mock_maildir, sample_emails
    ):
        """Test handling when only some message IDs are found."""
        # Only return one file for two message IDs
        mock_run_command.side_effect = [
            # notmuch search --output=files query (only finds one)
            (f"{sample_emails['hermes_email1']}\n".encode(), b""),
            # notmuch config get database.path
            (str(mock_maildir).encode(), b""),
        ]

        _, result = await mcp.call_tool(
            "move",
            {
                "message_ids": ["msg1@hermes.com", "missing@hermes.com"],
                "destination_folder": "Archive",
            },
        )

        # Should move 1 file but report about the missing one
        assert result["moved_files_count"] == 1
        assert len(result["message_ids"]) == 2
        assert (
            "Note: 1 of the requested message IDs could not be found"
            in result["status"]
        )

    @patch("mcp_handley_lab.email.notmuch.tool.run_command")
    async def test_move_os_rename_failure_raises_error(
        self, mock_run_command, mock_maildir, sample_emails
    ):
        """Test that OS-level rename failures are properly reported."""
        from mcp.server.fastmcp.exceptions import ToolError

        mock_run_command.side_effect = [
            (f"{sample_emails['hermes_email1']}\n".encode(), b""),
            (str(mock_maildir).encode(), b""),
        ]

        # Make the source file read-only to cause rename to fail
        source_path = Path(sample_emails["hermes_email1"])
        source_path.chmod(0o444)  # Read-only
        source_path.parent.chmod(0o444)  # Make parent dir read-only too

        try:
            with pytest.raises(ToolError) as exc_info:
                await mcp.call_tool(
                    "move",
                    {
                        "message_ids": ["msg1@hermes.com"],
                        "destination_folder": "Archive",
                    },
                )

            assert "Failed to move" in str(exc_info.value)
        finally:
            # Restore permissions for cleanup
            try:
                source_path.parent.chmod(0o755)
                source_path.chmod(0o644)
            except (OSError, FileNotFoundError):
                pass  # May already be cleaned up
