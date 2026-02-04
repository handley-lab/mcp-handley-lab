"""MCP Loop client - for spawning child loops from within Python REPLs.

This module allows Python code running inside an mcp-loop to spawn and manage
child loops. Environment variables are injected by the daemon on spawn.

Usage from within a Python loop:
    from mcp_handley_lab.loop.client import spawn, eval_code, list_loops

    # Spawn a child loop (parent_id auto-set to current loop)
    child_id = spawn("python", label="worker")

    # Eval code in child
    result = eval_code(child_id, "2 + 2")
    print(result)  # "4"

    # List children
    children = list_loops()
"""

import json
import os
import socket
from pathlib import Path
from typing import Any

# Default socket path (same as daemon)
RUN_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "mcp-loop"
DEFAULT_SOCKET = RUN_DIR / "mcp-loop.sock"

# Environment variables injected by daemon
ENV_SOCKET = "MCP_LOOP_SOCKET"
ENV_PARENT_ID = "MCP_LOOP_PARENT_ID"


def _get_socket_path() -> Path:
    """Get socket path from env or use default."""
    return Path(os.environ.get(ENV_SOCKET, str(DEFAULT_SOCKET)))


def _get_parent_id() -> str:
    """Get parent loop_id from env (set by daemon on spawn)."""
    return os.environ.get(ENV_PARENT_ID, "")


def _send_request(request: dict[str, Any]) -> dict[str, Any]:
    """Send request to daemon and return response."""
    socket_path = _get_socket_path()
    if not socket_path.exists():
        raise RuntimeError(f"Daemon not running (socket not found: {socket_path})")

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(str(socket_path))
        sock.sendall(json.dumps(request).encode() + b"\n")

        # Read response
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break

        response = json.loads(data.decode().strip())
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
) -> str:
    """Spawn a child loop.

    Args:
        backend: Backend type (python, bash, julia, etc.)
        label: Human-readable label for tmux window
        name: Optional name suffix for loop_id
        args: Extra arguments for the backend
        parent_id: Override parent_id (default: current loop from env)

    Returns:
        loop_id of spawned child
    """
    request = {
        "action": "spawn",
        "backend": backend,
        "label": label or backend,
        "name": name,
        "args": args,
        "parent_id": parent_id or _get_parent_id(),
    }
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


# Convenience: expose current loop's ID
def my_loop_id() -> str:
    """Get the loop_id of the current loop (from env)."""
    return _get_parent_id()
