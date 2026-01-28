from mcp.server.fastmcp import FastMCP

from mcp_handley_lab.repl import manager
from mcp_handley_lab.repl.backends import BACKENDS

mcp = FastMCP("REPL Tool")


@mcp.resource("repl://backends")
def repl_backends() -> list[str]:
    """All available REPL backends (bash, python, julia, etc.)."""
    return sorted(BACKENDS.keys())


@mcp.tool()
def session(
    action: str,
    session_id: str = "",
    backend: str = "bash",
    name: str = "",
    cell: str = "",
    args: str = "",
) -> dict:
    """
    Manage REPL sessions. Create a session before using the eval tool.
    Use repl://backends resource to discover available backends.

    Actions:
    - create: Create new session. Returns session_id for use with eval. Params: backend, name (optional), args (optional)
    - list: List active sessions. Returns list of sessions.
    - destroy: Destroy session (sends Ctrl-C first). Params: session_id
    - read: Read cells from session. Params: session_id, cell (optional)
            cell can be: index (0, 1, -1), "In[5]", "Out[7]", or omit for all cells
    """
    if action == "create":
        sid = manager.create(backend, name or None, args or None)
        return {"session_id": sid, "backend": backend, "name": name or sid}

    if action == "list":
        return {"sessions": manager.list_sessions(), "backends": list(BACKENDS.keys())}

    if action == "destroy":
        manager.destroy(session_id)
        return {"status": "destroyed", "session_id": session_id}

    if action == "read":
        cell_arg = int(cell) if cell.lstrip("-").isdigit() else (cell or None)
        result = manager.read_cells(session_id, cell_arg)
        return {"session_id": session_id, "cells": result}

    return {"error": f"Unknown action: {action}"}


@mcp.tool()
def eval(session_id: str, code: str, timeout: int = 30) -> dict:
    """
    Execute code in a REPL session. Requires a session_id from session(action='create').

    Returns output, cell_index, and timed_out flag.
    """
    result = manager.eval_code(session_id, code, timeout)
    return {"session_id": session_id, **result}
