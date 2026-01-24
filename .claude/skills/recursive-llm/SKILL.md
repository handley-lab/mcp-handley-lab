---
name: recursive-llm
description: Process documents too large for context using REPL + sub-LLM calls
allowed-tools: []
---

# Recursive LLM Pattern

Use this pattern when processing documents that exceed context limits (>100K tokens).

## When to Use

- Processing very large files (multi-MB text, code repos)
- Aggregating information from many documents
- Tasks requiring dense access to long content
- When direct context would cause quality degradation

## Prerequisites

- `mcp_handley_lab` must be installed in the Python environment
- API keys configured for desired providers (GEMINI_API_KEY, OPENAI_API_KEY, etc.)

## Pattern

1. **Create Python REPL session**
   ```
   mcp__repl__session(action="create", backend="python")
   ```

2. **Import llm module**
   ```python
   from mcp_handley_lab import llm
   ```

3. **Load context via file handle** (don't read entire file into memory)
   ```python
   from pathlib import Path
   context_path = Path("/path/to/large/document.txt")
   context_size = context_path.stat().st_size
   print(f"Context: {context_size:,} bytes")
   ```

4. **Process in chunks with sub-LLM calls**
   ```python
   results = []
   chunk_size = 100_000  # bytes (~25K tokens); adjust based on measured token usage

   with open(context_path, 'rb') as f:
       offset = 0
       while chunk := f.read(chunk_size):
           text = chunk.decode('utf-8', errors='replace')
           # Use delimiters to prevent prompt injection
           result = llm.query(f'''Extract key information from this document chunk.
<document_chunk offset="{offset}">
{text}
</document_chunk>
Summarize the key facts found in this chunk only.''')
           results.append({"offset": offset, "summary": result.text})
           offset += len(chunk)

   # Aggregate results
   summaries = "\n".join(f"[{r['offset']}]: {r['summary']}" for r in results)
   final = llm.query(f"Synthesize these chunk summaries:\n{summaries}")
   print(final.text)
   ```

## API Reference

```python
from mcp_handley_lab import llm

result = llm.query(
    prompt: str,              # The question/task
    model: str = "gemini",    # Provider or model name
    system_prompt: str = "",  # System instructions
    temperature: float = 1.0,
    options: dict = None,     # Provider-specific (grounding, reasoning_effort, etc.)
)

# Result fields:
result.text           # Response text
result.input_tokens   # Tokens used for input
result.output_tokens  # Tokens used for output
result.model_used     # Canonical model ID
result.raw            # Full adapter response for debugging
```

Available if configured in models.yaml with API keys set:
gemini, openai, claude, mistral, grok, groq

## Tips

- Use `model="gemini"` for large context windows
- Use delimiters (`<document>...</document>`) to prevent prompt injection
- Include byte offsets in prompts to preserve provenance
- Cache repeated queries in Python variables
- Use regex/string ops for pattern matching (faster than LLM)
- For parallel processing, use separate processes (not threads)
- Monitor token usage via `result.input_tokens` and `result.output_tokens`
- Start with ~100KB chunks, adjust based on actual token usage
