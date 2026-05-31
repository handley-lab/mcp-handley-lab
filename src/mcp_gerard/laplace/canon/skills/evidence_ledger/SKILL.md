---
name: evidence_ledger
description: "[EXPERIMENTAL] The standardised evidence scheme. Every claim is a CLM record carrying its derivation, literature, numerical support, and status, so support is tracked, auditable, and extensible during drafting."
---

# The Evidence Ledger [EXPERIMENTAL]

A manuscript is only as honest as its evidence base. This skill defines the
standardised scheme in which every load-bearing claim is recorded with its
support, and provides a completeness check so no claim reaches the page unbacked.

This is the umbrella ledger. The `epistemic_ledger` maps derivation structure and
the `empirical_ledger` verifies numerical truth - the evidence ledger binds claim,
derivation, literature, and numerics into one auditable record per claim.

## The record format

One record per load-bearing claim, tagged `<PROJECT>-CLM-NNN`:

```markdown
## EPT-CLM-007: Self-similar hierarchy multiplies N_c by (pi/2) per layer
**Claim:** <the precise statement, with the operative equation>
**Derivation:** <where it is derived, or the proof sketch; cite the spine step>
**Literature:** established_by [citekeys] / contested_by [citekeys] / context: <one sentence> / novelty: <one sentence>
**Numerical:** <the function/figure that demonstrates it>
**Status:** <Proved / Supported / gap: ... / conjecture / assumed>
```

## The Literature face is a query, not prose
A record's `Literature` field is not re-written prior-work prose. It is a query into the shared
`corpus_librarian` store - `established_by` and `contested_by` carry citekeys, plus one context
sentence and one novelty sentence local to this claim. The reference text lives once in `corpus.bib`
and is audited once. `established_by` resolves only to records the corpus marks `status: established` -
provisional, borrowed, and unverified sources may appear as context but never as settled support.
Fix a corpus record and every citing face is correct without reopening a single face.

## Status is computed, not asserted
A claim's `Status` is earned, never stamped. It is affirmative (`Proved` / `Supported` / `Established`)
only when its check has run green against the *current* derivation - the `reconciler`'s
header-hash. The moment the derivation's committed content changes, the record is stale until
re-checked, and a stale record reads as not-yet-earned to the completeness check below. This is the
two-tier trust of the corpus carried into the ledger: a claim is usable while provisional, but it
carries settled weight only once the evidence chain is green. Trust is a function of the chain, not
a declaration over it.

The scheme is not static. During drafting you **extend the ledger to need**: when
an argument leans on a claim that is not yet recorded, add the record and resolve
its support (derive it, find the literature via `literature_scout`, or run the
numerics) before the claim is allowed to carry weight.

## Usage

Check structural completeness and surface weak records:

```
laplace_run(skill="evidence_ledger", target="<path_to_evidence_ledger.md>")
```

This executes the backing `scripts/check_ledger.py`, which flags any record
missing a field, and any record whose `Status` is not an affirmative
(proved / supported / established) or whose literature or numerical support is
absent or a placeholder.

## Protocol
A claim with a missing field, a placeholder, or a non-affirmative status is **not
yet earned**. Resolve it - derive, cite, or compute - or soften the claim in the
manuscript to what the evidence actually supports. Run `evidence_alignment` to see
those records in relation to the paper's goals.
