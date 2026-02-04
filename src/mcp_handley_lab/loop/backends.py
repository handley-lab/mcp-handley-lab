"""Loop backends - TmuxBackend for terminal-based REPLs, ClaudeBackend for Claude Code."""

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, NamedTuple

TMUX_SESSION = "mcp-loop"
ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07")


class BackendConfig(NamedTuple):
    """Configuration for a REPL backend."""

    name: str
    command: list[str]
    description: str
    prompt_regex: str
    continuation_regex: str = ""
    supports_bracketed_paste: bool = True
    force_bracketed_paste: bool = False  # Wrap text directly with escape codes
    soft_newline: bool = False  # Use Escape+Enter for newlines (Julia-style)
    echo_commands: bool = True
    default_args: str = ""


# Bracketed paste escape sequences
BRACKETED_PASTE_START = "\x1b[200~"
BRACKETED_PASTE_END = "\x1b[201~"


BACKENDS = {
    "bash": BackendConfig(
        "bash", ["bash", "--norc", "--noprofile"], "Bash shell", r"^.*\$ ?$"
    ),
    "zsh": BackendConfig("zsh", ["zsh", "--no-rcs"], "Zsh shell", r"^.*[%$#] ?$"),
    "python": BackendConfig(
        "python",
        ["python3", "-u"],
        "Python interpreter",
        r"^>>> ?$",
        r"^\.\.\.",
    ),
    "ipython": BackendConfig(
        "ipython",
        ["ipython"],
        "IPython",
        r"^In \[\d+\]: ?$",
        r"^   \.\.\.:",
    ),
    "julia": BackendConfig(
        "julia", ["julia"], "Julia", r"^julia> ?$", soft_newline=True
    ),
    "R": BackendConfig("R", ["R"], "R", r"^> ?$", r"^\+ ?$"),
    "clojure": BackendConfig(
        "clojure",
        [
            "clojure",
            "-Sdeps",
            '{:deps {com.bhauman/rebel-readline {:mvn/version "0.1.5"}}}',
            "-M",
            "-m",
            "rebel-readline.main",
        ],
        "Clojure (rebel-readline)",
        r"^[a-zA-Z0-9._-]+=> ?$",
    ),
    "apl": BackendConfig(
        "apl",
        ["apl"],
        "GNU APL",
        r"      $",
        supports_bracketed_paste=False,
    ),
    "maple": BackendConfig(
        "maple",
        ["maple", "-c", "interface(errorcursor=false);"],
        "Maple",
        r"^> ?$",
    ),
    "ollama": BackendConfig(
        "ollama",
        ["ollama", "run", "llama3"],
        "Ollama LLM",
        r"^>>> ",
        supports_bracketed_paste=False,
        echo_commands=False,
    ),
    "mathematica": BackendConfig(
        "mathematica",
        ["math"],
        "Mathematica",
        r"^In\[\d+\]:= ?$",
        supports_bracketed_paste=False,
        default_args="-run $PrePrint=InputForm",
    ),
}


def get_backend(name: str) -> Any:
    """Get a backend instance by name."""
    if name == "claude":
        return ClaudeBackend()
    if name in BACKENDS:
        return TmuxBackend(BACKENDS[name])
    raise NotImplementedError(f"backend '{name}' not implemented")


def _run(args: list[str], **kw) -> subprocess.CompletedProcess:
    """Run a tmux command. Raises on failure by default."""
    kw.setdefault("check", True)
    return subprocess.run(["tmux", *args], capture_output=True, text=True, **kw)


def _capture(pane_id: str, lines: int = 500) -> str:
    """Capture terminal output from pane, stripping ANSI codes."""
    result = _run(["capture-pane", "-e", "-t", pane_id, "-p", "-S", f"-{lines}"])
    return ANSI.sub("", result.stdout)


def _ends_prompt(text: str, prompt: re.Pattern) -> bool:
    """Check if text ends with a prompt."""
    for line in reversed(text.split("\n")):
        if prompt.match(line):
            return True
        if line.strip():
            return False
    return False


