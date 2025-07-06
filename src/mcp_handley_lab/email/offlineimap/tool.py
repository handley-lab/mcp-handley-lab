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


@mcp.tool(description="Synchronize emails using offlineimap with one-time sync.")
def sync(account: str | None = None) -> str:
    """Run offlineimap to synchronize emails."""
    cmd = ["offlineimap", "-o1"]  # -o1 for one-time sync

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd, timeout=300)  # 5 minutes for email sync
    output = stdout.decode().strip()
    return f"Email sync completed successfully\n{output}"


@mcp.tool(description="Get offlineimap sync status and information.")
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


@mcp.tool(description="Get information about configured email repositories.")
def repo_info(config_file: str = None) -> str:
    """Get information about configured offlineimap repositories."""
    stdout, stderr = run_command(["offlineimap", "--info"])
    output = stdout.decode().strip()
    return f"Repository information:\n{output}"


@mcp.tool(description="Preview what would be synced without actually syncing.")
def sync_preview(account: str | None = None) -> str:
    """Preview email sync operations without making changes."""
    cmd = ["offlineimap", "--dry-run", "-o1"]

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()
    return f"Sync preview{' for account ' + account if account else ''}:\n{output}"


@mcp.tool(description="Perform quick sync without updating message flags.")
def quick_sync(account: str | None = None) -> str:
    """Perform quick email sync without updating flags."""
    cmd = ["offlineimap", "-q", "-o1"]

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd, timeout=180)  # 3 minutes for quick sync
    output = stdout.decode().strip()
    return f"Quick sync completed successfully\n{output}"


@mcp.tool(description="Sync specific folders only.")
def sync_folders(folders: str, account: str | None = None) -> str:
    """Sync only specified folders."""
    cmd = ["offlineimap", "-o1", "-f", folders]

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd, timeout=180)  # 3 minutes for folder sync
    output = stdout.decode().strip()
    return f"Folder sync completed successfully\n{output}"


