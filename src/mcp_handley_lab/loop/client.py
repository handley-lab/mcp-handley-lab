"""MCP Loop client - for spawning and managing loops.

Provides daemon autostart and a simple dict-based API for loop operations.
Used by both the MCP tool (tool.py) and standalone consumers (messenger).

Usage from within a Python loop:
    from mcp_handley_lab.loop.client import spawn, run, list_loops

    child_id = spawn("python", label="worker")
    result = run(child_id, "2 + 2")
    print(result)  # "4"
"""

import fcntl
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Daemon paths (matches daemon.py)
RUN_DIR = Path.home() / ".local" / "run"
STATE_DIR = Path.home() / ".local" / "state" / "mcp-loop"
SOCKET_PATH = RUN_DIR / "mcp-loop.sock"
PID_PATH = RUN_DIR / "mcp-loop.pid"
LOCK_PATH = RUN_DIR / "mcp-loop.lock"

STARTUP_TIMEOUT = 2.0

# Environment variables injected by daemon on spawn
ENV_SOCKET = "MCP_LOOP_SOCKET"
ENV_PARENT_ID = "MCP_LOOP_PARENT_ID"


def _get_socket_path() -> Path:
    """Get socket path from env or use default."""
    return Path(os.environ.get(ENV_SOCKET, str(SOCKET_PATH)))


def _get_parent_id() -> str:
    """Get parent loop_id from env (set by daemon on spawn)."""
    return os.environ.get(ENV_PARENT_ID, "")


def _socket_connectable() -> bool:
    """Check if socket exists and is connectable."""
    path = _get_socket_path()
    if not path.exists():
        return False
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(path))
        sock.close()
        return True
    except (ConnectionRefusedError, FileNotFoundError):
        return False


def _start_daemon() -> None:
    """Start the daemon process or verify it's running."""
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    lock_fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
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
        socket_path = _get_socket_path()
        if socket_path.exists() and PID_PATH.exists():
            try:
                pid = int(PID_PATH.read_text().strip())
                os.kill(pid, 0)
                if _socket_connectable():
                    return
            except (ValueError, ProcessLookupError, PermissionError):
                pass
            socket_path.unlink(missing_ok=True)

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


def _socket_connect() -> socket.socket:
    """Connect to daemon socket, starting daemon if needed."""
    socket_path = _get_socket_path()

    def new_socket() -> socket.socket:
        return socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    sock = new_socket()
    try:
        sock.connect(str(socket_path))
        return sock
    except (ConnectionRefusedError, FileNotFoundError):
        sock.close()

    _start_daemon()

    start = time.time()
    while time.time() - start < STARTUP_TIMEOUT:
        sock = new_socket()
        try:
            sock.connect(str(socket_path))
            return sock
        except (ConnectionRefusedError, FileNotFoundError):
            sock.close()
            time.sleep(0.1)

    raise RuntimeError(f"daemon failed to start; check {STATE_DIR / 'daemon.log'}")


def _send_request(request: dict[str, Any]) -> dict[str, Any]:
    """Send request to daemon and return response."""
    sock = _socket_connect()
    try:
        sock.sendall(json.dumps(request).encode() + b"\n")
        data = b""
        while b"\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                raise RuntimeError("daemon closed connection")
            data += chunk
        response = json.loads(data.decode())
        if not response.get("ok"):
            raise RuntimeError(
                f"{response.get('error_code', 'ERROR')}: {response.get('error', 'Unknown error')}"
            )
        return response
    finally:
        sock.close()