def _wait_for_completion(
    capture: Callable[[], str],
    baseline: str,
    prompt: re.Pattern,
    check_cancelled: Callable[[], bool],
) -> tuple[str, bool]:
    """Wait for REPL to return to prompt. Returns (output, was_cancelled)."""
    now = time.time
    start = now()
    prev = baseline
    stable = None

    while True:
        if check_cancelled():
            return prev, True

        elapsed = now() - start
        time.sleep(0.2 if elapsed < 1 else 1)

        cur = capture()
        if cur != prev:
            prev = cur
            stable = now() if _ends_prompt(cur, prompt) else None
        elif stable and now() - stable > 0.15:
            return cur, False


def _extract_output(
    baseline: str,
    captured: str,
    prompt: re.Pattern,
    sent_code: str,
    echo_commands: bool,
    continuation: re.Pattern | None = None,
) -> str:
    """Extract output from captured terminal, removing prompt and echoed code."""
    b, c = baseline.split("\n"), captured.split("\n")
    start = next(
        (i for i, (x, y) in enumerate(zip(b, c, strict=False)) if x != y), len(b)
    )
    lines = c[start:]

    while lines and (not lines[-1].strip() or prompt.match(lines[-1])):
        lines.pop()

    if continuation:
        lines = [ln for ln in lines if not continuation.match(ln)]

    code = sent_code.strip()
    if echo_commands and code:
        code_split = code.split("\n")
        code_lines = {ln.strip() for ln in code_split if ln.strip()}
        if lines and code_split[0].strip() in lines[0]:
            lines.pop(0)
        lines = [ln for ln in lines if ln.strip() not in code_lines]

    return "\n".join(lines)


def _parse_cells(pane_id: str, config: BackendConfig) -> list[dict[str, Any]]:
    """Parse terminal output into cells based on backend prompts."""
    output = _capture(pane_id, 2000)

    prompt_start = config.prompt_regex.rstrip("$")
    prompt = re.compile(prompt_start, re.M)
    continuation = (
        re.compile(config.continuation_regex) if config.continuation_regex else None
    )

    lines = output.split("\n")
    cells: list[dict[str, Any]] = []
    current_input: list[str] = []
    current_output: list[str] = []

    for line in lines:
        match = prompt.match(line)
        if match:
            if current_input or current_output:
                cells.append(
                    {
                        "index": len(cells),
                        "input": "\n".join(current_input),
                        "output": "\n".join(current_output).strip(),
                    }
                )
                current_input = []
                current_output = []
            input_text = line[match.end() :].strip()
            if input_text:
                current_input.append(input_text)
        elif continuation and continuation.match(line):
            cont_match = continuation.match(line)
            current_input.append(line[cont_match.end() :])
        elif current_input:
            current_output.append(line)

    if current_input and current_output:
        cells.append(
            {
                "index": len(cells),
                "input": "\n".join(current_input),
                "output": "\n".join(current_output).strip(),
            }
        )

    return cells


def _session_exists() -> bool:
    """Check if the tmux session exists."""
    result = subprocess.run(
        ["tmux", "has-session", "-t", TMUX_SESSION],
        capture_output=True,
    )
    return result.returncode == 0


