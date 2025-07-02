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

- NEVER copy, move, overwrite, or delete files outside `/home/will/code/mcp.3/`
- NEVER modify credential files in `~/` (home directory)
- NEVER touch system files, config files, or user data outside the project
- If testing requires different credentials, configure within the codebase using fixtures/environment variables
- When in doubt, ask the user before touching ANY file outside the project directory
- This prevents data loss and maintains system integrity

## Project Overview

This is an MCP (Model Context Protocol) framework project designed to bridge various external services and command-line utilities into a unified API. The framework provides a comprehensive toolkit for:

- **Code & Git Interaction**: Analyzing, summarizing, and diffing codebases via `code2prompt`
- **AI Model Integration**: Managing interactions with Google Gemini and OpenAI models
- **Productivity & Scheduling**: Google Calendar management
- **Academic Research**: ArXiv paper source code retrieval and analysis
- **Data Manipulation**: JSON querying and editing via `jq`
- **Interactive Editing**: Programmatic `vim` invocation
- **Workflow Automation**: Tool chaining for multi-step automated tasks
- **Persistent Memory**: Agent management with conversational memory for LLMs

## Critical Development Guidelines

### Environment Assumptions
- **CRITICAL**: Assume the environment is properly configured with all required tools installed (code2prompt, jq, vim, etc.) and API keys available (GEMINI_API_KEY, OPENAI_API_KEY, etc.)
- **NEVER use --break-system-packages**: Use virtual environments instead for package installations
- Work within a Python virtual environment for all package installations: `python -m venv venv && source venv/bin/activate`
- This is a local toolset, not for wider distribution - failures in practice guide improvements

### Code Philosophy - CONCISE ELEGANCE IS PARAMOUNT

**THE PRIME DIRECTIVE: Write concise, elegant code above all else.**

- **Elegant simplicity**: Every line should justify its existence. If it can be removed without loss of functionality, remove it
- **Ruthless conciseness**: Favor clarity through brevity. Dense but readable code is better than verbose "enterprise" patterns
- **No defensive programming**: This is a local tool - assume happy paths. Add guards only after actual failures occur
- **Trust the environment**: Don't check if tools exist or APIs are configured - they are
- **Minimal abstractions**: Use abstractions only when they eliminate significant duplication (3+ occurrences)
- **Direct over indirect**: Prefer direct function calls over factory patterns, dependency injection, or other indirection
- **Let Python be Python**: Use built-in features, list comprehensions, and standard library over custom implementations
- **Use standard library where possible**: Prefer `mimetypes`, `pathlib.Path.rglob()`, `subprocess` over manual implementations
- **Prefer functional design**: Use stateless functions with explicit parameters over classes with mutable state
- **Alpha software mindset**: Don't worry about backwards compatibility - break APIs freely to improve design

### ⚠️ CRITICAL ERROR HANDLING RULE

**NEVER SILENCE ERRORS BY DISABLING FUNCTIONALITY**

- **Errors must be fixed, not hidden**: When functionality breaks, fix the underlying issue rather than turning off the feature
- **No silent fallbacks**: Do not implement fallback modes that silently disable broken features without explicit user notification
- **Fail fast and loud**: Let errors surface immediately so they can be addressed properly
- **Document limitations explicitly**: If a feature has known limitations, document them clearly rather than silently working around them
- **Test-driven fixes**: When something breaks, write a test that reproduces the issue, then fix both the test and the implementation

Examples of prohibited patterns:
- Wrapping API calls in `try/except` that silently continue without the feature
- Adding configuration flags to "disable problematic features"
- Implementing fallback modes that hide broken functionality
- Using `pass` statements to ignore exceptions without user notification

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
6. **Alpha Development**: This is alpha software - APIs may change without notice to improve design

### Version Management
- **CRITICAL**: When bumping versions, update ALL version files: `pyproject.toml` AND `PKGBUILD`
- **GitHub CI requires**: Both files must have matching version numbers to pass version check
- **Version format**: Use semantic versioning with alpha suffix (e.g., `0.0.0a13`)

### Development Phases

1. **Phase 1**: Project setup with common utilities (config, memory, pricing) ✓ **COMPLETE**
2. **Phase 2**: Simple CLI-based tools (jq, vim) ✓ **COMPLETE**
3. **Phase 3**: External API integrations (Google Calendar, LLM providers) ✓ **COMPLETE**
4. **Phase 4**: Complex tools (code2prompt, tool_chainer) ✓ **COMPLETE**
5. **Phase 5**: Comprehensive testing and documentation ✓ **COMPLETE**

## Completed Implementations

### Vim Tool ✓ **100% Test Coverage**
- **Location**: `src/mcp_handley_lab/vim/`
- **Functions**: `prompt_user_edit`, `quick_edit`, `open_file`, `server_info`
- **Features**: Instructions support, diff output, backup creation, file extension detection
- **Tests**: 24 test cases covering all functionality and edge cases
- **Status**: Production ready with comprehensive error handling

