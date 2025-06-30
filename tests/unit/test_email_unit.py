"""Tests for the email MCP tool."""
import pytest
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path
import subprocess

from mcp_handley_lab.email.tool import (
    send, list_accounts, sync, sync_status, search, count, tag, server_info,
    _run_command, _parse_msmtprc
)


class TestEmailTool:
    """Test email tool functionality."""

    def test_run_command_success(self):
        """Test successful command execution."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.stdout = "command output"
            mock_run.return_value.strip.return_value = "command output"
            
            result = _run_command(["echo", "test"])
            assert result == "command output"

    def test_run_command_failure(self):
        """Test command execution failure."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, ["false"], stderr="error")
            
            with pytest.raises(RuntimeError, match="Command 'false' failed: error"):
                _run_command(["false"])

    def test_run_command_not_found(self):
        """Test command not found."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            
            with pytest.raises(RuntimeError, match="Command 'nonexistent' not found"):
                _run_command(["nonexistent"])

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
        with patch('pathlib.Path.home') as mock_home, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=msmtprc_content)):
            mock_home.return_value = Path("/home/test")
            
            accounts = _parse_msmtprc()
            assert accounts == ["work", "personal"]

    def test_parse_msmtprc_no_file(self):
        """Test parsing when msmtprc doesn't exist."""
        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = Path("/home/test")
            with patch('pathlib.Path.exists', return_value=False):
                accounts = _parse_msmtprc()
                assert accounts == []

    def test_send_email_basic(self):
        """Test sending a basic email."""
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = ""
            
            result = send("test@example.com", "Test Subject", "Test body")
            
            mock_run.assert_called_once()
            args = mock_run.call_args
            assert "msmtp" in args[0][0]
            assert "test@example.com" in args[0][0]
            assert "To: test@example.com" in args[1]["input_text"]
            assert "Subject: Test Subject" in args[1]["input_text"]
            assert "Test body" in args[1]["input_text"]
            assert result == "Email sent successfully to test@example.com"

    def test_send_email_with_account(self):
        """Test sending email with specific account."""
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = ""
            
            result = send("test@example.com", "Test", "Body", account="work")
            
            args = mock_run.call_args[0][0]
            assert "-a" in args
            assert "work" in args
            assert "account: work" in result

    def test_send_email_with_cc_bcc(self):
        """Test sending email with CC and BCC."""
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = ""
            
            send("test@example.com", "Test", "Body", cc="cc@example.com", bcc="bcc@example.com")
            
            args = mock_run.call_args
            cmd = args[0][0]
            content = args[1]["input_text"]
            
            # Check recipients in command
            assert "test@example.com" in cmd
            assert "cc@example.com" in cmd
            assert "bcc@example.com" in cmd
            
            # Check headers in content
            assert "Cc: cc@example.com" in content
            assert "Bcc: bcc@example.com" in content

    def test_list_accounts(self):
        """Test listing msmtp accounts."""
        with patch('mcp_handley_lab.email.tool._parse_msmtprc') as mock_parse:
            mock_parse.return_value = ["work", "personal"]
            
            result = list_accounts()
            assert "Available msmtp accounts:" in result
            assert "- work" in result
            assert "- personal" in result

    def test_list_accounts_none(self):
        """Test listing accounts when none exist."""
        with patch('mcp_handley_lab.email.tool._parse_msmtprc') as mock_parse:
            mock_parse.return_value = []
            
            result = list_accounts()
            assert "No msmtp accounts found" in result

    def test_sync_basic(self):
        """Test basic email sync."""
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = "Sync completed"
            
            result = sync()
            
            args = mock_run.call_args[0][0]
            assert "offlineimap" in args
            assert "-o1" in args
            assert "Email sync completed successfully" in result

    def test_sync_with_account(self):
        """Test sync with specific account."""
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = "Sync completed"
            
            sync(account="work")
            
            args = mock_run.call_args[0][0]
            assert "-a" in args
            assert "work" in args

    def test_sync_status(self):
        """Test sync status check."""
        with patch('pathlib.Path.home') as mock_home, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_home.return_value = Path("/home/test")
            mock_run.return_value = "Configuration valid"
            
            result = sync_status()
            
            args = mock_run.call_args[0][0]
            assert "offlineimap" in args
            assert "--dry-run" in args
            assert "Offlineimap configuration valid" in result

    def test_search_emails(self):
        """Test email search."""
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = "thread:001 Subject line"
            
            result = search("from:test@example.com")
            
            args = mock_run.call_args[0][0]
            assert "notmuch" in args
            assert "search" in args
            assert "from:test@example.com" in args
            assert "Search results for 'from:test@example.com'" in result

    def test_search_no_results(self):
        """Test search with no results."""
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = ""
            
            result = search("nonexistent")
            assert "No emails found matching query" in result

    def test_count_emails(self):
        """Test email count."""
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = "42"
            
            result = count("tag:inbox")
            
            args = mock_run.call_args[0][0]
            assert "notmuch" in args
            assert "count" in args
            assert "tag:inbox" in args
            assert "Found 42 emails matching 'tag:inbox'" in result

    def test_tag_add(self):
        """Test adding tags."""
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = ""
            
            result = tag("message123", add_tags="important,work")
            
            args = mock_run.call_args[0][0]
            assert "notmuch" in args
            assert "tag" in args
            assert "+important" in args
            assert "+work" in args
            assert "id:message123" in args
            assert "added: important,work" in result

    def test_tag_remove(self):
        """Test removing tags."""
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = ""
            
            result = tag("message123", remove_tags="spam")
            
            args = mock_run.call_args[0][0]
            assert "-spam" in args
            assert "removed: spam" in result

    def test_tag_no_operation(self):
        """Test tag with no add or remove."""
        with pytest.raises(ValueError, match="Must specify either add_tags or remove_tags"):
            tag("message123")

    def test_server_info(self):
        """Test server info collection."""
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run, \
             patch('mcp_handley_lab.email.tool._parse_msmtprc') as mock_parse, \
             patch('pathlib.Path.home') as mock_home, \
             patch('pathlib.Path.exists', return_value=True):
            
            mock_home.return_value = Path("/home/test")
            mock_parse.return_value = ["work", "personal"]
            
            # Mock different command responses
            def mock_command_response(cmd, *args, **kwargs):
                if "msmtp" in cmd and "--version" in cmd:
                    return "msmtp version 1.8.11"
                elif "offlineimap" in cmd and "--version" in cmd:
                    return "offlineimap v7.3.3"
                elif "notmuch" in cmd and "--version" in cmd:
                    return "notmuch 0.32.2"
                elif "notmuch" in cmd and "count" in cmd:
                    return "1234"
                return ""
            
            mock_run.side_effect = mock_command_response
            
            result = server_info()
            
            assert "✓ msmtp: msmtp version 1.8.11" in result
            assert "Accounts: 2 configured" in result
            assert "✓ offlineimap: offlineimap v7.3.3" in result
            assert "✓ notmuch: notmuch 0.32.2" in result
            assert "Database: 1234 messages indexed" in result

    def test_server_info_tool_missing(self):
        """Test server info when tools are missing."""
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.side_effect = RuntimeError("Command 'msmtp' not found")
            
            result = server_info()
            assert "✗ msmtp:" in result
            assert "not found" in result


if __name__ == "__main__":
    pytest.main([__file__])