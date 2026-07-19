"""Loop daemon - threaded Unix socket server.

Uses Unix process model: each loop has loop_id (like PID) and parent_id (like PPID).
No access control - if you know the loop_id, you can operate on it.
"""

import json
import logging
import os
import re
import signal
import socket
import socketserver
import subprocess
import threading
import time
from dataclasses import dataclass, field
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
    session_id: str = ""  # for claude/gemini: resume token
    sandbox_pid: int = 0  # PID of sandboxed process (for nsenter)
    cancelled: bool = False
    eval_running: bool = False
    eval_started_at: float = 0.0
    eval_thread: threading.Thread | None = None
    run_seq: int = 0  # generation counter for background eval guard
    lock: threading.Lock = field(default_factory=threading.Lock)

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "backend": self.backend,
            "parent_id": self.parent_id,
            "label": self.label,
            "pane_id": self.pane_id,
            "session_id": self.session_id,
            "sandbox_pid": self.sandbox_pid,
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
            session_id=d.get("session_id", ""),
            sandbox_pid=d.get("sandbox_pid", 0),
        )


class LoopDaemon:
    """Loop daemon managing loops with parent-child relationships."""

    def __init__(self):
        self.loops: dict[str, LoopState] = {}  # loop_id -> LoopState
        self.last_activity = time.time()
        self.running = True
        self.backends: dict[str, Any] = {}  # backend name -> backend instance
        self._lock = threading.RLock()  # protects self.loops and self.backends

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
        """Persist state to disk atomically. Caller must hold self._lock."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        data = {"loops": [s.to_dict() for s in self.loops.values()]}
        tmp_path = STATE_PATH.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2))
        tmp_path.rename(STATE_PATH)

    def _get_loop(self, loop_id: str) -> LoopState | None:
        """Get loop by ID. Acquires and releases _lock."""
        with self._lock:
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

        # Snapshot under lock
        with self._lock:
            all_loops = list(self.loops.values())

        result = []
        # Direct children
        direct = [loop for loop in all_loops if loop.parent_id == parent_id]
        result.extend(direct)
        # Recurse for grandchildren
        for child in direct:
            result.extend(self._get_descendants(child.loop_id, _visited))
        return result

    def _is_session_alive(self, session_id: str) -> bool:
        """Check if a Claude Code session is still running via its task lock file."""
        lock_path = Path.home() / ".claude" / "tasks" / session_id / ".lock"
        if not lock_path.exists():
            return False
        try:
            result = subprocess.run(["lsof", str(lock_path)], capture_output=True)
        except FileNotFoundError:
            return True  # lsof not available — assume alive (conservative)
        return result.returncode == 0

    def _is_orphaned(
        self, loop: LoopState, session_cache: dict[str, bool] | None = None
    ) -> bool:
        """Check if a loop's parent is dead."""
        pid = loop.parent_id
        if not pid:
            return False  # intentionally parentless
        with self._lock:
            if pid in self.loops:
                return False  # parent is a living loop
        if session_cache is not None:
            if pid not in session_cache:
                session_cache[pid] = self._is_session_alive(pid)
            return not session_cache[pid]
        return not self._is_session_alive(pid)

    def handle_request(self, request: Request) -> Response:
        """Handle a single request."""
        self.last_activity = time.time()

        action = request.action

        if action == "spawn":
            return self._spawn(request)
        elif action == "run":
            return self._run(request)
        elif action == "read":
            return self._read(request)
        elif action == "read_raw":
            return self._read_raw(request)
        elif action == "list":
            return self._list(request)
        elif action == "status":
            return self._status(request)
        elif action == "terminate":
            return self._terminate(request)
        elif action == "kill":
            return self._kill(request)
        elif action == "prune":
            return self._prune(request)
        elif action == "mount":
            return self._mount(request)
        else:
            return Response.error_response(f"unknown action: {action}")

    def _spawn(self, request: Request) -> Response:
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
            loop_id, pane_id = backend.spawn(
                label,
                request.name,
                request.args,
                request.child_allowed_tools,
                str(SOCKET_PATH),
                request.venv,
                request.cwd,
                request.prompt,
                sandbox=request.sandbox,
                session_id=request.session_id,
            )
        except Exception as e:
            return Response.error_response(str(e), ERROR_BACKEND_ERROR)

        # Get sandbox PID if available (for dynamic mounts via nsenter)
        sandbox_pid = 0
        if request.sandbox:
            try:
                proc = backend._state[pane_id]["proc"]
                sandbox_pid = proc.pid
            except (KeyError, AttributeError):
                pass

        state = LoopState(
            loop_id=loop_id,
            backend=request.backend,
            parent_id=request.parent_id,
            label=label,
            pane_id=pane_id,
            sandbox_pid=sandbox_pid,
        )
        with self._lock:
            self.loops[loop_id] = state
            self.save_state()

        return Response(
            ok=True,
            loop_id=loop_id,
            parent_id=request.parent_id,
            label=label,
            session_id=request.session_id,
        )

    def _run(self, request: Request) -> Response:
        """Run input through a loop. Returns immediately if takes longer than sync_timeout."""
        loop = self._get_loop(request.loop_id)
        if not loop:
            return Response.error_response(
                f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
            )

        with loop.lock:
            if loop.eval_running:
                return Response.error_response(
                    f"run already in progress on {request.loop_id}",
                    ERROR_INVALID_REQUEST,
                )
            loop.cancelled = False
            loop.eval_running = True
            loop.eval_started_at = time.time()
            started_at = loop.eval_started_at
            loop.run_seq += 1
            current_seq = loop.run_seq

        backend = self._get_backend(loop.backend)
        result_holder: dict[str, Any] = {}
        done_event = threading.Event()

        def _eval_worker():
            def is_cancelled():
                with loop.lock:
                    return loop.cancelled

            try:
                result_holder["result"] = backend.eval(
                    loop.pane_id, request.input, is_cancelled
                )
            except Exception as e:
                result_holder["error"] = e
            finally:
                with loop.lock:
                    if loop.run_seq == current_seq:
                        loop.eval_running = False
                        loop.eval_started_at = 0.0
                        loop.eval_thread = None
                done_event.set()

        thread = threading.Thread(target=_eval_worker, daemon=True)
        with loop.lock:
            loop.eval_thread = thread
        thread.start()

        sync_timeout = request.sync_timeout
        if sync_timeout < 0:
            done_event.wait()
        else:
            done_event.wait(timeout=sync_timeout if sync_timeout > 0 else 0.001)

        if done_event.is_set():
            with loop.lock:
                cancelled = loop.cancelled
            if cancelled:
                return Response.error_response("cancelled by user", ERROR_CANCELLED)

            if "error" in result_holder:
                return Response.error_response(
                    str(result_holder["error"]), ERROR_BACKEND_ERROR
                )

            result = result_holder["result"]

            # Update session_id if changed
            backend_session_id = result.get("session_id", "")
            if backend_session_id and backend_session_id != loop.session_id:
                with self._lock:
                    with loop.lock:
                        if loop.run_seq == current_seq:
                            loop.session_id = backend_session_id
                    self.save_state()

            elapsed = time.time() - started_at
            return Response(
                ok=True,
                output=result["output"],
                cell_index=result.get("cell_index", 0),
                session_id=loop.session_id,
                elapsed_seconds=elapsed,
            )
        else:
            # Still running - return immediately, worker continues in background
            elapsed = time.time() - started_at
            return Response(
                ok=True,
                running=True,
                elapsed_seconds=elapsed,
            )

    def _read(self, request: Request) -> Response:
        """Read cells from a loop."""
        loop = self._get_loop(request.loop_id)
        if not loop:
            return Response.error_response(
                f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
            )

        try:
            backend = self._get_backend(loop.backend)
            cells = backend.read(loop.pane_id)
            return Response(ok=True, cells=cells)
        except Exception as e:
            return Response.error_response(str(e), ERROR_BACKEND_ERROR)

    def _read_raw(self, request: Request) -> Response:
        """Read raw terminal output from a loop."""
        loop = self._get_loop(request.loop_id)
        if not loop:
            return Response.error_response(
                f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
            )

        try:
            backend = self._get_backend(loop.backend)
            raw = backend.read_raw(loop.pane_id)
            return Response(ok=True, raw_output=raw)
        except Exception as e:
            return Response.error_response(str(e), ERROR_BACKEND_ERROR)

    def _list(self, request: Request) -> Response:
        """List loops, optionally filtered by parent_id or descendants_of."""
        visible = []

        if request.descendants_of:
            loops_to_show = self._get_descendants(request.descendants_of)
        elif request.parent_id:
            with self._lock:
                loops_to_show = [
                    loop
                    for loop in self.loops.values()
                    if loop.parent_id == request.parent_id
                ]
        else:
            with self._lock:
                loops_to_show = list(self.loops.values())

        session_cache: dict[str, bool] = {}
        for loop in loops_to_show:
            info: dict[str, Any] = {
                "loop_id": loop.loop_id,
                "backend": loop.backend,
                "parent_id": loop.parent_id,
                "label": loop.label,
                "orphaned": self._is_orphaned(loop, session_cache),
            }
            if loop.session_id:
                info["session_id"] = loop.session_id
            visible.append(info)
        return Response(
            ok=True, loops=visible, current_session_id=request.current_session_id
        )

    def _status(self, request: Request) -> Response:
        """Get status of a loop."""
        loop = self._get_loop(request.loop_id)
        if not loop:
            return Response.error_response(
                f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
            )

        with loop.lock:
            running = loop.eval_running
            eval_started = loop.eval_started_at

        elapsed = time.time() - eval_started if running else 0.0
        started_at = (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(eval_started))
            if running
            else ""
        )

        return Response(
            ok=True,
            running=running,
            started_at=started_at,
            elapsed_seconds=elapsed,
        )

    def _terminate(self, request: Request) -> Response:
        """Terminate (Ctrl-C) a loop's running eval."""
        loop = self._get_loop(request.loop_id)
        if not loop:
            return Response.error_response(
                f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
            )

        with loop.lock:
            loop.cancelled = True
        try:
            backend = self._get_backend(loop.backend)
            backend.terminate(loop.pane_id)
        except Exception as e:
            return Response.error_response(str(e), ERROR_BACKEND_ERROR)

        return Response(ok=True)

    def _kill(self, request: Request) -> Response:
        """Force-kill a loop."""
        with self._lock:
            loop = self.loops.get(request.loop_id)
            if not loop:
                return Response.error_response(
                    f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
                )

            with loop.lock:
                loop.run_seq += 1  # invalidate any in-flight worker

            try:
                backend = self._get_backend(loop.backend)
                backend.kill(loop.pane_id)
            except Exception as e:
                return Response.error_response(str(e), ERROR_BACKEND_ERROR)

            session_id = loop.session_id
            del self.loops[request.loop_id]
            self.save_state()

        return Response(ok=True, session_id=session_id)

    def _prune(self, request: Request) -> Response:
        """Kill a loop, but only if it's orphaned."""
        loop = self._get_loop(request.loop_id)
        if not loop:
            return Response.error_response(
                f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
            )
        if not self._is_orphaned(loop):
            return Response.error_response(
                f"loop {request.loop_id} is not orphaned", ERROR_INVALID_REQUEST
            )
        return self._kill(request)

    def _mount(self, request: Request) -> Response:
        """Bind-mount a path inside a sandboxed loop's namespace."""
        loop = self._get_loop(request.loop_id)
        if not loop:
            return Response.error_response(
                f"loop not found: {request.loop_id}", ERROR_NOT_FOUND
            )
        if not loop.sandbox_pid:
            return Response.error_response(
                "loop has no sandbox (not spawned with sandbox)", ERROR_INVALID_REQUEST
            )

        from mcp_handley_lab.loop.sandbox import sandbox_mount

        try:
            sandbox_mount(loop.sandbox_pid, request.source, request.target)
        except Exception as e:
            return Response.error_response(str(e), ERROR_BACKEND_ERROR)

        return Response(ok=True)

    def _get_backend(self, name: str) -> Any:
        """Get or create backend instance."""
        with self._lock:
            if name not in self.backends:
                from mcp_handley_lab.loop.backends import get_backend

                self.backends[name] = get_backend(name)
            return self.backends[name]


