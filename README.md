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

# 3. Install the toolkit
pip install -e .

# 4. Set up your first API key (example with Gemini)
export GEMINI_API_KEY="your-api-key-here"

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

## Installation

1.  **Clone the repository:**
    ```bash
    git clone git@github.com:handley-lab/mcp-handley-lab.git
    cd mcp-handley-lab
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the project:**
    This command installs all required dependencies and makes the command-line scripts for each tool available in your environment. The `-e` flag installs the project in "editable" mode, meaning changes to the source code will be reflected immediately.
    ```bash
    pip install -e .
    ```

## Configuration

The framework requires API keys for services like OpenAI, Gemini, and Google Calendar. You have several options for configuring these:

- **Environment variables**: Export them in your current shell session
- **Shell profile**: Add them to `~/.bashrc`, `~/.zshrc`, or similar
- **`.env` file**: Create a local file in the project directory
- **System-wide**: Set them in `/etc/environment` (Linux/Unix)

Choose the method that best fits your workflow and security requirements.

### Option 1: Using Environment Variables (Recommended for Quick Start)

For immediate use, simply export the required variables in your terminal:

```bash
# Export for current session only
export OPENAI_API_KEY="sk-..."
export GEMINI_API_KEY="AIza..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Option 2: Using Shell Profile (Recommended for Regular Use)

Add the environment variables to your shell's configuration file for persistence across sessions:

```bash
# Add to ~/.bashrc, ~/.zshrc, or equivalent
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.bashrc
echo 'export GEMINI_API_KEY="AIza..."' >> ~/.bashrc
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc

# Reload your shell configuration
source ~/.bashrc
```

### Option 3: Using a `.env` File

1.  **Create the `.env` file:**
    Copy the example file to create your local configuration.
    ```bash
    cp .env.example .env
    ```

2.  **Add your API keys to the `.env` file:**
    Open the `.env` file in a text editor and fill in the required values.

    ```dotenv
    # .env
    
    # LLM API Keys
    OPENAI_API_KEY="sk-..."
    GEMINI_API_KEY="AIza..."
    ANTHROPIC_API_KEY="sk-ant-..."

    # Google Calendar Configuration (see instructions below)
    GOOGLE_CREDENTIALS_FILE="~/.config/google/credentials.json"
    GOOGLE_TOKEN_FILE="~/.config/google/token.json"
    ```

The tools will automatically detect and use environment variables from any of these sources.

### Google Calendar Setup

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

## Usage

Each tool in this toolkit is an independent MCP server. To use a tool, you first run its server process. Then, you use an MCP client to connect to and interact with that server.

### Running a Tool Server

The recommended way to run a tool is using its dedicated console script:

```bash
# Run the JQ tool server in your terminal
mcp-jq

# In another terminal, run the Gemini LLM tool server
mcp-gemini
```

You can also use the unified `mcp-handley-lab` entry point to list or run tools:

```bash
# List all available tools
mcp-handley-lab --help

# Run the ArXiv tool
mcp-handley-lab arxiv
```

### Interacting with a Tool Server

Use an MCP client, such as `mcp-cli`, to send requests to a running tool server.

```bash
# First, install the MCP command-line client
pip install mcp-cli

# Example: Connect to a running `mcp-jq` server and call its 'query' function
mcp-cli connect stdio mcp-jq --call 'query' '{"data": "{\"a\": 1}", "filter": ".a"}'
```

---

## Tool Reference and Examples

The following sections provide a detailed reference for each tool, including its available functions and usage examples with `mcp-cli`.

### Agent Management (`mcp-agent`)

This tool creates and manages stateful conversational agents, allowing LLM tools to maintain context across multiple interactions.

| Function | Description |
| :--- | :--- |
| `create_agent` | Creates a new named agent with an optional personality or system prompt. |
| `list_agents` | Lists all existing agents with summary statistics (cost, message count, etc.). |
| `agent_stats` | Retrieves detailed statistics and recent history for a specific agent. |
| `clear_agent` | Clears the conversation history of a specified agent. |
| `delete_agent` | Permanently deletes an agent and its history. |
| `get_response` | Retrieves a specific message from an agent's history by its index. |

