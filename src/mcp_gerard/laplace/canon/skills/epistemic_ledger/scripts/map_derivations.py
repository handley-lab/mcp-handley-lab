import sys
import re
import os

def read_safe(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(filepath, 'r', encoding='utf-16') as f:
            return f.read()

def parse_tex(filepath):
    # Honest exit contract: an unreadable target is an operational failure
    # (exit 2), never a silent pass. Successful analysis exits 0 regardless of
    # how many orphans or naked claims are flagged - finding them is the skill
    # working, not failing.
    if not os.path.isfile(filepath):
        print(f"Error: {filepath} is not a readable file.", file=sys.stderr)
        sys.exit(2)

    try:
        content = read_safe(filepath)
    except (OSError, UnicodeError) as e:
        print(f"Error: cannot read {filepath}: {e}", file=sys.stderr)
        sys.exit(2)

    # Find all equation labels
    labels = re.findall(r'\\label\{eq:([^}]+)\}', content)
    # Find all references (every cross-ref command, not just \ref)
    refs = re.findall(r'\\(?:ref|eqref|autoref|cref|Cref)\{eq:([^}]+)\}', content)
    
    orphans = set(labels) - set(refs)

    # Naked claims check: a section is naked if it has > 150 words but 0 math/refs
    sections = re.split(r'\\section\{([^}]+)\}', content)
    naked_claims = []
    
    if len(sections) > 1:
        for i in range(1, len(sections), 2):
            sec_name = sections[i]
            sec_text = sections[i+1]
            # Strip comments
            sec_text = re.sub(r'%.*?$', '', sec_text, flags=re.MULTILINE)
            # Find math environments or refs
            has_math = re.search(r'\$|\\\[|\\begin\{equation\}|\\(?:eq|auto|c|C)?ref\{eq:', sec_text)
            word_count = len(sec_text.split())
            
            # If a section is purely textual and lengthy, it's a naked claim
            if word_count > 150 and not has_math:
                naked_claims.append(sec_name)
    
    out_dir = os.path.dirname(filepath)
    out_file = os.path.join(out_dir, "epistemic_graph.md")

    with open(out_file, 'w', encoding='utf-8') as out:
        out.write("# Epistemic Ledger: Dependency Graph\n\n")
        out.write("This graph maps the mathematical dependencies of the manuscript.\n\n")
        
        out.write("```mermaid\n")
        out.write("graph TD\n")
        out.write("    Start[Manuscript Start] --> Analysis\n")
        
        for label in labels:
            if label in orphans:
                out.write(f"    {label}([{label}]):::orphan\n")
            else:
                out.write(f"    {label}[{label}] --> Conclusion\n")
                
        out.write("\n    classDef orphan fill:#f96,stroke:#333,stroke-width:2px;\n")
        out.write("```\n\n")
        
        if orphans or naked_claims:
            out.write("### ⚠️ Structural Failures Detected\n")
            if orphans:
                out.write("#### Orphaned Equations\n")
                out.write("The following equations are derived but never utilized (Orphans):\n")
                for o in orphans:
                    out.write(f"- `eq:{o}`\n")
                out.write("\n")
            
            if naked_claims:
                out.write("#### Naked Claims\n")
                out.write("The following sections assert physics without mathematics (Naked Claims):\n")
                for sec in naked_claims:
                    out.write(f"- `{sec}`\n")
                out.write("\n")

            out.write("**Protocol:** Utilise orphans, derive naked claims, or banish to Appendices.\n")
        else:
            out.write("### ✅ Epistemic Flow Intact\n")
            out.write("All derived equations are successfully integrated into the logic chain, and no naked claims were detected.\n")

    print(f"Epistemic Ledger successfully generated at: {out_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python map_derivations.py <path_to_tex_file>", file=sys.stderr)
        sys.exit(2)
    else:
        parse_tex(sys.argv[1])
