# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
- Work within a Python virtual environment for all package installations
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

Examples of what to avoid:
- Checking if a file exists before reading (let it fail with FileNotFoundError)
- Validating API keys are present (assume they are)
- Creating abstract base classes for single implementations
- Writing "just in case" error handling
- Adding type hints for obvious types (let FastMCP infer from usage)

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

### Development Phases

1. **Phase 1**: Project setup with common utilities (config, memory, pricing)
2. **Phase 2**: Simple CLI-based tools (jq, vim)
3. **Phase 3**: External API integrations (Google Calendar, LLM providers)
4. **Phase 4**: Complex tools (code2prompt, tool_chainer)
5. **Phase 5**: Comprehensive testing and documentation

## Running Tools Standalone

Each tool can be run independently for testing and development:

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install the package in development mode
pip install -e .

# Run individual tool servers
python -m mcp_framework.jq
python -m mcp_framework.vim
python -m mcp_framework.google_calendar
python -m mcp_framework.llm.gemini
python -m mcp_framework.llm.openai
python -m mcp_framework.code2prompt
python -m mcp_framework.tool_chainer

# Test with MCP client
mcp-cli connect stdio python -m mcp_framework.jq
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

# Get review and suggestions (prefer grounding=true for current information)
mcp__gemini__ask prompt="Review this code for improvements" agent_name="code_reviewer" model="pro" grounding=true files=[{"path": "/tmp/code_review.md"}]
```

**Note**: Always prefer `grounding=true` when using Gemini to ensure access to current information and best practices.

## Testing Strategy

- Unit tests mock external dependencies (APIs, CLIs)
- Integration tests verify tools work together
- Target 100% test coverage to identify refactoring opportunities
- Run tests with: `python -m pytest tests/ --cov=mcp_framework --cov-report=term-missing`

## Key Files

- `greenfield.md`: Comprehensive specification of all tools, their methods, parameters, and implementation strategy
- `.claude/settings.local.json`: Local Claude settings for bash command permissions