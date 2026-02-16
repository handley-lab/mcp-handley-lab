# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL SECURITY RULES

**NEVER USE --break-system-packages FLAG**

- This is an externally managed environment (Arch Linux with pacman)
- NEVER run `pip install --break-system-packages` under any circumstances
- If package installation fails, use virtual environments: `python -m venv venv && source venv/bin/activate`
- System package management must remain intact for system stability
- Breaking system packages can corrupt the entire Python installation

**NEVER MODIFY FILES OUTSIDE THE PROJECT DIRECTORY**

- NEVER copy, move, overwrite, or delete files outside the project directory
- NEVER modify credential files in `~/` (home directory)
- NEVER touch system files, config files, or user data outside the project
- If testing requires different credentials, configure within the codebase using fixtures/environment variables
- When in doubt, ask the user before touching ANY file outside the project directory
- This prevents data loss and maintains system integrity

## Project Overview

This is an MCP (Model Context Protocol) framework project designed to bridge various external services and command-line utilities into a unified API. The framework provides a comprehensive toolkit for:

- **Code & Git Interaction**: Converting, flattening, and diffing codebases via `code2prompt`
- **AI Model Integration**: Unified LLM tools supporting Gemini, OpenAI, Claude, Grok, Mistral, and Groq
- **Productivity & Scheduling**: Google Calendar management
- **Academic Research**: ArXiv paper source code retrieval and analysis
- **Persistent Memory**: Agent management with conversational memory for LLMs

## Filing GitHub Issues for MCP Tool Bugs

When you encounter a bug or issue in an MCP tool, file a GitHub issue with `gh issue create`. Reference the correct source file path so developers can locate the code.

### MCP Tool Source Locations

| MCP Server | Tool File | Description |
|------------|-----------|-------------|
| `mcp-llm` | `src/mcp_handley_lab/llm/tool.py` | Chat, vision, image gen, transcribe, OCR, models |
| `mcp-llm-embeddings` | `src/mcp_handley_lab/llm/embeddings/tool.py` | Text embeddings & semantic search |
| `mcp-email` | `src/mcp_handley_lab/email/tool.py` (entry); `email/notmuch/tool.py` (read/update), `email/mutt/tool.py` (send), `email/offlineimap/tool.py` (sync) | Email read/send/update/sync |
| `mcp-google-calendar` | `src/mcp_handley_lab/google_calendar/tool.py` | Calendar CRUD & search |
| `mcp-google-maps` | `src/mcp_handley_lab/google_maps/tool.py` | Directions & routes |
| `mcp-google-photos` | `src/mcp_handley_lab/google_photos/tool.py` | Photo search, browse, detail, download |
| `mcp-repl` | `src/mcp_handley_lab/repl/tool.py` | REPL session management |
| `mcp-mathematica` | `src/mcp_handley_lab/mathematica/tool.py` | Wolfram Language evaluation |
| `mcp-word` | `src/mcp_handley_lab/microsoft/word/tool.py` | Word document read/edit |
| `mcp-excel` | `src/mcp_handley_lab/microsoft/excel/tool.py` | Excel workbook read/edit |
| `mcp-search` | `src/mcp_handley_lab/search/tool.py` | Conversation transcript search |
| `mcp-screenshot` | `src/mcp_handley_lab/screenshot/tool.py` | Window/screen capture |
| `mcp-code2prompt` | `src/mcp_handley_lab/code2prompt/tool.py` | Codebase summarization |
| `mcp-arxiv` | `src/mcp_handley_lab/arxiv/tool.py` | ArXiv paper download |
| `mcp-otter` | `src/mcp_handley_lab/otter/tool.py` | Otter.ai live meeting transcripts |

### Issue Template

```bash
gh issue create \
  --title "fix(<server>): <short description>" \
  --body "## Description
<What happened vs what was expected>

## Source
Tool file: \`<path from table above>\`

## Steps to Reproduce
1. ...
2. ...

## Error Output
\`\`\`
<paste error>
\`\`\`"
```

## ⚠️ CRITICAL: VERSION MANAGEMENT REQUIRED FOR ALL CHANGES

**BEFORE ANY COMMIT OR PR: ALWAYS BUMP VERSION USING THE AUTOMATED SCRIPT**

