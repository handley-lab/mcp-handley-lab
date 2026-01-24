import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from mcp_handley_lab.repl.backends import BACKENDS
from mcp_handley_lab.repl.completion import extract_output, wait_for_completion

TMUX = "mcp-repls"
STORAGE = Path("~/.mcp-handley-lab/repl").expanduser()
SESSIONS_FILE = STORAGE / "sessions.json"
ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07")

STORAGE.mkdir(parents=True, exist_ok=True)
if not SESSIONS_FILE.exists():
    SESSIONS_FILE.write_text("{}")


def _run(args, **kw):
    return subprocess.run(["tmux", *args], capture_output=True, text=True, **kw)


def _load():
    return json.loads(SESSIONS_FILE.read_text())


def _save(s):
    SESSIONS_FILE.write_text(json.dumps(s))


def _capture(sid, n=500):
    # -e preserves escape codes which prevents tmux from stripping trailing whitespace
    return ANSI.sub(
        "", _run(["capture-pane", "-e", "-t", sid, "-p", "-S", f"-{n}"]).stdout
    )


def create(backend, name=None, args=None):
    if _run(["new-session", "-d", "-s", TMUX]).returncode == 0:
        default_window = _run(
            ["list-windows", "-t", TMUX, "-F", "#{window_id}"]
        ).stdout.strip()
    else:
        default_window = None

    cfg = BACKENDS[backend]
    extra_args = args or cfg.default_args
    command = cfg.command + (extra_args.split() if extra_args else [])
    name = name or f"{backend}-{datetime.now().strftime('%H%M%S')}"
    res = _run(
        ["new-window", "-t", TMUX, "-n", name, "-P", "-F", "#{pane_id}", *command]
    )
    pane_id = res.stdout.strip()

    if default_window:
        _run(["kill-window", "-t", default_window])

    sessions = _load()
    sessions[pane_id] = {
        "backend": backend,
        "name": name,
        "created_at": datetime.now().isoformat(),
    }
    _save(sessions)
    return pane_id


def list_sessions():
    panes = set(
        _run(["list-panes", "-t", TMUX, "-F", "#{pane_id}"], check=False).stdout.split()
    )
    return [{"session_id": k, **v} for k, v in _load().items() if k in panes]


def destroy(sid):
    _run(["send-keys", "-t", sid, "C-c"])
    _run(["kill-pane", "-t", sid], check=False)


def parse_cells(sid):
    """Parse terminal output into cells based on backend prompts."""
    meta = _load()[sid]
    cfg = BACKENDS[meta["backend"]]
    output = _capture(sid, 2000)

    # Match prompt at start of line (not requiring end of line)
    prompt_start = cfg.prompt_regex.rstrip("$")
    prompt = re.compile(prompt_start, re.M)
    continuation = (
        re.compile(cfg.continuation_regex) if cfg.continuation_regex else None
    )

    lines = output.split("\n")
    cells = []
    current_input = []
    current_output = []

    for line in lines:
        match = prompt.match(line)
        if match:
            # Save previous cell if we have content
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
            # Extract input after prompt
            input_text = line[match.end() :].strip()
            if input_text:
                current_input.append(input_text)
        elif continuation and continuation.match(line):
            # Continuation line - append to input
            cont_match = continuation.match(line)
            current_input.append(line[cont_match.end() :])
        elif current_input:
            # We have input, so this is output
            current_output.append(line)

    # Save final cell if it has content (but not if just waiting at prompt)
    if current_input and current_output:
        cells.append(
            {
                "index": len(cells),
                "input": "\n".join(current_input),
                "output": "\n".join(current_output).strip(),
            }
        )

    return cells


def read_cells(sid, cell=None):
    """Read cells from session. cell can be index (int), 'In[N]', 'Out[N]', or None for all."""
    cells = parse_cells(sid)

    if cell is None:
        return cells

    # Parse cell specifier
    if isinstance(cell, int):
        idx = cell if cell >= 0 else len(cells) + cell
        if 0 <= idx < len(cells):
            return cells[idx]
        return None

    # Handle In[N] or Out[N] format
    in_match = re.match(r"In\[(\d+)\]", cell, re.I)
    out_match = re.match(r"Out\[(\d+)\]", cell, re.I)

    if in_match:
        idx = int(in_match.group(1))
        for c in cells:
            if c["index"] == idx:
                return {"index": idx, "input": c["input"]}
        return None

    if out_match:
        idx = int(out_match.group(1))
        for c in cells:
            if c["index"] == idx:
                return {"index": idx, "output": c["output"]}
        return None

    # Try as integer string
    try:
        return read_cells(sid, int(cell))
    except ValueError:
        return None


def eval_code(sid, code, timeout=30):
    cfg = BACKENDS[_load()[sid]["backend"]]
    prompt = re.compile(cfg.prompt_regex, re.M)

    def cap():
        return _capture(sid, 1000)

    base = cap()

    # Send code
    code_text = code.rstrip("\n") + ("\n" if "\n" in code else "")
    if cfg.supports_bracketed_paste:
        _run(["load-buffer", "-"], input=code_text, check=True)
        _run(["paste-buffer", "-p", "-d", "-t", sid])
    else:
        _run(["send-keys", "-t", sid, "-l", code_text])
    _run(["send-keys", "-t", sid, "Enter"])

    out, timed_out = wait_for_completion(cap, base, prompt, timeout)
    if timed_out:
        _run(["send-keys", "-t", sid, "C-c"])
        out = cap()

    output = extract_output(
        base,
        out,
        prompt,
        code,
        cfg.echo_commands,
        re.compile(cfg.continuation_regex, re.M) if cfg.continuation_regex else None,
    )

    # Get cell index
    cells = parse_cells(sid)
    cell_index = len(cells) - 1 if cells else 0

    return {"output": output, "cell_index": cell_index, "timed_out": timed_out}
