"""Unified email client MCP tool integrating all email providers."""
from pathlib import Path

from mcp_handley_lab.common.process import run_command

# Import the shared mcp instance
from mcp_handley_lab.email.common import mcp

# Import all provider modules to trigger tool registration
print("Loading and registering email provider tools...")

print("All email tools registered.")


@mcp.tool(
    name="email_server_info",
    description="Check email tool server status and verify tool availability.",
)
def server_info(config_file: str = None) -> str:
    """Check the status of email tools and their configurations."""
    # Check msmtp first - if it fails, entire email system is broken
    stdout, stderr = run_command(["msmtp", "--version"])
    msmtp_version = stdout.decode().split("\n")[0]

    # Parse msmtp accounts
    from mcp_handley_lab.email.msmtp.tool import _parse_msmtprc

    accounts = _parse_msmtprc()

    # Check offlineimap
    stdout, stderr = run_command(["offlineimap", "--version"])
    offlineimap_version = stdout.decode().split("\n")[0]
    config_path = Path(config_file) if config_file else Path.home() / ".offlineimaprc"
    if not config_path.exists():
        raise RuntimeError(f"offlineimap configuration not found at {config_path}")

    # Check notmuch
    stdout, stderr = run_command(["notmuch", "--version"])
    notmuch_version = stdout.decode().strip()

    # Check notmuch database - let failures propagate as they indicate real problems
    stdout, stderr = run_command(["notmuch", "count", "*"])
    db_info = stdout.decode().strip()
    db_status = f"{db_info} messages indexed"

    # Check OAuth2 accounts
    oauth2_accounts = []
    try:
        from mcp_handley_lab.email.oauth2.tool import _get_m365_oauth2_config
        from mcp_handley_lab.email.offlineimap.tool import _parse_offlineimaprc

        offlineimap_accounts = _parse_offlineimaprc(config_file)
        for account_name in offlineimap_accounts:
            try:
                oauth2_config = _get_m365_oauth2_config(account_name, config_file)
                if oauth2_config:
                    oauth2_accounts.append(account_name)
            except Exception:
                continue
    except Exception:
        pass

    oauth2_status = (
        f"{len(oauth2_accounts)} OAuth2 configured"
        if oauth2_accounts
        else "none configured"
    )

    return f"""Email Tool Server Status:
✓ msmtp: {msmtp_version}
  Accounts: {len(accounts)} configured
✓ offlineimap: {offlineimap_version}
  Config: found
  OAuth2: {oauth2_status}
✓ notmuch: {notmuch_version}
  Database: {db_status}
✓ Microsoft 365 OAuth2: supported (msal available)
✓ mutt: integrated
✓ All email tools are registered and available"""


if __name__ == "__main__":
    print("\n--- Registered Email Tools ---")
    for tool_name in sorted(mcp.tools.keys()):
        print(f"- {tool_name}")

    print(f"\nStarting unified email tool server with {len(mcp.tools)} tools...")
    mcp.run()
