# Voice Corpus Source Map

**Status**: Gate 2 source discovery in progress. Source handles are recorded before text ingestion.

This node records where the corpus lives and how each source class should enter the synthesis. It is a map, not a dump.

## Source Classes

- **Calibration writing.** Initial source: Drive document `Eppur Si Muove`. Role: high-signal personal specimen. Boundary: read first, distil carefully, but do not grant it authority over every register.
- **Academic papers.** Initial source: Zotero library, Overleaf exports, local LaTeX projects. Role: manuscript register and technical thought. Boundary: treat published or near-published work as stronger evidence than abandoned drafts.
- **Personal writing.** Initial source: attached Overleaf exports, Drive, or local archives. Role: full voice, metaphor, rhythm, emotional and conceptual movement. Boundary: separate durable voice from time-bound self-state.
- **Sent Gmail.** Initial source: Gmail Sent, initial window 2024-05-31 to 2026-05-31. Role: correspondence register, direct address, decision style. Boundary: metadata and distilled patterns only unless a short excerpt is essential.
- **Admin and proposals.** Initial source: Overleaf exports, Drive files, local drafts. Role: constraint evidence and failure modes. Boundary: salvage tactics and recurring pressure, not target voice.
- **Author facts.** Initial source: all source classes. Role: build a provenance-backed memory of actual facts about Gerard. Boundary: separate factual claims from voice prescriptions and privacy-tier them.

## Source Registry

- **EPPUR-PRIMARY.** Source: Google Drive. Title: `Eppur Si Muove`. ID: `1P2KbItbb6HcEAF-2krKjzGaCfXipzNK_0gJWeCULsBI`. Date evidence: created 2025-05-01, updated 2026-05-19. Role: high-quality personal calibration specimen. Status: Gate 1 ingested.
- **EPPUR-PDF.** Source: Google Drive. Title: `Eppur Si Muove.pdf`. ID: `1bq9XkHQ8tAJpZs3DF-AntlB-B76iGJiL`. Date evidence: updated 2025-07-04. Role: rendered comparison copy. Status: located, not ingested.
- **EPPUR-MASTER-A.** Source: Google Drive. Title: `Eppur Si Muove -Master.pdf`. ID: `1-2GZntO2g4kRDt-1emyPZLkS4xuF3AX7`. Date evidence: created 2025-05-09. Role: earlier rendered variant. Status: located, not ingested.
- **EPPUR-MASTER-B.** Source: Google Drive. Title: `Eppur Si Muove -Master.pdf`. ID: `1guHyp-6yQ9jTriyl7s4Qnpm8M6FAhzeq`. Date evidence: updated 2025-05-08. Role: earlier rendered variant. Status: located, not ingested.
- **EPPUR-FRAGMENTS.** Source: Google Drive. Title: `Eppur Si Muove - fragments`. ID: `1FBjyD0YTytaU377sZarSDziyGgdWFy3d524n1RUX41w`. Date evidence: updated 2025-05-01. Role: fragmentary drafting evidence. Status: located, not ingested.
- **ZOTERO-MY-PAPERS.** Source: Zotero. Collection key: `HSSAXTCW`. Role: authored and co-authored academic spine. Status: Gate 2 metadata located, no full text ingested.
- **ZOTERO-MY-PAPERS-ARTICLES.** Source: Zotero. Collection key: `VHBHN73T`. Role: talks, CV, coverage, and article-adjacent context. Status: Gate 2 metadata located, no full text ingested.
- **OVERLEAF-ADMIN-20260531.** Source: local download. File: `C:\Users\gerar\Downloads\Overleaf Projects (34 items) (1).zip`. Role: applications, CVs, research statements, teaching statements, and proposal material. Status: located by filename inventory only.
- **OVERLEAF-ACADEMIC-REVIEW-20260531.** Source: local download. File: `C:\Users\gerar\Downloads\Overleaf Projects (30 items).zip`. Role: academic review or adjudication projects. Status: located by filename inventory only. Boundary: do not treat as authored manuscript voice until provenance is confirmed.
- **OVERLEAF-PERSONAL-20260531.** Source: local download. File: `C:\Users\gerar\Downloads\Overleaf Projects (34 items).zip`. Role: personal writing and fragments. Status: located by filename inventory only.

