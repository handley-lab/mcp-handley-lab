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


def create(backend, name=None):
    _run(["new-session", "-d", "-s", TMUX], check=False)
    cfg = BACKENDS[backend]
    name = name or f"{backend}-{datetime.now().strftime('%H%M%S')}"
    res = _run(["new-window", "-t", TMUX, "-n", name, "-P", "-F", "#{pane_id}", *cfg.command])
    pane_id = res.stdout.strip()

    sessions = _load()
    sessions[pane_id] = {"backend": backend, "name": name, "created_at": datetime.now().isoformat()}
    _save(sessions)
    return pane_id


def _send_code(sid, code, cfg):
    code = code.rstrip("\n") + ("\n" if "\n" in code else "")
    if cfg.supports_bracketed_paste:
        _run(["load-buffer", "-"], input=code, check=True)
        _run(["paste-buffer", "-p", "-d", "-t", sid])
    else:
        _run(["send-keys", "-t", sid, "-l", code])
    _run(["send-keys", "-t", sid, "Enter"])


def capture_output(sid, n=500):
    return ANSI.sub("", _run(["capture-pane", "-t", sid, "-p", "-S", f"-{n}"]).stdout)


def eval_code(sid, code, timeout=30):
    cfg = BACKENDS[_load()[sid]["backend"]]
    prompt = re.compile(cfg.prompt_regex, re.M)
    cap = lambda: capture_output(sid, 1000)
    base = cap()
    _send_code(sid, code, cfg)

    out, timed_out = wait_for_completion(cap, base, prompt, timeout)
    if timed_out:
        interrupt(sid)
        out = cap()

    return extract_output(
        base, out, prompt, code, cfg.echo_commands,
        re.compile(cfg.continuation_regex, re.M) if cfg.continuation_regex else None
    ), timed_out


def list_sessions():
    panes = set(_run(["list-panes", "-t", TMUX, "-F", "#{pane_id}"], check=False).stdout.split())
    return [{"session_id": k, **v} for k, v in _load().items() if k in panes]


def destroy(sid):
    _run(["kill-pane", "-t", sid], check=False)


def interrupt(sid):
    _run(["send-keys", "-t", sid, "C-c"])
