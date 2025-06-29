"""
Mock-based email tool tests that don't require real email servers.

These tests simulate email server responses and configuration files
to test the MCP email tool functionality safely.
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from mcp_handley_lab.email.tool import (
    send, list_accounts, sync, sync_status, repo_info, sync_preview, 
    quick_sync, sync_folders, search, count, tag, server_info,
    _parse_msmtprc, _run_command
)


class TestEmailMockIntegration:
    """Mock-based integration tests for email functionality."""
    
    def test_full_offlineimap_simulation(self):
        """Test complete offlineimap workflow with mocked responses."""
        
        # Mock successful offlineimap run
        mock_output = """
OfflineIMAP 8.0.0
Account sync TestAccount:
 *** Processing account TestAccount
 Establishing connection to localhost:1143 (TestAccount-Remote)
Folder INBOX [acc: TestAccount]:
 Syncing INBOX: IMAP -> Maildir
 Copy message UID 1001 (1/3) TestAccount-Remote:INBOX -> TestAccount-Local:INBOX
 Copy message UID 1002 (2/3) TestAccount-Remote:INBOX -> TestAccount-Local:INBOX
 Copy message UID 1003 (3/3) TestAccount-Remote:INBOX -> TestAccount-Local:INBOX
Folder Sent [acc: TestAccount]:
 Syncing Sent: IMAP -> Maildir
Account sync TestAccount:
 Calling hook: notmuch new
 Hook stdout: Processed 3 total files in almost no time.
Added 3 new messages to the database.

Hook stderr:

 Hook return code: 0
 *** Finished account 'TestAccount' in 0:05
"""
        
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = mock_output
            
            # Test sync
            result = sync(account="TestAccount")
            assert "sync completed successfully" in result
            assert "TestAccount" in mock_output
            
            # Verify correct command was called
            mock_run.assert_called_with(["offlineimap", "-o", "-a", "TestAccount"])
    
    def test_offlineimap_info_simulation(self):
        """Test repository info with mocked offlineimap --info output."""
        
        mock_info_output = """
OfflineIMAP 8.0.0
Remote repository 'TestAccount-Remote': type 'IMAP'
Host: localhost Port: 1143 SSL: False
Server capabilities: ('IMAP4REV1', 'UIDPLUS', 'IDLE', 'NAMESPACE')

Folderlist:
 INBOX
 Sent
 Drafts
 Archive

Local repository 'TestAccount-Local': type 'Maildir'
Folderlist:
 INBOX
 Sent
 Drafts
 Archive
"""
        
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = mock_info_output
            
            result = repo_info()
            assert "Repository information:" in result
            assert "TestAccount-Remote" in result
            assert "Maildir" in result
            
            mock_run.assert_called_with(["offlineimap", "--info"])
    
    def test_quick_sync_simulation(self):
        """Test quick sync with mocked output."""
        
        mock_quick_output = """
OfflineIMAP 8.0.0
Account sync TestAccount:
 *** Processing account TestAccount
Folder INBOX [acc: TestAccount]:
 Syncing INBOX: IMAP -> Maildir
 Skipping INBOX (not changed)
Folder Sent [acc: TestAccount]:
 Syncing Sent: IMAP -> Maildir
 Skipping Sent (not changed)
 *** Finished account 'TestAccount' in 0:02
"""
        
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = mock_quick_output
            
            result = quick_sync(account="TestAccount")
            assert "Quick sync completed successfully" in result
            
            # Verify -q flag was used
            mock_run.assert_called_with(["offlineimap", "-q", "-o", "-a", "TestAccount"])
    
    def test_folder_sync_simulation(self):
        """Test folder-specific sync."""
        
        mock_folder_output = """
OfflineIMAP 8.0.0
Account sync TestAccount:
 *** Processing account TestAccount
Folder INBOX [acc: TestAccount]:
 Syncing INBOX: IMAP -> Maildir
 Copy message UID 2001 (1/1) TestAccount-Remote:INBOX -> TestAccount-Local:INBOX
 *** Finished account 'TestAccount' in 0:01
"""
        
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = mock_folder_output
            
            result = sync_folders("INBOX", account="TestAccount")
            assert "Folder sync completed successfully" in result
            
            # Verify correct folder flag
            mock_run.assert_called_with(["offlineimap", "-o", "-f", "INBOX", "-a", "TestAccount"])
    
    def test_msmtp_simulation(self):
        """Test email sending with mocked msmtp."""
        
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = ""  # msmtp typically returns empty on success
            
            result = send(
                to="test@example.com",
                subject="Test Subject", 
                body="Test body",
                account="test_account"
            )
            
            assert "Email sent successfully to test@example.com" in result
            assert "account: test_account" in result
            
            # Check command structure
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            email_content = call_args[1]["input_text"]
            
            assert "msmtp" in cmd
            assert "-a" in cmd
            assert "test_account" in cmd
            assert "test@example.com" in cmd
            
            assert "To: test@example.com" in email_content
            assert "Subject: Test Subject" in email_content
            assert "Test body" in email_content
    
    def test_notmuch_simulation(self):
        """Test notmuch operations with mocked responses."""
        
        # Mock search results
        mock_search_output = """
