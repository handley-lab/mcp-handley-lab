---
name: result_foundry
description: "[EXPERIMENTAL] Establish, state, and evidence a core result — the innermost ring of a manuscript — at an explicit status, with every claim routed to its derivation and numerical support and every gap named."
---
# result_foundry

**Status: [EXPERIMENTAL]**

A coarse craft skill for the **core** of a paper: the results themselves, before any narrative
or framing. It governs the results/spine ledger — the trunk-root. Start broad; sculpt finer as
the work teaches what a "result" should look like here.

## What a locked result is (the four faces)
A result is finished when it carries four faces, each serving a different reader and stage. The
heavy human derivation is *sublinked* so it stays out of the working context while the light,
high-value content travels. The sublinked derivation is the single source of truth — the statement
and machine map are views of it, and the `reconciler` propagates on change.

1. **Statement** — the claim in one precise sentence, in fixed vocabulary, carrying its **status**
   (*established* / *partial-under-a-stated-restriction* / *open-gap*; a verification verdict, never
   an assertion — if you cannot say which, it is *open-gap*) and its **dependencies** (which earlier
   results it rests on, so propagation can find it).
2. **Pedagogical derivation** — the full human-facing argument, *sublinked* out of the working set,
   read only to verify or to draft an appendix.
3. **Machine map** — a compact reconstruction certificate: the assumptions used, the techniques
   employed, a terse recipe to reach the result, and the *verdict of actually running the check*. A
   result whose checker does not run is not "settled"; the checker's failure is recorded against it.
4. **Contextual scaffolding** (bounded; speculative leads drain to the backlog) — what motivates the
   assumptions, where the result sits in the literature and what it does there, the observed
   phenomena it explains, and what it licences (which later results it unlocks). These fields are the
   rhetorical moves of a paper pre-written, so the results ledger doubles as **pre-assembled
   narrative** feeding the spine and the eventual draft.

## Principles (the McCaul core)
- **Derive, do not assert.** Cut every sentence that is a position rather than a result. A naked
  claim with no derivation pointer and no number is not a result; it is a placeholder.
- **State the scope, then the claim.** The strongest version of a result is the one that says
  plainly what it does *not* cover. Scoping is not hedging — dropping the scope to sound more
  confident is the most common regression. (Hard-won: a later draft that deleted the "this does
  not establish X" boundary and the claim-provenance tags read as *more* confident and was
  *worse*; the careful earlier draft was the better one.)
- **Name the gap in the ledger, not in a footnote you'll forget.** Every restriction and every
  not-yet-analytic step is a first-class ledger entry and a candidate to kick back to the Foundry.
- **Verify before you lock.** Run the check. Confirm the headline number independently if you can.
  Disagreement between the asserted status and what you observe re-opens the result.
- **The core holds no framing.** No narrative, no thematic identity, no rhetorical arc here —
  those belong to outer rings. Keeping them out is what makes the core reusable under any framing.

## Usage
When establishing or revising a core result:
1. Write the one-sentence statement in locked vocabulary (from the glossary ledger).
2. Assign and *justify* the status; run the supporting check and record its verdict.
3. Route derivation + numerics + figure; record dependencies.
4. List any restriction as a named gap. If a gap blocks the claim, the status is not "established".
5. On the author's sign-off, hand to the `reconciler`.

*Experimental and coarse by design. Refine in-session whenever the author's edits reveal a
sharper standard for what a result must carry.*
