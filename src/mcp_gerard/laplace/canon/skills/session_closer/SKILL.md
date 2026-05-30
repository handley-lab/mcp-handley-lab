---
name: session_closer
description: "[EXPERIMENTAL] The single named protocol for closing a working session. Run once, by the session-closer only, never mid-ladder — settle and commit, log every skill used, assess, dream, reconcile the brief, sync external state — in that fixed order, so session evidence compounds into canon fitness instead of evaporating."
---
# session_closer

**Status: [EXPERIMENTAL]**

> **Earned name: Sawbones.** The index keeps `session_closer` for discovery, but the protocol earned a bedside name the session it was forged. The close is the suture - run once, at the end, by the hand putting the work down, so the session does not bleed out. Nothing dropped, nothing stale, no evidence left to evaporate on the floor. A name earned at the end, exactly as the canon asks names to be earned.

## Purpose
A session ends the same way every time, and yet the close was reconstructed from first principles
each time it happened. An ad hoc close drops steps, and the most damaging dropped step is per-skill
logging. When logging is skipped the fitness loop is starved at the source — skills that settle real
results read `usage 0`, the promotion gate never moves, and a dream over that state is a curation
no-op. The `session_closer` makes the close a single named protocol any model in the loop follows
identically, so the engine's central premise — evidence compounds automatically — actually closes.

This skill is the host-facing operational counterpart to the END-OF-SESSION ROUTINE in
`canon://agents/the_dreamer.yaml`. The persona states the dreamer's internal mandate. This skill is
what the session-closer runs.

## Who runs it, and when
- **The session-closer only.** The closer is whoever is wrapping the session — the orchestrator or
  principal, not a result-worker in the middle of a ladder.
- **Once, at the close.** Never mid-task. A worker who fires the close from inside an active result
  pollutes telemetry and, observed across models, has leaked an external API call the engine never
  makes by design. If the work is not being put down, this skill does not run.

## The pass (in fixed order)
1. **Settle and commit.** Stage only the finished artifacts of the element being closed and make one
   scoped commit. Follow the project's existing commit convention rather than inventing one.
2. **Log every skill used — before the dream.** For each skill whose protocol was actually followed
   this session, call `laplace_log` with an honest signal: +1 if following the protocol produced a
   result that passed verify, -1 if the protocol caused friction. Tie each signal to the concrete
   artifact it produced. This step is non-optional and comes before the dream, so the dream has
   evidence to act on rather than an empty window.
3. **Assess.** Call `laplace_assess`. Read the transitions, the refine candidates, and the unused
   list. This is the picture the dream will act on — confirm it reflects the session before dreaming.
4. **Dream.** Call `laplace_dream`. Apply deterministic curation. Forge only against friction that
   genuinely recurred this session. Any forge brief returned is `host_forge` — execute it inline and
   locally, drafting the `SKILL.md` directly. Never delegate a forge brief to an external API.
5. **Reconcile the brief.** Run the `reconciler` pass on the active project: classify what changed
   (lateral / downward / upward), apply lateral changes to the ledgers, queue structural follow-ons,
   and rewrite the active project's `HANDOFF.md` last.
6. **Sync external state.** Bring any out-of-canon record current — auto-memory, project index,
   dashboards — so the stale-context problem does not reappear from a source the canon does not own.
   This includes the **canon project node** (`canon://domains/.../projects/<project>`): it must hold
   only durable facts (thesis, scope, root, supersession) and **delegate per-result status to the
   project's `HANDOFF.md`** rather than restate it. A project node that copies the result ladder is a
   second source of truth, and the copy freezes the session it is written — confirm the node still
   points to the handoff rather than naming a specific active result.

## Invariants
- **Logging is non-optional and precedes the dream.** A close that dreams before logging dreams over
  nothing. If telemetry was not emitted, the close is incomplete.
- **The closer closes.** A result-worker mid-ladder does not run this. Role boundary before sequence.
- **Forge briefs execute inline.** The engine is self-contained and makes no external LLM call. The
  host drafts and persists. No exceptions.
- **The brief is reconciled last, every time** — consistent with `reconciler`. The observer is inside
  the box, so the starting context for the next session is the final thing brought current.
- **Honest signals only.** A +1 is earned by a passing result, not handed out to flatter the ledger.

## Backing
No deterministic script yet. A natural future backing script is a close-out verifier: given the
session's tool-call log, confirm each used skill received a `laplace_log` event and the handoff brief
was touched after the last result commit, and emit a PASS/FAIL on close completeness. The *judgement*
— which skills were genuinely used, what signal each earned — stays with the closer.