**Example:**
```bash
# 1. Create a new agent for code reviews
mcp-cli connect stdio mcp-agent --call 'create_agent' '{"agent_name": "code_reviewer", "personality": "You are a senior software engineer."}'

# 2. List all available agents
mcp-cli connect stdio mcp-agent --call 'list_agents'

# 3. Delete the agent
mcp-cli connect stdio mcp-agent --call 'delete_agent' '{"agent_name": "code_reviewer"}'
```

### ArXiv (`mcp-arxiv`)

This tool searches and downloads papers from the ArXiv preprint server.

| Function | Description |
| :--- | :--- |
| `search` | Searches ArXiv using its advanced query syntax. |
| `download` | Downloads a paper's PDF, source code (`src`), or only its LaTeX files (`tex`). |
| `list_files` | Lists all files within a paper's source archive without downloading it. |

**Example:**
```bash
# 1. Search for papers about large language models in the AI category
mcp-cli connect stdio mcp-arxiv --call 'search' '{"query": "ti:\"large language models\" AND cat:cs.AI", "max_results": 5}'

# 2. Download the source code for a specific paper ID
mcp-cli connect stdio mcp-arxiv --call 'download' '{"arxiv_id": "2301.07041", "format": "src"}'
```

### Code Analysis (`mcp-code2prompt`)

This tool analyzes local codebases and Git repositories to produce structured text.

| Function | Description |
| :--- | :--- |
| `generate_prompt` | Creates a summary of a codebase, including file contents and optional git diffs, and saves it to a file. |
| `server_info` | Returns the status and version of the `code2prompt` tool. |

**Example:**
```bash
# Generate a summary of a Python project, excluding the virtual environment
mcp-cli connect stdio mcp-code2prompt --call 'generate_prompt' \
  '{"path": "/path/to/my-project", "output_file": "/tmp/project_summary.md", "include": ["*.py"], "exclude": ["venv/"]}'
```

### Google Calendar (`mcp-google-calendar`)

This tool provides functions for managing Google Calendar events.

| Function | Description |
| :--- | :--- |
| `list_events` | Lists events within a date range, with an optional text search query. |
| `search_events` | Performs an advanced search for events. |
| `get_event` | Retrieves detailed information for a single event by its ID. |
| `create_event` | Creates a new event on a calendar. |
| `update_event` | Updates an existing event. |
| `delete_event` | Deletes an event. |
| `list_calendars` | Lists all calendars accessible to the user. |
| `find_time` | Finds available free time slots for a specified duration. |

**Example:**
```bash
# Create a new 30-minute meeting
mcp-cli connect stdio mcp-google-calendar --call 'create_event' \
  '{"summary": "Project Sync", "start_datetime": "2024-08-15T10:00:00Z", "end_datetime": "2024-08-15T10:30:00Z", "attendees": ["user@example.com"]}'
```

### JSON Manipulation (`mcp-jq`)

This tool is a wrapper for the `jq` command-line utility for processing JSON data.

| Function | Description |
| :--- | :--- |
| `query` | Queries JSON data from a string or file path using a `jq` filter expression. |
| `edit` | Edits a JSON file in-place using a `jq` transformation filter. |
| `read` | Reads and pretty-prints a JSON file. |
| `validate` | Validates the syntax of a JSON string or file. |
| `format` | Pretty-prints or compacts JSON data. |

**Example:**
```bash
# Extract the value of the "name" key from a JSON string
mcp-cli connect stdio mcp-jq --call 'query' \
  '{"data": "{\"user\": {\"name\": \"Alice\"}}", "filter": ".user.name"}'
```

### LLM Tools (`mcp-claude`, `mcp-gemini`, `mcp-openai`)

These tools provide a standardized interface for interacting with large language models from different providers.

