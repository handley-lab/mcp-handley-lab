"""OfflineIMAP email synchronization provider."""

from pathlib import Path
from typing import Literal

from pydantic import Field

from mcp_handley_lab.common.process import run_command
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
    config_path = Path(config_file) if config_file else Path.home() / ".offlineimaprc"

    if mode == "info":
        timeout = timeout_seconds or 120
        cmd = ["offlineimap", "--info"]
        if config_file:
            cmd.extend(["-c", config_file])
        stdout, _ = run_command(cmd, timeout=timeout)
        output = stdout.decode().strip()
        # Parse accounts from output
        accounts = [
            line.split()[-1]
            for line in output.splitlines()
            if line.strip().startswith("Account:")
        ]
        return OperationResult(
            status="success",
            message=f"Repository information:\n{output}",
            data={"raw": output, "accounts": accounts},
        )

    if mode == "status":
        if not config_path.exists():
            raise FileNotFoundError(f"Config not found at {config_path}")
        timeout = timeout_seconds or 60
        cmd = ["offlineimap", "--dry-run", "-o1"]
        if config_file:
            cmd.extend(["-c", config_file])
        if account:
            cmd.extend(["-a", account])
        stdout, _ = run_command(cmd, timeout=timeout)
        output = stdout.decode().strip()
        return OperationResult(
            status="success",
            message=f"Configuration valid:\n{output}",
            data={"raw": output, "valid": True},
        )

    # Build sync command
    cmd = ["offlineimap", "-o1"]

    if mode == "quick":
        cmd.append("-q")
    elif mode == "preview":
        cmd.append("--dry-run")

    if account:
        cmd.extend(["-a", account])
    if folders:
        cmd.extend(["-f", folders])
    if config_file:
        cmd.extend(["-c", config_file])

    timeout = timeout_seconds or (300 if mode == "full" else 180)
    stdout, _ = run_command(cmd, timeout=timeout)
    output = stdout.decode().strip()

    # Index new messages after actual sync (not preview mode)
    notmuch_output = ""
    if mode in ("full", "quick"):
        notmuch_stdout, _ = run_command(["notmuch", "new"], timeout=60)
        notmuch_output = notmuch_stdout.decode().strip()

    mode_desc = {"full": "Full", "quick": "Quick", "preview": "Preview"}
    message = f"{mode_desc.get(mode, mode)} sync completed:\n{output}"
    if notmuch_output:
        message += f"\n\nIndexing:\n{notmuch_output}"

    return OperationResult(
        status="success",
        message=message,
        data={"raw": output, "mode": mode, "indexed": notmuch_output},
    )