class _UnixStreamServer(socketserver.TCPServer):
    address_family = socket.AF_UNIX


class LoopServer(socketserver.ThreadingMixIn, _UnixStreamServer):
    daemon_threads = True

    def __init__(self, path: str, handler, loop_daemon: LoopDaemon):
        self.loop_daemon = loop_daemon
        super().__init__(path, handler)


class LoopHandler(socketserver.StreamRequestHandler):
    """Handle a single client connection (one thread per connection)."""

    server: LoopServer

    def handle(self):
        for line in self.rfile:
            if not line.strip():
                break
            try:
                data = json.loads(line.decode())
                request = Request.from_dict(data)
                response = self.server.loop_daemon.handle_request(request)
            except json.JSONDecodeError as e:
                response = Response.error_response(f"invalid JSON: {e}")
            except Exception as e:
                response = Response.error_response(f"internal error: {e}")

            self.wfile.write(json.dumps(response.to_dict()).encode() + b"\n")
            self.wfile.flush()


def _idle_monitor(loop_daemon: LoopDaemon, server: LoopServer):
    """Shutdown daemon after idle timeout with no loops."""
    while loop_daemon.running:
        time.sleep(60)
        idle_time = time.time() - loop_daemon.last_activity
        if idle_time > IDLE_TIMEOUT and not loop_daemon.loops:
            logging.info("Idle timeout reached with no loops, shutting down")
            loop_daemon.running = False
            server.shutdown()


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