## Gate 2 Academic Handles

Zotero was queried on 2026-05-31 through the local API. The query stayed at metadata level: title, creator list, year or date, item type, collection key, URL, DOI, Zotero key, and BibTeX key where available. Attachment paths, file URLs, PDFs, and full text were not requested.

First-pass manuscript evidence candidates:

- **ZOTERO-JIUS3YMP.** `Partition-free approach to open quantum systems in harmonic environments: An exact stochastic Liouville equation`. Zotero key: `JIUS3YMP`. BibTeX key: `mccaulPartitionfreeApproachOpen2017`. Type: journal article. Year: 2017. Venue: Physical Review B. Status: high-priority early academic voice.
- **ZOTERO-L6EIZU6E.** `Driving spin-boson models from equilibrium using exact quantum dynamics`. Zotero key: `L6EIZU6E`. BibTeX key: `mccaulDrivingSpinbosonModels2018`. Type: journal article. Year: 2018. Venue: Physical Review B. Status: high-priority early academic voice.
- **ZOTERO-2TMCRVBA.** `Stochastic representations of open systems`. Zotero key: `2TMCRVBA`. BibTeX key: `mccaulStochasticRepresentationsOpen2019`. Type: thesis. Year: 2019. Status: dissertation-scale academic voice.
- **ZOTERO-QNXVSEFR.** `Entropy nonconservation and boundary conditions for Hamiltonian dynamical systems`. Zotero key: `QNXVSEFR`. BibTeX key: `mccaulEntropyNonconservationBoundary2019`. Type: journal article. Year: 2019. Venue: Physical Review E. Status: high-priority concept and boundary-condition evidence.
- **ZOTERO-PYMMKYNE.** `Controlling arbitrary observables in correlated many-body systems`. Zotero key: `PYMMKYNE`. BibTeX key: `mccaulControllingArbitraryObservables2020`. Type: journal article. Year: 2020. Venue: Physical Review A. Status: pair with `ZOTERO-UQW3Y5J2`.
- **ZOTERO-UQW3Y5J2.** `Driven Imposters: Controlling Expectations in Many-Body Systems`. Zotero key: `UQW3Y5J2`. BibTeX key: `mccaulDrivenImpostersControlling2020`. Type: journal article. Year: 2020. Venue: Physical Review Letters. Status: high-priority title and framing evidence.
- **ZOTERO-AQXF2ZUL.** `Fast computation of dissipative quantum systems with ensemble rank truncation`. Zotero key: `AQXF2ZUL`. BibTeX key: `mccaulFastComputationDissipative2021`. Type: journal article. Year: 2021. Venue: Physical Review Research. Status: methods and computation evidence.
- **ZOTERO-27MBG7CN.** `How to win friends and influence functionals: deducing stochasticity from deterministic dynamics`. Zotero key: `27MBG7CN`. BibTeX key: `mccaulHowWinFriends2021`. Type: journal article. Year: 2021. Venue: European Physical Journal Special Topics. Status: high-priority humour-under-constraint evidence.
- **ZOTERO-D6E6KU5P.** `Optical Indistinguishability via Twinning Fields`. Zotero key: `D6E6KU5P`. BibTeX key: `mccaulOpticalIndistinguishabilityTwinning2021`. Type: journal article. Year: 2021. Venue: Physical Review Letters. Status: concise PRL-style voice evidence.
- **ZOTERO-MHPXQFHH.** `Free to harmonic unitary transformations in quantum and Koopman dynamics`. Zotero key: `MHPXQFHH`. BibTeX key: `mccaulFreeHarmonicUnitary2022`. Type: journal article. Year: 2022. Venue: Journal of Physics A. Status: mathematical-framing evidence.
- **ZOTERO-Y6FTCVRH.** `Wave operator representation of quantum and classical dynamics`. Zotero key: `Y6FTCVRH`. BibTeX key: `mccaulWaveOperatorRepresentation2023`. Type: journal article. Year: 2023. Venue: Physical Review A. Status: formal representation evidence.
- **ZOTERO-VHLW63Q7.** `Towards single atom computing via high harmonic generation`. Zotero key: `VHLW63Q7`. BibTeX key: `mccaulSingleAtomComputing2023`. Type: journal article. Year: 2023. Venue: European Physical Journal Plus. Status: bridge from optics to computing.
- **ZOTERO-9IFREHKD.** `Superoscillations Deliver Superspectroscopy`. Zotero key: `9IFREHKD`. BibTeX key: `mccaulSuperoscillationsDeliverSuperspectroscopy2023`. Type: journal article. Year: 2023. Venue: Physical Review Letters. Status: title, compression, and high-impact framing evidence.
- **ZOTERO-Q6RYZNSE.** `Unwrapping photonic reservoirs: Enhanced expressivity via random Fourier encoding over stretched domains`. Zotero key: `Q6RYZNSE`. BibTeX key: `mccaulUnwrappingPhotonicReservoirs2025a`. Type: journal article. Year: 2025. Venue: Chaos. Status: recent reservoir-computing evidence.
- **ZOTERO-4KPJQHKR.** `Minimal quantum reservoirs with Hamiltonian encoding`. Zotero key: `4KPJQHKR`. BibTeX key: `mccaulMinimalQuantumReservoirs2025`. Type: journal article. Year: 2025. Venue: Chaos. Status: recent reservoir-computing evidence.
- **ZOTERO-UNGFXZ9P.** `Free Snacks in Quantum Complexity`. Zotero key: `UNGFXZ9P`. BibTeX key: `mccaulFreeSnacksQuantum2025`. Type: preprint. Year: 2025. Status: sole-author recent voice candidate.

