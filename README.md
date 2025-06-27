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
- **Academic Research**: ArXiv paper source code retrieval and analysis

### Lab Administration
- **Google Cloud Compute**: Infrastructure management and provisioning
- **Group Resources**: Lab resource administration and allocation
- **Group Personal Assistant**: AI-powered assistance for lab coordination

### Implemented Features

- **JQ Tool**: JSON manipulation using the powerful `jq` command-line processor.
- **Vim Tool**: Interactive text editing capabilities using the Vim editor.
- **Code2Prompt**: Codebase analysis and summarization.
- **Google Calendar**: Full calendar management integration, including creating, listing, and updating events.
- **ArXiv Tool**: Multi-format ArXiv paper downloads (source/PDF/LaTeX), with intelligent caching and output control.
- **LLM Integration**: Access to Google Gemini and OpenAI models with support for persistent agents.
    - **ask**: General-purpose question answering.
    - **analyze_image**: Image analysis with vision models.
    - **generate_image**: Image generation with DALL-E and Imagen.
    - **Agent Management**: Create, list, and manage persistent agents for conversational memory.
- **Tool Chainer**: A tool for creating and executing workflows by chaining together other tools.

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
python -m mcp_handley_lab.jq

# Vim Tool
python -m mcp_handley_lab.vim

# Google Calendar Tool
python -m mcp_handley_lab.google_calendar

# Gemini Tool
python -m mcp_handley_lab.llm.gemini

# OpenAI Tool
python -m mcp_handley_lab.llm.openai

# ArXiv Tool  
python -m mcp_handley_lab.arxiv

# Tool Chainer
python -m mcp_handley_lab.tool_chainer
```

You can also use the console scripts:

```bash
mcp-jq
mcp-vim
mcp-code2prompt
mcp-google-calendar
mcp-arxiv
mcp-gemini
mcp-openai
mcp-tool-chainer
mcp-handley-lab
```

## Testing with MCP Client

```bash
# Install MCP client if not already installed
pip install mcp-cli

# Connect to a tool
mcp-cli connect stdio python -m mcp_handley_lab.jq
```

## Development Roadmap

### Implemented
- JQ Tool
- Vim Tool
- Code2Prompt
- Google Calendar
- ArXiv Tool
- LLM Integration (Gemini and OpenAI)
- Tool Chainer

### Partially Implemented
- **Gemini Improvements**: Grounding has been added. Schema improvements and output formatting are ongoing.

### Not Yet Implemented
- Email Integration
- TaskWarrior Integration
- Mathematica Integration
- Data Visualization
- HPC Integration
- RAG Filing System
- Google Cloud Integration

## Development

See [CLAUDE.md](CLAUDE.md) for development guidelines and architecture details.