```bash
# Use the automated version bump script with semantic versioning
python scripts/bump_version.py         # Auto-detect minimal bump (0.0.1b5 → 0.0.1b6, 0.0.1 → 0.0.2)
python scripts/bump_version.py patch   # For bug fixes (0.0.0b5 → 0.0.1)
python scripts/bump_version.py minor   # For new features (0.0.0b5 → 0.1.0)
python scripts/bump_version.py major   # For breaking changes (0.0.0b5 → 1.0.0)

# For development iterations:
python scripts/bump_version.py beta    # Beta versions (0.0.1 → 0.0.1b1, 0.0.1b5 → 0.0.1b6)

# For release process:
python scripts/bump_version.py rc      # Release candidate (0.0.0b5 → 0.0.0rc1)
python scripts/bump_version.py release # Final release (0.0.0rc1 → 0.0.0)

# Test first with dry-run:
python scripts/bump_version.py --dry-run
```

**The script automatically updates both pyproject.toml and PKGBUILD** - never edit version numbers manually.

**GitHub CI WILL FAIL** if versions don't match or aren't bumped from master. This is enforced automatically.

### Commit Quality Standards

**NEVER use `--no-verify` to skip pre-commit hooks.** Pre-commit hooks enforce:
- Code formatting (ruff-format)
- Linting standards (ruff)
- File quality checks (end-of-file-fixer, merge conflicts)

**Always fix linting issues properly:**
```bash
# ✅ Correct approach: Fix the issues
ruff check --fix src/
ruff format src/
git add .
git commit -m "fix: resolve linting issues"

# ❌ NEVER do this:
git commit --no-verify -m "bypass hooks"
```

**If pre-commit hooks fail, diagnose and fix the root cause:**
- Use `ruff check --fix` to auto-fix style issues
- Use `ruff format` for code formatting
- Manually fix any remaining linting errors
- Ensure all files end with newlines

## Critical Development Guidelines

### Environment Assumptions
- **CRITICAL**: Assume the environment is properly configured with all required tools installed (code2prompt, etc.) and API keys available (GEMINI_API_KEY, OPENAI_API_KEY, etc.)
- **NEVER use --break-system-packages**: Use virtual environments instead for package installations
- Work within a Python virtual environment for all package installations: `python -m venv venv && source venv/bin/activate`
- This is a local toolset, not for wider distribution - failures in practice guide improvements

### Code Philosophy - CONCISE ELEGANCE IS PARAMOUNT

**THE PRIME DIRECTIVE: Write concise, elegant code above all else.**

- **Elegant simplicity**: Every line should justify its existence. If it can be removed without loss of functionality, remove it
- **Ruthless concision**: Favor clarity through brevity. Dense but readable code is better than verbose "enterprise" patterns
- **No defensive programming**: This is a local tool - assume happy paths. Add guards only after actual failures occur
- **Trust the environment**: Don't check if tools exist or APIs are configured - they are
- **Minimal abstractions**: Use abstractions only when they eliminate significant duplication (3+ occurrences)
- **Direct over indirect**: Prefer direct function calls over factory patterns, dependency injection, or other indirection
- **Let Python be Python**: Use built-in features, list comprehensions, and standard library over custom implementations
- **Use standard library where possible**: Prefer `mimetypes`, `pathlib.Path.rglob()`, `subprocess` over manual implementations
- **Prefer functional design**: Use stateless functions with explicit parameters over classes with mutable state
- **Beta software mindset**: APIs may change to improve design, though we aim for stability
- **Always use absolute imports**: NEVER use relative imports (`from .module import`) - always use absolute imports (`from mcp_handley_lab.module import`)

### MCP Tool Design - MINIMAL TOOLS, MAXIMUM CAPABILITY

**Prefer fewer tools with more operations over many specialized tools.**

- **Operations over tools**: Prefer a single tool with an `operation` or `action` parameter over multiple tools (e.g., `memory(action="fork")` not `memory_fork()`, `memory_edit()`, `memory_list()`).
- **Claude Code recognizes patterns**: Design tool signatures that Claude naturally understands - simple parameters, clear names, predictable behavior.
- **Avoid tool sprawl**: Before adding a new tool, ask: can this be an operation on an existing tool? Can this be a parameter variation?
- **Descriptions should be complete**: With deferred MCP tools, context consumption is less important. What matters is that when Claude selects a tool, the description provides enough context to use it correctly. List all operations, scopes, and parameters - don't be terse.
- **Async tools don't parallelize**: MCP tools are async, so calling multiple tools "in parallel" provides no speedup. Call them sequentially for clarity.

