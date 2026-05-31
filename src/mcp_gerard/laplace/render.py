"""Client adapters: render the canon into each LLM client's native bootstrap.

The canon is the single source of truth. Rather than hand-maintain a bootstrap
for Claude, Gemini, Codex, and Antigravity, we generate a thin shim for each that
points every conversation at the same engine: start with ``laplace_orient``,
execute via ``laplace_skill`` / ``laplace_run``, verify via ``laplace_verify``.

This keeps the Laplace Engine the default across all the user's LLMs while the
real content lives in one place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp_gerard.laplace.canon import Canon, get_canon

# Where each client expects its bootstrap. None => content-only (no known path).
CLIENT_PATHS = {
    "claude": Path("~/.claude/skills/laplace/SKILL.md").expanduser(),
    "gemini": Path("~/.gemini/GEMINI.md").expanduser(),
    "codex": Path("~/.codex/AGENTS.md").expanduser(),
    "antigravity": Path("~/.antigravity/laplace_bootstrap.md").expanduser(),
}

MCP_REGISTRATION = {
    "mcpServers": {
        "laplace": {"type": "stdio", "command": "mcp-laplace", "args": [], "env": {}}
    }
}


def _loop_section(canon: Canon) -> str:
    domains = ", ".join(canon.domains().keys()) or "(none yet)"
    foundation = "\n".join(
        f"  - {n.title} (`canon://{n.ref}`)" for n in canon.global_foundation()
    )
    return f"""## The tripartite loop

Drive every non-trivial task through the Laplace Engine MCP:

1. **orient** - call `laplace_orient(goal=...)` first. It returns the relevant
   canon: the global foundation (voice, workflow, operations), the active
   domain's axioms and project state, and the candidate skills for your action.
2. **execute** - call `laplace_skill(name)` for a protocol, or `laplace_run(skill,
   target)` to run its backing script. This is the local action.
3. **verify** - call `laplace_verify(target)` to check consistency (epistemic,
   voice, crossref). A failing report means re-orient. Do not present unverified work.

Record friction with `laplace_log(skill, signal)`. The canon refines itself
between sessions via `laplace_dream` based on measured skill fitness.

Known domains: {domains}

Global foundation always available:
{foundation}
"""


def bootstrap(client: str, canon: Canon | None = None) -> str:
    """Generate the bootstrap text for a client."""
    canon = canon or get_canon()
    body = _loop_section(canon)

    if client == "claude":
        return (
            "---\n"
            "name: laplace\n"
            "description: Bootstrap the Laplace Engine - drive drafting tasks through "
            "orient/execute/verify against the shared canon.\n"
            "---\n\n"
            "# The Laplace Engine\n\n"
            "Your drafting standards, skills, and project context live in the shared "
            "Laplace canon, served by the `laplace` MCP server.\n\n"
            + body
        )
    if client == "gemini":
        return "# The Laplace Engine (Gemini bootstrap)\n\n" + body
    if client == "codex":
        return "# AGENTS.md - The Laplace Engine\n\n" + body
    return "# The Laplace Engine\n\n" + body


def sync(client: str, write: bool = False, canon: Canon | None = None) -> dict[str, Any]:
    """Render (and optionally write) a client's bootstrap shim."""
    canon = canon or get_canon()
    if client not in CLIENT_PATHS:
        return {"error": f"unknown client {client!r}", "clients": list(CLIENT_PATHS)}
    content = bootstrap(client, canon)
    target = CLIENT_PATHS[client]
    result: dict[str, Any] = {
        "client": client,
        "path": str(target),
        "content": content,
        "mcp_registration": MCP_REGISTRATION,
        "written": False,
    }
    if write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        result["written"] = True
    return result
