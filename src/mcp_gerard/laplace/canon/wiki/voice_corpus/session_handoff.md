# Voice Corpus Session Handoff

**Status**: durable close brief for the next session. This is not a Dreamer lifecycle result.

This node records what the Voice Corpus session built, what remains unproven, and how to continue without re-reading the whole thread. It deliberately contains no raw corpus text.

## Built This Session

- Created the Voice Corpus wiki cluster beneath the compact Voice and Author nodes.
- Added source mapping, reader protocol, ingestion gates, register matrix, manuscript, personal, correspondence, admin/proposal, author-signal, author-fact, top-level confluence, and this handoff node.
- Linked the cluster from the wiki root, Voice node, and Author node.
- Added `voice_corpus_reader`, a deterministic chunking skill that writes manifests and chunks under ignored cache paths and keeps stdout clean.
- Added `.codex/voice_corpus_cache/` to `.gitignore`.
- Updated the voice verifier so Markdown syntax does not trigger false voice failures.
- Added tests for the chunker and Markdown voice-check behaviour.

## Gate 1: Personal Calibration

Source: `EPPUR-PRIMARY`.

What happened:

- Located `Eppur Si Muove` in Google Drive.
- Cached the source in ignored working cache.
- Ran bounded reader passes for voice mechanics, author method, and facts.
- Admitted distilled claims into canon, not raw text.
- Added privacy-tiered author facts.

Correction made later:

- `Eppur Si Muove` is now treated as a high-signal personal calibration specimen, not the primary artefact for all writing.
- It proposes candidate mechanics. It does not rule manuscript, correspondence, canon, or admin/proposal registers.

Risk:

- The Drive export path echoed raw source into the thread before containment. This is the largest operational lesson. Future source acquisition should write directly to ignored cache without printing content.

## Gate 2: Academic Discovery

Sources located:

- Zotero collection `ZOTERO-MY-PAPERS`, collection key `HSSAXTCW`.
- Zotero child collection `ZOTERO-MY-PAPERS-ARTICLES`, collection key `VHBHN73T`.
- Local Overleaf bundles for admin/proposal, academic review, and personal writing.

Metadata admitted:

- The authored and co-authored academic spine runs from 2017 to 2025 in Zotero metadata.
- First reader-batch candidates are listed in the Manuscript Register.
- Public bibliographic facts were added to the Author Fact Ledger.

Contained but not read:

- `ZOTERO-UQW3Y5J2`, `Driven Imposters: Controlling Expectations in Many-Body Systems`.
- Zotero indexed full text was written to `.codex/voice_corpus_cache/raw/ZOTERO-UQW3Y5J2.txt`.
- `voice_corpus_reader` chunked it into three academic chunks with a manifest at `.codex/voice_corpus_cache/manifests/ZOTERO-UQW3Y5J2.json`.
- Subagent reader passes were attempted but failed because the session hit a usage limit. No manuscript-register claims from this paper have been admitted yet.

Correction made later:

- Treat hanging subagents as a structural failure, not bad luck. Future academic reader passes should be serial, restartable queue jobs with one live reader call at a time. A stalled call blocks one chunk, not the session.

## Top-Level Confluence

An advisory review was added at [Top-Level Confluence Review](canon://voice_corpus/top_level_confluence.md).

Current judgement:

- The top-level wiki, Voice node, and Author node are directionally confluent with the discovered voice.
- The root should later become less introductory and more operational: define the engine, state load order, route deep evidence only when needed.
- The Voice node should keep the one-voice principle but add a clearer counterweight against register collapse.
- Do not rewrite the root from `Eppur` alone. Wait for at least one manuscript batch and one correspondence batch.

## Known Risks

- Raw source leakage through connectors.
- Sensitive author facts becoming too easy to load.
- Single-source overfit from `Eppur`.
- Bibliographic authorship being mistaken for prose ownership.
- Preprint and publication duplicates in Zotero.
- Overleaf review bundles containing judgement voice rather than manuscript voice.
- Subagent limits interrupting the planned multi-reader architecture.
- Hanging subagents interrupting the close path before ledgers are written.
- Dreamer lifecycle and assessment instability. Do not run deprecations, refinements, or forge actions from this corpus work until the close machinery is known clean.

## Navigation For The Next Session

Start with:

- [Voice Corpus](canon://voice_corpus/index.md)
- [Ingestion Plan](canon://voice_corpus/ingestion_plan.md)
- [Source Map](canon://voice_corpus/source_map.md)
- [Manuscript Register](canon://voice_corpus/manuscript_register.md)
- [Author Fact Ledger](canon://voice_corpus/author_fact_ledger.md)
- [Top-Level Confluence Review](canon://voice_corpus/top_level_confluence.md)

Useful protocols:

- `context_firewall`
- `voice_corpus_reader`
- `focus_rail`
- `reference_archaeologist`
- `corpus_librarian`
- `identity_ledger`
- `evidence_ledger`
- `reconciler`
- `session_closer`

Do not treat that list as a lifecycle recommendation. It is a routing note.

## Next Concrete Step

Run the first academic reader pass on `ZOTERO-UQW3Y5J2` using the manifest and chunks already in ignored cache. Do it as a serial reader queue, not parallel subagents. Each chunk job should return distilled observations only:

- manuscript voice mechanics
- author-method signals
- factual claims, if any, with privacy tier and confidence
- chunk IDs or paragraph ranges
- no raw quotations beyond tiny fragments when strictly needed

After that, update the Manuscript Register with provisional Gate 2 claims and compare them against the Gate 1 candidate mechanics.
