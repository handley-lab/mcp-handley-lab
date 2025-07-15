# Google GenAI SDK Embedding API Documentation

## CRITICAL: Use NEW genai SDK, NOT deprecated generativeai

**Correct SDK**: `google-genai` (NEW, supported)
**Deprecated SDK**: `google-generativeai` (DEPRECATED, EOL Sept 30, 2025)

## Installation

```bash
pip install google-genai
```

## Import Statements

```python
from google import genai
from google.genai import types
```

## Client Setup

```python
client = genai.Client(api_key="YOUR_API_KEY")
# or use environment variable GOOGLE_API_KEY
client = genai.Client()
```

## Core Method: embed_content()

### Method Signature

```python
response = client.models.embed_content(
    model: str,
    contents: Union[str, List[str]],
    config: Optional[types.EmbedContentConfig] = None
)
```

### Parameters

#### Required Parameters

1. **`model`** (str): The embedding model to use
   - Primary: `"gemini-embedding-001"`
   - Alternative: `"text-embedding-004"`

2. **`contents`** (str or List[str]): Text content to embed
   - Single string: `"why is the sky blue?"`
   - Multiple strings: `["text1", "text2", "text3"]`

#### Optional Parameters

3. **`config`** (types.EmbedContentConfig): Configuration object with:
   - `output_dimensionality` (int): Control vector size (e.g., 768, 1536, 3072)
   - `task_type` (str): Optimize for specific use case
   - `title` (str): Title for RETRIEVAL_DOCUMENT tasks

### Task Types

- `"SEMANTIC_SIMILARITY"`: General semantic comparison
- `"RETRIEVAL_DOCUMENT"`: Document indexing for retrieval
- `"RETRIEVAL_QUERY"`: Query processing for search
- `"CLASSIFICATION"`: Text classification tasks
- `"CLUSTERING"`: Grouping similar texts

### Response Format

Returns `ContentEmbedding` object with:
- `values`: List[float] - The embedding vector
- `statistics`: Metadata about token count and truncation

## Code Examples

### Basic Embedding

```python
from google import genai

client = genai.Client()

# Single text embedding
response = client.models.embed_content(
    model="gemini-embedding-001",
    contents="What is machine learning?"
)

embedding_vector = response.values
print(f"Embedding dimensions: {len(embedding_vector)}")
```

### Multiple Contents

```python
# Multiple texts at once
response = client.models.embed_content(
    model="gemini-embedding-001",
    contents=[
        "Python programming tutorial",
        "Machine learning basics", 
        "Data science fundamentals"
    ]
)

for i, embedding in enumerate(response):
    print(f"Text {i}: {len(embedding.values)} dimensions")
```

### With Configuration

```python
from google.genai import types

# Optimized for semantic similarity with custom dimensions
response = client.models.embed_content(
    model="gemini-embedding-001",
    contents="How to implement neural networks?",
    config=types.EmbedContentConfig(
        task_type="SEMANTIC_SIMILARITY",
        output_dimensionality=1536
    )
)
```

### Document Retrieval Setup

```python
# For document indexing
response = client.models.embed_content(
    model="gemini-embedding-001",
    contents="Neural networks are computational models inspired by biological neural networks.",
    config=types.EmbedContentConfig(
        task_type="RETRIEVAL_DOCUMENT",
        title="Neural Networks Introduction",
        output_dimensionality=3072
    )
)
```

### Query Processing

```python
# For search queries
response = client.models.embed_content(
    model="gemini-embedding-001",
    contents="What are neural networks?",
    config=types.EmbedContentConfig(
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=3072
    )
)
```

## Error Handling

```python
try:
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents="Text to embed"
    )
except Exception as e:
    print(f"Embedding error: {e}")
```

## Similarity Calculation

```python
import numpy as np

def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors"""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

# Example usage
text1 = "Machine learning algorithms"
text2 = "AI and ML techniques"

emb1 = client.models.embed_content(model="gemini-embedding-001", contents=text1)
emb2 = client.models.embed_content(model="gemini-embedding-001", contents=text2)

similarity = cosine_similarity(emb1.values, emb2.values)
print(f"Similarity: {similarity}")
```

## Model Specifications

### gemini-embedding-001
- **Dimensions**: 3072 (default), flexible 128-3072
- **Max Input**: 2048 tokens
- **Languages**: 100+ supported
- **Pricing**: $0.15 per 1M input tokens
- **Availability**: General availability (July 2025)

### text-embedding-004
- Alternative model option
- May have different specifications

## Implementation Notes

1. **API Key**: Set `GOOGLE_API_KEY` environment variable or pass to client
2. **Rate Limits**: Check Google AI API documentation for current limits
3. **Batch Processing**: Process multiple contents in single call for efficiency
4. **Caching**: Consider caching embeddings locally to avoid recomputation
5. **Normalization**: Embeddings are normalized for cosine similarity

## Migration from Legacy SDK

If migrating from `google-generativeai`:

**OLD (Deprecated)**:
```python
import google.generativeai as genai
genai.configure(api_key="YOUR_API_KEY")
result = genai.embed_content(model="models/embedding-001", content="text")
```

**NEW (Current)**:
```python
from google import genai
client = genai.Client(api_key="YOUR_API_KEY")
response = client.models.embed_content(model="gemini-embedding-001", contents="text")
```

## Key Differences from Legacy SDK

1. **Client-based**: Use `genai.Client()` instead of global configuration
2. **Method path**: `client.models.embed_content()` vs `genai.embed_content()`
3. **Model names**: `"gemini-embedding-001"` vs `"models/embedding-001"`
4. **Response format**: Different object structure for response
5. **Config object**: Use `types.EmbedContentConfig` for configuration

This is the official, supported SDK for Google's embedding models as of 2025.
