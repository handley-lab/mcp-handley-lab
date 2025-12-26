"""Unified email client MCP tool integrating all email providers."""

from pathlib import Path

from pydantic import Field

from mcp_handley_lab.common.process import run_command

# Import the shared mcp instance
from mcp_handley_lab.email.common import mcp

# Import tool modules to register their @mcp.tool decorators
from mcp_handley_lab.email.msmtp import tool as _msmtp  # noqa: F401
from mcp_handley_lab.email.mutt import tool as _mutt  # noqa: F401
from mcp_handley_lab.email.mutt_aliases import tool as _mutt_aliases  # noqa: F401
from mcp_handley_lab.email.notmuch import tool as _notmuch  # noqa: F401
from mcp_handley_lab.email.offlineimap import tool as _offlineimap  # noqa: F401


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
        try:
            children = list(account.iterdir())
        except NotADirectoryError:
            continue
        for child in children:
            if child.name in MAILDIR_LEAFS:
                continue
            try:
                list((child / "cur").iterdir())
                folders.add(f"{account.name}/{child.name}")
            except (NotADirectoryError, FileNotFoundError):
                continue
    return sorted(folders)


def _list_accounts(config_file: str = "") -> list[str]:
    """List available msmtp accounts by parsing msmtp config."""
    msmtprc_path = Path(config_file) if config_file else Path.home() / ".msmtprc"

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
