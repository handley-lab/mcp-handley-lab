# Talks: Domain Axioms

A talk is the manuscript voice projected into the spoken and slide medium. It is not a new voice and not a lossy summary of the paper. It is the same argument rendered at the ceiling of a freer medium - see [Voice and Style](canon://aesthetics/voice_and_style.md). The talk medium permits what the manuscript forbids: direct address, a spoken aside, a single slide that is mostly one figure. Push that ceiling.

This domain has left pure scaffold. Two pipelines now exist and one talk is published - the spine theory below still holds, and the artifact question is being resolved by evidence rather than left open. See [Talk From Manuscript](canon://domains/talks/projects/talk_from_manuscript.md) for the live state.

## What the medium is

- A talk is built from an existing manuscript. The manuscript is the source of truth - the talk derives from it, never the reverse, and never asserts beyond it.
- The output is a slide artifact and a spine. The spine - the ordered beats and what each one must land - is medium-independent and comes first. The artifact is a **web deck in the site `talks/` section**, not beamer - settled by what shipped. Two deck mechanisms are live: a **manim -> mp4 -> hand-maintained `talk-deck.js`** pipeline (the published `dynamics-as-computation` talk, the cinematic ceiling) and a lighter **Slidev markdown deck** that embeds live HTML assets and renders KaTeX in-page (the proven low-friction path for maths-and-figure decks). Which becomes the default is the open call in the project node.
- Figures are reused from the manuscript, not redrawn - **and not recoloured**. The talk and the site share the manuscript's assets - see [Web](canon://domains/web/axioms.md). The slide's accent colour is chosen to match the figure's own data colour, so furniture and figure read as one object.
- **The substrate decides the theme.** A deck is dark when its assets are dark (manim on `BLACK`) and paper-light when its assets are light (REVTeX figures on white). Do not pick a theme by taste and fight the assets into it. This is the highest-leverage staging choice - see the [Slide Design Guide](canon://domains/talks/projects/talk_from_manuscript.md).

## The tripartite shape (generate - stage - refine)

- **generate** - extract the talk spine from the manuscript: the narrative arc, the load-bearing results, and the figures that carry them, as an ordered list of beats. Each beat states what it must land and which manuscript result or figure backs it. No skill forged yet. First candidate: a `talk_spine_generator` that reads a compiled manuscript and emits the beat list with provenance back to manuscript labels.
- **stage** - assemble the beats into the slide artifact: one idea per slide, manuscript figures placed, the spoken arc built, speaker notes carrying the asides the slide cannot. The `slide_builder` slot now has a **seed**: the Slide Design Guide (`talks/skills/references/slide-design-guide.md`), which translates [figure_standard](canon://skills/figure_standard) into slide rules - substrate-decides-theme, render-order-as-reveal-order, the three KaTeX traps, embed-vs-bake. Forge `slide_builder` from it on the next real talk, not before.
- **refine** - verify the talk against its manuscript: every slide claim traces to a manuscript result or figure (the epistemic discipline of [epistemic_ledger](canon://skills/epistemic_ledger), reused), no orphan slides, timing within the slot, voice projected not flattened, figures legible at projection size. First candidate: a `talk_ledger` evaluating skill.

## Rules

- **The manuscript is the source of truth.** Every claim on a slide must trace to a result, figure, or statement already in the manuscript. A talk that asserts beyond its paper is a defect, not a teaser.
- **One idea per slide.** Compression is the discipline here as everywhere. A slide that carries two ideas carries neither.
- **Reuse the figure.** Manuscript figures are the talk's figures. If a figure needs a talk-only variant, derive it from the manuscript original, do not invent a parallel one.
- **The spine before the slides.** Settle the ordered beats and what each must land before building any artifact. The arc is the work - the slides are its projection.
- **Project the voice, do not flatten it.** The talk medium is freer than the paper. Use the latitude - direct address, the dry aside - rather than retreating to a bullet-point summary.
