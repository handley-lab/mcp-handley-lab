import sys
import os
import re

def sanitize_xcolor_file(filepath):
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex to match deeply nested color mixings: e.g. blue!80!black!5!white or red!50!black!10
    # The xcolor syntax is typically valid for color1!pct!color2, but chaining further often fails 
    # if it doesn't match standard syntax, causing compiler crashes.
    # This regex looks for: word ! number ! word ! number [! word]...
    # We will safely truncate anything after the second color.
    
    # Pattern explanation: 
    # Match: (color)(!number)(!color) and then capture any trailing (!number!color...) 
    # We'll replace it with just the first safe mixing, e.g. blue!80!black or blue!10
    
    nested_color_pattern = re.compile(r'([a-zA-Z]+!\d+![a-zA-Z]+)(!\d+(?:![a-zA-Z]+)*)')
    
    def replacer(match):
        safe_base = match.group(1)
        stripped = match.group(2)
        print(f"[TikZ Mechanic] Healed invalid color syntax: {match.group(0)} -> {safe_base}")
        return safe_base

    new_content, count = nested_color_pattern.subn(replacer, content)

    # Also catch cases like: blue!80!black!10 (without trailing color)
    # This replaces color!num!color!num -> color!num!color
    number_tail_pattern = re.compile(r'([a-zA-Z]+!\d+![a-zA-Z]+)!\d+(?![a-zA-Z0-9!])')
    
    def tail_replacer(match):
        safe_base = match.group(1)
        print(f"[TikZ Mechanic] Flattened trailing opacity scalar: {match.group(0)} -> {safe_base}")
        return safe_base

    new_content, count2 = number_tail_pattern.subn(tail_replacer, new_content)

    if count > 0 or count2 > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"[TikZ Mechanic] Sanitisation complete. Fixed {count + count2} xcolor geometric vulnerabilities in {os.path.basename(filepath)}.")
    else:
        print(f"[TikZ Mechanic] No invalid xcolor nesting detected in {os.path.basename(filepath)}. File is safe.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sanitize_xcolor.py <path_to_tex_file>")
        sys.exit(1)
    
    target_file = sys.argv[1]
    sanitize_xcolor_file(target_file)
