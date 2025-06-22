# MCP Framework

A comprehensive Model Context Protocol (MCP) toolkit bridging external services and CLI utilities.

## Features

- **JQ Tool**: JSON manipulation using the powerful jq command-line processor
- **Vim Tool**: Interactive text editing capabilities
- **Code2Prompt**: Codebase analysis and summarization (coming soon)
- **Google Calendar**: Full calendar management integration (coming soon)
- **LLM Integration**: Gemini and OpenAI model access (coming soon)
- **Tool Chainer**: Workflow automation via tool composition (coming soon)

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e .
```

## Configuration

Copy `.env.example` to `.env` and add your API keys:

```bash
cp .env.example .env
# Edit .env with your API keys
```

## Running Tools

Each tool can be run as a standalone MCP server:

```bash
# JQ Tool
python -m mcp_framework.jq

# Vim Tool
python -m mcp_framework.vim

# Or use the console scripts
mcp-jq
mcp-vim
```

## Testing with MCP Client

```bash
# Install MCP client if not already installed
pip install mcp-cli

# Connect to a tool
mcp-cli connect stdio python -m mcp_framework.jq
```

## Development

See [CLAUDE.md](CLAUDE.md) for development guidelines and architecture details.