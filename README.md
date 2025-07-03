# MCP Handley Lab Toolkit

A comprehensive toolkit that bridges AI assistants with powerful command-line tools and services. MCP Handley Lab enables AI models like Claude, Gemini, or GPT to interact with your local development environment, manage calendars, analyze code, and automate complex workflows.

## What is the Model Context Protocol (MCP)?

The Model Context Protocol (MCP) is a specification that enables AI models, such as Claude, Gemini, or GPT, to interact with external tools and services through a standardized interface. It acts as a bridge, allowing an AI to use specialized programs, scripts, and APIs in the same way a developer uses command-line tools.

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

# 5. Register tools with Claude
claude mcp add gemini --scope user mcp-gemini
claude mcp add openai --scope user mcp-openai
claude mcp add arxiv --scope user mcp-arxiv

# 6. Verify tools are working
# Use /mcp command in Claude to check tool status
```

## Available Tools

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

### 🔧 **JSON Manipulation** (`jq`)
Process JSON data with the power of jq
  - Query, transform, and validate JSON
  - Edit files in-place with transformations
  - _Claude example_: `> use jq to extract the value of the "name" key from the json file at /tmp/data.json`

### 🤖 **AI Integration** (`gemini`, `openai`)
Connect with major AI providers
  - Persistent conversations with memory
  - Image analysis and generation
  - _Claude example_: `> ask gemini to review the changes you just made`

### 🔗 **Workflow Automation** (`tool-chainer`)
Chain tools together for complex tasks
  - Create multi-step workflows with conditions
  - Automate repetitive development tasks
  - _Claude example_: `> use tool-chainer to create a workflow that first analyzes my codebase with code2prompt, then asks gemini to review it`

### ✏️ **Interactive Editing** (`vim`)
Open vim for user input when needed
  - Create or edit content interactively
  - Useful for drafting emails or documentation
  - _Claude example_: `> use vim to open a draft of a relevant email`

## Using AI Tools Together

One of the most powerful features is using AI tools to analyze outputs from other tools. For example:

```bash
# 1. Use code2prompt to summarize your codebase
# Claude will run: mcp__code2prompt__generate_prompt path="/your/project" output_file="/tmp/summary.md"

# 2. Then ask Gemini to review it
# Claude will run: mcp__gemini__ask prompt="Review this codebase" files=[{"path": "/tmp/summary.md"}]
```

This pattern works because:
- `code2prompt` creates a structured markdown file with your code
- AI tools like Gemini can read files as context
- The AI gets a complete view of your codebase without hitting token limits

## Google Calendar Setup

The Google Calendar tool requires OAuth 2.0 credentials to access your calendar data securely.

1.  **Enable the Google Calendar API:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project or select an existing one.
    *   In the navigation menu, go to **APIs & Services > Library**.
    *   Search for "Google Calendar API" and enable it.

2.  **Create OAuth 2.0 Credentials:**
    *   Go to **APIs & Services > Credentials**.
    *   Click **+ CREATE CREDENTIALS** and select **OAuth client ID**.
    *   If prompted, configure the consent screen. Select **External** and provide an app name, user support email, and developer contact information.
    *   For the **Application type**, select **Desktop app**.
    *   Click **Create**.

3.  **Download and Save Credentials:**
    *   A dialog will appear with your credentials. Click **DOWNLOAD JSON**.
    *   Save this file to the path you specified in `GOOGLE_CREDENTIALS_FILE` in your configuration (e.g., `~/.config/google/credentials.json`).

4.  **First-time Authentication:**
    *   The first time you run the `mcp-google-calendar` tool, it will open a browser window asking you to authorize access to your Google Calendar.
    *   Complete the authorization flow. The tool will then create and save a token file at the path specified by `GOOGLE_TOKEN_FILE` (e.g., `~/.config/google/token.json`) for future, non-interactive use.

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
*   **Coding Standards**: This project uses `black` for code formatting and `ruff` for linting. Please apply them before submitting changes.
    ```bash
    black .
    ruff check . --fix
    ```
*   **Dependencies**: Project dependencies are managed in `pyproject.toml`.
*   **Entry Points**: Command-line scripts for new tools should be added to the `[project.scripts]` section of `pyproject.toml`.
# Test change
