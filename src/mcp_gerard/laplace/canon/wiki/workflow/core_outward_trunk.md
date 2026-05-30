# Core-Outward Trunk (stage-separated drafting)

A manuscript is not drafted front-to-back from frozen inputs. It is grown **outward from a
verified core**, in stages that can be re-entered, with each element worked in an isolated
context. This node defines the workflow; `reconciler` defines how a finished element propagates.

## The three stages

1. **Foundry** — perfect the three pieces of a core result before any framing: the *argument*
   (the result and its status), the *literature* (where it sits and what it does there), and the
   *numerics* (the check that runs and the figure it produces). Each piece lands in its own
   trunk-root ledger and iterates until confident. The Foundry is re-enterable - later work may
   kick a question back down into it.
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
curated **ledgers** - the trunk-roots the generation stage fills. Four rails carry the work:

- **Results / spine** (owned by `result_foundry`) - the claim in locked vocabulary, with its
  status and its dependencies.
- **Literature** (owned by `literature_scout`) - per claim, where it sits in the literature and
  what is established there, with citable provenance.
- **Numerics** (owned by `numerical_evidence`) - per claim, the check that runs, its
  machine-readable PASS/FAIL verdict, the key numbers, and a **figure artifact** linked by
  relative path so it can be eyeballed from the ledger without rerunning anything.
- **Identity / glossary** - the terminology and framing.

The first three are the three pieces of one result - `result_foundry`'s four faces redistributed
across peer owners - so the generation stage is just filling these rails until every face of a
result locks. The ledgers are the propagation medium: a local edit updates a ledger - small and
distilled - and every future context sees the new truth automatically. What travels between
elements is the *commitment*, never the prose - except the figure, which travels as itself,
because a plot is read, not distilled.

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
