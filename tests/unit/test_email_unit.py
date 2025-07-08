"""Tests for the email MCP tool."""
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
from mcp_handley_lab.email.msmtp.tool import _parse_msmtprc, list_accounts, send
from mcp_handley_lab.email.notmuch.tool import count, search, tag
from mcp_handley_lab.email.offlineimap.tool import sync, sync_status
from mcp_handley_lab.email.tool import server_info


class TestEmailTool:
    """Test email tool functionality."""

    def test_parse_msmtprc_success(self):
        """Test parsing msmtprc file successfully."""
        msmtprc_content = """
# Comment
account work
host smtp.example.com
user work@example.com

account default : work

account personal
host smtp.gmail.com
user personal@gmail.com
"""
        with patch("pathlib.Path.home") as mock_home, patch(
            "pathlib.Path.exists", return_value=True
        ), patch("builtins.open", mock_open(read_data=msmtprc_content)):
            mock_home.return_value = Path("/home/test")

            accounts = _parse_msmtprc()
            assert accounts == ["work", "personal"]

    def test_parse_msmtprc_no_file(self):
        """Test parsing when msmtprc doesn't exist."""
        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = Path("/home/test")
            with patch("pathlib.Path.exists", return_value=False):
                accounts = _parse_msmtprc()
                assert accounts == []

    def test_send_email_basic(self):
        """Test sending a basic email."""
        with patch(
            "mcp_handley_lab.email.msmtp.tool.run_command", new_callable=Mock
        ) as mock_run:
            mock_run.return_value = (b"", b"")

            result = send("test@example.com", "Test Subject", "Test body")

            mock_run.assert_called_once()
            args = mock_run.call_args
            assert "msmtp" in args[0][0]
            assert "test@example.com" in args[0][0]
            assert "To: test@example.com" in args[1]["input_data"].decode()
            assert "Subject: Test Subject" in args[1]["input_data"].decode()
            assert "Test body" in args[1]["input_data"].decode()
            assert result.status == "success"
            assert result.recipient == "test@example.com"
            assert result.account_used == ""

    def test_send_email_with_account(self):
        """Test sending email with specific account."""
        with patch(
            "mcp_handley_lab.email.msmtp.tool.run_command", new_callable=Mock
        ) as mock_run:
            mock_run.return_value = (b"", b"")

            result = send("test@example.com", "Test", "Body", account="work")

            args = mock_run.call_args[0][0]
            assert "-a" in args
            assert "work" in args
            assert result.account_used == "work"

    def test_send_email_with_cc_bcc(self):
        """Test sending email with CC and BCC."""
        with patch(
            "mcp_handley_lab.email.msmtp.tool.run_command", new_callable=Mock
        ) as mock_run:
            mock_run.return_value = (b"", b"")

            send(
                "test@example.com",
                "Test",
                "Body",
                cc="cc@example.com",
                bcc="bcc@example.com",
            )

            args = mock_run.call_args
            cmd = args[0][0]
            content = args[1]["input_data"].decode()

            # Check recipients in command
            assert "test@example.com" in cmd
            assert "cc@example.com" in cmd
            assert "bcc@example.com" in cmd

            # Check headers in content
            assert "Cc: cc@example.com" in content
            assert "Bcc: bcc@example.com" in content

    def test_list_accounts(self):
        """Test listing msmtp accounts."""
        with patch("mcp_handley_lab.email.msmtp.tool._parse_msmtprc") as mock_parse:
            mock_parse.return_value = ["work", "personal"]

            result = list_accounts()
            assert result == ["work", "personal"]

    def test_list_accounts_none(self):
        """Test listing accounts when none exist."""
        with patch("mcp_handley_lab.email.msmtp.tool._parse_msmtprc") as mock_parse:
            mock_parse.return_value = []

            result = list_accounts()
            assert result == []

    def test_sync_basic(self):
        """Test basic email sync."""
        with patch(
            "mcp_handley_lab.email.offlineimap.tool.run_command", new_callable=Mock
        ) as mock_run:
            mock_run.return_value = (b"Sync completed", b"")

            result = sync()

            args = mock_run.call_args[0][0]
            assert "offlineimap" in args
            assert "-o1" in args
            assert "Email sync completed successfully" in result

    def test_sync_with_account(self):
        """Test sync with specific account."""
        with patch(
            "mcp_handley_lab.email.offlineimap.tool.run_command", new_callable=Mock
        ) as mock_run:
            mock_run.return_value = (b"Sync completed", b"")

            sync(account="work")

            args = mock_run.call_args[0][0]
            assert "-a" in args
            assert "work" in args

    def test_sync_status(self):
        """Test sync status check."""
        with patch("pathlib.Path.home") as mock_home, patch(
            "pathlib.Path.exists", return_value=True
        ), patch(
            "mcp_handley_lab.email.offlineimap.tool.run_command", new_callable=Mock
        ) as mock_run:
            mock_home.return_value = Path("/home/test")
            mock_run.return_value = (b"Configuration valid", b"")

            result = sync_status()

            args = mock_run.call_args[0][0]
            assert "offlineimap" in args
            assert "--dry-run" in args
            assert "Offlineimap configuration valid" in result

    def test_search_emails(self):
        """Test email search."""
        with patch(
            "mcp_handley_lab.email.notmuch.tool.run_command", new_callable=Mock
        ) as mock_run:
            mock_run.return_value = (b"thread:001 Subject line", b"")

            result = search("from:test@example.com")

            args = mock_run.call_args[0][0]
            assert "notmuch" in args
            assert "search" in args
            assert "from:test@example.com" in args
            assert result == ["thread:001 Subject line"]

    def test_search_no_results(self):
        """Test search with no results."""
        with patch(
            "mcp_handley_lab.email.notmuch.tool.run_command", new_callable=Mock
        ) as mock_run:
            mock_run.return_value = (b"", b"")

            result = search("nonexistent")
            assert result == []

    def test_count_emails(self):
        """Test email count."""
        with patch(
            "mcp_handley_lab.email.notmuch.tool.run_command", new_callable=Mock
        ) as mock_run:
            mock_run.return_value = (b"42", b"")

            result = count("tag:inbox")

            args = mock_run.call_args[0][0]
            assert "notmuch" in args
            assert "count" in args
            assert "tag:inbox" in args
            assert result == 42

    def test_tag_add(self):
        """Test adding tags."""
        with patch(
            "mcp_handley_lab.email.notmuch.tool.run_command", new_callable=Mock
        ) as mock_run:
            mock_run.return_value = (b"", b"")

            result = tag("message123", add_tags="important,work")

            args = mock_run.call_args[0][0]
            assert "notmuch" in args
            assert "tag" in args
            assert "+important" in args
            assert "+work" in args
            assert "id:message123" in args
            assert result.message_id == "message123"
            assert result.added_tags == ["important", "work"]
            assert result.removed_tags == []

    def test_tag_remove(self):
        """Test removing tags."""
        with patch(
            "mcp_handley_lab.email.notmuch.tool.run_command", new_callable=Mock
        ) as mock_run:
            mock_run.return_value = (b"", b"")

            result = tag("message123", remove_tags="spam")

            args = mock_run.call_args[0][0]
            assert "-spam" in args
            assert result.message_id == "message123"
            assert result.added_tags == []
            assert result.removed_tags == ["spam"]

    def test_tag_no_operation(self):
        """Test tag with no add or remove."""
        with pytest.raises(
            ValueError, match="Must specify either add_tags or remove_tags"
        ):
            tag("message123")

    def test_server_info(self):
        """Test server info collection."""
        with patch(
            "mcp_handley_lab.email.tool.run_command", new_callable=Mock
        ) as mock_run, patch(
            "mcp_handley_lab.email.msmtp.tool._parse_msmtprc"
        ) as mock_parse, patch("pathlib.Path.home") as mock_home, patch(
            "pathlib.Path.exists", return_value=True
        ):
            mock_home.return_value = Path("/home/test")
            mock_parse.return_value = ["work", "personal"]

            # Mock different command responses
            def mock_command_response(cmd, *args, **kwargs):
                if "msmtp" in cmd and "--version" in cmd:
                    return (b"msmtp version 1.8.11", b"")
                elif "offlineimap" in cmd and "--version" in cmd:
                    return (b"offlineimap v7.3.3", b"")
                elif "notmuch" in cmd and "--version" in cmd:
                    return (b"notmuch 0.32.2", b"")
                elif "notmuch" in cmd and "count" in cmd:
                    return (b"1234", b"")
                return (b"", b"")

            mock_run.side_effect = mock_command_response

            result = server_info()

            assert result.name == "Email Tool Server"
            assert result.version == "1.9.4"
            assert result.status == "active"
            assert "msmtp - msmtp version 1.8.11" in result.capabilities
            assert "offlineimap - offlineimap v7.3.3" in result.capabilities
            assert "notmuch - notmuch 0.32.2" in result.capabilities
            assert result.dependencies["msmtp_accounts"] == "2"
            assert result.dependencies["notmuch_database"] == "1234 messages indexed"

    def test_server_info_tool_missing(self):
        """Test server info when tools are missing."""
        with patch(
            "mcp_handley_lab.email.tool.run_command", new_callable=Mock
        ) as mock_run:
            mock_run.side_effect = RuntimeError("Command 'msmtp' not found")

            with pytest.raises(RuntimeError, match="Command 'msmtp' not found"):
                server_info()


if __name__ == "__main__":
    pytest.main([__file__])
