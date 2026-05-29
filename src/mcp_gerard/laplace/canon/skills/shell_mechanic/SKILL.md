---
name: shell_mechanic
description: The execution engine. Resolves Python pathing friction and native PowerShell UTF-16 encoding errors by wrapping script execution in safe environments.
---

# Shell Mechanic [EXPERIMENTAL]

This skill acts as the environmental safety net for Laplace. During orchestration, terminal friction frequently arises from two core issues on Windows systems:
1. **Python Pathing Instability**: The `python` command may fail or not map to the correct executable, whereas `py` or `python3` might be required.
2. **UTF-16 Encoding Corruption**: Standard PowerShell redirects often output in UTF-16, which corrupts `.tex` AST parsing and triggers fatal build errors in `pdflatex` or `epistemic_ledger`.

## Usage

Instead of running bare Python scripts, wrap any high-risk file manipulations or complex compilations in the `Invoke-SafePython.ps1` wrapper.

### The Wrapper Script

Whenever you need to run a Python tool from the protocol (e.g., `compile_pdf.py`, `build_and_lint.py`), pass it to the safe executor:

The wrapper lives at `scripts/Invoke-SafePython.ps1` in this skill (resolve its absolute path via `laplace_skill("shell_mechanic").backing_path`):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/Invoke-SafePython.ps1 -ScriptPath "C:\path\to\script.py" -ScriptArgs "arg1", "arg2"
```

### What it does:
1. **Automatic Executable Resolution**: Safely scans `py`, `python`, and `python3` to locate the valid binary before execution.
2. **Encoding Lock**: Hardcodes `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` for the lifecycle of the execution, eliminating UTF-16 file corruption natively.

## Probationary Status
This is an `[EXPERIMENTAL]` structural upgrade developed by The Dreamer. When substituting standard `python` calls for this wrapper in your future orchestration, monitor the `stdout` for correctness and ask the user if the pathing friction is noticeably resolved.
