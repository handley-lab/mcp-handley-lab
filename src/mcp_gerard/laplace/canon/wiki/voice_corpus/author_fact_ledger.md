# Author Fact Ledger

**Status**: schema scaffold. Evidence pending corpus ingestion.

This ledger records factual claims about Gerard recovered from the corpus. It is adjacent to the voice and author-method records, not a substitute for them. Facts explain the authorial fossil record, but they do not automatically define the writing target.

## Admission Rule

A fact enters this node only when it has:

- a source handle
- a locator or chunk ID
- an evidence type
- a confidence level
- a privacy tier
- a note on whether it is durable, time-bound, or contradicted by later evidence

## Privacy Tiers

- **Public.** Suitable for ordinary project context. May appear in compact form when useful.
- **Internal.** Useful for collaboration but not for broad prompts. Keep in this ledger and load deliberately.
- **Sensitive.** Personal, identifying, relational, health, financial, or otherwise risky. Store as a redacted claim or keep only in private working cache.
- **Third-party.** Primarily about another person. Do not admit unless it is essential and redacted.

## Fact Schema

```yaml
- id:
  claim:
  category:
  source_handle:
  locator:
  evidence_type:
  confidence:
  privacy_tier:
  temporal_status:
  relevance:
  contradictions:
  notes:
```

## Categories

- biography
- education
- career and institutions
- research history
- writing history
- places and movement
- relationships and collaborators
- preferences and tastes
- constraints and obligations
- self-concept and recurring commitments

## Boundary

The fact ledger collects actual information about the author while preserving the same containment discipline as the voice cluster. It should not become a diary, a contact book, or a raw dossier. It is a provenance-backed memory aid for future collaboration and drafting.

## Gate 1 Facts From Eppur Si Muove

Source: `EPPUR-PRIMARY`. Status: single-source facts from a personal essay. Treat as self-report until corroborated.

- **FACT-EPPUR-001.** Claim: Gerard is a physicist. Category: career and institutions. Confidence: 0.95. Privacy: public. Temporal status: durable. Relevance: core professional identity. Caveat: self-report, not CV proof.
- **FACT-EPPUR-002.** Claim: Gerard uses physics, information, energy, vectors, and linear algebra as central conceptual lenses. Category: research history. Confidence: 0.90. Privacy: internal. Temporal status: durable. Relevance: anticipates framing instincts. Caveat: intellectual self-report, not a style rule.
- **FACT-EPPUR-003.** Claim: Gerard attended a Pisa workshop on quantum computation and thermodynamics. Category: research history. Confidence: 0.95. Privacy: internal. Temporal status: historical. Relevance: research-history context. Caveat: exact date not established here.
- **FACT-EPPUR-004.** Claim: entropy and irreversibility are live questions for Gerard. Category: preferences and tastes. Confidence: 0.80. Privacy: internal. Temporal status: durable. Relevance: useful project-context signal. Caveat: inferred from essay framing.
- **FACT-EPPUR-005.** Claim: Gerard has PhD history tied to central London. Category: education. Confidence: 0.90. Privacy: public. Temporal status: historical. Relevance: academic and place context. Caveat: institution and dates not established here.
- **FACT-EPPUR-006.** Claim: Gerard moved back from the US and refers to a former American home. Category: places and movement. Confidence: 0.90. Privacy: internal. Temporal status: historical. Relevance: geographic and life-stage context. Caveat: current residence not established here.
- **FACT-EPPUR-007.** Claim: Gerard is married. Category: relationships and collaborators. Confidence: 0.95. Privacy: internal. Temporal status: durable or unclear. Relevance: household and life-context awareness. Caveat: spouse identity excluded.
- **FACT-EPPUR-008.** Claim: Gerard has or had an older medically vulnerable companion animal. Category: relationships and collaborators. Confidence: 0.90. Privacy: internal. Temporal status: unclear. Relevance: household and emotional context. Caveat: current status may have changed.
- **FACT-EPPUR-009.** Claim: Gerard keeps or carried a diary and uses handwritten note-taking rituals while travelling. Category: writing history. Confidence: 0.80. Privacy: internal. Temporal status: durable or unclear. Relevance: source provenance and working-habit context. Caveat: single-scene evidence.
- **FACT-EPPUR-010.** Claim: Gerard self-identifies with Irish and Roman Catholic background, including altar-serving and confirmation history. Category: biography. Confidence: 0.90. Privacy: sensitive. Temporal status: historical or durable. Relevance: explains religious and cultural references. Caveat: polemical self-description neutralised.
- **FACT-EPPUR-011.** Claim: Gerard describes a strained relationship with academia and universities. Category: career and institutions. Confidence: 0.85. Privacy: internal. Temporal status: time-bound or unclear. Relevance: collaboration context for academic work. Caveat: emotional self-report.
- **FACT-EPPUR-012.** Claim: Gerard has sensitive health and neurodevelopmental context. Category: constraints and obligations. Confidence: 0.90. Privacy: sensitive. Temporal status: historical or time-bound. Relevance: may matter for pacing, accommodations, and care. Caveat: details intentionally redacted.
- **FACT-EPPUR-013.** Claim: Gerard describes smoking at the narrative time and an expectation that it would stop. Category: constraints and obligations. Confidence: 0.90. Privacy: sensitive. Temporal status: time-bound. Relevance: health and stress context. Caveat: may no longer apply.
- **FACT-EPPUR-014.** Claim: Gerard self-reports substance-use risk history and attempts at restraint after a difficult period. Category: constraints and obligations. Confidence: 0.85. Privacy: sensitive. Temporal status: historical or time-bound. Relevance: collaboration should not romanticise harmful states. Caveat: details intentionally suppressed.
- **FACT-EPPUR-015.** Claim: Gerard had life-insurance interactions affected by personal disclosures. Category: constraints and obligations. Confidence: 0.80. Privacy: sensitive. Temporal status: historical. Relevance: administrative context if directly relevant. Caveat: underwriting details omitted.
- **FACT-EPPUR-016.** Claim: Gerard has close friends connected to former US life and London PhD geography. Category: relationships and collaborators. Confidence: 0.75. Privacy: third-party. Temporal status: historical. Relevance: social and movement context only. Caveat: third-party identities and conduct redacted.
- **FACT-EPPUR-017.** Claim: Gerard's self-concept combines science/art tension, intense commitment, and identification with physicist-outsider figures. Category: self-concept and recurring commitments. Confidence: 0.85. Privacy: internal. Temporal status: durable or unclear. Relevance: motivation context without becoming a style rule. Caveat: self-report under heightened essay frame.

