---
name: html_mechanic
description: "[EXPERIMENTAL] Automates fine-grained textual polish across HTML, enforcing the Vonnegut Rule, spaced hyphens, British English, and the objective wryness of the Laplace voice."
---
# html_mechanic

**Status: [EXPERIMENTAL]**

## Purpose
The `html_mechanic` skill automates the rigorous textual enforcement of the Laplace voice specifically within HTML structures. It targets web-facing prose, stripping out AI slop, enforcing British English spelling, standardising typography (spaced hyphens), and applying the Vonnegut Rule (brief, pithy, punchy sentences) to web copy.

## Capabilities
- **Typography Standardisation**: Enforces spaced en-dashes or proper em-dashes where appropriate. Converts "AI slop" or verbose "synergistic" buzzwords into crisp, objective terms.
- **British English Enforcement**: Sweeps HTML text nodes to convert Americanisms (e.g., 'ize' -> 'ise', 'color' -> 'colour', 'behavior' -> 'behaviour').
- **The Vonnegut Rule**: Analyzes paragraphs for excessive length or convoluted subordinate clauses and breaks them into tighter, more impactful sentences reflecting objective wryness.
- **HTML-Safe Parsing**: Ensures that HTML tags and attributes (like `class="color-red"`) are NOT modified. Only text nodes and visible web copy are polished.

## Usage Instructions
When reviewing or modifying HTML files for phujck.github.io:
1. Parse the HTML to isolate text content from structural tags.
2. Apply the textual rewrite rules to the extracted text.
3. Review the text to ensure the "objective wryness" aesthetic is preserved and AI cliches are eliminated.
4. Re-inject the polished text back into the HTML file.

*This skill is under experimental validation. Be hyper-vigilant about not breaking HTML structures.*
