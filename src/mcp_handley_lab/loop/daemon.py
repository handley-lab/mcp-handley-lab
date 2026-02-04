"""Loop daemon - asyncio Unix socket server.

Uses Unix process model: each loop has loop_id (like PID) and parent_id (like PPID).
No access control - if you know the loop_id, you can operate on it.
"""

import asyncio
import json
import logging
import os
import re
import signal
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp_handley_lab.loop.protocol import (
    ERROR_BACKEND_ERROR,
    ERROR_CANCELLED,
    ERROR_INVALID_REQUEST,
    ERROR_NOT_FOUND,
    Request,
    Response,
)

# Paths
RUN_DIR = Path.home() / ".local" / "run"
STATE_DIR = Path.home() / ".local" / "state" / "mcp-loop"
SOCKET_PATH = RUN_DIR / "mcp-loop.sock"
PID_PATH = RUN_DIR / "mcp-loop.pid"
STATE_PATH = STATE_DIR / "state.json"
LOG_PATH = STATE_DIR / "daemon.log"

IDLE_TIMEOUT = 30 * 60  # 30 minutes


def sanitize_label(label: str, fallback: str = "loop") -> str:
    """Sanitize label for tmux window naming compatibility."""
    # Replace spaces with dashes, remove special chars
    result = re.sub(r"[^a-zA-Z0-9_-]", "-", label).strip("-")
    return result if result else fallback


@dataclass
class LoopState:
    """State for a single loop."""

    loop_id: str
    backend: str
    parent_id: str  # session_id or loop_id of spawner
    label: str  # human-readable tag for tmux window naming
    pane_id: str = ""  # for tmux backend
    cancelled: bool = False
    eval_running: bool = False
    eval_started_at: float = 0.0
    eval_task: asyncio.Task | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "backend": self.backend,
            "parent_id": self.parent_id,
            "label": self.label,
            "pane_id": self.pane_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LoopState":
        # Migration: handle old state.json with 'namespace' field
        if "namespace" in d and "parent_id" not in d:
            namespace = d["namespace"]
            # Extract last component for label, parent_id is unknown
            label = namespace.split("/")[-1] if namespace else d.get("backend", "")
            logging.warning(
                f"Migrating loop {d['loop_id']} from namespace to parent-child model"
            )
            return cls(
                loop_id=d["loop_id"],
                backend=d["backend"],
                parent_id="",  # Unknown after migration
                label=label,
                pane_id=d.get("pane_id", ""),
            )
        return cls(
            loop_id=d["loop_id"],
            backend=d["backend"],
            parent_id=d.get("parent_id", ""),
            label=d.get("label", d.get("backend", "")),
            pane_id=d.get("pane_id", ""),
        )


