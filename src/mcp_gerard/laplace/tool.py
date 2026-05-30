"""The Laplace Engine MCP server.

Exposes the tripartite drafting loop to any MCP client:

  orient   - laplace_orient / laplace_search / laplace_index / laplace_resolve
  execute  - laplace_skill / laplace_run
  verify   - laplace_verify
  dream    - laplace_assess / laplace_dream / laplace_rollback
  adapter  - laplace_sync

Every orient/execute/verify call is logged to the telemetry ledger, which feeds
the endogenous fitness assessment that governs the dreamer's silent refinements.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_gerard.laplace import assess as _assess
from mcp_gerard.laplace import dreamer as _dreamer
from mcp_gerard.laplace import render as _render
from mcp_gerard.laplace import telemetry as _telemetry
from mcp_gerard.laplace import verify as _verify
from mcp_gerard.laplace.canon import get_canon

mcp = FastMCP("laplace")


# ---------------------------------------------------------------------------
# ORIENT - understand the goal, load relevant canon
# ---------------------------------------------------------------------------


@mcp.tool()
def laplace_orient(
    goal: str = Field(description="What you are trying to accomplish, in a sentence."),
    domain: str = Field(
        default="",
        description="Optional domain (e.g. 'synthetics'). Inferred from the goal if omitted.",
    ),
) -> dict[str, Any]:
    """Load a concise, relevance-ranked canon bundle for a goal.

    The first third of the loop. Returns the global foundation (voice, workflow,
    operations), the active domain's axioms and project state, and the candidate
    skills for the next action - full content for the most relevant items, refs
    for the rest. Start every non-trivial task here.
    """
    canon = get_canon()
    bundle = canon.orient(goal, domain or None)
    _telemetry.log(
        "orient",
        domain=bundle["domain"],
        offered=[s["name"] for bucket in bundle["skills"].values() for s in bucket],
    )
    return bundle


@mcp.tool()
def laplace_search(
    query: str = Field(description="Keywords to search across all canon."),
    limit: int = Field(default=20, description="Maximum matches to return."),
) -> list[dict[str, Any]]:
    """Full-text search across wiki nodes and skills. Returns ref + line context."""
    canon = get_canon()
    q = query.lower()
    out: list[dict[str, Any]] = []
    for node in canon.wiki.values():
        text = canon.resolve(node.ref)[1]
        for i, line in enumerate(text.splitlines(), 1):
            if q in line.lower():
                out.append(
                    {"ref": f"canon://{node.ref}", "line": i, "match": line.strip()}
                )
                break
    for sk in canon.skills.values():
        blob = sk.description + " " + " ".join(sk.tags)
        if q in blob.lower() or q in sk.name.lower():
            out.append(
                {
                    "ref": f"canon://skills/{sk.name}",
                    "status": sk.status,
                    "match": sk.description,
                }
            )
    return out[:limit]


@mcp.tool()
def laplace_index() -> dict[str, Any]:
    """List the whole canon: wiki nodes, domains, and skills (with phase/status)."""
    canon = get_canon()
    return {
        "root": str(canon.root),
        "wiki": [
            {"ref": f"canon://{n.ref}", "title": n.title, "scope": n.scope}
            for n in canon.wiki.values()
        ],
        "domains": canon.domains(),
        "skills": [sk.summary() for sk in canon.skills.values()],
    }


@mcp.tool()
def laplace_resolve(
    ref: str = Field(description="A canon ref, e.g. 'canon://aesthetics/voice_and_style'."),
) -> dict[str, Any]:
    """Fetch the full content of a single canon ref."""
    canon = get_canon()
    path, content = canon.resolve(ref)
    return {"ref": ref, "path": str(path), "content": content}


# ---------------------------------------------------------------------------
# EXECUTE - translate the goal into a local action
# ---------------------------------------------------------------------------


@mcp.tool()
def laplace_skill(
    name: str = Field(description="Skill name, e.g. 'epistemic_ledger'."),
) -> dict[str, Any]:
    """Return a skill's protocol spec (SKILL.md) and how to run its backing script."""
    canon = get_canon()
    sk = canon.skills.get(name)
    if sk is None:
        return {"error": f"Unknown skill: {name!r}", "available": list(canon.skills)}
    info = sk.summary()
    info["protocol"] = sk.skill_md.read_text(encoding="utf-8")
    if sk.backing:
        info["backing_path"] = str(sk.backing_path)
        info["run"] = f"laplace_run(skill={name!r}, target=<path>)"
    return info


