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
- **email tools**: `msmtp`, `mutt`, `notmuch` for email management
- **repl tool**: `tmux` for session management
- **screenshot tool**: `maim`, `wmctrl` for X11 window capture

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
- `uv sync` for a local venv (run tools with `uv run mcp-llm-chat` or `source .venv/bin/activate`)
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
claude mcp add llm-chat --scope user mcp-llm-chat      # Chat with any LLM
claude mcp add llm-image --scope user mcp-llm-image    # Image generation
claude mcp add llm-models --scope user mcp-llm-models  # List available models

# Other essential tools
claude mcp add arxiv --scope user mcp-arxiv
claude mcp add google-maps --scope user mcp-google-maps

# Add additional tools as needed:
# claude mcp add llm-embeddings --scope user mcp-llm-embeddings
# claude mcp add llm-ocr --scope user mcp-llm-ocr
# claude mcp add llm-audio --scope user mcp-llm-audio
# claude mcp add py2nb --scope user mcp-py2nb
# claude mcp add code2prompt --scope user mcp-code2prompt
# claude mcp add google-calendar --scope user mcp-google-calendar
# claude mcp add vim --scope user mcp-vim
# claude mcp add email --scope user mcp-email
# claude mcp add word --scope user mcp-word                        # Word document editing
# claude mcp add mathematica --scope user mcp-mathematica
# claude mcp add repl --scope user mcp-repl
# claude mcp add screenshot --scope user mcp-screenshot
```

Verify tools are working with the `/mcp` command in Claude.

## Available Tools

### 🤖 **Unified LLM Tools** (`llm-chat`, `llm-image`, `llm-embeddings`, `llm-ocr`, `llm-audio`, `llm-models`)
Connect with multiple AI providers through unified interfaces
  - **llm-chat**: Chat with any LLM - provider inferred from model name (e.g., `gpt-5.2` → OpenAI, `gemini-2.5-flash` → Gemini)
  - **llm-image**: Generate images with DALL-E, Imagen, or Grok
  - **llm-embeddings**: Semantic embeddings for text (OpenAI, Gemini, Mistral)
  - **llm-ocr**: Document OCR via Mistral
  - **llm-audio**: Audio transcription via Mistral Voxtral
  - **llm-models**: List all available models across providers
  - Persistent conversations with memory via `agent_name` parameter
  - Supported providers: OpenAI, Gemini, Claude, Mistral, Grok, Groq
  - _Claude example_: `> ask gpt-5.2 to review the changes you just made`

### 📚 **ArXiv** (`arxiv`)
Search and download academic papers from ArXiv
  - Search by author, title, or topic
  - Download source code, PDFs, or LaTeX files
  - _Claude example_: `> find all papers by Harry Bevins on arxiv`

### 📓 **Python/Notebook Conversion** (`py2nb`)
Convert between Python scripts and Jupyter notebooks
  - Bidirectional Python ↔ Jupyter notebook conversion
  - Preserve markdown comments and cell structure
  - _Claude example_: `> convert this Python script to a Jupyter notebook`

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




### 🧮 **Mathematica** (`mathematica`)
Execute Mathematica code and computations
  - Run WolframScript commands and notebooks
  - Perform symbolic and numerical calculations
  - Generate plots and visualizations
  - Export results in various formats
  - _Claude example_: `> use Mathematica to solve this differential equation and plot the solution`
  - **Requires**: [WolframScript](https://www.wolfram.com/wolframscript/) installed and licensed

### ✏️ **Interactive Editing** (`vim`)
Open vim for user input when needed
  - Create or edit content interactively
  - Useful for drafting emails or documentation
  - _Claude example_: `> use vim to open a draft of a relevant email`

### 📧 **Email Management** (`email`)
Comprehensive email workflow integration
  - Send emails with msmtp
  - Compose, reply, and forward with Mutt
  - Search and manage emails with Notmuch
  - Contact management
  - _Claude example_: `> compose an email to the team about the project update`
  - **Requires**: `msmtp`, `mutt`, `notmuch`, and `offlineimap` installed and configured
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

### 🖥️ **REPL Sessions** (`repl`)
Manage interactive REPL sessions for various interpreters
  - Create persistent sessions (bash, python, ipython, aichat, ollama, mathematica)
  - Execute code and retrieve output with cell indexing (In[N]/Out[N])
  - Pass extra arguments to interpreters (e.g., `--matplotlib` for ipython)
  - _Claude example_: `> start an ipython session with matplotlib, create a plot, and show me the figure`
  - **Requires**: `tmux` and the desired interpreter installed

### 📸 **Screenshot Capture** (`screenshot`)
Capture screenshots of windows or the full screen
  - List all windows with ID, class, desktop, and name
  - Capture specific window by name or hex ID
  - Capture full screen
  - Save to file or return image directly
  - _Claude example_: `> show me the matplotlib Figure 1 window`
  - **Requires**: `maim` and `wmctrl` (X11)

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

# Simple query
result = llm.query("What is 2+2?")
print(result.text)  # "The answer is 4."

# With different provider
result = llm.query("Hello", model="openai")

# With provider-specific options
result = llm.query("Search for Python tutorials", model="gemini", options={"grounding": True})

# Access token usage
print(f"Input: {result.input_tokens}, Output: {result.output_tokens}")
```

### Recursive LLM Pattern for Large Documents

For documents too large to fit in context (>100K tokens), use the Recursive LLM pattern inspired by the [RLM paper](https://arxiv.org/abs/2502.07413). This approach processes documents in chunks using sub-LLM calls from within a REPL session:

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
        result = llm.query(f'''Extract key facts from this chunk.
<document_chunk offset="{offset}">
{text}
</document_chunk>''')
        results.append({"offset": offset, "summary": result.text})
        offset += len(chunk)

# Aggregate results
summaries = "\n".join(f"[{r['offset']}]: {r['summary']}" for r in results)
final = llm.query(f"Synthesize these summaries:\n{summaries}")
print(final.text)
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
