"""The verify third of the loop: consistency ledgers.

Structured, in-process checks that mirror the legacy mccaul-protocol scripts
(epistemic_ledger, latex_forge lint, global_weaver) so they return a
machine-readable mismatch report - and, crucially, a boolean ``passed`` per
check, which is the outcome signal the fitness assessment consumes.

``run_backing`` separately invokes a skill's original script as a subprocess for
its full human artifact (e.g. epistemic_graph.md, a compiled PDF).
"""

from __future__ import annotations

import glob
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp_gerard.laplace.canon import Canon, get_canon


def read_safe(path: str | Path) -> str:
    """UTF-8 with a UTF-16 fallback (PowerShell artifacts), mirroring the legacy."""
    p = Path(path)
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-16")


# ---------------------------------------------------------------------------
# epistemic: orphaned equations + naked claims  (mirrors map_derivations.py)
# ---------------------------------------------------------------------------


def check_epistemic(text: str) -> dict[str, Any]:
    labels = re.findall(r"\\label\{eq:([^}]+)\}", text)
    refs = re.findall(r"\\ref\{eq:([^}]+)\}", text)
    orphans = sorted(set(labels) - set(refs))

    sections = re.split(r"\\section\{([^}]+)\}", text)
    naked: list[str] = []
    if len(sections) > 1:
        for i in range(1, len(sections), 2):
            name = sections[i]
            body = re.sub(r"%.*?$", "", sections[i + 1], flags=re.MULTILINE)
            has_math = re.search(r"\$|\\\[|\\begin\{equation\}|\\ref\{eq:", body)
            if len(body.split()) > 150 and not has_math:
                naked.append(name)

    return {
        "pass": not orphans and not naked,
        "orphans": [f"eq:{o}" for o in orphans],
        "naked_claims": naked,
    }


# ---------------------------------------------------------------------------
# voice: British English, AI slop, TikZ colours, Vonnegut  (mirrors build_and_lint.py)
# ---------------------------------------------------------------------------

_AMERICANISMS = {
    r"\banalyze\b": "analyse",
    r"\bbehavior\b": "behaviour",
    r"\bparameterize\b": "parametrise",
    r"\bparameterized\b": "parametrised",
    r"\bcolor\b": "colour",
    r"\bmodeling\b": "modelling",
}
_AI_SLOP = [
    r"\bdelve\b",
    r"\btapestry\b",
    r"\btestament\b",
    r"\bcrucial\b",
    r"\bnot merely\b",
    r"\bbut rather\b",
    r"\bin summary\b",
    r"\bin conclusion\b",
]
_TIKZ_BANS = {
    r"\[red\]": "[red!80!black]",
    r"\[blue\]": "[blue!80!black]",
    r"\[green\]": "[green!80!black]",
    r"\[yellow\]": "[yellow!80!black]",
    r"\boutput/.style\b": "finalnode/.style (output is a reserved TikZ keyword)",
    r"\bstyle\s*=\s*output\b": "style=finalnode (output is reserved)",
    r"\[output\]": "[finalnode] (output is reserved)",
}
_VONNEGUT = [
    (r";", "Vonnegut Rule: eradicate semi-colons (unless required by TikZ syntax)."),
    (r"---", "Vonnegut Rule: use spaced hyphens ( - ), not em-dashes (---)."),
    (r"(?<!\-)--(?!\-)", "Vonnegut Rule: use spaced hyphens ( - ), not en-dashes (--)."),
]


def check_voice(text: str) -> dict[str, Any]:
    flags: list[dict[str, Any]] = []
    in_figure_star = False
    in_tikz = False

    for i, line in enumerate(text.splitlines(), 1):
        if r"\begin{figure*}" in line:
            in_figure_star = True
        elif r"\end{figure*}" in line:
            in_figure_star = False
        if r"\begin{tikzpicture}" in line or r"\begin{axis}" in line:
            in_tikz = True
        elif r"\end{tikzpicture}" in line or r"\end{axis}" in line:
            in_tikz = False

        if in_figure_star and r"\linewidth" in line and r"\includegraphics" in line:
            flags.append({"line": i, "kind": "layout", "message": r"\linewidth in figure* stretches single-column figures; use \columnwidth."})

        if in_tikz:
            if re.search(r"[xy]label\s*=\s*\{?\s*\$?[xyz]\$?\s*\}?(?=[,\]\s]|$)", line, re.I):
                flags.append({"line": i, "kind": "variable", "message": "Generic TikZ axis label (x/y/z); match manuscript symbols."})
            if re.search(r"\\node[^;]*\{\s*\$?[xyz]\$?\s*\}\s*;", line, re.I):
                flags.append({"line": i, "kind": "variable", "message": "Generic TikZ node variable (x/y/z); match manuscript symbols."})

        for pat, repl in _AMERICANISMS.items():
            if re.search(pat, line, re.I):
                flags.append({"line": i, "kind": "americanism", "message": f"Use British English: {repl!r}."})
        for pat in _AI_SLOP:
            if re.search(pat, line, re.I):
                flags.append({"line": i, "kind": "ai_slop", "message": f"AI slop: {pat.replace(chr(92)+'b','')!r}."})
        for pat, repl in _TIKZ_BANS.items():
            if re.search(pat, line, re.I):
                flags.append({"line": i, "kind": "tikz_colour", "message": f"Use Nature-style colour: {repl}."})
        for pat, msg in _VONNEGUT:
            if re.search(pat, line):
                if pat == r";" and line.strip().endswith(";") and ("\\" in line or "(" in line or "tikz" in line.lower()):
                    continue
                if pat == r"(?<!\-)--(?!\-)" and (re.search(r"\d--\d", line) or any(c in line for c in (r"\draw", r"\path", r"\node", r"\fill"))):
                    continue
                flags.append({"line": i, "kind": "vonnegut", "message": msg})

    return {"pass": not flags, "violations": flags, "count": len(flags)}


