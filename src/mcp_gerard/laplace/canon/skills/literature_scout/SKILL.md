---
name: literature_scout
description: "[EXPERIMENTAL] Owns the literature rail of the generation stage. For each core result, establish where it sits in the literature and what is genuinely established there, recording citable provenance per claim plus a bibtex entry, so the literature face is built alongside the result rather than patched onto a draft."
---

# Literature Scout [EXPERIMENTAL]

This skill owns the **literature rail** of the ledger bus - one of the three pieces
of the generation stage, peer to `result_foundry` (results) and `numerical_evidence`
(numerics). It does not wait for a draft to expose a thin citation. As a result is
established, its literature face is built in parallel: where the claim sits in the
field, what the field already establishes, and what is therefore novel here.

The output has two parts. The lasting one is a **shared literature store** - one
flexible corpus across projects, so a reference gathered once is never re-gathered,
and the citations a paper draws reflect the whole accumulated literature rather than
whatever was to hand. The per-result part is the `Literature` face: a *selection* into
that store for one claim, carrying where the claim sits and what is established near it.
Both are distinct from the reference vault, which governs how *internal prior work*
re-enters by re-derivation - the literature rail is the *external* record of what the
published field holds.

The store's schema, its retrieval, and the manuscript-location tags that make context
surface for the section being drafted are an **open design** - see the engine backlog,
`Generation-stage rails`. Until it is built, keep entries in whatever form the project
already uses, and do not bake a per-project `references.bib` in as the home.

This skill has no deterministic backing script - research is an act of judgement.
It orchestrates the tools already on hand.

## Protocol

1. **Target the claim.** Take a settled or in-progress result and phrase the precise
   proposition its literature face must address - where it sits, what the field
   establishes near it, what it claims as novel. Not a vague topic.
2. **Search.** Use the available research tools:
   - arXiv search (the `arxiv` MCP server / `mcp_gerard.arxiv`) for primary
     sources, with bibtex download.
   - A grounded/web-search LLM call (`mcp_gerard.llm.chat` with a grounding-capable
     model) for broader or cross-disciplinary context.
3. **Read before citing.** Confirm the source actually supports the proposition.
   Trust no abstract - quote the supporting result. A citation that does not bear
   the claim is worse than none.
4. **Record.** Add the source to the literature store (whatever form the project
   currently uses) and write the result's `Literature` face: what each cited source
   establishes, and the resulting novelty boundary for this claim. If a source only
   partially supports the claim, soften the claim to match - the ledger must stay honest.
5. **Hand to the reconciler.** A literature face that changes a result's novelty or
   scope is a commitment - propagate it like any other ledger edit.

## Honesty axiom
The point is not to decorate claims with references. It is to discover what the
literature genuinely establishes, and to bring the manuscript's reach into line
with it. If the search comes back empty, that is a finding: the claim is novel and
must be carried by derivation or numerics, or cut.
