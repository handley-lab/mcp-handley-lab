---
name: literature_scout
description: "[EXPERIMENTAL] Research skill. When a goal-relevant claim lacks support, scout the literature (arXiv, web) and return citable evidence + a bibtex entry, extending the evidence base to need."
---

# Literature Scout [EXPERIMENTAL]

Drafting reveals what the evidence base is missing. When `evidence_alignment`
flags an uncovered goal or a claim with thin `Literature`, this skill goes and
finds the grounding rather than letting the claim stand unbacked, then folds the
result back into the standardised ledger.

This skill has no deterministic backing script - research is an act of judgement.
It orchestrates the tools already on hand.

## Protocol

1. **Target the gap.** Take a specific claim or uncovered goal from the
   `evidence_alignment` support map. Phrase the precise proposition you need to
   ground (not a vague topic).
2. **Search.** Use the available research tools:
   - arXiv search (the `arxiv` MCP server / `mcp_gerard.arxiv`) for primary
     sources, with bibtex download.
   - A grounded/web-search LLM call (`mcp_gerard.llm.chat` with a grounding-capable
     model) for broader or cross-disciplinary context.
3. **Read before citing.** Confirm the source actually supports the proposition.
   Trust no abstract - quote the supporting result. A citation that does not bear
   the claim is worse than none.
4. **Record.** Append the source to `references.bib` and update the claim's
   `Literature` field in the evidence ledger. If the source only partially
   supports the claim, soften the claim to match - the ledger must stay honest.
5. **Re-align.** Re-run `evidence_alignment` to confirm the gap is closed and the
   goal's coverage has risen.

## Honesty axiom
The point is not to decorate claims with references. It is to discover what the
literature genuinely establishes, and to bring the manuscript's reach into line
with it. If the search comes back empty, that is a finding: the claim is novel and
must be carried by derivation or numerics, or cut.
