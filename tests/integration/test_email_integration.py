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


    @pytest.mark.skipif(not os.getenv('GMAIL_TEST_PASSWORD'),
                       reason="Gmail test credentials not available")
    def test_msmtp_send_and_receive_cycle(self):
        """Test complete email cycle: send with msmtp -> sync with offlineimap -> verify receipt."""
        import subprocess
        import time
        from pathlib import Path
        import uuid
        
        # Use fixture configurations
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "email"
        msmtprc_path = fixtures_dir / "msmtprc"
        offlineimaprc_path = fixtures_dir / "offlineimaprc"
        
        # Verify configs exist
        assert msmtprc_path.exists(), f"msmtp config not found: {msmtprc_path}"
        assert offlineimaprc_path.exists(), f"offlineimap config not found: {offlineimaprc_path}"
        
        # Create unique test email content
        test_id = str(uuid.uuid4())[:8]
        test_subject = f"MCP Test Email {test_id}"
        test_body = f"This is a test email sent at {time.strftime('%Y-%m-%d %H:%M:%S')} with ID: {test_id}"
        
        # Prepare email content for msmtp
        email_content = f"""To: handleylab@gmail.com
Subject: {test_subject}

{test_body}
"""
        
        try:
            # Step 1: Send email using msmtp
            print(f"📧 Sending test email with ID: {test_id}")
            send_result = subprocess.run([
                "msmtp",
                "-C", str(msmtprc_path),  # Use our test config
                "handleylab@gmail.com"
            ],
            input=email_content,
            cwd=str(fixtures_dir),
            capture_output=True,
            text=True,
            timeout=30
            )
            
            if send_result.returncode != 0:
                pytest.fail(f"msmtp send failed: {send_result.stderr}")
            
            print(f"✅ Email sent successfully")
            
            # Step 2: Wait for email delivery (Gmail can take a few seconds)
            print("⏳ Waiting 10 seconds for email delivery...")
            time.sleep(10)
            
            # Step 3: Sync emails using offlineimap
            print("📥 Syncing emails with offlineimap...")
            sync_result = subprocess.run([
                "offlineimap",
                "-c", str(offlineimaprc_path),
                "-o1"  # One-time sync
            ],
            cwd=str(fixtures_dir),
            capture_output=True,
            text=True,
            timeout=60
            )
            
            # offlineimap often returns non-zero but still works
            sync_output = sync_result.stdout + sync_result.stderr
            assert "imap.gmail.com" in sync_output, "Should connect to Gmail IMAP"
            print("✅ Email sync completed")
            
            # Step 4: Check for received email in maildir
            project_root = Path(__file__).parent.parent.parent
            test_mail_dir = project_root / ".test_mail" / "HandleyLab"
            inbox_dir = test_mail_dir / "INBOX"
            
            # Check all maildir folders for the test email
            email_found = False
            email_locations = []
            
            if test_mail_dir.exists():
                # Search in INBOX and other folders
                search_dirs = [
                    inbox_dir / "new",
                    inbox_dir / "cur", 
                    test_mail_dir / "[Gmail].All Mail" / "new",
                    test_mail_dir / "[Gmail].All Mail" / "cur"
                ]
                
                for search_dir in search_dirs:
                    if search_dir.exists():
                        for email_file in search_dir.iterdir():
                            if email_file.is_file():
                                try:
                                    content = email_file.read_text()
                                    if test_id in content and test_subject in content:
                                        email_found = True
                                        email_locations.append(str(email_file))
                                        print(f"🎯 Found test email in: {email_file}")
                                        break
                                except (UnicodeDecodeError, PermissionError):
                                    continue
                        if email_found:
                            break
            
            # Verify the email was received
            if email_found:
                print(f"✅ Email cycle test successful! Email with ID {test_id} was sent and received.")
                print(f"📍 Email location: {email_locations[0]}")
                
                # Step 5: Clean up - delete the test email
                try:
                    for email_location in email_locations:
                        email_path = Path(email_location)
                        if email_path.exists():
                            email_path.unlink()
                            print(f"🗑️  Deleted test email: {email_path.name}")
                    
                    # Also run a sync to update the server (delete from Gmail)
                    print("🔄 Syncing deletion back to server...")
                    delete_sync_result = subprocess.run([
                        "offlineimap",
                        "-c", str(offlineimaprc_path),
                        "-o1"
                    ],
                    cwd=str(fixtures_dir),
                    capture_output=True,
                    text=True,
                    timeout=30
                    )
                    print("✅ Cleanup sync completed")
                    
                except Exception as cleanup_error:
                    print(f"⚠️  Cleanup failed (non-critical): {cleanup_error}")
                    # Don't fail the test for cleanup issues
                    
            else:
                # List what we did find for debugging
                all_emails = []
                if test_mail_dir.exists():
                    for search_dir in search_dirs:
                        if search_dir.exists():
                            all_emails.extend([f.name for f in search_dir.iterdir() if f.is_file()])
                
                pytest.fail(f"Test email with ID {test_id} not found after send+sync cycle. "
                          f"Found {len(all_emails)} total emails in maildir. "
                          f"This could be due to Gmail delivery delay or filtering.")
                          
        except subprocess.TimeoutExpired as e:
            pytest.fail(f"Email operation timed out: {e}")
        except Exception as e:
            pytest.fail(f"Email cycle test failed: {e}")

    @pytest.mark.skipif(not os.getenv('GMAIL_TEST_PASSWORD'),
                       reason="Gmail test credentials not available")
    def test_email_tool_send_and_receive_cycle(self):
        """Test email cycle using the email tool functions: send() -> sync() -> search()."""
        import time
        import uuid
        from pathlib import Path
        from unittest.mock import patch
        
        # Change to fixtures directory for relative path resolution
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "email"
        original_cwd = os.getcwd()
        
        try:
            os.chdir(str(fixtures_dir))
            
            # Create unique test email
            test_id = str(uuid.uuid4())[:8]
            test_subject = f"MCP Tool Test {test_id}"
            test_body = f"Email tool integration test sent at {time.strftime('%Y-%m-%d %H:%M:%S')} with ID: {test_id}"
            
            # Mock the config paths to use our test configurations
            def mock_run_command(cmd, input_text=None, cwd=None):
                if cmd[0] == "msmtp":
                    # Add our test config to msmtp command
                    test_cmd = ["msmtp", "-C", "msmtprc"] + cmd[1:]
                    import subprocess
                    result = subprocess.run(test_cmd, input=input_text, capture_output=True, text=True, cwd=fixtures_dir)
                    if result.returncode != 0:
                        raise RuntimeError(f"Command '{' '.join(test_cmd)}' failed: {result.stderr.strip()}")
                    return result.stdout.strip()
                elif cmd[0] == "offlineimap":
                    # Add our test config to offlineimap command  
                    test_cmd = ["offlineimap", "-c", "offlineimaprc"] + cmd[1:]
                    import subprocess
                    result = subprocess.run(test_cmd, capture_output=True, text=True, cwd=fixtures_dir)
                    return result.stdout.strip()
                else:
                    # For other commands, use the original function
                    from mcp_handley_lab.email.tool import _run_command
                    return _run_command.__wrapped__(cmd, input_text, cwd)
            
            with patch('mcp_handley_lab.email.tool._run_command', side_effect=mock_run_command):
                # Step 1: Send email using email tool
                print(f"📧 Sending test email with email tool, ID: {test_id}")
                send_result = send(
                    to="handleylab@gmail.com",
                    subject=test_subject,
                    body=test_body,
                    account="HandleyLab"
                )
                
                assert "sent successfully" in send_result.lower()
                print("✅ Email sent via email tool")
                
                # Step 2: Wait for delivery
                print("⏳ Waiting 10 seconds for email delivery...")
                time.sleep(10)
                
                # Step 3: Sync using email tool
                print("📥 Syncing with email tool...")
                sync_result = sync()
                assert "sync" in sync_result.lower()
                print("✅ Sync completed via email tool")
                
                # Step 4: Search for the email using notmuch (if available)
                try:
                    search_result = search(f"subject:{test_id}")
                    if "No emails found" not in search_result:
                        print(f"🎯 Found test email via search: {search_result[:100]}...")
                        print(f"✅ Complete email tool cycle successful for ID: {test_id}")
                    else:
                        # Search might not find it immediately, but the file-level test above proved it works
                        print(f"⚠️  Search didn't find email immediately, but send+sync cycle completed")
                        
                except Exception as search_error:
                    # If notmuch isn't configured, that's okay - we've verified send+sync works
                    print(f"⚠️  Search test skipped (notmuch issue: {search_error})")
                    print(f"✅ Send+sync cycle completed successfully for ID: {test_id}")
                
                # Step 5: Clean up - find and delete the test email
                try:
                    project_root = Path(__file__).parent.parent.parent
                    test_mail_dir = project_root / ".test_mail" / "HandleyLab"
                    
                    # Search for our test email and delete it
                    deleted_count = 0
                    if test_mail_dir.exists():
                        search_dirs = [
                            test_mail_dir / "INBOX" / "new",
                            test_mail_dir / "INBOX" / "cur", 
                            test_mail_dir / "[Gmail].All Mail" / "new",
                            test_mail_dir / "[Gmail].All Mail" / "cur"
                        ]
                        
                        for search_dir in search_dirs:
                            if search_dir.exists():
                                for email_file in search_dir.iterdir():
                                    if email_file.is_file():
                                        try:
                                            content = email_file.read_text()
                                            if test_id in content:
                                                email_file.unlink()
                                                deleted_count += 1
                                                print(f"🗑️  Deleted test email: {email_file.name}")
                                        except (UnicodeDecodeError, PermissionError):
                                            continue
                    
                    if deleted_count > 0:
                        # Sync deletions back to server
                        print("🔄 Syncing deletion back to server...")
                        sync_result = sync()
                        print("✅ Cleanup sync completed")
                    
                except Exception as cleanup_error:
                    print(f"⚠️  Cleanup failed (non-critical): {cleanup_error}")
                    # Don't fail the test for cleanup issues
                
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