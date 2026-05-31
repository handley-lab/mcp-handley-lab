---
name: reconciler
description: "[EXPERIMENTAL] On an author's sign-off, propagate a finished element's change through the work — lateral changes eagerly into the ledgers, structural changes into a dependency-ordered queue — and rewrite the handoff brief last."
---
# reconciler

**Status: [EXPERIMENTAL]**

## Purpose
A clean-context firewall keeps each element isolated, but real edits have consequences for
other elements. The `reconciler` is the mechanism that propagates a *committed* change through
the structure **without** reopening everything in one poisoned context. It is invoked when the
author signs off on an element ("I'm happy with this") — that sign-off is the trigger.

## What it is given (and only this)
The reconciler is a **dedicated, isolated pass** (its own subagent / context). It receives:
1. **what it is doing** — that it is reconciling one committed element;
2. **the project state** — the compact ledgers (results/spine, evidence, identity/glossary) and
   the handoff brief; *not* the full text of every element;
3. **the delta + its rationale** — what changed about the element and why.

It reasons over `{delta + dependency graph + ledgers}` only, so it cannot itself become a
poisoning vector. The dependency graph is read from the elements' declared dependencies.

## The pass (in order)
1. **Classify the delta** into one or more of:
   - **lateral** — terminology / identity / a shared definition;
   - **downward** — a commitment that constrains elements further out (refine them);
   - **upward** — the element revealed a *need from an earlier stage* (kick back to the Foundry:
     more theory, evidence, or a figure).
2. **Apply lateral changes eagerly** — write them straight into the glossary/identity ledger.
   Because every future context loads that ledger, the change is everywhere at once; no element
   is reopened to absorb a rename.
3. **Queue structural changes** — emit a **dependency-ordered** reconciliation list. Each item
   names the affected element, the reason, and its tag (downward-refinement /
   upward-foundry-kickback / lateral-followup). Each item is later worked in *its own* clean
   context. The reconciler routes; it does not flood.
4. **Capture the craft lesson** — if the sign-off taught something about *how* this kind of
   element should be made, write it immediately into the governing craft skill (in-session
   capture), keeping it free of project specifics.
5. **Rewrite the handoff brief — last.** The brief is the outermost node in the very structure
   being reconciled: it is the prompt the next session (and the next reconciler) is spawned with.
   Bringing it current is therefore the final propagation step. This is what stops the starting
   context from ever being frozen — the observer is inside the box.

## Invariants
- **Never** widen the working context to "see everything." Distil, then propagate.
- **Lateral is eager, structural is queued.** Do not auto-rewrite distant elements; queue them.
- **Name gaps, don't smooth them.** An upward kickback is a first-class output, not a failure.
- **The brief is reconciled last, every time.** If the brief was not touched, the pass is
  incomplete.

## The staleness mechanism (how a change is detected, not just routed)
The classification above is judgement. Detecting *that* an element changed is mechanical, and the
mechanism must not cry wolf - a signal that fires on every typo trains the author to ignore it,
which is worse than no signal because it gives false confidence. Three rules hold the mechanism in
the valley:

1. **Hash machine-relevant content, not bytes.** Each element's source of truth (its derivation)
   carries a small structured header - assumptions, the stated result, the recipe. The reconciler
   hashes *that* normalised content, not the prose narrative. A prose-only edit - rewording,
   a fixed typo, a clearer sentence - never trips staleness. Only a change to what the element
   *commits to* does.
2. **Grade staleness by severity.** A dependent element carries one of two grades, never a flat flag:
   - **STALE-direct** - this element's own header changed. Its check must be re-run before it is
     trusted again.
   - **STALE-upstream** - a dependency's *consumed interface* changed (see below). Advisory: review
     whether the element still holds. Not a hard FAIL, and it does not block.
3. **Stale a dependent only when the interface it consumes changes.** "R3 depends on R2" rarely means
   "any edit to R2 invalidates R3" - R3 usually consumes only R2's *stated result*, not its proof.
   The dependency edge records what is consumed, and the reconciler hashes that slot alone. An edit
   to R2's proof that leaves its stated result intact never reaches R3. This is what stops one core
   edit from avalanching the whole ladder to STALE.

Status is computed from this, never asserted: an element is trusted (`PASS`) only after its check
runs green against the *current* header hash. The instant the header changes, it is `STALE-direct`
until re-checked. This is the same discipline as `derive, do not assert`, mechanised.

## Backing
`scripts/reconcile.py` - the now-forgeable graph-walk. Given the registry of elements, their declared
dependencies (and the consumed-interface tag per edge), and the stored header hashes, it recomputes
hashes, marks `STALE-direct` / `STALE-upstream` in dependency order, and re-runs checks for
direct-stale elements. It propagates and grades - it does not rewrite prose. The *semantic*
classification (lateral / downward / upward) and the handoff rewrite stay judgement.