class TmuxBackend:
    """Backend using tmux for terminal-based REPLs."""

    def __init__(self, config: BackendConfig):
        self.config = config

    def spawn(
        self,
        label: str,
        name: str | None,
        args: str | None,
        child_allowed_tools: list[str],
        socket_path: str = "",
    ) -> tuple[str, str]:
        """Spawn a new REPL. Returns (loop_id, pane_id).

        Args:
            label: Human-readable label for tmux window
            name: Optional name suffix for loop_id
            args: Extra arguments for the backend
            child_allowed_tools: Tools the loop can use (for Claude backend)
            socket_path: Daemon socket path to inject as MCP_LOOP_SOCKET
        """
        # Create session if it doesn't exist
        default_window = None
        if not _session_exists():
            _run(["new-session", "-d", "-s", TMUX_SESSION])
            default_window = _run(
                ["list-windows", "-t", TMUX_SESSION, "-F", "#{window_id}"]
            ).stdout.strip()

        extra_args = args or self.config.default_args
        base_command = self.config.command + (extra_args.split() if extra_args else [])

        # Generate loop_id
        timestamp = datetime.now().strftime("%H%M%S")
        loop_id = f"{self.config.name}-{name or timestamp}"

        # Strip venv from environment so tmux windows start clean
        clean_path = os.pathsep.join(
            p
            for p in os.environ.get("PATH", "").split(os.pathsep)
            if not p.startswith(sys.prefix)
        )
        env_cmd = [
            "env",
            "-u",
            "VIRTUAL_ENV",
            "-u",
            "PYTHONPATH",
            f"PATH={clean_path}",
        ]
        # Inject loop env vars for client library
        if socket_path:
            env_cmd.append(f"MCP_LOOP_SOCKET={socket_path}")
            env_cmd.append(f"MCP_LOOP_PARENT_ID={loop_id}")

        command = env_cmd + base_command
        window_name = f"{label}-{loop_id}"

        result = _run(
            [
                "new-window",
                "-t",
                TMUX_SESSION,
                "-n",
                window_name,
                "-P",
                "-F",
                "#{pane_id}",
                *command,
            ]
        )
        pane_id = result.stdout.strip()
        if not pane_id:
            raise RuntimeError("tmux new-window returned empty pane_id")

        if default_window:
            _run(["kill-window", "-t", default_window])

        return loop_id, pane_id

    def eval(
        self, pane_id: str, code: str, check_cancelled: Callable[[], bool]
    ) -> dict[str, Any]:
        """Evaluate code in REPL. Blocks until completion or cancellation."""
        prompt = re.compile(self.config.prompt_regex, re.M)

        def cap():
            return _capture(pane_id, 1000)

        base = cap()

        # Send code
        code_text = code.rstrip("\n") + ("\n" if "\n" in code else "")
        if self.config.soft_newline and "\n" in code:
            # Use Escape+Enter for newlines (Julia-style multi-line input)
            lines = code.rstrip("\n").split("\n")
            for i, line in enumerate(lines):
                _run(["send-keys", "-t", pane_id, "-l", line])
                if i < len(lines) - 1:
                    _run(["send-keys", "-t", pane_id, "Escape", "Enter"])
                else:
                    _run(["send-keys", "-t", pane_id, "Enter"])
        elif self.config.force_bracketed_paste:
            # Wrap text directly with escape sequences (for REPLs that don't
            # request bracketed paste mode from tmux, e.g. Julia)
            wrapped = f"{BRACKETED_PASTE_START}{code_text}{BRACKETED_PASTE_END}"
            _run(["send-keys", "-t", pane_id, "-l", wrapped])
            _run(["send-keys", "-t", pane_id, "Enter"])
        elif self.config.supports_bracketed_paste:
            _run(["load-buffer", "-"], input=code_text)
            _run(["paste-buffer", "-p", "-d", "-t", pane_id])
            _run(["send-keys", "-t", pane_id, "Enter"])
        else:
            _run(["send-keys", "-t", pane_id, "-l", code_text])
            _run(["send-keys", "-t", pane_id, "Enter"])

        out, cancelled = _wait_for_completion(cap, base, prompt, check_cancelled)
        if cancelled:
            _run(["send-keys", "-t", pane_id, "C-c"])
            out = cap()

        continuation = (
            re.compile(self.config.continuation_regex, re.M)
            if self.config.continuation_regex
            else None
        )
        output = _extract_output(
            base, out, prompt, code, self.config.echo_commands, continuation
        )

        cells = _parse_cells(pane_id, self.config)
        cell_index = len(cells) - 1 if cells else 0

        return {"output": output, "cell_index": cell_index}

    def read(self, pane_id: str) -> list[dict[str, Any]]:
        """Read cells from REPL."""
        return _parse_cells(pane_id, self.config)

    def read_raw(self, pane_id: str) -> str:
        """Read raw terminal capture."""
        return _capture(pane_id, 2000)

    def terminate(self, pane_id: str) -> None:
        """Send Ctrl-C to interrupt running eval."""
        _run(["send-keys", "-t", pane_id, "C-c"])

    def kill(self, pane_id: str) -> None:
        """Force-kill the pane."""
        _run(["send-keys", "-t", pane_id, "C-c"])
        _run(["kill-pane", "-t", pane_id])


