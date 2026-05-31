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

Contained and read:

- `ZOTERO-UQW3Y5J2`, `Driven Imposters: Controlling Expectations in Many-Body Systems`.
- Zotero indexed full text was written to `.codex/voice_corpus_cache/raw/ZOTERO-UQW3Y5J2.txt`.
- `voice_corpus_reader` chunked it into four academic chunks with a manifest at `.codex/voice_corpus_cache/manifests/ZOTERO-UQW3Y5J2.json`.
- Twelve serial queue jobs completed: `voice`, `author_method`, and `facts` for each chunk.
- Manuscript-register claims from this source have now been admitted as provisional PRL-style evidence.

Correction made later:

- Treat hanging subagents as a structural failure, not bad luck. Future academic reader passes should be serial, restartable queue jobs with one live reader call at a time. A stalled call blocks one chunk, not the session.
- The serial queue worker caught one raw-leak attempt and one invalid fact locator before canon admission. Keep those guardrails.

Subagent audit note:

- A later subagent audit was run against the manifest at `.codex/voice_corpus_cache/manifests/ZOTERO-UQW3Y5J2.json`.
- The audit completed `P0001-P0002` and `P0003-P0004`, and confirmed the main manuscript-register mechanics: title as compressed argument, PRL compression, structural humour under formal licence, constraint as authority, contrast as explanatory machinery, and figure logic as compression.
- The audit did not complete the remaining chunks `P0005` and `P0006`. Do not use that audit as conclusion-level evidence.
- Provenance mismatch RECONCILED (2026-05-31, next session): the manifest is authoritative and holds **four** chunks - `P0001-P0002`, `P0003-P0004`, `P0005-P0005`, `P0006-P0006`. The earlier four-chunk reader note was correct. The audit note that called this a "three-chunk manifest" was wrong - it conflated the two single-paragraph chunks P0005 and P0006. Net: the audit reached 2 of the 4 chunks.

## Emergency Handoff - 2026-05-31

This section records the state at the user-requested stop. It is deliberately blunt so the next session can audit the damage instead of inheriting a heroic story.

Committed and pushed checkpoint:

- Commit `cbd163f` on `origin/feat/laplace-engine`: `Stabilize voice corpus reader queue`.
- That commit contains the durable queue-generation code, serial-reader protocol, timeout changes, and tests.

Canon edits after that checkpoint, staged for the next commit:

- `ZOTERO-UQW3Y5J2` has been admitted as the first full-text academic anchor.
- Manuscript-register claims are provisional and PRL-specific: title as compressed argument, mischief formalised into constraint, failure converted into admissibility, compression by named machinery, and application as structural proof.
- Author fact ledger gained only public/bibliographic facts from `ZOTERO-UQW3Y5J2`. One invalid reader fact was rejected.

Private cache state:

- `ZOTERO-UQW3Y5J2`: 12/12 reader jobs done, synthesised, admitted to canon as provisional Gate 2 evidence.
- `ZOTERO-9IFREHKD`: 9/9 reader jobs done. It is **not** yet synthesised and **not** admitted to canon.
- `ZOTERO-27MBG7CN`: 3 jobs done, 1 job manually marked `blocked` after the user interrupted the run, 20 pending. The live worker processes were stopped.
- `ZOTERO-UNGFXZ9P`: raw text extracted and queue created, 24 jobs pending, no reader outputs.

Known wreckage to audit next:

- API route instability: OpenAI returned insufficient quota, Anthropic returned low-credit, Gemini flash-lite hit the free-tier daily request cap, then Gemini flash was used.
- Reader output quality is uneven. The raw-leak detector caught over-literal outputs. One reader produced an impossible byte span and that claim was rejected.
- The synthesis for `ZOTERO-UQW3Y5J2` contains useful signal but also generic content-summary noise in the private ledger. The canon admission intentionally kept only a narrower set of claims.
- The private queue worker lives under `.codex/voice_corpus_cache/tools/reader_queue_worker.py`, which is ignored and not committed. The committed durable part is the queue format and protocol, not that private worker.
- `.mcp.json` and `src/mcp_gerard/laplace/render.py` have unrelated unstaged local edits that were not part of the corpus commit.

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

Continue by auditing the wreckage before ingesting more. Do this order:

- inspect `.codex/voice_corpus_cache/readers/ZOTERO-27MBG7CN/queue.jsonl` and decide whether to retry, skip, or discard the blocked job
- synthesise `ZOTERO-9IFREHKD` only from its completed reader JSON, then decide whether any claim is safe enough for canon
- only then resume `ZOTERO-27MBG7CN` or `ZOTERO-UNGFXZ9P`
- run verification before any Dreamer lifecycle mutation

The next academic pass should deliberately add contrast rather than more of the same:

- one humour-bearing academic source, such as `ZOTERO-27MBG7CN`
- one recent sole-author or first-author source, such as `ZOTERO-UNGFXZ9P` if full text is available
- one non-manuscript register source from correspondence or admin/proposal before any top-level Voice rewrite

## Backlog Triage - 2026-05-31 (next session, post engine fix)

The engine hang is fixed (assess no longer deadlocks - see the gitio temp-file fix and the tool watchdog). The corpus backlog was triaged in that order:

- `ZOTERO-UQW3Y5J2`: 12/12 done, synthesised, admitted. Chunk-count provenance reconciled to four chunks (above).
- `ZOTERO-9IFREHKD`: 9/9 done and now **synthesised** at `.codex/voice_corpus_cache/ledgers/gate2_zotero_9ifrehkd_synthesis.md`. Conservative canon admission made: one public funding fact (Keck Foundation, ARO) added to the Author Fact Ledger, and a corroboration note added to the Manuscript Register. It confirms the UQW3Y5J2 mechanics, adds no new mechanic or register. Most of its reader output was topic summary and was discarded.
- `ZOTERO-27MBG7CN`: 3/24 done. The one `blocked` job was a false block (manual interrupt at the emergency stop, not a real error) and has been reset to `pending`. State is now 3 done, 21 pending.
- `ZOTERO-UNGFXZ9P`: 0/24 done, all pending. Raw text and queue exist, no reader outputs yet.

Remaining work needs a reader pass over the 21 + 24 pending jobs. That requires the private worker (`.codex/voice_corpus_cache/tools/reader_queue_worker.py`) with a working LLM provider - the constraint here was provider quota, not the queue or the engine. Resume there when credit is available. Per the standing guardrail, run `laplace_verify` before any Dreamer lifecycle mutation, and prefer contrast sources (humour-bearing, sole-author, non-manuscript register) over more of the same.
