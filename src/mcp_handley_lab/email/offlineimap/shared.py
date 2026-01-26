"""Core offlineimap email sync functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

from typing import Literal

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.shared.models import OperationResult


def sync(
    mode: Literal["full", "quick", "preview", "status", "info"] = "full",
    account: str = "",
    folders: str = "",
    config_file: str = "",
    timeout_seconds: int = 0,
) -> OperationResult:
    """Unified email synchronization with multiple modes.

    Args:
        mode: Sync mode: 'full' (complete), 'quick' (fast, new only), 'preview' (dry-run),
            'status' (validate config), 'info' (repo details).
        account: Optional account name to sync. If omitted, all accounts are synced.
        folders: Comma-separated folder names to sync (e.g., 'INBOX,Sent').
            If omitted, all folders are synced.
        config_file: Optional path to offlineimap config. Defaults to ~/.offlineimaprc.
        timeout_seconds: Timeout in seconds (0 uses mode defaults:
            full=300, quick/preview=180, status=60, info=120).

    Returns:
        OperationResult with sync status and details.
    """
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
