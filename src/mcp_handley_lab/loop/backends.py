"""Loop backends - TmuxBackend for terminal-based REPLs."""

import os
import re
import subprocess
import sys
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
    echo_commands: bool = True
    default_args: str = ""


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
        default_args="--matplotlib",
    ),
    "julia": BackendConfig("julia", ["julia"], "Julia", r"^julia> ?$"),
    "R": BackendConfig("R", ["R"], "R", r"^> ?$", r"^\+ ?$"),
    "clojure": BackendConfig(
        "clojure",
        ["clojure"],
        "Clojure",
        r"^[a-zA-Z0-9._-]+=> ?$",
        supports_bracketed_paste=False,
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
        namespace: str,
        name: str | None,
        args: str | None,
        child_allowed_tools: list[str],
    ) -> tuple[str, str]:
        """Spawn a new REPL. Returns (loop_id, pane_id)."""
        # Create session if it doesn't exist
        default_window = None
        if not _session_exists():
            _run(["new-session", "-d", "-s", TMUX_SESSION])
            default_window = _run(
                ["list-windows", "-t", TMUX_SESSION, "-F", "#{window_id}"]
            ).stdout.strip()

        extra_args = args or self.config.default_args
        base_command = self.config.command + (extra_args.split() if extra_args else [])

        # Strip venv from environment so tmux windows start clean
        clean_path = os.pathsep.join(
            p
            for p in os.environ.get("PATH", "").split(os.pathsep)
            if not p.startswith(sys.prefix)
        )
        command = [
            "env",
            "-u",
            "VIRTUAL_ENV",
            "-u",
            "PYTHONPATH",
            f"PATH={clean_path}",
        ] + base_command

        timestamp = datetime.now().strftime("%H%M%S")
        loop_id = f"{self.config.name}-{name or timestamp}"
        window_name = f"{namespace}-{loop_id}"

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
        if self.config.supports_bracketed_paste:
            _run(["load-buffer", "-"], input=code_text)
            _run(["paste-buffer", "-p", "-d", "-t", pane_id])
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
