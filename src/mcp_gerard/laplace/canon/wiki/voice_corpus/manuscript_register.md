# Manuscript Register

**Status**: Gate 2 metadata inventory started. First academic full-text reader pass ingested.

This is the target register for improving manuscript drafting. It is the strictest projection of the voice, not the weakest one.

## Evidence Sources

- Zotero library for published and cited academic work
- Overleaf exports for active and abandoned manuscripts
- local LaTeX projects where available
- existing Laplace manuscript canon
- cautious calibration transfer from [Eppur Si Muove](canon://voice_corpus/eppur_si_muove.md)

## Gate 2 Source Inventory

Source discovery on 2026-05-31 located a Zotero `My Papers` collection and three local Overleaf bundles. The Zotero pass was metadata-only. The Overleaf pass read only bundle and nested-project filenames.

Primary academic spine:

- `ZOTERO-MY-PAPERS`, collection key `HSSAXTCW`, holds the authored and co-authored academic spine from 2017 through 2025.
- `ZOTERO-MY-PAPERS-ARTICLES`, collection key `VHBHN73T`, holds talks, CV, coverage, and article-adjacent context.
- `OVERLEAF-ACADEMIC-REVIEW-20260531` holds academic review projects. Treat as academic-adjacent judgement voice, not manuscript voice, until provenance is confirmed.

First reader batch should prefer texts where Gerard is first or sole author, where the title itself carries the voice, or where the venue imposes a strong register constraint:

- `ZOTERO-UQW3Y5J2`: `Driven Imposters: Controlling Expectations in Many-Body Systems`. Use for PRL compression, naming, and formalised mischief.
- `ZOTERO-27MBG7CN`: `How to win friends and influence functionals: deducing stochasticity from deterministic dynamics`. Use for humour that survives academic form.
- `ZOTERO-D6E6KU5P`: `Optical Indistinguishability via Twinning Fields`. Use for compact PRL framing and coined object discipline.
- `ZOTERO-9IFREHKD`: `Superoscillations Deliver Superspectroscopy`. Use for high-impact compression and title-as-claim.
- `ZOTERO-MHPXQFHH`: `Free to harmonic unitary transformations in quantum and Koopman dynamics`. Use for mathematical object framing.
- `ZOTERO-Y6FTCVRH`: `Wave operator representation of quantum and classical dynamics`. Use for representation-first exposition.
- `ZOTERO-Q6RYZNSE`: `Unwrapping photonic reservoirs: Enhanced expressivity via random Fourier encoding over stretched domains`. Use for recent reservoir-computing voice.
- `ZOTERO-UNGFXZ9P`: `Free Snacks in Quantum Complexity`. Use for sole-author recent voice, after preprint status is checked.
- `ZOTERO-2TMCRVBA`: `Stochastic representations of open systems`. Use for dissertation-scale voice and old-self baseline, not as the manuscript target by default.

The first batch should not average the corpus. It should deliberately compare constraints:

- thesis scale against PRL scale
- title-led framing against neutral mathematical exposition
- older open-systems work against current reservoir and complexity work
- solo or first-author pieces against broad collaborative pieces

## Gate 2 Full-Text Evidence: Driven Imposters

Source: `ZOTERO-UQW3Y5J2`, `Driven Imposters: Controlling Expectations in Many-Body Systems`. Status: first academic full-text pass, PRL-style evidence. Reader jobs: `voice`, `author_method`, and `facts` over four chunks. Treat these claims as same-register provisional evidence, not a complete manuscript ideal.

Evidence quality:

- Full text was chunked into four provenance units and processed through twelve serial reader jobs.
- All reader outputs passed raw-leak checks.
- One reader fact with an impossible byte span was rejected before canon admission.
- The source is collaborative and venue-constrained, so it is stronger evidence for title/framing/compression than for sentence-level sole-author style.

Provisional manuscript mechanics from this source:

- **Title as compressed argument.** The title makes the technical result do rhetorical work: an object can be made to pass as another object under controlled observables. This is not decorative humour. It names the mechanism.
- **Mischief formalised into constraint.** The register permits dry irreverence only after the mathematical object exists. The imposter frame works because the paper immediately pays it off through tracking control, uniqueness conditions, and physical realisability.
- **Failure converted into admissibility.** Singularities, dielectric breakdown, scaling limits, and transient control errors are not treated as embarrassment. They become constraints, caveats, or design conditions.
- **Compression by named machinery.** The prose leans on a small set of formal objects - tracking Hamiltonian, target observable, control field, Fermi-Hubbard test system - then lets figures and equations carry the mechanical load.
- **Application as structural proof.** The material-mimicry example is not merely an application section. It demonstrates that the abstract control frame can make two regimes exchange observable behaviour under specified limits.

Transfer rules:

- In manuscript drafting, coined or playful names should arrive only when the formal object can carry them.
- An introduction should move from a field problem to the structural object quickly, then name the failure condition the method controls.
- Limitations should be written as part of the mechanism. Avoid separate apology paragraphs when the caveat can become a constraint.
- PRL-style compression is useful for titles, abstracts, captions, and conclusion hinges. It is not enough evidence for the whole academic register.

## Platonic Target

The ideal manuscript voice should:

- state the structural object early
- compress mechanical derivation into equations, figures, appendices, and captions
- expand on why the object is the right object
- frame implications without sounding promotional
- use humour only as structural diagnosis
- use metaphor only when it carries formal work
- maintain British English and the Vonnegut rule
- preserve authorial pressure through ordering, contrast, and chosen emphasis

## Gate 1 Transfer From Eppur Si Muove

Source: `EPPUR-PRIMARY`. Status: provisional personal-register calibration, pending academic-corpus confirmation. These are candidates to test, not manuscript rules.

- **Frame first.** Begin from the largest honest structure, then descend to the technical case.
- **Mechanism before name.** Let coined terms, section titles, and theorem names arrive only after the mechanism is visible.
- **Compress after skeleton.** Once the conceptual skeleton is clear, use short hinge sentences and schematic figures to carry settled machinery.
- **Expand at hinges.** Spend prose on motive, consequence, analogy, and the moment where a local result becomes a general object.
- **Use technical objects as thought.** Mathematical objects should organise cognition, not decorate exposition.
- **Correct by constraint.** Replace confessional self-correction with explicit limits, assumptions, and failure modes.
- **Deflate false solemnity.** Use dry structural humour sparingly where it clarifies hierarchy, pretence, or institutional absurdity.

## Reader Questions

- Where do the best papers make a reader feel the frame snap into place?
- Which introductions carry the author without becoming informal?
- Which old manuscript habits dilute the claim?
- Which failed proposals contain a strong framing move trapped in a bad form?
- Which personal-writing moves can be translated into objective academic prose?

## Gate 2 Reader Questions

- Which paper titles are merely labels, and which are compressed arguments?
- Where does the introduction move from field background to Gerard's structural object?
- Which metaphors survive because they name a mechanism?
- Where does the journal format force useful compression?
- Where does the journal format flatten the thought?
- Which collaborator-heavy papers should count as context but not voice evidence?

## Output Needed

This node eventually needs:

- a sentence-level style schema
- an introduction schema
- a claim-and-derivation schema
- a figure-caption schema
- a failure-mode ledger
- a transfer table from personal and correspondence registers
