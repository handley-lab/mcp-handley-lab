---
name: voice_corpus_reader
description: "[EXPERIMENTAL] Prepares private voice-corpus sources for bounded reader agents: cache raw text outside git, split it into stable provenance chunks, and emit manifests that let readers return claims without leaking source text into canon."
---
# voice_corpus_reader

**Status: [EXPERIMENTAL]**

## Purpose

The Voice Corpus needs large private sources, but the first calibration pass showed the failure mode: a connector can echo raw text into the transcript before the evidence has been contained. This skill owns the containment layer before any reader sees the source.

It does not analyse the writing. It makes the source safe to analyse.

## Protocol

1. **Acquire locally first.** Put source text in an ignored cache path. Do not paste raw source into a prompt, canon node, or handoff.
2. **Chunk deterministically.** Split on structural boundaries first: paragraphs, sections, messages, or LaTeX blocks. Fall back to size only when structure is absent.
3. **Preserve provenance.** Every chunk must carry source handle, source class, register, source hash, chunk ID, paragraph range, character range, and byte range.
4. **Keep stdout clean.** Backing scripts report counts and paths only. They never print source text.
5. **Send readers handles, not dumps.** A bounded reader receives a manifest plus one chunk or chunk path. It returns distilled observations, factual claims, privacy tiers, and evidence locators.
6. **Admit only distilled claims.** Canon nodes receive claims with provenance and limits. Raw source and long summaries stay in ignored cache.

## Backing

`scripts/chunk_source.py` prepares one UTF-8 text source:

```text
laplace_run(
  skill="voice_corpus_reader",
  target="<source.txt>",
  args=[
    "--source-handle", "EPPUR-PRIMARY",
    "--register", "personal",
    "--source-kind", "google_doc",
    "--cache-root", ".codex/voice_corpus_cache",
  ],
)
```

The script writes:

- `manifests/<source-handle>.json`
- `chunks/<source-handle>/<chunk-id>.txt`

It returns a summary only: source handle, chunk count, manifest path, and chunk directory.

## Register Values

- `calibration`
- `academic`
- `personal`
- `sent_gmail`
- `admin_proposal`

## Invariants

- Raw source is private working material.
- Chunk IDs must be stable for unchanged content.
- The same source, handle, register, and salt must produce the same manifest.
- Changing content must change the source hash and affected chunk IDs.
- Sensitive and third-party facts are routed to the author fact rail, never into the compact Author node.
