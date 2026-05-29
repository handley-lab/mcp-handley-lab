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
**Literature:** <prior work that grounds or contextualises it>
**Numerical:** <the function/figure that demonstrates it>
**Status:** <Proved / Supported / gap: ... / conjecture / assumed>
```

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
