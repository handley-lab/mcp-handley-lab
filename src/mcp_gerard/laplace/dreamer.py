"""The Dreamer: the slow, self-refining loop.

Between sessions, the dreamer reads the telemetry-derived fitness assessment and
silently reparametrises the canon:

  * Deterministic curation (always safe, autonomous): apply the evidence-gated
    lifecycle transitions from ``assess`` - promote proven experimental skills to
    core, deprecate the unused or degraded - by writing the machine-owned
    ``lifecycle.yaml`` and committing it to the canon git history.

  * Generative forging (optional, LLM-backed): draft or refine a SKILL.md from
    observed friction, born ``experimental`` under the Probationary Protocol.

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
from mcp_gerard.laplace.canon import Canon, get_canon

# ---------------------------------------------------------------------------
# git helpers, scoped to the canon subtree
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


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


def forge_skill(
    canon: Canon,
    friction: str,
    transcript: str = "",
    model: str = "claude",
) -> dict[str, Any]:
    """Draft a new experimental skill from observed friction, using the LLM.

    Resilient: if the LLM is unavailable, returns a brief the host agent can run
    instead, so the dreamer degrades to propose-only rather than failing.
    """
    persona = canon.resolve("agents/the_dreamer.yaml")[1] if (canon.root / "agents" / "the_dreamer.yaml").exists() else ""
    instructions = (
        "Forge ONE new skill that would permanently eliminate the described "
        "friction. Output a complete SKILL.md with YAML frontmatter containing "
        "`name` (snake_case) and `description`, followed by a concise protocol. "
        "The skill is born EXPERIMENTAL.\n\n"
        f"OBSERVED FRICTION:\n{friction}\n\n"
        f"RECENT TRANSCRIPT (excerpt):\n{transcript[:4000]}"
    )
    try:
        from mcp_gerard import llm  # imported lazily; needs API keys

        result = llm.chat(
            prompt=instructions,
            system_prompt=persona or "You are The Dreamer, refining the Laplace canon.",
            model=model,
            branch="false",
            temperature=0.4,
        )
        content = result.content
    except Exception as e:  # noqa: BLE001 - degrade to a brief on any failure
        return {
            "forged": False,
            "mode": "brief",
            "reason": f"LLM unavailable ({type(e).__name__}); returning brief for host to execute.",
            "persona": persona,
            "instructions": instructions,
        }

    m = _NAME_RE.search(content)
    if not m:
        return {"forged": False, "mode": "draft", "draft": content, "reason": "no name in draft"}
    name = m.group(1).lower()
    skill_dir = canon.root / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")

    # Register as experimental in the lifecycle overlay.
    life = dict(canon.lifecycle or {})
    life.setdefault("skills", {})
    life["skills"][name] = {
        "status": "experimental",
        "forged": _now(),
        "history": [{"from": None, "to": "experimental", "reason": "forged by dreamer", "at": _now()}],
    }
    _save_lifecycle(canon, life)
    return {"forged": True, "name": name, "path": skill_md, "skill_md": skill_md}


# ---------------------------------------------------------------------------
# the cycle
# ---------------------------------------------------------------------------


def dream(
    apply: bool = True,
    forge: bool = False,
    friction: str = "",
    transcript: str = "",
    model: str = "claude",
    commit: bool = True,
) -> dict[str, Any]:
    """Run the R&R cycle. Deterministic curation by default; forging on request."""
    canon = get_canon(fresh=True)
    report = _assess.assess(canon)
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

    if forge and friction:
        canon = get_canon(fresh=True)  # pick up lifecycle write
        fres = forge_skill(canon, friction, transcript, model)
        out["forge"] = fres
        if fres.get("forged"):
            changed.append(Path(fres["skill_md"]))
            changed.append(_lifecycle_path(canon))

    if commit and changed:
        msg = _audit_message(out)
        sha = _commit(canon.root, changed, msg)
        out["commit"] = sha

    get_canon(fresh=True)  # ensure subsequent reads see the new canon
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