Example of what NOT to do:
```python
# BAD: 5 tools for one concept
@mcp.tool
def memory_list(): ...
@mcp.tool
def memory_fork(): ...
@mcp.tool
def memory_edit(): ...
@mcp.tool
def memory_delete(): ...
@mcp.tool
def memory_history(): ...
```

Example of preferred approach:
```python
# GOOD: 1 tool with operations
@mcp.tool
def memory(
    action: str,  # "list", "fork", "edit", "delete", "history"
    conversation: str = "main",
    **kwargs
): ...
```

### ⚠️ CRITICAL ERROR HANDLING RULE

**NEVER SILENCE ERRORS BY DISABLING FUNCTIONALITY**

- **Errors must be fixed, not hidden**: When functionality breaks, fix the underlying issue rather than turning off the feature
- **No silent fallbacks**: Do not implement fallback modes that silently disable broken features without explicit user notification
- **Fail fast and loud**: Let errors surface immediately so they can be addressed properly
- **Document limitations explicitly**: If a feature has known limitations, document them clearly rather than silently working around them
- **Test-driven fixes**: When something breaks, write a test that reproduces the issue, then fix both the test and the implementation

**Exceptions - graceful handling is allowed for:**
- **Discovery/injection helpers**: Functions that inject optional context into tool descriptions (e.g., listing available accounts, tags, calendars) may return empty results when optional dependencies are not configured. These enhance UX but tools must still function without them.

Examples of prohibited patterns:
- Wrapping API calls in `try/except` that silently continue without the feature
- Adding configuration flags to "disable problematic features"
- Implementing fallback modes that hide broken functionality
- Using `pass` statements to ignore exceptions without user notification (except for documented discovery helpers)

Examples of what to avoid:
- Checking if a file exists before reading (let it fail with FileNotFoundError)
- Validating API keys are present (assume they are)
- Creating abstract base classes for single implementations
- Writing "just in case" error handling
- Adding type hints for obvious types (let FastMCP infer from usage)
- Global mutable state (prefer stateless functions with explicit storage parameters)
- Complex class hierarchies (prefer simple functions)

### Communication Standards
- **Maintain professional, measured tone**: Throughout all interactions, not just in writing
- **Avoid emojis**: Keep communication professional and clear
- **Use markdown formatting**: Leverage markdown for clarity and structure
- **Evidence-based reporting**: Report current status without premature declarations of success
- **Quantified results**: Present findings with specific metrics and data

## Architecture & Implementation Strategy

The project follows a modern Python SDK approach using `FastMCP` from the MCP SDK. The recommended structure separates each tool into its own module with shared utilities in a common directory.

### Key Implementation Patterns

1. **Tool Implementation**: Each tool uses `@mcp.tool()` decorators with type hints for automatic schema generation
2. **Configuration**: Centralized settings management using `pydantic-settings` with environment variables
3. **Error Handling**: Use specific Python exceptions (ValueError, FileNotFoundError, etc.) - FastMCP handles conversion to MCP errors
4. **Data Modeling**: Pydantic BaseModel for complex data structures
5. **Stateless Design**: Functions take explicit storage_dir parameters instead of using global state
6. **Beta Development**: This is beta software - APIs may change to improve design, though we aim for stability
7. **CRITICAL: Avoid Union types for inputs**: Never use `Union[str, dict, list]` or similar union types for MCP tool parameters. This makes Claude Code integration difficult as Claude cannot determine which type to use. Always use single, specific types (e.g., `str`) and handle type variations internally within the function implementation.

### Development Phases

1. **Phase 1**: Project setup with common utilities (config, memory, pricing) ✓ **COMPLETE**
2. **Phase 2**: External API integrations (Google Calendar, LLM providers) ✓ **COMPLETE**
3. **Phase 3**: Complex tools (code2prompt) ✓ **COMPLETE**
4. **Phase 4**: Comprehensive testing and documentation ✓ **COMPLETE**

## Completed Implementations

### Unified LLM Tools ✓
Provider-agnostic LLM tools supporting Gemini, OpenAI, Claude, Grok, Mistral, and Groq.

#### mcp-llm
- **Location**: `src/mcp_handley_lab/llm/tool.py`
- **Functions**: `chat`, `conversation`, `generate_image`, `transcribe`, `ocr`, `list_models`
- **Features**: Text generation, vision analysis (via `images` param on `chat`), image generation, audio transcription, OCR, model discovery, persistent memory via branches
- **Model Selection**: Use `model` parameter with provider name (gemini, openai, claude, grok, mistral, groq) or specific model ID