## Gate 2 Facts From Zotero Metadata

Source: `ZOTERO-MY-PAPERS`. Status: Zotero metadata from the local library. Treat as bibliographic evidence until checked against public records or source files.

- **FACT-ZOTERO-001.** Claim: Gerard has a 2019 thesis titled `Stochastic representations of open systems`. Category: education. Source handle: `ZOTERO-2TMCRVBA`. Locator: Zotero item metadata. Evidence type: bibliographic metadata. Confidence: 0.90. Privacy: public. Temporal status: historical. Relevance: corroborates PhD-era open-systems research. Caveat: Zotero metadata, not official degree record.
- **FACT-ZOTERO-002.** Claim: Gerard's publication spine in the local Zotero `My Papers` collection runs from at least 2017 to 2025. Category: research history. Source handle: `ZOTERO-MY-PAPERS`. Locator: collection key `HSSAXTCW`. Evidence type: Zotero collection inventory. Confidence: 0.85. Privacy: public. Temporal status: historical and continuing. Relevance: gives chronological structure for academic voice ingestion. Caveat: local library may include duplicates or preprint counterparts.
- **FACT-ZOTERO-003.** Claim: Gerard's recorded research topics include open quantum systems, stochastic representations, quantum and Koopman dynamics, control of many-body observables, optical indistinguishability, superoscillations, high harmonic generation, photonic reservoirs, and quantum complexity. Category: research history. Source handle: `ZOTERO-MY-PAPERS`. Locator: collection titles and item metadata. Evidence type: bibliographic metadata. Confidence: 0.85. Privacy: public. Temporal status: durable. Relevance: topic map for manuscript-register readers. Caveat: topic labels inferred from titles.
- **FACT-ZOTERO-004.** Claim: Gerard has first-author or sole-author metadata records in the academic spine, including `Driven Imposters`, `How to win friends and influence functionals`, `Superoscillations Deliver Superspectroscopy`, and `Free Snacks in Quantum Complexity`. Category: writing history. Source handle: `ZOTERO-MY-PAPERS`. Locator: item keys `UQW3Y5J2`, `27MBG7CN`, `9IFREHKD`, `UNGFXZ9P`. Evidence type: creator metadata. Confidence: 0.85. Privacy: public. Temporal status: historical. Relevance: prioritises sources where authorial voice is more likely to be visible. Caveat: authorship position is not the same as prose ownership.
- **FACT-ZOTERO-005.** Claim: Gerard's recent research metadata includes reservoir-computing work in 2025, including `Unwrapping photonic reservoirs` and `Minimal quantum reservoirs with Hamiltonian encoding`. Category: research history. Source handle: `ZOTERO-MY-PAPERS`. Locator: item keys `Q6RYZNSE`, `4KPJQHKR`, and `ZMHXNSKD`. Evidence type: bibliographic metadata. Confidence: 0.85. Privacy: public. Temporal status: current or recent. Relevance: helps future drafting load current academic context. Caveat: publication and preprint relationships need deduplication.
- **FACT-ZOTERO-006.** Claim: The Zotero child collection records public-facing academic context, including a 2025 Kharkiv Quantum Seminar entry and an Institute for Optical Science event page for `Malleable light: From Single Atom Computing to Superspectroscopy`. Category: career and institutions. Source handle: `ZOTERO-MY-PAPERS-ARTICLES`. Locator: item keys `X85KTHPU` and `HCTPQMXJ`. Evidence type: Zotero webpage and video metadata. Confidence: 0.75. Privacy: public. Temporal status: historical. Relevance: presentation and public-profile context. Caveat: local metadata, not independently verified here.
