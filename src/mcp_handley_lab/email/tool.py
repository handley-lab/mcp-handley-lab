"""Unified email client MCP tool integrating all email providers."""

import importlib
from pathlib import Path

from pydantic import Field

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

    for sub_dir in package_dir.iterdir():
        if sub_dir.is_dir() and (sub_dir / "__init__.py").exists():
            tool_module_path = sub_dir / "tool.py"
            if tool_module_path.exists():
                module_name = f"mcp_handley_lab.{package_name}.{sub_dir.name}.tool"
                importlib.import_module(module_name)


# Run the discovery process when this module is loaded
discover_and_register_tools()


def _list_tags() -> list[str]:
    """List all tags in the notmuch database."""
    stdout, _ = run_command(["notmuch", "search", "--output=tags", "*"])
    output = stdout.decode().strip()
    return sorted([tag.strip() for tag in output.split("\n") if tag.strip()])


MAILDIR_LEAFS = {"cur", "new", "tmp"}


def _list_folders() -> list[str]:
    """List maildir folders using shallow directory scan (fast; skips cur/new/tmp)."""
    db_path_stdout, _ = run_command(["notmuch", "config", "get", "database.path"])
    maildir_root = Path(db_path_stdout.decode().strip())

    folders: set[str] = set()
    for account in maildir_root.iterdir():
        if not account.is_dir():
            continue
        for child in account.iterdir():
            if (
                child.is_dir()
                and child.name not in MAILDIR_LEAFS
                and (child / "cur").is_dir()
            ):
                folders.add(f"{account.name}/{child.name}")
    return sorted(folders)


def _list_accounts(config_file: str = "") -> list[str]:
    """List available msmtp accounts by parsing msmtp config."""
    msmtprc_path = Path(config_file) if config_file else Path.home() / ".msmtprc"
    if not msmtprc_path.exists():
        raise FileNotFoundError(f"msmtp configuration not found at {msmtprc_path}")

    accounts = []
    with open(msmtprc_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("account ") and not line.startswith("account default"):
                account_name = line.split()[1]
                accounts.append(account_name)
    return accounts


@mcp.tool(
    description="""List email-related items. Types: 'tags' (notmuch tags), 'folders' (maildir folders), 'accounts' (msmtp send accounts)."""
)
def list(
    type: str = Field(
        ...,
        description="What to list: 'tags', 'folders', or 'accounts'.",
    ),
) -> list[str]:
    """Unified list command for email items."""
    if type == "tags":
        return _list_tags()
    elif type == "folders":
        return _list_folders()
    elif type == "accounts":
        return _list_accounts()
    else:
        raise ValueError(f"Unknown type: {type}. Use 'tags', 'folders', or 'accounts'.")
