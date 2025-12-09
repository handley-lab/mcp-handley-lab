# Thinking/Reasoning Features Research

Research conducted: 2025-12-06

## Executive Summary

All major LLM providers now offer "thinking" or "reasoning" modes that allow models to perform
internal chain-of-thought reasoning before producing responses. This improves performance on
complex tasks like math, coding, and multi-step analysis.

| Provider | Current Status | Implementation Difficulty |
|----------|----------------|---------------------------|
| Mistral | Already implemented (`include_thinking`) | Done |
| Gemini | SDK supports natively | Easy |
| Claude | Requires API changes | Medium |
| OpenAI | Requires new API (Responses) | Medium-Hard |

---

## 1. Mistral (Already Implemented)

**File:** `src/mcp_handley_lab/llm/mistral/tool.py`

### Parameters
- `include_thinking: bool = False` - Include reasoning model thinking in output

### Implementation
```python
def _extract_text_content(content: str | list, include_thinking: bool = True) -> str:
    """Extract text from Mistral response content."""
    if isinstance(content, str):
        return content

    text_parts = []
    for chunk in content:
        if hasattr(chunk, "text"):
            text_parts.append(chunk.text)
        elif hasattr(chunk, "thinking") and include_thinking:
            for think_part in chunk.thinking:
                if hasattr(think_part, "text"):
                    text_parts.append(f"<thinking>\n{think_part.text}\n</thinking>")
    return "\n\n".join(text_parts)
```

### Notes
- Thinking content comes from `ThinkChunk` objects in response
- Wrapped in `<thinking>` tags for clarity
- Works with Magistral reasoning models

---

## 2. Google Gemini

**SDK:** `google-genai` (already using)

### API Parameters

```python
from google.genai.types import ThinkingConfig, ThinkingLevel, GenerateContentConfig

config = GenerateContentConfig(
    thinking_config=ThinkingConfig(
        include_thoughts=True,              # Get thought summaries
        thinking_level=ThinkingLevel.LOW,   # For Gemini 3: "LOW" or "HIGH"
        thinking_budget=1024                # For Gemini 2.5: token count (-1=dynamic)
    )
)
```

### Parameters

| Parameter | Type | Values | Models |
|-----------|------|--------|--------|
| `include_thoughts` | bool | True/False | All thinking models |
| `thinking_level` | enum | `LOW`, `HIGH` | Gemini 3 only |
| `thinking_budget` | int | 128-32768, -1=dynamic, 0=disable | Gemini 2.5 only |

### Model Support

| Model | Default | Range | Disable |
|-------|---------|-------|---------|
| Gemini 3 Pro | Dynamic (HIGH) | LOW/HIGH | Cannot disable |
| Gemini 2.5 Pro | Dynamic | 128-32768 | Cannot disable |
| Gemini 2.5 Flash | Dynamic | 0-24576 | `budget=0` |
| Gemini 2.5 Flash Lite | Off | 512-24576 | `budget=0` |

### Response Format

```python
response = client.models.generate_content(
    model='gemini-2.5-pro',
    contents='What is 2+2?',
    config=config
)

for part in response.candidates[0].content.parts:
    if part.thought:  # Boolean attribute
        print(f"[THINKING]: {part.text}")
    else:
        print(f"[ANSWER]: {part.text}")

# Usage metadata
print(f"Thinking tokens: {response.usage_metadata.thoughts_token_count}")
print(f"Output tokens: {response.usage_metadata.candidates_token_count}")
```

### Implementation Plan

1. Add imports:
   ```python
   from google.genai.types import ThinkingConfig, ThinkingLevel
   ```

2. Add parameters to `ask()`:
   ```python
   include_thoughts: bool = Field(default=False, ...)
   thinking_level: str | None = Field(default=None, ...)  # "low" or "high"
   thinking_budget: int | None = Field(default=None, ...)
   ```

3. Update `_gemini_generation_adapter`:
   - Build `ThinkingConfig` from parameters
   - Add to `GenerateContentConfig`
   - Extract thinking from response parts
   - Include `thoughts_token_count` in usage

---

## 3. OpenAI

### Current State: Chat Completions API

Our current implementation uses `client.chat.completions.create()`:
- Does NOT support reasoning/thinking features
- Does NOT support `reasoning.effort` or `reasoning.summary`
- Reasoning models (o1, o3, gpt-5) work but without reasoning control

### New: Responses API

OpenAI introduced the **Responses API** (`client.responses.create()`) as the recommended
replacement for Chat Completions.

#### Key Differences

| Feature | Chat Completions | Responses API |
|---------|------------------|---------------|
| Endpoint | `/v1/chat/completions` | `/v1/responses` |
| Reasoning control | No | Yes |
| Reasoning summaries | No | Yes |
| Web search tool | No | Yes (built-in) |
| Code interpreter | No | Yes (built-in) |
| File search | No | Yes (built-in) |
| State management | Manual | Automatic (`store: true`) |
| Performance | Baseline | 3% better on SWE-bench |
| Cost | Baseline | 40-80% better cache utilization |

#### Reasoning Parameters

```python
response = client.responses.create(
    model="gpt-5",
    reasoning={
        "effort": "medium",    # "none", "minimal", "low", "medium", "high", "xhigh"
        "summary": "auto"      # "auto", "concise", "detailed"
    },
    input=[{"role": "user", "content": "..."}]
)

# Response includes reasoning output
for item in response.output:
    if item.type == "reasoning":
        print(f"Reasoning summary: {item.summary}")
    elif item.type == "message":
        print(f"Answer: {item.content[0].text}")
```