#### mcp-llm-embeddings
- **Location**: `src/mcp_handley_lab/llm/embeddings/`
- **Functions**: `get_embeddings`, `calculate_similarity`, `index_documents`, `search_documents`
- **Features**: Text embeddings, semantic search, document indexing

### Google Calendar Tool ✓
- **Location**: `src/mcp_handley_lab/google_calendar/`
- **Functions**: `search_events`, `get_event`, `create_event`, `update_event`, `delete_event`, `list_calendars`, `find_time`

### ArXiv Tool ✓
- **Location**: `src/mcp_handley_lab/arxiv/`
- **Functions**: `download` (formats: src, pdf, tex, bibtex), `search`

## Running Tools

### Unified Entry Point

The project provides a unified entry point for all tools:

```bash
# Install the package
pip install -e .[dev]

# LLM Tools (unified, provider-agnostic)
mcp-llm                                         # Chat, vision, image gen, transcribe, OCR, models
mcp-llm-embeddings                              # Text embeddings & search

# Other Tools
mcp-code2prompt                                 # Codebase summarization
mcp-arxiv                                       # ArXiv paper download
mcp-google-calendar                             # Calendar management
mcp-google-maps                                 # Directions/routes
mcp-email                                       # Email via notmuch
```

### JSON-RPC MCP Server Usage

Each tool runs as a JSON-RPC server following the Model Context Protocol (MCP) specification. Here's how to interact with them:

#### 1. Basic MCP Protocol Sequence

```bash
# Start any tool server (example with LLM chat)
mcp-llm
```

#### 2. JSON-RPC Message Flow

Send these JSON-RPC messages in sequence:

**Step 1: Initialize the server**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "test-client", "version": "1.0.0"}
  }
}
```

**Step 2: Send initialization notification**
```json
{"jsonrpc": "2.0", "method": "notifications/initialized"}
```

**Step 3: List available tools**
```json
{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
```

**Step 4: Call a tool**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "chat",
    "arguments": {
      "prompt": "What is 2+2?",
      "model": "gemini"
    }
  }
}
```

#### 3. Complete Working Example

```bash
# Test LLM chat tool via JSON-RPC
(
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}'
echo '{"jsonrpc": "2.0", "method": "notifications/initialized"}'
echo '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}'
echo '{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "chat", "arguments": {"prompt": "What is 5+5?", "model": "gemini"}}}'
) | mcp-llm
```

#### 4. Expected Responses

**Initialize Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {...},
    "serverInfo": {"name": "LLM Tool", "version": "..."}
  }
}
```

**Tools List Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "chat",
        "description": "Send a message to an LLM. Provider is auto-detected from model name...",
        "inputSchema": {...}
      },
      ...
    ]
  }
}
```

**Tool Call Response (Structured Output):**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": {
          "content": "The answer is 10.",
          "usage": {
            "input_tokens": 15,
            "output_tokens": 8,
            "cost": 0.0002,
            "model_used": "gemini-2.5-pro"
          },
          "agent_name": "session"
        }
      }
    ],
    "isError": false
  }
}
```

#### 5. Integration with MCP Clients

For integration with MCP clients like Claude Desktop:

```bash
# Test with official MCP client tools
mcp-cli connect stdio mcp-llm
```

#### 6. Testing and Debugging JSON-RPC

**CRITICAL**: Always test tool functions via JSON-RPC, not just server startup. Starting a server only validates imports and initialization - it doesn't test actual tool execution.

**Common Testing Mistake:**
```bash
# ❌ This only tests server startup, NOT tool function execution
mcp-llm  # Server starts successfully but tool calls may still fail
```

**Proper Testing Approach:**
```bash
# ✅ Test actual tool execution via JSON-RPC
(
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}'
echo '{"jsonrpc": "2.0", "method": "notifications/initialized"}'
echo '{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "chat", "arguments": {"prompt": "What is 2+2?", "model": "gemini"}}}'
) | mcp-llm
```

**Automated Test Script:**
```python
#!/usr/bin/env python3
import subprocess
import json

