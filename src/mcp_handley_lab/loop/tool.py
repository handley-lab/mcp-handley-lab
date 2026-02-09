"""MCP Loop Tool - REPL orchestration with parent-child model.

Uses Unix process model: each loop has loop_id (like PID) and parent_id (like PPID).
No access control - if you know the loop_id, you can operate on it.
"""

import hashlib
import json
import os
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, model_serializer

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


class Cell(BaseModel):
    """A cell from REPL output."""

    index: int
    input: str
    output: str


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


class ManageArgs(BaseModel):
    """Input arguments for manage action."""

    action: str
    loop_id: str = ""
    parent_id: str = ""  # for spawn: session_id or parent loop_id
    label: str = ""  # for spawn: optional tag for tmux window naming
    backend: str = ""
    name: str = ""
    args: str = ""  # backend-specific args
    cwd: str = ""  # for spawn: working directory
    prompt: str = ""  # for spawn: system prompt (claude backend)
    descendants_of: str = ""  # for list: filter to subtree
    child_allowed_tools: list[str] = Field(default_factory=list)
    venv: str = (
        ""  # for spawn: path to venv (created with --system-site-packages if missing)
    )
    sandbox: str = ""  # for spawn: JSON mount spec {"guest": ["host", "rw|ro"], ...}


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
        import sys

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


mcp = FastMCP("Loop Tool")


@mcp.tool()
def manage(params: ManageArgs) -> ManageResult:
    """
    Manage loops: spawn, list, read, read_raw, status, terminate, kill.

    Loops are persistent REPL sessions (Python, Bash, Julia, etc.) that run in tmux.
    Uses Unix process model: each loop has loop_id (like PID) and parent_id (like PPID).
    If you know the loop_id, you can operate on it.

    Actions:
    - spawn: Create new loop. Params: backend (required), parent_id (optional), label (optional)
    - list: List loops. Params: parent_id (direct children), descendants_of (subtree)
    - read: Get cells from loop. Params: loop_id
    - read_raw: Get raw terminal capture. Params: loop_id
    - status: Check if run is in progress. Params: loop_id
    - terminate: Send Ctrl-C to interrupt. Params: loop_id
    - kill: Force-kill loop. Params: loop_id

    Available backends: bash, zsh, python, ipython, julia, R, clojure, apl, maple, ollama, mathematica, claude, gemini, openai

    Args:
        params: ManageArgs with action and action-specific fields

    Returns:
        ManageResult with action-specific fields populated. List includes current_session_id for context.
    """
    # For spawn: use provided parent_id, or fall back to session_id from hook file
    # For list: include current session_id for context in response
    session_id = _get_session_id()
    parent_id = params.parent_id
    if params.action == "spawn" and not parent_id:
        parent_id = session_id

    sandbox = json.loads(params.sandbox) if params.sandbox else {}

    request = Request(
        action=params.action,
        loop_id=params.loop_id,
        parent_id=parent_id,
        label=params.label,
        backend=params.backend,
        name=params.name,
        args=params.args,
        cwd=params.cwd,
        child_allowed_tools=params.child_allowed_tools,
        prompt=params.prompt,
        descendants_of=params.descendants_of,
        current_session_id=session_id if params.action == "list" else "",
        venv=params.venv,
        sandbox=sandbox,
    )

    response = _send_request(request)

    if not response.ok:
        raise RuntimeError(f"{response.error_code}: {response.error}")

    # Build result with only relevant fields (exclude_none in serialization)
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


@mcp.tool()
def run(loop_id: str, input: str, sync_timeout: float = 1.0) -> RunResult:
    """
    Run input through a loop.

    If run completes within sync_timeout, returns result directly.
    If run takes longer, returns immediately with running=True; use status/read to check progress.
    To interrupt, use manage(action="terminate") to send Ctrl-C.

    Args:
        loop_id: Target loop ID from spawn
        input: Input to run (code for Python/Bash, natural language for Claude)
        sync_timeout: Seconds to wait (default 1.0). 0=return immediately, negative=block until done.

    Returns:
        RunResult with output, cell_index, elapsed_seconds. If running=True, run continues in background.
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
