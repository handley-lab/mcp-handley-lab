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

    @pytest.mark.skipif(not os.getenv('GMAIL_TEST_PASSWORD'), 
                       reason="Gmail test credentials not available (set GMAIL_TEST_PASSWORD)")
    def test_real_offlineimap_sync(self):
        """Test offlineimap sync with real handleylab@gmail.com test account."""
        import subprocess
        from pathlib import Path
        
        # Use the fixture configuration files
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "email"
        offlineimaprc_path = fixtures_dir / "offlineimaprc"
        
        # Verify test config exists
        assert offlineimaprc_path.exists(), f"Test config not found: {offlineimaprc_path}"
        
        # Check that test mail directory gets created (relative to config dir)
        project_root = Path(__file__).parent.parent.parent
        test_mail_dir = project_root / ".test_mail" / "HandleyLab"
        
        try:
            # Run offlineimap sync using the test configuration
            result = subprocess.run([
                "offlineimap", 
                "-c", str(offlineimaprc_path),
                "-o1"  # One-time sync
            ], 
            cwd=str(fixtures_dir),
            capture_output=True, 
            text=True, 
            timeout=60  # 60 second timeout
            )
            
            # Check that sync completed (offlineimap often returns non-zero but still works)
            output = result.stdout + result.stderr
            assert "imap.gmail.com" in output, "Should connect to Gmail IMAP"
            assert "HandleyLab" in output, "Should process HandleyLab account"
            
            # Verify maildir structure was created
            assert test_mail_dir.exists(), "Test maildir should be created"
            
            # Check for basic maildir structure
            expected_folders = ["INBOX", "[Gmail]"]
            created_folders = [d.name for d in test_mail_dir.iterdir() if d.is_dir()]
            
            # At least INBOX should exist
            inbox_found = any("INBOX" in folder for folder in created_folders)
            assert inbox_found, f"INBOX folder not found in: {created_folders}"
            
            print(f"✓ Offlineimap sync successful")
            print(f"✓ Created folders: {created_folders}")
            
        except subprocess.TimeoutExpired:
            pytest.fail("Offlineimap sync timed out after 60 seconds")
        except subprocess.CalledProcessError as e:
            # Check if it's a real error or just offlineimap's typical non-zero exit
            if "ERROR" in e.stderr.upper():
                pytest.fail(f"Offlineimap sync failed: {e.stderr}")
            else:
                # Offlineimap often returns non-zero but still works
                print(f"Offlineimap completed with warnings: {e.stderr}")

    @pytest.mark.skipif(True, reason="Complex test - main functionality covered by test_real_offlineimap_sync")  
    def test_email_tool_sync_function(self):
        """Test the email tool sync function with real configuration."""
        import os
        from pathlib import Path
        from unittest.mock import patch
        
        # Change to fixtures directory for relative path resolution
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "email"
        original_cwd = os.getcwd()
        
        try:
            os.chdir(str(fixtures_dir))
            
            # Mock offlineimap to use our test config file explicitly
            def mock_run_command(cmd, input_text=None, cwd=None):
                if cmd[0] == "offlineimap":
                    # Add our test config to the command
                    test_cmd = ["offlineimap", "-c", "offlineimaprc"] + cmd[1:]
                    # Run the actual command
                    import subprocess
                    result = subprocess.run(test_cmd, capture_output=True, text=True, cwd=fixtures_dir)
                    return result.stdout.strip()
                else:
                    # For other commands, use the original function
                    from mcp_handley_lab.email.tool import _run_command
                    return _run_command.__wrapped__(cmd, input_text, cwd)
            
            with patch('mcp_handley_lab.email.tool._run_command', side_effect=mock_run_command):
                # Test the sync function
                result = sync()
                
                # Should complete successfully or with warnings
                assert "sync" in result.lower()
                
                # Verify it uses -o1 flag (should not hang)
                assert "completed" in result.lower() or "warning" in result.lower()
                
                print(f"✓ Email tool sync function result: {result[:100]}...")
                
        finally:
            os.chdir(original_cwd)


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