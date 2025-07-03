# MCP Handley Lab Toolkit

## What is the Model Context Protocol (MCP)?

The Model Context Protocol (MCP) is a specification that enables AI models, such as Claude, Gemini, or GPT, to interact with external tools and services through a standardized interface. It acts as a bridge, allowing an AI to use specialized programs, scripts, and APIs in the same way a developer uses command-line tools.

Each tool runs as a small server that listens for requests from an MCP client. This allows an AI assistant to perform complex tasks like analyzing a codebase, managing calendar events, or searching for academic papers by calling the appropriate tool.

## Available Tools

*   **ArXiv (`arxiv`)**: Searches for academic papers on ArXiv and downloads their source code or PDF files.
  * _claude code example_: `> find all papers by Harry Bevins on arxiv` 
*   **Code flattening (`code2prompt`)**: converts local codebases to structured, token-aware summaries suitable for consumption by LLMs. Includes support for `git diff`.
  * _claude code example_: `> use code2prompt and gemini to look for refactoring opportunities in my codebase`
*   **Google Calendar (`google-calendar`)**: Provides integration with Google Calendar for creating, listing, updating, deleting, and searching events, as well as finding free time slots.
  * _claude code example_: `> when did I last meet with Jiamin Hou?, and when would be a good slot to meet with her again this week?` 
*   **JSON Manipulation (`jq`)**: A wrapper around the `jq` command-line tool for querying, editing, validating, and formatting JSON data.
  *  _claude code example_: `> use jq to extract the value of the "name" key from the json file at /tmp/data.json`
*   **LLM Integration (Claude, Gemini, OpenAI)**: Standardized tools for interacting with major LLM providers. These tools share a common interface for text and image analysis, and image generation. They integrate with the Agent Management tool for persistent conversations.
  * _claude code example_: `> ask gemini to review the changes you just made`
*   **Tool Chainer (`tool-chainer`)**: A meta-tool to create, manage, and execute workflows by chaining other MCP tools together with conditional logic.
  * _claude code example_: `> use tool-chainer to create a workflow that first analyzes my codebase with code2prompt, then asks gemini to review it` 
*   **Interactive Editing (`vim`)**: Programmatically opens an interactive `vim` session for user-driven content creation and editing, and captures the results.
  * _claude code example_: `> use vim to open a draft of a relevant email`

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
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

The framework requires API keys for services like OpenAI, Gemini, and Google Calendar. These can be configured using a `.env` file or shell environment variables.

### Option 1: Using a `.env` File

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

### Option 2: Using Shell Environment Variables

Alternatively, you can set the configuration variables directly in your shell's environment.

1.  **Add export commands to your shell profile:**
    Edit your `~/.bashrc`, `~/.bash_profile`, or `~/.zshrc` file to include the following lines:

    ```bash
    # LLM API Keys
    export OPENAI_API_KEY="sk-..."
    export GEMINI_API_KEY="AIza..."
    export ANTHROPIC_API_KEY="sk-ant-..."
    
    # Google Calendar Configuration
    export GOOGLE_CREDENTIALS_FILE="$HOME/.config/google/credentials.json"
    export GOOGLE_TOKEN_FILE="$HOME/.config/google/token.json"
    ```

2.  **Reload your shell configuration:**
    Run `source ~/.bashrc` (or the appropriate file for your shell) to apply the changes.

The tools will automatically use these environment variables if a `.env` file is not found.

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
