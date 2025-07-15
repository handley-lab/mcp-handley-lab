Of course. Here is a comprehensive implementation plan for adding embedding functionality to the Gemini tool within the MCP framework, based on the provided codebase and API documentation.

### Overview

This plan details the steps to extend the `mcp_handley_lab.llm.gemini` module with powerful embedding capabilities using the new `google-genai` SDK. The implementation will seamlessly integrate with the existing FastMCP framework, follow established coding patterns, and provide four key functionalities: `get_embeddings`, `index_documents`, `search_documents`, and `calculate_similarity`.

The plan is structured as follows:
1.  **Pydantic Model Definitions:** Creating new response models for our embedding functions.
2.  **Core Gemini Tool Implementation:** Adding the new functions to `src/mcp_handley_lab/llm/gemini/tool.py`.
3.  **Integration with MCP Framework:** Updating the `server_info` to reflect new capabilities.
4.  **Summary of Changes:** A quick reference of all modified and new files.

---

### Step 1: Pydantic Model Definitions

First, we will define the data structures for our new tool's responses. These models ensure type-safe and predictable outputs.

**File to Edit:** `src/mcp_handley_lab/shared/models.py`

Add the following classes to the end of the file:

```python
# src/mcp_handley_lab/shared/models.py

# ... (existing model definitions) ...

class EmbeddingResult(BaseModel):
    """Result of an embedding request for a single piece of content."""
    embedding: list[float]
    token_count: int


class DocumentIndex(BaseModel):
    """A single indexed document containing its path and embedding vector."""
    path: str
    embedding: list[float]


class IndexResult(BaseModel):
    """Result of an indexing operation."""
    index_path: str
    files_indexed: int
    total_tokens: int
    message: str


class SearchResult(BaseModel):
    """A single result from a semantic search."""
    path: str
    similarity_score: float


class SimilarityResult(BaseModel):
    """Result of a similarity calculation between two texts."""
    similarity: float
```

---

### Step 2: Core Gemini Tool Implementation

This is the main part of the implementation. We will extend `src/mcp_handley_lab/llm/gemini/tool.py` with the required functions.

**File to Edit:** `src/mcp_handley_lab/llm/gemini/tool.py`

#### 2.1 Add Necessary Imports

First, update the import section at the top of the file to include `numpy` for calculations, `json` for indexing, and the new models and types we need.

```python
# src/mcp_handley_lab/llm/gemini/tool.py

# ... (existing imports)
import json
from typing import Any, List, Union

import numpy as np
from google import genai as google_genai
from google.genai import types as google_types
from google.genai.types import (
# ... (existing google.genai.types imports)
)

# ... (existing mcp_handley_lab imports)
from mcp_handley_lab.shared.models import (
    EmbeddingResult,  # New
    IndexResult,      # New
    ImageGenerationResult,
    LLMResult,
    ModelListing,
    SearchResult,     # New
    ServerInfo,
    SimilarityResult, # New
)
```

#### 2.2 Add a Similarity Helper Function

Add a private helper function within the file to calculate cosine similarity. This follows the recommendation in the API documentation.

```python
# src/mcp_handley_lab/llm/gemini/tool.py

# ... (after the imports and before the first @mcp.tool decorator)

def _calculate_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two embedding vectors."""
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    dot_product = np.dot(vec1_np, vec2_np)
    norm_product = np.linalg.norm(vec1_np) * np.linalg.norm(vec2_np)
    if norm_product == 0:
        return 0.0
    return dot_product / norm_product
```

#### 2.3 Implement the `get_embeddings` Function

This function will be the core wrapper around the `embed_content` API call.

