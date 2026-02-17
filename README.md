# MCP Handley Lab Toolkit

> **⚠️ BETA SOFTWARE**: This toolkit is in active development. While functional, APIs may change and some features may have rough edges. Issues and pull requests are welcome!

A toolkit that bridges AI assistants with command-line tools and services. Built on the Model Context Protocol (MCP), it enables AI models like Claude, Gemini, or GPT to interact with your local development environment, manage calendars, analyze code, and automate workflows through a standardized interface.

## Requirements

- **Python**: 3.10 or higher
- **MCP CLI**: `pip install mcp[cli]` (for Claude Desktop integration)
- **Package Manager**: Either standard `pip`/`venv` or [`pipx`](https://github.com/pypa/pipx)
    - Alternatively, [`uv`](https://github.com/astral-sh/uv)/[`uv tool`](https://docs.astral.sh/uv/concepts/tools/) (optional, faster alternative)

### System Dependencies (Optional)
Some tools require additional system packages:
- **code2prompt tool**: `cargo install code2prompt`
- **email tools**: `mutt`, `notmuch`, `offlineimap` for email management
- **repl tool**: `tmux` for session management
- **screenshot tool**: `maim`, `wmctrl` for X11 window capture
- **messenger**: `claude` CLI (Claude Code) for WhatsApp/Telegram bridge

## Quick Start

### Installation with uv tool (Recommended)

[uv tool](https://docs.astral.sh/uv/concepts/tools/) installs Python CLI applications in isolated environments while making them globally available. (Note: `uvx` is an alias for `uv tool run` if you've seen that elsewhere.)

```bash
git clone git@github.com:handley-lab/mcp-handley-lab.git
cd mcp-handley-lab
uv tool install .
```

Then continue to [Configuration](#configuration) to set up API keys and register tools with Claude.

### Alternative: pipx

[pipx](https://github.com/pypa/pipx) provides similar functionality if you don't have uv:

```bash
git clone git@github.com:handley-lab/mcp-handley-lab.git
cd mcp-handley-lab
pipx install .
```

### Arch Linux

A PKGBUILD is included in the repository for native package manager integration:

```bash
git clone git@github.com:handley-lab/mcp-handley-lab.git
cd mcp-handley-lab
makepkg -si
```

This installs to `/usr/bin/` and is managed by pacman. Note that `uv` and `pipx` are also available in the official Arch repos (`pacman -S uv` or `pacman -S python-pipx`).

### Development Installation

For contributors who want to modify the code:

```bash
# Clone and enter the project
git clone git@github.com:handley-lab/mcp-handley-lab.git
cd mcp-handley-lab

# Install editable and globally available
uv tool install -e .
```

Alternatively:
- `uv sync` for a local venv (run tools with `uv run mcp-llm` or `source .venv/bin/activate`)
- Traditional pip: `python3 -m venv venv && source venv/bin/activate && pip install -e .`

## Configuration

After installing, set up API keys and register tools with Claude.

### API Keys

Export in your `.bashrc`/`.zshrc`, a `.env` file, or the current session:

```bash
export OPENAI_API_KEY="sk-..."
export GEMINI_API_KEY="AIza..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
export GROK_API_KEY="grok-..."
export GOOGLE_MAPS_API_KEY="AIza..."
# Note: Google Calendar requires OAuth setup (see tool description below)
```

### Register Tools with Claude

Register only the tools you need to avoid context bloat:

```bash
# Unified LLM tools (one tool handles all providers via model inference)
claude mcp add llm --scope user mcp-llm                # Chat, vision, image gen, transcribe, OCR, models

# Other essential tools
claude mcp add arxiv --scope user mcp-arxiv
claude mcp add google-maps --scope user mcp-google-maps

# Add additional tools as needed:
# claude mcp add llm-embeddings --scope user mcp-llm-embeddings
# claude mcp add code2prompt --scope user mcp-code2prompt
# claude mcp add google-calendar --scope user mcp-google-calendar
# claude mcp add email --scope user mcp-email
# claude mcp add word --scope user mcp-word                        # Word document editing
# claude mcp add excel --scope user mcp-excel                      # Excel spreadsheet editing
# claude mcp add mathematica --scope user mcp-mathematica
# claude mcp add loop --scope user mcp-loop
# claude mcp add otter --scope user mcp-otter                      # Otter.ai transcripts
# claude mcp add screenshot --scope user mcp-screenshot
# claude mcp add search --scope user mcp-search                    # Transcript search
```

Verify tools are working with the `/mcp` command in Claude.

## Available Tools

### 🤖 **Unified LLM Tools** (`llm`, `llm-embeddings`)
Connect with multiple AI providers through unified interfaces
  - **llm**: Chat, vision, image generation, transcription, OCR, model discovery - all in one tool
  - **llm-embeddings**: Semantic embeddings for text (OpenAI, Gemini, Mistral)
  - Provider inferred from model name (e.g., `gpt-5.2` → OpenAI, `gemini-2.5-flash` → Gemini)
  - Persistent conversations with memory via `agent_name` parameter
  - Supported providers: OpenAI, Gemini, Claude, Mistral, Grok, Groq
  - _Claude example_: `> ask gpt-5.2 to review the changes you just made`

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
### 📊 **Excel Spreadsheets** (`excel`)
Comprehensive Excel spreadsheet manipulation via openpyxl
  - **Reading**: Sheet list, cell data (grid/markdown/json), named ranges, tables
  - **Editing**: Set cells, formulas, formatting, add/delete rows/columns/sheets
  - **Tables**: Create structured tables, sort, filter
  - _Claude example_: `> read the sales figures from Sheet1 and add a total row`

### 🧮 **Mathematica** (`mathematica`)
Execute Mathematica code and computations
  - Run WolframScript commands and notebooks
  - Perform symbolic and numerical calculations
  - Generate plots and visualizations
  - Export results in various formats
  - _Claude example_: `> use Mathematica to solve this differential equation and plot the solution`
  - **Requires**: [WolframScript](https://www.wolfram.com/wolframscript/) installed and licensed

### 📧 **Email Management** (`email`)
Comprehensive email workflow integration
  - Compose, reply, and forward with Mutt (interactive sign-off before sending)
  - Search and manage emails with Notmuch
  - Sync mailboxes with offlineimap
  - Contact management
  - _Claude example_: `> compose an email to the team about the project update`
  - **Requires**: `mutt`, `notmuch`, and `offlineimap` installed and configured
  - **Microsoft 365 accounts**: [OAuth2 setup guide](docs/email-oauth2-setup.md)

### 📄 **Word Documents** (`word`)
Comprehensive Word document manipulation via pure OOXML
  - **Reading**: Progressive disclosure (outline → blocks → full), search, metadata
  - **Content**: Paragraphs, headings, tables, images (inline + floating), text boxes
  - **Formatting**: Styles (create/edit/delete), runs, paragraph formatting, tab stops
  - **Tables**: Add/delete rows/columns, merge cells, borders, shading, alignment
  - **Track Changes**: Read revisions, accept/reject individual or all changes
  - **References**: Bookmarks, captions, cross-references, TOC, footnotes/endnotes
  - **Bibliography**: Add sources, insert citations, generate bibliography
  - **Comments**: Add, reply, resolve/unresolve threaded comments
  - **Page Setup**: Margins, orientation, columns, borders, sections, headers/footers
  - **Lists**: Numbered/bulleted lists, promote/demote, restart numbering
  - **Other**: Content controls, equations, hyperlinks, custom properties
  - _Claude example_: `> read the outline of my thesis, then add a citation to Smith2020 in the introduction`

### 🖥️ **Loop Sessions** (`loop`)
Manage persistent REPL and LLM sessions via a background daemon
  - Terminal REPLs: bash, python, ipython, julia, R, clojure, apl, maple, mathematica (via tmux)
  - LLM backends: claude, gemini, openai (via CLI subprocesses with subscription auth)
  - Execute code or chat and retrieve output with cell indexing
  - Pass extra arguments to interpreters (e.g., `--matplotlib` for ipython)
  - _Claude example_: `> start an ipython session with matplotlib, create a plot, and show me the figure`
  - **Requires**: `tmux` for terminal REPLs; `claude`, `gemini`, `codex` CLIs for LLM backends

### 💬 **Messenger** (`messenger`)
Bridge WhatsApp and Telegram to Claude via persistent loop sessions
  - One Claude session per conversation, with automatic session resume across restarts
  - WhatsApp support via webhook (requires Meta Business API setup)
  - Telegram support via long-polling (requires Bot API token from [@BotFather](https://t.me/BotFather))
  - Commands: `/reset` or `/new` to start a fresh session
  - Sessions stored in `~/messenger/{platform}/{id}/`
  - **Not an MCP tool** — runs as a standalone server: `messenger [port]` (default: 8080)
  - **Requires**: `claude` CLI ([Claude Code](https://claude.ai/code)) installed and authenticated

  **Setup:**
  1. Install this package (provides the `messenger` command)
  2. Install and authenticate the `claude` CLI
  3. Set environment variables (see `src/mcp_handley_lab/messenger/.env.example`):
     ```bash
     # Telegram (easiest — just need a bot token)
     export TELEGRAM_BOT_TOKEN="123456:ABC..."
     export TELEGRAM_ALLOWED_CHAT_IDS="12345,67890"  # comma-separated, optional allowlist

     # WhatsApp (requires Meta Business API app + webhook)
     export WHATSAPP_VERIFY_TOKEN="your-verify-token"
     export WHATSAPP_ACCESS_TOKEN="your-access-token"
     export WHATSAPP_PHONE_NUMBER_ID="your-phone-number-id"
     export WHATSAPP_APP_SECRET="your-app-secret"

     # Optional
     export CLAUDE_PERMISSION_MODE="acceptEdits"  # default
     export CLAUDE_SYSTEM_PROMPT="You are a personal assistant."  # default
     ```
  4. Run `messenger` (or `messenger 9090` for a custom port)
  5. For WhatsApp: point your webhook URL to `http://your-server:8080/webhook`

### 🎙️ **Otter.ai Transcripts** (`otter`)
Access live and recent Otter.ai meeting transcripts
  - List live meetings and fetch real-time transcripts
  - Browse and search recent meetings by title
  - Refresh session cookies via headless Playwright
  - _Claude example_: `> what's being said in my current meeting?`
  - **Requires**: Otter.ai account logged in via Chrome; `pip install -e '.[otter]'` for session refresh

### 📸 **Screenshot Capture** (`screenshot`)
Capture screenshots of windows or the full screen
  - List all windows with ID, class, desktop, and name
  - Capture specific window by name or hex ID
  - Capture full screen
  - Save to file or return image directly
  - _Claude example_: `> show me the matplotlib Figure 1 window`
  - **Requires**: `maim` and `wmctrl` (X11)

### 🔎 **Transcript Search** (`search`)
Search and slice across past AI conversation transcripts
  - Full-text search (FTS5) across Claude Code, Codex, Gemini, and MCP memory conversations
  - Slice conversation segments by position for context retrieval
  - List and browse available sessions
  - Sync and index conversation files into a searchable database
  - _Claude example_: `> search my past conversations for discussions about authentication`

## Recommended External MCPs

These MCP servers from other projects complement this toolkit:

| MCP | Description | Installation |
|-----|-------------|--------------|
| [Playwright](https://github.com/microsoft/playwright-mcp) | Browser automation for web scraping and testing | `npx @playwright/mcp@latest` |

See [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) for a comprehensive list of available MCP servers.

## Using AI Tools Together

You can use AI tools to analyze outputs from other tools. For example:

```bash
# 1. Use code2prompt to summarize your codebase
# Claude will run: mcp__code2prompt__generate_prompt path="/your/project" output_file="/tmp/summary.md"

# 2. Then ask any LLM to review it (provider inferred from model name)
# Claude will run: mcp__llm-chat__ask model="gemini-2.5-flash" prompt="Review this codebase" files=["/tmp/summary.md"]
```

This pattern works because:
- `code2prompt` creates a structured markdown file with your code
- The unified `llm-chat` tool can read files as context
- The provider is automatically inferred from the model name

## Direct LLM Access in Python

For advanced workflows, you can use the `llm` module directly from Python without going through MCP:

```python
from mcp_handley_lab import llm

# Stateless query (branch="" disables memory)
result = llm.chat("What is 2+2?", branch="")
print(result.content)  # "The answer is 4."

# With conversation memory (default branch="session")
result = llm.chat("What is 2+2?")
result = llm.chat("Double that")  # Knows context, returns 8

# With different provider
result = llm.chat("Hello", model="openai", branch="")

# With provider-specific options
result = llm.chat("Search for Python tutorials", model="gemini", branch="", options={"grounding": True})

# Access token usage
print(f"Input: {result.usage.input_tokens}, Output: {result.usage.output_tokens}")
```

### Recursive LLM Pattern for Large Documents

For documents too large to fit in context (>100K tokens), use the Recursive LLM pattern inspired by the [RLM paper](https://arxiv.org/abs/2512.24601). This approach processes documents in chunks using sub-LLM calls from within a REPL session:

```python
# In a Python REPL session (mcp__repl__session)
from mcp_handley_lab import llm
from pathlib import Path

# Process a large file in chunks
context_path = Path("/path/to/large/document.txt")
results = []
chunk_size = 100_000  # ~25K tokens

with open(context_path, 'rb') as f:
    offset = 0
    while chunk := f.read(chunk_size):
        text = chunk.decode('utf-8', errors='replace')
        result = llm.chat(f'''Extract key facts from this chunk.
<document_chunk offset="{offset}">
{text}
</document_chunk>''', branch="")  # Stateless sub-calls
        results.append({"offset": offset, "summary": result.content})
        offset += len(chunk)

# Aggregate results
summaries = "\n".join(f"[{r['offset']}]: {r['summary']}" for r in results)
final = llm.chat(f"Synthesize these summaries:\n{summaries}", branch="")
print(final.content)
```

The `/recursive-llm` skill (in `.claude/skills/recursive-llm/SKILL.md`) provides detailed guidance on when and how to use this pattern.


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

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

**Quick start for contributors:**
1. Fork and clone the repository
2. Create a feature branch
3. Make your changes following existing patterns
4. Run tests and linting: `pytest && ruff check .`
5. Bump version: `python scripts/bump_version.py`
6. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.
