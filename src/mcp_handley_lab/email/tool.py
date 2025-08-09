"""Unified email client MCP tool integrating all email providers."""

import importlib
from pathlib import Path

from pydantic import Field

from mcp_handley_lab.common.process import run_command

# Import the shared mcp instance
from mcp_handley_lab.email.common import mcp
from mcp_handley_lab.shared.models import ServerInfo


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
def server_info(
    config_file: str = Field(
        default=None,
        description="Optional path to the offlineimap configuration file (e.g., ~/.offlineimaprc). If not provided, the default location will be used.",
    ),
) -> ServerInfo:
    """Check the configured status of email tools without running external commands."""
    # This function should report configured dependencies, not run them.

    dependencies = {
        "msmtp": "required",
        "offlineimap": "required",
        "notmuch": "required",
        "msal (for OAuth2)": "optional",
    }

    # Check for config files, which is a quick, non-blocking operation
    msmtprc_path = Path.home() / ".msmtprc"
    offlineimaprc_path = (
        Path(config_file) if config_file else Path.home() / ".offlineimaprc"
    )

    dependencies["msmtp_config"] = "found" if msmtprc_path.exists() else "not found"
    dependencies["offlineimap_config"] = (
        "found" if offlineimaprc_path.exists() else "not found"
    )

    # Check for msal import without subprocess
    try:
        import importlib.util

        spec = importlib.util.find_spec("msal")
        dependencies["msal_oauth2"] = "available" if spec else "not installed"
    except ImportError:
        dependencies["msal_oauth2"] = "not installed"

    return ServerInfo(
        name="Email Tool Server",
        version="1.9.4",
        status="active",  # Assumes active, relies on user to run health checks
        capabilities=["msmtp", "offlineimap", "notmuch", "mutt", "oauth2"],
        dependencies=dependencies,
    )


@mcp.tool(
    description="Actively checks email tool dependencies by running version commands."
)
def check_dependencies() -> str:
    """Actively tests email tool availability by running external commands."""
    results = []

    try:
        run_command(["msmtp", "--version"])
        results.append("✅ msmtp: available")
    except Exception as e:
        results.append(f"❌ msmtp: {e}")

    try:
        run_command(["offlineimap", "--version"])
        results.append("✅ offlineimap: available")
    except Exception as e:
        results.append(f"❌ offlineimap: {e}")

    try:
        run_command(["notmuch", "--version"])
        results.append("✅ notmuch: available")
    except Exception as e:
        results.append(f"❌ notmuch: {e}")

    return "\n".join(results)
