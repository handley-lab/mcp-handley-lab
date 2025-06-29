#!/usr/bin/env python3
"""
Email test environment setup script.

This script helps create a controlled test environment for email tools,
similar to how Google Calendar tests work with test credentials.
"""
import os
import tempfile
import shutil
from pathlib import Path
import subprocess
import sys


def create_test_configs():
    """Create test configuration files for email tools."""
    
    test_dir = Path.home() / ".email_test"
    test_dir.mkdir(exist_ok=True)
    
    print(f"Creating test environment in: {test_dir}")
    
    # 1. Create test offlineimap config
    offlineimap_config = test_dir / "offlineimaprc"
    offlineimap_content = f"""
# Test OfflineIMAP Configuration
[general]
accounts = TestGmail
maxsyncaccounts = 1
pythonfile = 

[Account TestGmail]
localrepository = TestGmail-Local
remoterepository = TestGmail-Remote
status_backend = sqlite
postsynchook = notmuch new

[Repository TestGmail-Local]
type = Maildir
localfolders = {test_dir}/maildir
restoreatime = no

[Repository TestGmail-Remote]
type = Gmail
remoteuser = test@gmail.com
# Use OAuth2 or app password for testing
remotepasseval = get_test_password()
realdelete = no
maxconnections = 1
folderfilter = lambda folder: folder in ['INBOX', '[Gmail]/Sent Mail', '[Gmail]/Drafts']
ssl = yes
sslcacertfile = /etc/ssl/certs/ca-certificates.crt

# Function to get test password
pythonfile = {test_dir}/offlineimap_helpers.py
"""
    
    with open(offlineimap_config, 'w') as f:
        f.write(offlineimap_content)
    
    # 2. Create helper Python file for offlineimap
    helpers_file = test_dir / "offlineimap_helpers.py"
    helpers_content = """
import os

def get_test_password():
    '''Get test email password from environment or file.'''
    # Try environment variable first
    password = os.getenv('EMAIL_TEST_PASSWORD')
    if password:
        return password
    
    # Try password file
    password_file = os.path.expanduser('~/.email_test/password')
    if os.path.exists(password_file):
        with open(password_file, 'r') as f:
            return f.read().strip()
    
    raise ValueError("No test password found. Set EMAIL_TEST_PASSWORD env var or create ~/.email_test/password file")
"""
    
    with open(helpers_file, 'w') as f:
        f.write(helpers_content)
    
    # 3. Create test msmtp config
    msmtp_config = test_dir / "msmtprc"
    msmtp_content = f"""
# Test MSMTP Configuration
defaults
auth           on
tls            on
tls_trust_file /etc/ssl/certs/ca-certificates.crt
logfile        {test_dir}/msmtp.log

# Test Gmail account
account        test_gmail
host           smtp.gmail.com
port           587
from           test@gmail.com
user           test@gmail.com
passwordeval   "cat {test_dir}/password"

# Default account
account default : test_gmail
"""
    
    with open(msmtp_config, 'w') as f:
        f.write(msmtp_content)
    
    # Set proper permissions for msmtp config
    os.chmod(msmtp_config, 0o600)
    
    # 4. Create maildir structure
    maildir = test_dir / "maildir"
    maildir.mkdir(exist_ok=True)
    
    for folder in ['cur', 'new', 'tmp']:
        (maildir / folder).mkdir(exist_ok=True)
    
    # Create some test subfolders
    for subfolder in ['.Sent', '.Drafts', '.Archive']:
        for folder in ['cur', 'new', 'tmp']:
            (maildir / subfolder / folder).mkdir(parents=True, exist_ok=True)
    
    # 5. Create sample test messages
    create_test_messages(maildir)
    
    return test_dir


def create_test_messages(maildir):
    """Create some sample email messages for testing."""
    
    # Sample message in new folder
    test_msg = """Return-Path: <test@example.com>
Delivered-To: testuser@localhost
Received: from example.com
Date: Thu, 28 Jun 2025 10:00:00 +0000
From: Test Sender <test@example.com>
To: Test User <testuser@localhost>
Subject: Test Message for Email Tool
Message-ID: <test123@example.com>

This is a test message for the MCP email tool integration tests.

It contains some sample content for testing search and tagging functionality.

Tags: test, sample, integration
"""
    
    # Write to new folder
    new_msg = maildir / "new" / "test_message_001"
    with open(new_msg, 'w') as f:
        f.write(test_msg)
    
    # Another message in cur folder (seen)
    seen_msg = """Return-Path: <important@example.com>
Date: Thu, 28 Jun 2025 09:00:00 +0000  
From: Important Sender <important@example.com>
To: Test User <testuser@localhost>
Subject: Important Test Message
Message-ID: <important123@example.com>

This is an important test message.

Priority: high
Category: work
"""
    
    cur_msg = maildir / "cur" / "important_message_001:2,S"
    with open(cur_msg, 'w') as f:
        f.write(seen_msg)


