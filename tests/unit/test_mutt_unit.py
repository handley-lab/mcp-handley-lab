"""Tests for mutt tool."""
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from mcp_handley_lab.email.mutt.tool import (
    _build_mutt_command,
    list_folders,
    server_info,
)
from mcp_handley_lab.email.mutt_aliases.tool import (
    add_contact,
    remove_contact,
)


class TestMuttContactManagement:
    """Test mutt contact management functions."""

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.home")
    @patch("mcp_handley_lab.email.mutt_aliases.tool.run_command")
    def test_add_contact_individual(self, mock_run_command, mock_home, mock_file):
        """Test adding an individual contact."""
        mock_home.return_value = Path("/home/test")
        mock_run_command.return_value = (b'alias_file="~/.mutt/addressbook"', b"")

        result = add_contact("john_doe", "john@example.com", "John Doe")

        assert "Added contact: john_doe (John Doe)" in result.message
        mock_file.assert_called_once()
        mock_file().write.assert_called_once_with(
            'alias john_doe "John Doe" <john@example.com>\n'
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.home")
    @patch("mcp_handley_lab.email.mutt_aliases.tool.run_command")
    def test_add_contact_group(self, mock_run_command, mock_home, mock_file):
        """Test adding a group contact."""
        mock_home.return_value = Path("/home/test")
        mock_run_command.return_value = (b'alias_file="~/.mutt/addressbook"', b"")

        result = add_contact(
            "gw_team", "alice@cam.ac.uk,bob@cam.ac.uk", "GW Project Team"
        )

        assert "Added contact: gw_team (GW Project Team)" in result.message
        mock_file().write.assert_called_once_with(
            'alias gw_team "GW Project Team" <alice@cam.ac.uk,bob@cam.ac.uk>\n'
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.home")
    @patch("mcp_handley_lab.email.mutt_aliases.tool.run_command")
    def test_add_contact_no_name(self, mock_run_command, mock_home, mock_file):
        """Test adding contact without name."""
        mock_home.return_value = Path("/home/test")
        mock_run_command.return_value = (b'alias_file="~/.mutt/addressbook"', b"")

        result = add_contact("simple", "test@example.com")

        assert "Added contact: simple (test@example.com)" in result.message
        mock_file().write.assert_called_once_with("alias simple test@example.com\n")

    def test_add_contact_validation(self):
        """Test input validation for add_contact."""
        with pytest.raises(ValueError, match="Both alias and email are required"):
            add_contact("", "test@example.com")

        with pytest.raises(ValueError, match="Both alias and email are required"):
            add_contact("test", "")

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='alias john_doe "John Doe" <john@example.com>\nalias gw_team "GW Team" <alice@cam.ac.uk>\n',
    )
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.home")
    @patch("mcp_handley_lab.email.mutt_aliases.tool.run_command")
    def test_remove_contact_success(
        self, mock_run_command, mock_home, mock_exists, mock_file
    ):
        """Test successfully removing a contact."""
        mock_home.return_value = Path("/home/test")
        mock_exists.return_value = True
        mock_run_command.return_value = (b'alias_file="~/.mutt/addressbook"', b"")

        # Mock readlines and write
        mock_file.return_value.readlines.return_value = [
            'alias john_doe "John Doe" <john@example.com>\n',
            'alias gw_team "GW Team" <alice@cam.ac.uk>\n',
        ]

        result = remove_contact("john_doe")

        assert "Removed contact: john_doe" in result.message
        # Should write back only the gw_team line
        mock_file.return_value.writelines.assert_called_once_with(
            ['alias gw_team "GW Team" <alice@cam.ac.uk>\n']
        )

    @patch("mcp_handley_lab.email.mutt_aliases.tool._find_contact_fuzzy")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='alias gw_team "GW Team" <alice@cam.ac.uk>\n',
    )
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.home")
    @patch("mcp_handley_lab.email.mutt_aliases.tool.run_command")
    def test_remove_contact_not_found(
        self, mock_run_command, mock_home, mock_exists, mock_file, mock_fuzzy
    ):
        """Test removing a contact that doesn't exist."""
        mock_home.return_value = Path("/home/test")
        mock_exists.return_value = True
        mock_run_command.return_value = (b'alias_file="~/.mutt/addressbook"', b"")

        mock_file.return_value.readlines.return_value = [
            'alias gw_team "GW Team" <alice@cam.ac.uk>\n'
        ]
        mock_fuzzy.return_value = []  # No fuzzy matches found

        with pytest.raises(ValueError, match="Contact 'nonexistent' not found"):
            remove_contact("nonexistent")

    def test_remove_contact_validation(self):
        """Test input validation for remove_contact."""
        with pytest.raises(ValueError, match="Alias is required"):
            remove_contact("")


