"""Terminal auto-open for REPL sessions."""

import os
import shlex
import subprocess

from mcp_handley_lab.cli.config import load_config_safe


def _is_attached(session: str) -> bool:
    r = subprocess.run(["tmux", "list-clients", "-t", session], capture_output=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def maybe_open_terminal(session: str):
    """Open terminal if display available and no client attached."""
    if not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")):
        return
    if _is_attached(session):
        return

    cfg = load_config_safe().get("repl", {})
    if not cfg.get("auto_open_terminal", True):
        return

    # Use configured command, or fall back to $TERMINAL
    if cmd := cfg.get("terminal_command"):
        subprocess.Popen(
            shlex.split(cmd.format(session=session)), start_new_session=True
        )
    elif terminal := os.getenv("TERMINAL"):
        subprocess.Popen(
            [terminal, "-e", "tmux", "attach", "-t", session], start_new_session=True
        )
