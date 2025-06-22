# MCP Handley Lab

A comprehensive Model Context Protocol (MCP) framework for the Handley Research Group, providing productivity tools, scientific computing capabilities, and lab administration features.

## Vision

This toolkit aims to be a complete research lab management system covering:

### Personal Productivity & GTD
- **Task Management**: TaskWarrior integration for sophisticated to-do tracking
- **Email Management**: Complete email workflow (OfflineIMAP sync, Mutt/alternative reading, Claude summarization, Notmuch search, msmtp sending)
- **Calendar**: Google Calendar integration with advanced scheduling
- **Filing with RAG**: Intelligent document organization and retrieval

### Scientific Computing
- **Mathematical Computing**: Mathematica integration for advanced calculations
- **Data Visualization**: Comprehensive plotting and analysis tools
- **HPC Access**: High-performance computing cluster management
- **Code Analysis**: Advanced codebase analysis and summarization via code2prompt

### Lab Administration
- **Google Cloud Compute**: Infrastructure management and provisioning
- **Group Resources**: Lab resource administration and allocation
- **Group Personal Assistant**: AI-powered assistance for lab coordination

### Current Features

- **JQ Tool**: JSON manipulation using the powerful jq command-line processor
- **Vim Tool**: Interactive text editing capabilities
- **Code2Prompt**: Codebase analysis and summarization
- **Google Calendar**: Full calendar management integration
- **LLM Integration**: Gemini and OpenAI model access with persistent agents
- **Tool Chainer**: Workflow automation via tool composition

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

## Development Roadmap

### Immediate Priorities
- **Email Integration**: Complete workflow with OfflineIMAP, Mutt, Notmuch, msmtp
- **TaskWarrior Integration**: Sophisticated to-do list management
- **Mathematica Integration**: Mathematical computing capabilities
- **Calendar Enhancements**: Address book integration, batching, UI improvements

### Scientific Tools
- **Data Visualization**: Advanced plotting and analysis capabilities
- **HPC Integration**: Cluster access and job management
- **Research Paper Analysis**: Voice analysis from author's publication corpus

### Infrastructure & Quality
- **Gemini Improvements**: Add grounding, improve schemas, enhance output formatting
- **Testing & Coverage**: Comprehensive test suite with 100% coverage target
- **Documentation**: Complete API documentation and usage examples
- **Chat Interface**: Investigate chat capabilities for interactive workflows

### Advanced Features
- **RAG Filing System**: Intelligent document organization and retrieval
- **Google Cloud Integration**: Compute instance management and provisioning
- **Lab Resource Management**: Group administration and resource allocation
- **Multi-modal AI**: Integration of text, code, and data analysis workflows

## Development

See [CLAUDE.md](CLAUDE.md) for development guidelines and architecture details.