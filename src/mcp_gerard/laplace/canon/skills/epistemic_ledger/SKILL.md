---
name: epistemic_ledger
description: Computationally verifies the 'Derive, Do Not Assert' axiom by parsing the LaTeX AST and generating a Mermaid dependency graph of the logical flow.
---

# The Epistemic Ledger

This skill reads a LaTeX manuscript and outputs a structural map of its logic, flagging unbacked claims or orphaned equations.

## Usage

Run it through the engine:

```
laplace_run(skill="epistemic_ledger", target="<path_to_tex_file>")
```

This executes the backing `scripts/map_derivations.py`, parses `\label{eq:...}` and `\ref{eq:...}` tags, and writes an `epistemic_graph.md` beside the target file. For a fast structured pass/fail without the artifact, use `laplace_verify(target="<path>", checks=["epistemic"])`.

## Protocol
Open the generated `epistemic_graph.md`, or read the `laplace_verify` report. Any disconnected nodes in the Mermaid diagram represent a structural failure in the argument. You must resolve these breaks - by deriving the missing link - before submitting the manuscript.
