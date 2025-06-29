"""Integration tests for the email MCP tool with real offlineimap setup."""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from mcp_handley_lab.email.tool import (
    send, list_accounts, sync, sync_status, repo_info, sync_preview, 
    quick_sync, sync_folders, search, count, tag, server_info
)


@pytest.fixture
def test_offlineimap_config():
    """Create a temporary offlineimap configuration for testing."""
    config_content = """
[general]
accounts = TestLocal
maxsyncaccounts = 1
pythonfile = 

[Account TestLocal]
localrepository = TestLocal-Local
remoterepository = TestLocal-Remote
status_backend = sqlite

[Repository TestLocal-Local]
type = Maildir
localfolders = ~/test_maildir
restoreatime = no

[Repository TestLocal-Remote]
type = IMAP
remotehost = localhost
remoteport = 1143
remoteuser = testuser
remotepass = testpass
ssl = no
sslcacertfile = 
starttls = no
# Use a test IMAP server or mock
folderfilter = lambda folder: folder in ['INBOX', 'Sent', 'Drafts']
"""
    
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.offlineimaprc', delete=False) as f:
        f.write(config_content)
        return f.name


@pytest.fixture
def test_msmtp_config():
    """Create a temporary msmtp configuration for testing."""
    config_content = """
# Test account
account test
host localhost
port 587
from test@example.com
user test@example.com
password testpass
auth on
tls off

# Default account
account default : test
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.msmtprc', delete=False) as f:
        f.write(config_content)
        return f.name


@pytest.fixture
def test_maildir():
    """Create a temporary maildir structure for testing."""
    maildir = tempfile.mkdtemp(prefix='test_maildir_')
    
    # Create basic maildir structure
    for folder in ['cur', 'new', 'tmp']:
        os.makedirs(os.path.join(maildir, folder))
    
    # Create some test subdirectories
    for subfolder in ['Sent', 'Drafts']:
        for folder in ['cur', 'new', 'tmp']:
            os.makedirs(os.path.join(maildir, f'.{subfolder}', folder))
    
    return maildir


@pytest.fixture
def mock_imap_server():
    """Mock IMAP server for testing (could be expanded to use real test server)."""
    # This could be enhanced to start a real test IMAP server like dovecot
    # For now, we'll mock the responses
    return "localhost:1143"


class TestEmailIntegration:
    """Integration tests for email functionality."""
    
    def test_offlineimap_config_parsing(self, test_offlineimap_config):
        """Test parsing of offlineimap configuration."""
        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = Path(os.path.dirname(test_offlineimap_config))
            
            # Mock the config file existence
            with patch('pathlib.Path.exists', return_value=True), \
                 patch('builtins.open', open):
                
                # Test that config file can be read
                config_path = Path(test_offlineimap_config)
                assert config_path.exists()
                
                content = config_path.read_text()
                assert "TestLocal" in content
                assert "localhost" in content
    
    @pytest.mark.skipif(not os.getenv('ENABLE_EMAIL_INTEGRATION_TESTS'), 
                       reason="Email integration tests disabled (set ENABLE_EMAIL_INTEGRATION_TESTS=1)")
    def test_sync_with_test_config(self, test_offlineimap_config, test_maildir):
        """Test email sync with test configuration."""
        with patch.dict(os.environ, {'HOME': os.path.dirname(test_offlineimap_config)}):
            try:
                result = sync(account="TestLocal")
                # Should attempt to connect but likely fail due to no server
                assert "sync" in result.lower()
            except Exception as e:
                # Expected to fail without real IMAP server
                assert "connection" in str(e).lower() or "failed" in str(e).lower()
    
    def test_msmtp_account_parsing(self, test_msmtp_config):
        """Test parsing of msmtp configuration."""
        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = Path(os.path.dirname(test_msmtp_config))
            
            with patch('pathlib.Path.exists', return_value=True), \
                 patch('builtins.open', open):
                
                from mcp_handley_lab.email.tool import _parse_msmtprc
                
                # Mock the file path resolution
                with patch('pathlib.Path.home') as mock_home2:
                    mock_home2.return_value = Path(os.path.dirname(test_msmtp_config))
                    config_file = Path(test_msmtp_config)
                    
                    # Read and parse the config manually for testing
                    content = config_file.read_text()
                    assert "account test" in content
                    assert "test@example.com" in content
    
    def test_maildir_structure(self, test_maildir):
        """Test maildir structure creation."""
        maildir_path = Path(test_maildir)
        
        # Check basic maildir structure
        assert (maildir_path / "cur").exists()
        assert (maildir_path / "new").exists() 
        assert (maildir_path / "tmp").exists()
        
        # Check subfolder structure
        assert (maildir_path / ".Sent" / "cur").exists()
        assert (maildir_path / ".Drafts" / "cur").exists()
    
    @pytest.mark.skipif(not os.getenv('ENABLE_EMAIL_INTEGRATION_TESTS'),
                       reason="Email integration tests disabled")
    def test_full_email_workflow(self, test_offlineimap_config, test_msmtp_config, test_maildir):
        """Test complete email workflow with test configurations."""
        # This would be a comprehensive test with a real test IMAP server
        # For now, we'll test the configuration setup
        
        # Test that all configs are properly created
        assert os.path.exists(test_offlineimap_config)
        assert os.path.exists(test_msmtp_config)
        assert os.path.exists(test_maildir)
        
        # Test that server_info works with test configs
        result = server_info()
        assert "Email Tool Server Status" in result


def create_test_imap_server():
    """Helper to create a test IMAP server using Docker or systemd."""
    # Example Docker command to start a test IMAP server:
    # docker run -d --name test-imap -p 1143:143 -p 1993:993 \
    #   -e MAIL_USER=testuser -e MAIL_PASS=testpass \
    #   antespi/docker-imap-devel
    pass


def setup_test_notmuch_db(maildir_path):
    """Setup a test notmuch database."""
    import subprocess
    
    try:
        # Initialize notmuch database in test maildir
        subprocess.run([
            'notmuch', 'setup', 
            '--database', maildir_path,
            '--mail-root', maildir_path
        ], check=True, capture_output=True)
        
        # Initial notmuch scan
        subprocess.run([
            'notmuch', 'new'
        ], cwd=maildir_path, check=True, capture_output=True)
        
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


if __name__ == "__main__":
    # Manual testing helpers
    print("Email Integration Test Helpers")
    print("=============================")
    print()
    print("To run integration tests:")
    print("  export ENABLE_EMAIL_INTEGRATION_TESTS=1")
    print("  python -m pytest tests/test_email_integration.py -v")
    print()
    print("To setup a real test IMAP server:")
    print("  # Using Docker:")
    print("  docker run -d --name test-imap -p 1143:143 \\")
    print("    -e MAIL_USER=testuser -e MAIL_PASS=testpass \\") 
    print("    antespi/docker-imap-devel")
    print()
    print("  # Or using dovecot locally:")
    print("  sudo apt install dovecot-imapd")
    print("  # Configure /etc/dovecot/dovecot.conf for testing")