---
name: global_weaver
description: Automates cross-referencing and label synchronisation across the entire Synthetics Grand Orchestra of manuscripts. 
---

# Global Weaver

The synthetics project requires multiple parallel manuscripts (*Law of Laws*, *Wigner's Many Friends*, *Cost of Complexity*, *Variational Wrong Object*) to reference each other continuously. 
To eliminate the manual friction of checking whether a referenced equation or section exists in another manuscript, use the Global Weaver.

## Usage

```
laplace_run(skill="global_weaver", target="<target_directory>")
```

This executes the backing `scripts/weave_orchestra.py` and writes a `cross_reference_report.md` artifact. For a fast structured pass/fail, use `laplace_verify(target="<target_directory>", checks=["crossref"])`.

The script will recursively scan the given directory for `.tex` files. It will:
1. Build a global registry of all exported `\label{...}` across all manuscripts.
2. Check every `\ref{...}` and `\cite{...}` in every manuscript against this global registry.
3. Output a `cross_reference_report.md` artifact detailing any broken references, missing labels, or orphaned cross-links.

## Protocol
Run this skill whenever a new section or major derivation is integrated that impacts other manuscripts. Address all flagged breaks before marking the orchestration phase complete.
