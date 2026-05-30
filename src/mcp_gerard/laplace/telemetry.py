"""Telemetry ledger: the durable, append-only record of loop activity.

Every orient/execute/verify call appends a structured event here. This log is the
substrate the endogenous assessment reads to compute skill fitness, which in turn
governs the dreamer's silent promotions and deprecations.

Storage is a JSONL file under the state dir (``LAPLACE_STATE`` or
``~/.mcp-gerard/laplace``). Append-only and cheap; the audited, revertible record
of *canon edits* lives in the canon git history (see dreamer.py), not here.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def state_dir() -> Path:
    base = os.environ.get("LAPLACE_STATE")
    d = Path(base).expanduser() if base else Path("~/.mcp-gerard/laplace").expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def telemetry_path() -> Path:
    return state_dir() / "telemetry.jsonl"


# A session id groups events from one drive of the loop. Override per host client
# via LAPLACE_SESSION; otherwise one id per server process.
_SESSION = os.environ.get("LAPLACE_SESSION") or uuid.uuid4().hex[:12]


def session_id() -> str:
    return os.environ.get("LAPLACE_SESSION") or _SESSION


def log(phase: str, **fields: Any) -> dict[str, Any]:
    """Append one event and return it."""
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session": session_id(),
        "phase": phase,
        **fields,
    }
    path = telemetry_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def events(since_session: str | None = None, since: str | None = None) -> list[dict[str, Any]]:
    """Read all events, optionally filtered by session id or ISO timestamp cutoff."""
    path = telemetry_path()
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since_session and ev.get("session") != since_session:
            continue
        if since and ev.get("ts", "") < since:
            continue
        out.append(ev)
    return out


def last_dream_ts() -> str | None:
    """Return the ISO timestamp of the most recent dream_complete event, or None."""
    for ev in reversed(events()):
        if ev.get("phase") == "dream_complete":
            return ev["ts"]
    return None


def clear() -> None:
    """Wipe the telemetry log (used by tests)."""
    p = telemetry_path()
    if p.exists():
        p.unlink()
