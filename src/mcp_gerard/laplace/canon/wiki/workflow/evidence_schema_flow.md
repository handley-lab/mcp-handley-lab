# Evidence-Schema Flow (one object, many faces)

A result is not a pile of separate documents - a derivation here, a literature note there, a
figure somewhere else. It is **one object seen from several sides**. This node defines how the
faces link to that object and flow into a finished manuscript without any fact living in two places.
`evidence_ledger` defines the per-claim record, `reconciler` defines propagation, `corpus_librarian`
holds the literature - this node is the architecture that binds them.

## The one object and its projections
The canonical object is the **derivation** of a result - the heavy, human-authored source of truth.
Every other face is a *projection* of it, never a copy:

- **Machine map** - assumptions, technique, recipe, check, figure. Partly auto-extracted from the
  derivation's structured header, partly human-filled (the check script, the figure path).
- **Literature face** - a query into `corpus_librarian`: `established_by` / `contested_by` citekeys
  plus a context and novelty sentence. The prior-work prose lives once, in the corpus.
- **Scaffolding** - motivation, explains, licences. The pre-written rhetorical moves, authored
  against the derivation, flagged stale for review when the derivation's commitments change.

Faces are addressed by `result_id`, not by file path, so a file can move without breaking a link.

## Ownership: what the engine computes, what the human writes
The reconciler never overwrites prose. The split is fixed:

| Reconciler-owned (computed / parsed) | Human-owned (prose / judgement) |
|---|---|
| assumptions, citations parsed from the header | the derivation narrative |
| check status, data-figure path | the check script itself |
| claim status (computed from the chain) | scaffolding motivation / explains / licences |
| corpus claim text resolved into a face | the local context / novelty sentences |

A missing structured slot does not block the human - it degrades to `UNVERIFIED` and the engine
steps aside. The tool serves the drafting, never the reverse.

## The narrative master doc (NMD)
The NMD is a **composition manifest**, not a prose document. It is an ordered set of transclusion
directives over faces - `include R_i/scaffolding.motivation`, `include R_i/derivation.statement`,
`include R_i/scaffolding.consequence` - plus the one thing it genuinely owns: **section-level
connective prose**, the cross-result transitions and section framing. Result-local prose lives in
the faces. When a paragraph's home is in doubt it goes to the NMD, because that is where the
whole-document pass happens. Duplication is forbidden and checkable - a passage that is transcluded
may not also be inline.

A render flag toggles proof depth (brief stubs vs full proofs), so one manifest produces a
conference version and a journal version from the same source.

## The render-then-read loop (how the voice survives transclusion)
Prose assembled from independently-written faces fractures the voice at the seams - a direct threat
to the one-voice discipline. The mitigation is not to abandon composition but to **render, then
read as one document**. The pipeline emits a full-prose draft from the manifest. The author
voice-edits *that whole document*, and the edits back-propagate to the owning face - never lost,
never stranded in the rendered output. The manifest is the plumbing - the rendered draft is where
the single mark across the whole work is enforced. The paper is never shipped as concatenated faces.

## The three failure modes this architecture is built against
Every mechanism here is shaped by one of three maladaptations a naive version would breed:

1. **Cry-wolf.** A staleness signal that fires on every typo is ignored, and an ignored signal is
   worse than none - it gives false confidence. So: hash the committed content, not the bytes;
   grade staleness by severity (`STALE-direct` vs advisory `STALE-upstream`); signal only on a
   genuine transition.
2. **The tool shaping the work.** A schema that dictates how a derivation is written - to please a
   parser, to silence a flag - has inverted the relationship. So: every automated slot is optional
   and degradable; missing structure yields `UNVERIFIED` and the engine gets out of the way.
3. **Deadline-vs-rigour.** A system only usable with time to spare is abandoned exactly when the
   author is busy. So: every gate has a proceed-anyway path that records the debt -
   `unverified` / `provisional` / `borrowed` - rather than blocking. The honest tag is the
   mechanism, not the locked door.

The honest tell: mitigations 1 and 3 and the inter-result rule all reduce to the same move -
**distinguish what genuinely changed from what was merely touched.** Get that right and the rest follows.
