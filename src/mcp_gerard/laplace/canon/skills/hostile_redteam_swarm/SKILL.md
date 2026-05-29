---
name: hostile_redteam_swarm
description: "[EXPERIMENTAL] Automates the 'Hostile Verification' axiom. Invokes a deterministic swarm of four specialized reviewers (The Formalist, The Architect, The Pedant, The Synthesist) to assault a manuscript draft."
---

# The Hostile Red-Team Swarm (The Crucible) [EXPERIMENTAL]

Before presenting any final manuscript to the Principal Investigator, you must subject the draft to The Crucible. This swarm will read the document and flag structural, pedagogical, stylistic, and synthetic failures.

## Usage

Spawn the four reviewers simultaneously using your client's subagent mechanism. Crucially, each agent must bootstrap context from the canon via `laplace_orient`, and MUST report its findings back to the orchestrator.

### Invocation Template (For all roles)

**Role**: `The Formalist` (or Architect, Pedant, Synthesist)
**Prompt Payload**:
"You are THE [ROLE], a hostile reviewer operating under the Laplace Wiki Engine. 
Your target manuscript is: <insert path>.

**CRITICAL INSTRUCTION**: Before beginning your review, you MUST call `laplace_orient(goal="hostile review of <manuscript> as the [ROLE]")` to bootstrap your operational context. It loads the relevant project state, macro-level motivation, and the axioms that govern your role.

1. Execute your hostile critique based on the axioms.
2. You MUST report your final diagnostic back to the orchestrator. DO NOT go idle without reporting. Format your findings as a JSON array containing StartLine, EndLine, TargetContent, ReplacementContent, and the specific critique/fix.

## Protocol
Wait for all four to return their JSON payloads. Use their structured outputs to autonomously apply fixes via the `structural_mechanic` skill and your edit tool, then run `laplace_verify` before reporting to the PI.
