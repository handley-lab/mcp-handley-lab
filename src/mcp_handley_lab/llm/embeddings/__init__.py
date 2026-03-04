"""Embeddings utilities for direct use (no MCP required)."""

from mcp_handley_lab.llm.embeddings.shared import (
    calculate_similarity,
    get_embeddings,
    index_documents,
    search_documents,
)

__all__ = [
    "calculate_similarity",
    "get_embeddings",
    "index_documents",
    "search_documents",
]
