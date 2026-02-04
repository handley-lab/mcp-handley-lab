"""Loop daemon protocol - JSON over Unix socket."""

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

    action: str  # spawn, eval, read, read_raw, list, status, terminate, kill
    namespace: str
    loop_id: str = ""
    backend: str = ""
    code: str = ""
    prompt: str = ""  # for spawn (claude)
    name: str = ""  # optional name for spawn
    args: str = ""  # backend-specific args
    child_allowed_tools: list[str] = field(default_factory=list)
    sync_timeout: float = 1.0  # seconds to wait before returning async

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "namespace": self.namespace,
            "loop_id": self.loop_id,
            "backend": self.backend,
            "code": self.code,
            "prompt": self.prompt,
            "name": self.name,
            "args": self.args,
            "child_allowed_tools": self.child_allowed_tools,
            "sync_timeout": self.sync_timeout,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Request":
        return cls(
            action=d.get("action", ""),
            namespace=d.get("namespace", ""),
            loop_id=d.get("loop_id", ""),
            backend=d.get("backend", ""),
            code=d.get("code", ""),
            prompt=d.get("prompt", ""),
            name=d.get("name", ""),
            args=d.get("args", ""),
            child_allowed_tools=d.get("child_allowed_tools", []),
            sync_timeout=d.get("sync_timeout", 1.0),
        )


@dataclass
class Response:
    """Response from the loop daemon."""

    ok: bool
    error: str = ""
    error_code: str = ""
    loop_id: str = ""
    output: str = ""
    namespace: str = ""
    elapsed_seconds: float = 0.0
    cell_index: int = 0
    loops: list[dict[str, Any]] = field(default_factory=list)
    cells: list[dict[str, Any]] = field(default_factory=list)
    running: bool = False
    started_at: str = ""
    raw_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict. Always includes all fields for protocol consistency."""
        return {
            "ok": self.ok,
            "error": self.error,
            "error_code": self.error_code,
            "loop_id": self.loop_id,
            "output": self.output,
            "namespace": self.namespace,
            "elapsed_seconds": self.elapsed_seconds,
            "cell_index": self.cell_index,
            "loops": self.loops,
            "cells": self.cells,
            "running": self.running,
            "started_at": self.started_at,
            "raw_output": self.raw_output,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Response":
        return cls(
            ok=d.get("ok", False),
            error=d.get("error", ""),
            error_code=d.get("error_code", ""),
            loop_id=d.get("loop_id", ""),
            output=d.get("output", ""),
            namespace=d.get("namespace", ""),
            elapsed_seconds=d.get("elapsed_seconds", 0.0),
            cell_index=d.get("cell_index", 0),
            loops=d.get("loops", []),
            cells=d.get("cells", []),
            running=d.get("running", False),
            started_at=d.get("started_at", ""),
            raw_output=d.get("raw_output", ""),
        )

    @classmethod
    def error_response(
        cls, message: str, code: str = ERROR_INVALID_REQUEST
    ) -> "Response":
        return cls(ok=False, error=message, error_code=code)
