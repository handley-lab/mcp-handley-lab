# MCP Handley Lab Toolkit

A toolkit that bridges AI assistants with command-line tools and services. Built on the Model Context Protocol (MCP), it enables AI models like Claude, Gemini, or GPT to interact with your local development environment, manage calendars, analyze code, and automate workflows through a standardized interface.

## Quick Start

Get up and running in 5 minutes:

```bash
# 1. Clone and enter the project
git clone git@github.com:handley-lab/mcp-handley-lab.git
cd mcp-handley-lab

# 2. Set up Python environment
python3 -m venv venv
source venv/bin/activate

# 3. Install the toolkit (editable mode for development)
pip install -e .

# 4. Set up API keys (export in .bashrc, .env file, or current session)
export OPENAI_API_KEY="sk-..."
export GEMINI_API_KEY="AIza..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_MAPS_API_KEY="AIza..."

# 5. Register tools with Claude
claude mcp add gemini --scope user mcp-gemini
claude mcp add openai --scope user mcp-openai
claude mcp add arxiv --scope user mcp-arxiv
claude mcp add google-maps --scope user mcp-google-maps

# 6. Verify tools are working
# Use /mcp command in Claude to check tool status
```

## Available Tools

### 🤖 **AI Integration** (`gemini`, `openai`)
Connect with major AI providers
  - Persistent conversations with memory
  - Image analysis and generation
  - _Claude example_: `> ask gemini to review the changes you just made`

### 📚 **ArXiv** (`arxiv`)
Search and download academic papers from ArXiv
  - Search by author, title, or topic
  - Download source code, PDFs, or LaTeX files
  - _Claude example_: `> find all papers by Harry Bevins on arxiv`

### 🔍 **Code Flattening** (`code2prompt`)
Convert codebases into structured, AI-readable text
  - Flatten project structure and code into markdown format
  - Include git diffs for review workflows
  - _Claude example_: `> use code2prompt and gemini to look for refactoring opportunities in my codebase`
  - **Requires**: [code2prompt CLI tool](https://github.com/mufeedvh/code2prompt#installation) (`cargo install code2prompt`)

### 📅 **Google Calendar** (`google-calendar`)
Manage your calendar programmatically
  - Create, update, and search events
  - Find free time slots for meetings
  - _Claude example_: `> when did I last meet with Jiamin Hou?, and when would be a good slot to meet with her again this week?`
  - **Requires**: [OAuth2 setup](docs/google-calendar-setup.md)

### 🗺️ **Google Maps** (`google-maps`)
Get directions and routing information
  - Multi-modal directions (driving, walking, cycling, transit)
  - Real-time traffic awareness with departure times
  - Alternative routes and waypoint support
  - _Claude example_: `> what time train do I need to get from Cambridge North to get to Euston in time for 10:30 on Sunday?`
  - **Requires**: Google Maps API key (`GOOGLE_MAPS_API_KEY`)


### 🔧 **JSON Manipulation** (`jq`)
Process JSON data with the power of jq
  - Query, transform, and validate JSON
  - Edit files in-place with transformations
  - _Claude example_: `> use jq to extract the value of the "name" key from the json file at /tmp/data.json`

### 🔗 **Workflow Automation** (`tool-chainer`)
Chain tools together for multi-step tasks
  - Create multi-step workflows with conditions
  - Automate repetitive development tasks
  - _Claude example_: `> use tool-chainer to create a workflow that first analyzes my codebase with code2prompt, then asks gemini to review it`

### ✏️ **Interactive Editing** (`vim`)
Open vim for user input when needed
  - Create or edit content interactively
  - Useful for drafting emails or documentation
  - _Claude example_: `> use vim to open a draft of a relevant email`

### 📝 **Notes Management** (`notes`)
Persistent, searchable note-taking system
  - Human-readable YAML files with automatic tagging
  - Real-time file watching and fast search
  - Automatic server startup for millisecond response times
  - _Claude example_: `> create a note about this conversation in the testing folder`

## Notes System Setup

The notes system automatically starts a background server for optimal performance when first accessed. No additional setup required.

## Using AI Tools Together

You can use AI tools to analyze outputs from other tools. For example:

```bash
# 1. Use code2prompt to summarize your codebase
# Claude will run: mcp__code2prompt__generate_prompt path="/your/project" output_file="/tmp/summary.md"

# 2. Then ask Gemini to review it
# Claude will run: mcp__gemini__ask prompt="Review this codebase" files=[{"path": "/tmp/summary.md"}]
```

This pattern works because:
- `code2prompt` creates a structured markdown file with your code
- AI tools like Gemini can read files as context
- The AI gets a view of your codebase without hitting token limits

## Additional Setup

Some tools require additional configuration:

- **Google Calendar**: Requires OAuth2 setup. See [Google Calendar Setup Guide](docs/google-calendar-setup.md)

## Testing

This project uses `pytest` for testing. The tests are divided into `unit` and `integration` categories.

1.  **Install development dependencies:**
    ```bash
    pip install -e ".[dev]"
    ```

2.  **Run all tests:**
    ```bash
    pytest
    ```

3.  **Run only unit or integration tests:**
    ```bash
    # Run unit tests (do not require network access or API keys)
    pytest -m unit

    # Run integration tests (require API keys and network access)
    pytest -m integration
    ```

## Development

This modular structure makes it easy to use **Claude Code itself** to write new MCP tools. Simply ask Claude to analyze existing tools and create new ones following the same patterns.

*   **Project Structure**: Each tool is a self-contained Python module located in `src/mcp_handley_lab/`. New tools should follow the existing structure. Shared logic is placed in `src/mcp_handley_lab/common/`.
*   **Adding New Tools**: Use Claude Code to generate new tools by analyzing existing implementations and following the established patterns.
*   **Testing Changes**: After modifying tools, Claude Desktop must be restarted to use the updated versions. For development testing, ask Claude to run tools via JSON-RPC without restarting.
*   **Coding Standards**: This project uses `black` for code formatting and `ruff` for linting. Please apply them before submitting changes.
    ```bash
    black .
    ruff check . --fix
    ```
*   **Dependencies**: Project dependencies are managed in `pyproject.toml`.
*   **Entry Points**: Command-line scripts for new tools should be added to the `[project.scripts]` section of `pyproject.toml`.
