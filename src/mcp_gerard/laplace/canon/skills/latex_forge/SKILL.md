---
name: latex_forge
description: The mechanical proofing engine. Use this skill to structurally lint and compile LaTeX manuscripts to enforce the McCaul aesthetics (British English, no AI slop, Nature-Style TikZ) before presenting drafts.
---

# The LaTeX Forge [EXPERIMENTAL]

This skill enforces the mechanical axioms of the McCaul Protocol. It acts as a pre-compilation sieve to ensure no textual slop or amateur visual styling survives to the Principal Investigator's desk.

## Usage

When you finish a major rewrite of a `.tex` file, you must run the linting engine:

```
laplace_run(skill="latex_forge", target="<path_to_tex_file>")                  # report only
laplace_run(skill="latex_forge", target="<path_to_tex_file>", args=["--auto-fix"])
```

Or, for a fast structured pass/fail you can act on directly, `laplace_verify(target="<path>", checks=["voice"])`.

The engine runs the backing `scripts/build_and_lint.py`, which outputs a Markdown review of the file, flagging:
1. **Americanisms** (e.g., parameterize -> parametrise).
2. **AI Slop** (e.g., "delve", "testament", "tapestry", forced parallelisms).
3. **TikZ Violations** (e.g., raw `red` or `blue` instead of `blue!80!black` or custom muted colors).
4. **TikZ Keyword Collisions** (e.g., using `output` as a style or node name, which is a reserved keyword in the TikZ `positioning` library and causes severe compilation crashes. Use `finalnode` instead).
5. **Layout Distortions** (e.g., using `\linewidth` for single-column figures inside full-page `\begin{figure*}` environments).
6. **Variable Inconsistencies** (e.g., default `x` or `z` labels in TikZ instead of manuscript variables like `\mathcal{M}` or `\theta`).

## Protocol
Do not fail the compilation aggressively. The engine will flag concerns "at a glance." You are expected to read the generated flags and address any structural failures before presenting the final PDF to the PI.

## Compilation 

**CRITICAL RULE:** Never compile manuscripts using raw `latexmk`, `pdflatex`, or `bibtex` commands in the terminal. You must **STRICTLY** default to the Forge Compiler to eliminate manual friction and enforce standard compilation loops.

The Forge Compiler is the auxiliary `scripts/compile_pdf.py` in this skill (resolve its directory via `laplace_skill("latex_forge").backing_path`). Run it with Python through the shell - on Windows, wrap it in the `shell_mechanic` safe executor to avoid UTF-16 and pathing friction:

```powershell
powershell -ExecutionPolicy Bypass -File <shell_mechanic>/scripts/Invoke-SafePython.ps1 -ScriptPath "<latex_forge>/scripts/compile_pdf.py" -ScriptArgs "<path_to_tex_file>"
```
This single command automates the `pdflatex -> bibtex -> pdflatex -> pdflatex` chain and suppresses standard output unless an error occurs.

### Global Orchestration

If you are coordinating multiple subagents or require the entire SGO to be compiled simultaneously, use the Orchestration Compiler (`scripts/compile_orchestra.py`). It recursively finds all `main.tex` files in a target directory and compiles them concurrently:

```powershell
powershell -ExecutionPolicy Bypass -File <shell_mechanic>/scripts/Invoke-SafePython.ps1 -ScriptPath "<latex_forge>/scripts/compile_orchestra.py" -ScriptArgs "<target_directory>"
```
