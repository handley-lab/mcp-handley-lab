"""Shared embeddings functions for direct use (no MCP required)."""

import json
import math
from pathlib import Path
from typing import Any

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


def get_embeddings(
    texts: list[str],
    model: str = "text-embedding-3-small",
    output_file: str = "",
) -> dict[str, Any]:
    """Generate embedding vectors for text.

    Args:
        texts: Text strings to embed. Max 16 for Mistral.
        model: Embedding model. Provider is inferred from name.
        output_file: File path to save embeddings as JSON.

    Returns:
        Dict with embeddings, model, provider, dimensions, count.
    """
    provider = _resolve_embedding_provider(model)

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
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2))

    return result


def calculate_similarity(
    text1: str,
    text2: str,
    model: str = "text-embedding-3-small",
) -> dict[str, Any]:
    """Calculate semantic similarity between two texts using embeddings.

    Args:
        text1: First text for comparison.
        text2: Second text for comparison.
        model: Embedding model to use.

    Returns:
        Dict with similarity score, model, provider.
    """
    embeddings = _get_embeddings([text1, text2], model)
    similarity = _cosine_similarity(embeddings[0], embeddings[1])

    return {
        "similarity": similarity,
        "model": model,
        "provider": _resolve_embedding_provider(model),
    }


def index_documents(
    document_paths: list[str],
    output_index_path: str,
    model: str = "text-embedding-3-small",
) -> dict[str, Any]:
    """Create a searchable semantic index from document files.

    Args:
        document_paths: File paths to text documents to index.
        output_index_path: File path to save the JSON index.
        model: Embedding model to use.

    Returns:
        Dict with message, index_path, model, document_count.
    """
    documents = []
    for path in document_paths:
        file_path = Path(path)
        content = file_path.read_text(encoding="utf-8")
        documents.append({"path": path, "content": content})

    texts = [doc["content"] for doc in documents]
    embeddings = _get_embeddings(texts, model)

    index = {
        "model": model,
        "provider": _resolve_embedding_provider(model),
        "documents": [
            {"path": doc["path"], "embedding": emb}
            for doc, emb in zip(documents, embeddings, strict=True)
        ],
    }

    index_path = Path(output_index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2))

    return {
        "message": f"Indexed {len(documents)} documents",
        "index_path": output_index_path,
        "model": model,
        "document_count": len(documents),
    }


def search_documents(
    query: str,
    index_path: str,
    model: str = "",
    top_k: int = 5,
) -> dict[str, Any]:
    """Search a document index by semantic similarity.

    Args:
        query: Search query.
        index_path: Path to the JSON document index.
        model: Embedding model. Defaults to index model.
        top_k: Number of top results to return.

    Returns:
        Dict with query, model, results list.
    """
    index_file = Path(index_path)
    index = json.loads(index_file.read_text())

    search_model = model if model else index.get("model", "text-embedding-3-small")

    index_model = index.get("model")
    if model and index_model and model != index_model:
        raise ValueError(
            f"Model mismatch: query model '{model}' differs from index model '{index_model}'. "
            f"Use the same model or omit model param to use index model."
        )

    query_embedding = _get_embeddings([query], search_model)[0]

    results = []
    for doc in index["documents"]:
        similarity = _cosine_similarity(query_embedding, doc["embedding"])
        results.append({"path": doc["path"], "similarity": similarity})

    results.sort(key=lambda x: x["similarity"], reverse=True)

    return {
        "query": query,
        "model": search_model,
        "results": results[:top_k],
    }
