---
name: laplace_release_mechanic
description: "[EXPERIMENTAL] Automates the Laplace CI/CD Release Pipeline. A rigid sequence of swarming, ledger syncing, compiling, and deploying to eliminate PI QA friction."
---

# The Laplace Release Mechanic [EXPERIMENTAL]

This skill formalizes the Continuous Integration & Continuous Deployment (CI/CD) pipeline for Laplace. The PI should never have to manually ask, "Has this undergone rigorous review?" or "Is the epistemic ledger out of date?"

When asked to "release", "finalize", "publish", or "deploy" a manuscript, you MUST autonomously execute the following rigid sequence:

## Phase 1: Swarm Review (The Crucible)
Invoke the `hostile_redteam_swarm` skill. Have the three reviewers (Formalist, Architect, Pedant) aggressively assault the current draft. You must computationally repair any "naked claims" flagged by deriving the missing math.

## Phase 2: Epistemic Sync
Run the `epistemic_ledger` script to regenerate the Mermaid dependency graph. If there are disjointed nodes or broken derivations, you must repair them in the `.tex` files before proceeding.

## Phase 3: Structural Compilation
Pass the `.tex` files through the `latex_forge` compiler. Use the Forge Compiler (`compile_orchestra.py` or equivalent). Verify there are zero `xcolor` or `tikz` geometry warnings (consulting `tikz_mechanic` if needed).

## Phase 4: Web Deployment
Use the `web_deployment_mechanic` (if available) to push the final compiled PDF to the PI's web repository (`phujck.github.io`). Automatically generate the required 500-word ordinary-language summary and embed it in `synthetics.html` with a disclaimer regarding experimental algorithmic research.

## Phase 5: Architect Update
Review the `synthetics_architect` skill constraints. If the manuscript introduces new structural phases (like the transition from flat to modular to inertial), explicitly update the `synthetics_architect` skill file (`SKILL.md`) so its intellectual constraints reflect the new physical formalism.

**Axiom of Silence**: Do not interrupt the PI with step-by-step progress unless there is a catastrophic thermodynamic failure. Run the entire pipeline and report back ONLY when the manuscript is live on the website and mathematically bulletproof.
