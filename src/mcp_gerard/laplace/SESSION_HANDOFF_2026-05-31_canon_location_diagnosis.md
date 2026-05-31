# Session Handoff — Canon Location Diagnosis (fuel for a meta-dream)

**Date:** 2026-05-31
**Branch:** `feat/laplace-engine`
**Status:** diagnosis only — no canon prose changed. Queued for a big meta-dream on *where things live*.

---

## Why this exists

The next session is a **big meta-dream**. This doc is the durable, dreamer-facing
transmission of what was found, because the telemetry channel is **not reliable
right now** (see "Transmission caveat" below) — do not assume the fitness numbers
carry this. Read this file.

## What this session actually was

It started as the canon weave pass the graph handoff
(`SESSION_HANDOFF_2026-05-31_graph.md`) queued. It became a **location
diagnosis** instead, because two premises broke:

1. A garbled first read had me about to weave **fictional** skills (`anf_node`,
   `section_smith`, `cross_link`, `citation_integrity`, `prose_polish`,
   `voice_check`) — none exist. The real canon is 32 skills / 35 wiki.
2. The prior handoff names **`global_weaver` as the weave owner. It is not.**
   See below.

## Findings

### 1. Definitions live in-repo — confirmed
`get_canon().root` = `mcp-gerard/src/mcp_gerard/laplace/canon` (32 skills, 35
wiki, no junction/symlink). **Nothing lives in a paper orchestra that
shouldn't.** The author's worry ("skills live in the paper orchestras") is an
over-reading of two true things: (a) project *state* correctly defers to the
orchestra repos, and (b) a handful of skills carry project lore.

### 2. The real mess: coupling lives in *skills*, not nodes
- **By-design (correct):** project nodes (ANF, phujck, talks) defer live state to
  their repos via `HANDOFF.md`. The firewall pattern works here.
- **Coupling smells (the work):**
  - `figure_standard` (global) hard-codes `scripts/figs/anf_style.py` from the ANF
    project — self-flagged to lift into a canon backing once proven on a 2nd
    project. Not yet lifted.
  - `global_weaver` (core) hard-codes one manuscript set in its description (*Law
    of Laws, Wigner's Many Friends, Cost of Complexity, Variational Wrong Object*).
  - web mechanic family (`web_deployment_mechanic`, `css_forge`, `html_mechanic`,
    `laplace_release_mechanic` — mostly deprecated) hard-codes `phujck.github.io`.
  - `synthetics_architect` ties to the **superseded** Phases of Hierarchy.
- **Not coupling, just vocabulary:** "orchestra/orchestrator", "handoff",
  `compile_orchestra.py`, `weave_orchestra.py` are engine nouns — don't count them.

### 3. `global_weaver` is miscast — and there is no canon-weaver
`global_weaver`'s prose + backing `scripts/weave_orchestra.py` weave a
**manuscript directory** (cross-refs/labels across SGO papers), NOT the canon
graph. So:
- The canon-weave task has **no owner**. `graph.py` *measures* health (38 orphans
  / 41 components over 72 nodes) but nothing *repairs* it.
- The weave task itself is still valid against the **real** orphan list — the
  `evidence_ledger` / `numerical_evidence` / `literature_scout` → `result_foundry`
  cluster is genuine (their prose already names each other; they just lack
  `[[ ]]` / `canon://` links).

## Dream candidates (decisions for the meta-dream)

1. **Split or rename `global_weaver`** into an orchestra-weaver vs. a new
   **canon-weaver** skill that owns repairing `graph.py` health. Or generalise one.
2. **Enforce `context_firewall` across the canon** — lift project paths out of
   global/core skills (`figure_standard`, `global_weaver`) into project nodes.
3. **Retire the dead web/release mechanic family** or rebuild with real backings
   (they're already deprecated and unused).
4. **Run the real weave** over the genuine orphan cluster once an owner exists.

## Transmission caveat (itself dream fuel)

Friction was logged via `laplace_log` (−1) against `global_weaver`,
`figure_standard`, `context_firewall` with full notes. **But `laplace_assess`
run immediately after did NOT reflect them** — `global_weaver` still reads
`feedback: 0` / "healthy", `figure_standard` reads `feedback: +1`. The logs
succeeded (they're in the telemetry log) but the assess/dream window isn't
reading them back. This is the **assess/dream window mismatch + racing
auto-commit** friction (a `laplace_log` call auto-committed `lifecycle.yaml` and
raced a manual commit this session). The meta-dream should treat the telemetry
pipeline's read/write window as a first-class target — a self-refinement engine
that can't reliably read its own friction signals is the deepest bug here.

## State
- No canon prose changed. `lifecycle.yaml` telemetry committed (`2adbe96`) and pushed.
- Memory: `canon-location-discipline.md`, `laplace-engine-self-dev-friction.md`.
- Untracked scratch left in repo root (`empty.txt`, `out.json`, `out.txt`,
  `request.json`) — not mine to delete; clean up at will.
