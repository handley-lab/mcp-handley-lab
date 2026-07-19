"""Loop backends - TmuxBackend for terminal-based REPLs, ClaudeBackend for Claude Code."""

import contextlib
import json
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
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
    if name == "gemini":
        return GeminiBackend()
    if name == "openai":
        return OpenAIBackend()
    if name.startswith("jupyter"):
        kernel_map = {
            "jupyter": "python3",
            "jupyter-python": "python3",
            "jupyter-julia": "julia",
            "jupyter-r": "ir",
        }
        return JupyterBackend(default_kernel=kernel_map.get(name, "python3"))
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
        venv: str = "",
        cwd: str = "",
        prompt: str = "",
        *,
        sandbox: dict[str, list[str]] | None = None,
        session_id: str = "",
    ) -> tuple[str, str]:
        """Spawn a new REPL. Returns (loop_id, pane_id).

        Args:
            label: Human-readable label for tmux window
            name: Optional name suffix for loop_id
            args: Extra arguments for the backend
            child_allowed_tools: Tools the loop can use (for Claude backend)
            socket_path: Daemon socket path to inject as MCP_LOOP_SOCKET
            venv: Path to venv (created with --system-site-packages if missing)
            cwd: Working directory (unused for tmux backend)
            prompt: System prompt (unused for tmux backend)
            sandbox: Ignored (tmux windows can't be namespaced)
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

        # Handle venv: create if missing, then activate
        venv_path = None
        if venv:
            venv_path = Path(venv).expanduser().resolve()
            if not (venv_path / "bin" / "activate").exists():
                # Create venv with system site-packages access
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "venv",
                        "--system-site-packages",
                        str(venv_path),
                    ],
                    check=True,
                )
            # Prepend venv bin to PATH and set VIRTUAL_ENV
            clean_path = f"{venv_path}/bin:{clean_path}"

        # All -u flags must come before NAME=VALUE assignments (POSIX env requirement)
        unset_vars = ["PYTHONPATH"]
        if not venv_path:
            unset_vars.append("VIRTUAL_ENV")

        set_vars = [f"PATH={clean_path}"]
        if venv_path:
            set_vars.append(f"VIRTUAL_ENV={venv_path}")
        if socket_path:
            set_vars.append(f"MCP_LOOP_SOCKET={socket_path}")
            set_vars.append(f"MCP_LOOP_PARENT_ID={loop_id}")

        env_cmd = ["env"]
        for var in unset_vars:
            env_cmd.extend(["-u", var])
        env_cmd.extend(set_vars)

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


def _subscription_env(own_key: str) -> dict[str, str]:
    """Build subprocess env stripping only the CLI's own API key.

    Each CLI checks its own API key at startup to decide auth method.
    Stripping only that key forces subscription/OAuth auth for the CLI,
    while preserving other keys for MCP servers and child processes.
    The stripped key is saved as _<KEY> so MCP servers can restore it.
    """
    env = dict(os.environ)
    val = env.pop(own_key, None)
    if val is not None:
        env[f"_{own_key}"] = val
    return env


class LLMBackend:
    """Base for subprocess-based LLM backends with cell tracking.

    Subclass state dicts must include: cells, current_input,
    current_output_parts, current_events, plus backend-specific keys.
    """

    def __init__(self):
        self._state: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def read(self, pane_id: str) -> list[dict[str, Any]]:
        """Read cells, projected to {index, input, output, in_progress}."""
        with self._lock:
            state = self._state.get(pane_id)
            if not state:
                return []
            cells = [
                {
                    "index": c["index"],
                    "input": c["input"],
                    "output": c["output"],
                    "in_progress": False,
                }
                for c in state["cells"]
            ]
            if state["current_input"]:
                cells.append(
                    {
                        "index": len(state["cells"]),
                        "input": state["current_input"],
                        "output": "".join(state["current_output_parts"]),
                        "in_progress": True,
                    }
                )
            return cells

    def read_raw(self, pane_id: str) -> str:
        """Read cells with raw events as JSON string."""
        with self._lock:
            state = self._state.get(pane_id)
            if not state:
                return "[]"
            cells = [
                {
                    "index": c["index"],
                    "input": c["input"],
                    "output": c["output"],
                    "events": c.get("events", []),
                    "in_progress": False,
                }
                for c in state["cells"]
            ]
            if state["current_input"]:
                cells.append(
                    {
                        "index": len(state["cells"]),
                        "input": state["current_input"],
                        "output": "".join(state["current_output_parts"]),
                        "events": list(state["current_events"]),
                        "in_progress": True,
                    }
                )
            return json.dumps(cells, indent=2)

    def terminate(self, pane_id: str) -> None:
        """Send SIGINT to interrupt running eval."""
        with self._lock:
            state = self._state.get(pane_id)
            proc = state.get("proc") if state else None
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGINT)

    def kill(self, pane_id: str) -> None:
        """Force-kill and remove session state."""
        with self._lock:
            state = self._state.pop(pane_id, None)
        if state:
            proc = state.get("proc")
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                for pipe in (proc.stdin, proc.stdout):
                    if pipe:
                        pipe.close()


class ClaudeBackend(LLMBackend):
    """Backend for Claude Code in stream-json mode."""

    def spawn(
        self,
        label: str,
        name: str | None,
        args: str | None,
        child_allowed_tools: list[str],
        socket_path: str = "",
        venv: str = "",
        cwd: str = "",
        prompt: str = "",
        *,
        sandbox: dict[str, list[str]] | None = None,
        session_id: str = "",
    ) -> tuple[str, str]:
        """Spawn a new Claude session. Returns (loop_id, loop_id).

        Args:
            label: Human-readable label
            name: Optional name suffix for loop_id
            args: Extra CLI arguments for claude
            child_allowed_tools: Tools the loop can use (--allowedTools)
            socket_path: Accepted for API consistency (unused)
            venv: Accepted for API consistency (unused)
            cwd: Working directory for the Claude process
            prompt: System prompt (passed as --append-system-prompt)
            sandbox: Mount spec for namespace isolation
            session_id: Resume a previous session (passed as --resume)
        """
        import shlex

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

        # Resume previous session if session_id provided
        if session_id:
            cmd.extend(["--resume", session_id])

        # Append to default system prompt if specified
        if prompt:
            cmd.extend(["--append-system-prompt", prompt])

        # Add allowed tools if specified
        if child_allowed_tools:
            cmd.extend(["--allowedTools", ",".join(child_allowed_tools)])

        # Add any extra args
        if args:
            cmd.extend(shlex.split(args))

        env = _subscription_env("ANTHROPIC_API_KEY")

        # Wrap command with sandbox if requested
        popen_cwd = cwd or None
        if sandbox:
            from mcp_handley_lab.loop.sandbox import sandbox_cmd

            cmd, popen_cwd = sandbox_cmd(cmd, cwd, sandbox, "claude", env=env)
            env = None  # env is baked into sandbox config

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # Avoid deadlock from unbuffered stderr
            text=True,
            bufsize=1,  # Line buffered
            env=env,
            cwd=popen_cwd,
        )

        # Don't wait for init - Claude only sends it after first user message
        with self._lock:
            self._state[loop_id] = {
                "proc": proc,
                "cells": [],
                "session_id": "",
                "current_input": "",
                "current_output_parts": [],
                "current_events": [],
            }

        return loop_id, loop_id  # loop_id serves as both identifiers

    def eval(
        self, pane_id: str, code: str, check_cancelled: Callable[[], bool]
    ) -> dict[str, Any]:
        """Send message to Claude and wait for response."""
        with self._lock:
            state = self._state.get(pane_id)
            if not state:
                raise RuntimeError(f"Claude session not found: {pane_id}")
            proc = state["proc"]
            state["current_input"] = code
            state["current_output_parts"] = []
            state["current_events"] = []

        if proc.poll() is not None:
            raise RuntimeError(f"Claude process has exited (code {proc.returncode})")

        # Tag message as loop-generated (persists in JSONL for search filtering)
        meta = json.dumps({"source": "mcp_loop", "loop_id": pane_id})
        tagged = f"{code}\n\n<!-- mcp_meta: {meta} -->"
        msg = {"type": "user", "message": {"role": "user", "content": tagged}}
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

        result = None
        try:
            while True:
                if check_cancelled():
                    self.terminate(pane_id)
                    with self._lock:
                        if pane_id not in self._state:
                            return {"output": "[killed]", "cell_index": 0}
                        output = (
                            "".join(state["current_output_parts"]) + "\n[cancelled]"
                        )
                        cell_index = len(state["cells"])
                        return {"output": output, "cell_index": cell_index}

                line = proc.stdout.readline()
                if not line:
                    break

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                with self._lock:
                    if pane_id not in self._state:
                        return {"output": "[killed]", "cell_index": 0}
                    state["current_events"].append(data)

                if msg_type == "system":
                    if data.get("subtype") == "init":
                        with self._lock:
                            state["session_id"] = data.get("session_id", "")
                    continue

                if msg_type == "assistant":
                    message = data.get("message", {})
                    for content in message.get("content", []):
                        ctype = content.get("type")
                        if ctype == "text":
                            with self._lock:
                                state["current_output_parts"].append(
                                    content.get("text", "")
                                )
                        elif ctype == "thinking":
                            text = content.get("thinking", "")
                            summary = text[:200] + "..." if len(text) > 200 else text
                            with self._lock:
                                state["current_output_parts"].append(
                                    f"\n[THINKING: {summary}]\n"
                                )
                        elif ctype == "tool_use":
                            name = content.get("name", "?")
                            inp = content.get("input", {})
                            parts = []
                            for k, v in inp.items():
                                s = str(v)
                                parts.append(
                                    f"{k}={s[:80]}{'...' if len(s) > 80 else ''}"
                                )
                            with self._lock:
                                state["current_output_parts"].append(
                                    f"\n[TOOL: {name}({', '.join(parts)})]\n"
                                )
                        elif ctype == "tool_result":
                            text = str(content.get("content", ""))
                            summary = text[:200] + "..." if len(text) > 200 else text
                            with self._lock:
                                state["current_output_parts"].append(
                                    f"\n[RESULT: {summary}]\n"
                                )

                elif msg_type == "result":
                    result = data
                    break

            with self._lock:
                if pane_id not in self._state:
                    return {"output": "[killed]", "cell_index": 0}
                output = (
                    result.get("result", "".join(state["current_output_parts"]))
                    if result
                    else "".join(state["current_output_parts"])
                )
                cell_index = len(state["cells"])
                state["cells"].append(
                    {
                        "index": cell_index,
                        "input": code,
                        "output": output,
                        "events": list(state["current_events"]),
                    }
                )
                return {
                    "output": output,
                    "cell_index": cell_index,
                    "session_id": state.get("session_id", ""),
                }
        finally:
            with self._lock:
                if pane_id in self._state:
                    state["current_input"] = ""
                    state["current_output_parts"] = []
                    state["current_events"] = []


class GeminiBackend(LLMBackend):
    """Backend for Gemini CLI in stream-json mode (uses Google OAuth subscription)."""

    def spawn(
        self,
        label: str,
        name: str | None,
        args: str | None,
        child_allowed_tools: list[str],
        socket_path: str = "",
        venv: str = "",
        cwd: str = "",
        prompt: str = "",
        *,
        sandbox: dict[str, list[str]] | None = None,
        session_id: str = "",
    ) -> tuple[str, str]:
        """Spawn a new Gemini session. Returns (loop_id, loop_id)."""
        timestamp = datetime.now().strftime("%H%M%S")
        loop_id = f"gemini-{name or timestamp}"

        # Parse model from args if provided
        model = ""
        if args:
            import shlex

            arg_list = shlex.split(args)
            for i, arg in enumerate(arg_list):
                if arg == "--model" and i + 1 < len(arg_list):
                    model = arg_list[i + 1]
                elif arg.startswith("--model="):
                    model = arg.split("=", 1)[1]

        with self._lock:
            self._state[loop_id] = {
                "session_id": "",
                "model": model,
                "cells": [],
                "proc": None,
                "sandbox": sandbox or {},
                "cwd": cwd,
                "current_input": "",
                "current_output_parts": [],
                "current_events": [],
            }

        return loop_id, loop_id

    def eval(
        self, pane_id: str, code: str, check_cancelled: Callable[[], bool]
    ) -> dict[str, Any]:
        """Send message to Gemini CLI and wait for response."""
        with self._lock:
            state = self._state.get(pane_id)
            if not state:
                raise RuntimeError(f"Gemini session not found: {pane_id}")
            session_id = state["session_id"]
            model = state["model"]
            loop_sandbox = state.get("sandbox", {})
            loop_cwd = state.get("cwd", "")
            state["current_input"] = code
            state["current_output_parts"] = []
            state["current_events"] = []

        # Build command
        cmd = ["gemini", "--output-format", "stream-json"]
        if session_id:
            cmd.extend(["--resume", session_id])
        if model:
            cmd.extend(["--model", model])

        env = _subscription_env("GEMINI_API_KEY")

        # Wrap command with sandbox if requested
        popen_cwd = None
        if loop_sandbox:
            from mcp_handley_lab.loop.sandbox import sandbox_cmd

            cmd, popen_cwd = sandbox_cmd(cmd, loop_cwd, loop_sandbox, "gemini", env=env)
            env = None  # env is baked into sandbox config

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
            cwd=popen_cwd,
        )

        with self._lock:
            state["proc"] = proc

        # Send prompt via stdin and close
        proc.stdin.write(code + "\n")
        proc.stdin.close()

        try:
            while True:
                if check_cancelled():
                    proc.send_signal(signal.SIGINT)
                    with self._lock:
                        if pane_id not in self._state:
                            return {"output": "[killed]", "cell_index": 0}
                        state["proc"] = None
                        output = (
                            "".join(state["current_output_parts"]) + "\n[cancelled]"
                        )
                        cell_index = len(state["cells"])
                    return {"output": output, "cell_index": cell_index}

                line = proc.stdout.readline()
                if not line:
                    break

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                with self._lock:
                    if pane_id not in self._state:
                        return {"output": "[killed]", "cell_index": 0}
                    state["current_events"].append(data)

                if msg_type == "init" and not session_id:
                    session_id = data.get("session_id", "")
                    with self._lock:
                        state["session_id"] = session_id

                elif msg_type == "message" and data.get("role") == "assistant":
                    text = data.get("content", "")
                    if text:
                        with self._lock:
                            state["current_output_parts"].append(text)

                elif msg_type == "result":
                    if data.get("status") != "success":
                        raise RuntimeError(f"Gemini error: {data}")
                    break

            with self._lock:
                if pane_id not in self._state:
                    return {"output": "[killed]", "cell_index": 0}
                state["proc"] = None
                output = "".join(state["current_output_parts"])
                cell_index = len(state["cells"])
                state["cells"].append(
                    {
                        "index": cell_index,
                        "input": code,
                        "output": output,
                        "events": list(state["current_events"]),
                    }
                )
                return {"output": output, "cell_index": cell_index}
        finally:
            if proc.poll() is None:
                proc.terminate()
            with self._lock:
                if pane_id in self._state:
                    state["proc"] = None
                    state["current_input"] = ""
                    state["current_output_parts"] = []
                    state["current_events"] = []


class OpenAIBackend(LLMBackend):
    """Backend for Codex CLI (uses ChatGPT subscription)."""

    def spawn(
        self,
        label: str,
        name: str | None,
        args: str | None,
        child_allowed_tools: list[str],
        socket_path: str = "",
        venv: str = "",
        cwd: str = "",
        prompt: str = "",
        *,
        sandbox: dict[str, list[str]] | None = None,
        session_id: str = "",
    ) -> tuple[str, str]:
        """Spawn a new Codex session. Returns (loop_id, loop_id)."""
        timestamp = datetime.now().strftime("%H%M%S")
        loop_id = f"openai-{name or timestamp}"

        # Parse model from args if provided
        model = ""
        if args:
            import shlex

            arg_list = shlex.split(args)
            for i, arg in enumerate(arg_list):
                if arg == "--model" and i + 1 < len(arg_list):
                    model = arg_list[i + 1]
                elif arg.startswith("--model="):
                    model = arg.split("=", 1)[1]

        with self._lock:
            self._state[loop_id] = {
                "thread_id": "",
                "model": model,
                "cells": [],
                "proc": None,
                "sandbox": sandbox or {},
                "cwd": cwd,
                "current_input": "",
                "current_output_parts": [],
                "current_events": [],
            }

        return loop_id, loop_id

    def eval(
        self, pane_id: str, code: str, check_cancelled: Callable[[], bool]
    ) -> dict[str, Any]:
        """Send message to Codex CLI and wait for response."""
        with self._lock:
            state = self._state.get(pane_id)
            if not state:
                raise RuntimeError(f"Codex session not found: {pane_id}")
            thread_id = state["thread_id"]
            model = state["model"]
            loop_sandbox = state.get("sandbox", {})
            loop_cwd = state.get("cwd", "")
            state["current_input"] = code
            state["current_output_parts"] = []
            state["current_events"] = []

        # Build command
        if thread_id:
            cmd = ["codex", "exec", "resume", thread_id, "--json", code]
        else:
            cmd = ["codex", "exec", "--json", code]
        if model:
            cmd.extend(["--model", model])

        env = _subscription_env("OPENAI_API_KEY")

        # Wrap command with sandbox if requested
        popen_cwd = None
        if loop_sandbox:
            from mcp_handley_lab.loop.sandbox import sandbox_cmd

            cmd, popen_cwd = sandbox_cmd(cmd, loop_cwd, loop_sandbox, "openai", env=env)
            env = None  # env is baked into sandbox config

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
            cwd=popen_cwd,
        )

        with self._lock:
            state["proc"] = proc

        try:
            while True:
                if check_cancelled():
                    proc.send_signal(signal.SIGINT)
                    with self._lock:
                        if pane_id not in self._state:
                            return {"output": "[killed]", "cell_index": 0}
                        state["proc"] = None
                        output = (
                            "".join(state["current_output_parts"]) + "\n[cancelled]"
                        )
                        cell_index = len(state["cells"])
                    return {"output": output, "cell_index": cell_index}

                line = proc.stdout.readline()
                if not line:
                    break

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                with self._lock:
                    if pane_id not in self._state:
                        return {"output": "[killed]", "cell_index": 0}
                    state["current_events"].append(data)

                if msg_type == "thread.started" and not thread_id:
                    thread_id = data.get("thread_id", "")
                    with self._lock:
                        state["thread_id"] = thread_id

                elif msg_type == "item.completed":
                    item = data.get("item", {})
                    if item.get("type") == "agent_message":
                        text = item.get("text", "")
                        if text:
                            with self._lock:
                                state["current_output_parts"].append(text)

                elif msg_type == "turn.completed":
                    break

                elif msg_type in ("turn.failed", "error"):
                    raise RuntimeError(f"Codex error: {data}")

            with self._lock:
                if pane_id not in self._state:
                    return {"output": "[killed]", "cell_index": 0}
                state["proc"] = None
                output = "".join(state["current_output_parts"])
                cell_index = len(state["cells"])
                state["cells"].append(
                    {
                        "index": cell_index,
                        "input": code,
                        "output": output,
                        "events": list(state["current_events"]),
                    }
                )
                return {"output": output, "cell_index": cell_index}
        finally:
            if proc.poll() is None:
                proc.terminate()
            with self._lock:
                if pane_id in self._state:
                    state["proc"] = None
                    state["current_input"] = ""
                    state["current_output_parts"] = []
                    state["current_events"] = []


class JupyterBackend(LLMBackend):
    """Backend using Jupyter kernels for structured code execution.

    Uses jupyter_client to communicate with Jupyter kernels (Python, Julia, R, etc.)
    via the Jupyter messaging protocol. Provides clean JSON-based completion detection
    without terminal scraping or ANSI stripping.
    """

    EVAL_TIMEOUT = 300  # Wall-clock timeout for eval in seconds
    MAX_EVENTS = 1000
    MAX_DATA_LEN = 10000
    # Mimetypes that are always omitted from event storage (binary/large payloads)
    _OMIT_MIMES = frozenset(
        {
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/svg+xml",
            "application/pdf",
            "application/json",
        }
    )

    def __init__(self, default_kernel: str = "python3"):
        super().__init__()
        self._default_kernel = default_kernel

    def spawn(
        self,
        label: str,
        name: str | None,
        args: str | None,
        child_allowed_tools: list[str],
        socket_path: str = "",
        venv: str = "",
        cwd: str = "",
        prompt: str = "",
        *,
        sandbox: dict[str, list[str]] | None = None,
        session_id: str = "",
    ) -> tuple[str, str]:
        """Spawn a new Jupyter kernel. Returns (loop_id, loop_id).

        Args:
            label: Human-readable label
            name: Optional name suffix for loop_id
            args: Extra arguments (supports --kernel <name>)
            child_allowed_tools: Unused (Jupyter kernels don't have tool access)
            socket_path: Daemon socket path to inject as MCP_LOOP_SOCKET
            venv: Not supported for jupyter (raises error if provided)
            cwd: Working directory for the kernel
            prompt: Unused (Jupyter kernels don't have system prompts)
            sandbox: Not supported for jupyter (raises error if provided)
            session_id: Unused
        """
        import shlex

        from jupyter_client import KernelManager
        from jupyter_client.kernelspec import KernelSpecManager

        if sandbox:
            raise ValueError("sandbox is not supported for jupyter backends")
        if venv:
            raise ValueError("venv is not supported for jupyter backends")

        timestamp = datetime.now().strftime("%H%M%S")
        loop_id = f"jupyter-{name or timestamp}"

        # Parse --kernel from args
        kernel_name = self._default_kernel
        if args:
            arg_list = shlex.split(args)
            for i, arg in enumerate(arg_list):
                if arg == "--kernel" and i + 1 < len(arg_list):
                    kernel_name = arg_list[i + 1]
                elif arg.startswith("--kernel="):
                    kernel_name = arg.split("=", 1)[1]

        km = KernelManager(kernel_name=kernel_name)
        kc = None
        try:
            # Build env with loop socket info
            env = dict(os.environ)
            if socket_path:
                env["MCP_LOOP_SOCKET"] = socket_path
                env["MCP_LOOP_PARENT_ID"] = loop_id

            km.start_kernel(cwd=cwd or None, env=env)
            kc = km.client()
            kc.start_channels()
            kc.wait_for_ready(timeout=60)

            # Drain startup chatter from iopub
            deadline = time.time() + 1.0
            while time.time() < deadline:
                try:
                    kc.get_iopub_msg(timeout=0.1)
                except queue.Empty:
                    break

        except Exception as e:
            if kc is not None:
                with contextlib.suppress(Exception):
                    kc.stop_channels()
                if hasattr(kc, "close"):
                    with contextlib.suppress(Exception):
                        kc.close()
            with contextlib.suppress(Exception):
                km.shutdown_kernel(now=True)
            if hasattr(km, "cleanup_resources"):
                with contextlib.suppress(Exception):
                    km.cleanup_resources()
            # List available kernels in error message
            try:
                specs = KernelSpecManager().find_kernel_specs()
                available = ", ".join(sorted(specs.keys()))
            except Exception:
                available = "(could not list)"
            raise RuntimeError(
                f"Failed to start jupyter kernel '{kernel_name}': {e}. "
                f"Available kernels: {available}"
            ) from e

        with self._lock:
            self._state[loop_id] = {
                "km": km,
                "kc": kc,
                "cells": [],
                "current_input": "",
                "current_output_parts": [],
                "current_events": [],
            }

        return loop_id, loop_id

    def eval(
        self, pane_id: str, code: str, check_cancelled: Callable[[], bool]
    ) -> dict[str, Any]:
        """Execute code in Jupyter kernel and wait for completion."""
        with self._lock:
            state = self._state.get(pane_id)
            if not state:
                raise RuntimeError(f"Jupyter session not found: {pane_id}")
            kc = state["kc"]
            km = state["km"]
            base_cell_index = len(state["cells"])
            state["current_input"] = code
            state["current_output_parts"] = []
            state["current_events"] = []
            state["stdin_handled"] = False

        msg_id = kc.execute(code, allow_stdin=False)
        saw_matching_msg = False
        suffix = ""  # Appended to output on non-normal exit
        start = time.time()

        try:
            while True:
                # Check state still exists (kill during eval)
                with self._lock:
                    if pane_id not in self._state:
                        return {"output": "[killed]", "cell_index": base_cell_index}

                # Check cancellation every iteration (not only on queue.Empty)
                if check_cancelled():
                    km.interrupt_kernel()
                    self._drain_until_idle(kc, msg_id, state, pane_id)
                    suffix = "[cancelled]"
                    break

                # Check wall-clock timeout every iteration
                if time.time() - start > self.EVAL_TIMEOUT:
                    km.interrupt_kernel()
                    self._drain_until_idle(kc, msg_id, state, pane_id)
                    suffix = "[timed out]"
                    break

                # Poll stdin every iteration (kernel may block waiting for input
                # even when no iopub messages arrive)
                with self._lock:
                    stdin_handled = state.get("stdin_handled", False)
                if not stdin_handled:
                    self._poll_stdin(kc, km, state, pane_id)

                # Check kernel alive
                if not km.is_alive():
                    suffix = "[kernel died]"
                    break

                # Poll iopub for output messages
                try:
                    msg = kc.get_iopub_msg(timeout=0.2)
                except queue.Empty:
                    continue

                # Filter by parent msg_id
                parent_id = msg.get("parent_header", {}).get("msg_id")
                if parent_id != msg_id:
                    # Accept unparented status:idle if we've seen matching msgs
                    if (
                        saw_matching_msg
                        and not parent_id
                        and msg.get("msg_type") == "status"
                        and msg.get("content", {}).get("execution_state") == "idle"
                    ):
                        break
                    continue

                saw_matching_msg = True
                self._process_iopub_msg(msg, state, pane_id)

                if (
                    msg.get("msg_type") == "status"
                    and msg.get("content", {}).get("execution_state") == "idle"
                ):
                    break

            # Finalize cell (all exit paths: normal, cancelled, timed out, kernel died)
            dead_state = None
            with self._lock:
                if pane_id not in self._state:
                    return {"output": "[killed]", "cell_index": base_cell_index}
                output = "".join(state["current_output_parts"])
                if suffix:
                    if output:
                        output += "\n"
                    output += suffix
                cell_index = len(state["cells"])
                state["cells"].append(
                    {
                        "index": cell_index,
                        "input": code,
                        "output": output,
                        "events": list(state["current_events"]),
                    }
                )

                # Auto-cleanup on kernel death (pop under lock, cleanup outside)
                if suffix == "[kernel died]":
                    dead_state = self._state.pop(pane_id, None)

            # Cleanup outside the lock
            if dead_state:
                self._cleanup_kernel(dead_state)

            return {"output": output, "cell_index": cell_index}

        except Exception:
            # ZMQ/channel errors — check if killed
            with self._lock:
                if pane_id not in self._state:
                    return {"output": "[killed]", "cell_index": base_cell_index}
            raise

        finally:
            with self._lock:
                if pane_id in self._state:
                    state["current_input"] = ""
                    state["current_output_parts"] = []
                    state["current_events"] = []
                    state.pop("stdin_handled", None)

    def terminate(self, pane_id: str) -> None:
        """Interrupt the running kernel."""
        with self._lock:
            state = self._state.get(pane_id)
            km = state.get("km") if state else None
        if km and km.is_alive():
            km.interrupt_kernel()

    def kill(self, pane_id: str) -> None:
        """Shut down kernel and remove session state."""
        with self._lock:
            state = self._state.pop(pane_id, None)
        if state:
            self._cleanup_kernel(state)

    def _cleanup_kernel(self, state: dict[str, Any]) -> None:
        """Clean up kernel resources from a popped state dict."""
        kc = state.get("kc")
        km = state.get("km")
        if kc:
            with contextlib.suppress(Exception):
                kc.stop_channels()
            if hasattr(kc, "close"):
                with contextlib.suppress(Exception):
                    kc.close()
        if km:
            with contextlib.suppress(Exception):
                km.shutdown_kernel(now=True)
            if hasattr(km, "cleanup_resources"):
                with contextlib.suppress(Exception):
                    km.cleanup_resources()

    def _poll_stdin(
        self,
        kc: Any,
        km: Any,
        state: dict[str, Any],
        pane_id: str,
    ) -> None:
        """Check for stdin requests and reject them (non-blocking)."""
        try:
            stdin_msg = kc.get_stdin_msg(timeout=0)
        except queue.Empty:
            return
        if stdin_msg.get("msg_type") == "input_request":
            # Reply empty and interrupt — we don't support interactive input
            with contextlib.suppress(Exception):
                if hasattr(kc, "input_reply"):
                    kc.input_reply("")
                else:
                    kc.input("")
            with contextlib.suppress(Exception):
                km.interrupt_kernel()
            with self._lock:
                if pane_id in self._state:
                    state["stdin_handled"] = True
                    state["current_output_parts"].append(
                        "[error: kernel requested stdin; not supported]"
                    )

    def _process_iopub_msg(
        self,
        msg: dict,
        state: dict[str, Any],
        pane_id: str,
    ) -> None:
        """Process a matching iopub message, appending output and storing event."""
        msg_type = msg.get("msg_type", "")
        content = msg.get("content", {})

        # Store event (capped, with truncation)
        with self._lock:
            if pane_id not in self._state:
                return
            if len(state["current_events"]) < self.MAX_EVENTS:
                event = self._truncate_event(msg)
                state["current_events"].append(event)

        # Process message types
        if msg_type == "stream":
            text = content.get("text", "")
            with self._lock:
                if pane_id in self._state:
                    state["current_output_parts"].append(text)

        elif msg_type == "execute_result":
            text = content.get("data", {}).get("text/plain", "")
            with self._lock:
                if pane_id in self._state:
                    state["current_output_parts"].append(text)

        elif msg_type == "display_data":
            data = content.get("data", {})
            text = data.get("text/plain", "")
            if text:
                with self._lock:
                    if pane_id in self._state:
                        state["current_output_parts"].append(text)
            elif data:
                first_mime = next(iter(data))
                with self._lock:
                    if pane_id in self._state:
                        state["current_output_parts"].append(
                            f"[display_data: {first_mime}]"
                        )

        elif msg_type == "error":
            traceback = content.get("traceback", [])
            if traceback:
                cleaned = "\n".join(ANSI.sub("", ln) for ln in traceback)
            else:
                ename = content.get("ename", "Error")
                evalue = content.get("evalue", "")
                cleaned = f"{ename}: {evalue}"
            with self._lock:
                if pane_id in self._state:
                    state["current_output_parts"].append(cleaned)

    def _drain_until_idle(
        self,
        kc: Any,
        msg_id: str,
        state: dict[str, Any],
        pane_id: str,
    ) -> None:
        """Read iopub messages until idle or timeout (used after interrupt)."""
        deadline = time.time() + 5.0
        saw_matching = False
        while time.time() < deadline:
            try:
                msg = kc.get_iopub_msg(timeout=0.2)
            except queue.Empty:
                continue
            parent_id = msg.get("parent_header", {}).get("msg_id")
            msg_type = msg.get("msg_type", "")
            content = msg.get("content", {})

            if parent_id == msg_id:
                saw_matching = True
                if msg_type == "status" and content.get("execution_state") == "idle":
                    break
                self._process_iopub_msg(msg, state, pane_id)
                continue

            # Accept unparented idle once we've seen matching messages
            if (
                saw_matching
                and not parent_id
                and msg_type == "status"
                and content.get("execution_state") == "idle"
            ):
                break

    def _truncate_event(self, msg: dict) -> dict:
        """Truncate large data values in event for storage."""
        event = dict(msg)
        content = event.get("content", {})
        if "data" in content and isinstance(content["data"], dict):
            truncated_data = {}
            for mime, value in content["data"].items():
                if mime in self._OMIT_MIMES:
                    truncated_data[mime] = f"[omitted {mime} {len(str(value))}]"
                elif isinstance(value, str) and len(value) > self.MAX_DATA_LEN:
                    truncated_data[mime] = value[: self.MAX_DATA_LEN] + "..."
                elif not isinstance(value, str):
                    truncated_data[mime] = f"[omitted {mime} {len(str(value))}]"
                else:
                    truncated_data[mime] = value
            event = {**event, "content": {**content, "data": truncated_data}}
        return event
