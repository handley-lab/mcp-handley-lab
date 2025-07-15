# OpenAI Embeddings API Technical Details

## API Endpoint
`POST https://api.openai.com/v1/embeddings`

## Request Format

```python
client.embeddings.create(
    input=str | List[str],
    model=str,
    dimensions=Optional[int],  # Only for v3 models
    encoding_format=Optional[str]  # Default: "float"
)
```

## Response Structure

```python
class EmbeddingResponse:
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: UsageInfo

class EmbeddingData:
    embedding: List[float]
    index: int
    object: str = "embedding"

class UsageInfo:
    prompt_tokens: int
    total_tokens: int
```

## Model Specifications

| Model | Default Dims | Max Dims | Cost per 1K tokens | Performance (MTEB) |
|-------|-------------|----------|--------------------|--------------------|
| text-embedding-3-small | 1536 | 1536 | $0.00002 | 62.3% |
| text-embedding-3-large | 3072 | 3072 | $0.00013 | 64.6% |
| text-embedding-ada-002 | 1536 | 1536 | $0.0001 | 61.0% |

## Error Scenarios

1. **Invalid Model**: Returns 404 with model not found
2. **Token Limit Exceeded**: Returns 400 with token limit error
3. **API Key Issues**: Returns 401 unauthorized
4. **Rate Limit**: Returns 429 with retry-after header
5. **Invalid Input**: Returns 400 with validation error

## Dimensions Parameter Usage

```python
# Full size
response = client.embeddings.create(
    input="text",
    model="text-embedding-3-large"  # 3072 dimensions
)

# Reduced size
response = client.embeddings.create(
    input="text", 
    model="text-embedding-3-large",
    dimensions=1024  # Reduced to 1024 dimensions
)
```

## Batch Processing Limits

- **Max inputs per request**: 2048
- **Max tokens per input**: 8192
- **Max total tokens per request**: ~300K
- **Recommended batch size**: 100-500 inputs

## Rate Limits

- **Tier 1**: 3K requests/minute, 150K tokens/minute
- **Tier 2**: 3.5K requests/minute, 350K tokens/minute  
- **Tier 3**: 5K requests/minute, 1M tokens/minute
- **Tier 4**: 10K requests/minute, 3M tokens/minute
- **Tier 5**: 30K requests/minute, 10M tokens/minute

## Implementation Notes

1. **No Token Counting API**: Unlike Gemini, OpenAI doesn't have separate token counting
2. **Usage in Response**: Token count available in `response.usage.total_tokens`
3. **Consistent Dimensions**: All embeddings in batch have same dimensions
4. **Float Format**: Embeddings are returned as list of floats
5. **Index Ordering**: Results maintain input order via `index` field

## Pricing Calculation

```python
def calculate_cost(tokens: int, model: str) -> float:
    rates = {
        "text-embedding-3-small": 0.00002,
        "text-embedding-3-large": 0.00013, 
        "text-embedding-ada-002": 0.0001
    }
    return (tokens / 1000) * rates.get(model, 0)
```

## Cosine Similarity

Standard cosine similarity calculation works with OpenAI embeddings:

```python
import numpy as np

def cosine_similarity(a: List[float], b: List[float]) -> float:
    a_np = np.array(a)
    b_np = np.array(b)
    return np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np))
```
