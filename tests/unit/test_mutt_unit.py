"""Tests for mutt tool."""
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from mcp_handley_lab.email.mutt.tool import (
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
    @patch("mcp_handley_lab.email.mutt_aliases.tool._run_command")
    def test_add_contact_individual(self, mock_run_command, mock_home, mock_file):
        """Test adding an individual contact."""
        mock_home.return_value = Path("/home/test")
        mock_run_command.return_value = 'alias_file="~/.mutt/addressbook"'

        result = add_contact("john_doe", "john@example.com", "John Doe")

        assert "Added contact: john_doe (John Doe)" in result.message
        mock_file.assert_called_once()
        mock_file().write.assert_called_once_with(
            'alias john_doe "John Doe" <john@example.com>\n'
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.home")
    @patch("mcp_handley_lab.email.mutt_aliases.tool._run_command")
    def test_add_contact_group(self, mock_run_command, mock_home, mock_file):
        """Test adding a group contact."""
        mock_home.return_value = Path("/home/test")
        mock_run_command.return_value = 'alias_file="~/.mutt/addressbook"'

        result = add_contact(
            "gw_team", "alice@cam.ac.uk,bob@cam.ac.uk", "GW Project Team"
        )

        assert "Added contact: gw_team (GW Project Team)" in result.message
        mock_file().write.assert_called_once_with(
            'alias gw_team "GW Project Team" <alice@cam.ac.uk,bob@cam.ac.uk>\n'
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.home")
    @patch("mcp_handley_lab.email.mutt_aliases.tool._run_command")
    def test_add_contact_no_name(self, mock_run_command, mock_home, mock_file):
        """Test adding contact without name."""
        mock_home.return_value = Path("/home/test")
        mock_run_command.return_value = 'alias_file="~/.mutt/addressbook"'

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
    @patch("mcp_handley_lab.email.mutt_aliases.tool._run_command")
    def test_remove_contact_success(
        self, mock_run_command, mock_home, mock_exists, mock_file
    ):
        """Test successfully removing a contact."""
        mock_home.return_value = Path("/home/test")
        mock_exists.return_value = True
        mock_run_command.return_value = 'alias_file="~/.mutt/addressbook"'

        # Mock readlines and write
        mock_file.return_value.readlines.return_value = [
            'alias john_doe "John Doe" <john@example.com>\n',
            'alias gw_team "GW Team" <alice@cam.ac.uk>\n',
        ]

        result = remove_contact("john_doe")

        assert "Removed contact: john_doe" in result
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
    @patch("mcp_handley_lab.email.mutt_aliases.tool._run_command")
    def test_remove_contact_not_found(
        self, mock_run_command, mock_home, mock_exists, mock_file, mock_fuzzy
    ):
        """Test removing a contact that doesn't exist."""
        mock_home.return_value = Path("/home/test")
        mock_exists.return_value = True
        mock_run_command.return_value = 'alias_file="~/.mutt/addressbook"'

        mock_file.return_value.readlines.return_value = [
            'alias gw_team "GW Team" <alice@cam.ac.uk>\n'
        ]
        mock_fuzzy.return_value = []  # No fuzzy matches found

        result = remove_contact("nonexistent")

        assert "Contact 'nonexistent' not found" in result

    def test_remove_contact_validation(self):
        """Test input validation for remove_contact."""
        with pytest.raises(ValueError, match="Alias is required"):
            remove_contact("")


class TestMuttFolderManagement:
    """Test mutt folder management functions."""

    @patch("mcp_handley_lab.email.mutt.tool._run_command")
    def test_list_folders_success(self, mock_run_command):
        """Test successfully listing folders."""
        mock_run_command.return_value = (
            'mailboxes="INBOX Sent Archive Trash Projects/GW"'
        )

        result = list_folders()

        assert result == ["INBOX", "Sent", "Archive", "Trash", "Projects/GW"]
        assert "INBOX" in result
        assert "Projects/GW" in result

    @patch("mcp_handley_lab.email.mutt.tool._run_command")
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

    @patch("mcp_handley_lab.email.mutt.tool._run_command")
    def test_list_folders_empty(self, mock_run_command):
        """Test listing folders when no mailboxes configured."""
        mock_run_command.return_value = 'mailboxes=""'

        result = list_folders()

        assert result == []


class TestMuttServerInfo:
    """Test mutt server info function."""

    @patch("mcp_handley_lab.email.mutt.tool._run_command")
    def test_server_info_success(self, mock_run_command):
        """Test successful server info retrieval."""
        mock_run_command.return_value = (
            "Mutt 2.2.14 (516568dc) (2025-02-20)\nOther info..."
        )

        result = server_info()

        assert result.name == "Mutt Tool"
        assert "Mutt 2.2.14" in result.version
        assert result.status == "active"
        assert "compose_email" in str(result.capabilities)
        assert "compose_email" in str(result.capabilities)
        # add_contact is now in mutt_aliases, not mutt
        assert "server_info" in str(result.capabilities)

    @patch("mcp_handley_lab.email.mutt.tool._run_command")
    def test_server_info_mutt_not_found(self, mock_run_command):
        """Test server info when mutt not installed."""
        mock_run_command.side_effect = FileNotFoundError()

        with pytest.raises(FileNotFoundError):
            server_info()


class TestMuttContactWorkflows:
    """Test real-world contact management workflows."""

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.home")
    @patch("mcp_handley_lab.email.mutt_aliases.tool._run_command")
    def test_gw_project_workflow(self, mock_run_command, mock_home, mock_file):
        """Test adding GW project team contact."""
        mock_home.return_value = Path("/home/test")
        mock_run_command.return_value = 'alias_file="~/.mutt/addressbook"'

        # Add GW team
        result = add_contact(
            "gw_team",
            "alice@cam.ac.uk,bob@cam.ac.uk,carol@cam.ac.uk",
            "GW Project Team",
        )

        assert "Added contact: gw_team (GW Project Team)" in result

        # Verify the alias format is correct for mutt
        expected_alias = 'alias gw_team "GW Project Team" <alice@cam.ac.uk,bob@cam.ac.uk,carol@cam.ac.uk>\n'
        mock_file().write.assert_called_once_with(expected_alias)
