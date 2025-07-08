"""Unified email client MCP tool integrating all email providers."""
from pathlib import Path

from mcp_handley_lab.common.process import run_command

# Import the shared mcp instance
from mcp_handley_lab.email.common import mcp

# Import all provider modules to trigger tool registration


@mcp.tool(
    description="Checks status of all email tools (msmtp, offlineimap, notmuch) and their configurations."
)
def server_info(config_file: str = None) -> str:
    """Check the status of email tools and their configurations."""
    stdout, stderr = run_command(["msmtp", "--version"])
    msmtp_version = stdout.decode().split("\n")[0]

    from mcp_handley_lab.email.msmtp.tool import _parse_msmtprc

    accounts = _parse_msmtprc()

    stdout, stderr = run_command(["offlineimap", "--version"])
    offlineimap_version = stdout.decode().split("\n")[0]
    config_path = Path(config_file) if config_file else Path.home() / ".offlineimaprc"
    if not config_path.exists():
        raise RuntimeError(f"offlineimap configuration not found at {config_path}")

    stdout, stderr = run_command(["notmuch", "--version"])
    notmuch_version = stdout.decode().strip()

    stdout, stderr = run_command(["notmuch", "count", "*"])
    db_info = stdout.decode().strip()
    db_status = f"{db_info} messages indexed"

    try:
        import importlib.util

        spec = importlib.util.find_spec("msal")
        oauth2_status = (
            "supported (msal available)"
            if spec
            else "not supported (msal not installed)"
        )
    except ImportError:
        oauth2_status = "not supported (msal not installed)"

    return f"""Email Tool Server Status:
✓ msmtp: {msmtp_version}
  Accounts: {len(accounts)} configured
✓ offlineimap: {offlineimap_version}
  Config: found
✓ notmuch: {notmuch_version}
  Database: {db_status}
✓ Microsoft 365 OAuth2: {oauth2_status}
✓ mutt: integrated
✓ All email tools are registered and available"""


if __name__ == "__main__":
    mcp.run()
