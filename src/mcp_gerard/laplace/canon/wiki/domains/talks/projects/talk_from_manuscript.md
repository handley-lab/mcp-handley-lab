# Project: Talk From Manuscript

The generic pipeline for turning one of the orchestra manuscripts into a talk. This node tracks the pipeline state for the engine. It is a scaffold - fill it as the first real talk is built.

## The pipeline

Source manuscript -> spine (generate) -> slide artifact (stage) -> verified talk (refine). The spine is medium-independent and comes first. The artifact form is chosen per talk.

## Inputs and outputs

- **Input**: a compiled manuscript from the orchestra (a `.tex` source plus its figures and label set). The richest near-term candidate is [Adaptive Normal Form](canon://domains/synthetics/projects/adaptive_normal_form.md) once its draft settles.
- **Output**: a slide artifact plus a spine document. The natural home for a web-facing talk is the `talks/` section of [phujck.github.io](canon://domains/web/projects/phujck_github_io.md), which already exists.

## Active state

- Status: scaffold only. No talk skill is forged yet. The three slots (`talk_spine_generator`, `slide_builder`, `talk_ledger`) are forge targets, named in the [axioms](canon://domains/talks/axioms.md), to be created on the first real talk.
- The refine third can borrow [epistemic_ledger](canon://skills/epistemic_ledger) immediately - a slide claim traces to a manuscript label exactly as a manuscript claim traces to an equation.

## Next concrete step (when the work resumes)

- Pick the first source manuscript (likely Adaptive Normal Form after the figure rail lands).
- Hand-build one spine from it - the ordered beats with provenance to manuscript labels - to learn the shape before forging `talk_spine_generator`.
- Choose the artifact form (reveal.js for the site, or beamer) once the spine exists.
- Forge the generate and stage skills from that first build, not before.
