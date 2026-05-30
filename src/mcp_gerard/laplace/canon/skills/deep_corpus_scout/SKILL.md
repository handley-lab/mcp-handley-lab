---
name: deep_corpus_scout
description: "[EXPERIMENTAL] Recursive large-corpus flattening and summarization. Ideal for extracting evidence from dense ArXiv source tarballs or complex multi-file codebases."
---

# Deep Corpus Scout [EXPERIMENTAL]

While the `literature_scout` handles targeted citation grounding, the **Deep Corpus Scout** is built for sheer volume. When Laplace encounters an entire codebase, a multi-file LaTeX repository, or an ArXiv source tarball that exceeds the standard context window, this skill orchestrates recursive reduction and flattening.

This skill has no deterministic backing script; it is a complex workflow executed natively by the LLM and the loop daemon.

## Protocol

1. **Target the Corpus.**
   - If starting from an ArXiv paper, use `mcp_gerard.arxiv` to download the raw `.tar.gz` source. Extract the tarball into a temporary workspace.
   - If starting from a GitHub repo, clone the repository.

2. **Flatten.**
   - Invoke `mcp_gerard.code2prompt` on the root directory. This tool compresses the entire nested tree (and its file contents) into a single, standardized, AI-readable Markdown document.

3. **Recursive LLM Summarization.**
   - If the flattened Markdown document is too large for a single context pass (or if maximum extraction detail is required), use the **Recursive LLM Pattern**.
   - Split the flattened file into logical chunks (e.g., by chapter, file, or class).
   - Feed each chunk independently to a background LLM process (via `mcp_gerard.loop` or `mcp_gerard.llm`) with a strict extraction prompt.
   - Aggregate the resulting sub-summaries into a final "Master Summary" or "Evidence Base".

4. **Integration.**
   - Cross-reference the resulting Master Summary with the `epistemic_ledger` to verify any claims, or pass it to the `hostile_redteam_swarm` for deep review.
