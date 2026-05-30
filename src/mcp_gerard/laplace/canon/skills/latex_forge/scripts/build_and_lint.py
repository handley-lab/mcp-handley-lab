import sys
import re
import os

def read_safe(filepath):
    """Gracefully handle UTF-16 artifacts from PowerShell and standard UTF-8."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.readlines()
    except UnicodeDecodeError:
        with open(filepath, 'r', encoding='utf-16') as f:
            return f.readlines()

def lint_file(filepath, auto_fix=False):
    # Honest exit contract: an unreadable target is an operational failure
    # (exit 2), never a silent pass. A report with flags is still a successful
    # run (exit 0) - flagging slop is the skill working, not failing.
    if not os.path.isfile(filepath):
        print(f"Error: {filepath} is not a readable file.", file=sys.stderr)
        sys.exit(2)

    try:
        lines = read_safe(filepath)
    except (OSError, UnicodeError) as e:
        print(f"Error: cannot read {filepath}: {e}", file=sys.stderr)
        sys.exit(2)
    flags = []
    
    # Dictionaries of banned syntax
    americanisms = {
        r'\banalyze\b': 'analyse',
        r'\bbehavior\b': 'behaviour',
        r'\bparameterize\b': 'parametrise',
        r'\bparameterized\b': 'parametrised',
        r'\bcolor\b': 'colour',
        r'\bmodeling\b': 'modelling'
    }

    ai_slop = [
        r'\bdelve\b',
        r'\btapestry\b',
        r'\btestament\b',
        r'\bcrucial\b',
        r'\bnot merely\b',
        r'\bbut rather\b',
        r'\bin summary\b',
        r'\bin conclusion\b'
    ]

    tikz_bans = {
        r'\[red\]': '[red!80!black]',
        r'\[blue\]': '[blue!80!black]',
        r'\[green\]': '[green!80!black]',
        r'\[yellow\]': '[yellow!80!black]',
        r'\boutput/.style\b': 'finalnode/.style (output is a reserved TikZ keyword that breaks positioning)',
        r'\bstyle\s*=\s*output\b': 'style=finalnode (output is a reserved TikZ keyword)',
        r'\[output\]': '[finalnode] (output is a reserved TikZ keyword)'
    }

    vonnegut_rules = [
        (r';', "The Vonnegut Rule: Eradicate all semi-colons globally (unless strictly required by TikZ syntax)."),
        (r'---', "The Vonnegut Rule: Use spaced hyphens ( - ) rather than em-dashes (---)."),
        (r'(?<!\-)--(?!\-)', "The Vonnegut Rule: Use spaced hyphens ( - ) rather than en-dashes (--) for parentheticals.")
    ]

    modified_lines = []
    changed = False

    in_figure_star = False
    in_tikz = False

    for i, line in enumerate(lines):
        orig_line = line
        
        # Track environments for layout and variable consistency checks
        if r'\begin{figure*}' in line:
            in_figure_star = True
        elif r'\end{figure*}' in line:
            in_figure_star = False
            
        if r'\begin{tikzpicture}' in line or r'\begin{axis}' in line:
            in_tikz = True
        elif r'\end{tikzpicture}' in line or r'\end{axis}' in line:
            in_tikz = False

        # Check Layout Distortion
        if in_figure_star and r'\linewidth' in line and r'\includegraphics' in line:
            flags.append(f"- **Line {i+1}** [Layout Distortion]: `\\linewidth` used for graphic inside `figure*`. This stretches single-column Python figures across the full page. Consider using `\\columnwidth` or a specific scaled width.")

        # Check Variable Inconsistency in TikZ/Axis
        if in_tikz:
            if re.search(r'[xy]label\s*=\s*\{?\s*\$?[xyz]\$?\s*\}?(?=[,\]\s]|$)', line, re.IGNORECASE):
                flags.append(f"- **Line {i+1}** [Variable Inconsistency]: Generic TikZ axis label (x/y/z) detected. Ensure this matches manuscript text (e.g., \\mathcal{{M}} vs x, \\theta vs z).")
            if re.search(r'\\node[^;]*\{\s*\$?[xyz]\$?\s*\}\s*;', line, re.IGNORECASE):
                flags.append(f"- **Line {i+1}** [Variable Inconsistency]: Generic TikZ node variable (x/y/z) detected. Ensure this matches manuscript text (e.g., \\mathcal{{M}} vs x, \\theta vs z).")

        # Check and Fix Americanisms
        for pattern, replacement in americanisms.items():
            if re.search(pattern, line, re.IGNORECASE):
                flags.append(f"- **Line {i+1}** [Americanism]: Found `{pattern.replace(r'\\b','')}`. Use British English (`{replacement}`).")
                if auto_fix:
                    # simplistic case-insensitive replace keeping case for first letter is hard, but we'll do simple sub
                    line = re.sub(pattern, replacement, line, flags=re.IGNORECASE)
        
        # Check AI Slop
        for pattern in ai_slop:
            if re.search(pattern, line, re.IGNORECASE):
                flags.append(f"- **Line {i+1}** [AI Slop]: Found `{pattern.replace(r'\\b','')}`. Eradicate sycophantic or narrative bloat.")

        # Check and Fix TikZ Colors
        for pattern, replacement in tikz_bans.items():
            if re.search(pattern, line, re.IGNORECASE):
                flags.append(f"- **Line {i+1}** [Aesthetics]: Found raw `{pattern}` in TikZ. The 'Child Made It' rule mandates Nature-style premium colors (e.g., `{replacement}`).")
                if auto_fix:
                    line = re.sub(pattern, replacement, line, flags=re.IGNORECASE)
                    
        # Check Vonnegut Rules
        for pattern, message in vonnegut_rules:
            if re.search(pattern, line):
                # Simple heuristic to avoid flagging TikZ semicolons: if line ends with ';' and contains '\' or '(', ignore.
                if pattern == r';' and line.strip().endswith(';') and ('\\' in line or '(' in line or 'tikz' in line.lower()):
                    continue
                # Ignore en-dashes used for page ranges or equations or TikZ paths
                if pattern == r'(?<!\-)--(?!\-)' and (re.search(r'\d--\d', line) or '\\draw' in line or '\\path' in line or '\\node' in line or '\\fill' in line):
                    continue
                flags.append(f"- **Line {i+1}** [Vonnegut]: {message}")

        modified_lines.append(line)
        if line != orig_line:
            changed = True

    if auto_fix and changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(modified_lines)
        print(f"AUTO-FIX APPLIED: Re-wrote {filepath} with British English and Nature-style colours.")

    print(f"# LaTeX Forge Lint Report: {os.path.basename(filepath)}")
    print("*" * 50)
    if not flags:
        print("PASS: No structural violations detected.")
    else:
        print("WARNINGS FLAGGED FOR REVIEW:\n")
        for flag in flags:
            print(flag)
        if auto_fix:
            print("\n*Protocol:* AI slop cannot be reliably auto-fixed. Address remaining flags manually.")
        else:
            print("\n*Protocol:* Address these flags before presenting the draft. You may use `--auto-fix` to resolve Americanisms and TikZ colours automatically.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build_and_lint.py <path_to_tex_file> [--auto-fix]", file=sys.stderr)
        sys.exit(2)
    else:
        filepath = sys.argv[1]
        auto_fix = '--auto-fix' in sys.argv
        lint_file(filepath, auto_fix)
