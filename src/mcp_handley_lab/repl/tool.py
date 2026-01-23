"""REPL tool for persistent interactive sessions via MCP.

Manages REPL sessions (IPython, Bash, Python) using tmux as the backend.
Sessions persist across MCP server restarts because tmux owns the processes.
"""

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.repl.backends import list_backends
from mcp_handley_lab.repl.manager import TmuxSessionManager

mcp = FastMCP("REPL Tool")

# Lazy-initialized manager
_manager: TmuxSessionManager | None = None


def _get_manager() -> TmuxSessionManager:
    """Get or create the session manager."""
    global _manager
    if _manager is None:
        _manager = TmuxSessionManager()
    return _manager


class SessionCreateResult(BaseModel):
    """Result of creating a new REPL session."""

    session_id: str = Field(
        ..., description="Unique identifier for the session (tmux pane ID)"
    )
    backend: str = Field(..., description="The backend type (bash, ipython, python)")
    name: str = Field(..., description="Human-readable session name")
    message: str = Field(..., description="Status message")


class SessionInfo(BaseModel):
    """Information about an active REPL session."""

    session_id: str = Field(..., description="Unique identifier for the session")
    backend: str = Field(..., description="The backend type")
    name: str = Field(..., description="Human-readable session name")
    created_at: str = Field(..., description="ISO timestamp when session was created")


class EvalResult(BaseModel):
    """Result of executing code in a REPL session."""

    output: str = Field(..., description="Command output")
    exit_code: int | None = Field(None, description="Exit code (None if timed out)")
    timed_out: bool = Field(False, description="Whether the command timed out")
    session_id: str = Field(..., description="The session ID where code was executed")


class ReadResult(BaseModel):
    """Result of reading current session output."""

    output: str = Field(..., description="Current visible output from the session")
    session_id: str = Field(..., description="The session ID")


class BackendInfo(BaseModel):
    """Information about an available backend."""

    name: str = Field(..., description="Backend name")
    description: str = Field(..., description="Backend description")


@mcp.tool(
    description="Create a new REPL session. Sessions persist in tmux and survive MCP restarts. Returns session_id for subsequent operations. Use this to load large data (files, documents, datasets) as variables that persist outside your context window - you can then programmatically examine, slice, and query the data without consuming context."
)
def create(
    backend: str = Field(
        "bash",
        description="The REPL backend type: 'bash', 'ipython', or 'python'",
    ),
    name: str = Field(
        "",
        description="Optional human-readable name for the session. Auto-generated if not provided.",
    ),
) -> SessionCreateResult:
    """Create a new REPL session in tmux."""
    manager = _get_manager()
    session_id = manager.create(backend, name or None)

    sessions = manager._load_sessions()
    meta = sessions.get(session_id, {})

    return SessionCreateResult(
        session_id=session_id,
        backend=backend,
        name=meta.get("name", name or backend),
        message=f"Created {backend} session in tmux pane {session_id}",
    )


@mcp.tool(
    description="Execute code in a REPL session. Uses prompt detection for reliable completion detection. Returns output and exit code. Variables persist between calls - load large data once, then run multiple queries against it. Only the output comes back into context, not the full data."
)
def eval(
    session_id: str = Field(
        ...,
        description="The session ID (tmux pane ID) returned from create()",
    ),
    code: str = Field(
        ...,
        description="The code to execute. Can reference variables from previous eval() calls - e.g., load a file into `data`, then query `data[0:100]` or `len(data)` in subsequent calls.",
    ),
    timeout: int = Field(
        30,
        description="Maximum seconds to wait for completion. Command is interrupted if exceeded.",
    ),
) -> EvalResult:
    """Execute code in a REPL session and return the output."""
    manager = _get_manager()
    output, timed_out = manager.eval(session_id, code, timeout)

    return EvalResult(
        output=output,
        exit_code=None,  # Prompt-based detection doesn't capture exit codes
        timed_out=timed_out,
        session_id=session_id,
    )


@mcp.tool(
    description="Read the current visible output from a REPL session without executing anything."
)
def read(
    session_id: str = Field(
        ...,
        description="The session ID (tmux pane ID)",
    ),
    lines: int = Field(
        100,
        description="Number of lines to capture from scrollback",
    ),
) -> ReadResult:
    """Capture current pane output."""
    manager = _get_manager()
    output = manager.capture_output(session_id, lines)

    return ReadResult(
        output=output,
        session_id=session_id,
    )


@mcp.tool(description="Send Ctrl-C to interrupt a running command in a REPL session.")
def interrupt(
    session_id: str = Field(
        ...,
        description="The session ID (tmux pane ID)",
    ),
) -> dict:
    """Send Ctrl-C to interrupt the current command."""
    manager = _get_manager()
    manager.send_interrupt(session_id)

    return {
        "status": "interrupted",
        "session_id": session_id,
        "message": "Sent Ctrl-C to session",
    }


@mcp.tool(
    description="List all active REPL sessions. Reconciles with tmux to remove orphaned entries."
)
def list_sessions() -> list[SessionInfo]:
    """List all active REPL sessions."""
    manager = _get_manager()
    sessions = manager.list_sessions()

    return [
        SessionInfo(
            session_id=s.session_id,
            backend=s.backend,
            name=s.name,
            created_at=s.created_at,
        )
        for s in sessions
    ]


@mcp.tool(
    description="Destroy a REPL session. Kills the tmux pane and cleans up metadata."
)
def destroy(
    session_id: str = Field(
        ...,
        description="The session ID (tmux pane ID) to destroy",
    ),
) -> dict:
    """Kill a tmux pane and clean up metadata."""
    manager = _get_manager()
    manager.destroy(session_id)

    return {
        "status": "destroyed",
        "session_id": session_id,
        "message": f"Destroyed session {session_id}",
    }


@mcp.tool(description="List available REPL backends (bash, ipython, python).")
def backends() -> list[BackendInfo]:
    """List all available backends."""
    return [
        BackendInfo(name=b["name"], description=b["description"])
        for b in list_backends()
    ]
