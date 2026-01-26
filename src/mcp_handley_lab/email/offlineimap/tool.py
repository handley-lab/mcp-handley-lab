"""OfflineIMAP email synchronization provider."""

from typing import Literal

from pydantic import Field

from mcp_handley_lab.email.common import mcp
from mcp_handley_lab.shared.models import OperationResult


@mcp.tool(
    description="""Unified email synchronization tool. Modes: 'full' (complete sync), 'quick' (new messages only), 'preview' (dry-run), 'status' (validate config), 'info' (show repo details). Use 'folders' param to sync specific folders only."""
)
def sync(
    mode: Literal["full", "quick", "preview", "status", "info"] = Field(
        default="full",
        description="Sync mode: 'full' (complete), 'quick' (fast, new only), 'preview' (dry-run), 'status' (validate config), 'info' (repo details).",
    ),
    account: str = Field(
        default="",
        description="Optional account name to sync. If omitted, all accounts are synced.",
    ),
    folders: str = Field(
        default="",
        description="Comma-separated folder names to sync (e.g., 'INBOX,Sent'). If omitted, all folders are synced.",
    ),
    config_file: str = Field(
        default="",
        description="Optional path to offlineimap config. Defaults to ~/.offlineimaprc.",
    ),
    timeout_seconds: int = Field(
        default=0,
        description="Timeout in seconds (0 uses mode defaults: full=300, quick/preview=180, status=60, info=120).",
        ge=0,
    ),
) -> OperationResult:
    """Unified email synchronization with multiple modes."""
    from mcp_handley_lab.email.offlineimap.shared import sync as _sync

    return _sync(
        mode=mode,
        account=account,
        folders=folders,
        config_file=config_file,
        timeout_seconds=timeout_seconds,
    )