### Google Calendar Tool ✓ **100% Test Coverage**
- **Location**: `src/mcp_handley_lab/google_calendar/`
- **Functions**: `list_events`, `get_event`, `create_event`, `update_event`, `delete_event`, `list_calendars`, `find_time`, `server_info`
- **Features**: OAuth2 authentication, calendar management, event CRUD operations, free time finding
- **Tests**: 51 test cases covering all functionality, error handling, and edge cases
- **Status**: Production ready with comprehensive API integration

### Gemini LLM Tool ✓ **100% Test Coverage**
- **Location**: `src/mcp_handley_lab/llm/gemini/`
- **Functions**: `ask`, `analyze_image`, `generate_image`, `create_agent`, `list_agents`, `agent_stats`, `get_response`, `clear_agent`, `delete_agent`, `server_info`
- **Features**: Text generation, image analysis, image generation with Imagen 3, Google Search grounding, persistent agent memory, file input support
- **SDK**: Migrated to official `google-genai` SDK (replacing deprecated `google-generativeai`)
- **Tests**: 56 unit tests + 9 integration tests covering all functionality and API compatibility
- **Status**: Production ready with full google-genai integration

### OpenAI LLM Tool ✓ **100% Test Coverage**
- **Location**: `src/mcp_handley_lab/llm/openai/`
- **Functions**: `ask`, `analyze_image`, `generate_image`, `get_response`, `server_info`
- **Features**: Text generation, image analysis, image generation with DALL-E, persistent agent memory, file input support
- **Tests**: 6 integration tests covering all functionality and API compatibility
- **Status**: Production ready with full OpenAI integration

### Tool Chainer Tool ✓ **100% Test Coverage**
- **Location**: `src/mcp_handley_lab/tool_chainer/`
- **Functions**: `discover_tools`, `register_tool`, `chain_tools`, `execute_chain`, `show_history`, `clear_cache`, `server_info`
- **Features**: Tool discovery, registration, chaining, conditional execution, variable substitution
- **Tests**: 6 integration tests covering all functionality
- **Status**: Production ready

### ArXiv Tool ✓ **100% Test Coverage**
- **Location**: `src/mcp_handley_lab/arxiv/`
- **Functions**: `download`, `list_files`, `server_info`
- **Features**: Multi-format ArXiv download (src/pdf/tex), file listing, output control ('-' for stdout), caching in /tmp
- **Formats**: 'src' (full source), 'pdf' (PDF file), 'tex' (LaTeX files: .tex/.bib/.bbl only)
- **Tests**: 16 test cases covering all formats, caching, error handling, and integration tests
- **Status**: Production ready with comprehensive caching and output control

## Running Tools

### Unified Entry Point

The project provides a unified entry point for all tools:

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install the package in development mode
pip install -e .

# Use unified entry point
python -m mcp_handley_lab --help                # Show available tools
python -m mcp_handley_lab jq                    # Run JQ tool
python -m mcp_handley_lab vim                   # Run Vim tool
python -m mcp_handley_lab code2prompt           # Run Code2Prompt tool
python -m mcp_handley_lab llm.gemini            # Run Gemini LLM tool
python -m mcp_handley_lab llm.openai          # Run OpenAI LLM tool
python -m mcp_handley_lab google_calendar       # Run Google Calendar tool
python -m mcp_handley_lab tool_chainer        # Run Tool Chainer tool
python -m mcp_handley_lab arxiv                 # Run ArXiv tool

# Or use direct script entries
mcp-handley-lab --help                          # Unified entry point
mcp-jq                                          # Direct JQ tool
mcp-vim                                         # Direct Vim tool
mcp-code2prompt                                 # Direct Code2Prompt tool
mcp-gemini                                      # Direct Gemini tool
mcp-openai                                    # Direct OpenAI tool
mcp-google-calendar                             # Direct Google Calendar tool
mcp-tool-chainer                              # Direct Tool Chainer tool
mcp-arxiv                                       # Direct ArXiv tool
```

### JSON-RPC MCP Server Usage

Each tool runs as a JSON-RPC server following the Model Context Protocol (MCP) specification. Here's how to interact with them:

#### 1. Basic MCP Protocol Sequence

```bash
# Start any tool server (example with Gemini)
source venv/bin/activate
mcp-gemini
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
    "name": "ask", 
    "arguments": {
      "prompt": "What is 2+2?", 
      "output_file": "/tmp/result.txt", 
      "agent_name": false
    }
  }
}
```

#### 3. Complete Working Example

```bash
source venv/bin/activate

