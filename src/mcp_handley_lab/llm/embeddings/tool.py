"""Embeddings Tool for semantic search and document indexing via MCP.

Provides embeddings, similarity calculation, and document search capabilities
using multiple providers (OpenAI, Gemini, Mistral).
"""

from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("Embeddings Tool")


@mcp.tool(
    description="Generate embedding vectors for text. "
    "Supports OpenAI (text-embedding-*), Gemini (gemini-embedding-*), "
    "Mistral (mistral-embed, codestral-embed). Use list_models to discover models. "
    "Related: index_documents, search_documents, calculate_similarity. "
    "Returns: {embeddings: [[float]], model, provider, dimensions, count}."
)
def get_embeddings(
    texts: list[str] = Field(
        ...,
        description="Text strings to embed. Max 16 for Mistral.",
    ),
    model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model. Provider is inferred from name.",
    ),
    output_file: str = Field(
        default="",
        description="File path to save embeddings as JSON. Empty means no file output.",
    ),
) -> dict[str, Any]:
    """Generate embeddings for text or code."""
    from mcp_handley_lab.llm.embeddings.shared import get_embeddings as _get_embeddings

    return _get_embeddings(texts=texts, model=model, output_file=output_file)


@mcp.tool(
    description="Calculate semantic similarity between two texts using embeddings. "
    "Related: get_embeddings, index_documents, search_documents. "
    "Returns: {similarity: float (-1.0 to 1.0), model, provider}."
)
def calculate_similarity(
    text1: str = Field(
        ...,
        description="First text for comparison.",
    ),
    text2: str = Field(
        ...,
        description="Second text for comparison.",
    ),
    model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model to use.",
    ),
) -> dict[str, Any]:
    """Calculate cosine similarity between two texts."""
    from mcp_handley_lab.llm.embeddings.shared import (
        calculate_similarity as _calculate_similarity,
    )

    return _calculate_similarity(text1=text1, text2=text2, model=model)


@mcp.tool(
    description="Create a searchable semantic index from document files. "
    "Reads files, generates embeddings, and saves as JSON index. "
    "Use search_documents to query the index. "
    "Returns: {message, index_path, model, document_count}."
)
def index_documents(
    document_paths: list[str] = Field(
        ...,
        description="File paths to text documents to index.",
    ),
    output_index_path: str = Field(
        ...,
        description="File path to save the JSON index.",
    ),
    model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model to use.",
    ),
) -> dict[str, Any]:
    """Create a semantic index from document files."""
    from mcp_handley_lab.llm.embeddings.shared import (
        index_documents as _index_documents,
    )

    return _index_documents(
        document_paths=document_paths,
        output_index_path=output_index_path,
        model=model,
    )


@mcp.tool(
    description="Search a document index created by index_documents. "
    "Returns: {query, model, results: [{path, similarity}]}. "
    "Model defaults to index model if not specified."
)
def search_documents(
    query: str = Field(
        ...,
        description="Search query.",
    ),
    index_path: str = Field(
        ...,
        description="Path to the JSON document index.",
    ),
    model: str = Field(
        default="",
        description="Embedding model. Defaults to index model. Must match index dimensions.",
    ),
    top_k: int = Field(
        default=5,
        description="Number of top results to return.",
    ),
) -> dict[str, Any]:
    """Search documents by semantic similarity."""
    from mcp_handley_lab.llm.embeddings.shared import (
        search_documents as _search_documents,
    )

    return _search_documents(
        query=query, index_path=index_path, model=model, top_k=top_k
    )