@mcp.tool()
def laplace_run(
    skill: str = Field(description="Skill whose backing script to run, e.g. 'epistemic_ledger'."),
    target: str = Field(default="", description="Positional path for the script (a .tex file or directory); omit for flags-only scripts."),
    args: list[str] = Field(default_factory=list, description="Extra CLI args, e.g. ['--auto-fix'] or ['--source', '...', '--start', '10']."),
) -> dict[str, Any]:
    """Execute a skill's backing script for its full artifact (graph, PDF, report)."""
    return _verify.run_backing(skill, target, args)  # telemetry logged inside run_backing


# ---------------------------------------------------------------------------
# VERIFY - translate the result back, check consistency
# ---------------------------------------------------------------------------


@mcp.tool()
def laplace_verify(
    target: str = Field(description="A .tex file (voice/epistemic) or directory (crossref)."),
    checks: list[str] = Field(
        default_factory=lambda: list(_verify.DEFAULT_CHECKS),
        description="Subset of: epistemic, voice, crossref, empirical.",
    ),
) -> dict[str, Any]:
    """Run consistency ledgers and return a structured mismatch report with pass/fail.

    The third of the loop. A non-passing report is the signal to re-orient; the
    pass/fail outcome is also logged and feeds skill-fitness assessment.
    """
    return _verify.verify(target, checks)  # telemetry logged inside verify.verify


# ---------------------------------------------------------------------------
# DREAM - endogenous assessment and silent self-refinement
# ---------------------------------------------------------------------------


@mcp.tool()
def laplace_assess() -> dict[str, Any]:
    """Report per-skill fitness (usage, pass-rate, feedback) and recommended lifecycle moves.

    The selection signal: what is used, what is not, and how it affects outcomes.
    The dreamer consults this before mutating canon.
    """
    return _assess.assess(get_canon())


@mcp.tool()
def laplace_log(
    skill: str = Field(description="Skill the signal applies to."),
    signal: int = Field(description="+1 if the skill helped, -1 if it caused friction."),
    note: str = Field(default="", description="Optional free-text context."),
) -> dict[str, Any]:
    """Record explicit feedback about a skill, feeding its fitness."""
    return _telemetry.log("feedback", skill=skill, signal=int(signal), note=note)


@mcp.tool()
def laplace_dream(
    apply: bool = Field(default=True, description="Apply evidence-gated lifecycle transitions to the canon."),
    forge: bool = Field(default=False, description="Also attempt to forge a new experimental skill from friction."),
    friction: str = Field(default="", description="Description of repeated friction to forge a skill against (with forge=True)."),
    transcript: str = Field(default="", description="Optional session transcript excerpt to inform forging."),
    model: str = Field(default="claude", description="Model to draft forged skills with."),
) -> dict[str, Any]:
    """Run the Dreamer's R&R cycle: assess fitness, then silently refine the canon.

    Promotes proven experimental skills to core, deprecates the unused/degraded,
    and (optionally) forges a new experimental skill - each as a revertible commit.
    """
    return _dreamer.dream(apply=apply, forge=forge, friction=friction, transcript=transcript, model=model)


@mcp.tool()
def laplace_rollback(
    ref: str = Field(description="The dreamer commit to revert, e.g. a sha or 'HEAD'."),
) -> dict[str, Any]:
    """Revert a previous dreamer canon mutation."""
    return _dreamer.rollback(ref)


# ---------------------------------------------------------------------------
# ADAPTER - make the engine the default across every LLM client
# ---------------------------------------------------------------------------


@mcp.tool()
def laplace_sync(
    client: str = Field(description="Target client: claude, gemini, codex, or antigravity."),
    write: bool = Field(default=False, description="Write the bootstrap to the client's native location."),
) -> dict[str, Any]:
    """Render (and optionally install) a client's bootstrap shim from the canon."""
    return _render.sync(client, write=write)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
