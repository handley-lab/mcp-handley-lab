import sys
import re
import os
import glob

def read_safe(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(filepath, 'r', encoding='utf-16') as f:
            return f.read()

def weave(target_dir):
    if not os.path.isdir(target_dir):
        print(f"Error: {target_dir} is not a directory.")
        return

    tex_files = glob.glob(os.path.join(target_dir, '**', '*.tex'), recursive=True)
    if not tex_files:
        print("No .tex files found.")
        return

    global_labels = {}
    references_map = {}

    for filepath in tex_files:
        content = read_safe(filepath)
        filename = os.path.basename(filepath)
        
        # We find labels, typical format \label{prefix:name}
        labels = re.findall(r'\\label\{([^}]+)\}', content)
        for lbl in labels:
            if lbl not in global_labels:
                global_labels[lbl] = []
            global_labels[lbl].append(filename)
            
        # Find refs (every cross-ref command, not just \ref)
        refs = re.findall(r'\\(?:ref|eqref|autoref|cref|Cref)\{([^}]+)\}', content)
        if filename not in references_map:
            references_map[filename] = []
        references_map[filename].extend(refs)

    out_file = os.path.join(target_dir, "cross_reference_report.md")
    
    broken_refs = []
    duplicate_labels = {lbl: files for lbl, files in global_labels.items() if len(files) > 1}

    for filename, refs in references_map.items():
        for ref in refs:
            if ref not in global_labels:
                broken_refs.append((filename, ref))

    with open(out_file, 'w', encoding='utf-8') as out:
        out.write("# Global Weaver: Cross-Reference Report\n\n")
        
        if not broken_refs and not duplicate_labels:
            out.write("### ✅ Global Synchronization Intact\n")
            out.write("All cross-references and labels are perfectly aligned across the orchestra.\n")
        else:
            out.write("### ⚠️ Orchestral Dissonance Detected\n\n")
            
            if broken_refs:
                out.write("#### Broken References\n")
                out.write("The following files reference labels that do not exist anywhere in the orchestra:\n")
                for filename, ref in broken_refs:
                    out.write(f"- `{filename}`: `\\ref{{{ref}}}`\n")
                out.write("\n")
                
            if duplicate_labels:
                out.write("#### Duplicate Labels\n")
                out.write("The following labels are defined in multiple locations, causing namespace collisions:\n")
                for lbl, files in duplicate_labels.items():
                    out.write(f"- `{lbl}` defined in: {', '.join(files)}\n")
                out.write("\n")

            out.write("**Protocol:** Resolve broken links and namespace collisions immediately.\n")

    print(f"Global Weaver report successfully generated at: {out_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python weave_orchestra.py <target_directory>")
    else:
        weave(sys.argv[1])
