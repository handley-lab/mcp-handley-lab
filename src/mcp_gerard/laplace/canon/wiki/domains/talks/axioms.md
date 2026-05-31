# Talks: Domain Axioms

A talk is the manuscript voice projected into the spoken and slide medium. It is not a new voice and not a lossy summary of the paper. It is the same argument rendered at the ceiling of a freer medium - see [Voice and Style](canon://aesthetics/voice_and_style.md). The talk medium permits what the manuscript forbids: direct address, a spoken aside, a single slide that is mostly one figure. Push that ceiling.

This domain is in scaffold state. The structure is laid here so the manuscript-to-talk pipeline can start at the low level and the skills can be forged on first real use.

## What the medium is

- A talk is built from an existing manuscript. The manuscript is the source of truth - the talk derives from it, never the reverse, and never asserts beyond it.
- The output is a slide artifact and a spine. The artifact form is deliberately not fixed yet (reveal.js for the site `talks/` section, or beamer for a PDF). The spine - the ordered beats and what each one must land - is medium-independent and comes first.
- Figures are reused from the manuscript, not redrawn. The talk and the site share the manuscript's assets - see [Web](canon://domains/web/axioms.md).

## The tripartite shape (generate - stage - refine)

- **generate** - extract the talk spine from the manuscript: the narrative arc, the load-bearing results, and the figures that carry them, as an ordered list of beats. Each beat states what it must land and which manuscript result or figure backs it. No skill forged yet. First candidate: a `talk_spine_generator` that reads a compiled manuscript and emits the beat list with provenance back to manuscript labels.
- **stage** - assemble the beats into the slide artifact: one idea per slide, manuscript figures placed, the spoken arc built, speaker notes carrying the asides the slide cannot. No skill forged yet. First candidate: a `slide_builder` keyed to the chosen artifact form.
- **refine** - verify the talk against its manuscript: every slide claim traces to a manuscript result or figure (the epistemic discipline of [epistemic_ledger](canon://skills/epistemic_ledger), reused), no orphan slides, timing within the slot, voice projected not flattened, figures legible at projection size. First candidate: a `talk_ledger` evaluating skill.

## Rules

- **The manuscript is the source of truth.** Every claim on a slide must trace to a result, figure, or statement already in the manuscript. A talk that asserts beyond its paper is a defect, not a teaser.
- **One idea per slide.** Compression is the discipline here as everywhere. A slide that carries two ideas carries neither.
- **Reuse the figure.** Manuscript figures are the talk's figures. If a figure needs a talk-only variant, derive it from the manuscript original, do not invent a parallel one.
- **The spine before the slides.** Settle the ordered beats and what each must land before building any artifact. The arc is the work - the slides are its projection.
- **Project the voice, do not flatten it.** The talk medium is freer than the paper. Use the latitude - direct address, the dry aside - rather than retreating to a bullet-point summary.