class TestMuttFolderManagement:
    """Test mutt folder management functions."""

    @patch("mcp_handley_lab.email.mutt.tool.run_command")
    def test_list_folders_success(self, mock_run_command):
        """Test successfully listing folders."""
        mock_run_command.return_value = (
            b'mailboxes="INBOX Sent Archive Trash Projects/GW"',
            b"",
        )

        result = list_folders()

        assert result == ["INBOX", "Sent", "Archive", "Trash", "Projects/GW"]
        assert "INBOX" in result
        assert "Projects/GW" in result

    @patch("mcp_handley_lab.email.mutt.tool.run_command")
    def test_list_folders_no_config(self, mock_run_command):
        """Test listing folders when no config found."""
        mock_run_command.side_effect = RuntimeError(
            "Command failed with exit code 1: mailboxes: unknown variable"
        )

        with pytest.raises(
            RuntimeError,
            match="Command failed with exit code 1: mailboxes: unknown variable",
        ):
            list_folders()

    @patch("mcp_handley_lab.email.mutt.tool.run_command")
    def test_list_folders_empty(self, mock_run_command):
        """Test listing folders when no mailboxes configured."""
        mock_run_command.return_value = (b'mailboxes=""', b"")

        result = list_folders()

        assert result == []


class TestMuttServerInfo:
    """Test mutt server info function."""

    @patch("mcp_handley_lab.email.mutt.tool.run_command")
    def test_server_info_success(self, mock_run_command):
        """Test successful server info retrieval."""
        mock_run_command.return_value = (
            b"Mutt 2.2.14 (516568dc) (2025-02-20)\nOther info...",
            b"",
        )

        result = server_info()

        assert result.name == "Mutt Tool"
        assert "Mutt 2.2.14" in result.version
        assert result.status == "active"
        assert "compose" in str(result.capabilities)
        # add_contact is now in mutt_aliases, not mutt
        assert "server_info" in str(result.capabilities)

    @patch("mcp_handley_lab.email.mutt.tool.run_command")
    def test_server_info_mutt_not_found(self, mock_run_command):
        """Test server info when mutt not installed."""
        mock_run_command.side_effect = FileNotFoundError()

        with pytest.raises(FileNotFoundError):
            server_info()


class TestMuttContactWorkflows:
    """Test real-world contact management workflows."""

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.home")
    @patch("mcp_handley_lab.email.mutt_aliases.tool.run_command")
    def test_gw_project_workflow(self, mock_run_command, mock_home, mock_file):
        """Test adding GW project team contact."""
        mock_home.return_value = Path("/home/test")
        mock_run_command.return_value = (b'alias_file="~/.mutt/addressbook"', b"")

        # Add GW team
        result = add_contact(
            "gw_team",
            "alice@cam.ac.uk,bob@cam.ac.uk,carol@cam.ac.uk",
            "GW Project Team",
        )

        assert "Added contact: gw_team (GW Project Team)" in result.message

        # Verify the alias format is correct for mutt
        expected_alias = 'alias gw_team "GW Project Team" <alice@cam.ac.uk,bob@cam.ac.uk,carol@cam.ac.uk>\n'
        mock_file().write.assert_called_once_with(expected_alias)


class TestMuttCommandConstruction:
    """Test mutt command construction functions."""

    def test_build_mutt_command_attachment_ordering(self):
        """Test that attachments are ordered correctly with temp file."""
        # This test specifically addresses the bug where -i flag was placed after --
        # causing temp file path to be interpreted as recipient address
        cmd = _build_mutt_command(
            to="test@example.com",
            subject="Test Subject",
            attachments=["/path/to/file.pdf"],
            temp_file_path="/tmp/body.txt",
        )

        # Find the positions of key elements
        dash_h_pos = cmd.index("-H")
        temp_file_pos = cmd.index("/tmp/body.txt")
        dash_a_pos = cmd.index("-a")
        attachment_pos = cmd.index("/path/to/file.pdf")
        separator_pos = cmd.index("--")
        recipient_pos = cmd.index("test@example.com")

        # Verify correct ordering: -H comes before -a, and -- comes before recipient
        assert dash_h_pos < dash_a_pos, "'-H' flag should come before '-a' flag"
        assert (
            temp_file_pos < dash_a_pos
        ), "temp file path should come before attachments"
        assert dash_a_pos < separator_pos, "'-a' flag should come before '--' separator"
        assert (
            attachment_pos < separator_pos
        ), "attachment path should come before '--' separator"
        assert (
            separator_pos < recipient_pos
        ), "'--' separator should come before recipient"

    def test_build_mutt_command_no_attachments(self):
        """Test command construction without attachments."""
        cmd = _build_mutt_command(
            to="test@example.com",
            subject="Test Subject",
            temp_file_path="/tmp/body.txt",
        )

        # Should not contain attachment-related flags
        assert "-a" not in cmd
        assert "--" not in cmd
        assert "-H" in cmd
        assert "/tmp/body.txt" in cmd
        assert "test@example.com" in cmd

    def test_build_mutt_command_no_temp_file(self):
        """Test command construction without temp file."""
        cmd = _build_mutt_command(
            to="test@example.com",
            subject="Test Subject",
            attachments=["/path/to/file.pdf"],
        )

        # Should contain attachment flags but no -i flag
        assert "-a" in cmd
        assert "--" in cmd
        assert "/path/to/file.pdf" in cmd
        assert "-i" not in cmd
        assert "test@example.com" in cmd
