# Union Type Elimination Plan

## Objective
Eliminate ALL union types from the MCP tools to create clean, simple APIs that are easy to understand and generate proper schemas for MCP clients.

## Core Principles

### 1. NO Union Types Anywhere
- Replace `list[str | dict[str, str]]` with `list[str]`
- Replace `str | None = None` with `str = "default_value"`
- Replace `int | None = None` with `int = 0` (where 0 = use default)
- Replace complex unions like `str | bool | None` with simple string patterns

### 2. Consistent Default Patterns
- **Lists**: Always use `list[str] = []` (never `list[str] | None = None`)
- **Optional strings**: Use meaningful defaults like `str = ""` or `str = "default"`
- **Optional integers**: Use `int = 0` where 0 means "use system default"
- **Required parameters**: No defaults at all

### 3. String-Based Special Values
Instead of union types, use string conventions:
- `agent_name: str = "session"` where:
  - `"actual_name"` = use named agent
  - `"session"` = use session-based memory (default)
  - `""` = disable memory entirely

## Specific API Changes

### LLM Tools (OpenAI, Gemini, Claude)

**Before (Complex Union Types):**
```python
def ask(
    prompt: str,
    output_file: str | None = "-",
    agent_name: str | bool | None = None,
    files: list[str | dict[str, str]] | None = None,
    max_output_tokens: int | None = None,
) -> str:
```

**After (Clean Simple Types):**
```python
def ask(
    prompt: str,
    output_file: str = "-",
    agent_name: str = "session", 
    files: list[str] = [],
    max_output_tokens: int = 0,
) -> str:
```

### File Handling Simplification

**Before:** Complex union types supporting multiple input formats
```python
files: list[str | dict[str, str]] | None = None
# Supported: ["/path/file.txt", {"path": "/path/file.txt"}, {"content": "text"}]
```

**After:** Simple file paths only
```python
files: list[str] = []
# Supported: ["/path/file.txt", "/path/file2.py"]
```

### Agent Memory Pattern

**Before:** Complex union type
```python
agent_name: str | bool | None = None
# None = session memory, False = no memory, "name" = named agent
```

**After:** Simple string pattern
```python
agent_name: str = "session"
# "session" = session memory, "" = no memory, "name" = named agent
```

### Max Tokens Pattern

**Before:** Union with None
```python
max_output_tokens: int | None = None
# None = use model default
```

**After:** Zero-based default
```python
max_output_tokens: int = 0
# 0 = use model default, >0 = specific limit
```

## Implementation Strategy

### Phase 1: Function Signatures ✅
- Replace all union types in function parameters
- Use simple defaults instead of None values
- Ensure consistent patterns across all tools

### Phase 2: Internal Logic Updates ✅
- Update `if param is not None:` to `if param > 0:` or `if param:`
- Handle new string-based patterns for agent_name
- Maintain backward compatibility in shared functions

### Phase 3: Shared Code Consolidation ✅
- Create `resolve_files_for_llm()` in common.py for simple file path handling
- Create `resolve_images_for_llm()` in common.py for image processing
- Remove duplicated file resolution logic from individual tools
- Keep Gemini-specific logic for Part/Blob objects (API requirement)

### Phase 4: Documentation Updates
- Update all tool descriptions to reflect new simple API
- Remove references to complex input formats
- Clarify string-based special values (agent_name patterns)

### Phase 5: Testing & Validation ✅
- Test all LLM tools via JSON-RPC to ensure proper schema generation
- Verify file handling works with actual file paths
- Confirm MCP clients see clean parameter types (no "unknown" types)

## Expected Benefits

### For MCP Schema Generation
- No more "unknown" parameter types in Claude Code
- Clean, obvious parameter types for all tools
- Better auto-completion and validation in MCP clients

### For Code Maintainability  
- Elimination of complex type checking logic
- Consistent patterns across all tools
- Reduced cognitive load when reading/modifying code
- Fewer edge cases and error conditions

### For API Usability
- Simpler parameter passing (just strings and lists of strings)
- Clear conventions that are self-documenting
- No need to remember complex union type rules
- Consistent behavior across all tools

## Success Criteria

1. **Zero Union Types**: No `|` operators in any function parameter types
2. **Clean Schemas**: MCP clients show specific types for all parameters (no "unknown")
3. **Functional Equivalence**: All existing functionality preserved
4. **Code Reduction**: Significant reduction in type-checking and resolution logic
5. **Test Coverage**: All tools pass JSON-RPC validation tests

## Files Affected

### Core LLM Tools
- `src/mcp_handley_lab/llm/openai/tool.py`
- `src/mcp_handley_lab/llm/gemini/tool.py` 
- `src/mcp_handley_lab/llm/claude/tool.py`
- `src/mcp_handley_lab/llm/common.py` (shared utilities)

### Other Tools
- `src/mcp_handley_lab/jq/tool.py` (remove pydantic constr)
- `src/mcp_handley_lab/vim/tool.py` (clean up optional strings)
- `src/mcp_handley_lab/google_calendar/tool.py` (list defaults)
- `src/mcp_handley_lab/code2prompt/tool.py` (list defaults)

## Implementation Status

- ✅ Phase 1: Function Signatures Updated 
- ✅ Phase 2: Internal Logic Updated  
- ✅ Phase 3: Shared Code Consolidated
- ✅ Phase 4: Documentation Updates Complete
- ✅ Phase 5: Testing & Validation Complete

**ALL PHASES COMPLETE: Union types eliminated across entire codebase. APIs are now clean and simple.**
