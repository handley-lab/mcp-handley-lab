"""MCP Loop Tool - REPL orchestration with parent-child model.

Uses Unix process model: each loop has loop_id (like PID) and parent_id (like PPID).
No access control - if you know the loop_id, you can operate on it.
"""

import json

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.loop.shared import ManageResult, RunResult

mcp = FastMCP("Loop Tool")


class ManageArgs(BaseModel):
    """Input arguments for manage action."""

    action: str
    loop_id: str = ""
    parent_id: str = ""  # for spawn: session_id or parent loop_id
    label: str = ""  # for spawn: optional tag for tmux window naming
    backend: str = ""
    name: str = ""
    args: str = ""  # backend-specific args
    cwd: str = ""  # for spawn: working directory
    prompt: str = ""  # for spawn: system prompt (claude backend)
    session_id: str = ""  # for spawn: resume a previous session (claude backend)
    descendants_of: str = ""  # for list: filter to subtree
    child_allowed_tools: list[str] = Field(default_factory=list)
    venv: str = (
        ""  # for spawn: path to venv (created with --system-site-packages if missing)
    )
    sandbox: str = ""  # for spawn: JSON mount spec {"guest": ["host", "rw|ro"], ...}


@mcp.tool()
def manage(params: ManageArgs) -> ManageResult:
    """
    Manage loops: spawn, list, read, read_raw, status, terminate, kill, prune.

    Loops are persistent REPL sessions (Python, Bash, Julia, etc.) that run in tmux.
    Uses Unix process model: each loop has loop_id (like PID) and parent_id (like PPID).
    If you know the loop_id, you can operate on it.

    Actions:
    - spawn: Create new loop. Params: backend (required), parent_id (optional), label (optional)
    - list: List loops. Params: parent_id (direct children), descendants_of (subtree). Each loop includes orphaned flag.
    - read: Get cells from loop. Params: loop_id
    - read_raw: Get raw terminal capture. Params: loop_id
    - status: Check if run is in progress. Params: loop_id
    - terminate: Send Ctrl-C to interrupt. Params: loop_id
    - kill: Force-kill loop. Params: loop_id
    - prune: Kill a loop only if orphaned (safe kill). Params: loop_id

    Available backends: bash, zsh, python, ipython, julia, R, clojure, apl, maple, ollama, mathematica, claude, gemini, openai, jupyter, jupyter-python, jupyter-julia, jupyter-r

    Args:
        params: ManageArgs with action and action-specific fields

    Returns:
        ManageResult with action-specific fields populated. List includes current_session_id for context.
    """
    from mcp_handley_lab.loop.shared import manage as _manage

    sandbox = json.loads(params.sandbox) if params.sandbox else None

    return _manage(
        action=params.action,
        loop_id=params.loop_id,
        parent_id=params.parent_id,
        label=params.label,
        backend=params.backend,
        name=params.name,
        args=params.args,
        cwd=params.cwd,
        prompt=params.prompt,
        session_id=params.session_id,
        descendants_of=params.descendants_of,
        child_allowed_tools=params.child_allowed_tools,
        venv=params.venv,
        sandbox=sandbox,
    )


@mcp.tool()
def run(loop_id: str, input: str, sync_timeout: float = 1.0) -> RunResult:
    """
    Run input through a loop.

    If run completes within sync_timeout, returns result directly.
    If run takes longer, returns immediately with running=True; use status/read to check progress.
    To interrupt, use manage(action="terminate") to send Ctrl-C.

    Args:
        loop_id: Target loop ID from spawn
        input: Input to run (code for Python/Bash, natural language for Claude)
        sync_timeout: Seconds to wait (default 1.0). 0=return immediately, negative=block until done.

    Returns:
        RunResult with output, cell_index, elapsed_seconds. If running=True, run continues in background.
    """
    from mcp_handley_lab.loop.shared import run as _run

    return _run(loop_id=loop_id, input=input, sync_timeout=sync_timeout)
