# Project: Talk From Manuscript

The generic pipeline for turning one of the orchestra manuscripts into a talk. This node tracks the pipeline state for the engine. No longer a bare scaffold - one talk is published and the staging tooling is being scouted live.

## The pipeline

Source manuscript -> spine (generate) -> slide artifact (stage) -> verified talk (refine). The spine is medium-independent and comes first. The artifact is a web deck in the site `talks/` section - settled, not beamer.

## Inputs and outputs

- **Input**: a compiled manuscript from the orchestra (a `.tex` source plus its figures and label set). The richest near-term candidate is [Adaptive Normal Form](canon://domains/synthetics/projects/adaptive_normal_form.md), whose figure rail is well underway.
- **Output**: a slide artifact plus a spine document. The home for a web-facing talk is the `talks/` section of [phujck.github.io](canon://domains/web/projects/phujck_github_io.md). The published `dynamics-as-computation` talk lives there now.

## The tooling, as it actually stands (scouted 2026-05-31)

The talk-production repo is `C:\Users\gerar\VScodeProjects\talks` - a thin pipeline plus design skills, not the engine. Two deck mechanisms are live, the central open call is which becomes default:

- **manim -> mp4 -> hand-maintained `talk-deck.js`** (the existing pipeline, `talks/pipeline/` + `talks/skills/{talk-init,talk-plan,manim-scene,talk-render}`, reference idioms in `talks/skills/references/dynamics-as-computation-idioms.md`). Produces the `dynamics-as-computation` talk - the cinematic ceiling. Cost: heavy (27 MB of mp4 for one talk), manim is high-friction to drive, assets are baked recordings not live.
- **Slidev markdown deck** (pilot at `talks/_pilots/slidev-dynamics/`, built this session). Markdown source, KaTeX in-page, custom dark/paper themes, live HTML assets embedded by `<iframe>` (the `viz/why-algebra/*.html` integrators) and manuscript figures reused verbatim by `<Fig>`. A full deck with three live embeds builds to **2.2 MB** against the manim talk's 27 MB. Proven to render elegant display mathematics and reuse REVTeX figures unmodified (the ANF mock-up, `talks/_pilots/slidev-dynamics/anf.md`).

The third engine option scouted and **held**: Motion Canvas (TypeScript, "manim but with a live web-component player") - the right tool only if a future talk needs staged explanatory *motion* that is neither a manim film nor a hand-canvas interactive. GSAP (now fully free) is the lighter in-page-motion fallback. Neither is needed yet.

## Active state

- The `slide_builder` stage slot now has a **seed**, not just a name: `talks/skills/references/slide-design-guide.md`, which translates [figure_standard](canon://skills/figure_standard) into slide rules. The `talk_spine_generator` and `talk_ledger` slots are still unforged forge targets.
- The refine third can borrow [epistemic_ledger](canon://skills/epistemic_ledger) immediately - a slide claim traces to a manuscript label exactly as a manuscript claim traces to an equation. The voice check also applies to slide prose and captions.

## Next concrete step (when the work resumes)

- **Decide the default deck shell.** The likely split: Slidev for maths-and-figure-heavy decks (ANF and most orchestra papers), the manim pipeline reserved for genuinely cinematic assets (3D camera moves, field evolutions). Confirm or override.
- Build the **ANF talk for real** off the published-figure rail - hand-author the spine (ordered beats, provenance to R1-R5 labels) first, then stage it through the design guide. This is the first true manuscript-to-talk build.
- Forge `talk_spine_generator` and `slide_builder` from that build, not before. Lift the design guide into a backing once it proves on a second deck.
