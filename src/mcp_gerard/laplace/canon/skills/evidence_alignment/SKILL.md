---
name: evidence_alignment
description: "[EXPERIMENTAL] The key high-level skill: recognise what the evidence base actually supports in relation to the paper's goals. Produces a support map and a ranked list of gaps to close."
---

# Evidence Alignment [EXPERIMENTAL]

The hardest judgement in drafting is not writing - it is recognising the distance
between what you want to claim (the goal) and what the evidence will bear. This
skill makes that distance explicit. It sits at the hinge of the loop: it informs
**orient** (what do we already know that serves this goal?) and it gates
**verify** (does the draft claim only what the ledger supports?).

## What it does

Given the goals and the evidence ledger, it classifies every relevant claim into
a support tier and reports the gaps:

- **strong** - affirmative status, with both literature and numerical support.
- **partial** - supported but thin: a missing pillar, or a soft status.
- **weak** - a declared gap, a conjecture, or an unbacked assertion.

For each goal it reports coverage (how much is strong), the partial/weak claims
that must be shored up, and - crucially - **goals with no matching claim at all**,
which are the prompts for `literature_scout` to extend the evidence base to need.

## Usage

```
laplace_run(skill="evidence_alignment", target="<path_to_evidence_ledger.md>",
            args=["--goals", "hierarchy depth, stability threshold, cost of control"])
```

This executes the backing `scripts/align_evidence.py`, printing a support map and
writing `support_map.md` beside the ledger. Omit `--goals` to tier the whole
ledger.

## Protocol
Run this at the **start** of a drafting pass (to know what you can honestly argue)
and again before **verify** (to confirm the draft over-claims nothing). Close
strong > partial > weak in priority order: derive or compute the partials, scout
literature for the uncovered goals, and soften or cut any claim that stays weak.
The paper's reach should equal its support - no more, no less.
