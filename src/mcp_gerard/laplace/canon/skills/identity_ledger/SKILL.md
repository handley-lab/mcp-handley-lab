---
name: identity_ledger
description: "[EXPERIMENTAL] Guards a manuscript's narrative identity. Tracks the load-bearing coined terms, framings, and motifs that make the paper itself, and flags a draft that has drifted away from them."
---

# The Identity Ledger [EXPERIMENTAL]

Rigour is necessary but not sufficient. A draft can be flawlessly grounded in the
evidence and still lose the paper - its coined name for the central phenomenon,
its signature cross-domain framing, the thesis that makes it memorable. An
evidence-driven pass optimises for what is *supported*. This skill protects what is
*the paper*.

It was forged in response to a measured failure: a fully evidence-grounded redraft
of *The Phases of Hierarchy* scored higher on rigour yet dropped the "ultraepistemic
catastrophe" name and the Transformer mapping - the work's branded identity. The
evidence workflow had no signal that rewarded keeping them. This ledger is that
signal.

## The record format

A per-project manifest (e.g. `inputs/identity_ledger.md`), one record per
load-bearing identity element, tagged `ID-NNN`:

```markdown
## ID-001: Ultraepistemic Catastrophe (UEC)
**Kind:** coined-term
**Forms:** ultraepistemic catastrophe, UEC
**Role:** names the core failure mode; belongs in the abstract and introduction.
**Status:** load-bearing
```

- **Kind:** coined-term | framing | motif | thesis
- **Forms:** the surface strings to detect (the term and its aliases/acronyms)
- **Role:** what the element does and where it must appear
- **Status:** load-bearing (must survive any draft) | optional (preferred)

The ledger is not a style cage. It is the short list of things that, if a draft
lacks them, the draft is no longer *this* paper.

## Usage

Check a draft for identity drift:

```
laplace_run(skill="identity_ledger", target="<path_to_draft.tex>",
            args=["--manifest", "<path_to_identity_ledger.md>"])
```

This executes the backing `scripts/check_identity.py`, which reports each element
as present or missing, separating load-bearing from optional. A draft missing any
load-bearing element has drifted.

## Protocol
Run this alongside `evidence_alignment` - the two are complementary poles of the
loop. Alignment stops the draft over-claiming beyond the evidence; the identity
ledger stops it under-claiming its own identity into blandness. Restore any missing
load-bearing element before presenting the draft. If you deliberately retire one,
remove its record - do not let the ledger lie.