def spawn(
    backend: str,
    label: str = "",
    name: str = "",
    args: str = "",
    parent_id: str = "",
    cwd: str = "",
    prompt: str = "",
    child_allowed_tools: list[str] | None = None,
    sandbox: dict[str, list[str]] | None = None,
    session_id: str = "",
) -> str:
    """Spawn a child loop.

    Args:
        backend: Backend type (python, bash, julia, etc.)
        label: Human-readable label for tmux window
        name: Optional name suffix for loop_id
        args: Extra arguments for the backend
        parent_id: Override parent_id (default: current loop from env)
        cwd: Working directory for the spawned loop
        prompt: System prompt (for claude backend)
        child_allowed_tools: Tools the loop can use (for claude backend)
        sandbox: Mount spec {guest_path: [host_path, mode]} for namespace isolation
        session_id: Resume a previous session (for claude backend)

    Returns:
        loop_id of spawned child
    """
    request: dict[str, Any] = {
        "action": "spawn",
        "backend": backend,
        "label": label or backend,
        "name": name,
        "args": args,
        "parent_id": parent_id or _get_parent_id(),
        "cwd": cwd,
        "prompt": prompt,
        "child_allowed_tools": child_allowed_tools or [],
    }
    if sandbox:
        request["sandbox"] = sandbox
    if session_id:
        request["session_id"] = session_id
    response = _send_request(request)
    return response["loop_id"]


def run(loop_id: str, input: str, sync_timeout: float = 30.0) -> str:
    """Run input through a loop.

    Args:
        loop_id: Target loop
        input: Input to run (code for Python/Bash, natural language for Claude)
        sync_timeout: Seconds to wait for completion (default 30s)

    Returns:
        Output string
    """
    request = {
        "action": "run",
        "loop_id": loop_id,
        "input": input,
        "sync_timeout": sync_timeout,
    }
    response = _send_request(request)
    if response.get("running"):
        raise RuntimeError("Run timed out - use status() to check progress")
    return response.get("output", response.get("raw_output", ""))


def list_loops(
    parent_id: str = "",
    descendants_of: str = "",
) -> list[dict[str, Any]]:
    """List loops.

    Args:
        parent_id: Filter to direct children of this parent
        descendants_of: Filter to full subtree under this parent

    Returns:
        List of loop info dicts with loop_id, backend, parent_id, label
    """
    request = {
        "action": "list",
        "parent_id": parent_id,
        "descendants_of": descendants_of,
    }
    response = _send_request(request)
    return response.get("loops", [])


def session_id(loop_id: str) -> str:
    """Get the session_id for a loop (for resume after kill).

    Returns:
        Session ID string, or empty string if not available.
    """
    response = _send_request({"action": "list"})
    for loop in response.get("loops", []):
        if loop.get("loop_id") == loop_id:
            return loop.get("session_id", "")
    return ""


def status(loop_id: str) -> dict[str, Any]:
    """Get status of a loop.

    Returns:
        Dict with running (bool), cell_count, last_cell info
    """
    request = {"action": "status", "loop_id": loop_id}
    return _send_request(request)


def read(loop_id: str) -> list[dict[str, Any]]:
    """Read cells from a loop.

    Returns:
        List of cell dicts with index, input, output
    """
    request = {"action": "read", "loop_id": loop_id}
    response = _send_request(request)
    return response.get("cells", [])


def read_raw(loop_id: str) -> list[dict[str, Any]]:
    """Read cells with raw events from a loop.

    Returns:
        List of cell dicts with index, input, output, events
    """
    request = {"action": "read_raw", "loop_id": loop_id}
    response = _send_request(request)
    return json.loads(response.get("raw_output", "[]"))


def terminate(loop_id: str) -> bool:
    """Send Ctrl-C to interrupt a running eval.

    Returns:
        True if successful
    """
    request = {"action": "terminate", "loop_id": loop_id}
    response = _send_request(request)
    return response.get("ok", False)


def kill(loop_id: str) -> bool:
    """Force-kill a loop.

    Returns:
        True if successful
    """
    request = {"action": "kill", "loop_id": loop_id}
    response = _send_request(request)
    return response.get("ok", False)


def mount(loop_id: str, source: str, target: str) -> None:
    """Bind-mount source to target inside a sandboxed loop's namespace.

    Both source and target are guest paths (inside the namespace).
    """
    _send_request(
        {
            "action": "mount",
            "loop_id": loop_id,
            "source": source,
            "target": target,
        }
    )


def my_loop_id() -> str:
    """Get the loop_id of the current loop (from env)."""
    return _get_parent_id()
