# Laplace Engine — Global Autonomy Backlog

A standing to-do for the engine and the autonomous dreamer, captured so items can be deliberately deferred rather than chased - the `focus_rail` discipline applied to the engine itself. Nothing here is active until promoted. Each entry is stated as work to do, in universal terms (no project specifics).

## Skills to forge or re-forge
- **deep_corpus_scout (re-forge, decoupled).** Recursive large-corpus flattening and distillation - dense source tarballs, multi-file repositories - for evidence extraction beyond a single context pass. A prior dreamer forged it coupled to external API modules; it was reverted to keep the engine self-contained. Re-forge in decoupled, host-executed form, and decide whether it merges with `reference_archaeologist` (targeted distillation) or stands distinct (sheer volume).

## Engine behaviour
- **orient under-ranks generating skills.** `laplace_orient` returns `skills.generating == []` even when the bucket is populated. Fix the relevance ranking so generating-activity skills surface for relevant goals.
- **Canon hot-reload.** The server caches the canon at startup, so mid-session canon edits are invisible to the live tools until a fresh session. Add cache invalidation or reload on file change.
- **Clean-context dreaming (top item).** The dreamer's generative step should run on distilled friction plus telemetry in an isolated context, never a long saturated session transcript - the engine's own context-firewall. Provide a way to hand the dreamer a scrubbed brief rather than a whole conversation.
- **Dreamer reads this backlog.** Wire the autonomous agenda to consult this file alongside the fitness assessment, so deferred items resurface on their own.

## Host-executed forge ergonomics
- **First-class host-forge flow.** `persist_forged_skill` exists; make the loop ergonomic (a documented step or a tool) so drafting, persisting, registering activity/tags in `index.yaml`, and committing is one smooth path. Auto-derive or prompt for activity and tags on registration.

## Skill and canon refinements
- **context_firewall: sibling-project clause.** It covers canon-poisoning but not project-to-project poisoning. Encode the active re-earning firewall: prior material enters only by re-derivation, and names are earned once the development produces what they denote.
- **Author-layer accretion mechanism.** The author node was hand-placed. Give the dreamer a distinct global/author target, with cross-session recurrence gating so traits accrete slowly and are revised rather than frozen.
- **Backing-script health.** Refine-recommended: two evaluating skills report script ok-rate 0.0 and one reports a low verify pass-rate. Fix the backing scripts.

## Architectural note
The autonomous dreamer's generative step is host-executed - the most powerful model already in the loop, running locally - not an external API call. Deterministic curation (fitness assessment, lifecycle transitions) stays in-engine. The engine stands as its own object.