class LoopDaemon:
    """Loop daemon managing loops with parent-child relationships."""

    def __init__(self):
        self.loops: dict[str, LoopState] = {}  # loop_id -> LoopState
        self.last_activity = time.time()
        self.running = True
        self.backends: dict[str, Any] = {}  # backend name -> backend instance

    def load_state(self):
        """Load persisted state. Re-adoption deferred to Phase 2."""
        if not STATE_PATH.exists():
            return
        data = json.loads(STATE_PATH.read_text())
        for loop_data in data.get("loops", []):
            state = LoopState.from_dict(loop_data)
            self.loops[state.loop_id] = state
            logging.info(f"Loaded loop {state.loop_id}")

    def save_state(self):
        """Persist state to disk atomically."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        data = {"loops": [s.to_dict() for s in self.loops.values()]}
        tmp_path = STATE_PATH.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2))
        tmp_path.rename(STATE_PATH)

    def _get_loop(self, loop_id: str) -> LoopState | None:
        """Get loop by ID (Unix philosophy: if you have the ID, you can use it)."""
        return self.loops.get(loop_id)

    def _get_descendants(
        self, parent_id: str, _visited: set[str] | None = None
    ) -> list[LoopState]:
        """Get all loops that are descendants of the given parent."""
        if _visited is None:
            _visited = set()
        if parent_id in _visited:
            return []  # Cycle detected - stop recursion
        _visited.add(parent_id)

        result = []
        # Direct children
        direct = [loop for loop in self.loops.values() if loop.parent_id == parent_id]
        result.extend(direct)
        # Recurse for grandchildren
        for child in direct:
            result.extend(self._get_descendants(child.loop_id, _visited))
        return result

    async def handle_request(self, request: Request) -> Response:
        """Handle a single request."""
        self.last_activity = time.time()

        action = request.action

        # No namespace check - Unix philosophy: operations just need loop_id

        if action == "spawn":
            return await self._spawn(request)
        elif action == "run":
            return await self._run(request)
        elif action == "read":
            return await self._read(request)
        elif action == "read_raw":
            return await self._read_raw(request)
        elif action == "list":
            return await self._list(request)
        elif action == "status":
            return await self._status(request)
        elif action == "terminate":
            return await self._terminate(request)
        elif action == "kill":
            return await self._kill(request)
        else:
            return Response.error_response(f"unknown action: {action}")

    async def _spawn(self, request: Request) -> Response:
        """Spawn a new loop."""
        if not request.backend:
            return Response.error_response("backend required", ERROR_INVALID_REQUEST)

        # Use provided label or default to backend name (both sanitized for tmux)
        label = sanitize_label(
            request.label if request.label else request.backend,
            fallback=request.backend,
        )

        try:
            backend = self._get_backend(request.backend)
            loop_id, pane_id = await asyncio.to_thread(
                backend.spawn,
                label,  # Use label for tmux window naming
                request.name,
                request.args,
                request.child_allowed_tools,
                str(SOCKET_PATH),  # For client library env injection
            )
        except Exception as e:
            return Response.error_response(str(e), ERROR_BACKEND_ERROR)

        state = LoopState(
            loop_id=loop_id,
            backend=request.backend,
            parent_id=request.parent_id,
            label=label,
            pane_id=pane_id,
        )
        self.loops[loop_id] = state
        self.save_state()

        return Response(
            ok=True, loop_id=loop_id, parent_id=request.parent_id, label=label
        )

    async def _run(self, request: Request) -> Response:
        """Run input through a loop. Returns immediately if takes longer than sync_timeout."""
        loop = self._get_loop(request.loop_id)
        if not loop:
            return Response.error_response(
                f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
            )

        # Reject if already running (no queuing)
        if loop.eval_running:
            return Response.error_response(
                f"run already in progress on {request.loop_id}", ERROR_INVALID_REQUEST
            )

        loop.cancelled = False
        loop.eval_running = True
        loop.eval_started_at = time.time()

        backend = self._get_backend(loop.backend)
        task = asyncio.create_task(
            asyncio.to_thread(
                backend.eval,
                loop.pane_id,
                request.input,
                lambda: loop.cancelled,
            )
        )
        loop.eval_task = task

        # sync_timeout >= 0: wait that long (0 = return immediately)
        # sync_timeout < 0: wait indefinitely (block until done)
        sync_timeout = request.sync_timeout

        try:
            if sync_timeout < 0:
                # Block until done
                result = await asyncio.shield(task)
            else:
                result = await asyncio.wait_for(
                    asyncio.shield(task), timeout=sync_timeout
                )

            if loop.cancelled:
                return Response.error_response("cancelled by user", ERROR_CANCELLED)

            elapsed = time.time() - loop.eval_started_at
            loop.eval_running = False
            loop.eval_started_at = 0.0
            return Response(
                ok=True,
                output=result["output"],
                cell_index=result.get("cell_index", 0),
                elapsed_seconds=elapsed,
            )
        except asyncio.TimeoutError:
            # Still running - return immediately, task continues in background
            asyncio.create_task(self._background_run_cleanup(loop, task))
            elapsed = time.time() - loop.eval_started_at
            return Response(
                ok=True,
                running=True,
                elapsed_seconds=elapsed,
            )
        except Exception as e:
            loop.eval_running = False
            loop.eval_started_at = 0.0
            return Response.error_response(str(e), ERROR_BACKEND_ERROR)

    async def _background_run_cleanup(self, loop: LoopState, task: asyncio.Task):
        """Wait for background run to complete and update state."""
        try:
            await task
        except Exception as e:
            logging.error(f"Background run error on {loop.loop_id}: {e}")
        finally:
            loop.eval_running = False
            loop.eval_started_at = 0.0
            loop.eval_task = None

    async def _read(self, request: Request) -> Response:
        """Read cells from a loop (does not acquire lock)."""
        loop = self._get_loop(request.loop_id)
        if not loop:
            return Response.error_response(
                f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
            )

        try:
            backend = self._get_backend(loop.backend)
            cells = await asyncio.to_thread(backend.read, loop.pane_id)
            return Response(ok=True, cells=cells)
        except Exception as e:
            return Response.error_response(str(e), ERROR_BACKEND_ERROR)

    async def _read_raw(self, request: Request) -> Response:
        """Read raw terminal output from a loop."""
        loop = self._get_loop(request.loop_id)
        if not loop:
            return Response.error_response(
                f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
            )

        try:
            backend = self._get_backend(loop.backend)
            raw = await asyncio.to_thread(backend.read_raw, loop.pane_id)
            return Response(ok=True, raw_output=raw)
        except Exception as e:
            return Response.error_response(str(e), ERROR_BACKEND_ERROR)

    async def _list(self, request: Request) -> Response:
        """List loops, optionally filtered by parent_id or descendants_of."""
        visible = []

        if request.descendants_of:
            # Get full subtree under this parent
            loops_to_show = self._get_descendants(request.descendants_of)
        elif request.parent_id:
            # Get direct children only
            loops_to_show = [
                loop
                for loop in self.loops.values()
                if loop.parent_id == request.parent_id
            ]
        else:
            # Show all loops
            loops_to_show = list(self.loops.values())

        for loop in loops_to_show:
            visible.append(
                {
                    "loop_id": loop.loop_id,
                    "backend": loop.backend,
                    "parent_id": loop.parent_id,
                    "label": loop.label,
                }
            )
        # Echo caller's session_id back for context (daemon is stateless re: sessions)
        return Response(
            ok=True, loops=visible, current_session_id=request.current_session_id
        )

    async def _status(self, request: Request) -> Response:
        """Get status of a loop."""
        loop = self._get_loop(request.loop_id)
        if not loop:
            return Response.error_response(
                f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
            )

        elapsed = time.time() - loop.eval_started_at if loop.eval_running else 0.0
        started_at = (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(loop.eval_started_at))
            if loop.eval_running
            else ""
        )

        return Response(
            ok=True,
            running=loop.eval_running,
            started_at=started_at,
            elapsed_seconds=elapsed,
        )

    async def _terminate(self, request: Request) -> Response:
        """Terminate (Ctrl-C) a loop's running eval."""
        loop = self._get_loop(request.loop_id)
        if not loop:
            return Response.error_response(
                f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
            )

        loop.cancelled = True
        try:
            backend = self._get_backend(loop.backend)
            await asyncio.to_thread(backend.terminate, loop.pane_id)
        except Exception as e:
            return Response.error_response(str(e), ERROR_BACKEND_ERROR)

        return Response(ok=True)

    async def _kill(self, request: Request) -> Response:
        """Force-kill a loop."""
        loop = self._get_loop(request.loop_id)
        if not loop:
            return Response.error_response(
                f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
            )

        try:
            backend = self._get_backend(loop.backend)
            await asyncio.to_thread(backend.kill, loop.pane_id)
        except Exception as e:
            return Response.error_response(str(e), ERROR_BACKEND_ERROR)

        del self.loops[request.loop_id]
        self.save_state()
        return Response(ok=True)

    def _get_backend(self, name: str) -> Any:
        """Get or create backend instance."""
        if name not in self.backends:
            from mcp_handley_lab.loop.backends import get_backend

            self.backends[name] = get_backend(name)
        return self.backends[name]


