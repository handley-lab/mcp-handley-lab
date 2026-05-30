---
name: derivation_generator
description: "[EXPERIMENTAL] Generate a mathematical derivation from a result statement and its model assumptions — structural decisions first, algebra second, closure condition named as a labelled object."
---
# derivation_generator

**Status: [EXPERIMENTAL]**

The bottleneck in derivation work is not the algebra. It is the structural decisions made before any symbols are written. This skill encodes those decisions as a named, ordered scaffold that sits above the algebra, so the derivation is reviewable and reconstructable without re-doing the symbol-pushing.

## Protocol

### 1. State scope and reference point

Before writing any symbols, commit to two things in plain language:

- **Scope**: what the derivation establishes and what it does not. The strongest result is the one that states plainly what it does not cover.
- **Reference point**: the object being expanded around, the baseline state, or the fixed point relative to which perturbations are measured. Name it explicitly. If the reference point is not obvious, naming it *is* the first structural decision.

Write these in one or two declarative sentences. Do not start from the most general expression and narrow — start from the correct scope and reference point immediately.

### 2. Commit to the operational ordering

In any multi-step system, the order of operations is load-bearing. The wrong ordering produces spurious terms that must be cancelled by hand; the right one eliminates entire classes before expansion begins.

State the ordering explicitly as a numbered decision, and give the reason it is the right one. Form: **"We perform X before Y because Z."** If you cannot state the reason, the ordering is not yet committed — do not proceed.

### 3. Name the closure condition

Every non-trivial derivation goes through because of one algebraic fact that is not a mechanical step: a conservation law, a fixed-point condition, a symmetry identity, a self-consistency equation. Name it explicitly as a labelled object before writing the algebra that uses it. Form: **"[C]: ..."** where C is a short mnemonic. The closure condition is what allows simplification; leaving it implicit is what makes derivations hard to reconstruct.

### 4. Apply symmetry as a filter

Invoke any applicable symmetry, conservation law, or invariance to eliminate entire term classes *before* expanding. Symmetry is a pre-filter, not a post-hoc check on the final expression. State which terms vanish and why, in one sentence, before writing the remaining terms.

### 5. Write the algebra

With scope, reference point, operational ordering, closure condition, and symmetry filter established, write the algebra. It should now be three to five lines. If it is longer, a structural decision was not committed — stop and return to Step 2 or 3.

### 6. Output format

Produce a derivation file with the following structure:

```
## Scope
...

## Reference point
...

## Operational ordering
1. ...
   Reason: ...

## Closure condition
[C]: ...

## Symmetry filter
...

## Derivation
(algebra here)

## Result
(the result in locked vocabulary, with status tag)
```

The named structural steps are the derivation. The algebra is evidence they go through. The author reviews the steps; the algebra is routine once the steps are locked.

## Usage

Invoke when asked to derive a result from stated assumptions. Load the result statement and model assumptions first; do not expand the working context with prior derivations or manuscript text. If a closure condition is not identifiable at Step 3, flag it as an open gap and do not proceed to Step 5.