**Reasoning Effort by Model:**
- `gpt-5.1`: defaults to `none` (no reasoning), supports `none`, `low`, `medium`, `high`
- Models before `gpt-5.1`: default to `medium`, don't support `none`
- `gpt-5-pro`: defaults to and only supports `high`
- `xhigh`: only supported for `gpt-5.1-codex-max`

#### Complete API Mapping

| Chat Completions | Responses API | Notes |
|------------------|---------------|-------|
| `messages` | `input` | Can be string or array |
| `messages[role=system]` | `instructions` | System prompt moved to dedicated param |
| `response.choices[0].message.content` | `response.output_text` | Helper property |
| `response.choices[0].message` | `response.output` | Array of items |
| `response.usage.prompt_tokens` | `response.usage.input_tokens` | Renamed |
| `response.usage.completion_tokens` | `response.usage.output_tokens` | Renamed |
| `max_tokens` | `max_output_tokens` | Renamed |
| `response_format` | `text.format` | Structured outputs |
| N/A | `reasoning` | NEW: reasoning config |
| N/A | `previous_response_id` | NEW: multi-turn |
| N/A | `store` | NEW: state management |

#### Simple Migration Example

```python
# Chat Completions (current)
messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello"}
]
completion = client.chat.completions.create(model="gpt-5", messages=messages)
text = completion.choices[0].message.content

# Responses API (new)
response = client.responses.create(
    model="gpt-5",
    instructions="You are helpful.",
    input="Hello"
)
text = response.output_text
```

#### Multi-turn Conversations

```python
# Chat Completions: manually manage context
messages = [{"role": "user", "content": "Hi"}]
r1 = client.chat.completions.create(model="gpt-5", messages=messages)
messages.append(r1.choices[0].message)
messages.append({"role": "user", "content": "Follow up"})
r2 = client.chat.completions.create(model="gpt-5", messages=messages)

# Responses API: use previous_response_id
r1 = client.responses.create(model="gpt-5", input="Hi")
r2 = client.responses.create(
    model="gpt-5",
    input="Follow up",
    previous_response_id=r1.id
)
```

#### Deprecation Timeline
- **Assistants API**: Deprecated August 26, 2025, sunset August 26, 2026
- **Chat Completions**: Still supported, but Responses recommended for new projects

### Decision: Full Migration to Responses API

We will migrate entirely to the Responses API because:
1. **Better reasoning support**: Native `reasoning.effort` and `reasoning.summary`
2. **Future-proof**: OpenAI recommends for all new projects
3. **Better performance**: 3% improvement on SWE-bench
4. **Lower costs**: 40-80% better cache utilization
5. **Cleaner API**: `output_text` helper, `instructions` param

---

## 4. Anthropic Claude

### Extended Thinking API

```python
response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=16000,
    thinking={
        "type": "enabled",
        "budget_tokens": 10000  # Minimum 1024
    },
    messages=[{"role": "user", "content": "..."}]
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `thinking.type` | str | `"enabled"` to turn on |
| `thinking.budget_tokens` | int | Max thinking tokens (min 1024) |

### Supported Models
- Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`)
- Claude Sonnet 4 (`claude-sonnet-4-20250514`)
- Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
- Claude Opus 4.5 (`claude-opus-4-5-20251101`)
- Claude Opus 4.1 (`claude-opus-4-1-20250805`)
- Claude Opus 4 (`claude-opus-4-20250514`)

### Response Format

```json
{
  "content": [
    {
      "type": "thinking",
      "thinking": "Let me analyze this step by step...",
      "signature": "WaUjzkypQ2mUEVM36O2T..."
    },
    {
      "type": "text",
      "text": "Based on my analysis..."
    }
  ]
}
```

### Key Features
- **Summarized thinking**: Claude 4 models return summaries (not raw thoughts)
- **Streaming**: `thinking_delta` events for streaming
- **Tool use**: Supports interleaved thinking with tools (beta header required)
- **Signature field**: Encrypted verification of thinking blocks
- **Redacted thinking**: Safety-flagged thinking is encrypted

### Pricing
- Billed for full thinking tokens (not summary)
- Thinking from previous turns stripped from context (not billed twice)

### Implementation Plan

1. Add parameters to `ask()`:
   ```python
   enable_thinking: bool = Field(default=False, ...)
   thinking_budget: int = Field(default=10000, ...)
   ```

2. Update adapter:
   ```python
   if enable_thinking:
       params["thinking"] = {
           "type": "enabled",
           "budget_tokens": thinking_budget
       }
   ```

3. Extract thinking from response content blocks

---

## Implementation Priority

### Phase 1: Gemini (Easy)
- SDK already supports it
- Just add parameters and config
- No breaking changes

### Phase 2: Claude (Medium)
- Straightforward API addition
- Need to handle thinking content blocks
- Consider signature preservation for multi-turn

### Phase 3: OpenAI (Hard)
- Requires decision on API migration
- Consider hybrid approach initially
- Full migration later if needed

---

## References

- [Google Gemini Thinking Docs](https://ai.google.dev/gemini-api/docs/thinking)
- [OpenAI Responses API Migration](https://platform.openai.com/docs/guides/migrate-to-responses)
- [OpenAI Reasoning Guide](https://platform.openai.com/docs/guides/reasoning)
- [Anthropic Extended Thinking](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking)
- [Mistral AI Documentation](https://docs.mistral.ai/)
