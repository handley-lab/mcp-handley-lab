# Session handoff - 2026-05-31 - the canon graph (laplace_graph)

## What this session did

Scouted **skyllwt/AutoSci** (a Claude-Code-native research agent, same substrate
as the engine) for graph-visualisation features, then built the integration as a
new face of the engine.

**Shipped (committed on `feat/laplace-engine`):**

- `src/mcp_gerard/laplace/graph.py` + the **`laplace_graph`** MCP tool. One
  `CanonGraph` object - nodes (wiki/skill/domain/agent), edges
  (`links_to`/`belongs_to_domain`/`has_axioms`/`dangling`), each edge carrying
  the prose line it was mined from as evidence - projected into four renders:
  Mermaid, Obsidian `.canvas`, Obsidian `graph.json`, JSON edge list. Skill
  nodes are sized by measured fitness from `assess.py`. `from_manuscript()`
  builds the *same object* from a `.tex` file/dir (sections/figures/equations,
  later extended to claims/citations, wired by `\ref` with `\input` reading
  order), so the manuscript interlock graph and the canon graph share every
  renderer. `health()` reports orphans, dangling links, dead-wood-linked
  skills, and component count. Full laplace suite green.

**NOT built (honest correction):** the dreamer's R&R run this session surfaced
**`graph_ledger`** - a verify-side skill that would run `CanonGraph.health()` as
a PASS/FAIL ledger - but returned it as a *host-forge brief*, which was not
executed. A concurrent session left a malformed `graph_ledger` stub in
`canon/index.yaml` with no `SKILL.md`. So `graph_ledger` does **not** exist as a
usable skill. It is the **top deferred item** below, not a shipped artifact.

## What the build revealed (live findings)

- **The canon is badly under-woven: ~41 connected components across 72 nodes,
  ~39 orphans** (25 of 31 skills have zero prose links in or out). This is now a
  measurable defect via `laplace_graph --health`. A `graph_ledger` skill (see
  below, not yet built) would turn it into a tracked PASS/FAIL; **`global_weaver`
  owns the remediation weave pass** (a chip was spawned for it).
- Fixed two real parsing bugs found via the graph: a `canon://` link ending a
  sentence ate the trailing full stop; agent personas (`the_dreamer`,
  `the_empiricist`) were linked from prose but not loaded as nodes.

## Next concrete steps (to mature this capability)

1. **Forge `graph_ledger` for real** (the dreamer's outstanding host-forge
   brief). Write `canon/skills/graph_ledger/SKILL.md` (evaluating, experimental),
   fix the malformed `canon/index.yaml` stub a concurrent session left, and add a
   `graph`/`topology` check to `verify.py` that calls
   `CanonGraph.from_canon().health()` so it runs through `laplace_verify` with a
   PASS/FAIL. This is the headline unfinished item.
2. **Run the weave pass** (`global_weaver`) and use `graph_ledger` /
   `laplace_graph --health` as the before/after metric. Target: collapse the
   component count.
3. **`focus` should match a label or path-tail**, not only a full node id or
   skill name (`--focus voice_and_style` fails today). Five-line fix in
   `graph._match_node`.
4. **DONE - manuscript `\input`-order stitching shipped** (commit `43d54ca`).
   `from_manuscript` now flattens a root `.tex` along its `\input`/`\include`
   tree (`_flatten_inputs`), registers section `\label` aliases, and adds the
   full interlock layer (claims, citations, `figure`+`table` floats, bare TikZ).
   law-of-laws `tex_v5/main.tex` went 41 -> **0 dangling**, 0 orphans, 1
   component (228 nodes). Point it at `main.tex`, not the `sections/` dir.
5. **Deferred from the AutoSci scout (not built):** the interactive localhost
   viewer (`serve.py` + Cytoscape `graph.js` with SSE live-reload + the
   skill-intent boundary, where the UI emits copy-paste `laplace_*` calls rather
   than faking execution). The JSON renderer is already its wire format.
6. **Rasterisation is deliberately out of scope** - the tool emits specs
   (Mermaid/Canvas/JSON), not pixels. PNG needs mermaid-cli/Chromium, which the
   sandbox cannot install. If in-pipeline PNGs are wanted, that is a separate
   `figure_standard`-adjacent rasteriser skill, not a gap here.

## Operational note for the next session

The execution **sandbox silently no-ops on writes**: a `git commit` returns
RC=0 but HEAD never advances, an outbound `curl` returns a false 404. Both are
sandbox rollback, not failure. For any write or network op, **disable the
sandbox from the first attempt**. This cost real time twice this session
(the feature commit and the dreamer's forge commit both had to be redone).

## For the meta-dreamer (cross-session transit) - 2026-05-31, interlock session

Three engine-level frictions surfaced while developing the engine *on itself*.
None is a drafting-skill gap, so none was forged. They are reconciliation work
for the meta-level.

1. **The live MCP server runs stale code for the whole session.** `mcp-laplace`
   is a stdio server spawned once at session start. Editing `graph.py` and
   re-running tests via `uv run` exercised the new code (66 green), but
   `laplace_graph(manuscript=main.tex)` through the *live tool* returned an empty
   graph - the in-process server still held the pre-edit module. `uv tool install
   -e . --force` refreshes the binary but the running connection only picks it up
   on a client-side reconnect. **Implication for self-development:** verify engine
   changes via `uv run`/pytest, never via the live `laplace_*` tools in the same
   session. A future affordance could be a `laplace_reload` or a staleness banner.

2. **`laplace_assess` and `laplace_dream` disagree on the telemetry window.**
   At close, `assess` saw **497 events** and recommended two evidence-gated
   transitions (`session_closer` experimental->core, earned; `synthetics_architect`
   ->deprecated). The subsequent `dream(apply=true)` reported its own assessment
   over **58 events**, `transitions: []`, `boundary_advanced: false` - so it
   applied neither. Likely by design (dream scopes to events since the last
   boundary), but the effect is that an *earned* promotion `assess` reports does
   not actually land, and a reader trusting `assess` would think it did. The
   meta-dreamer should reconcile the two windows, or have `assess` mark which
   recommendations are inside the current dream boundary.

3. **Auto-commit machinery races the session.** Commits appeared mid-session that
   this agent did not author (`43d54ca`, the duplicate `e2661e0`/`8eea9ac` pair),
   plus scratch files (`.agents/`, `.codex/`, `out.json`, `request.json`). The
   feature work survived intact, but the working-tree state was non-obvious to
   reason about. Worth either gitignoring the scratch artifacts or making the
   automation's commits legible (a marker in the message).