def run_daemon():
    """Run the loop daemon."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_PATH),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.info("Loop daemon starting")

    # Write sandbox launcher script (used by sandbox_cmd when spawning sandboxed loops)
    from mcp_handley_lab.loop.sandbox import write_launcher_script

    write_launcher_script()

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    if _socket_connectable(SOCKET_PATH):
        logging.error("Daemon already running (socket connectable)")
        raise RuntimeError("daemon already running")

    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()

    pid_tmp = PID_PATH.with_suffix(".tmp")
    pid_tmp.write_text(str(os.getpid()))
    pid_tmp.rename(PID_PATH)

    loop_daemon = LoopDaemon()
    loop_daemon.load_state()

    server = LoopServer(str(SOCKET_PATH), LoopHandler, loop_daemon)
    SOCKET_PATH.chmod(0o600)

    def _shutdown(*_args):
        loop_daemon.running = False
        server.shutdown()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    threading.Thread(
        target=_idle_monitor, args=(loop_daemon, server), daemon=True
    ).start()

    logging.info(f"Loop daemon listening on {SOCKET_PATH}")

    try:
        server.serve_forever(poll_interval=1.0)
    finally:
        server.server_close()
        with loop_daemon._lock:
            loop_daemon.save_state()
        SOCKET_PATH.unlink(missing_ok=True)
        PID_PATH.unlink(missing_ok=True)
        logging.info("Loop daemon stopped")


def main():
    """Entry point for daemon."""
    run_daemon()


if __name__ == "__main__":
    main()
