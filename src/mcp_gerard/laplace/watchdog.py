"""Tool-level watchdog: no laplace_* handler may hang its caller indefinitely.

The engine is a single-process stdio server. A handler that blocks - a wedged
subprocess, a deadlocked pipe, a daemon that inherited a handle - blocks the
*caller* with no recourse, because the MCP client only sees a tool that never
returns. That is the structural defect: a tool able to hang the caller forever.

``guard`` runs the real work on a daemon worker thread and waits at most
``timeout`` seconds for it. If the work overruns, the engine returns a clean,
structured timeout dict and abandons the thread rather than blocking. Python
cannot force-kill a thread, but every blocking call the handlers make is itself
bounded (git ``timeout=10``, script ``timeout<=110``), so the abandoned worker
unwinds on its own; the daemon flag keeps it from holding process exit.

This is the umbrella that makes the engine honest under *any* future blocking
fault, not just the fsmonitor pipe deadlock that motivated it.
"""

from __future__ import annotations

import threading
from typing import Any, Callable


def guard(name: str, timeout: float, thunk: Callable[[], Any]) -> Any:
    """Run ``thunk`` with a hard wall-clock cap. Return its value, or a timeout dict.

    Exceptions raised by ``thunk`` propagate unchanged (the caller's normal error
    path). Only a genuine overrun is converted into a structured result.
    """
    box: dict[str, Any] = {}
    done = threading.Event()

    def _run() -> None:
        try:
            box["value"] = thunk()
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller thread
            box["error"] = exc
        finally:
            done.set()

    worker = threading.Thread(target=_run, name=f"laplace-{name}", daemon=True)
    worker.start()

    if not done.wait(timeout):
        return {
            "error": f"{name} exceeded its {timeout:.0f}s watchdog and was abandoned",
            "timed_out": True,
            "hint": (
                "The engine returned control instead of hanging. The underlying "
                "work is detached and bounded by its own subprocess timeout, so it "
                "will unwind on its own. If this recurs, check for a wedged git or "
                "git-fsmonitor--daemon process holding a pipe open."
            ),
        }

    if "error" in box:
        raise box["error"]
    return box["value"]
