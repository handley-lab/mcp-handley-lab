"""Shared MCP instance for unified email tool with module-level description injection."""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


class ToolConfig(TypedDict):
    fn: Callable[..., Any]
    description: str


# Tool configs for module-level description injection.
# Populated by provider modules (notmuch, mutt, offlineimap) before mcp.run().
_TOOL_CONFIGS: dict[str, ToolConfig] = {}


def _list_accounts(config_file: str = "") -> list[str]:
    """List available msmtp accounts by parsing msmtp config.

    Returns empty list if msmtprc doesn't exist (msmtp is optional).
    This is intentional graceful handling for discovery - tools still work
    without msmtp configured, they just won't have account list in descriptions.
    """
    msmtprc_path = Path(config_file) if config_file else Path.home() / ".msmtprc"

    accounts = []
    try:
        with open(msmtprc_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("account ") and not line.startswith(
                    "account default"
                ):
                    account_name = line.split()[1]
                    accounts.append(account_name)
    except FileNotFoundError:
        # msmtprc is optional - return empty list for discovery helpers
        pass
    return accounts


# Single, shared MCP instance for the entire email tool.
# All provider modules will import and use this instance.
mcp = FastMCP("Email")
