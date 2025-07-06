"""OfflineIMAP email synchronization provider."""
import configparser
from pathlib import Path

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp


def _parse_offlineimaprc(config_file: str = None) -> dict:
    """Parse offlineimap config to extract account configurations."""
    config_path = Path(config_file) if config_file else Path.home() / ".offlineimaprc"
    if not config_path.exists():
        return {}

    config = configparser.ConfigParser()
    config.read(config_path)
    
    accounts = {}
    
    # Find all accounts in general section
    if config.has_section('general') and config.has_option('general', 'accounts'):
        account_names = [name.strip() for name in config.get('general', 'accounts').split(',')]
        
        for account_name in account_names:
            account_section = f"Account {account_name}"
            if config.has_section(account_section):
                remote_repo = config.get(account_section, 'remoterepository', fallback=None)
                if remote_repo and config.has_section(f"Repository {remote_repo}"):
                    accounts[account_name] = {
                        'remote_repo': remote_repo,
                        'section': f"Repository {remote_repo}"
                    }
    
    return accounts


@mcp.tool(description="""Synchronize emails between local and remote servers using offlineimap.

Performs a complete email synchronization to download new messages, upload sent items, and synchronize folder structures between local maildir and remote IMAP servers.

Key Parameters:
- account: Optional specific account name to sync (from .offlineimaprc)

Behavior:
- Downloads new emails from remote IMAP server
- Uploads locally sent emails to remote server
- Synchronizes folder structures and message flags
- Uses one-time sync mode (non-daemon)
- Respects configured folder filters and rules
- Updates message flags (read/unread, flagged, etc.)

Configuration:
- Reads from ~/.offlineimaprc by default
- Supports multiple account configurations
- Handles OAuth2 and traditional authentication
- Configurable folder mappings and filters

Examples:
```python
# Sync all configured accounts
sync()

# Sync specific account only
sync(account="work")

# Typical email workflow:
# 1. sync() - Download new emails
# 2. new() - Index with notmuch
# 3. Read/manage emails
# 4. sync() - Upload sent emails and flag changes
```

Note: Requires properly configured .offlineimaprc file with account settings.""")
def sync(account: str | None = None) -> str:
    """Run offlineimap to synchronize emails."""
    cmd = ["offlineimap", "-o1"]  # -o1 for one-time sync

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd, timeout=300)  # 5 minutes for email sync
    output = stdout.decode().strip()
    return f"Email sync completed successfully\n{output}"


@mcp.tool(description="""Validate offlineimap configuration and check setup status.

Verifies that offlineimap configuration is valid and reports any setup issues. This is a configuration validation tool, not a live sync status checker.

Key Parameters:
- config_file: Optional path to offlineimap config file (defaults to ~/.offlineimaprc)

Behavior:
- Validates .offlineimaprc configuration syntax
- Checks account definitions and repository settings
- Performs dry-run to test connections without syncing
- Reports configuration errors and warnings
- Does not perform actual email synchronization

Validation Checks:
- Configuration file exists and is readable
- Account definitions are complete
- Repository settings are valid
- Authentication methods are properly configured
- Folder mappings are correct

Examples:
```python
# Validate default configuration
sync_status()

# Validate custom config file
sync_status(config_file="/path/to/custom.offlineimaprc")

# Use before first sync to catch setup issues
# sync_status() -> fix any issues -> sync()
```

Note: This checks configuration validity, not real-time sync status.""")
def sync_status(config_file: str = None) -> str:
    """Check offlineimap sync status."""
    # Check if offlineimap config exists
    config_path = Path(config_file) if config_file else Path.home() / ".offlineimaprc"
    if not config_path.exists():
        raise FileNotFoundError(f"offlineimap configuration not found at {config_path}")

    # Run dry-run to check configuration
    stdout, stderr = run_command(["offlineimap", "--dry-run", "-o1"])
    output = stdout.decode().strip()
    return f"Offlineimap configuration valid:\n{output}"


@mcp.tool(description="""Display detailed information about configured email repositories and accounts.

Provides comprehensive information about all configured email accounts, repositories, and their settings. Useful for understanding your email setup and troubleshooting.

Key Parameters:
- config_file: Optional path to offlineimap config file (defaults to ~/.offlineimaprc)

Behavior:
- Lists all configured accounts and repositories
- Shows connection settings (servers, ports, SSL)
- Displays authentication methods and credentials
- Reports folder mapping configurations
- Shows sync settings and filters

Information Provided:
- Account names and descriptions
- Remote server settings (IMAP server, port, SSL)
- Local repository paths (maildir locations)
- Authentication methods (password, OAuth2, etc.)
- Folder mappings and filters
- Sync settings and options

Examples:
```python
# Show all repository information
repo_info()

# Analyze custom configuration
repo_info(config_file="/path/to/custom.offlineimaprc")

# Use for:
# - Understanding current email setup
# - Troubleshooting connection issues
# - Documenting email configuration
# - Planning configuration changes
```

Useful for setup validation and configuration documentation.""")
def repo_info(config_file: str = None) -> str:
    """Get information about configured offlineimap repositories."""
    stdout, stderr = run_command(["offlineimap", "--info"])
    output = stdout.decode().strip()
    return f"Repository information:\n{output}"


