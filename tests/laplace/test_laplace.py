"""Tests for the Laplace Engine: canon, verify, assessment, dreamer, render."""

from __future__ import annotations

import shutil

import pytest

from mcp_gerard.laplace import assess, dreamer, render, telemetry, verify
from mcp_gerard.laplace import canon as canonmod
from mcp_gerard.laplace.canon import Canon

pytestmark = pytest.mark.unit


SEED_TEX = r"""\documentclass{article}
\begin{document}
\section{Introduction}
We analyze the color of the system; this is crucial --- really.
\begin{equation}\label{eq:used} x = 1 \end{equation}
As shown in \ref{eq:used}, the result holds.
\begin{equation}\label{eq:orphan} y = 2 \end{equation}
We also cite \ref{eq:missing} here.
\end{document}
"""


# ---------------------------------------------------------------------------
# canon
# ---------------------------------------------------------------------------


def test_canon_loads_skills_and_wiki():
    c = Canon.load()
    assert len(c.skills) >= 10
    assert len(c.wiki) >= 8
    # phases and statuses are constrained vocabularies
    assert {s.phase for s in c.skills.values()} <= {"orient", "execute", "verify"}
    assert {s.status for s in c.skills.values()} <= {"experimental", "core", "deprecated"}


def test_canon_resolve_variants():
    c = Canon.load()
    # canon:// ref, bare wiki ref, and bare skill name all resolve
    assert "Laplace Voice" in c.resolve("canon://aesthetics/voice_and_style")[1]
    assert c.resolve("aesthetics/voice_and_style")[1]
    assert c.resolve("epistemic_ledger")[0].name == "SKILL.md"
    with pytest.raises(KeyError):
        c.resolve("canon://nope/nothing")


def test_orient_infers_domain_and_ranks_skills():
    c = Canon.load()
    b = c.orient("lint the latex voice and check derivations for the phases of hierarchy")
    assert b["domain"] == "synthetics"
    # domain axioms + project are loaded with content
    refs = {d["ref"] for d in b["domain_context"]}
    assert any("synthetics/axioms" in r for r in refs)
    names = {s["name"] for s in b["skills"]}
    assert {"latex_forge", "epistemic_ledger"} & names


# ---------------------------------------------------------------------------
# verify (mirrors legacy ledgers)
# ---------------------------------------------------------------------------


def test_verify_flags_seeded_errors(tmp_path):
    tex = tmp_path / "seed.tex"
    tex.write_text(SEED_TEX, encoding="utf-8")
    rep = verify.verify(str(tex))
    assert rep["passed"] is False
    kinds = {f["kind"] for f in rep["checks"]["voice"]["violations"]}
    assert {"americanism", "ai_slop", "vonnegut"} <= kinds
    assert "eq:orphan" in rep["checks"]["epistemic"]["orphans"]
    assert any(b["ref"] == "eq:missing" for b in rep["checks"]["crossref"]["broken_refs"])


def test_verify_clean_file_passes(tmp_path):
    tex = tmp_path / "clean.tex"
    tex.write_text(
        r"\section{Intro}\begin{equation}\label{eq:a} x=1 \end{equation}"
        r" see \ref{eq:a}." + "\n",
        encoding="utf-8",
    )
    rep = verify.verify(str(tex))
    assert rep["passed"] is True
    assert rep["issue_count"] == 0


# ---------------------------------------------------------------------------
# assessment + lifecycle
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("LAPLACE_STATE", str(tmp_path / "state"))
    telemetry.clear()
    yield
    telemetry.clear()


def test_fitness_promotes_and_deprecates(isolated_state):
    for _ in range(6):
        telemetry.log("verify_check", skill="latex_forge", check="voice", passed=True)
    for _ in range(9):
        telemetry.log("orient", domain="web", offered=["css_forge"])
    rep = assess.assess(Canon.load())
    moves = {t["name"]: t["to"] for t in rep["transitions"]}
    assert moves.get("latex_forge") == "core"
    assert moves.get("css_forge") == "deprecated"
    assert "css_forge" in rep["unused"]


