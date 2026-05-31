"""Deadlock-proof git invocation for the engine.

The engine ran every git query through ``subprocess.run(..., capture_output=True)``,
which on Windows can deadlock indefinitely - defeating its own ``timeout`` - and
hung ``laplace_assess`` for ~30 minutes at a time. The mechanism:

  1. ``capture_output=True`` opens an OS pipe and marks its write handle
     inheritable so the child git can write to it.
  2. Git for Windows (and Claude Code's own background ``git -c
     core.fsmonitor=true`` status checks, observed spawning from the live client
     process) may start a *detached* ``git-fsmonitor--daemon``. A daemon that
     starts while our pipe's write handle is inheritable inherits it.
  3. Our git finishes, but ``subprocess.run`` blocks forever in the pipe drain:
     the read never sees EOF because the long-lived daemon still holds the write
     end open. The ``timeout`` only guards the child's exit, not the drain.

Two defences, both here so every engine git call gets them:

  * **No pipe.** Redirect stdout/stderr to temp files. With no pipe handle in
    existence there is nothing for a daemon to inherit, so the drain cannot
    block and ``timeout`` is always honoured. This is the load-bearing fix - it
    holds even when *another* process spawns the daemon.
  * **No daemon of our own.** ``-c core.fsmonitor=false`` so our own calls never
    spawn one. Belt to the temp-file braces.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def run_git(root: str | Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run ``git -C <root> <args>`` capturing output via temp files, never pipes.

    Returns a CompletedProcess with text stdout/stderr, matching the shape the
    callers expect from ``subprocess.run(..., capture_output=True, text=True)``.
    Raises ``subprocess.TimeoutExpired`` / ``OSError`` exactly as before.
    """
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as out, tempfile.TemporaryFile(
        mode="w+", encoding="utf-8", errors="replace"
    ) as err:
        proc = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-C", str(root), *args],
            stdout=out,
            stderr=err,
            timeout=timeout,
        )
        out.seek(0)
        err.seek(0)
        return subprocess.CompletedProcess(proc.args, proc.returncode, out.read(), err.read())