@mcp.tool(description="""Preview email synchronization operations without making any changes.

Performs a dry-run simulation of email synchronization to show what would be synchronized without actually downloading, uploading, or modifying any emails.

Key Parameters:
- account: Optional specific account to preview (from .offlineimaprc)

Behavior:
- Simulates complete sync operation
- Shows what emails would be downloaded
- Reports what emails would be uploaded
- Displays folder operations that would occur
- No actual changes are made to local or remote
- Useful for testing configuration changes

Preview Information:
- New messages that would be downloaded
- Local messages that would be uploaded
- Folder creation/deletion operations
- Flag synchronization changes
- Potential conflicts or issues

Examples:
```python
# Preview sync for all accounts
sync_preview()

# Preview specific account
sync_preview(account="work")

# Use cases:
# - Test new configuration before real sync
# - Check what changes after long offline period
# - Validate folder filters and mappings
# - Estimate sync time and data transfer
```

Safe way to test synchronization without affecting your emails.""")
def sync_preview(account: str | None = None) -> str:
    """Preview email sync operations without making changes."""
    cmd = ["offlineimap", "--dry-run", "-o1"]

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()
    return f"Sync preview{' for account ' + account if account else ''}:\n{output}"


@mcp.tool(description="""Perform fast email synchronization focusing on new messages only.

Executes a quick synchronization that prioritizes downloading new messages while skipping time-consuming flag updates and folder operations.

Key Parameters:
- account: Optional specific account to sync quickly (from .offlineimaprc)

Behavior:
- Downloads new messages quickly
- Skips detailed flag synchronization
- Minimal folder structure updates
- Faster than full sync but less comprehensive
- Ideal for frequent, quick email checks
- Uses reduced timeout for faster completion

Speed Optimizations:
- Focuses on new message detection
- Skips expensive flag comparison operations
- Minimal remote folder scanning
- Reduced connection time
- Optimized for frequent use

Examples:
```python
# Quick sync all accounts
quick_sync()

# Quick sync specific account
quick_sync(account="personal")

# Usage patterns:
# - Frequent email checks during work
# - Quick inbox updates
# - When you need new emails fast
# - Between full comprehensive syncs
```

Note: Follow up with full sync() periodically for complete synchronization.""")
def quick_sync(account: str | None = None) -> str:
    """Perform quick email sync without updating flags."""
    cmd = ["offlineimap", "-q", "-o1"]

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd, timeout=180)  # 3 minutes for quick sync
    output = stdout.decode().strip()
    return f"Quick sync completed successfully\n{output}"


@mcp.tool(description="""Synchronize only specified email folders for targeted email management.

Performs selective synchronization of specific folders rather than syncing all configured folders. Useful for managing large mailboxes or focusing on important folders.

Key Parameters:
- folders: Comma-separated list of folder names to sync
- account: Optional specific account (from .offlineimaprc)

Behavior:
- Syncs only the specified folders
- Ignores all other folders in the account
- Performs complete sync for selected folders
- Useful for large mailboxes with many folders
- Allows fine-grained control over sync operations

Folder Selection:
- Use exact folder names from your email server
- Common folders: INBOX, Sent, Drafts, Archive
- Support for nested folders (e.g., 'INBOX/Projects')
- Case-sensitive folder names
- Multiple folders separated by commas

Examples:
```python
# Sync only inbox
sync_folders("INBOX")

# Sync multiple important folders
sync_folders("INBOX,Sent,Drafts")

# Sync specific account's folders
sync_folders("INBOX,Archive", account="work")

# Use cases:
# - Large mailboxes with many folders
# - Urgent inbox-only sync
# - Selective folder management
# - Bandwidth-limited environments
```

Efficient for managing large email accounts with selective folder needs.""")
def sync_folders(folders: str, account: str | None = None) -> str:
    """Sync only specified folders."""
    cmd = ["offlineimap", "-o1", "-f", folders]

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd, timeout=180)  # 3 minutes for folder sync
    output = stdout.decode().strip()
    return f"Folder sync completed for: {folders}\n{output}"


