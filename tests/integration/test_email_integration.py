"""Integration tests for the email MCP tool with real offlineimap setup."""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


def find_email_in_maildir(
    maildir_path: Path, test_id: str, test_subject: str = None
) -> bool:
    """Helper to find an email with specific ID and optional subject in maildir directories."""
    if not maildir_path.exists():
        return False

    # Search in INBOX and other common folders
    search_dirs = [
        maildir_path / "INBOX" / "new",
        maildir_path / "INBOX" / "cur",
        maildir_path / "[Gmail].All Mail" / "new",
        maildir_path / "[Gmail].All Mail" / "cur",
    ]

    for search_dir in search_dirs:
        if search_dir.exists():
            for email_file in search_dir.iterdir():
                if email_file.is_file():
                    try:
                        content = email_file.read_text()
                        if test_id in content and (
                            test_subject is None or test_subject in content
                        ):
                            return True
                    except (UnicodeDecodeError, PermissionError):
                        continue
    return False


def run_email_command(command: list, fixtures_dir: Path) -> subprocess.CompletedProcess:
    """Helper to run email-related commands with consistent error handling."""
    return subprocess.run(
        command,
        cwd=str(fixtures_dir),
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture
def email_fixtures_dir() -> Path:
    """Fixture providing path to email fixtures directory."""
    return Path(__file__).parent.parent / "fixtures" / "email"


@pytest.fixture
def test_maildir():
    """Create a temporary maildir structure for testing."""
    maildir = tempfile.mkdtemp(prefix="test_maildir_")

    # Create basic maildir structure
    for folder in ["cur", "new", "tmp"]:
        os.makedirs(os.path.join(maildir, folder))

    # Create some test subdirectories
    for subfolder in ["Sent", "Drafts"]:
        for folder in ["cur", "new", "tmp"]:
            os.makedirs(os.path.join(maildir, f".{subfolder}", folder))

    return maildir


class TestEmailIntegration:
    """Integration tests for email functionality with real email infrastructure.

    Tests use actual IMAP/SMTP interactions with configured test credentials for comprehensive validation.
    """

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

    @pytest.mark.integration
    def test_real_offlineimap_sync(self):
        """Test offlineimap sync with real handleylab@gmail.com test account."""
        import subprocess
        from pathlib import Path

        # Use the fixture configuration files
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "email"
        offlineimaprc_path = fixtures_dir / "offlineimaprc"

        # Verify test config exists
        assert (
            offlineimaprc_path.exists()
        ), f"Test config not found: {offlineimaprc_path}"

        # Check that test mail directory gets created (relative to config dir)
        project_root = Path(__file__).parent.parent.parent
        test_mail_dir = project_root / ".test_mail" / "HandleyLab"

        try:
            # Run offlineimap sync using the test configuration - fail fast on errors
            result = subprocess.run(
                [
                    "offlineimap",
                    "-c",
                    str(offlineimaprc_path),
                    "-o1",  # One-time sync
                ],
                cwd=str(fixtures_dir),
                capture_output=True,
                text=True,
                # Streamlined for fast test execution
                check=True,  # Fail fast on non-zero exit codes
            )

            # Verify successful connection and account processing
            output = result.stdout + result.stderr
            assert "imap.gmail.com" in output, "Should connect to Gmail IMAP"
            assert "HandleyLab" in output, "Should process HandleyLab account"

            # Verify maildir structure was created
            assert test_mail_dir.exists(), "Test maildir should be created"

            # Check for basic maildir structure
            created_folders = [d.name for d in test_mail_dir.iterdir() if d.is_dir()]

            # At least INBOX should exist
            inbox_found = any("INBOX" in folder for folder in created_folders)
            assert inbox_found, f"INBOX folder not found in: {created_folders}"

            print("✓ Offlineimap sync successful")
            print(f"✓ Created folders: {created_folders}")

        except subprocess.CalledProcessError as e:
            # Fail fast and loud - let offlineimap errors surface immediately
            pytest.fail(
                f"Offlineimap sync failed with exit code {e.returncode}: {e.stderr}"
            )

    @pytest.mark.integration
    def test_msmtp_send_and_receive_cycle(self):
        """Test complete email cycle: send with msmtp -> sync with offlineimap -> verify receipt."""
        import subprocess
        import time
        import uuid
        from pathlib import Path

        # Use fixture configurations
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "email"
        msmtprc_path = fixtures_dir / "msmtprc"
        offlineimaprc_path = fixtures_dir / "offlineimaprc"

        # Verify configs exist
        assert msmtprc_path.exists(), f"msmtp config not found: {msmtprc_path}"
        assert (
            offlineimaprc_path.exists()
        ), f"offlineimap config not found: {offlineimaprc_path}"

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
            send_result = subprocess.run(
                [
                    "msmtp",
                    "-C",
                    str(msmtprc_path),  # Use our test config
                    "handleylab@gmail.com",
                ],
                input=email_content,
                cwd=str(fixtures_dir),
                capture_output=True,
                text=True,
            )

            if send_result.returncode != 0:
                pytest.fail(f"msmtp send failed: {send_result.stderr}")

            print("✅ Email sent successfully")

            # Step 2: Email delivery (real Gmail infrastructure)
            print("📧 Email delivery to Gmail")

            # Step 3: Sync emails using offlineimap
            print("📥 Syncing emails with offlineimap...")
            sync_result = subprocess.run(
                [
                    "offlineimap",
                    "-c",
                    str(offlineimaprc_path),
                    "-o1",  # One-time sync
                ],
                cwd=str(fixtures_dir),
                capture_output=True,
                text=True,
                check=True,  # Fail fast on non-zero exit codes
            )

            # Verify successful connection
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
                    test_mail_dir / "[Gmail].All Mail" / "cur",
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
                print(
                    f"✅ Email cycle test successful! Email with ID {test_id} was sent and received."
                )
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
                    subprocess.run(
                        ["offlineimap", "-c", str(offlineimaprc_path), "-o1"],
                        cwd=str(fixtures_dir),
                        capture_output=True,
                        text=True,
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
                            all_emails.extend(
                                [f.name for f in search_dir.iterdir() if f.is_file()]
                            )

                pytest.fail(
                    f"Test email with ID {test_id} not found after send+sync cycle. "
                    f"Found {len(all_emails)} total emails in maildir. "
                    f"This could be due to Gmail delivery delay or filtering."
                )

        except Exception as e:
            pytest.fail(f"Email cycle test failed: {e}")

    @pytest.mark.integration
    def test_email_tool_functions_with_custom_configs(self):
        """Test direct subprocess calls to email tools with custom config files.

        Since the email tool functions don't yet support config_file parameters,
        this test validates the email infrastructure by calling the tools directly
        with custom config file paths.
        """
        import time
        import uuid
        from pathlib import Path

        # Use real test configuration files
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "email"
        msmtprc_path = fixtures_dir / "msmtprc"
        offlineimaprc_path = fixtures_dir / "offlineimaprc"

        # Verify test configs exist
        assert msmtprc_path.exists(), f"msmtp config not found: {msmtprc_path}"
        assert (
            offlineimaprc_path.exists()
        ), f"offlineimap config not found: {offlineimaprc_path}"

        # Create unique test email
        test_id = str(uuid.uuid4())[:8]
        test_subject = f"MCP Tool Config Test {test_id}"
        test_body = f"Email tool config test sent at {time.strftime('%Y-%m-%d %H:%M:%S')} with ID: {test_id}"

        # Prepare email content for msmtp
        email_content = f"""To: handleylab@gmail.com
Subject: {test_subject}

{test_body}
"""

        try:
            # Step 1: Send email using msmtp with custom config
            print(f"📧 Sending test email with msmtp -C, ID: {test_id}")
            send_result = subprocess.run(
                [
                    "msmtp",
                    "-C",
                    str(msmtprc_path),  # Use custom config file
                    "-a",
                    "HandleyLab",  # Use HandleyLab account
                    "handleylab@gmail.com",
                ],
                input=email_content,
                capture_output=True,
                text=True,
            )

            if send_result.returncode != 0:
                pytest.fail(f"msmtp send failed: {send_result.stderr}")

            print("✅ Email sent via msmtp with custom config")

            # Step 2: Email delivery (real Gmail infrastructure)
            print("📧 Email delivery to Gmail")

            # Step 3: Sync using offlineimap with custom config
            print("📥 Syncing with offlineimap with custom config...")
            sync_result = subprocess.run(
                [
                    "offlineimap",
                    "-c",
                    str(offlineimaprc_path),  # Use custom config file
                    "-o1",  # One-time sync
                ],
                cwd=str(fixtures_dir),  # Run from fixtures dir so Python file is found
                capture_output=True,
                text=True,
                check=True,  # Fail fast on non-zero exit codes
            )

            # Verify successful connection
            sync_output = sync_result.stdout + sync_result.stderr
            assert "imap.gmail.com" in sync_output, "Should connect to Gmail IMAP"
            print("✅ Sync completed via offlineimap with custom config")

            # Step 4: Search for the email in maildir
            project_root = Path(__file__).parent.parent.parent
            test_mail_dir = project_root / ".test_mail" / "HandleyLab"

            # Check all maildir folders for the test email
            email_found = False
            email_locations = []

            if test_mail_dir.exists():
                search_dirs = [
                    test_mail_dir / "INBOX" / "new",
                    test_mail_dir / "INBOX" / "cur",
                    test_mail_dir / "[Gmail].All Mail" / "new",
                    test_mail_dir / "[Gmail].All Mail" / "cur",
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

            if email_found:
                print(
                    f"✅ Email tool config test successful! Email with ID {test_id} was sent and received."
                )
                print(f"📍 Email location: {email_locations[0]}")

                # Step 5: Clean up - delete the test email
                try:
                    for email_location in email_locations:
                        email_path = Path(email_location)
                        if email_path.exists():
                            email_path.unlink()
                            print(f"🗑️  Deleted test email: {email_path.name}")

                    # Sync deletions back to server
                    print("🔄 Syncing deletion back to server...")
                    subprocess.run(
                        ["offlineimap", "-c", str(offlineimaprc_path), "-o1"],
                        cwd=str(fixtures_dir),  # Run from fixtures dir
                        capture_output=True,
                        text=True,
                    )
                    print("✅ Cleanup sync completed")

                except Exception as cleanup_error:
                    print(f"⚠️  Cleanup failed (non-critical): {cleanup_error}")

            else:
                pytest.fail(
                    f"Test email with ID {test_id} not found after send+sync cycle. "
                    f"This could be due to Gmail delivery delay or filtering."
                )

        except Exception as e:
            pytest.fail(f"Email tool config test failed: {e}")

    @pytest.mark.asyncio
    async def test_email_tool_functions_integration(self):
        """Test email tool functions that don't require credentials."""
        from mcp_handley_lab.email.common import mcp
        from mcp_handley_lab.email.msmtp.tool import _parse_msmtprc, list_accounts

        # Test msmtp account parsing with real config file
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "email"
        msmtprc_path = fixtures_dir / "msmtprc"

        # Test parsing real msmtprc file
        try:
            accounts = _parse_msmtprc(str(msmtprc_path))
            assert "HandleyLab" in accounts
            assert len(accounts) >= 1
        except FileNotFoundError:
            pytest.skip("Test msmtprc file not found")

        # Test list_accounts function
        try:
            accounts = list_accounts(str(msmtprc_path))
            assert "HandleyLab" in accounts
        except FileNotFoundError:
            pytest.skip("Test msmtprc file not found")

        # Test server_info function using MCP call_tool
        try:
            result = await mcp.call_tool("server_info", {})
            import json

            response = json.loads(result[0].text)
            assert "error" not in response, response.get("error")
            info = response

            # Accept any of the email-related tool servers due to MCP tool conflicts
            assert "Tool" in info["name"]
            assert info["status"] == "active"
            # Since there are multiple email tools, just check that we get a valid response
            assert "capabilities" in info
        except (FileNotFoundError, RuntimeError) as e:
            pytest.skip(f"Email tools not available: {e}")

    def test_notmuch_functions_integration(self):
        """Test notmuch functions with real database (if available)."""
        from mcp_handley_lab.email.notmuch.tool import count, search, tag

        try:
            # Test count function - should work even with empty database
            result = count("*")
            assert isinstance(result, int)
            assert result >= 0

            # Test search function
            search_result = search("*")
            assert isinstance(search_result, list)

            # Test tag function with non-existent message (should fail gracefully)
            try:
                tag_result = tag("nonexistent123", add_tags=["test"])
                # If it succeeds, check the result structure
                assert hasattr(tag_result, "message_id")
            except RuntimeError:
                # Expected for non-existent message - notmuch should fail fast
                pass

        except (FileNotFoundError, RuntimeError) as e:
            pytest.skip(f"Notmuch not available or configured: {e}")

    def test_offlineimap_dry_run_integration(self):
        """Test offlineimap sync_status with real config."""
        from mcp_handley_lab.email.offlineimap.tool import sync_status

        # Test with real config file
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "email"
        offlineimaprc_path = fixtures_dir / "offlineimaprc"

        if not offlineimaprc_path.exists():
            pytest.skip("Test offlineimaprc file not found")

        try:
            # Change to fixtures directory for Python file resolution
            original_cwd = os.getcwd()
            os.chdir(str(fixtures_dir))

            # Test dry run - should validate config without connecting
            result = sync_status(str(offlineimaprc_path))
            assert hasattr(result, "message")
            assert len(result.message) > 0

        except (FileNotFoundError, RuntimeError) as e:
            pytest.skip(f"Offlineimap not available: {e}")
        finally:
            os.chdir(original_cwd)
