---
name: web_deployment_mechanic
description: "[EXPERIMENTAL] Automates the deployment of finished manuscripts to the phujck.github.io website, including summary generation, HTML updating, and PDF copying."
---

# Web Deployment Mechanic [EXPERIMENTAL]

This skill automates the high-friction manual task of publishing an approved manuscript to the PI's static website (`c:\Users\gerar\VScodeProjects\phujck.github.io`).

## Deployment Protocol

When directed to publish or deploy a manuscript to the website, follow these steps exactly:

1. **PDF Synchronization**:
   - Copy the finalized, compiled `.pdf` from the manuscript directory to `c:\Users\gerar\VScodeProjects\phujck.github.io\assets\docs\`.
   - Ensure the filename is lowercased and hyphenated (e.g., `the-phases-of-hierarchy.pdf`).

2. **The Ordinary-Language Summary**:
   - Read the final abstract and introduction of the manuscript.
   - Draft a ~500-word summary in *ordinary language*. It must bridge the mathematical formalism into physical intuitions (e.g., translating "Layer Normalisation" into "hierarchical attenuation").
   - **Crucial Disclaimer**: You MUST include a disclaimer in the HTML stating: *"Disclaimer: This is experimental work in algorithmic research and should not be considered final."*

3. **Nature-Style Visual Embedding**:
   - Generate or extract 1-2 Nature-style visual elements (e.g., Mermaid diagrams or clean vector SVGs) representing the core conceptual bridge (e.g., the Ultraepistemic Catastrophe or Hierarchical Attenuation).
   - Ensure these visuals obey the 'Child Made It' rule: clean flat pastel fills, thick dark outlines, muted vermilions.

4. **HTML Injection (`synthetics.html`)**:
   - Open `c:\Users\gerar\VScodeProjects\phujck.github.io\synthetics.html`.
   - Append the new entry, summary, disclaimer, and PDF link to the appropriate section.
   - Ensure strict alignment with the `html_mechanic` (British English, spaced hyphens, Vonnegut Rule).

5. **Commit and Push (The Hostile Verification Axiom)**:
   - Use the `git_mechanic` skill to stage, commit, and push the changes to the `phujck.github.io` repository.

## Operational Constraints
- Never deploy a manuscript that has not passed the full `laplace_release_mechanic` pipeline.
- The web deployment is the final physical manifestation of the manuscript. Treat its aesthetic quality with the same rigor as the LaTeX source.