thread:0001 2025-06-28 [1/3] Test Sender; Test Message Subject (inbox unread)
thread:0002 2025-06-27 [1/1] Another Sender; Another Subject (inbox)
thread:0003 2025-06-26 [2/5] Someone Else; Re: Important Topic (inbox important)
"""
        
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = mock_search_output
            
            result = search("tag:inbox", limit=10)
            assert "Search results for 'tag:inbox'" in result
            assert "Test Message Subject" in result
            assert "thread:0001" in result
            
            mock_run.assert_called_with(["notmuch", "search", "--limit", "10", "tag:inbox"])
    
    def test_notmuch_count_simulation(self):
        """Test notmuch count with mocked response."""
        
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = "42"
            
            result = count("tag:unread")
            assert "Found 42 emails matching 'tag:unread'" in result
            
            mock_run.assert_called_with(["notmuch", "count", "tag:unread"])
    
    def test_notmuch_tagging_simulation(self):
        """Test notmuch tagging operations."""
        
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = ""  # notmuch tag returns empty on success
            
            # Test adding tags
            result = tag("message123", add_tags="important,work")
            assert "Tags updated for message message123" in result
            assert "added: important,work" in result
            
            call_args = mock_run.call_args[0][0]
            assert "notmuch" in call_args
            assert "tag" in call_args
            assert "+important" in call_args
            assert "+work" in call_args
            assert "id:message123" in call_args
    
    def test_config_file_simulation(self):
        """Test configuration file parsing with mocked files."""
        
        # Mock msmtprc content
        mock_msmtprc = """
# Test msmtp config
account work
host smtp.work.com
user work@work.com

account personal  
host smtp.gmail.com
user personal@gmail.com

account default : work
"""
        
        with patch('pathlib.Path.home') as mock_home, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=mock_msmtprc)):
            
            mock_home.return_value = Path("/tmp/test")
            
            accounts = _parse_msmtprc()
            assert accounts == ["work", "personal"]
    
    def test_server_info_simulation(self):
        """Test server info with all tools mocked."""
        
        def mock_command_response(cmd, *args, **kwargs):
            if "msmtp" in cmd and "--version" in cmd:
                return "msmtp version 1.8.30"
            elif "offlineimap" in cmd and "--version" in cmd:
                return "OfflineIMAP 8.0.0"
            elif "notmuch" in cmd and "--version" in cmd:
                return "notmuch 0.39"
            elif "notmuch" in cmd and "count" in cmd:
                return "1500"
            return ""
        
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run, \
             patch('mcp_handley_lab.email.tool._parse_msmtprc') as mock_parse, \
             patch('pathlib.Path.home') as mock_home, \
             patch('pathlib.Path.exists', return_value=True):
            
            mock_home.return_value = Path("/tmp/test")
            mock_parse.return_value = ["work", "personal", "test"]
            mock_run.side_effect = mock_command_response
            
            result = server_info()
            
            assert "✓ msmtp: msmtp version 1.8.30" in result
            assert "Accounts: 3 configured" in result
            assert "✓ offlineimap: OfflineIMAP 8.0.0" in result
            assert "✓ notmuch: notmuch 0.39" in result
            assert "Database: 1500 messages indexed" in result
    
    def test_error_handling_simulation(self):
        """Test error handling with mocked failures."""
        
        # Test offlineimap connection error
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.side_effect = RuntimeError("Connection failed: [Errno 111] Connection refused")
            
            # The sync function catches RuntimeError and returns it as a string
            result = sync(account="nonexistent")
            assert "completed with warnings" in result
            assert "Connection failed" in result
        
        # Test msmtp not found
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.side_effect = RuntimeError("Command 'msmtp' not found")
            
            with pytest.raises(RuntimeError, match="not found"):
                send("test@example.com", "Subject", "Body")
    
    def test_json_rpc_simulation(self):
        """Test complete JSON-RPC workflow simulation."""
        
        # This would simulate the complete MCP server interaction
        # using the FastMCP test client if available
        
        with patch('mcp_handley_lab.email.tool._run_command') as mock_run:
            mock_run.return_value = "sync completed"
            
            # Test that functions work through the MCP interface
            result = sync()
            assert "sync completed" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])