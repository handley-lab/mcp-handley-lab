# Engine Recovery - Session Handoff (2026-05-31)

A pseudo-dream transcript. Written at close so the next session inherits the state, not a heroic story. This was a recovery session: the engine was wedged, codex and several Claude sessions had piled up, and there was un-ingested debt. It is now in shape. Read this, then carry on.

## What this session did

Seven commits on `mcp-gerard` `feat/laplace-engine` (plus one doc note on physics_paper_orchestra `master`):

- `4277bee` / `4a7cbc0` - killed the `laplace_assess` 30-minute hang. Root cause was NOT codex and NOT engine rot. It was a Windows subprocess pipe deadlock: Claude Code's own background `git -c core.fsmonitor=true` spawns detached fsmonitor daemon processes that inherited the engine's git stdout pipe, so `subprocess.run` blocked forever draining a pipe that never hit EOF, defeating its own timeout. Added a per-tool `watchdog.guard` (no `laplace_*` handler can hang the caller again).
- `0a577ae` - the load-bearing fix: `gitio.run_git` captures git via temp files, not pipes. No pipe handle exists for a daemon to inherit, so timeout is always honoured. Both engine git callers route through it. Verified live and under deliberate daemon churn (0.15s).
- `6d9b649` - reconciled the ZOTERO-UQW3Y5J2 chunk-count provenance (manifest is authoritative: four chunks).
- `3c1ba3c` - synthesised ZOTERO-9IFREHKD (9/9 reader jobs were done but unsynthesised). It corroborates the existing manuscript mechanics, adds one public funding fact. Triaged the reader queues.
- `c2ee5b9` - scaffolded the `web` and `talks` domains on the generate-stage-refine shape.
- `4498efb` - fixed the no-op-dream window leak (a preview consumed the assessment window). The boundary now advances only on a real applied transition.
- `55eb19f` - the first genuine lifecycle dream the engine has committed: `voice_corpus_reader` promoted to core (earned, 12 uses), `idea_foundry` and `orient_recovery` deprecated (offered, never used).

34 tests pass. The forensic verdict on the original fear: codex did not break the engine. Its `tool.py`/`verify.py` edits were hang-defenses and a correct Markdown-aware voice fix. No rollback was warranted and none was done - a rollback would have destroyed working value.

## Current engine state

- Healthy. assess, verify, dream all run clean. The dream loop is stable (a second dream is a proper no-op that does not re-consume the window).
- Lifecycle is curated and committed. `orient_recovery` was deprecated for non-use - reversible via `laplace_rollback 55eb19f` if that domain=null recovery branch is wanted back.
- `web` and `talks` domains exist as scaffolds. Their skill slots are named as forge targets, deliberately empty. Forge them on first real use, not before, or the dreamer will deprecate them as unused.

## Open threads for the next session

- **Corpus reader backlog needs provider credit.** ZOTERO-9IFREHKD is done and synthesised. ZOTERO-27MBG7CN (21 pending) and ZOTERO-UNGFXZ9P (24 pending) await a reader pass via the private worker `.codex/voice_corpus_cache/tools/reader_queue_worker.py`. The wall was quota, not the engine. Prefer contrast sources (humour-bearing, sole-author, non-manuscript register) over more of the same.
- **Live MCP server is stale.** Restart Claude Code so the running server reflects the promoted/deprecated skills and the new `web`/`talks` domains. Engine state on disk is correct and committed.
- **First real web or talks work** is the trigger to forge the first skill. Web: wrap a repo helper (`check_html.py` or `check_img.py`) as a `web_ledger` backing. Talks: hand-build one spine from a manuscript before forging `talk_spine_generator`. Adaptive Normal Form is the natural first manuscript once its figure rail lands.
- **`mccaul_protocol` sits at net -3 feedback** but stays core - assess flags it for refine but never demotes a core skill on feedback alone (known gap, AUTONOMY_BACKLOG). Worth a deliberate look.
- **Kernel-vs-routine doc gap** still open in AUTONOMY_BACKLOG: `laplace_dream` is the deterministic kernel, the full R&R is the dreamer persona's closer-run routine. README should state the distinction.

## Guardrails and notes

- `render.py` and `.mcp.json` carry pre-existing local edits (a doc reword and an absolute-path tweak). Left uncommitted on purpose - not mine to fold in.
- Optional environment hardening: set `core.fsmonitor` to false in the global git config. Stops the daemon proliferation at the source. Untaken - the author's call. The engine is immune regardless now.
- A telemetry backup sits at `~/.mcp-gerard/laplace/telemetry.jsonl.bak` (made before removing one spurious dream marker). Safe to delete once the loop is trusted.
- Server and daemon leak: every Claude/codex session spawns an `mcp-laplace.exe` and none are reaped. Reap stale ones with a CIM filter on the laplace process names (`mcp-laplace`, the `mcp_gerard\laplace` path) and the fsmonitor daemon when they clutter.
