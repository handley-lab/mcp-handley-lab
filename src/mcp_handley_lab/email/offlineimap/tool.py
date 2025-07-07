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
    if config.has_section("general") and config.has_option("general", "accounts"):
        account_names = [
            name.strip() for name in config.get("general", "accounts").split(",")
        ]

        for account_name in account_names:
            account_section = f"Account {account_name}"
            if config.has_section(account_section):
                remote_repo = config.get(
                    account_section, "remoterepository", fallback=None
                )
                if remote_repo and config.has_section(f"Repository {remote_repo}"):
                    accounts[account_name] = {
                        "remote_repo": remote_repo,
                        "section": f"Repository {remote_repo}",
                    }

    return accounts


@mcp.tool(
    description="Performs a full, one-time email synchronization for one or all accounts configured in `~/.offlineimaprc`. Downloads new mail, uploads sent items, and syncs flags and folders between local and remote servers. An optional `account` name can be specified to sync only that account."
)
def sync(account: str | None = None) -> str:
    """Run offlineimap to synchronize emails."""
    cmd = ["offlineimap", "-o1"]  # -o1 for one-time sync

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd, timeout=300)  # 5 minutes for email sync
    output = stdout.decode().strip()
    return f"Email sync completed successfully\n{output}"


@mcp.tool(
    description="Validates the `~/.offlineimaprc` configuration by performing a dry run without actually syncing any mail. This is used to check for syntax errors, connection issues, or other setup problems before running a real sync."
)
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


@mcp.tool(
    description="Displays comprehensive information about all configured email accounts, repositories, and their settings from `~/.offlineimaprc`. Shows connection details, authentication methods, and folder mappings. Useful for troubleshooting and understanding your email setup."
)
def repo_info(config_file: str = None) -> str:
    """Get information about configured offlineimap repositories."""
    stdout, stderr = run_command(["offlineimap", "--info"])
    output = stdout.decode().strip()
    return f"Repository information:\n{output}"


@mcp.tool(
    description="Performs a dry-run simulation of email synchronization to show what would be synchronized without actually downloading, uploading, or modifying any emails. Useful for testing configuration changes and understanding sync operations before committing."
)
def sync_preview(account: str | None = None) -> str:
    """Preview email sync operations without making changes."""
    cmd = ["offlineimap", "--dry-run", "-o1"]

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()
    return f"Sync preview{' for account ' + account if account else ''}:\n{output}"


@mcp.tool(
    description="Performs fast email synchronization focusing on new messages while skipping time-consuming flag updates and folder operations. Downloads new emails quickly but less comprehensive than full sync. Ideal for frequent email checks."
)
def quick_sync(account: str | None = None) -> str:
    """Perform quick email sync without updating flags."""
    cmd = ["offlineimap", "-q", "-o1"]

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd, timeout=180)  # 3 minutes for quick sync
    output = stdout.decode().strip()
    return f"Quick sync completed successfully\n{output}"


@mcp.tool(
    description="Syncs only specified folders rather than all configured folders. Provide comma-separated folder names to sync selectively. Useful for large mailboxes or focusing on important folders like 'INBOX,Sent,Drafts'. Efficient for managing large email accounts with selective folder needs."
)
def sync_folders(folders: str, account: str | None = None) -> str:
    """Sync only specified folders."""
    cmd = ["offlineimap", "-o1", "-f", folders]

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd, timeout=180)  # 3 minutes for folder sync
    output = stdout.decode().strip()
    return f"Folder sync completed for: {folders}\n{output}"