def test_unused_experimental_not_promoted(isolated_state):
    rep = assess.assess(Canon.load())
    # With no telemetry, nothing earns promotion.
    assert all(t["to"] != "core" for t in rep["transitions"])


# ---------------------------------------------------------------------------
# dreamer (isolated canon copy outside the repo => independent git repo)
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_canon(tmp_path, monkeypatch):
    dst = tmp_path / "canon"
    shutil.copytree(canonmod._PACKAGED_CANON, dst)
    monkeypatch.setenv("LAPLACE_CANON", str(dst))
    monkeypatch.setenv("LAPLACE_STATE", str(tmp_path / "state"))
    telemetry.clear()
    canonmod.get_canon(fresh=True)
    yield dst
    telemetry.clear()


def test_dream_applies_transitions_commits_and_rolls_back(isolated_canon):
    for _ in range(6):
        telemetry.log("verify_check", skill="latex_forge", check="voice", passed=True)
    out = dreamer.dream(apply=True, forge=False)
    assert any(t["name"] == "latex_forge" and t["to"] == "core" for t in out["assessment"]["transitions"])
    assert out.get("commit")
    # status persisted through the lifecycle overlay
    assert canonmod.get_canon(fresh=True).skills["latex_forge"].status == "core"
    # rollback reverts
    rb = dreamer.rollback(out["commit"])
    assert rb["ok"]
    assert canonmod.get_canon(fresh=True).skills["latex_forge"].status == "experimental"


def test_dream_noop_without_evidence(isolated_canon):
    out = dreamer.dream(apply=True, forge=False)
    assert out["assessment"]["transitions"] == []
    assert out.get("commit") is None


# ---------------------------------------------------------------------------
# render / client adapters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("client", ["claude", "gemini", "codex", "antigravity"])
def test_sync_renders_each_client(client):
    res = render.sync(client, write=False)
    assert "laplace_orient" in res["content"]
    assert res["mcp_registration"]["mcpServers"]["laplace"]["command"] == "mcp-laplace"
    assert res["written"] is False


def test_sync_claude_has_skill_frontmatter():
    res = render.sync("claude", write=False)
    assert res["content"].startswith("---\nname: laplace\n")


# ---------------------------------------------------------------------------
# evidence skills (ledger completeness + alignment)
# ---------------------------------------------------------------------------

LEDGER = """# Evidence Ledger

## EPT-CLM-001: Strong claim about gain
**Claim:** The gain scales as sqrt(N).
**Derivation:** Appendix A.
**Literature:** Condorcet (1785).
**Numerical:** validate_gain().
**Status:** Proved.

## EPT-CLM-002: Weak claim about depth
**Claim:** Hierarchy depth must exceed three.
**Derivation:** Sketch only.
**Literature:** none
**Numerical:** TODO
**Status:** conjecture, gap remains.
"""


def test_evidence_ledger_flags_incomplete_and_weak(tmp_path):
    led = tmp_path / "evidence_ledger.md"
    led.write_text(LEDGER, encoding="utf-8")
    r = verify.run_backing("evidence_ledger", target=str(led))
    out = r["stdout"]
    assert "Records: 2" in out
    assert "EPT-CLM-002" in out  # weak/incomplete flagged
    assert "EPT-CLM-001" not in out.split("Incomplete")[-1].split("Non-affirmative")[0] \
        if "Incomplete" in out else True  # strong claim not in incomplete section
    assert r["returncode"] == 1  # incomplete records => exit 1


def test_evidence_alignment_tiers_and_finds_uncovered_goal(tmp_path):
    led = tmp_path / "evidence_ledger.md"
    led.write_text(LEDGER, encoding="utf-8")
    r = verify.run_backing(
        "evidence_alignment", target=str(led),
        args=["--goals", "gain, teleportation"],
    )
    out = r["stdout"]
    assert "1 strong, 0 partial, 1 weak" in out
    assert "gain" in out
    assert "teleportation" in out and "uncovered" in out.lower()
    assert (tmp_path / "support_map.md").exists()
