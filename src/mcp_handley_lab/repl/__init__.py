"""REPL tool for persistent interactive sessions via MCP.

This module provides a general REPL (Read-Eval-Print-Loop) tool that manages
persistent sessions with interactive interpreters (Bash, IPython, Python)
using tmux as the backend.

Key features:
- Sessions persist across MCP server restarts (tmux owns the processes)
- Prompt-based detection for reliable command completion
- Support for multiple backends (bash, ipython, python, aichat, ollama, mathematica)
- Command history logging
- Session metadata persistence

Usage:
    # Create a session
    session = create(backend="ipython", name="my-session")

    # Execute code
    result = eval(session_id=session.session_id, code="2 + 2")

    # List sessions
    sessions = list_sessions()

    # Destroy when done
    destroy(session_id=session.session_id)
"""

from mcp_handley_lab.repl.backends import (
    BACKENDS,
    BackendConfig,
    get_backend,
    list_backends,
)
from mcp_handley_lab.repl.manager import TmuxSessionManager
from mcp_handley_lab.repl.tool import mcp

__all__ = [
    "BACKENDS",
    "BackendConfig",
    "TmuxSessionManager",
    "get_backend",
    "list_backends",
    "mcp",
]
