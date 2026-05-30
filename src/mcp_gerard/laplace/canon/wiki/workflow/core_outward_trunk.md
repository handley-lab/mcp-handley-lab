# Core-Outward Trunk (stage-separated drafting)

A manuscript is not drafted front-to-back from frozen inputs. It is grown **outward from a
verified core**, in stages that can be re-entered, with each element worked in an isolated
context. This node defines the workflow; `reconciler` defines how a finished element propagates.

## The three stages

1. **Foundry** — perfect the *argument*, the *evidence/numerics*, and the *figures* first, and
   iterate until they are confident. The Foundry is re-enterable: later work may kick a question
   back down into it.
2. **Spine** — establish the *narrative spine and thematic identity*: the global frame that
   constrains every element below it. Pin this before drafting any outward prose.
3. **Trunk** — only now draft the manuscript, **element by element, core-outward**.

## Core-outward order

Build from the centre of gravity to the edges:

```
core results → narrative spine / identity → technical assets → technical sections
            → conclusion → introduction → abstract
```

The framing rings (conclusion, introduction, abstract) are drafted **last**, because they
summarise commitments that only exist once the inner rings are settled. Drafting the abstract
first — the usual default — forces premature commitment and invites drift.

## The ledger bus (how coherence survives isolation)

Elements never load each other's raw text. They load only a small set of authoritative,
curated **ledgers**: a results/spine ledger (what is true), an evidence ledger (provenance),
and an identity/glossary ledger (terminology + framing). The ledgers are the propagation
medium: a local edit updates a ledger — small and distilled — and every future context sees the
new truth automatically. What travels between elements is the *commitment*, never the prose.

## The clean-context firewall

Each element is worked with the minimum that element needs: the element itself, its immediate
neighbours, the governing craft skill, the relevant axiom, the ledgers, and the evidence it
cites. **Never** the whole manuscript or the prior conversation. Isolation is the anti-poisoning
mechanism; the ledger bus is what stops isolation from becoming incoherence.

## The session loop

`orient` (load the handoff brief + the ledgers + the governing skill) → work one element with
the author until they are happy → **commit** (the author's sign-off is the trigger) →
`reconciler` propagates → choose the next element from the queue. The loop breathes
Foundry ⇄ Spine ⇄ Trunk and global ⇄ local without ever holding the whole work in one context.

## Status discipline

Results carry an explicit status — established / partial-under-a-restriction / open-gap — and
gaps are *named*, never smoothed. "Settled" is a verification verdict, not an assertion. A
finished element is one whose every claim traces to the ledger at a known status.