# ---------------------------------------------------------------------------
# crossref: broken refs + duplicate labels  (mirrors weave_orchestra.py)
# ---------------------------------------------------------------------------


def check_crossref(target: str | Path) -> dict[str, Any]:
    target = Path(target)
    if target.is_dir():
        tex_files = [Path(p) for p in glob.glob(str(target / "**" / "*.tex"), recursive=True)]
    else:
        tex_files = [target]

    global_labels: dict[str, list[str]] = {}
    references_map: dict[str, list[str]] = {}
    for fp in tex_files:
        content = read_safe(fp)
        name = fp.name
        for lbl in re.findall(r"\\label\{([^}]+)\}", content):
            global_labels.setdefault(lbl, []).append(name)
        references_map.setdefault(name, []).extend(re.findall(r"\\ref\{([^}]+)\}", content))

    broken = [
        {"file": fn, "ref": ref}
        for fn, refs in references_map.items()
        for ref in refs
        if ref not in global_labels
    ]
    duplicates = {lbl: files for lbl, files in global_labels.items() if len(files) > 1}
    return {"pass": not broken and not duplicates, "broken_refs": broken, "duplicate_labels": duplicates}


# ---------------------------------------------------------------------------
# aggregate verify
# ---------------------------------------------------------------------------

DEFAULT_CHECKS = ["epistemic", "voice", "crossref"]


def verify(
    target: str | Path,
    checks: list[str] | None = None,
    canon: Canon | None = None,
) -> dict[str, Any]:
    """Run consistency checks on a target and return a structured mismatch report."""
    canon = canon or get_canon()
    checks = checks or DEFAULT_CHECKS
    target = Path(target)
    results: dict[str, Any] = {}

    text = None
    if not target.is_dir() and any(c in {"voice", "epistemic"} for c in checks):
        text = read_safe(target)

    for check in checks:
        if check == "voice":
            results["voice"] = check_voice(text or "")
        elif check == "epistemic":
            results["epistemic"] = check_epistemic(text or "")
        elif check == "crossref":
            results["crossref"] = check_crossref(target)
        elif check == "empirical":
            # No deterministic check: hand back the protocol for an agent to run.
            sk = canon.skills.get("empirical_ledger")
            results["empirical"] = {
                "pass": None,
                "manual": True,
                "protocol": sk.skill_md.read_text(encoding="utf-8") if sk else "",
            }
        else:
            results[check] = {"pass": None, "error": f"unknown check {check!r}"}

    decided = [r["pass"] for r in results.values() if r.get("pass") is not None]
    passed = all(decided) if decided else None
    n_issues = sum(
        len(r.get("violations", [])) + len(r.get("orphans", [])) + len(r.get("naked_claims", [])) + len(r.get("broken_refs", [])) + len(r.get("duplicate_labels", {}))
        for r in results.values()
    )
    return {
        "target": str(target),
        "checks": results,
        "passed": passed,
        "issue_count": n_issues,
        "summary": f"{'PASS' if passed else 'FAIL' if passed is False else 'PARTIAL'}: {n_issues} issue(s) across {len(results)} check(s).",
    }


# ---------------------------------------------------------------------------
# execute: run a skill's backing script for its full artifact
# ---------------------------------------------------------------------------


def run_backing(
    skill: str,
    target: str = "",
    args: list[str] | None = None,
    canon: Canon | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    """Invoke a skill's backing script as a subprocess. Returns stdout/stderr/code."""
    canon = canon or get_canon()
    sk = canon.skills.get(skill)
    if sk is None:
        return {"error": f"unknown skill {skill!r}", "available": list(canon.skills)}
    if not sk.backing or not sk.backing_path or not sk.backing_path.exists():
        return {"error": f"skill {skill!r} has no runnable backing script"}

    script = sk.backing_path
    extra = ([target] if target else []) + (args or [])
    if script.suffix == ".ps1":
        cmd = ["powershell", "-NoProfile", "-File", str(script), *extra]
    else:
        cmd = [sys.executable, str(script), *extra]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return {"error": f"execution failed: {e}", "cmd": cmd}
    return {
        "skill": skill,
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "ok": proc.returncode == 0,
    }
