# Laplace Engine — Global Autonomy Backlog

A standing to-do for the engine and the autonomous dreamer, captured so items can be deliberately deferred rather than chased - the `focus_rail` discipline applied to the engine itself. Nothing here is active until promoted. Each entry is stated as work to do, in universal terms (no project specifics).

## Skills to forge or re-forge
- **deep_corpus_scout (re-forge, decoupled).** Recursive large-corpus flattening and distillation - dense source tarballs, multi-file repositories - for evidence extraction beyond a single context pass. A prior dreamer forged it coupled to external API modules; it was reverted to keep the engine self-contained. Re-forge in decoupled, host-executed form, and decide whether it merges with `reference_archaeologist` (targeted distillation) or stands distinct (sheer volume).

## Generating skills to forge-by-doing (mathematics & evidence)
The core of the generating activity ("doing mathematics to add to evidence") and the producers of the result schema's derivation, machine-map, and empirical faces. Identified this session but deliberately NOT forged: a generating skill is earned from the friction of actually doing the act, and no derivation or numerical check has been run yet. Forge each from real friction the first time the act is performed (the first core result of a project), never from imagination.
- **Derivation generation.** Doing the mathematics: declare the assumptions used, name and apply the technique, execute the steps to the result, and emit the compact machine-map (assumptions / techniques / recipe). Distinct from `epistemic_ledger` (evaluates derivation flow) and `result_foundry` (records the locked result) - neither does the deriving.
- **Numerical-evidence generation.** Writing and running the demonstration that validates an analytic result and yields the verdict for its status. Distinct from `empirical_ledger`, which audits existing data against claims after the fact - this produces the evidence in the first place.
- **Activity mislabel (related).** `empirical_ledger` is tagged `generating` but is an auditing / `evaluating` skill. Reclassify it; the mislabel helped hide the numerical-generation gap.

## Engine behaviour
- **orient under-ranks generating skills.** `laplace_orient` returns `skills.generating == []` even when the bucket is populated. Fix the relevance ranking so generating-activity skills surface for relevant goals.
- ~~**Canon hot-reload.**~~ *Done (2026-05-30):* `get_canon()` now caches against an mtime fingerprint over the manifest, lifecycle overlay, and skill/wiki sources, reloading automatically when anything changes on disk - so host-forge writes and hand edits are live without a fresh session. `fresh=True` still forces a reload.
- **Clean-context dreaming (top item).** The dreamer's generative step should run on distilled friction plus telemetry in an isolated context, never a long saturated session transcript - the engine's own context-firewall. Provide a way to hand the dreamer a scrubbed brief rather than a whole conversation.
- **Dreamer reads this backlog.** Wire the autonomous agenda to consult this file alongside the fitness assessment, so deferred items resurface on their own.

## Host-executed forge ergonomics
- **First-class host-forge flow.** `persist_forged_skill` exists; make the loop ergonomic (a documented step or a tool) so drafting, persisting, registering activity/tags in `index.yaml`, and committing is one smooth path. Auto-derive or prompt for activity and tags on registration.

## Skill and canon refinements
- **context_firewall: sibling-project clause.** It covers canon-poisoning but not project-to-project poisoning. Encode the active re-earning firewall: prior material enters only by re-derivation, and names are earned once the development produces what they denote.
- **Author-layer accretion mechanism.** The author node was hand-placed. Give the dreamer a distinct global/author target, with cross-session recurrence gating so traits accrete slowly and are revised rather than frozen.
- **Backing-script health.** *Exit-code honesty fixed (2026-05-30):* both evaluating scripts now exit 2 on an unreadable target and 0 on a produced report, so exec-ok means what assess assumes. Remaining: one evaluating skill still reports a low verify pass-rate; and the historical ok-rate-0.0 telemetry stays in the unbounded event log, so assess keeps surfacing a now-healthy skill - see "assess recency window" below.
- **run_backing discards failure diagnostics.** On a non-zero backing-script exit, telemetry records only `ok=false` - no returncode, no stderr tail. A later dreamer sees "script ok-rate 0.0" with nothing to act on and must re-reproduce by hand. Capture a short failure signature (returncode + stderr tail) on execute events so refine signals are self-diagnosing.
- **assess recency window.** Fitness is computed over the entire append-only event log, so failures from a since-fixed script (or a deleted target path) permanently depress a skill's measured quality and generate phantom refine signals that never clear. Add a decay or rolling window so the signal tracks current behaviour.
- ~~**Laplace test suite: 4 pre-existing failures.**~~ *Done (2026-05-30):* all four were stale assumptions, not engine breakage - `Skill.phase`→`activity`, flat-list vs activity-bucketed orient skills, and transition tests assuming pre-drift statuses. Fixed; the `isolated_canon` fixture now seeds a committed experimental baseline so promotion/deprecation are genuine and drift-proof. Suite green (21 passed), plus new hot-reload coverage.

## Architectural note
The autonomous dreamer's generative step is host-executed - the most powerful model already in the loop, running locally - not an external API call. Deterministic curation (fitness assessment, lifecycle transitions) stays in-engine. The engine stands as its own object.
