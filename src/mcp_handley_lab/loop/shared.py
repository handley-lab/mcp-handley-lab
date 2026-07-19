"""Shared loop functions for direct use (no MCP required)."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, model_serializer

from mcp_handley_lab.loop.client import _socket_connect
from mcp_handley_lab.loop.protocol import Request, Response

# Session tracking paths
STATE_DIR = Path.home() / ".local" / "state" / "mcp-loop"
SESSION_DIR = STATE_DIR / "sessions"


class LoopInfo(BaseModel):
    """Information about a loop."""

    loop_id: str
    backend: str
    parent_id: str
    label: str
    orphaned: bool = False


class Cell(BaseModel):
    """A cell from REPL output."""

    index: int
    input: str
    output: str
    in_progress: bool = False


class ManageResult(BaseModel):
    """Result of manage action. Only relevant fields are populated."""

    model_config = ConfigDict(extra="forbid")

    # spawn
    loop_id: str | None = None
    parent_id: str | None = None
    label: str | None = None
    # list
    loops: list[LoopInfo] | None = None
    current_session_id: str | None = None  # for list: caller's session for context
    # read
    cells: list[Cell] | None = None
    # read_raw
    raw_output: str | None = None
    # status
    running: bool | None = None
    started_at: str | None = None
    elapsed_seconds: float | None = None
    # always present
    ok: bool = True

    @model_serializer
    def serialize(self) -> dict:
        """Exclude None fields from serialization."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


class RunResult(BaseModel):
    """Result of running input through a loop."""

    output: str = ""
    cell_index: int = 0
    elapsed_seconds: float = 0.0
    running: bool = False  # True if run still executing in background


def _get_session_id() -> str:
    """Get current session ID from hook file (keyed by git root hash)."""
    try:
        cwd = os.getcwd()
        # Normalize to git root
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        root = result.stdout.strip() if result.returncode == 0 else cwd
        root_hash = hashlib.md5(root.encode()).hexdigest()
        session_file = SESSION_DIR / root_hash
        if session_file.exists():
            return session_file.read_text().strip()
    except Exception as e:
        print(f"mcp-loop: warning: could not read session_id: {e}", file=sys.stderr)
    return ""


def _send_request(request: Request) -> Response:
    """Send request to daemon and return response."""
    sock = _socket_connect()
    try:
        sock.sendall(json.dumps(request.to_dict()).encode() + b"\n")
        data = b""
        while b"\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                raise RuntimeError("daemon closed connection")
            data += chunk
        return Response.from_dict(json.loads(data.decode()))
    finally:
        sock.close()


def manage(
    action: str,
    loop_id: str = "",
    parent_id: str = "",
    label: str = "",
    backend: str = "",
    name: str = "",
    args: str = "",
    cwd: str = "",
    prompt: str = "",
    session_id: str = "",
    descendants_of: str = "",
    child_allowed_tools: list[str] | None = None,
    venv: str = "",
    sandbox: dict[str, Any] | None = None,
) -> ManageResult:
    """Manage loops: spawn, list, read, read_raw, status, terminate, kill, prune.

    Args:
        action: One of spawn, list, read, read_raw, status, terminate, kill, prune.
        loop_id: Target loop ID (for read, status, terminate, kill, prune).
        parent_id: Session ID or parent loop ID (for spawn, list).
        label: Optional tag for tmux window naming (for spawn).
        backend: Backend type (for spawn).
        name: Backend name.
        args: Backend-specific args.
        cwd: Working directory (for spawn).
        prompt: System prompt (for spawn with claude backend).
        session_id: Resume a previous session (for spawn with claude backend).
        descendants_of: Filter to subtree (for list).
        child_allowed_tools: Allowed tools list (for spawn).
        venv: Path to venv (for spawn).
        sandbox: Mount spec dict (for spawn).

    Returns:
        ManageResult with action-specific fields populated.
    """
    current_session_id = _get_session_id()
    if action == "spawn" and not parent_id:
        parent_id = current_session_id

    request = Request(
        action=action,
        loop_id=loop_id,
        parent_id=parent_id,
        label=label,
        backend=backend,
        name=name,
        args=args,
        cwd=cwd,
        child_allowed_tools=child_allowed_tools or [],
        prompt=prompt,
        session_id=session_id,
        descendants_of=descendants_of,
        current_session_id=current_session_id if action == "list" else "",
        venv=venv,
        sandbox=sandbox or {},
    )

    response = _send_request(request)

    if not response.ok:
        raise RuntimeError(f"{response.error_code}: {response.error}")

    result = ManageResult(ok=response.ok)

    if response.loop_id:
        result.loop_id = response.loop_id
    if response.parent_id:
        result.parent_id = response.parent_id
    if response.label:
        result.label = response.label
    if response.current_session_id:
        result.current_session_id = response.current_session_id
    if response.loops:
        result.loops = [LoopInfo(**loop) for loop in response.loops]
    if response.cells:
        result.cells = [Cell(**cell) for cell in response.cells]
    if response.raw_output:
        result.raw_output = response.raw_output
    if response.running:
        result.running = response.running
    if response.started_at:
        result.started_at = response.started_at
    if response.elapsed_seconds:
        result.elapsed_seconds = response.elapsed_seconds

    return result


def run(
    loop_id: str,
    input: str,
    sync_timeout: float = 1.0,
) -> RunResult:
    """Run input through a loop.

    Args:
        loop_id: Target loop ID from spawn.
        input: Input to run (code for Python/Bash, natural language for Claude).
        sync_timeout: Seconds to wait. 0=return immediately, negative=block until done.

    Returns:
        RunResult with output, cell_index, elapsed_seconds, running.
    """
    request = Request(
        action="run",
        loop_id=loop_id,
        input=input,
        sync_timeout=sync_timeout,
    )

    response = _send_request(request)

    if not response.ok:
        raise RuntimeError(f"{response.error_code}: {response.error}")

    return RunResult(
        output=response.output,
        cell_index=response.cell_index,
        elapsed_seconds=response.elapsed_seconds,
        running=response.running,
    )