```python
# src/mcp_handley_lab/llm/gemini/tool.py

# ... (add this function after the `generate_image` function)

@mcp.tool(
    description="Generates embedding vectors for a given list of text strings using a specified model. Supports task-specific embeddings like 'SEMANTIC_SIMILARITY' or 'RETRIEVAL_DOCUMENT'."
)
def get_embeddings(
    contents: Union[str, List[str]],
    model: str = "gemini-embedding-001",
    task_type: str = "SEMANTIC_SIMILARITY",
    output_dimensionality: int = 0,
) -> List[EmbeddingResult]:
    """Generates embeddings for one or more text strings."""
    if isinstance(contents, str):
        contents = [contents]

    if not contents:
        raise ValueError("Contents list cannot be empty.")

    config_params = {"task_type": task_type.upper()}
    if output_dimensionality > 0:
        config_params["output_dimensionality"] = output_dimensionality

    config = google_types.EmbedContentConfig(**config_params)

    try:
        response = client.models.embed_content(
            model=model, contents=contents, config=config
        )

        results = []
        for embedding in response:
            results.append(
                EmbeddingResult(
                    embedding=embedding.values,
                    token_count=embedding.statistics.token_count,
                )
            )
        return results

    except Exception as e:
        raise RuntimeError(f"Failed to get embeddings: {e}") from e
```

#### 2.4 Implement `calculate_similarity`

This tool will provide a simple way to compare two pieces of text.

```python
# src/mcp_handley_lab/llm/gemini/tool.py

# ... (add after get_embeddings)

@mcp.tool(
    description="Calculates the semantic similarity score (cosine similarity) between two text strings. Returns a score between -1.0 and 1.0, where 1.0 is identical."
)
def calculate_similarity(
    text1: str, text2: str, model: str = "gemini-embedding-001"
) -> SimilarityResult:
    """Calculates the cosine similarity between two texts."""
    if not text1 or not text2:
        raise ValueError("Both text1 and text2 must be provided.")

    embeddings = get_embeddings(contents=[text1, text2], model=model)

    if len(embeddings) != 2:
        raise RuntimeError("Failed to generate embeddings for both texts.")

    similarity = _calculate_cosine_similarity(
        embeddings[0].embedding, embeddings[1].embedding
    )

    return SimilarityResult(similarity=similarity)
```

#### 2.5 Implement `index_documents`

This tool will create a searchable JSON index from a list of document paths.

```python
# src/mcp_handley_lab/llm/gemini/tool.py

# ... (add after calculate_similarity)

@mcp.tool(
    description="Creates a searchable semantic index from a list of document file paths. It reads the files, generates embeddings for them, and saves the index as a JSON file."
)
def index_documents(
    document_paths: List[str],
    output_index_path: str,
    model: str = "gemini-embedding-001",
) -> IndexResult:
    """Creates a semantic index from document files."""
    from mcp_handley_lab.shared.models import DocumentIndex

    indexed_data = []
    total_tokens = 0
    batch_size = 100  # Process up to 100 documents per API call

    for i in range(0, len(document_paths), batch_size):
        batch_paths = document_paths[i : i + batch_size]
        batch_contents = []
        valid_paths = []

        for doc_path_str in batch_paths:
            doc_path = Path(doc_path_str)
            if doc_path.is_file():
                try:
                    batch_contents.append(doc_path.read_text(encoding="utf-8"))
                    valid_paths.append(doc_path_str)
                except Exception as e:
                    print(f"Warning: Could not read file {doc_path_str}: {e}")
            else:
                print(f"Warning: File not found, skipping: {doc_path_str}")

        if not batch_contents:
            continue

        embedding_results = get_embeddings(
            contents=batch_contents, model=model, task_type="RETRIEVAL_DOCUMENT"
        )

        for path, emb_result in zip(valid_paths, embedding_results):
            indexed_data.append(
                DocumentIndex(path=path, embedding=emb_result.embedding)
            )
            total_tokens += emb_result.token_count

    # Save the index to a file
    index_file = Path(output_index_path)
    index_file.parent.mkdir(parents=True, exist_ok=True)
    with open(index_file, "w") as f:
        # Pydantic's model_dump is used here to serialize our list of models
        json.dump([item.model_dump() for item in indexed_data], f, indent=2)

    return IndexResult(
        index_path=str(index_file),
        files_indexed=len(indexed_data),
        total_tokens=total_tokens,
        message=f"Successfully indexed {len(indexed_data)} files to {index_file}.",
    )
```

