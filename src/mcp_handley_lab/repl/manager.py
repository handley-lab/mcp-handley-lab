"""Tmux session manager for REPL sessions.

Manages REPL processes via tmux panes. Sessions survive MCP server restarts
because tmux owns the processes, not the MCP server.
"""

import fcntl
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mcp_handley_lab.repl.backends import BackendConfig, get_backend
from mcp_handley_lab.repl.completion import (
    PromptDetector,
    extract_output,
)

TMUX_SESSION = "mcp-repls"
DEFAULT_CAPTURE_LINES = 500


@dataclass
class SessionInfo:
    """Information about a REPL session."""

    session_id: str
    backend: str
    name: str
    created_at: str
    pane_id: str


def _get_storage_dir() -> Path:
    """Get the storage directory for REPL session metadata."""
    base = Path(os.environ.get("MCP_HANDLEY_LAB_MEMORY_DIR", "~/.mcp-handley-lab"))
    return base.expanduser() / "repl"


def _run_tmux(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a tmux command."""
    cmd = ["tmux"] + args
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _ensure_tmux_session() -> None:
    """Ensure the mcp-repls tmux session exists."""
    result = _run_tmux(["has-session", "-t", TMUX_SESSION], check=False)
    if result.returncode != 0:
        # Create detached session with a dummy window we'll close later
        _run_tmux(["new-session", "-d", "-s", TMUX_SESSION, "-n", "__init__"])


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07")
    return ansi_pattern.sub("", text)


class TmuxSessionManager:
    """Manages REPL sessions via tmux panes."""

    def __init__(self):
        self._storage_dir = _get_storage_dir()
        self._sessions_file = self._storage_dir / "sessions.json"
        self._history_dir = self._storage_dir / "history"
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Ensure storage directories exist."""
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._history_dir.mkdir(parents=True, exist_ok=True)

    def _load_sessions(self) -> dict[str, dict]:
        """Load session metadata from disk."""
        if not self._sessions_file.exists():
            return {}
        try:
            with open(self._sessions_file, encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_sessions(self, sessions: dict[str, dict]) -> None:
        """Save session metadata to disk atomically."""
        tmp_file = self._sessions_file.with_suffix(".json.tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(sessions, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.replace(tmp_file, self._sessions_file)

    def _add_session(self, session_id: str, backend: str, name: str) -> None:
        """Add a session to metadata."""
        sessions = self._load_sessions()
        sessions[session_id] = {
            "backend": backend,
            "name": name,
            "created_at": datetime.now().isoformat(),
        }
        self._save_sessions(sessions)

    def _remove_session(self, session_id: str) -> None:
        """Remove a session from metadata."""
        sessions = self._load_sessions()
        sessions.pop(session_id, None)
        self._save_sessions(sessions)

    def _log_command(
        self, session_id: str, code: str, output: str, exit_code: int | None
    ) -> None:
        """Log a command execution to history."""
        history_file = self._history_dir / f"{session_id}.jsonl"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "code": code,
            "output": output,
            "exit_code": exit_code,
        }
        with open(history_file, "a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(json.dumps(entry) + "\n")
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def create(self, backend: str, name: str | None = None) -> str:
        """Create a new REPL session in tmux.

        Args:
            backend: The backend type (bash, ipython, python).
            name: Optional human-readable name for the session.

        Returns:
            The session_id (tmux pane ID).
        """
        _ensure_tmux_session()
        config = get_backend(backend)

        # Generate a unique window name
        timestamp = datetime.now().strftime("%H%M%S")
        window_name = name or f"{backend}-{timestamp}"

        # Create new window with the REPL command
        command = " ".join(config.command)
        result = _run_tmux(
            [
                "new-window",
                "-t",
                TMUX_SESSION,
                "-n",
                window_name,
                "-P",
                "-F",
                "#{pane_id}",
                command,
            ]
        )

        pane_id = result.stdout.strip()

        # Store metadata
        self._add_session(pane_id, backend, window_name)

        # Give the REPL a moment to start and display its prompt
        time.sleep(0.5)

        return pane_id

    def send_code(
        self, session_id: str, code: str, bracketed_paste: bool = True
    ) -> None:
        """Send code to a session.

        Uses bracketed paste mode for safe multi-line transmission via
        tmux load-buffer and paste-buffer -p.

        Args:
            session_id: The tmux pane ID.
            code: The code to send.
            bracketed_paste: Use bracketed paste mode (default True).
        """
        code = code.rstrip("\n")

        if bracketed_paste:
            # Bracketed paste: we'll send Enter separately, so don't add newline
            # For multi-line code, add one newline to end the block (Python needs this)
            if "\n" in code:
                code = code + "\n"
            # Use tmux buffer for bracketed paste
            # 1. Load code into tmux buffer from stdin
            subprocess.run(
                ["tmux", "load-buffer", "-"],
                input=code,
                capture_output=True,
                text=True,
                check=True,
            )

            # 2. Paste with bracketed paste mode (-p) and delete buffer (-d)
            _run_tmux(["paste-buffer", "-p", "-d", "-t", session_id])

            # 3. Send Enter to trigger execution (bracketed paste doesn't auto-execute)
            _run_tmux(["send-keys", "-t", session_id, "Enter"])
        else:
            # Fallback: send-keys (for REPLs that don't support bracketed paste)
            # Add newline for multi-line code to end blocks
            if "\n" in code:
                code = code + "\n"
            _run_tmux(["send-keys", "-t", session_id, "-l", code])
            _run_tmux(["send-keys", "-t", session_id, "Enter"])

    def capture_output(
        self, session_id: str, lines: int = DEFAULT_CAPTURE_LINES
    ) -> str:
        """Capture current pane output.

        Args:
            session_id: The tmux pane ID.
            lines: Number of lines to capture from scrollback.

        Returns:
            The captured output with ANSI codes stripped.
        """
        result = _run_tmux(
            [
                "capture-pane",
                "-t",
                session_id,
                "-p",  # Print to stdout
                "-S",
                f"-{lines}",  # Start from N lines back
            ],
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to capture pane output: {result.stderr}")

        return _strip_ansi(result.stdout)

    def send_interrupt(self, session_id: str) -> None:
        """Send Ctrl-C to interrupt the current command.

        Args:
            session_id: The tmux pane ID.
        """
        _run_tmux(["send-keys", "-t", session_id, "C-c"])

    def list_sessions(self) -> list[SessionInfo]:
        """List all active REPL sessions.

        Reconciles metadata with actual tmux panes - removes orphaned entries.

        Returns:
            List of SessionInfo for active sessions.
        """
        # Get actual tmux panes
        result = _run_tmux(
            ["list-panes", "-t", TMUX_SESSION, "-F", "#{pane_id}:#{window_name}"],
            check=False,
        )

        if result.returncode != 0:
            # Session doesn't exist - no panes
            actual_panes = {}
        else:
            actual_panes = {}
            for line in result.stdout.strip().split("\n"):
                if ":" in line:
                    pane_id, window_name = line.split(":", 1)
                    actual_panes[pane_id] = window_name

        # Load metadata
        sessions = self._load_sessions()

        # Reconcile: only include sessions that still exist in tmux
        active_sessions = []
        orphaned = []

        for session_id, meta in sessions.items():
            if session_id in actual_panes:
                active_sessions.append(
                    SessionInfo(
                        session_id=session_id,
                        backend=meta.get("backend", "unknown"),
                        name=meta.get("name", actual_panes[session_id]),
                        created_at=meta.get("created_at", ""),
                        pane_id=session_id,
                    )
                )
            else:
                orphaned.append(session_id)

        # Clean up orphaned metadata
        if orphaned:
            for sid in orphaned:
                sessions.pop(sid, None)
            self._save_sessions(sessions)

        return active_sessions

    def destroy(self, session_id: str) -> None:
        """Kill a tmux pane and clean up metadata.

        Args:
            session_id: The tmux pane ID.
        """
        _run_tmux(["kill-pane", "-t", session_id], check=False)
        self._remove_session(session_id)

    def exists(self, session_id: str) -> bool:
        """Check if a session still exists.

        Args:
            session_id: The tmux pane ID.

        Returns:
            True if the pane exists.
        """
        result = _run_tmux(
            ["list-panes", "-t", session_id, "-F", "#{pane_id}"],
            check=False,
        )
        return result.returncode == 0 and session_id in result.stdout

    def get_backend_config(self, session_id: str) -> BackendConfig | None:
        """Get the backend configuration for a session.

        Args:
            session_id: The tmux pane ID.

        Returns:
            BackendConfig if found, None otherwise.
        """
        sessions = self._load_sessions()
        meta = sessions.get(session_id)
        if meta is None:
            return None
        try:
            return get_backend(meta["backend"])
        except ValueError:
            return None

    def eval(
        self,
        session_id: str,
        code: str,
        timeout: int = 30,
    ) -> tuple[str, int | None]:
        """Execute code and wait for completion via prompt detection.

        Sends code to the REPL and waits for the prompt to reappear,
        then extracts the output between prompts.

        Args:
            session_id: The tmux pane ID.
            code: The code to execute.
            timeout: Maximum seconds to wait for completion.

        Returns:
            Tuple of (output, exit_code). exit_code is always None
            (prompt-based detection doesn't capture exit codes).

        Raises:
            RuntimeError: If the session doesn't exist or backend is unknown.
        """
        if not self.exists(session_id):
            raise RuntimeError(f"Session {session_id} does not exist")

        config = self.get_backend_config(session_id)
        if config is None:
            raise RuntimeError(f"Unknown backend for session {session_id}")

        # Compile prompt and continuation patterns
        prompt_pattern = re.compile(config.prompt_regex, re.MULTILINE)
        continuation_pattern = (
            re.compile(config.continuation_regex, re.MULTILINE)
            if config.continuation_regex
            else None
        )

        # 1. Capture baseline output before sending command
        baseline_output = self.capture_output(session_id, lines=1000)
        detector = PromptDetector(prompt_pattern)

        # 2. Send code (no sentinel wrapping)
        self.send_code(
            session_id, code, bracketed_paste=config.supports_bracketed_paste
        )

        # 3. Wait for completion with two-phase polling
        result = detector.wait_for_completion(
            capture_func=lambda: self.capture_output(session_id, lines=1000),
            baseline_output=baseline_output,
            timeout=timeout,
        )

        # 4. Handle timeout
        if not result.completed:
            self.send_interrupt(session_id)
            time.sleep(0.2)
            # Capture final state after interrupt
            result = type(result)(
                completed=False,
                captured_output=self.capture_output(session_id, lines=1000),
                elapsed_seconds=result.elapsed_seconds,
            )

        # 5. Extract output by comparing baseline and captured
        output = extract_output(
            baseline_output,
            result.captured_output,
            prompt_pattern,
            code,
            config.echo_commands,
            continuation_pattern,
        )

        # 6. Log and return
        timed_out = not result.completed
        self._log_command(session_id, code, output, None)
        return output, timed_out
