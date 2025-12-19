"""MSMTP configuration utilities."""

from pathlib import Path

from pydantic import Field

from mcp_handley_lab.email.common import mcp


def _parse_msmtprc(config_file: str = "") -> list[str]:
    """Parse msmtp config to extract account names."""
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
    description="List available msmtp accounts from ~/.msmtprc configuration. Use to discover valid account names for the send tool."
)
def list_accounts(
    config_file: str = Field(
        default="",
        description="Optional path to the msmtp configuration file. Defaults to `~/.msmtprc`.",
    ),
) -> list[str]:
    """List available msmtp accounts by parsing msmtp config."""
    accounts = _parse_msmtprc(config_file)

    return accounts
