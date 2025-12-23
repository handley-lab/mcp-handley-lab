"""Embeddings Tool for semantic search and document indexing via MCP.

Provides embeddings, similarity calculation, and document search capabilities
using multiple providers (OpenAI, Gemini, Mistral).
"""

import json
import math
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("Embeddings Tool")

# Embedding model prefixes for provider inference
EMBEDDING_PREFIXES = [
    ("text-embedding-", "openai"),
    ("gemini-embedding", "gemini"),
    ("mistral-embed", "mistral"),
    ("codestral-embed", "mistral"),
]


def _resolve_embedding_provider(model: str) -> str:
    """Infer provider from embedding model name."""
    for prefix, provider in EMBEDDING_PREFIXES:
        if model.startswith(prefix):
            return provider
    raise ValueError(
        f"Unknown embedding model: '{model}'. "
        f"Supported prefixes: text-embedding-* (OpenAI), "
        f"gemini-embedding-* (Gemini), mistral-embed/codestral-embed (Mistral)"
    )


def _get_embeddings(texts: list[str], model: str) -> list[list[float]]:
    """Get embeddings using the appropriate provider via registry."""
    from mcp_handley_lab.llm.registry import get_adapter

    provider = _resolve_embedding_provider(model)
    adapter = get_adapter(provider, "embeddings")
    return adapter(texts, model)


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=True))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


@mcp.tool(
    description="Generate embedding vectors for text. "
    "Supports OpenAI (text-embedding-*), Gemini (gemini-embedding-*), "
    "Mistral (mistral-embed, codestral-embed). "
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
    provider = _resolve_embedding_provider(model)

    # Mistral has a 16 text limit
    if provider == "mistral" and len(texts) > 16:
        raise ValueError(f"Mistral: maximum 16 texts per request (got {len(texts)})")

    embeddings = _get_embeddings(texts, model)

    result = {
        "embeddings": embeddings,
        "model": model,
        "provider": provider,
        "dimensions": len(embeddings[0]) if embeddings else 0,
        "count": len(embeddings),
    }

    if output_file:
        Path(output_file).write_text(json.dumps(result, indent=2))

    return result


@mcp.tool(
    description="Calculate semantic similarity between two texts. "
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
    embeddings = _get_embeddings([text1, text2], model)

    similarity = _cosine_similarity(embeddings[0], embeddings[1])

    return {
        "similarity": similarity,
        "model": model,
        "provider": _resolve_embedding_provider(model),
    }


@mcp.tool(
    description="Create a searchable semantic index from document files. "
    "Reads files, generates embeddings, and saves as JSON index. "
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
    # Read documents
    documents = []
    for path in document_paths:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Document not found: {path}")
        content = file_path.read_text(encoding="utf-8")
        documents.append({"path": path, "content": content})

    # Get embeddings for all documents
    texts = [doc["content"] for doc in documents]
    embeddings = _get_embeddings(texts, model)

    # Build index
    index = {
        "model": model,
        "provider": _resolve_embedding_provider(model),
        "documents": [
            {"path": doc["path"], "embedding": emb}
            for doc, emb in zip(documents, embeddings, strict=True)
        ],
    }

    # Save index
    Path(output_index_path).write_text(json.dumps(index, indent=2))

    return {
        "message": f"Indexed {len(documents)} documents",
        "index_path": output_index_path,
        "model": model,
        "document_count": len(documents),
    }


@mcp.tool(
    description="Search a document index for relevant documents. "
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
    # Load index
    index_file = Path(index_path)
    if not index_file.exists():
        raise FileNotFoundError(f"Index not found: {index_path}")

    index = json.loads(index_file.read_text())

    # Use index model if not specified
    search_model = model if model else index.get("model", "text-embedding-3-small")

    # Validate model matches index if both specified
    index_model = index.get("model")
    if model and index_model and model != index_model:
        raise ValueError(
            f"Model mismatch: query model '{model}' differs from index model '{index_model}'. "
            f"Use the same model or omit model param to use index model."
        )

    # Get query embedding
    query_embedding = _get_embeddings([query], search_model)[0]

    # Calculate similarities
    results = []
    for doc in index["documents"]:
        similarity = _cosine_similarity(query_embedding, doc["embedding"])
        results.append({"path": doc["path"], "similarity": similarity})

    # Sort by similarity descending
    results.sort(key=lambda x: x["similarity"], reverse=True)

    return {
        "query": query,
        "model": search_model,
        "results": results[:top_k],
    }