Collaborative or lower-priority academic candidates:

- **ZOTERO-X79R5KZH.** `Sequential optical response suppression for chemical mixture characterization`. Status: co-authored 2022 journal article.
- **ZOTERO-IBCC2EJ6.** `Optical distinguishability of Mott insulators in the time versus frequency domain`. Status: co-authored 2022 journal article.
- **ZOTERO-79JUV5HH.** `Dynamical Generation of Epsilon-Near-Zero Behaviour via Tracking and Feedback Control`. Status: co-authored 2023 preprint.
- **ZOTERO-P5V6H378.** `Ultrafast laser-driven dynamics in metal/magnetic-insulator interfaces`. Status: co-authored 2023 journal article.
- **ZOTERO-9P9A44HB.** `Extracting correlation length in Mott insulators by strong-field driving`. Status: co-authored 2024 journal article.
- **ZOTERO-EL34Z4MX.** `Super-sensing: 100-Fold enhancement in THz time-domain spectroscopy contrast via superoscillating waveform shaping`. Status: co-authored 2024 preprint.
- **ZOTERO-9XFE9YBL.** `Quantum Dynamical Emulation of Imaginary Time Evolution`. Status: co-authored 2024 preprint.
- **ZOTERO-ZMHXNSKD.** `Unwrapping photonic reservoirs: enhanced expressivity via random Fourier encoding over stretched domains`. Status: preprint counterpart to `ZOTERO-Q6RYZNSE`.
- **ZOTERO-8ZRJQIJG.** `Dynamical learning and quantum memory with non-Hermitian many-body systems`. Status: co-authored 2025 preprint.
- **ZOTERO-CXCNCRH6.** `Observables in Motion: A guide to simulating classical and quantum dynamics`. Status: co-authored 2025 preprint.

## Provenance Fields

Reader outputs should preserve:

- source handle
- source class
- document title
- source ID or path
- chunk or section locator
- date range where available
- reader model and run date
- evidence quality
- register assignment
- confidence
- privacy tier for factual claims
- temporal status for factual claims

## Privacy Boundary

The wiki stores distilled knowledge and selected factual claims. Working cache may store extracted text, chunk summaries, and private evidence ledgers, but the canon-facing nodes should carry only what a future drafting agent or collaborator needs to act correctly. Sensitive or third-party facts should stay redacted or remain in private cache.

## Cache Discipline

Use three cache layers outside the canon:

- extraction cache keyed by salted source hash plus mtime, revision ID, or message ID
- chunk-analysis cache keyed by reader prompt version, chunk hash, and model ID
- reducer cache keyed by sorted observation hashes

The canon records source handles and distilled claims. Raw text cache must be ignored by git and treated as private working material.
