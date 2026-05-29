---
name: structural_mechanic
description: "[EXPERIMENTAL] Automates 'Pedagogical Segregation' and structural banishments. Migrates pedagogical math and derivations from the main text to appendices, replacing them with crisp citations."
---

# The Structural Mechanic [EXPERIMENTAL]

**Status: [EXPERIMENTAL]**

## Purpose
The Architect demands that the main text be a relentless, high-stakes structural argument. Heavy mathematical derivations and pedagogical step-by-step proofs must be banished to the appendices. The `structural_mechanic` automates this migration, eliminating the operational friction of manually cutting, pasting, and patching `.tex` files.

## Scripts

### `banish_to_appendix.py`
Located in `scripts/banish_to_appendix.py`. This script extracts a specific line range from a source `.tex` file, appends it to a target appendix `.tex` file, and replaces the extracted block in the source file with a concise reference string.

**Usage** (a flags-only script, so pass everything via `args`):
```
laplace_run(skill="structural_mechanic", args=[
  "--source", "path/to/main_section.tex",
  "--start", "<StartLine>", "--end", "<EndLine>",
  "--target", "path/to/appendix.tex",
  "--ref", "\\emph{See Appendix \\ref{app:derivation} for the full step-by-step derivation.}",
])
```

## Protocol
1. Wait for The Architect to flag pedagogical bloat.
2. Ensure The Architect provides the exact `StartLine` and `EndLine` of the offending block.
3. Run `banish_to_appendix.py` (via `laplace_run`) to seamlessly migrate the block.
4. Run `laplace_verify(target=..., checks=["crossref"])` and recompile via `latex_forge` to confirm the structural flow and references remain unbroken.