# Test Gemini tool via JSON-RPC
(
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}'
echo '{"jsonrpc": "2.0", "method": "notifications/initialized"}'
echo '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}'
echo '{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "ask", "arguments": {"prompt": "What is 5+5?", "output_file": "/tmp/test.txt", "agent_name": false}}}'
) | mcp-gemini
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
    "serverInfo": {"name": "Gemini Tool", "version": "1.9.4"}
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
        "name": "ask",
        "description": "Asks a question to a Gemini model...",
        "inputSchema": {...}
      },
      ...
    ]
  }
}
```

**Tool Call Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [{"type": "text", "text": "Response saved to: /tmp/test.txt..."}],
    "isError": false
  }
}
```

#### 5. Integration with MCP Clients

For integration with MCP clients like Claude Desktop:

```bash
# Test with official MCP client tools
mcp-cli connect stdio mcp-gemini
```

#### 6. Testing and Debugging JSON-RPC

**CRITICAL**: Always test tool functions via JSON-RPC, not just server startup. Starting a server (e.g., `mcp-gemini`) only validates imports and initialization - it doesn't test actual tool execution.

**Common Testing Mistake:**
```bash
# ❌ This only tests server startup, NOT tool function execution
mcp-gemini  # Server starts successfully but tool calls may still fail
```

**Proper Testing Approach:**
```bash
# ✅ Test actual tool execution via JSON-RPC
source venv/bin/activate

# Method 1: Automated test script
python /tmp/test_jsonrpc.py

# Method 2: Manual JSON-RPC commands  
(
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}'
echo '{"jsonrpc": "2.0", "method": "notifications/initialized"}'
echo '{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "ask", "arguments": {"prompt": "What is 2+2?", "output_file": "/tmp/test.txt"}}}'
) | mcp-gemini
```

**Automated Test Script (`/tmp/test_jsonrpc.py`):**
```python
#!/usr/bin/env python3
import subprocess
import json

def test_mcp_jsonrpc():
    process = subprocess.Popen(
        ['mcp-gemini'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
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
            "params": {"name": "ask", "arguments": {"prompt": "What is 2+2?", "output_file": "/tmp/test.txt"}}
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

**CRITICAL: Test Changes Locally Before Using MCP Tools:**
- After making changes to tool implementations, ALWAYS test locally first
- MCP tools won't reflect your changes until the server is restarted
- Test options:
  1. JSON-RPC testing (preferred): Send test messages to the server
  2. Python direct testing: Create test scripts that import and call functions
  3. Unit tests: Run pytest on modified functionality
- Example: After adding search_events to Google Calendar, test with JSON-RPC before attempting mcp__google-calendar__search_events

**Error Examples to Watch For:**
```json
// Missing import error
{"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"Error executing tool ask: Gemini API error: name 'memory_manager' is not defined"}],"isError":true}}

// API key missing  
{"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"Error executing tool ask: Gemini API error: GEMINI_API_KEY not found"}],"isError":true}}
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
    "name": "list_events",
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
      "output_path": "-"
    }
  }
}
```

## Using Gemini Agents for Code Review and Ideation

Leverage Gemini agents as intelligent helpers for code review and brainstorming:

1. **Generate code summary**: Use `mcp__code2prompt__generate_prompt` to create a structured representation of the code
2. **Initialize or select agent**: Create a new agent with `mcp__gemini__create_agent` or use an existing one for the session
3. **Review and ideate**: Use `mcp__gemini__ask` with the gemini-2.5-pro model, passing the code2prompt output as a file

Example workflow:
```bash
# Generate code summary
mcp__code2prompt__generate_prompt path="/path/to/code" output_file="/tmp/code_review.md"

# Create a specialized agent
mcp__gemini__create_agent agent_name="code_reviewer" personality="Expert Python developer focused on clean code and best practices"

# Get review and suggestions
mcp__gemini__ask prompt="Review this code for improvements" agent_name="code_reviewer" model="gemini-2.5-pro" files=[{"path": "/tmp/code_review.md"}]
```


## Reference Documentation

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
- **LLM tools** (Gemini, OpenAI): Convert cancellation to `RuntimeError` with agent memory recording
- **Code2prompt**: Graceful cancellation during codebase analysis
- **Vim tools**: Process cleanup with graceful termination
- **Tool chainer**: Subprocess cleanup during tool execution

### Usage Recommendations

1. **Use stdout for quick queries**: LLM tools default to `output_file="-"` for immediate responses
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
- **Integration tests only**: `python -m pytest tests/test_tool_chainer_integration.py tests/test_openai_integration.py tests/integration/test_jq_integration.py -v`
- **Unit tests only**: `python -m pytest tests/ -k "not integration" --cov=mcp_handley_lab --cov-report=term-missing`
- **Fast integration check**: `python -m pytest tests/test_tool_chainer_integration.py tests/test_openai_integration.py tests/integration/test_jq_integration.py`
- **Target**: 100% test coverage to identify refactoring opportunities

## Key Files

- `greenfield.md`: Comprehensive specification of all tools, their methods, parameters, and implementation strategy
- `.claude/settings.local.json`: Local Claude settings for bash command permissions