| Function | Description |
| :--- | :--- |
| `ask` | Sends a text-based prompt to a model. Supports file context and persistent memory via `agent_name`. |
| `analyze_image` | Sends one or more images along with a text prompt to a vision model. |
| `generate_image`| (Gemini/OpenAI only) Generates an image from a text prompt. |
| `list_models` | Lists all available models from the provider with details on pricing and capabilities. |

**Example:**
```bash
# 1. Create a persistent agent first (see Agent Management section)
mcp-cli connect stdio mcp-agent --call 'create_agent' '{"agent_name": "python_expert"}'

# 2. Ask a question using the agent. The conversation history is now stored.
mcp-cli connect stdio mcp-gemini --call 'ask' \
  '{"prompt": "What is the best way to handle errors in Python?", "agent_name": "python_expert", "output_file": "/tmp/python_errors.md"}'

# 3. Ask a follow-up question. The agent will have the context of the previous turn.
mcp-cli connect stdio mcp-gemini --call 'ask' \
  '{"prompt": "Can you show me a code example?", "agent_name": "python_expert", "output_file": "/tmp/python_example.md"}'
```

### Tool Chainer (`mcp-tool-chainer`)

This is a meta-tool for creating and executing automated workflows that combine multiple MCP tools.

| Function | Description |
| :--- | :--- |
| `discover_tools` | Finds available tools on a specified MCP server. |
| `register_tool` | Registers a tool, making it available for use in a chain. |
| `chain_tools` | Defines a sequence of tool calls with conditional logic. |
| `execute_chain` | Executes a defined chain, substituting variables as needed. |
| `show_history` | Displays the execution history of recently run chains. |
| `clear_cache` | Clears all registered tools, chains, and history. |

**Example:**
```bash
# This example requires two terminals. In the first, run the server:
mcp-tool-chainer

# In the second terminal, use mcp-cli to define and run the chain:
# 1. Register the code analysis tool
mcp-cli call 'register_tool' '{"tool_id": "summarizer", "server_command": "mcp-code2prompt", "tool_name": "generate_prompt"}'

# 2. Register the Gemini LLM tool
mcp-cli call 'register_tool' '{"tool_id": "reviewer", "server_command": "mcp-gemini", "tool_name": "ask"}'

# 3. Define a chain that summarizes a codebase, then asks an AI to review it
mcp-cli call 'chain_tools' '{
  "chain_id": "review_my_code",
  "steps": [
    {
      "tool_id": "summarizer",
      "arguments": {"path": "/path/to/your/project", "output_file": "/tmp/code_summary.md"}
    },
    {
      "tool_id": "reviewer",
      "arguments": {
        "prompt": "Please review this codebase for potential bugs.",
        "files": [{"path": "/tmp/code_summary.md"}],
        "output_file": "/tmp/ai_review.md"
      }
    }
  ]
}'

# 4. Execute the chain
mcp-cli call 'execute_chain' '{"chain_id": "review_my_code"}'
```

### Vim (`mcp-vim`)

This tool provides a way to programmatically open a `vim` session for interactive user input.

| Function | Description |
| :--- | :--- |
| `prompt_user_edit` | Opens Vim with pre-filled content for the user to edit. Returns the final content. |
| `quick_edit` | Opens Vim with an empty buffer for creating new content. |
| `open_file` | Opens an existing local file in Vim for editing. |

**Example:**
```bash
# Open Vim with a Python snippet and instructions for the user to add a docstring
mcp-cli connect stdio mcp-vim --call 'prompt_user_edit' \
  '{"content": "def my_func():\n  pass", "file_extension": ".py", "instructions": "Add a docstring."}'
```

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

*   **Project Structure**: Each tool is a self-contained Python module located in `src/mcp_handley_lab/`. New tools should follow the existing structure. Shared logic is placed in `src/mcp_handley_lab/common/`.
*   **Coding Standards**: This project uses `black` for code formatting and `ruff` for linting. Please apply them before submitting changes.
    ```bash
    black .
    ruff check . --fix
    ```
*   **Dependencies**: Project dependencies are managed in `pyproject.toml`.
*   **Entry Points**: Command-line scripts for new tools should be added to the `[project.scripts]` section of `pyproject.toml`.