# Claude subprocess state - keyed by loop_id
_claude_processes: dict[str, dict[str, Any]] = {}
_claude_lock = threading.Lock()


class ClaudeBackend:
    """Backend for Claude Code in stream-json mode."""

    def spawn(
        self,
        label: str,
        name: str | None,
        args: str | None,
        child_allowed_tools: list[str],
        socket_path: str = "",
    ) -> tuple[str, str]:
        """Spawn a new Claude session. Returns (loop_id, loop_id).

        Note: socket_path is accepted for API consistency but not used
        (Claude Code has its own MCP integration).
        """
        timestamp = datetime.now().strftime("%H%M%S")
        loop_id = f"claude-{name or timestamp}"

        cmd = [
            "claude",
            "-p",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
        ]

        # Add allowed tools if specified
        if child_allowed_tools:
            cmd.extend(["--allowedTools", ",".join(child_allowed_tools)])

        # Add any extra args
        if args:
            cmd.extend(args.split())

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # Avoid deadlock from unbuffered stderr
            text=True,
            bufsize=1,  # Line buffered
        )

        # Don't wait for init - Claude only sends it after first user message
        with _claude_lock:
            _claude_processes[loop_id] = {
                "proc": proc,
                "cells": [],
                "session_id": "",
            }

        return loop_id, loop_id  # loop_id serves as both identifiers

    def eval(
        self, pane_id: str, code: str, check_cancelled: Callable[[], bool]
    ) -> dict[str, Any]:
        """Send message to Claude and wait for response."""
        with _claude_lock:
            state = _claude_processes.get(pane_id)
            if not state:
                raise RuntimeError(f"Claude session not found: {pane_id}")
            proc = state["proc"]
            cells = state["cells"]

        if proc.poll() is not None:
            raise RuntimeError(f"Claude process has exited (code {proc.returncode})")

        # Send user message
        msg = {"type": "user", "message": {"role": "user", "content": code}}
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

        # Collect response (no lock needed - proc is per-session)
        output_parts: list[str] = []
        result = None

        while True:
            if check_cancelled():
                self.terminate(pane_id)
                with _claude_lock:
                    return {
                        "output": "".join(output_parts) + "\n[cancelled]",
                        "cell_index": len(cells),
                    }

            line = proc.stdout.readline()
            if not line:
                break

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "system":
                # Init message - capture session_id
                if data.get("subtype") == "init":
                    with _claude_lock:
                        state["session_id"] = data.get("session_id", "")
                continue

            if msg_type == "assistant":
                # Extract text content
                message = data.get("message", {})
                for content in message.get("content", []):
                    if content.get("type") == "text":
                        output_parts.append(content.get("text", ""))

            elif msg_type == "result":
                result = data
                break

        output = (
            result.get("result", "".join(output_parts))
            if result
            else "".join(output_parts)
        )

        # Store as cell
        with _claude_lock:
            cell_index = len(cells)
            cells.append({"index": cell_index, "input": code, "output": output})

        return {"output": output, "cell_index": cell_index}

    def read(self, pane_id: str) -> list[dict[str, Any]]:
        """Read conversation cells."""
        with _claude_lock:
            state = _claude_processes.get(pane_id)
            return list(state["cells"]) if state else []

    def read_raw(self, pane_id: str) -> str:
        """Read raw output (returns JSON of cells for Claude backend)."""
        with _claude_lock:
            state = _claude_processes.get(pane_id)
            return json.dumps(state["cells"], indent=2) if state else "[]"

    def terminate(self, pane_id: str) -> None:
        """Send SIGINT to interrupt running eval."""
        with _claude_lock:
            state = _claude_processes.get(pane_id)
            proc = state["proc"] if state else None
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGINT)

    def kill(self, pane_id: str) -> None:
        """Force-kill the Claude process."""
        with _claude_lock:
            state = _claude_processes.pop(pane_id, None)
        if state:
            proc = state["proc"]
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            # Close pipes to release FDs
            for pipe in (proc.stdin, proc.stdout):
                if pipe:
                    pipe.close()
