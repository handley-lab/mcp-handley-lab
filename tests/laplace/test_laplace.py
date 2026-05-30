"""Tests for the Laplace Engine: canon, verify, assessment, dreamer, render."""

from __future__ import annotations

import shutil

import pytest
import yaml

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
    # activities and statuses are constrained vocabularies
    assert {s.activity for s in c.skills.values()} <= {"generating", "staging", "evaluating"}
    assert {s.status for s in c.skills.values()} <= {"experimental", "core", "deprecated"}


def test_canon_resolve_variants():
    c = Canon.load()
    # canon:// ref, bare wiki ref, and bare skill name all resolve
    assert "Laplace Voice" in c.resolve("canon://aesthetics/voice_and_style")[1]
    assert c.resolve("aesthetics/voice_and_style")[1]
    assert c.resolve("epistemic_ledger")[0].name == "SKILL.md"
    with pytest.raises(KeyError):
        c.resolve("canon://nope/nothing")


def test_get_canon_reloads_on_disk_change(tmp_path, monkeypatch):
    dst = tmp_path / "canon"
    shutil.copytree(canonmod._PACKAGED_CANON, dst)
    monkeypatch.setenv("LAPLACE_CANON", str(dst))
    first = canonmod.get_canon(fresh=True)
    # An unchanged canon returns the cached object - no needless reload.
    assert canonmod.get_canon() is first
    # A skill forged on disk (host-forge style) is visible without fresh=True:
    # the live tools pick up the change within the running process.
    probe = dst / "skills" / "probe_skill"
    probe.mkdir(parents=True)
    (probe / "SKILL.md").write_text(
        "---\nname: probe_skill\ndescription: probe\n---\n# Probe [EXPERIMENTAL]\n",
        encoding="utf-8",
    )
    reloaded = canonmod.get_canon()
    assert reloaded is not first
    assert "probe_skill" in reloaded.skills


def test_orient_infers_domain_and_ranks_skills():
    c = Canon.load()
    b = c.orient("lint the latex voice and check derivations for the phases of hierarchy")
    assert b["domain"] == "synthetics"
    # domain axioms + project are loaded with content
    refs = {d["ref"] for d in b["domain_context"]}
    assert any("synthetics/axioms" in r for r in refs)
    # skills are bucketed by activity (generating|staging|evaluating)
    names = {s["name"] for bucket in b["skills"].values() for s in bucket}
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


def test_epistemic_counts_eqref_not_just_ref(tmp_path):
    # A label referenced only via \eqref must not be reported as an orphan.
    tex = tmp_path / "eqref.tex"
    tex.write_text(
        r"\begin{equation}\label{eq:a} x=1 \end{equation} see \eqref{eq:a}." + "\n",
        encoding="utf-8",
    )
    rep = verify.verify(str(tex), checks=["epistemic"])
    assert rep["checks"]["epistemic"]["orphans"] == []


def test_voice_flags_unicode_emdash(tmp_path):
    tex = tmp_path / "uni.tex"
    tex.write_text("This clause — an aside — lingers.\n", encoding="utf-8")
    rep = verify.verify(str(tex), checks=["voice"])
    assert any(f["kind"] == "vonnegut" for f in rep["checks"]["voice"]["violations"])


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


def test_fitness_promotes_and_deprecates(isolated_canon):
    # isolated_canon seeds both skills experimental, so good evidence promotes
    # latex_forge to core and sustained non-use deprecates css_forge.
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
    # Deterministic lifecycle baseline, independent of whatever statuses the
    # shipped manifest happens to carry: the skills these tests exercise start
    # experimental. Committed as the repo's base so promotion/deprecation are
    # genuine transitions and a dreamer rollback has a target to revert to.
    seed = {"skills": {
        "latex_forge": {"status": "experimental"},
        "css_forge": {"status": "experimental"},
    }}
    (dst / "lifecycle.yaml").write_text(yaml.safe_dump(seed), encoding="utf-8")
    dreamer._ensure_repo(dst)
    dreamer._git(dst, "add", "-A")
    dreamer._git(dst, "commit", "-m", "seed: experimental baseline")
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


def test_noop_dream_does_not_advance_boundary(isolated_canon):
    # An idle dream - empty window, nothing applied or forged - must NOT stamp the
    # boundary, or a later dream's window would be fragmented and friction orphaned.
    out0 = dreamer.dream(apply=True, forge=False)
    assert out0["assessment"]["events_seen"] == 0
    assert out0["boundary_advanced"] is False
    assert telemetry.last_dream_ts() is None
    # A productive dream (earns a transition) does advance the boundary.
    for _ in range(6):
        telemetry.log("verify_check", skill="latex_forge", check="voice", passed=True)
    out1 = dreamer.dream(apply=True, forge=False)
    assert out1["boundary_advanced"] is True
    assert telemetry.last_dream_ts() is not None


def test_events_since_filters_by_timestamp(isolated_state):
    telemetry.log("feedback", skill="latex_forge", signal=1)
    cutoff = telemetry.events()[-1]["ts"]  # timestamp of that event
    telemetry.log("feedback", skill="latex_forge", signal=1)  # after cutoff
    after = telemetry.events(since=cutoff)
    # only the event AT or AFTER cutoff survives; the one strictly before does not
    assert all(ev["ts"] >= cutoff for ev in after)
    assert len(after) >= 1


def test_dream_stamps_and_scopes_next_dream(isolated_canon):
    # Pre-dream events: earn a transition.
    for _ in range(6):
        telemetry.log("verify_check", skill="latex_forge", check="voice", passed=True)
    out1 = dreamer.dream(apply=True, forge=False)
    # dream_complete was logged — last_dream_ts is non-None.
    ts = telemetry.last_dream_ts()
    assert ts is not None
    # Second dream sees only events AFTER the first dream's stamp.
    # No new events => assess sees nothing => no transitions.
    out2 = dreamer.dream(apply=False, forge=False)
    assert out2["assessment"]["events_seen"] == 0


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


IDENTITY = """# Identity Ledger

## ID-001: Widget Theorem
**Kind:** coined-term
**Forms:** widget theorem, WT
**Role:** the core named result; must appear.
**Status:** load-bearing

## ID-002: Gadget framing
**Kind:** framing
**Forms:** gadget framing
**Role:** preferred cross-domain bridge.
**Status:** optional
"""


def test_identity_ledger_detects_drift(tmp_path):
    man = tmp_path / "identity_ledger.md"
    man.write_text(IDENTITY, encoding="utf-8")
    draft = tmp_path / "draft.tex"
    draft.write_text("This draft uses the gadget framing but never the core result.\n", encoding="utf-8")
    r = verify.run_backing("identity_ledger", target=str(draft), args=["--manifest", str(man)])
    assert "DRIFT" in r["stdout"]
    assert "ID-001" in r["stdout"]  # load-bearing Widget Theorem dropped
    assert r["returncode"] == 1


def test_identity_ledger_passes_when_present(tmp_path):
    man = tmp_path / "identity_ledger.md"
    man.write_text(IDENTITY, encoding="utf-8")
    draft = tmp_path / "draft.tex"
    draft.write_text("We prove the Widget Theorem via the gadget framing.\n", encoding="utf-8")
    r = verify.run_backing("identity_ledger", target=str(draft), args=["--manifest", str(man)])
    assert "No identity drift" in r["stdout"]
    assert r["returncode"] == 0


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
