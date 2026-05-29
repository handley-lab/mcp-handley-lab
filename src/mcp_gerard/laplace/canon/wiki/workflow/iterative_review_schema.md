# Iterative Review Schema (The Critical Generative Regime)

To break free of single-shot LLM fragility, Laplace operates under strict, compartmentalized review loops.

* **Mandatory Minimum 2-Pass Independent Review**: An output (whether core text, figures, or code) is not complete until it has been:
  1. **Conceptualized**: High-level design mapped against the axioms.
  2. **Executed**: The raw output generated.
  3. **Hostilely Reviewed**: Evaluated by a distinct agent context (e.g., The Formalist, The Architect) designed explicitly to hunt for flaws.
  4. **Iterated**: Flaws are fixed before final presentation to the PI.
* **Anti-Context Dropping**: Never conceptualize, code, and review in a single context window. Spawn explicit subagent roles for the review phase.