def setup_notmuch_database(test_dir):
    """Initialize notmuch database for testing."""
    
    maildir = test_dir / "maildir"
    
    # Create notmuch config
    notmuch_config = test_dir / ".notmuch-config"
    config_content = f"""
[database]
path={maildir}

[user]
name=Test User
primary_email=testuser@localhost
other_email=test@localhost

[new]
tags=unread;inbox
ignore=

[search]
exclude_tags=deleted;spam

[maildir]
synchronize_flags=true
"""
    
    with open(notmuch_config, 'w') as f:
        f.write(config_content)
    
    # Initialize notmuch database
    try:
        env = os.environ.copy()
        env['NOTMUCH_CONFIG'] = str(notmuch_config)
        
        # Initialize database
        result = subprocess.run([
            'notmuch', 'setup'
        ], env=env, capture_output=True, text=True, input='\n\n\n\n\n')
        
        if result.returncode != 0:
            print(f"Warning: notmuch setup failed: {result.stderr}")
            return False
        
        # Scan for messages
        result = subprocess.run([
            'notmuch', 'new'
        ], env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✓ Notmuch database initialized with {result.stdout.strip()}")
            return True
        else:
            print(f"Warning: notmuch new failed: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("Warning: notmuch not found, skipping database setup")
        return False


def create_password_file(test_dir):
    """Create a template password file."""
    
    password_file = test_dir / "password"
    
    if not password_file.exists():
        print(f"\nCreate password file at: {password_file}")
        print("Enter your test email password (or app password):")
        
        try:
            password = input().strip()
            if password:
                with open(password_file, 'w') as f:
                    f.write(password)
                os.chmod(password_file, 0o600)
                print("✓ Password file created")
            else:
                print("No password entered, you'll need to create this manually")
        except KeyboardInterrupt:
            print("\nSkipping password setup")


def run_tests_with_config(test_dir):
    """Run email tool tests with the test configuration."""
    
    # Set environment variables to use test configs
    env = os.environ.copy()
    env.update({
        'HOME': str(test_dir.parent),  # So ~/.email_test is found
        'OFFLINEIMAPRC': str(test_dir / "offlineimaprc"),
        'MSMTPRC': str(test_dir / "msmtprc"),
        'NOTMUCH_CONFIG': str(test_dir / ".notmuch-config"),
        'ENABLE_EMAIL_INTEGRATION_TESTS': '1'
    })
    
    # Create symlinks in fake home directory
    fake_home = test_dir.parent
    
    # Link configs to expected locations
    configs = [
        ('.offlineimaprc', test_dir / "offlineimaprc"),
        ('.msmtprc', test_dir / "msmtprc"),
        ('.notmuch-config', test_dir / ".notmuch-config")
    ]
    
    for link_name, target in configs:
        link_path = fake_home / link_name
        if link_path.exists():
            link_path.unlink()
        link_path.symlink_to(target)
    
    print(f"\n Running tests with environment:")
    print(f"  HOME={env['HOME']}")
    print(f"  OFFLINEIMAPRC={env.get('OFFLINEIMAPRC', 'default')}")
    print(f"  MSMTPRC={env.get('MSMTPRC', 'default')}")
    print(f"  NOTMUCH_CONFIG={env.get('NOTMUCH_CONFIG', 'default')}")
    
    # Run the integration tests
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            'tests/test_email_integration.py', 
            '-v', '--tb=short'
        ], env=env, cwd=Path.cwd())
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error running tests: {e}")
        return False


def main():
    """Main setup function."""
    
    print("Email Tool Test Environment Setup")
    print("================================")
    
    if len(sys.argv) > 1 and sys.argv[1] == '--clean':
        # Clean up test environment
        test_dir = Path.home() / ".email_test"
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"✓ Cleaned up test environment: {test_dir}")
        return
    
    # Create test environment
    test_dir = create_test_configs()
    print(f"✓ Test configs created in: {test_dir}")
    
    # Setup notmuch database
    if setup_notmuch_database(test_dir):
        print("✓ Notmuch database initialized")
    
    # Create password file
    create_password_file(test_dir)
    
    print(f"\n✓ Test environment ready!")
    print(f"\nTo use this test environment:")
    print(f"  1. Edit {test_dir}/offlineimaprc with real test account details")
    print(f"  2. Edit {test_dir}/msmtprc with real SMTP settings")
    print(f"  3. Run: python tests/email_test_setup.py --run-tests")
    print(f"\nTo clean up:")
    print(f"  python tests/email_test_setup.py --clean")
    
    if len(sys.argv) > 1 and sys.argv[1] == '--run-tests':
        print("\nRunning integration tests...")
        success = run_tests_with_config(test_dir)
        if success:
            print("✓ All tests passed!")
        else:
            print("✗ Some tests failed")


if __name__ == "__main__":
    main()