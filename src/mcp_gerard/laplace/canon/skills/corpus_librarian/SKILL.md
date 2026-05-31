---
name: corpus_librarian
description: "[EXPERIMENTAL] Owns the shared literature store the literature_scout rail draws on. One global corpus.bib across projects - each record carries a distilled claim, a concept cluster, and a trust status - synthesised on demand into a cluster guide and queried by a result's Literature face. Ingestion never blocks, trust is promoted deliberately."
---
# corpus_librarian

**Status: [EXPERIMENTAL]**

## Purpose
`literature_scout` names a shared literature store as an open design - one flexible corpus
across projects, so a reference gathered once is never re-gathered, and a paper's citations
reflect the whole accumulated literature rather than whatever was to hand. This skill is that
store and its discipline. The scout locates and reads - the librarian holds, distils, and serves.

The store has one job the per-project `references.bib` cannot do: it lets a reference be **one
object with two projections**. In `corpus.bib` it is a full record with a distilled claim and a
trust status. In a result's `Literature` face it is a citekey query - `established_by`,
`contested_by`, a context sentence, a novelty sentence. The reference text lives once and is
audited once. Fix the record, and every citing face is correct without a single face being reopened.

## The store
One global `corpus.bib` (biblatex), engine-owned and cross-project - not a per-project bib. Keep
it a real `.bib` at a discoverable path so standard tooling still reads it. Standard fields are
untouched. The corpus carries these extension fields (biblatex `usera`-`userf` or custom fields):

```bibtex
@article{firstauthorYEARword,
  author = {}, title = {}, journal = {}, year = {}, doi = {},   % standard, untouched
  tldr   = {},   % one sentence: objective + result. Describes the paper.
  claim  = {},   % one sentence: the single most citable proposition. DECLARES, not describes.
  status = {},   % unverified | provisional | borrowed | partial:<restriction> | contested | established | open-gap
  cluster= {},   % concept-cluster label(s); set by a clustering pass, may be empty at ingest
  support= {},   % supporting | contrasting | mentioning  (how the field received it; lazy, optional)
  keywords = {}, % concept tags against keywords.yaml beside corpus.bib
  provenance = {}, % comma-separated project keys that cite this record
  added  = {},   % ISO date of first ingestion; immutable
  scout  = {},   % which session/agent ingested it; immutable
}
```

`tldr` describes, `claim` declares - the distinction is load-bearing. The Literature face resolves
a citekey to its `claim` and `status`, so a wrong `claim` poisons every face that cites it. Guard
`claim` and `status`. A wrong `tldr` is cosmetic.

## Two-tier trust (ingestion never blocks)
A blocking confirmation gate becomes a rubber stamp under deadline. So ingestion is always open and
trust is promoted separately:

- A new record enters at `status: unverified`, its `claim` provisional. It is usable and visibly
  untrusted.
- `status: borrowed` marks a claim imported wholesale from prior internal work or a trusted draft
  without fresh confirmation - the honest tag for a deadline cheat. Borrowed is not established.
- Promotion to `status: established` is the only step that needs the author, done in deliberate
  batches, never inline at ingest. A periodic dream may flag a stale-`established` record for re-look
  (carry a `reviewed:` date if the field has moved on).

**The trust boundary is enforced at query time, not ingest time.** `literature_scout` populates a
Literature face's `established_by` only from `established` records. Provisional, borrowed, and
unverified records surface as candidates pending confirmation - never as settled support.

## Citekeys
Deterministic: `firstauthor` (lowercased, ascii-folded) + `year` + first significant `word` of the
title. The validator enforces the pattern and rejects duplicates, so two projects ingesting the
same paper converge on one key rather than colliding.

## The synthesis layer (cluster guide)
A concept cluster is the set of records sharing a `cluster` label. On demand - when a section
targeting that cluster is opened - the librarian emits an **ephemeral cluster guide**: anchor papers,
established claims, partial/contested claims, open gaps, a chronological spine, and the novelty
boundary for the current project. The shape is the three-part state-of-the-art: where the field is
now, how it got here, where it could go next. The guide is generated and handed to drafting as
context - it is never stored. `corpus.bib` is the only persistent artifact.

## The three modes
1. **Ingest.** Given a DOI / arXiv id / bib snippet, write a record with standard fields,
   author-or-LLM-drafted `tldr` and `claim` (provisional), `status: unverified` (or `borrowed`),
   a deterministic citekey, and `provenance` set to the calling project. Run the validator.
2. **Cluster guide.** Given a cluster label or concept query, read matching records, group by
   status, sort the spine by year, and emit the guide. Established-only for trusted claims.
3. **Provenance update.** Given a project key and the citekeys its manuscript used, append the key
   to each record's `provenance`. A natural `session_closer` sync step.

The generative steps - drafting the `claim`, writing the `novelty` sentence - are host-executed by a
grounding-capable model, never automated by the backing script. The script is structural only.

## Backing
`scripts/check_corpus.py` - validates that every record carries the required fields, that `status`
is in the allowed vocabulary, that citekeys match the deterministic pattern, and that no key is
duplicated. Run it on ingest and at session close.

```
laplace_run(skill="corpus_librarian", target="<path_to_corpus.bib>")
```

The cluster-guide synthesis (`cluster_guide.py` - read, filter by cluster, group by status, emit)
is the natural next backing script. Until it lands, run mode 2 as a judged read of the corpus.

## Relation to siblings
- `literature_scout` is the rail front-end - it targets a claim, searches, reads, and decides what
  each source establishes. The librarian is the back-end store and synthesis. The scout hands a
  confirmed source to the librarian to ingest.
- `deep_corpus_scout` (backlogged) is the batch sibling - bulk extraction from a tarball or a large
  repository. The librarian is curated single-record ingest plus synthesis. Distinct skills.
- `evidence_ledger` holds the per-result Literature face that queries this store.
