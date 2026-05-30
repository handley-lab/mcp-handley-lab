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

## Backing
No deterministic script yet. The mechanical graph-walk (given declared dependencies, list
candidate-affected elements) is a natural future backing script; the *semantic* classification
stays judgement.