#### 2.6 Implement `search_documents`

This tool will use the generated index to perform a semantic search.

```python
# src/mcp_handley_lab/llm/gemini/tool.py

# ... (add after index_documents)

@mcp.tool(
    description="Performs a semantic search for a query against a pre-built document index file. Returns a ranked list of the most relevant documents based on similarity."
)
def search_documents(
    query: str,
    index_path: str,
    top_k: int = 5,
    model: str = "gemini-embedding-001",
) -> List[SearchResult]:
    """Searches a document index for the most relevant documents to a query."""
    index_file = Path(index_path)
    if not index_file.is_file():
        raise FileNotFoundError(f"Index file not found: {index_path}")

    with open(index_file, "r") as f:
        indexed_data = json.load(f)

    if not indexed_data:
        return []

    # Get embedding for the query
    query_embedding_result = get_embeddings(
        contents=query, model=model, task_type="RETRIEVAL_QUERY"
    )
    query_embedding = query_embedding_result[0].embedding

    # Calculate similarities
    similarities = []
    for item in indexed_data:
        doc_embedding = item["embedding"]
        score = _calculate_cosine_similarity(query_embedding, doc_embedding)
        similarities.append({"path": item["path"], "score": score})

    # Sort by similarity and return top_k
    similarities.sort(key=lambda x: x["score"], reverse=True)

    results = [
        SearchResult(path=item["path"], similarity_score=item["score"])
        for item in similarities[:top_k]
    ]

    return results
```

---

### Step 3: Integration with MCP Framework

To make the new tools discoverable, we need to add them to the `capabilities` list in the `server_info` function.

**File to Edit:** `src/mcp_handley_lab/llm/gemini/tool.py`

Modify the `server_info` function as shown:

```python
# src/mcp_handley_lab/llm/gemini/tool.py

# ... (at the end of the file)

@mcp.tool(
    description="Checks Gemini Tool server status and API connectivity. Returns version info, model availability, and a list of available functions."
)
def server_info() -> ServerInfo:
    """Get server status and Gemini configuration."""

    # Test API by listing models
    models_response = client.models.list()
    available_models = []
    for model in models_response:
        # Filter for models that can be used with the generateContent and embedContent methods.
        if "gemini" in model.name or "embedding" in model.name:
            available_models.append(model.name.split("/")[-1])
            
    # Add our new functions to the capabilities list
    info = build_server_info(
        provider_name="Gemini",
        available_models=available_models,
        memory_manager=memory_manager,
        vision_support=True,
        image_generation=True,
    )
    
    # Manually add embedding capabilities to the server info
    embedding_capabilities = [
        "get_embeddings - Generate embedding vectors for text.",
        "calculate_similarity - Compare two texts for semantic similarity.",
        "index_documents - Create a searchable index from files.",
        "search_documents - Search an index for a query.",
    ]
    info.capabilities.extend(embedding_capabilities)
    
    return info
```

*Note*: The original `build_server_info` helper doesn't account for embedding functions, so we manually extend the `capabilities` list.

---

### Summary of Changes

1.  **`src/mcp_handley_lab/shared/models.py`:**
    *   Added `EmbeddingResult`, `DocumentIndex`, `IndexResult`, `SearchResult`, and `SimilarityResult` Pydantic models.

2.  **`src/mcp_handley_lab/llm/gemini/tool.py`:**
    *   Added new imports for `numpy`, `json`, and the new Pydantic models.
    *   Added a private helper function `_calculate_cosine_similarity`.
    *   Implemented four new MCP tools:
        *   `get_embeddings`
        *   `calculate_similarity`
        *   `index_documents`
        *   `search_documents`
    *   Updated the `server_info` function to include the new embedding capabilities, making them discoverable by the framework's CLI.

This plan provides a complete and robust implementation of embedding functionality, adhering to the architecture and patterns of the existing MCP framework.
