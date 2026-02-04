"""Loop daemon protocol - JSON over Unix socket.

Uses Unix process model: each loop has loop_id (like PID) and parent_id (like PPID).
No namespace hierarchy - if you know the loop_id, you can operate on it.
"""

from dataclasses import dataclass, field
from typing import Any

# Error codes
ERROR_NOT_FOUND = "not_found"
ERROR_BACKEND_ERROR = "backend_error"
ERROR_INVALID_REQUEST = "invalid_request"
ERROR_CANCELLED = "cancelled"


@dataclass
class Request:
    """Request to the loop daemon."""

    action: str  # spawn, run, read, read_raw, list, status, terminate, kill
    loop_id: str = ""  # for operations on existing loops
    parent_id: str = ""  # for spawn: session_id or parent loop_id
    label: str = ""  # for spawn: optional human-readable tag for tmux window
    backend: str = ""  # for spawn
    input: str = ""  # for run
    prompt: str = ""  # for spawn (claude)
    name: str = ""  # optional name for spawn
    args: str = ""  # backend-specific args
    child_allowed_tools: list[str] = field(default_factory=list)
    sync_timeout: float = 1.0  # seconds to wait before returning async
    descendants_of: str = ""  # for list: filter to subtree of this parent
    current_session_id: str = (
        ""  # for list: caller's session_id for context in response
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "loop_id": self.loop_id,
            "parent_id": self.parent_id,
            "label": self.label,
            "backend": self.backend,
            "input": self.input,
            "prompt": self.prompt,
            "name": self.name,
            "args": self.args,
            "child_allowed_tools": self.child_allowed_tools,
            "sync_timeout": self.sync_timeout,
            "descendants_of": self.descendants_of,
            "current_session_id": self.current_session_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Request":
        return cls(
            action=d.get("action", ""),
            loop_id=d.get("loop_id", ""),
            parent_id=d.get("parent_id", ""),
            label=d.get("label", ""),
            backend=d.get("backend", ""),
            input=d.get("input", ""),
            prompt=d.get("prompt", ""),
            name=d.get("name", ""),
            args=d.get("args", ""),
            child_allowed_tools=d.get("child_allowed_tools", []),
            sync_timeout=d.get("sync_timeout", 1.0),
            descendants_of=d.get("descendants_of", ""),
            current_session_id=d.get("current_session_id", ""),
        )


@dataclass
class Response:
    """Response from the loop daemon."""

    ok: bool
    error: str = ""
    error_code: str = ""
    loop_id: str = ""
    parent_id: str = ""  # for spawn: the parent_id that was set
    label: str = ""  # for spawn: the label that was set
    output: str = ""
    elapsed_seconds: float = 0.0
    cell_index: int = 0
    loops: list[dict[str, Any]] = field(default_factory=list)
    cells: list[dict[str, Any]] = field(default_factory=list)
    running: bool = False
    started_at: str = ""
    raw_output: str = ""
    current_session_id: str = ""  # for list: the caller's session_id for context

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict. Always includes all fields for protocol consistency."""
        return {
            "ok": self.ok,
            "error": self.error,
            "error_code": self.error_code,
            "loop_id": self.loop_id,
            "parent_id": self.parent_id,
            "label": self.label,
            "output": self.output,
            "elapsed_seconds": self.elapsed_seconds,
            "cell_index": self.cell_index,
            "loops": self.loops,
            "cells": self.cells,
            "running": self.running,
            "started_at": self.started_at,
            "raw_output": self.raw_output,
            "current_session_id": self.current_session_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Response":
        return cls(
            ok=d.get("ok", False),
            error=d.get("error", ""),
            error_code=d.get("error_code", ""),
            loop_id=d.get("loop_id", ""),
            parent_id=d.get("parent_id", ""),
            label=d.get("label", ""),
            output=d.get("output", ""),
            elapsed_seconds=d.get("elapsed_seconds", 0.0),
            cell_index=d.get("cell_index", 0),
            loops=d.get("loops", []),
            cells=d.get("cells", []),
            running=d.get("running", False),
            started_at=d.get("started_at", ""),
            raw_output=d.get("raw_output", ""),
            current_session_id=d.get("current_session_id", ""),
        )

    @classmethod
    def error_response(
        cls, message: str, code: str = ERROR_INVALID_REQUEST
    ) -> "Response":
        return cls(ok=False, error=message, error_code=code)
