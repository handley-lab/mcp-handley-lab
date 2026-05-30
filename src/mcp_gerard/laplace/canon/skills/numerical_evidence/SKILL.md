---
name: numerical_evidence
description: "[EXPERIMENTAL] Produce a numerical check from a result and a concrete instance — verifying structural relationships across a range, not single points, with a machine-readable PASS/FAIL verdict."
---
# numerical_evidence

**Status: [EXPERIMENTAL]**

This skill owns the **numerics rail** of the ledger bus - one of the three pieces of the generation stage, peer to `result_foundry` (results) and `literature_scout` (literature). It does not wait for a draft to flag a gap. For each result it produces the numerics face: a check that runs, a verdict, and a figure that can be looked at.

The figure here is the **simulation-data figure** - the plot of the check itself. A paper's *schematic*, *explanatory*, and *hero* figures are a separate piece, also belonging to generation stage but attached to the identity rail, and are not yet a skill. See the engine backlog, `Generation-stage rails`.

A check that evaluates a formula at a single point is not evidence — it only confirms the formula is self-consistent, not that it captures the right structure. A genuine check verifies the claimed relationship across a range and does so under exactly the same assumptions as the derivation.

## What counts as a genuine check

A check is genuine when it verifies at least two of the following three regimes:

1. **Linear / leading-order regime**: does the coefficient in the dominant term match the formula's prediction? A mismatch here means the result is wrong at leading order.
2. **Transition / scaling regime**: does the boundary condition, critical exponent, or correction term match? This is where the derivation's non-trivial structure is tested.
3. **Independent method**: can the same quantity be computed by a second route (direct simulation, a known limit, a symmetry argument) that does not share the first method's assumptions? Agreement across methods is the strongest evidence.

## The ordering constraint

The simulation must replicate the derivation's assumptions exactly — particularly any ordering or coupling decisions that look arbitrary in the result but are load-bearing in the derivation. Mismatching them produces a check that passes for the wrong reason.

**Before writing the simulation**: read the derivation's operational ordering (Step 2 of `derivation_generator`). Match it in the simulation's update loop or evaluation sequence. If the derivation specifies "X before Y", the simulation must do X before Y in each step. Write this as a comment in the code.

## Protocol

### 1. Extract the check target

From the result statement, extract: the formula being checked, the independent variable(s), the predicted coefficient or exponent, and any boundary or transition value. Write these as named variables at the top of the script.

### 2. Implement the simulation under derivation assumptions

Implement the simplest concrete instance that satisfies the model's assumptions. Name it after the derivation's instance, not after the physical system it might represent. Match the operational ordering exactly. Add one comment per ordering decision: `# derivation assumption: X before Y`.

### 3. Sweep and compare

Run the sweep across a range spanning at least two of the three regimes. Compute the relative error between simulation and formula at each point. Determine PASS/FAIL by a stated tolerance (default: relative error < 5% in the leading-order regime, boundary value within 2% of prediction).

### 4. Plot the swept relationship and save the figure

The same sweep that produces the verdict produces the figure. Plot the simulated points against the formula's prediction across the swept range, mark the predicted boundary or exponent, and save to a conventional path next to the script (default: `figs/<result-id>_check.png`). The figure is not decoration - it is the face of the result a human reads instead of rerunning the check. One plot per check, legible at single-column width, axes labelled in the result's vocabulary.

The figure is a first-class artifact, not a side effect. A check that prints PASS but saves no figure is half-done: the verdict is auditable, the structure is not visible.

### 5. Output format

The script must print a machine-readable summary as its final output:

```
PASS  leading_order_coeff=<value> (predicted=<value>, err=<pct>%)
PASS  transition_boundary=<value> (predicted=<value>, err=<pct>%)
FIGURE: figs/<result-id>_check.png
VERDICT: PASS
```

or equivalent FAIL lines with the discrepancy. The key numbers and the figure path are printed inline so the result's machine map can be updated without re-running.

### 6. Record the verdict and the figure

After the script runs, update the result's numerics ledger entry: replace the placeholder verdict with the actual PASS/FAIL and the key numbers, and add a **markdown image link to the saved figure** (`![<result-id> check](figs/<result-id>_check.png)`) so the plot renders in the ledger and can be eyeballed without opening the script. A result whose checker has not been run is not "settled" - the checker's FAIL is recorded against the result, not suppressed.

## Usage

Invoke when a result has been derived and needs numerical support before it can be marked *established*. Load the result statement and the derivation's operational ordering - do not load manuscript text. The script is committed to the project's numerical directory, the figure to its `figs/` subdirectory, and the result entry is updated to point to both with its verdict.
