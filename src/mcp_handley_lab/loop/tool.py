"""MCP Loop Tool - REPL orchestration with hierarchical namespaces."""

import fcntl
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, model_serializer

from mcp_handley_lab.loop.protocol import Request, Response

# Daemon paths
RUN_DIR = Path.home() / ".local" / "run"
STATE_DIR = Path.home() / ".local" / "state" / "mcp-loop"
SOCKET_PATH = RUN_DIR / "mcp-loop.sock"
PID_PATH = RUN_DIR / "mcp-loop.pid"
LOCK_PATH = RUN_DIR / "mcp-loop.lock"

STARTUP_TIMEOUT = 2.0
SOCKET_TIMEOUT = 3600.0  # 1 hour - generous for long evals


class LoopInfo(BaseModel):
    """Information about a loop."""

    loop_id: str
    backend: str
    namespace: str


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
    namespace: str | None = None
    # list
    loops: list[LoopInfo] | None = None
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


class EvalResult(BaseModel):
    """Result of code evaluation in a loop."""

    output: str = ""
    cell_index: int = 0
    elapsed_seconds: float = 0.0
    running: bool = False  # True if eval still running in background


class ManageArgs(BaseModel):
    """Input arguments for manage action."""

    action: str
    namespace: str
    loop_id: str = ""
    backend: str = ""
    name: str = ""
    args: str = ""
    child_allowed_tools: list[str] = Field(default_factory=list)


def _socket_connectable() -> bool:
    """Check if socket exists and is connectable."""
    if not SOCKET_PATH.exists():
        return False
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(SOCKET_PATH))
        sock.close()
        return True
    except (ConnectionRefusedError, FileNotFoundError):
        return False


def _socket_connect() -> socket.socket:
    """Connect to daemon socket, starting daemon if needed."""

    def new_socket() -> socket.socket:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(SOCKET_TIMEOUT)
        return sock

    # Try to connect
    sock = new_socket()
    try:
        sock.connect(str(SOCKET_PATH))
        return sock
    except (ConnectionRefusedError, FileNotFoundError):
        sock.close()

    # Need to start daemon
    _start_daemon()

    # Poll for connection - new socket per attempt
    start = time.time()
    while time.time() - start < STARTUP_TIMEOUT:
        sock = new_socket()
        try:
            sock.connect(str(SOCKET_PATH))
            return sock
        except (ConnectionRefusedError, FileNotFoundError):
            sock.close()
            time.sleep(0.1)

    raise RuntimeError(f"daemon failed to start; check {STATE_DIR / 'daemon.log'}")


def _start_daemon() -> None:
    """Start the daemon process or verify it's running.

    Raises RuntimeError if daemon cannot be started/verified.
    """
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    # Use lockfile to prevent double-spawn
    lock_fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        # Another process is starting the daemon - wait for socket
        os.close(lock_fd)
        start = time.time()
        while time.time() - start < STARTUP_TIMEOUT:
            if _socket_connectable():
                return
            time.sleep(0.1)
        raise RuntimeError(
            f"daemon startup lock held; timed out waiting for socket; check {STATE_DIR / 'daemon.log'}"
        ) from None

    try:
        # Check if daemon already running
        if SOCKET_PATH.exists() and PID_PATH.exists():
            try:
                pid = int(PID_PATH.read_text().strip())
                os.kill(pid, 0)
                # Process exists - verify socket is connectable
                if _socket_connectable():
                    return
            except (ValueError, ProcessLookupError, PermissionError):
                pass
            # Stale socket/PID, clean up
            SOCKET_PATH.unlink(missing_ok=True)

        # Spawn daemon - redirect stderr to log for debugging
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        log_path = STATE_DIR / "daemon.log"
        with open(log_path, "a") as log_file:
            subprocess.Popen(
                [sys.executable, "-m", "mcp_handley_lab.loop.daemon"],
                start_new_session=True,
                stdout=log_file,
                stderr=log_file,
            )
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


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
    Each loop has a namespace for isolation. Spawned loops get child namespaces.

    Actions:
    - spawn: Create new loop. Params: backend (required), name (optional), args (optional)
    - list: List loops visible to namespace
    - read: Get cells from loop. Params: loop_id
    - read_raw: Get raw terminal capture. Params: loop_id
    - status: Check if eval is running. Params: loop_id
    - terminate: Send Ctrl-C to interrupt. Params: loop_id
    - kill: Force-kill loop. Params: loop_id

    Available backends: bash, zsh, python, ipython, julia, R, clojure, apl, maple, ollama, mathematica

    Args:
        params: ManageArgs with action, namespace, and action-specific fields

    Returns:
        ManageResult with action-specific fields populated
    """
    request = Request(
        action=params.action,
        namespace=params.namespace,
        loop_id=params.loop_id,
        backend=params.backend,
        name=params.name,
        args=params.args,
        child_allowed_tools=params.child_allowed_tools,
    )

    response = _send_request(request)

    if not response.ok:
        raise RuntimeError(f"{response.error_code}: {response.error}")

    # Build result with only relevant fields (exclude_none in serialization)
    result = ManageResult(ok=response.ok)

    if response.loop_id:
        result.loop_id = response.loop_id
    if response.namespace:
        result.namespace = response.namespace
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
def eval(
    loop_id: str, code: str, namespace: str, sync_timeout: float = 1.0
) -> EvalResult:
    """
    Evaluate code in a loop.

    If eval completes within sync_timeout, returns result directly.
    If eval takes longer, returns immediately with running=True; use status/read to check progress.
    To interrupt, use manage(action="terminate") to send Ctrl-C.

    Args:
        loop_id: Target loop ID from spawn
        code: Code to evaluate
        namespace: Root namespace
        sync_timeout: Seconds to wait (default 1.0). 0=return immediately, negative=block until done.

    Returns:
        EvalResult with output, cell_index, elapsed_seconds. If running=True, eval continues in background.
    """
    request = Request(
        action="eval",
        namespace=namespace,
        loop_id=loop_id,
        code=code,
        sync_timeout=sync_timeout,
    )

    response = _send_request(request)

    if not response.ok:
        raise RuntimeError(f"{response.error_code}: {response.error}")

    return EvalResult(
        output=response.output,
        cell_index=response.cell_index,
        elapsed_seconds=response.elapsed_seconds,
        running=response.running,
    )
