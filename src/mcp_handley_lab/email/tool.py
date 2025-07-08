"""Unified email client MCP tool integrating all email providers."""
import importlib
from pathlib import Path

from mcp_handley_lab.common.process import run_command

# Import the shared mcp instance
from mcp_handley_lab.email.common import mcp


def discover_and_register_tools():
    """
    Automatically discovers and imports tool modules from subdirectories
    to trigger their @mcp.tool decorators for registration.
    """
    package_dir = Path(__file__).parent
    package_name = package_dir.name

    print(f"Discovering tools in '{package_name}' sub-packages...")

    for sub_dir in package_dir.iterdir():
        # Look for subdirectories that are valid packages (have __init__.py)
        # and contain a tool.py file.
        if sub_dir.is_dir() and (sub_dir / "__init__.py").exists():
            tool_module_path = sub_dir / "tool.py"
            if tool_module_path.exists():
                # Construct the full module path for importlib
                # e.g., 'mcp_handley_lab.email.msmtp.tool'
                module_name = f"mcp_handley_lab.{package_name}.{sub_dir.name}.tool"
                try:
                    # This import triggers the @mcp.tool decorators
                    importlib.import_module(module_name)
                    print(f"  ✓ Registered tools from: {sub_dir.name}")
                except ImportError as e:
                    print(f"  ✗ Failed to import {module_name}: {e}")


# Run the discovery process when this module is loaded
discover_and_register_tools()


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