async def handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, daemon: LoopDaemon
):
    """Handle a single client connection."""
    try:
        while True:
            line = await reader.readline()
            if not line:
                break

            try:
                data = json.loads(line.decode())
                request = Request.from_dict(data)
                response = await daemon.handle_request(request)
            except json.JSONDecodeError as e:
                response = Response.error_response(f"invalid JSON: {e}")
            except Exception as e:
                response = Response.error_response(f"internal error: {e}")

            writer.write(json.dumps(response.to_dict()).encode() + b"\n")
            await writer.drain()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.error(f"Client handler error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()


async def idle_shutdown(daemon: LoopDaemon):
    """Shutdown daemon after idle timeout with no loops."""
    while daemon.running:
        await asyncio.sleep(60)
        idle_time = time.time() - daemon.last_activity
        if idle_time > IDLE_TIMEOUT and not daemon.loops:
            logging.info("Idle timeout reached with no loops, shutting down")
            daemon.running = False


def _socket_connectable(path: Path) -> bool:
    """Check if socket exists and is connectable."""
    if not path.exists():
        return False
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(path))
        sock.close()
        return True
    except (ConnectionRefusedError, FileNotFoundError):
        return False


async def run_daemon():
    """Run the loop daemon."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_PATH),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.info("Loop daemon starting")

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    if _socket_connectable(SOCKET_PATH):
        logging.error("Daemon already running (socket connectable)")
        raise RuntimeError("daemon already running")

    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()

    pid_tmp = PID_PATH.with_suffix(".tmp")
    pid_tmp.write_text(str(os.getpid()))
    pid_tmp.rename(PID_PATH)

    daemon = LoopDaemon()
    daemon.load_state()

    server = await asyncio.start_unix_server(
        lambda r, w: handle_client(r, w, daemon), path=str(SOCKET_PATH)
    )
    SOCKET_PATH.chmod(0o600)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: setattr(daemon, "running", False))

    idle_task = asyncio.create_task(idle_shutdown(daemon))
    logging.info(f"Loop daemon listening on {SOCKET_PATH}")

    try:
        while daemon.running:
            await asyncio.sleep(1)
    finally:
        idle_task.cancel()
        server.close()
        await server.wait_closed()
        daemon.save_state()
        SOCKET_PATH.unlink(missing_ok=True)
        PID_PATH.unlink(missing_ok=True)
        logging.info("Loop daemon stopped")


def main():
    """Entry point for daemon."""
    asyncio.run(run_daemon())


if __name__ == "__main__":
    main()