def test_mcp_jsonrpc():
    process = subprocess.Popen(
        ['mcp-llm'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=0)

    try:
        # Initialize
        init_request = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                      "clientInfo": {"name": "test-client", "version": "1.0.0"}}
        }
        process.stdin.write(json.dumps(init_request) + '\n')
        process.stdin.flush()
        response = process.stdout.readline()
        print("Initialize:", response.strip())

        # Send initialized notification
        process.stdin.write('{"jsonrpc": "2.0", "method": "notifications/initialized"}\n')
        process.stdin.flush()

        # Test tool call
        ask_request = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "chat", "arguments": {"prompt": "What is 2+2?", "model": "gemini"}}
        }
        process.stdin.write(json.dumps(ask_request) + '\n')
        process.stdin.flush()
        response = process.stdout.readline()
        print("Tool call:", response.strip())

        # Check for errors
        if '"isError":true' in response:
            print("❌ Tool execution failed!")
        else:
            print("✅ Tool execution successful!")

    finally:
        process.terminate()
        process.wait()

if __name__ == "__main__": test_mcp_jsonrpc()
```

**Why JSON-RPC Testing Matters:**
- Server startup only validates imports and FastMCP registration
- Tool execution requires all dependencies and proper imports
- Missing imports (like `memory_manager`) only surface during actual function calls
- Integration issues with shared utilities are caught during JSON-RPC testing
- Claude Code uses JSON-RPC exclusively - direct function calls don't match real usage

**CRITICAL: Restart Required for MCP Tool Changes:**
- After making changes to MCP tool implementations, Claude Code must be restarted for changes to take effect
- This applies to all MCP tools accessed via `mcp__` prefix
- The user must restart Claude Code before testing updated MCP functionality
- For development testing without restarting, use JSON-RPC commands directly as shown above

**CRITICAL: Test Changes Locally Before Using MCP Tools:**
- After making changes to tool implementations, ALWAYS test locally first
- **Claude Desktop must be restarted** to use updated tool versions via MCP
- **When using Claude Code: User must restart Claude Code for tool changes to take effect**
- For development testing without restarting Claude, use JSON-RPC commands directly
- Test options:
  1. JSON-RPC testing (preferred): Send test messages to the server
  2. Python direct testing: Create test scripts that import and call functions
  3. Unit tests: Run pytest on modified functionality
- Example: After adding search_events to Google Calendar, test with JSON-RPC before attempting mcp__google-calendar__search_events

**Error Examples to Watch For:**
```json
// Missing import error
{"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"Error executing tool ask: name 'some_module' is not defined"}],"isError":true}}

// API key missing
{"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"Error executing tool ask: API key not found for provider"}],"isError":true}}
```

#### 7. Tool-Specific Examples

**JQ Tool:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "query",
    "arguments": {
      "data": "{\"users\": [{\"name\": \"Alice\"}]}",
      "filter": ".users[0].name"
    }
  }
}
```

**Google Calendar Tool:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "search_events",
    "arguments": {
      "start_date": "2024-06-25",
      "end_date": "2024-06-26"
    }
  }
}
```

**Code2Prompt Tool:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "generate_prompt",
    "arguments": {
      "path": "/path/to/code",
      "include": ["*.py"],
      "output_file": "/tmp/code_summary.md"
    }
  }
}
```

**ArXiv Tool:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "download",
    "arguments": {
      "arxiv_id": "2301.07041",
      "format": "tex",
      "output_path": "/tmp/result.txt"
    }
  }
}
```

## Using Agents for Code Review and Ideation

Leverage persistent agents as intelligent helpers for code review and brainstorming. This workflow uses the `agent` management system, `code2prompt` for codebase conversion, and any LLM tool for analysis:

1. **Generate code summary**: Use `mcp__code2prompt__generate_prompt` to create a structured representation of the code
2. **Initialize or select agent**: Create a new agent with the dedicated `agent` management system
3. **Review and ideate**: Use `mcp__llm__chat` with the agent for persistent memory

Example workflow:
```bash
# Generate code summary
mcp__code2prompt__generate_prompt path="/path/to/code" output_file="/tmp/code_review.md"

# Get review and suggestions with persistent memory
# The agent will be created automatically on first use
mcp__llm__chat prompt="Review this code for improvements" agent_name="code_reviewer" model="gemini" files=["/tmp/code_review.md"]
```

## MCP Resources

MCP resources provide read-only discovery data that can be cached by clients. Check relevant resources before making tool calls that need discovery info.

Note: Calendar and email discovery data (calendars, tags, folders, accounts) are now injected directly into tool descriptions at module load time, so explicit resource queries are no longer needed for those.

### Available Resources

| Resource URI | Server | Description |
|-------------|--------|-------------|
| `model://list` | mcp-llm | All LLM models grouped by provider with capabilities and pricing |
| `repl://backends` | mcp-repl | All available REPL backends (bash, python, julia, etc.) |

