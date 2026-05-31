# Session handoff - 2026-05-31 - the canon graph (laplace_graph)

## What this session did

Scouted **skyllwt/AutoSci** (a Claude-Code-native research agent, same substrate
as the engine) for graph-visualisation features, then built the integration as a
new face of the engine.

**Shipped (committed on `feat/laplace-engine`):**

- `71ce5fc` - `src/mcp_gerard/laplace/graph.py` + the **`laplace_graph`** MCP
  tool. One `CanonGraph` object - nodes (wiki/skill/domain/agent), edges
  (`links_to`/`belongs_to_domain`/`has_axioms`/`dangling`), each edge carrying
  the prose line it was mined from as evidence - projected into four renders:
  Mermaid, Obsidian `.canvas`, Obsidian `graph.json`, JSON edge list. Skill
  nodes are sized by measured fitness from `assess.py`. `from_manuscript()`
  builds the *same object* from a `.tex` file/dir (sections/figures/equations
  wired by `\ref`, sections classed into core-outward rings), so the manuscript
  interlock graph and the canon graph share every renderer. `health()` reports
  orphans, dangling links, dead-wood-linked skills, and component count.
  25 tests, full laplace suite green (57).
- `76b6f6e` - dreamer-forged **`graph_ledger`** skill (experimental): canon
  `health()` as a verify-side PASS/FAIL ledger. Frontmatter repaired and
  cross-linked by hand (the forge's YAML was malformed and its own commit was
  sandbox-rolled-back).

## What the build revealed (live findings)

- **The canon is badly under-woven: 41 connected components across 72 nodes, 39
  orphans** (25 of 31 skills have zero prose links in or out). This is now a
  measurable defect. `graph_ledger` is the ledger for it; **`global_weaver` owns
  the remediation weave pass** (a chip was spawned for it).
- Fixed two real parsing bugs found via the graph: a `canon://` link ending a
  sentence ate the trailing full stop; agent personas (`the_dreamer`,
  `the_empiricist`) were linked from prose but not loaded as nodes.

## Next concrete steps (to mature this capability)

1. **Run the weave pass** (`global_weaver`) and use `graph_ledger` /
   `laplace_graph --health` as the before/after metric. Target: collapse the
   component count.
2. **`graph_ledger` needs a `verify.py` check entry** to be runnable through
   `laplace_verify` - right now it is protocol-only. Add a `graph`/`topology`
   check that calls `CanonGraph.from_canon().health()`.
3. **`focus` should match a label or path-tail**, not only a full node id or
   skill name (`--focus voice_and_style` fails today). Five-line fix in
   `graph._match_node`.
4. **Manuscript parser needs `\input`-order stitching.** law-of-laws shows 56
   dangling refs, partly because cross-file label resolution does not yet follow
   `\input`. Merge in document order before resolving.
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
