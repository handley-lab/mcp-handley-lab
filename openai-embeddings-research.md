# OpenAI Embeddings Research

## Available Models

### text-embedding-3-small
- **Dimensions**: 1536 (default)
- **Cost**: $0.00002 per 1k tokens (5x cheaper than ada-002)
- **Use case**: Most cost-effective with improved accuracy
- **Performance**: Average MIRACL score increased from 31.4% to 44.0%

### text-embedding-3-large  
- **Dimensions**: 3072 (default)
- **Cost**: $0.00013 per 1k tokens
- **Use case**: Best performance option
- **Performance**: Average MIRACL score increased from 31.4% to 54.9%

### text-embedding-ada-002
- **Dimensions**: 1536
- **Status**: Not deprecated, still available
- **Legacy model**: Predecessor to the v3 models

## API Parameters

### Required Parameters
- `input`: String or array of strings to embed
- `model`: Model ID (e.g., "text-embedding-3-small")

### Optional Parameters
- `dimensions`: Reduce dimensions for smaller vectors (new in v3 models)
- `encoding_format`: Format for embeddings (default: "float")

## Key Features

### Dimensions Parameter (New in v3)
- Can shorten embeddings by removing numbers from the end
- Example: text-embedding-3-large from 3072 → 256 dimensions
- Maintains concept-representing properties even when shortened
- Trade-off between performance and storage/cost

### Token Limits
- **Maximum input length**: 8,192 tokens
- **Maximum array size**: 2048 inputs per request
- **Total tokens per request**: ~300K tokens

## Response Format

```json
{
  "object": "list",
  "data": [
    {
      "embedding": [0.0023064255, ..., -0.0028842222],
      "index": 0,
      "object": "embedding"
    }
  ],
  "model": "text-embedding-3-small",
  "usage": {
    "prompt_tokens": 24,
    "total_tokens": 24
  }
}
```

## Python SDK Usage

```python
from openai import OpenAI

client = OpenAI(api_key="YOUR_API_KEY")

# Basic usage
response = client.embeddings.create(
    input="Your text here",
    model="text-embedding-3-small"
)

# With dimensions parameter
response = client.embeddings.create(
    input="Your text here", 
    model="text-embedding-3-large",
    dimensions=1024  # Reduce from 3072 to 1024
)

# Batch processing
response = client.embeddings.create(
    input=["Text 1", "Text 2", "Text 3"],
    model="text-embedding-3-small"
)

# Access embeddings
embeddings = [data.embedding for data in response.data]
total_tokens = response.usage.total_tokens
```

## Implementation Strategy for MCP Tool

Based on Gemini implementation patterns:

1. **Core Functions**:
   - `get_embeddings()` - Generate embeddings for text(s)
   - `calculate_similarity()` - Cosine similarity between texts
   - `index_documents()` - Create searchable document index
   - `search_documents()` - Search index with query

2. **Fail Fast Principles**:
   - Direct API calls without try/catch blocks
   - Trust response structure completely
   - No defensive programming patterns
   - Let OpenAI errors surface directly

3. **Response Handling**:
   - Use `response.data[0].embedding` for direct access
   - Use `response.usage.total_tokens` for usage stats
   - No fallbacks or default values

4. **Batch Processing**:
   - Use `EMBEDDING_BATCH_SIZE = 100` constant
   - Process documents in batches for efficiency
   - Direct list comprehension for result processing

5. **Model Configuration**:
   - Default to "text-embedding-3-small" for cost efficiency
   - Support dimensions parameter for v3 models
   - Maintain backwards compatibility with ada-002