### Usage via JSON-RPC

```bash
# List available resources
{"jsonrpc": "2.0", "id": 1, "method": "resources/list"}

# Read a specific resource
{"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": "model://list"}}
```

### When to Use Resources vs Tools

- **Resources**: Discovery, listing, static/semi-static data (models, REPL backends)
- **Tools**: Actions, mutations, queries with parameters (send email, create event, chat)

## Reference Documentation

### MCP Protocol and SDK Documentation
- **MCP Python SDK README**: https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/refs/heads/main/README.md
- **FastMCP Framework**: Used throughout this project for MCP tool implementation
- **User Input with `ctx.elicit()`**: MCP tools can gather interactive user input using the elicitation mechanism
- **IMPORTANT**: Although the README shows async examples, this project uses synchronous implementations

### Official Pricing and Model Information
- **OpenAI Pricing**: https://platform.openai.com/docs/pricing (Note: Requires authentication)
- **Google Gemini Pricing**: https://ai.google.dev/gemini-api/docs/pricing
- **Anthropic Claude Pricing**: https://docs.anthropic.com/en/docs/about-claude/models/overview#model-pricing

Always verify pricing and model specifications from official sources before updating configurations.

## MCP Tool Interruption and ESC Key Behavior

### ESC Key Behavior in Claude Desktop

**Expected Behavior**: Pressing ESC during MCP tool execution is intended to interrupt incorrect tool calls - this is normal UX behavior.

**Previous Issue**: ESC interruption could break MCP connections, requiring reconnection.

**Solution Implemented**: Added graceful `asyncio.CancelledError` handling to all long-running tools:
- **LLM tools**: Convert cancellation to `RuntimeError` with agent memory recording
- **Code2prompt**: Graceful cancellation during codebase analysis
- **Vim tools**: Process cleanup with graceful termination

### Usage Recommendations

1. **Use file output for responses**: LLM tools save responses to specified output files
2. **ESC interruption is safe**: Connection remains stable after cancellation
3. **Long operations can be cancelled**: Users can safely interrupt incorrect tool calls

### Technical Implementation

```python
try:
    await long_running_operation()
except asyncio.CancelledError:
    # Clean up resources (processes, memory, etc.)
    raise RuntimeError("Operation was cancelled by user")
```

This pattern ensures MCP connection stability while allowing user control over tool execution.

## Task Management

**CRITICAL**: Maintain detailed todo lists with sub-tasks for all work. Break down every major task into smaller, testable components. This ensures nothing is overlooked and provides clear progress tracking.

Example structure:
- Major task
  - Sub-task 1: Specific implementation detail
  - Sub-task 2: Testing component
  - Sub-task 3: Verification step

Always test your implementations before marking tasks as complete.

## Testing Strategy

### Unit Tests vs Integration Tests
- **Unit tests**: Mock external dependencies (APIs, CLIs) for fast, isolated testing
- **Integration tests**: Call real external tools/APIs to validate actual contracts
- **Both are essential**: Unit tests provide breadth, integration tests provide real-world validation

### Modern Testing Philosophy: MCP Protocol First

**CRITICAL**: All integration tests must use MCP protocol (`call_tool()`) instead of direct function calls.

**Why MCP Protocol is Required**:
- Pydantic `Field()` descriptors only work through MCP interface
- Direct function calls pass `FieldInfo` objects instead of actual values
- MCP converts `Field()` descriptors to proper Python types
- FastMCP handles validation and type coercion automatically
- Claude Code uses MCP protocol exclusively - direct calls don't match real usage

**✅ Correct Integration Test Pattern**:
```python
@pytest.mark.asyncio
async def test_tool_function():
    # Use MCP protocol - matches real usage
    _, response = await mcp.call_tool("function_name", {
        "param": "value"
    })
    assert "error" not in response
    result = response  # Properly converted response
```

**❌ NEVER Do This in Integration Tests**:
```python
def test_tool_function():
    # Direct call - bypasses MCP conversion
    result = function_name(param="value")  # WRONG!
```

### Test Categories and Separation of Concerns

