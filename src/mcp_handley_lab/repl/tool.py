from mcp.server.fastmcp import FastMCP

from mcp_handley_lab.repl import manager
from mcp_handley_lab.repl.backends import BACKENDS

mcp = FastMCP("REPL Tool")


@mcp.tool()
def create(backend: str = "bash", name: str = "") -> dict:
    return {"session_id": manager.create(backend, name or None), "message": f"Created {backend} session"}


@mcp.tool()
def eval(session_id: str, code: str, timeout: int = 30) -> dict:
    output, timed_out = manager.eval_code(session_id, code, timeout)
    return {"output": output, "timed_out": timed_out, "session_id": session_id}


@mcp.tool()
def read(session_id: str, lines: int = 100) -> dict:
    return {"output": manager.capture_output(session_id, lines), "session_id": session_id}


@mcp.tool()
def interrupt(session_id: str) -> dict:
    manager.interrupt(session_id)
    return {"status": "interrupted", "session_id": session_id}


@mcp.tool()
def list_sessions() -> list[dict]:
    return manager.list_sessions()


@mcp.tool()
def destroy(session_id: str) -> dict:
    manager.destroy(session_id)
    return {"status": "destroyed", "session_id": session_id}


@mcp.tool()
def backends() -> list[dict]:
    return [{"name": k, "description": v.description} for k, v in BACKENDS.items()]
