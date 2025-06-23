# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL SECURITY RULE

**NEVER USE --break-system-packages FLAG**

- This is an externally managed environment (Arch Linux with pacman)
- NEVER run `pip install --break-system-packages` under any circumstances
- If package installation fails, use virtual environments: `python -m venv venv && source venv/bin/activate`
- System package management must remain intact for system stability
- Breaking system packages can corrupt the entire Python installation

## Project Overview

This is an MCP (Model Context Protocol) framework project designed to bridge various external services and command-line utilities into a unified API. The framework provides a comprehensive toolkit for:

- **Code & Git Interaction**: Analyzing, summarizing, and diffing codebases via `code2prompt`
- **AI Model Integration**: Managing interactions with Google Gemini and OpenAI models
- **Productivity & Scheduling**: Google Calendar management
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
- **Direct over indirect**: Prefer direct function calls over factory patterns, dependency injection, or other indirections
- **Let Python be Python**: Use built-in features, list comprehensions, and standard library over custom implementations
- **Prefer functional design**: Use stateless functions with explicit parameters over classes with mutable state
- **Alpha software mindset**: Don't worry about backwards compatibility - break APIs freely to improve design

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

### Development Phases

1. **Phase 1**: Project setup with common utilities (config, memory, pricing) ✓ **COMPLETE**
2. **Phase 2**: Simple CLI-based tools (jq, vim) ✓ **COMPLETE - 100% test coverage**
3. **Phase 3**: External API integrations (Google Calendar, LLM providers) ✓ **GOOGLE CALENDAR COMPLETE - 100% test coverage**
4. **Phase 4**: Complex tools (code2prompt, tool_chainer)
5. **Phase 5**: Comprehensive testing and documentation

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

## Running Tools Standalone

Each tool can be run independently for testing and development:

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install the package in development mode
pip install -e .

# Run individual tool servers
python -m mcp_handley_lab.jq
python -m mcp_handley_lab.vim
python -m mcp_handley_lab.google_calendar
python -m mcp_handley_lab.llm.gemini
python -m mcp_handley_lab.llm.openai
python -m mcp_handley_lab.code2prompt
python -m mcp_handley_lab.tool_chainer

# Test with MCP client
mcp-cli connect stdio python -m mcp_handley_lab.jq
```

## Using Gemini Agents for Code Review and Ideation

Leverage Gemini agents as intelligent helpers for code review and brainstorming:

1. **Generate code summary**: Use `mcp__code2prompt__generate_prompt` to create a structured representation of the code
2. **Initialize or select agent**: Create a new agent with `mcp__gemini__create_agent` or use an existing one for the session
3. **Review and ideate**: Use `mcp__gemini__ask` with the pro model, passing the code2prompt output as a file

Example workflow:
```bash
# Generate code summary
mcp__code2prompt__generate_prompt path="/path/to/code" output_file="/tmp/code_review.md"

# Create a specialized agent
mcp__gemini__create_agent agent_name="code_reviewer" personality="Expert Python developer focused on clean code and best practices"

# Get review and suggestions
mcp__gemini__ask prompt="Review this code for improvements" agent_name="code_reviewer" model="pro" files=[{"path": "/tmp/code_review.md"}]
```


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
- **Full test suite**: `python -m pytest tests/ --cov=mcp_handley_lab --cov-report=term-missing`
- **Unit tests only**: `python -m pytest tests/test_*.py -k "not Integration"`
- **Integration tests only**: `python -m pytest tests/test_*.py -k "Integration"`
- **Target**: 100% test coverage to identify refactoring opportunities

## Key Files

- `greenfield.md`: Comprehensive specification of all tools, their methods, parameters, and implementation strategy
- `.claude/settings.local.json`: Local Claude settings for bash command permissions