Following architectural best practices, tests are organized by concern:

#### **Pure Unit Tests** (Filesystem, Logic, Parsing)
- Mock all external dependencies (APIs, CLIs, file I/O)
- Test business logic in isolation
- Fast execution, no network calls
- Example: `test_mutt_filesystem_operations.py`

#### **CLI Integration Tests** (Command Execution)
- Real CLI commands with mocked filesystem
- Focus on process execution and command construction
- Test CLI interface compatibility
- Example: `test_mutt_cli_integration.py`

#### **API Integration Tests** (Service Integration)
- Real API calls with VCR cassettes for consistency
- Test service integration and response handling
- Validate API contract compliance
- Example: `test_google_calendar_integration.py`

#### **Unhappy Path Tests** (Error Scenarios)
- Systematic error scenario testing
- Authentication failures, invalid inputs, zero results
- Rate limiting, network errors, boundary conditions
- Example: `test_google_calendar_unhappy_paths.py`

#### **Workflow Tests** (End-to-End Scenarios)
- Complete workflows combining multiple components
- Real-world usage scenarios and cross-component integration
- Example: `test_mutt_workflows.py`

### Factory Fixtures for Complex Setup

Use factory fixtures to eliminate test boilerplate:

```python
@pytest.fixture
async def event_creator() -> AsyncGenerator[Callable, None]:
    created_event_ids = []

    async def _event_factory(params: Dict[str, Any]) -> str:
        # Create with defaults + user params
        full_params = {**defaults, **params}
        _, response = await mcp.call_tool("create_event", full_params)
        event_id = response["event_id"]
        created_event_ids.append(event_id)
        return event_id

    yield _event_factory

    # Automatic cleanup
    for event_id in created_event_ids:
        await mcp.call_tool("delete_event", {"event_id": event_id})
```

**Benefits**: Eliminates 15+ lines of boilerplate per test, guaranteed cleanup, focus on test logic.

### Critical Importance of Integration Tests
Integration tests are **essential** for tools that interact with external CLIs or APIs:

1. **Catch CLI parameter mismatches**: Mocked tests can't detect when CLI tools change their argument syntax
2. **Validate real output formats**: Ensure tools actually produce expected data structures
3. **Test environment variations**: Different versions, configurations, and edge cases
4. **Prevent production failures**: Catch breaking changes before they reach users

**Example bugs caught by integration tests that unit tests missed:**
- `--output` vs `--output-file` parameter mismatch
- `--git-diff` vs `--diff` CLI flag error
- `--analyze` flag that doesn't exist in the CLI
- `--git-diff-branch main..feature` vs `--git-diff-branch main feature` argument format

### Integration Test Design Patterns
- **Environment checks**: Gracefully skip when dependencies unavailable
- **Real file I/O**: Create actual temp files and directories
- **Cleanup**: Ensure tests don't leave artifacts
- **Error validation**: Test both success and failure scenarios
- **Comprehensive fixtures**: Rich test data covering multiple scenarios

### Testing Commands
- **All tests**: `python -m pytest tests/ --cov=mcp_handley_lab --cov-report=term-missing`
- **Integration tests only**: `python -m pytest tests/test_openai_integration.py -v`
- **Unit tests only**: `python -m pytest tests/ -k "not integration" --cov=mcp_handley_lab --cov-report=term-missing`
- **Fast integration check**: `python -m pytest tests/test_openai_integration.py`
- **Slow tests excluded**: `python -m pytest tests/ -m "not slow" --cov=mcp_handley_lab --cov-report=term-missing`
- **Email integration tests**: `RUN_SLOW_TESTS=1 python -m pytest tests/integration/test_email_integration.py -v`
- **Target**: 100% test coverage to identify refactoring opportunities

### VCR (HTTP Recording) for Fast Integration Tests
- **VCR now properly configured**: `pytest-vcr>=3.0.0` added to dev dependencies
- **API-based integration tests use VCR**: Record real HTTP requests once, replay for fast subsequent runs
- **VCR cassettes stored in**: `tests/fixtures/vcr_cassettes/` (auto-created)
- **Re-record cassettes**: Delete cassette files and re-run tests to capture new API interactions

## Key Files

- `pyproject.toml`: Package configuration and entry points
- `src/mcp_handley_lab/llm/providers/*/models.yaml`: Model configurations per provider
- `.claude/settings.local.json`: Local Claude settings for bash command permissions
