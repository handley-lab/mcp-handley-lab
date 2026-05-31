"""The Dreamer: the slow, self-refining loop.

Between sessions, the dreamer reads the telemetry-derived fitness assessment and
silently reparametrises the canon:

  * Deterministic curation (always safe, autonomous): apply the evidence-gated
    lifecycle transitions from ``assess`` - promote proven experimental skills to
    core, deprecate the unused or degraded - by writing the machine-owned
    ``lifecycle.yaml`` and committing it to the canon git history.

  * Generative forging (host-executed): the engine is self-contained and makes no
    external LLM API call. It hands a forging brief to the host - the most powerful
    model already in the loop, running locally - which drafts the SKILL.md and
    persists it via ``persist_forged_skill``, born ``experimental`` under the
    Probationary Protocol. Judgement routes to the host; determinism stays here.

Every mutation is a single scoped git commit, so ``rollback`` can undo it.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from mcp_gerard.laplace import assess as _assess
from mcp_gerard.laplace import telemetry as _telemetry
from mcp_gerard.laplace.gitio import run_git
from mcp_gerard.laplace.canon import Canon, get_canon

# ---------------------------------------------------------------------------
# git helpers, scoped to the canon subtree
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    # Deadlock-proof: captures via temp files, not pipes, so a stray
    # git-fsmonitor--daemon can never inherit a pipe handle and hang the drain
    # past the timeout. See gitio for the full autopsy.
    return run_git(root, *args, timeout=timeout)


def _ensure_repo(root: Path) -> None:
    if _git(root, "rev-parse", "--git-dir").returncode != 0:
        _git(root, "init")


def _commit(root: Path, paths: list[Path], message: str) -> str | None:
    """Stage only the given paths and commit. Returns the new commit sha or None."""
    _ensure_repo(root)
    rels = [str(p) for p in paths]
    if _git(root, "add", *rels).returncode != 0:
        return None
    # Nothing staged => nothing to commit.
    if _git(root, "diff", "--cached", "--quiet").returncode == 0:
        return None
    if _git(root, "commit", "-m", message).returncode != 0:
        return None
    res = _git(root, "rev-parse", "HEAD")
    return res.stdout.strip() if res.returncode == 0 else None


# ---------------------------------------------------------------------------
# lifecycle persistence
# ---------------------------------------------------------------------------


def _lifecycle_path(canon: Canon) -> Path:
    return canon.root / "lifecycle.yaml"


def _save_lifecycle(canon: Canon, data: dict[str, Any]) -> Path:
    path = _lifecycle_path(canon)
    header = (
        "# Machine-owned lifecycle overlay. The dreamer writes this; do not hand-edit.\n"
        "# It overrides skill `status` in index.yaml based on measured fitness.\n"
    )
    path.write_text(header + yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# deterministic curation
# ---------------------------------------------------------------------------


def apply_transitions(canon: Canon, report: dict[str, Any]) -> dict[str, Any]:
    """Write recommended lifecycle transitions into lifecycle.yaml."""
    life = dict(canon.lifecycle or {})
    life.setdefault("skills", {})
    fitness_by = {r["name"]: r["fitness"] for r in report["skills"]}

    for t in report["transitions"]:
        name = t["name"]
        entry = life["skills"].get(name, {}) or {}
        entry["status"] = t["to"]
        entry["fitness"] = fitness_by.get(name)
        entry["updated"] = _now()
        entry.setdefault("history", []).append(
            {"from": t["from"], "to": t["to"], "reason": t["reason"], "at": _now()}
        )
        life["skills"][name] = entry

    path = _save_lifecycle(canon, life)
    return {"lifecycle_path": path, "applied": report["transitions"]}


# ---------------------------------------------------------------------------
# generative forging (optional)
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"name:\s*([a-z0-9_]+)", re.IGNORECASE)


def _friction_from_report(report: dict[str, Any]) -> str:
    """Synthesise a friction brief from the fitness assessment when none is supplied.

    Lets the dreamer run autonomously: with no explicit friction it still hands the
    host a substantive, assessment-driven agenda.
    """
    lines: list[str] = []
    for r in report.get("refine_recommended", []):
        lines.append(f"- refine '{r['name']}': {r['refine_reason']} (signal {r['refine_signal']}).")
    unused = report.get("unused", [])
    if unused:
        lines.append("- long-unused skills to review for deprecation or merge: " + ", ".join(unused[:10]) + ".")
    if not lines:
        return "No explicit friction supplied. Review the session transcript for repeated manual work and conversational bottlenecks, and remedy them."
    return "Autonomous, assessment-driven refinement agenda:\n" + "\n".join(lines)


def forge_skill(
    canon: Canon,
    friction: str,
    transcript: str = "",
    model: str = "claude",
) -> dict[str, Any]:
    """Produce the forging brief for the host to execute directly and locally.

    The Laplace engine stands as its own object and makes no external LLM API call.
    Forging needs maximum thought and capacity, so the brief is handed to the host -
    the most powerful model already in the loop - which drafts the SKILL.md and
    persists it via ``persist_forged_skill``. ``model`` is an advisory hint only.
    """
    persona = canon.resolve("agents/the_dreamer.yaml")[1] if (canon.root / "agents" / "the_dreamer.yaml").exists() else ""
    instructions = (
        "You are the host - the most powerful model already in the loop, running "
        "locally. Execute this brief directly and with maximum rigour. Do not "
        "delegate it to an external API.\n\n"
        "Forge ONE new skill (or refine the named weak one) that would permanently "
        "eliminate the described friction. Write a complete SKILL.md with YAML "
        "frontmatter containing `name` (snake_case) and `description`, then a concise "
        "protocol. The skill is born EXPERIMENTAL. Persist it via "
        "persist_forged_skill(canon, content) and register its activity and tags in "
        "index.yaml. Then commit the canon (a single revertible commit).\n\n"
        f"OBSERVED FRICTION:\n{friction}\n\n"
        f"RECENT TRANSCRIPT (excerpt):\n{transcript[:4000]}"
    )
    return {
        "forged": False,
        "mode": "host_forge",
        "reason": "Laplace engine is self-contained; the host model forges directly and locally.",
        "model_hint": model,
        "persona": persona,
        "instructions": instructions,
    }


def persist_forged_skill(canon: Canon, content: str) -> dict[str, Any]:
    """Persist a host-drafted SKILL.md and register it experimental in lifecycle.

    Called by the host after it has drafted the skill from the forge brief.
    """
    m = _NAME_RE.search(content)
    if not m:
        return {"forged": False, "reason": "no name found in draft frontmatter"}
    name = m.group(1).lower()
    skill_dir = canon.root / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")

    # Register as experimental in the machine-owned lifecycle overlay.
    life = dict(canon.lifecycle or {})
    life.setdefault("skills", {})
    life["skills"][name] = {
        "status": "experimental",
        "forged": _now(),
        "history": [{"from": None, "to": "experimental", "reason": "forged by dreamer (host-executed)", "at": _now()}],
    }
    _save_lifecycle(canon, life)
    return {"forged": True, "name": name, "path": skill_md, "skill_md": skill_md}


# ---------------------------------------------------------------------------
# the cycle
# ---------------------------------------------------------------------------

# A dream that applied no transition, forged nothing, and saw fewer than this many
# events is idle and must NOT advance the assessment boundary (see AUTONOMY_BACKLOG,
# "No-op dream orphans evidence"). Conservative floor: only a truly empty window is
# idle. Raise it to also treat near-empty windows as idle.
_NOOP_EVENT_FLOOR = 1


def dream(
    apply: bool = True,
    forge: bool = False,
    friction: str = "",
    transcript: str = "",
    model: str = "claude",
    commit: bool = True,
) -> dict[str, Any]:
    """Run the R&R cycle. Deterministic curation by default; forging on request."""
    since = _telemetry.last_dream_ts()  # only assess events since the last dream
    canon = get_canon(fresh=True)
    report = _assess.assess(canon, since=since)
    out: dict[str, Any] = {
        "assessment": {
            "transitions": report["transitions"],
            "refine_recommended": report.get("refine_recommended", []),
            "unused": report["unused"],
            "events_seen": report["events_seen"],
        }
    }
    changed: list[Path] = []

    if apply and report["transitions"]:
        res = apply_transitions(canon, report)
        out["curation"] = {"applied": res["applied"]}
        changed.append(res["lifecycle_path"])

    if forge:
        canon = get_canon(fresh=True)  # pick up lifecycle write
        brief_friction = friction or _friction_from_report(report)
        # Self-contained engine: hand the brief to the host model to execute
        # directly and locally. The host persists via persist_forged_skill and
        # commits separately, so nothing is auto-committed here.
        out["forge"] = forge_skill(canon, brief_friction, transcript, model)

    if commit and changed:
        msg = _audit_message(out)
        sha = _commit(canon.root, changed, msg)
        out["commit"] = sha

    get_canon(fresh=True)  # ensure subsequent reads see the new canon

    # Window-leak guard: only advance the assessment boundary when the dream did
    # something. Stamping dream_complete on an idle fire would fragment the rolling
    # window and let genuine friction slip behind the boundary, assessed once and
    # never acted on.
    did_apply = bool(apply and report["transitions"])
    is_noop = not did_apply and not forge and report["events_seen"] < _NOOP_EVENT_FLOOR
    if is_noop:
        out["boundary_advanced"] = False
    else:
        _telemetry.log("dream_complete", events_seen=report["events_seen"], since=since)
        out["boundary_advanced"] = True
    return out


def _audit_message(out: dict[str, Any]) -> str:
    parts = ["dream:"]
    for t in out.get("curation", {}).get("applied", []):
        parts.append(f"{t['name']} {t['from']}->{t['to']}")
    f = out.get("forge", {})
    if f.get("forged"):
        parts.append(f"forge {f['name']}")
    return " ".join(parts) if len(parts) > 1 else "dream: no-op"


def rollback(ref: str) -> dict[str, Any]:
    """Revert a previous dreamer commit (scoped to canon files)."""
    canon = get_canon()
    res = _git(canon.root, "revert", "--no-edit", ref)
    get_canon(fresh=True)
    return {"ref": ref, "ok": res.returncode == 0, "stdout": res.stdout, "stderr": res.stderr}
