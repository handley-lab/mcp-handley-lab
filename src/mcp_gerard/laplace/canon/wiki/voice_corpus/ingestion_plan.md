# Voice Corpus Ingestion Plan

**Status**: execution scaffold. Gate 1 has been ingested. Gate 2 metadata discovery has started.

The corpus should be admitted in gates. Each gate produces a private evidence ledger, a short register synthesis, and candidate wiki edits. The wiki receives only claims that survive firewall review.

## Gate 0 - Containment

- Confirm source classes and ingestion windows.
- Create ignored local cache paths for raw extraction and chunk ledgers.
- Salt and hash source IDs before reader prompts.
- Run one dry reader pass on a tiny non-sensitive sample.

**Tooling status on 2026-05-31**: `voice_corpus_reader` exists as a deterministic chunking skill. It writes manifests and chunk files under `.codex/voice_corpus_cache/`, preserves paragraph, character, and byte ranges, and keeps stdout free of source text. `EPPUR-PRIMARY` has a manifest and one chunk covering paragraphs P1-P50.

## Gate 1 - Calibration

- Read `Eppur Si Muove` primary Google Doc through a calibration reader.
- Run a second author-method reader on the same source.
- Run a fact reader on the same source, producing privacy-tiered claims about Gerard.
- Compare against the rendered PDFs only after the primary text is distilled.
- Update [Eppur Si Muove](canon://voice_corpus/eppur_si_muove.md), [Personal Register](canon://voice_corpus/personal_register.md), [Register Matrix](canon://voice_corpus/registers.md), [Author Signals](canon://voice_corpus/author_signals.md), and [Author Fact Ledger](canon://voice_corpus/author_fact_ledger.md).

**Gate 1 status on 2026-05-31**: primary text ingested through three read-only reader passes. The canon now admits the first distilled claims. Cross-register status remains provisional until later gates.

## Gate 2 - Academic Register

- Use Zotero for published or citable academic works.
- Use Overleaf or local LaTeX exports for active and abandoned manuscripts.
- Separate published, near-published, abandoned, and proposal-adjacent material.
- Update [Manuscript Register](canon://voice_corpus/manuscript_register.md).

**Gate 2 status on 2026-05-31**: Zotero local API is available. The `My Papers` collection has been read at metadata level. Three Overleaf bundle downloads have been located by filename inventory only: admin/proposal, academic-review, and personal-writing bundles. `ZOTERO-UQW3Y5J2` has now been read through serial full-text reader jobs as the first PRL-style academic anchor.

Next Gate 2 actions:

- choose the first academic reader batch from the source handles in [Source Map](canon://voice_corpus/source_map.md)
- acquire full text locally only after the handle list is fixed
- chunk each chosen source with `voice_corpus_reader`
- run manuscript voice, author-method, and fact readers as restartable serial queue jobs on chunk handles rather than raw dumps
- admit only register claims that can name a source handle and locator
- continue Gate 2 with at least one humour-bearing paper and one recent sole-author or first-author source before promoting academic claims to cross-register law

Gate 2 execution constraint:

- Do not spawn parallel subagents for reader passes. Use one stateless reader call at a time, write the chunk ledger immediately, and mark a stalled chunk `blocked` instead of letting the whole session hang.

## Gate 3 - Personal Register

- Ingest personal essays and fragments in chronological bands.
- Mark old-self evidence separately from durable voice mechanics.
- Compare every strong claim against Gate 1 before canon admission.

## Gate 4 - Correspondence Register

- Search Gmail Sent from 2024-05-31 to 2026-05-31.
- Strip quoted replies, signatures, legal footers, and recipient-identifying details.
- Cluster by communicative action: refusal, encouragement, explanation, decision, repair, logistics.
- Update [Correspondence Register](canon://voice_corpus/correspondence_register.md).

## Gate 5 - Admin and Proposal Register

- Ingest proposals and administrative documents as constraint evidence.
- Extract salvageable framing moves and failure modes.
- Do not let compliance language define the target voice.

## Gate 6 - Cross-Register Synthesis

- Give the synthesis reader only distilled ledgers.
- State the invariant voice.
- State the ideal schema for each register.
- State transfer rules into manuscript drafting.
- State failure modes and correction moves.
- State which facts are relevant context for future collaboration, and which should stay private or unloaded by default.

## Gate 7 - Verification

- Re-run `laplace_orient` for voice-corpus and manuscript-drafting goals.
- Check that top-level Voice and Author nodes remain compact.
- Check that deep nodes carry provenance, evidence quality, and register limits.
- Check that factual claims carry confidence, temporal status, privacy tier, and provenance.
- Run Laplace unit tests after canon edits.
- Check the reader queue: no pending live worker, every chunk is `done`, `blocked`, or deliberately `skipped`.
