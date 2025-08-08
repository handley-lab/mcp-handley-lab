Project Path: src

Source Tree:

```txt
src
└── mcp_handley_lab
    ├── __init__.py
    ├── __main__.py
    ├── arxiv
    │   ├── __init__.py
    │   └── tool.py
    ├── cli
    │   ├── __init__.py
    │   ├── completion.py
    │   ├── config.py
    │   ├── discovery.py
    │   ├── formatter.py
    │   ├── main.py
    │   └── rpc_client.py
    ├── code2prompt
    │   ├── __init__.py
    │   └── tool.py
    ├── common
    │   ├── __init__.py
    │   ├── config.py
    │   ├── pricing.py
    │   ├── process.py
    │   └── terminal.py
    ├── email
    │   ├── __init__.py
    │   ├── common.py
    │   ├── msmtp
    │   │   ├── __init__.py
    │   │   └── tool.py
    │   ├── mutt
    │   │   ├── __init__.py
    │   │   └── tool.py
    │   ├── mutt_aliases
    │   │   ├── __init__.py
    │   │   └── tool.py
    │   ├── notmuch
    │   │   ├── __init__.py
    │   │   └── tool.py
    │   ├── oauth2
    │   │   ├── __init__.py
    │   │   └── tool.py
    │   ├── offlineimap
    │   │   ├── __init__.py
    │   │   └── tool.py
    │   └── tool.py
    ├── google_calendar
    │   ├── __init__.py
    │   └── tool.py
    ├── google_maps
    │   ├── __init__.py
    │   └── tool.py
    ├── llm
    │   ├── __init__.py
    │   ├── agent_utils.py
    │   ├── claude
    │   │   ├── __init__.py
    │   │   └── tool.py
    │   ├── common.py
    │   ├── gemini
    │   │   ├── __init__.py
    │   │   └── tool.py
    │   ├── grok
    │   │   ├── __init__.py
    │   │   └── tool.py
    │   ├── memory.py
    │   ├── model_loader.py
    │   ├── openai
    │   │   ├── __init__.py
    │   │   └── tool.py
    │   └── shared.py
    ├── mathematica
    │   ├── __init__.py
    │   ├── cli.py
    │   └── tool.py
    ├── py2nb
    │   ├── __init__.py
    │   ├── converter.py
    │   ├── models.py
    │   └── tool.py
    ├── shared
    │   └── models.py
    ├── vim
    │   ├── __init__.py
    │   └── tool.py
    └── word
        ├── __init__.py
        ├── converter.py
        ├── models.py
        ├── parser.py
        ├── tool.py
        └── utils.py

```

`src/mcp_handley_lab/__main__.py`:

```py
"""Unified entry point for all MCP tools."""

import importlib
import sys
from pathlib import Path


def get_available_tools():
    """Discover available tools by finding directories with tool.py files."""
    tools_dir = Path(__file__).parent

    tool_files = sorted(tools_dir.rglob("tool.py"))

    tools = []
    for tool_file in tool_files:
        relative_path = tool_file.parent.relative_to(tools_dir)
        tools.append(".".join(relative_path.parts))

    return sorted(t for t in tools if t)


def show_help():
    """Display help message with available tools."""
    tools = get_available_tools()

    print("Usage: python -m mcp_handley_lab <tool_name>")
    print("\nAvailable tools:")
    for tool in tools:
        print(f"  - {tool}")

    print("\nExamples:")
    print("  python -m mcp_handley_lab vim")
    print("  python -m mcp_handley_lab llm.gemini")
    print("  python -m mcp_handley_lab google_calendar")


def main():
    """Main entry point."""
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help", "help"]:
        show_help()
        sys.exit(0)

    tool_name = sys.argv[1]

    module_path = f"mcp_handley_lab.{tool_name}.tool"
    tool_module = importlib.import_module(module_path)
    tool_module.mcp.run()


if __name__ == "__main__":
    main()

```

`src/mcp_handley_lab/arxiv/__init__.py`:

```py
"""ArXiv source code retrieval tool."""

```

`src/mcp_handley_lab/arxiv/tool.py`:

```py
"""ArXiv source code retrieval MCP server."""

import gzip
import os
import tarfile
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from xml.etree import ElementTree

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.shared.models import ServerInfo


class DownloadResult(BaseModel):
    """Result of downloading an ArXiv paper."""

    message: str = Field(
        ...,
        description="A summary message describing the result of the download operation.",
    )
    arxiv_id: str = Field(
        ..., description="The ArXiv ID of the paper that was downloaded."
    )
    format: str = Field(
        ...,
        description="The format of the downloaded content (e.g., 'src', 'pdf', 'tex').",
    )
    output_path: str = Field(
        ...,
        description="The path where the content was saved, or '-' if printed to stdout.",
    )
    size_bytes: int = Field(
        ..., description="The total size of the downloaded content in bytes."
    )
    files: list[str] = Field(
        default_factory=list,
        description="A list of file names included in the downloaded archive.",
    )


class ArxivPaper(BaseModel):
    """
    ArXiv paper metadata.
    Fields may be omitted or truncated depending on the parameters used in the search tool.
    """

    id: str = Field(..., description="The ArXiv ID of the paper (e.g., '2301.07041').")
    title: str | None = Field(default=None, description="The title of the paper.")
    authors: list[str] | None = Field(
        default=None, description="List of authors' names. May be truncated."
    )
    summary: str | None = Field(
        default=None, description="Abstract or summary of the paper. May be truncated."
    )
    published: str | None = Field(
        default=None, description="Publication date in YYYY-MM-DD format."
    )
    categories: list[str] | None = Field(
        default=None, description="ArXiv subject categories (e.g., ['cs.AI', 'cs.LG'])."
    )
    pdf_url: str | None = Field(
        default=None, description="Direct URL to download the PDF version."
    )
    abs_url: str | None = Field(
        default=None, description="URL to the ArXiv abstract page."
    )


mcp = FastMCP("ArXiv Tool")


def _get_cached_source(arxiv_id: str) -> bytes | None:
    """Get cached source archive if it exists."""
    cache_file = Path(tempfile.gettempdir()) / f"arxiv_{arxiv_id}.tar"
    try:
        return cache_file.read_bytes()
    except FileNotFoundError:
        return None


def _cache_source(arxiv_id: str, content: bytes) -> None:
    """Cache source archive for future use."""
    cache_file = Path(tempfile.gettempdir()) / f"arxiv_{arxiv_id}.tar"
    cache_file.write_bytes(content)


def _get_source_archive(arxiv_id: str) -> bytes:
    """Get source archive, using cache if available."""
    cached = _get_cached_source(arxiv_id)
    if cached:
        return cached
    url = f"https://arxiv.org/src/{arxiv_id}"
    with httpx.Client(follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        _cache_source(arxiv_id, response.content)
        return response.content


def _handle_source_content_structured(
    arxiv_id: str, content: bytes, format: str, output_path: str
) -> DownloadResult:
    """Handle source content, trying tar first, then single file."""
    try:
        # Try to handle as tar archive first (most common case)
        return _handle_tar_archive_structured(arxiv_id, content, format, output_path)
    except tarfile.TarError:
        # Not a tar archive, try as single gzipped file
        return _handle_single_file_structured(arxiv_id, content, format, output_path)


def _handle_single_file_structured(
    arxiv_id: str, content: bytes, format: str, output_path: str
) -> DownloadResult:
    """Handle a single gzipped file (not a tar archive)."""
    # Decompress the gzipped content
    decompressed = gzip.decompress(content)
    filename = f"{arxiv_id}.tex"  # Assume it's a tex file

    if output_path == "-":
        # Return file info for stdout
        return DownloadResult(
            message=f"ArXiv source file for {arxiv_id}: single .tex file",
            arxiv_id=arxiv_id,
            format=format,
            output_path=output_path,
            size_bytes=len(decompressed),
            files=[filename],
        )
    else:
        # Save to directory
        os.makedirs(output_path, exist_ok=True)
        file_path = os.path.join(output_path, filename)
        with open(file_path, "wb") as f:
            f.write(decompressed)
        return DownloadResult(
            message=f"ArXiv source saved to directory: {output_path}",
            arxiv_id=arxiv_id,
            format=format,
            output_path=output_path,
            size_bytes=len(decompressed),
            files=[filename],
        )


def _handle_tar_archive_structured(
    arxiv_id: str, content: bytes, format: str, output_path: str
) -> DownloadResult:
    """Handle a tar archive."""
    tar_stream = BytesIO(content)

    with tarfile.open(fileobj=tar_stream, mode="r:*") as tar:
        if output_path == "-":
            # List files for stdout
            files = []
            total_size = 0
            for member in tar.getmembers():
                if member.isfile() and (
                    format != "tex"
                    or any(
                        member.name.endswith(ext) for ext in [".tex", ".bib", ".bbl"]
                    )
                ):
                    files.append(member.name)
                    total_size += member.size

            message = (
                f"ArXiv {'LaTeX' if format == 'tex' else 'source'} files for {arxiv_id}"
            )
            return DownloadResult(
                message=message,
                arxiv_id=arxiv_id,
                format=format,
                output_path=output_path,
                size_bytes=total_size,
                files=files,
            )
        else:
            # Save to directory
            os.makedirs(output_path, exist_ok=True)
            extracted_files = []
            total_size = 0

            if format == "tex":
                # Extract .tex, .bib, .bbl files
                for member in tar.getmembers():
                    if member.isfile() and any(
                        member.name.endswith(ext) for ext in [".tex", ".bib", ".bbl"]
                    ):
                        tar.extract(member, path=output_path, filter="data")
                        extracted_files.append(member.name)
                        total_size += member.size
            else:
                # Extract all files (src format)
                tar.extractall(path=output_path, filter="data")
                for member in tar.getmembers():
                    if member.isfile():
                        extracted_files.append(member.name)
                        total_size += member.size

            return DownloadResult(
                message=f"ArXiv {'LaTeX' if format == 'tex' else 'source'} files saved to directory: {output_path}",
                arxiv_id=arxiv_id,
                format=format,
                output_path=output_path,
                size_bytes=total_size,
                files=extracted_files,
            )


@mcp.tool(
    description="Downloads an ArXiv paper by ID in various formats ('src', 'pdf', 'tex') or lists its source files."
)
def download(
    arxiv_id: str = Field(
        ...,
        description="The unique ArXiv identifier for the paper (e.g., '2301.07041').",
    ),
    format: str = Field(
        "src",
        description="The format of the paper to download. Valid options are 'src', 'pdf', or 'tex'.",
    ),
    output_path: str = Field(
        "",
        description="Path to save the content. For 'pdf' format: saves as a single file. For 'src' and 'tex' formats: creates a directory with this name and extracts files into it. If empty, defaults to '<arxiv_id>.pdf' for pdf or '<arxiv_id>' for source formats. Use '-' to list file info to stdout instead of saving.",
    ),
) -> DownloadResult:
    if format not in ["src", "pdf", "tex"]:
        raise ValueError(f"Invalid format '{format}'. Must be 'src', 'pdf', or 'tex'")

    if not output_path:
        output_path = f"{arxiv_id}.pdf" if format == "pdf" else arxiv_id

    if format == "pdf":
        url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        with httpx.Client(follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        size_bytes = len(response.content)
        if output_path == "-":
            # Return file info for stdout
            return DownloadResult(
                message=f"ArXiv PDF for {arxiv_id}: {size_bytes / (1024 * 1024):.2f} MB",
                arxiv_id=arxiv_id,
                format=format,
                output_path=output_path,
                size_bytes=size_bytes,
                files=[f"{arxiv_id}.pdf"],
            )
        else:
            with open(output_path, "wb") as f:
                f.write(response.content)
            return DownloadResult(
                message=f"ArXiv PDF saved to: {output_path}",
                arxiv_id=arxiv_id,
                format=format,
                output_path=output_path,
                size_bytes=size_bytes,
                files=[output_path],
            )

    else:
        content = _get_source_archive(arxiv_id)
        return _handle_source_content_structured(arxiv_id, content, format, output_path)


def _parse_arxiv_entry(entry: ElementTree.Element) -> dict[str, Any]:
    """Parse a single ArXiv entry from the Atom feed."""
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    def find_text(path, default=""):
        elem = entry.find(path, ns)
        return (
            elem.text.strip().replace("\n", " ")
            if elem is not None and elem.text
            else default
        )

    title = find_text("atom:title")
    summary = find_text("atom:summary")
    id_text = find_text("atom:id")
    arxiv_id = id_text.split("/")[-1].split("v")[0] if id_text else ""
    authors = [
        author.text
        for author in entry.findall("atom:author/atom:name", ns)
        if author.text
    ]

    published_text = find_text("atom:published")
    dt = datetime.fromisoformat(published_text.replace("Z", "+00:00"))
    published_date = dt.strftime("%Y-%m-%d")

    categories = [
        cat.get("term") for cat in entry.findall("atom:category", ns) if cat.get("term")
    ]

    pdf_url = ""
    abs_url = ""
    for link in entry.findall("atom:link", ns):
        if link.get("title") == "pdf":
            pdf_url = link.get("href", "")
        elif link.get("rel") == "alternate":
            abs_url = link.get("href", "")

    return {
        "id": arxiv_id,
        "title": title,
        "authors": authors,
        "summary": summary,
        "published": published_date,
        "categories": categories,
        "pdf_url": pdf_url,
        "abs_url": abs_url,
    }


def _apply_field_filtering(
    paper_dict: dict[str, Any],
    include_fields: list[str] | None,
) -> dict[str, Any]:
    """
    Apply field filtering to a paper dictionary.

    If include_fields is None, returns all fields.
    If include_fields is provided, returns only those fields (plus 'id' which is always included).
    """
    if include_fields is None:
        # Return all fields
        return paper_dict

    # Use specified fields, ensuring 'id' is always included
    included_fields = set(include_fields)
    included_fields.add("id")

    # Filter the paper dictionary
    return {k: v for k, v in paper_dict.items() if k in included_fields}


@mcp.tool(
    description="Searches ArXiv for papers. Supports advanced syntax (e.g., 'au:Hinton', 'ti:attention'). Use include_fields to limit output for context window management."
)
def search(
    query: str = Field(
        ...,
        description="The search query. Supports field prefixes (au, ti, abs, co) and boolean operators (AND, OR, ANDNOT).",
    ),
    max_results: int = Field(
        50,
        description="The maximum number of results to return.",
    ),
    start: int = Field(
        0, description="The starting index for the search results, used for pagination."
    ),
    sort_by: Literal["relevance", "lastUpdatedDate", "submittedDate"] = Field(
        "relevance",
        description="Sorting criteria. Options: 'relevance', 'lastUpdatedDate', 'submittedDate'.",
    ),
    sort_order: Literal["ascending", "descending"] = Field(
        "descending",
        description="Sorting order. Options: 'ascending' or 'descending'.",
    ),
    include_fields: list[
        Literal[
            "id",
            "title",
            "authors",
            "summary",
            "published",
            "categories",
            "pdf_url",
            "abs_url",
        ]
    ]
    | None = Field(
        None,
        description="Specific fields to include in results. If not provided, all fields are included. Available: id, title, authors, summary, published, categories, pdf_url, abs_url.",
    ),
    max_authors: int | None = Field(
        5,
        ge=1,
        description="Max authors to return per paper. If more, a summary is added. Set to null for no limit.",
    ),
    max_summary_len: int | None = Field(
        1000,
        ge=1,
        description="Max summary length (characters). Truncates with '...'. Set to null for no limit.",
    ),
) -> list[ArxivPaper]:
    """
    Searches ArXiv and returns a list of papers with configurable output limiting.
    """
    base_url = "http://export.arxiv.org/api/query"

    params = {
        "search_query": query,  # httpx handles encoding
        "start": start,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }

    try:
        with httpx.Client(follow_redirects=True) as client:
            response = client.get(base_url, params=params)
            response.raise_for_status()
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError:
        raise ValueError(
            "Failed to parse response from ArXiv API. The service may be down or returning invalid data."
        ) from None
    except httpx.HTTPStatusError as e:
        raise ConnectionError(
            f"ArXiv API error: {e.response.status_code} - {e.response.text}"
        ) from e
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    results = []
    for entry in root.findall("atom:entry", ns):
        paper_dict = _parse_arxiv_entry(entry)

        # Apply field-specific limits (truncation)
        if (
            paper_dict["authors"]
            and max_authors is not None
            and len(paper_dict["authors"]) > max_authors
        ):
            num_remaining = len(paper_dict["authors"]) - max_authors
            paper_dict["authors"] = paper_dict["authors"][:max_authors]
            paper_dict["authors"].append(f"... and {num_remaining} more")

        if (
            paper_dict["summary"]
            and max_summary_len is not None
            and len(paper_dict["summary"]) > max_summary_len
        ):
            end = paper_dict["summary"].rfind(" ", 0, max_summary_len)
            paper_dict["summary"] = (
                paper_dict["summary"][: end if end != -1 else max_summary_len] + "..."
            )

        # Apply field filtering
        final_paper_dict = _apply_field_filtering(paper_dict, include_fields)

        results.append(ArxivPaper(**final_paper_dict))

    return results


@mcp.tool(
    description="Checks ArXiv tool status and lists available functions. Use this to discover server capabilities."
)
def server_info() -> ServerInfo:
    return ServerInfo(
        name="ArXiv Tool",
        version="1.0.0",
        status="active",
        capabilities=["search", "download", "server_info"],
        dependencies={
            "httpx": "latest",
            "pydantic": "latest",
            "supported_formats": "src,pdf,tex",
        },
    )

```

`src/mcp_handley_lab/cli/__init__.py`:

```py
"""MCP CLI module for unified command-line interface."""

```

`src/mcp_handley_lab/cli/completion.py`:

```py
"""Shell completion support for MCP CLI."""

from pathlib import Path

import click


def install_completion_script():
    """Install zsh completion script."""

    zsh_completion = """#compdef mcp-cli

_mcp_cli() {
    local curcontext="$curcontext" state line
    local -a commands tools
    typeset -A opt_args

    # Check completion context based on current position
    if [[ $CURRENT -eq 2 ]]; then
        # First tier: tools and options
        local -a tools options

        # Get available tools dynamically
        tools=($(mcp-cli --list-tools 2>/dev/null | awk '/^  [a-zA-Z]/ {print $1}'))

        # Define options
        options=(
            '--help:Show help message'
            '--list-tools:List all available tools'
            '--config:Show configuration file location'
            '--init-config:Create default configuration file'
            '--install-completion:Install zsh completion script'
            '--show-completion:Show completion installation instructions'
        )

        # Add completions without group labels
        _describe '' tools
        _describe '' options
        return 0
    elif [[ $CURRENT -eq 3 && $words[2] && $words[2] != -* ]]; then
        # Second tier: functions and tool options
        local tool=$words[2]
        local -a functions options

        # Get functions for the selected tool
        functions=($(mcp-cli $tool --help 2>/dev/null | awk '/^FUNCTIONS$/,/^$/ {if (/^    [a-zA-Z]/) {gsub(/^    /, ""); print $1}}'))

        # Tool-level options
        options=(
            '--help:Show help for this tool'
            '--json-output:Output in JSON format'
            '--params-from-json:Load parameters from JSON file'
        )

        # Add completions without group labels
        _describe '' functions
        _describe '' options
        return 0
    elif [[ $CURRENT -gt 3 && $words[2] && $words[2] != -* && $words[3] && $words[3] != -* ]]; then
        # Third tier: parameters and function options
        local tool=$words[2]
        local function=$words[3]
        local -a params options

        # Get parameter names for the function
        params=($(mcp-cli $tool $function --help 2>/dev/null | awk '/^OPTIONS$/,/^$/ {if (/^    [a-zA-Z]/) {gsub(/^    /, ""); print $1 "="}}'))

        # Function-level options
        options=(
            '--help:Show detailed help for this function'
            '--json-output:Output in JSON format'
            '--params-from-json:Load parameters from JSON file'
        )

        # Add completions without group labels
        _describe '' params
        _describe '' options
        return 0
    fi
}

compdef _mcp_cli mcp-cli
"""

    # Try to install in user's zsh completion directory
    zsh_completion_dir = Path.home() / ".zsh" / "completions"
    if not zsh_completion_dir.exists():
        zsh_completion_dir.mkdir(parents=True, exist_ok=True)

    completion_file = zsh_completion_dir / "_mcp-cli"

    with open(completion_file, "w") as f:
        f.write(zsh_completion)

    click.echo(f"Zsh completion installed to: {completion_file}")
    click.echo("Add the following to your ~/.zshrc:")
    click.echo(f"fpath=({zsh_completion_dir} $fpath)")
    click.echo("autoload -U compinit && compinit")


def show_completion_install():
    """Show instructions for enabling completion."""
    click.echo("To enable shell completion:")
    click.echo("")
    click.echo("For Zsh:")
    click.echo('  eval "$(_MCP_CLI_COMPLETE=zsh_source mcp-cli)"')
    click.echo("")
    click.echo("For Bash:")
    click.echo('  eval "$(_MCP_CLI_COMPLETE=bash_source mcp-cli)"')
    click.echo("")
    click.echo("Add the appropriate line to your shell's configuration file.")
    click.echo(
        "Or run 'mcp-cli --install-completion' to install zsh completion permanently."
    )

```

`src/mcp_handley_lab/cli/config.py`:

```py
"""Configuration management for MCP CLI."""

import os
from pathlib import Path
from typing import Any

import click
import tomllib


def get_config_dir() -> Path:
    """Get the configuration directory for MCP CLI."""
    if config_home := os.getenv("XDG_CONFIG_HOME"):
        return Path(config_home) / "mcp"
    return Path.home() / ".config" / "mcp"


def get_config_file() -> Path:
    """Get the configuration file path."""
    return get_config_dir() / "config.toml"


def load_config() -> dict[str, Any]:
    """Load configuration from file."""
    config_file = get_config_file()
    with open(config_file, "rb") as f:
        return tomllib.load(f)


def create_default_config():
    """Create a default configuration file."""
    config_file = get_config_file()
    config_dir = config_file.parent

    # Create config directory if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)

    # Default configuration
    default_config = """# MCP CLI Configuration

[aliases]
# Tool aliases for common shortcuts
# notes = "knowledge-tool"
# code = "jq"

[defaults]
# Default models for LLM providers
# gemini_model = "gemini-2.5-pro"
# openai_model = "gpt-4o"
# claude_model = "claude-3-5-sonnet-20240620"

# Default output format: "human" or "json"
output_format = "human"

# Default file output behavior
# output_file = "-"  # stdout by default
"""

    if not config_file.exists():
        with open(config_file, "w") as f:
            f.write(default_config)
        click.echo(f"Created default configuration at: {config_file}")
    else:
        click.echo(f"Configuration file already exists at: {config_file}")

```

`src/mcp_handley_lab/cli/discovery.py`:

```py
"""Tool discovery for MCP CLI."""

import json
from typing import Any

import click

from .rpc_client import get_tool_client


def get_available_tools() -> dict[str, str]:
    """Get a list of available tool commands."""
    # Map of tool names to their script entry commands
    scripts = {
        "jq": "mcp-jq",
        "vim": "mcp-vim",
        "code2prompt": "mcp-code2prompt",
        "arxiv": "mcp-arxiv",
        "google-calendar": "mcp-google-calendar",
        "gemini": "mcp-gemini",
        "openai": "mcp-openai",
        "claude": "mcp-claude",
        "google-maps": "mcp-google-maps",
        "email": "mcp-email",
        "github": "mcp-github",
        "notes": "mcp-notes",
    }

    return scripts


def get_tool_info_from_cache() -> dict[str, dict[str, Any]]:
    """Load tool information from pre-generated cache."""
    try:
        from importlib.resources import files

        schema_file = files("mcp_handley_lab") / "tool_schemas.json"
        if schema_file.is_file():
            return json.loads(schema_file.read_text()).get("tools", {})
        return {}
    except Exception as e:
        click.echo(f"Warning: Failed to load tool cache: {e}", err=True)
        return {}


def get_tool_info(tool_name: str, command: str) -> dict[str, Any] | None:
    """Get detailed information about a tool - try cache first, fallback to RPC introspection."""

    # Try cached schema first (instant)
    cached_tools = get_tool_info_from_cache()
    if tool_name in cached_tools:
        tool_info = cached_tools[tool_name].copy()
        tool_info["command"] = command
        return tool_info

    # Fallback to RPC introspection
    try:
        client = get_tool_client(tool_name, command)
        tools_list = client.list_tools()

        if not tools_list:
            return None

        return {
            "name": tool_name,
            "command": command,
            "functions": {tool["name"]: tool for tool in tools_list},
        }

    except Exception as e:
        click.echo(f"Warning: Failed to get info for {tool_name}: {e}", err=True)
        return None

```

`src/mcp_handley_lab/cli/formatter.py`:

```py
"""LLM response formatter for better CLI display."""

from typing import Any


def format_llm_response(response: dict[str, Any], max_content_length: int = 200) -> str:
    """Format LLM response for clean CLI display.

    Args:
        response: LLM response dictionary
        max_content_length: Maximum characters to show from content

    Returns:
        Formatted string for display
    """
    if not isinstance(response, dict):
        return str(response)

    # Extract key information
    content = response.get("content", "")
    usage = response.get("usage", {})
    agent_name = response.get("agent_name", "")
    model = usage.get("model_used", "")

    # Format content preview
    if len(content) > max_content_length:
        content_preview = content[:max_content_length] + "..."
    else:
        content_preview = content

    # Clean up content for display (remove excessive newlines)
    content_preview = " ".join(content_preview.split())

    # Build formatted output
    output = []

    # Header with model and agent info
    header_parts = []
    if model:
        header_parts.append(f"Model: {model}")
    if agent_name:
        header_parts.append(f"Agent: {agent_name}")

    if header_parts:
        output.append("🤖 " + " | ".join(header_parts))

    # Usage stats
    if usage:
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cost = usage.get("cost", 0)

        usage_line = f"📊 Tokens: {input_tokens} in → {output_tokens} out"
        if cost > 0:
            usage_line += f" | Cost: ${cost:.4f}"
        output.append(usage_line)

    # Content preview
    if content_preview:
        output.append("💬 " + content_preview)

    # Additional metadata if available
    finish_reason = response.get("finish_reason")
    if finish_reason and finish_reason != "stop":
        output.append(f"⚠️  Finish reason: {finish_reason}")

    return "\n".join(output)


def format_usage_only(response: dict[str, Any]) -> str:
    """Extract and format only usage statistics.

    Args:
        response: LLM response dictionary

    Returns:
        Formatted usage string
    """
    if not isinstance(response, dict):
        return "No usage data"

    usage = response.get("usage", {})
    if not usage:
        return "No usage data"

    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cost = usage.get("cost", 0)
    model = usage.get("model_used", "unknown")

    parts = [
        f"Input: {input_tokens:,} tokens",
        f"Output: {output_tokens:,} tokens",
        f"Total: {input_tokens + output_tokens:,} tokens",
    ]

    if cost > 0:
        parts.append(f"Cost: ${cost:.4f}")

    return f"{model} | " + " | ".join(parts)


def extract_content_only(response: dict[str, Any]) -> str:
    """Extract only the content from LLM response.

    Args:
        response: LLM response dictionary

    Returns:
        Content string
    """
    if not isinstance(response, dict):
        return str(response)

    return response.get("content", "")

```

`src/mcp_handley_lab/cli/main.py`:

```py
"""Main CLI implementation using Click framework."""

import atexit
import json
import sys

import click

from .completion import install_completion_script, show_completion_install
from .config import create_default_config, get_config_file
from .discovery import get_available_tools, get_tool_info
from .rpc_client import cleanup_clients, get_tool_client


def _get_validated_tool_info(tool_name: str) -> tuple[str, dict]:
    """Gets tool command and info, or exits if not found."""
    available_tools = get_available_tools()
    if tool_name not in available_tools:
        click.echo(
            f"Error: Tool '{tool_name}' not found. Available: {', '.join(available_tools.keys())}",
            err=True,
        )
        sys.exit(1)

    command = available_tools[tool_name]
    tool_info = get_tool_info(tool_name, command)
    if not tool_info:
        click.echo(f"Error: Failed to introspect tool '{tool_name}'", err=True)
        sys.exit(1)
    return command, tool_info


@click.command(add_help_option=False)
@click.argument("tool_name", required=False)
@click.argument("function_name", required=False)
@click.argument("params", nargs=-1)
@click.option("--list-tools", is_flag=True, help="List all available tools")
@click.option("--help", is_flag=True, help="Show help message")
@click.option("--json-output", is_flag=True, help="Output in JSON format")
@click.option(
    "--params-from-json", type=click.File("r"), help="Load parameters from JSON file"
)
@click.option("--config", help="Show configuration file location", is_flag=True)
@click.option("--init-config", help="Create default configuration file", is_flag=True)
@click.option(
    "--install-completion", help="Install zsh completion script", is_flag=True
)
@click.option(
    "--show-completion", help="Show completion installation instructions", is_flag=True
)
@click.pass_context
def cli(
    ctx,
    tool_name,
    function_name,
    params,
    list_tools,
    help,
    json_output,
    params_from_json,
    config,
    init_config,
    install_completion,
    show_completion,
):
    """MCP CLI - Unified command-line interface for MCP tools.

    USAGE
        mcp-cli --list-tools                 # List available tools
        mcp-cli <tool> --help                # Show help for a tool
        mcp-cli <tool> <function> --help     # Show detailed function help
        mcp-cli <tool> <function> [args...]  # Execute a function

    EXAMPLES
        mcp-cli --list-tools
        mcp-cli arxiv --help
        mcp-cli arxiv search "machine learning"
        mcp-cli jq query '{"name":"value"}' filter='.name'
    """

    # Check for conflicts between global options and tool specification
    global_options_used = []
    if config:
        global_options_used.append("--config")
    if init_config:
        global_options_used.append("--init-config")
    if install_completion:
        global_options_used.append("--install-completion")
    if show_completion:
        global_options_used.append("--show-completion")
    if list_tools:
        global_options_used.append("--list-tools")

    if tool_name and global_options_used:
        click.echo(
            f"Error: Global options {', '.join(global_options_used)} cannot be used with tool '{tool_name}'",
            err=True,
        )
        click.echo(
            f"Use 'mcp-cli {' '.join(global_options_used)}' without specifying a tool",
            err=True,
        )
        ctx.exit(1)

    # Handle global configuration options (only if no tool specified)
    if config:
        click.echo(f"Configuration file: {get_config_file()}")
        ctx.exit()

    if init_config:
        create_default_config()
        ctx.exit()

    if install_completion:
        install_completion_script()
        ctx.exit()

    if show_completion:
        show_completion_install()
        ctx.exit()

    if list_tools:
        list_all_tools()
        ctx.exit()

    # Handle help flag
    if help:
        if tool_name and function_name:
            # Function-specific help: mcp-cli <tool> <function> --help
            show_function_help(tool_name, function_name)
        elif tool_name:
            # Tool-specific help: mcp-cli <tool> --help
            show_tool_help(tool_name)
        else:
            # Global help: mcp-cli --help
            show_global_help()
        ctx.exit()

    # If no tool provided, show help
    if not tool_name:
        click.echo(ctx.get_help())
        ctx.exit()

    # Require function name for execution
    if not function_name:
        click.echo(f"Usage: mcp-cli {tool_name} <function> [params...]", err=True)
        click.echo(
            f"Use 'mcp-cli {tool_name} --help' to see available functions.", err=True
        )
        ctx.exit(1)

    # Execute tool function
    run_tool_function(
        ctx, tool_name, function_name, params, json_output, params_from_json
    )


def show_global_help():
    """Show global help for the MCP CLI."""
    click.echo("NAME")
    click.echo("    mcp-cli - Unified command-line interface for MCP tools")
    click.echo()

    click.echo("USAGE")
    click.echo("    mcp-cli --list-tools                 # List available tools")
    click.echo("    mcp-cli <tool> --help                # Show help for a tool")
    click.echo("    mcp-cli <tool> <function> --help     # Show detailed function help")
    click.echo("    mcp-cli <tool> <function> [args...]  # Execute a function")
    click.echo()

    click.echo("EXAMPLES")
    click.echo("    mcp-cli --list-tools")
    click.echo("    mcp-cli arxiv --help")
    click.echo('    mcp-cli arxiv search "machine learning"')
    click.echo("    mcp-cli jq query '{\"name\":\"value\"}' filter='.name'")
    click.echo()

    click.echo("GLOBAL OPTIONS")
    click.echo("    --list-tools         List all available tools")
    click.echo("    --help               Show this help message")
    click.echo("    --config             Show configuration file location")
    click.echo("    --init-config        Create default configuration file")
    click.echo("    --install-completion Install zsh completion script")


def list_all_tools():
    """List all available tools."""
    # Just list tool names without introspection for speed
    available_tools = get_available_tools()

    click.echo("Available tools:")
    for tool_name in sorted(available_tools.keys()):
        click.echo(f"  {tool_name}")

    # Note: aliases would require config loading, skip for speed
    click.echo(f"\nTotal: {len(available_tools)} tools")
    click.echo("Use 'mcp-cli <tool> --help' to see available functions.")


def show_tool_help(tool_name):
    """Show comprehensive help for a specific tool."""
    command, tool_info = _get_validated_tool_info(tool_name)
    functions = tool_info.get("functions", {})

    # Show tool header
    click.echo("NAME")
    click.echo(f"    {tool_name}")
    click.echo()

    # Show tool usage
    click.echo("USAGE")
    click.echo(f"    mcp-cli {tool_name} <function> [OPTIONS]")
    click.echo(f"    mcp-cli {tool_name} --help")
    click.echo()

    # Show available functions
    if functions:
        click.echo("FUNCTIONS")
        for func_name, func_info in sorted(functions.items()):
            description = func_info.get("description", "No description")
            # Keep first sentence only for brevity
            if ". " in description:
                description = description.split(". ")[0] + "."
            click.echo(f"    {func_name:<15} {description}")
        click.echo()

        click.echo("EXAMPLES")
        # Show examples for first few functions with realistic parameters
        example_functions = list(functions.items())[:3]
        for func_name, func_info in example_functions:
            input_schema = func_info.get("inputSchema", {})
            required = input_schema.get("required", [])

            if required:
                # Show example with realistic value for first required parameter
                param_name = required[0]
                if "query" in param_name.lower():
                    example_value = '"machine learning"'
                elif "id" in param_name.lower():
                    example_value = '"2301.07041"'
                elif "data" in param_name.lower():
                    example_value = '\'{"name": "value"}\''
                else:
                    example_value = '"example"'
                click.echo(f"    mcp-cli {tool_name} {func_name} {example_value}")
            else:
                click.echo(f"    mcp-cli {tool_name} {func_name}")
        click.echo()

        click.echo(
            f"Use 'mcp-cli {tool_name} <function> --help' for detailed parameter information."
        )
    else:
        click.echo("No functions available for this tool.")


def show_function_help(tool_name, function_name):
    """Show detailed help for a specific function."""
    command, tool_info = _get_validated_tool_info(tool_name)
    functions = tool_info.get("functions", {})
    if function_name not in functions:
        available_functions = list(functions.keys())
        click.echo(
            f"Function '{function_name}' not found in {tool_name}. Available: {', '.join(available_functions)}",
            err=True,
        )
        sys.exit(1)

    func_info = functions[function_name]
    description = func_info.get("description", "No description available")
    input_schema = func_info.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    # Function header
    click.echo("NAME")
    click.echo(f"    {tool_name}.{function_name}")
    click.echo()

    # Usage
    click.echo("USAGE")
    if required:
        # Show required parameters as positional
        required_positional = " ".join([f"<{p}>" for p in required])
        usage_line = f"    mcp-cli {tool_name} {function_name} {required_positional}"

        # Add optional parameters indication
        optional_params = [p for p in properties if p not in required]
        if optional_params:
            usage_line += " [OPTIONS]"

        click.echo(usage_line)
    else:
        # No required parameters
        all_optional = list(properties)
        if all_optional:
            click.echo(f"    mcp-cli {tool_name} {function_name} [OPTIONS]")
        else:
            click.echo(f"    mcp-cli {tool_name} {function_name}")
    click.echo()

    # Description
    click.echo("DESCRIPTION")
    click.echo(f"    {description}")
    click.echo()

    # Parameters
    if properties:
        click.echo("OPTIONS")
        for param_name, param_info in properties.items():
            param_type = param_info.get("type", "string")
            param_desc = param_info.get("description", "")
            default = param_info.get("default")

            # Build parameter line with type and default
            if default is not None:
                if isinstance(default, str):
                    default_info = f"'{default}'"
                else:
                    default_info = str(default)
                type_info = f"{param_type} (default: {default_info})"
            else:
                type_info = param_type

            click.echo(f"    {param_name:<15} {type_info}")

            # Parameter description on same line or next line if it fits
            if param_desc:
                if len(param_desc) < 50:
                    # Short description - could fit on same line but keep consistent
                    click.echo(f"                    {param_desc}")
                else:
                    # Wrap longer descriptions
                    import textwrap

                    wrapped = textwrap.fill(
                        param_desc,
                        width=65,
                        initial_indent="                    ",
                        subsequent_indent="                    ",
                    )
                    click.echo(wrapped)
        click.echo()

    # Examples
    if required:
        click.echo("EXAMPLES")
        click.echo(f'    mcp-cli {tool_name} {function_name} "machine learning"')
        optional_params = [p for p in properties if p not in required]
        if optional_params:
            first_optional = optional_params[0]
            click.echo(
                f'    mcp-cli {tool_name} {function_name} "deep learning" {first_optional}=20'
            )
        click.echo()


# Register cleanup on exit
atexit.register(cleanup_clients)


def run_tool_function(
    ctx, tool_name, function_name, params, json_output, params_from_json
):
    """Run a tool function."""
    command, tool_info = _get_validated_tool_info(tool_name)

    functions = tool_info.get("functions", {})
    if function_name not in functions:
        available_functions = list(functions.keys())
        click.echo(
            f"Function '{function_name}' not found in {tool_name}. Available: {', '.join(available_functions)}",
            err=True,
        )
        ctx.exit(1)

    # Parse parameters
    kwargs = {}
    if params_from_json:
        kwargs = json.load(params_from_json)

    # Get function schema for parameter mapping
    function_schema = functions[function_name]
    input_schema = function_schema.get("inputSchema", {})
    required_params = input_schema.get("required", [])
    all_params = list(input_schema.get("properties", {}).keys())

    # Simplified parameter parsing - keep all values as strings
    positional_args = [p for p in params if "=" not in p]
    for param in params:
        if "=" in param:
            key, value = param.split("=", 1)
            kwargs[key] = value  # Keep as string, don't convert to dict

    # Map positional args to parameters (required first, then others)
    param_order = required_params + [p for p in all_params if p not in required_params]
    for i, param_name in enumerate(param_order):
        if i < len(positional_args) and param_name not in kwargs:
            kwargs[param_name] = positional_args[i]

    # Execute the tool
    client = get_tool_client(tool_name, command)
    response = client.call_tool(function_name, kwargs)

    if response is None:
        click.echo(f"Failed to execute {function_name}", err=True)
        ctx.exit(1)

    # Handle response
    if response.get("jsonrpc") == "2.0":
        if "error" in response:
            error = response["error"]
            click.echo(f"Error: {error.get('message', 'Unknown error')}", err=True)
            ctx.exit(1)
        else:
            result = response.get("result", {})
            if json_output:
                click.echo(json.dumps(result, indent=2))
            else:
                # Simplified output handling
                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    if isinstance(content, str):
                        click.echo(content)
                    else:
                        click.echo(json.dumps(result, indent=2))
                else:
                    click.echo(
                        json.dumps(result, indent=2)
                        if isinstance(result, dict | list)
                        else str(result)
                    )
    else:
        click.echo(str(response))


if __name__ == "__main__":
    cli()

```

`src/mcp_handley_lab/cli/rpc_client.py`:

```py
"""JSON-RPC client for communicating with MCP tools."""

import json
import subprocess
import time
from typing import Any

import click


class MCPToolClient:
    """Client for communicating with MCP tools via JSON-RPC."""

    def __init__(self, tool_name: str, command: str):
        self.tool_name = tool_name
        self.command = command
        self.process: subprocess.Popen | None = None
        self._initialized = False

    def start_tool_server(self) -> bool:
        """Start the MCP tool server process."""
        try:
            # Start the tool server process using the command
            self.process = subprocess.Popen(
                [self.command],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,
            )

            # Give the process a moment to start
            time.sleep(0.1)

            # Check if process is still running
            if self.process.poll() is not None:
                stderr = self.process.stderr.read()
                click.echo(
                    f"Process {self.tool_name} exited early. Stderr: {stderr}", err=True
                )
                return False

            # Initialize the server
            if not self._initialize_server():
                self.cleanup()
                return False

            self._initialized = True
            return True

        except Exception as e:
            click.echo(f"Failed to start {self.tool_name} server: {e}", err=True)
            return False

    def _initialize_server(self) -> bool:
        """Send initialization messages to the MCP server."""
        try:
            # Send initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "mcp-cli", "version": "1.0.0"},
                },
            }

            self.process.stdin.write(json.dumps(init_request) + "\n")
            self.process.stdin.flush()

            # Read response with timeout
            response_line = self.process.stdout.readline()
            if not response_line:
                stderr = (
                    self.process.stderr.read() if self.process.stderr else "No stderr"
                )
                click.echo(
                    f"No response from {self.tool_name}. Stderr: {stderr}", err=True
                )
                return False

            try:
                response = json.loads(response_line.strip())
            except json.JSONDecodeError as e:
                click.echo(
                    f"Invalid JSON response from {self.tool_name}: {response_line}. Error: {e}",
                    err=True,
                )
                return False

            if "error" in response:
                click.echo(f"Initialization error: {response['error']}", err=True)
                return False

            # Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }

            self.process.stdin.write(json.dumps(initialized_notification) + "\n")
            self.process.stdin.flush()

            return True

        except Exception as e:
            click.echo(f"Failed to initialize {self.tool_name}: {e}", err=True)
            stderr = (
                self.process.stderr.read()
                if self.process and self.process.stderr
                else "No stderr"
            )
            if stderr:
                click.echo(f"Stderr: {stderr}", err=True)
            return False

    def _ensure_initialized(self) -> bool:
        """Starts the tool server if not already running. Returns success."""
        if not self._initialized:
            return self.start_tool_server()
        return True

    def list_tools(self) -> list[dict[str, Any]] | None:
        """Get list of available tools from the server."""
        if not self._ensure_initialized():
            return None

        try:
            request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}

            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()

            response_line = self.process.stdout.readline()
            if not response_line:
                return None

            response = json.loads(response_line.strip())
            if "error" in response:
                click.echo(f"Error listing tools: {response['error']}", err=True)
                return None

            return response.get("result", {}).get("tools", [])

        except Exception as e:
            click.echo(f"Failed to list tools from {self.tool_name}: {e}", err=True)
            return None

    def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Call a specific tool function."""
        if not self._ensure_initialized():
            return None

        try:
            request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }

            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()

            response_line = self.process.stdout.readline()
            if not response_line:
                return None

            response = json.loads(response_line.strip())
            return response

        except Exception as e:
            click.echo(f"Failed to call {tool_name}: {e}", err=True)
            return None

    def cleanup(self):
        """Clean up the server process."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            except Exception:
                pass
            finally:
                self.process = None
                self._initialized = False


# Global clients dictionary
_CLIENTS: dict[str, MCPToolClient] = {}


def get_tool_client(tool_name: str, command: str) -> MCPToolClient:
    """Get or create a client for a tool."""
    if tool_name not in _CLIENTS:
        _CLIENTS[tool_name] = MCPToolClient(tool_name, command)
    return _CLIENTS[tool_name]


def cleanup_clients():
    """Clean up all clients."""
    for client in _CLIENTS.values():
        client.cleanup()
    _CLIENTS.clear()

```

`src/mcp_handley_lab/code2prompt/tool.py`:

```py
"""Code2Prompt tool for codebase flattening and conversion via MCP."""

from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.shared.models import ServerInfo


class GenerationResult(BaseModel):
    """Result of code2prompt generation."""

    message: str = Field(
        ...,
        description="A confirmation message indicating the result of the generation.",
    )
    output_file_path: str = Field(
        ..., description="The absolute path to the generated prompt summary file."
    )
    file_size_bytes: int = Field(
        ..., description="The size of the generated file in bytes."
    )


mcp = FastMCP("Code2Prompt Tool")


def _run_code2prompt(args: list[str]) -> str:
    """Runs a code2prompt command."""
    cmd = ["code2prompt"] + args
    stdout, stderr = run_command(cmd)
    return stdout.decode("utf-8").strip()


@mcp.tool(
    description="Generates a structured, token-counted summary of a codebase. Supports include/exclude, git diffs, and formatting options."
)
def generate_prompt(
    path: str = Field(..., description="The source directory or file path to analyze."),
    output_file: str = Field(
        ..., description="The path where the generated summary file will be saved."
    ),
    include: list[str] = Field(
        default_factory=list,
        description="A list of glob patterns to explicitly include files (e.g., '*.py', 'src/**/*').",
    ),
    exclude: list[str] = Field(
        default_factory=list,
        description="A list of glob patterns to exclude files (e.g., '*_test.py', 'dist/*').",
    ),
    output_format: str = Field(
        "markdown",
        description="The output format for the summary. Valid options include 'markdown', 'json'.",
    ),
    line_numbers: bool = Field(
        False, description="Include line numbers in code blocks."
    ),
    full_directory_tree: bool = Field(
        False, description="Display full directory tree including empty directories."
    ),
    follow_symlinks: bool = Field(
        False, description="Follow symbolic links when scanning."
    ),
    hidden: bool = Field(False, description="Include hidden files and directories."),
    no_codeblock: bool = Field(
        False, description="Omit markdown code block fences around file content."
    ),
    absolute_paths: bool = Field(
        False, description="Use absolute paths instead of relative paths."
    ),
    encoding: str = Field(
        "cl100k",
        description="The name of the tiktoken encoding to use for token counting (e.g., 'cl100k', 'p50k_base').",
    ),
    tokens: str = Field(
        "format",
        description="Determines how token counts are displayed. Valid options are 'format', 'only', 'none'.",
    ),
    sort: str = Field(
        "name_asc",
        description="The sorting order for files. Options: 'name_asc', 'name_desc', 'tokens_asc', 'tokens_desc'.",
    ),
    include_priority: bool = Field(
        False, description="'include' patterns take priority over .gitignore rules."
    ),
    template: str = Field(
        "", description="Path to a custom Jinja2 template file to format the output."
    ),
    include_git_diff: bool = Field(
        False, description="Generate content from git diff instead of full directory."
    ),
    git_diff_branch1: str = Field(
        "",
        description="The first branch or commit for git diff comparison. Requires git_diff_branch2.",
    ),
    git_diff_branch2: str = Field(
        "",
        description="The second branch or commit for git diff comparison. Requires git_diff_branch1.",
    ),
    git_log_branch1: str = Field(
        "",
        description="The first branch or commit for git log comparison. Requires git_log_branch2.",
    ),
    git_log_branch2: str = Field(
        "",
        description="The second branch or commit for git log comparison. Requires git_log_branch1.",
    ),
    no_ignore: bool = Field(
        False, description="Disable .gitignore and .c2pignore file processing."
    ),
) -> GenerationResult:
    """Generate a structured prompt from codebase."""
    arg_definitions = [
        {"name": "--output-file", "value": output_file, "type": "value"},
        {"name": "--output-format", "value": output_format, "type": "value"},
        {"name": "--encoding", "value": encoding, "type": "value"},
        {"name": "--tokens", "value": tokens, "type": "value"},
        {"name": "--sort", "value": sort, "type": "value"},
        {"name": "--template", "value": template, "type": "optional_value"},
        {"name": "--include-priority", "condition": include_priority, "type": "flag"},
        {"name": "--no-ignore", "condition": no_ignore, "type": "flag"},
        {"name": "--line-numbers", "condition": line_numbers, "type": "flag"},
        {
            "name": "--full-directory-tree",
            "condition": full_directory_tree,
            "type": "flag",
        },
        {"name": "--follow-symlinks", "condition": follow_symlinks, "type": "flag"},
        {"name": "--hidden", "condition": hidden, "type": "flag"},
        {"name": "--no-codeblock", "condition": no_codeblock, "type": "flag"},
        {"name": "--absolute-paths", "condition": absolute_paths, "type": "flag"},
        {"name": "--diff", "condition": include_git_diff, "type": "flag"},
        {"name": "--include", "values": include or [], "type": "multi_value"},
        {"name": "--exclude", "values": exclude or [], "type": "multi_value"},
    ]

    args = [path]
    for arg_def in arg_definitions:
        if (
            arg_def["type"] == "value"
            and arg_def.get("value")
            or arg_def["type"] == "optional_value"
            and arg_def.get("value")
        ):
            args.extend([arg_def["name"], str(arg_def["value"])])
        elif arg_def["type"] == "flag" and arg_def.get("condition"):
            args.append(arg_def["name"])
        elif arg_def["type"] == "multi_value":
            for val in arg_def.get("values", []):
                args.extend([arg_def["name"], val])

    if git_diff_branch1 and git_diff_branch2:
        args.extend(["--git-diff-branch", git_diff_branch1, git_diff_branch2])

    if git_log_branch1 and git_log_branch2:
        args.extend(["--git-log-branch", git_log_branch1, git_log_branch2])

    _run_code2prompt(args)

    output_path = Path(output_file)
    file_size = output_path.stat().st_size

    return GenerationResult(
        message="Code2prompt Generation Successful",
        output_file_path=output_file,
        file_size_bytes=file_size,
    )


@mcp.tool(
    description="Checks the status of the Code2Prompt server and its CLI dependency. Returns version info and available functions."
)
def server_info() -> ServerInfo:
    """Get server status and code2prompt version."""
    version = _run_code2prompt(["--version"])

    return ServerInfo(
        name="Code2Prompt Tool",
        version=version.strip(),
        status="active",
        capabilities=["generate_prompt", "server_info"],
        dependencies={"code2prompt": version.strip()},
    )

```

`src/mcp_handley_lab/common/config.py`:

```py
"""Configuration management for MCP Framework."""

from pathlib import Path

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global settings for MCP Framework."""

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # API Keys
    gemini_api_key: str = Field(default="YOUR_API_KEY_HERE", description="API key for Google Gemini services.")
    openai_api_key: str = Field(default="YOUR_API_KEY_HERE", description="API key for OpenAI services.")
    anthropic_api_key: str = Field(default="YOUR_API_KEY_HERE", description="API key for Anthropic Claude services.")
    xai_api_key: str = Field(default="YOUR_API_KEY_HERE", description="API key for xAI Grok services.")
    google_maps_api_key: str = Field(default="YOUR_API_KEY_HERE", description="API key for Google Maps services.")

    # Google Calendar
    google_credentials_file: str = Field(default="~/.google_calendar_credentials.json", description="Path to Google Calendar OAuth2 credentials file.")
    google_token_file: str = Field(default="~/.google_calendar_token.json", description="Path to Google Calendar OAuth2 token cache file.")

    @property
    def google_credentials_path(self) -> Path:
        """Get resolved path for Google credentials."""
        return Path(self.google_credentials_file).expanduser()

    @property
    def google_token_path(self) -> Path:
        """Get resolved path for Google token."""
        return Path(self.google_token_file).expanduser()


settings = Settings()

```

`src/mcp_handley_lab/common/pricing.py`:

```py
"""Cost tracking and pricing utilities for LLM usage."""

from pathlib import Path
from typing import Any

import yaml


class PricingCalculator:
    """Calculates costs for various LLM models using YAML-based pricing configurations."""

    @classmethod
    def _load_pricing_config(cls, provider: str) -> dict[str, Any]:
        """Load pricing configuration from unified model YAML file."""
        current_dir = Path(__file__).parent
        models_file = current_dir.parent / "llm" / provider / "models.yaml"

        with open(models_file, encoding="utf-8") as f:
            return yaml.safe_load(f)

    @classmethod
    def calculate_cost(
        cls,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        provider: str = "gemini",
        input_modality: str = "text",
        output_quality: str = "medium",
        cached_input_tokens: int = 0,
        images_generated: int = 0,
        seconds_generated: int = 0,
    ) -> float:
        """Calculate cost using YAML-based pricing configurations."""
        config = cls._load_pricing_config(provider)

        models = config.get("models", {})
        if model not in models:
            raise ValueError(
                f"Model '{model}' not found in pricing config for provider '{provider}'"
            )

        model_config = models[model]
        total_cost = 0.0

        pricing_type = model_config.get("pricing_type")

        if pricing_type == "per_image":
            price_per_image = model_config.get("price_per_image", 0.0)
            return images_generated * price_per_image

        elif pricing_type == "per_second":
            price_per_second = model_config.get("price_per_second", 0.0)
            return seconds_generated * price_per_second

        elif "input_tiers" in model_config:
            for tier in model_config["input_tiers"]:
                threshold = (
                    float("inf") if tier["threshold"] == ".inf" else tier["threshold"]
                )
                if input_tokens <= threshold:
                    total_cost += (input_tokens / 1_000_000) * tier["price"]
                    break

            for tier in model_config.get("output_tiers", []):
                threshold = (
                    float("inf") if tier["threshold"] == ".inf" else tier["threshold"]
                )
                if output_tokens <= threshold:
                    total_cost += (output_tokens / 1_000_000) * tier["price"]
                    break

        elif "input_by_modality" in model_config:
            modality_price = model_config["input_by_modality"].get(input_modality, 0.30)
            total_cost += (input_tokens / 1_000_000) * modality_price
            total_cost += (output_tokens / 1_000_000) * model_config.get(
                "output_per_1m", 0.0
            )

        elif pricing_type == "complex":
            if model == "gpt-image-1":
                if input_modality == "text":
                    total_cost += (input_tokens / 1_000_000) * model_config[
                        "text_input_per_1m"
                    ]
                    total_cost += (cached_input_tokens / 1_000_000) * model_config[
                        "cached_text_input_per_1m"
                    ]
                elif input_modality == "image":
                    total_cost += (input_tokens / 1_000_000) * model_config[
                        "image_input_per_1m"
                    ]
                    total_cost += (cached_input_tokens / 1_000_000) * model_config[
                        "cached_image_input_per_1m"
                    ]

                if images_generated > 0:
                    image_pricing = model_config["image_output_pricing"]
                    per_image_cost = image_pricing.get(output_quality, 0.04)
                    total_cost += images_generated * per_image_cost

        else:
            input_price = model_config.get("input_per_1m", 0.0)
            output_price = model_config.get("output_per_1m", 0.0)

            total_cost += (input_tokens / 1_000_000) * input_price
            total_cost += (output_tokens / 1_000_000) * output_price

            if cached_input_tokens > 0 and "cached_input_per_1m" in model_config:
                cached_price = model_config["cached_input_per_1m"]
                total_cost += (cached_input_tokens / 1_000_000) * cached_price

        return total_cost

    @classmethod
    def format_cost(cls, cost: float) -> str:
        """Format cost for display."""
        if cost == 0:
            return "$0.00"
        elif cost < 0.01:
            return f"${cost:.4f}"
        else:
            return f"${cost:.2f}"

    @classmethod
    def format_usage(cls, input_tokens: int, output_tokens: int, cost: float) -> str:
        """Format usage summary for display."""
        return f"{input_tokens:,} tokens (↑{input_tokens:,}/↓{output_tokens:,}) ≈{cls.format_cost(cost)}"


# Global function for backward compatibility
def calculate_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    provider: str = "gemini",
    **kwargs,
) -> float:
    """Global function that delegates to PricingCalculator.calculate_cost."""
    return PricingCalculator.calculate_cost(
        model, input_tokens, output_tokens, provider, **kwargs
    )


def format_usage(input_tokens: int, output_tokens: int, cost: float) -> str:
    """Global function that delegates to PricingCalculator.format_usage."""
    return PricingCalculator.format_usage(input_tokens, output_tokens, cost)

```

`src/mcp_handley_lab/common/process.py`:

```py
"""Shared utilities for command execution."""

import subprocess


def run_command(
    cmd: list[str], input_data: bytes | None = None, timeout: int = 30
) -> tuple[bytes, bytes]:
    """Runs a command synchronously, returning (stdout, stderr).

    Args:
        cmd: Command and arguments as a list
        input_data: Optional stdin data to send to the process
        timeout: Timeout in seconds (default: 30)

    Returns:
        Tuple of (stdout, stderr) as bytes

    Raises:
        RuntimeError: If command fails, is not found, or times out
    """
    try:
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Command failed with exit code {result.returncode}: {result.stderr.decode()}"
            )
        return result.stdout, result.stderr
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Command timed out after {timeout} seconds") from e
    except FileNotFoundError as e:
        raise RuntimeError(f"Command not found: {cmd[0]}") from e

```

`src/mcp_handley_lab/common/terminal.py`:

```py
"""Terminal utilities for launching interactive applications."""

import contextlib
import os
import re
import subprocess
import time
import uuid


def launch_interactive(
    command: str,
    window_title: str | None = None,
    prefer_tmux: bool = True,
    wait: bool = False,
) -> str:
    """Launch an interactive command in a new terminal window.

    Automatically detects environment and chooses appropriate method:
    - If in tmux session: creates new tmux window
    - Otherwise: launches xterm window

    Args:
        command: The command to execute
        window_title: Optional title for the window
        prefer_tmux: Whether to prefer tmux over xterm when both available
        wait: Whether to wait for the command to complete before returning

    Returns:
        Status message describing what was launched

    Raises:
        RuntimeError: If neither tmux nor xterm is available
    """
    in_tmux = bool(os.environ.get("TMUX"))

    if in_tmux and prefer_tmux:
        if wait:
            unique_id = str(uuid.uuid4())[:8]
            window_name = f"task-{unique_id}"
            done_name = f"done-{unique_id}"

            sync_command = f"{command}; tmux rename-window '{done_name}'"
            tmux_cmd = ["tmux", "new-window", "-n", window_name, sync_command]

            try:
                current_window = subprocess.check_output(
                    ["tmux", "display-message", "-p", "#{window_index}"], text=True
                ).strip()

                subprocess.run(tmux_cmd, check=True)
                print(f"Waiting for user input from {window_title or 'tmux window'}...")

                while True:
                    output = subprocess.check_output(
                        ["tmux", "list-windows"], text=True
                    )
                    if re.search(rf"{done_name}", output):
                        break
                    if not re.search(rf"{window_name}", output):
                        break
                    time.sleep(0.1)

                if current_window:
                    with contextlib.suppress(subprocess.CalledProcessError):
                        subprocess.run(
                            ["tmux", "select-window", "-t", current_window], check=True
                        )

                return f"Completed in tmux window: {command}"
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to run command in tmux: {e}") from e
        else:
            tmux_cmd = ["tmux", "new-window"]

            if window_title:
                tmux_cmd.extend(["-n", window_title])

            tmux_cmd.append(command)

            try:
                subprocess.run(tmux_cmd, check=True)
                return f"Launched in new tmux window: {command}"
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to create tmux window: {e}") from e

    else:
        if wait:
            xterm_cmd = ["xterm"]

            if window_title:
                xterm_cmd.extend(["-title", window_title])

            xterm_cmd.extend(["-e", command])

            try:
                print(
                    f"Waiting for user input from {window_title or 'xterm window'}..."
                )
                subprocess.run(xterm_cmd, check=True)
                return f"Completed in xterm: {command}"
            except FileNotFoundError as e:
                raise RuntimeError("xterm not available for interactive launch") from e
        else:
            xterm_cmd = ["xterm"]

            if window_title:
                xterm_cmd.extend(["-title", window_title])

            xterm_cmd.extend(["-e", command])

            try:
                subprocess.Popen(xterm_cmd)
                return f"Launched in xterm: {command}"
            except FileNotFoundError as e:
                raise RuntimeError(
                    "Neither tmux nor xterm available for interactive launch"
                ) from e


def check_interactive_support() -> dict:
    """Check what interactive terminal options are available.

    Returns:
        Dict with availability status of tmux and xterm
    """
    result = {
        "tmux_session": bool(os.environ.get("TMUX")),
        "tmux_available": False,
        "tmux_error": None,
        "xterm_available": False,
        "xterm_error": None,
    }

    try:
        subprocess.run(["tmux", "list-sessions"], capture_output=True, check=True)
        result["tmux_available"] = True
    except FileNotFoundError:
        pass
    except subprocess.CalledProcessError as e:
        result["tmux_error"] = str(e)

    try:
        subprocess.run(["which", "xterm"], capture_output=True, check=True)
        result["xterm_available"] = True
    except FileNotFoundError:
        pass
    except subprocess.CalledProcessError as e:
        result["xterm_error"] = str(e)

    return result

```

`src/mcp_handley_lab/email/__init__.py`:

```py
"""Email client MCP tool for msmtp, offlineimap, and notmuch integration."""

__version__ = "0.1.0"

```

`src/mcp_handley_lab/email/common.py`:

```py
"""Shared MCP instance for unified email tool."""

from mcp.server.fastmcp import FastMCP

# Single, shared MCP instance for the entire email tool.
# All provider modules will import and use this instance.
mcp = FastMCP("Email")

```

`src/mcp_handley_lab/email/msmtp/__init__.py`:

```py
"""MSMTP email sending provider."""

```

`src/mcp_handley_lab/email/msmtp/tool.py`:

```py
"""MSMTP email sending provider."""

from pathlib import Path

from pydantic import BaseModel, Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp


class SendResult(BaseModel):
    """Result of sending an email."""

    status: str = Field(default="success", description="The status of the send operation, typically 'success'.")
    recipient: str = Field(..., description="The primary recipient's email address (the 'To' field).")
    account_used: str = Field(default="", description="The msmtp account used for sending, if specified.")
    cc_recipients: list[str] = Field(default_factory=list, description="A list of email addresses in the 'Cc' field.")
    bcc_recipients: list[str] = Field(default_factory=list, description="A list of email addresses in the 'Bcc' field.")


def _parse_msmtprc(config_file: str = "") -> list[str]:
    """Parse msmtp config to extract account names."""
    msmtprc_path = Path(config_file) if config_file else Path.home() / ".msmtprc"
    if not msmtprc_path.exists():
        raise FileNotFoundError(f"msmtp configuration not found at {msmtprc_path}")

    accounts = []
    with open(msmtprc_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("account ") and not line.startswith("account default"):
                account_name = line.split()[1]
                accounts.append(account_name)

    return accounts


@mcp.tool(
    description="Send email using msmtp with configured accounts from ~/.msmtprc. Non-interactive automated sending with support for CC/BCC recipients."
)
def send(
    to: str = Field(
        ..., description="The primary recipient's email address."
    ),
    subject: str = Field(..., description="The subject line of the email."),
    body: str = Field(..., description="The main content (body) of the email."),
    account: str = Field(
        default="",
        description="The msmtp account to send from. If empty, the default account is used. Use 'list_accounts' to see options.",
    ),
    cc: str = Field(
        default="",
        description="Comma-separated list of email addresses for CC recipients.",
    ),
    bcc: str = Field(
        default="",
        description="Comma-separated list of email addresses for BCC recipients.",
    ),
) -> SendResult:
    """Send an email using msmtp with existing ~/.msmtprc configuration."""
    email_content = f"To: {to}\n"
    email_content += f"Subject: {subject}\n"

    if cc:
        email_content += f"Cc: {cc}\n"
    if bcc:
        email_content += f"Bcc: {bcc}\n"

    email_content += "\n"
    email_content += body

    cmd = ["msmtp"]
    if account:
        cmd.extend(["-a", account])

    recipients = [to]
    if cc:
        recipients.extend([addr.strip() for addr in cc.split(",")])
    if bcc:
        recipients.extend([addr.strip() for addr in bcc.split(",")])

    cmd.extend(recipients)

    input_bytes = email_content.encode()
    stdout, stderr = run_command(cmd, input_data=input_bytes)

    cc_list = [addr.strip() for addr in cc.split(",")] if cc else []
    bcc_list = [addr.strip() for addr in bcc.split(",")] if bcc else []

    return SendResult(
        recipient=to,
        account_used=account,
        cc_recipients=cc_list,
        bcc_recipients=bcc_list,
    )


@mcp.tool(
    description="List available msmtp accounts from ~/.msmtprc configuration. Use to discover valid account names for the send tool."
)
def list_accounts(
    config_file: str = Field(
        default="",
        description="Optional path to the msmtp configuration file. Defaults to `~/.msmtprc`.",
    )
) -> list[str]:
    """List available msmtp accounts by parsing msmtp config."""
    accounts = _parse_msmtprc(config_file)

    return accounts

```

`src/mcp_handley_lab/email/mutt/__init__.py`:

```py
"""Mutt email tool for MCP."""

```

`src/mcp_handley_lab/email/mutt/tool.py`:

```py
"""Mutt tool for interactive email composition via MCP."""

import os
import shlex
import tempfile

from pydantic import Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.common.terminal import launch_interactive
from mcp_handley_lab.email.common import mcp
from mcp_handley_lab.shared.models import OperationResult, ServerInfo


def _execute_mutt_command(cmd: list[str], input_text: str = None) -> str:
    """Execute mutt command and return output."""
    input_bytes = input_text.encode() if input_text else None
    stdout, stderr = run_command(cmd, input_data=input_bytes)
    return stdout.decode().strip()


def _prepare_body_with_signature(initial_body: str = "") -> str:
    """Prepare email body with signature if configured."""
    body_content = initial_body or "Automated email"

    sig_result = _execute_mutt_command(["mutt", "-Q", "signature"])
    sig_path = sig_result.split("=", 1)[1].strip().strip('"')
    sig_path = os.path.expanduser(sig_path) if sig_path.startswith("~") else sig_path

    with open(sig_path) as f:
        signature = f.read().strip()

    return body_content + f"\n\n{signature}" if signature else body_content


def _build_mutt_command(
    to: str = None,
    subject: str = "",
    cc: str = None,
    bcc: str = None,
    attachments: list[str] = None,
    auto_send: bool = False,
    reply_all: bool = False,
    folder: str = None,
    temp_file_path: str = None,
    in_reply_to: str = None,
    references: str = None,
) -> list[str]:
    """Build mutt command with proper arguments."""
    mutt_cmd = ["mutt"]

    if auto_send:
        mutt_cmd.extend(["-e", "set postpone=no"])

    if reply_all:
        mutt_cmd.extend(["-e", "set reply_to_all=yes"])

    if subject:
        mutt_cmd.extend(["-s", subject])

    if cc:
        mutt_cmd.extend(["-c", cc])

    if bcc:
        mutt_cmd.extend(["-b", bcc])

    if temp_file_path:
        mutt_cmd.extend(["-H", temp_file_path])

    if folder:
        mutt_cmd.extend(["-f", folder])

    if attachments:
        mutt_cmd.append("-a")
        mutt_cmd.extend(attachments)
        mutt_cmd.append("--")

    if in_reply_to:
        mutt_cmd.extend(["-e", f"my_hdr In-Reply-To: {in_reply_to}"])

    if references:
        mutt_cmd.extend(["-e", f"my_hdr References: {references}"])

    if to:
        mutt_cmd.append(to)

    return mutt_cmd


def _execute_mutt_interactive_or_auto(
    mutt_cmd: list[str],
    auto_send: bool = False,
    body_content: str = "",
    window_title: str = "Mutt",
) -> None:
    """Execute mutt command either interactively or automatically."""
    if auto_send:
        _execute_mutt_command(mutt_cmd, input_text=body_content)
    else:
        command_str = shlex.join(mutt_cmd)
        launch_interactive(command_str, window_title=window_title, wait=True)


@mcp.tool(
    description="Opens Mutt to compose an email, using your full configuration (signatures, editor). Supports attachments, pre-filled body, and an `auto_send` option that bypasses interactive review."
)
def compose(
    to: str = Field(
        ...,
        description="The primary recipient's email address (e.g., 'user@example.com').",
    ),
    subject: str = Field(default="", description="The subject line of the email."),
    cc: str = Field(
        default=None, description="Email address for the 'Cc' (carbon copy) field."
    ),
    bcc: str = Field(
        default=None,
        description="Email address for the 'Bcc' (blind carbon copy) field.",
    ),
    initial_body: str = Field(
        default="", description="Text to pre-populate in the email body."
    ),
    attachments: list[str] = Field(
        default=None, description="A list of local file paths to attach to the email."
    ),
    auto_send: bool = Field(
        default=False,
        description="If True, sends the email automatically without opening the interactive Mutt editor. A signature will be appended if configured. WARNING: Only use with explicit user permission as this bypasses review.",
    ),
    in_reply_to: str = Field(
        default=None,
        description="The Message-ID of the email being replied to, for proper threading. Used by 'reply' tool.",
    ),
    references: str = Field(
        default=None,
        description="A space-separated list of Message-IDs for threading context. Used by 'reply' tool.",
    ),
) -> OperationResult:
    """Compose an email using mutt's interactive interface."""

    if initial_body:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_f:
            # Create RFC822 email draft with headers
            temp_f.write(f"To: {to}\n")
            if subject:
                temp_f.write(f"Subject: {subject}\n")
            if cc:
                temp_f.write(f"Cc: {cc}\n")
            if bcc:
                temp_f.write(f"Bcc: {bcc}\n")
            if in_reply_to:
                temp_f.write(f"In-Reply-To: {in_reply_to}\n")
            if references:
                temp_f.write(f"References: {references}\n")
            temp_f.write("\n")  # Empty line separates headers from body
            temp_f.write(initial_body)
            if not initial_body.endswith("\n"):
                temp_f.write("\n")  # Ensure proper line ending
            temp_file_path = temp_f.name

        mutt_cmd = _build_mutt_command(
            to=None,  # Already in draft file
            subject=None,  # Already in draft file
            cc=None,  # Already in draft file
            bcc=None,  # Already in draft file
            attachments=attachments,
            auto_send=auto_send,
            temp_file_path=temp_file_path,
            in_reply_to=None,  # Already in draft file
            references=None,  # Already in draft file
        )

        body_content = _prepare_body_with_signature(initial_body) if auto_send else ""
        window_title = f"Mutt: {subject or 'New Email'}"

        _execute_mutt_interactive_or_auto(
            mutt_cmd, auto_send, body_content, window_title
        )

        # Only delete temp file if auto_send (mutt finished using it)
        if auto_send:
            os.unlink(temp_file_path)
    else:
        mutt_cmd = _build_mutt_command(
            to=to,
            subject=subject,
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            auto_send=auto_send,
            in_reply_to=in_reply_to,
            references=references,
        )

        body_content = _prepare_body_with_signature() if auto_send else ""
        window_title = f"Mutt: {subject or 'New Email'}"

        _execute_mutt_interactive_or_auto(
            mutt_cmd, auto_send, body_content, window_title
        )

    attachment_info = f" with {len(attachments)} attachment(s)" if attachments else ""
    action = "sent automatically" if auto_send else "composition completed"

    return OperationResult(
        status="success",
        message=f"Email {action}: {to}{attachment_info}",
    )


@mcp.tool(
    description="""Opens Mutt in interactive terminal to reply to specific email by message ID. Supports reply-all mode and initial body text. Headers auto-populated from original message."""
)
def reply(
    message_id: str = Field(
        ..., description="The notmuch message ID of the email to reply to."
    ),
    reply_all: bool = Field(
        default=False,
        description="If True, reply to all recipients (To and Cc) of the original message.",
    ),
    initial_body: str = Field(
        default="",
        description="Text to add to the top of the reply, above the quoted original message.",
    ),
    auto_send: bool = Field(
        default=False,
        description="If True, sends the reply automatically without opening the interactive Mutt editor. WARNING: Only use with explicit user permission as this bypasses review.",
    ),
) -> OperationResult:
    """Reply to an email using compose with extracted reply data."""

    # Import notmuch show to get original message data
    from mcp_handley_lab.email.notmuch.tool import _get_message_from_raw_source, show

    # Get original message data
    result = show(f"id:{message_id}")
    original_msg = result[0]
    raw_msg = _get_message_from_raw_source(message_id)

    # Extract reply data
    reply_to = original_msg.from_address
    reply_cc = original_msg.to_address if reply_all else None

    # Build subject with Re: prefix
    original_subject = original_msg.subject
    reply_subject = (
        f"Re: {original_subject}"
        if not original_subject.startswith("Re: ")
        else original_subject
    )

    # Build threading headers
    in_reply_to = raw_msg.get("Message-ID")
    existing_references = raw_msg.get("References")
    references = (
        f"{existing_references} {in_reply_to}" if existing_references else in_reply_to
    )

    # Build reply body
    reply_separator = f"On {original_msg.date}, {original_msg.from_address} wrote:"
    quoted_body_lines = [
        f"> {line}" for line in original_msg.body_markdown.splitlines()
    ]
    quoted_body = "\n".join(quoted_body_lines)

    # Combine user's body + separator + quoted original
    complete_reply_body = (
        f"{initial_body}\n\n{reply_separator}\n{quoted_body}"
        if initial_body
        else f"{reply_separator}\n{quoted_body}"
    )

    # Use compose with extracted data
    return compose(
        to=reply_to,
        cc=reply_cc,
        subject=reply_subject,
        initial_body=complete_reply_body,
        in_reply_to=in_reply_to,
        references=references,
        auto_send=auto_send,
    )


@mcp.tool(
    description="""Opens Mutt in interactive terminal to forward specific email by message ID. Supports pre-populated recipient and initial commentary. Original message included per your configuration."""
)
def forward(
    message_id: str = Field(
        ..., description="The notmuch message ID of the email to forward."
    ),
    to: str = Field(
        default="",
        description="The recipient's email address for the forwarded message. If empty, Mutt will prompt for it.",
    ),
    initial_body: str = Field(
        default="",
        description="Commentary to add to the top of the email, above the forwarded message.",
    ),
    auto_send: bool = Field(
        default=False,
        description="If True, sends the forward automatically without opening the interactive Mutt editor. WARNING: Only use with explicit user permission as this bypasses review.",
    ),
) -> OperationResult:
    """Forward an email using compose with extracted forward data."""

    # Import notmuch show to get original message data

    from mcp_handley_lab.email.notmuch.tool import show

    # Get original message data
    result = show(f"id:{message_id}")
    original_msg = result[0]

    # Build forward subject with Fwd: prefix
    original_subject = original_msg.subject
    forward_subject = (
        f"Fwd: {original_subject}"
        if not original_subject.startswith("Fwd: ")
        else original_subject
    )

    # Use original message content with normalized line endings
    forwarded_content = "\n".join(original_msg.body_markdown.splitlines())

    # Build forward body using mutt's configured format
    forward_intro = f"----- Forwarded message from {original_msg.from_address} -----"
    forward_trailer = "----- End forwarded message -----"

    # Combine user's body + intro + original message + trailer
    complete_forward_body = (
        f"{initial_body}\n\n{forward_intro}\n{forwarded_content}\n{forward_trailer}"
        if initial_body
        else f"{forward_intro}\n{forwarded_content}\n{forward_trailer}"
    )

    # Use compose with extracted data (no threading headers for forwards)
    return compose(
        to=to,
        subject=forward_subject,
        initial_body=complete_forward_body,
        auto_send=auto_send,
    )


@mcp.tool(
    description="""Lists all configured mailboxes from Mutt configuration. Useful for discovering folder names for move operations and understanding your email folder structure."""
)
def list_folders() -> list[str]:
    """List available mailboxes from mutt configuration."""
    result = _execute_mutt_command(["mutt", "-Q", "mailboxes"])

    if not result or "mailboxes=" not in result:
        return []

    folders_part = result.split("mailboxes=", 1)[1].strip('"')
    folders = [f.strip() for f in folders_part.split() if f.strip()]

    return folders


@mcp.tool(
    description="""Opens Mutt in interactive terminal focused on specific folder. Full functionality available for reading, replying, and managing emails within that mailbox."""
)
def open_folder(
    folder: str = Field(
        ...,
        description="The name of the mail folder to open (e.g., '=INBOX'). Use 'list_folders' to see available options.",
    ),
) -> OperationResult:
    """Open mutt with a specific folder."""
    mutt_cmd = _build_mutt_command(folder=folder)
    window_title = f"Mutt: {folder}"
    _execute_mutt_interactive_or_auto(mutt_cmd, window_title=window_title)

    return OperationResult(status="success", message=f"Opened folder: {folder}")


@mcp.tool(description="Checks Mutt Tool server status and mutt command availability.")
def server_info() -> ServerInfo:
    """Get server status and mutt version."""
    result = _execute_mutt_command(["mutt", "-v"])
    version_lines = result.split("\n")
    version_line = version_lines[0] if version_lines else "Unknown version"

    return ServerInfo(
        name="Mutt Tool",
        version=version_line,
        status="active",
        capabilities=[
            "compose",
            "reply",
            "forward",
            "move",
            "list_folders",
            "open_folder",
            "server_info",
        ],
        dependencies={"mutt": version_line},
    )

```

`src/mcp_handley_lab/email/mutt_aliases/__init__.py`:

```py
"""Mutt aliases management for email address book."""

```

`src/mcp_handley_lab/email/mutt_aliases/tool.py`:

```py
"""Mutt aliases tool for managing email address book via MCP."""

import re
from pathlib import Path

from pydantic import Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp
from mcp_handley_lab.shared.models import (
    MuttContact,
    MuttContactSearchResult,
    OperationResult,
    ServerInfo,
)


def _parse_alias_line(line: str) -> MuttContact:
    """Parse a mutt alias line into a MuttContact object."""
    line = line.strip()
    if not line.startswith("alias "):
        raise ValueError(f"Invalid alias line: {line}")

    # Match: alias nickname "Name" <email> or alias nickname email
    match = re.match(r'alias\s+(\S+)\s+"([^"]+)"\s*<([^>]+)>', line)
    if match:
        alias, name, email = match.groups()
        return MuttContact(alias=alias, email=email, name=name)

    # Match: alias nickname email (simple format)
    match = re.match(r"alias\s+(\S+)\s+(\S+)", line)
    if match:
        alias, email = match.groups()
        # Extract name from comment if present
        name = ""
        if "#" in line:
            name = line.split("#", 1)[1].strip()
        return MuttContact(alias=alias, email=email, name=name)

    raise ValueError(f"Could not parse alias line: {line}")


def _get_all_contacts(config_file: str = None) -> list[MuttContact]:
    """Get all contacts from mutt address book."""
    alias_file = get_mutt_alias_file(config_file)
    if not alias_file.exists():
        return []

    contacts = []
    with open(alias_file) as f:
        for line in f:
            line = line.strip()
            if line and line.startswith("alias "):
                contact = _parse_alias_line(line)
                contacts.append(contact)

    return contacts


def _find_contact_fuzzy(
    query: str, max_results: int = 5, config_file: str = None
) -> list[MuttContact]:
    """Find contacts using simple fuzzy matching."""
    contacts = _get_all_contacts(config_file)
    if not contacts:
        return []

    query_lower = query.lower()
    matches = []

    for contact in contacts:
        if (
            query_lower in contact.alias.lower()
            or query_lower in contact.email.lower()
            or query_lower in contact.name.lower()
        ):
            matches.append(contact)

    return matches[:max_results]


def get_mutt_alias_file(config_file: str = None) -> Path:
    """Get mutt alias file path from mutt configuration."""
    cmd = ["mutt", "-Q", "alias_file"]
    if config_file:
        cmd.extend(["-F", config_file])

    stdout, stderr = run_command(cmd)
    result = stdout.decode().strip()
    path = result.split("=")[1].strip("\"'")
    if path.startswith("~"):
        path = str(Path.home()) + path[1:]
    return Path(path)


@mcp.tool(
    description="""Adds contact or group to Mutt address book. Creates nickname shortcuts for email addresses. Supports individual contacts and groups with comma-separated emails or space-separated aliases."""
)
def add_contact(
    alias: str = Field(
        ..., description="A short, unique nickname for the contact (e.g., 'jdoe')."
    ),
    email: str = Field(
        ...,
        description="The full email address for an individual, or a list of aliases for a group.",
    ),
    name: str = Field(
        default="",
        description="The contact's full name (e.g., 'John Doe'). Recommended for clarity.",
    ),
    config_file: str = Field(
        default=None,
        description="Optional path to the mutt config file. Used to locate the alias file.",
    ),
) -> OperationResult:
    """Add a contact to mutt's address book."""

    if not alias or not email:
        raise ValueError("Both alias and email are required")

    clean_alias = alias.lower()
    alias_file = get_mutt_alias_file(config_file)

    if "@" in email:
        if name:
            alias_line = f'alias {clean_alias} "{name}" <{email}>\n'
        else:
            alias_line = f"alias {clean_alias} {email}\n"
    else:
        if name:
            alias_line = f"alias {clean_alias} {email}  # {name}\n"
        else:
            alias_line = f"alias {clean_alias} {email}\n"

    # Ensure the directory exists
    alias_file.parent.mkdir(parents=True, exist_ok=True)

    with open(alias_file, "a") as f:
        f.write(alias_line)

    return OperationResult(
        status="success", message=f"Added contact: {clean_alias} ({name or email})"
    )


@mcp.tool(
    description="""Searches Mutt address book with fuzzy matching. Finds contacts by partial alias, name, or email using fzf-style algorithm."""
)
def find_contact(
    query: str = Field(
        ..., description="The search term to find a contact by alias, name, or email."
    ),
    max_results: int = Field(
        default=10, description="The maximum number of contacts to return.", gt=0
    ),
    config_file: str = Field(
        default=None,
        description="Optional path to the mutt config file. Used to locate the alias file.",
    ),
) -> MuttContactSearchResult:
    """Find contacts using fuzzy matching."""

    if not query:
        raise ValueError("Search query is required")

    matches = _find_contact_fuzzy(query, max_results, config_file)

    return MuttContactSearchResult(
        query=query, matches=matches, total_found=len(matches)
    )


@mcp.tool(
    description="""Removes contact from Mutt address book with fuzzy matching. Tries exact match first, then fuzzy. Prevents accidental deletion with multiple matches."""
)
def remove_contact(
    alias: str = Field(
        ...,
        description="The alias of the contact to remove. Tries an exact match first, then a fuzzy search.",
    ),
    config_file: str = Field(
        default=None,
        description="Optional path to the mutt config file. Used to locate the alias file.",
    ),
) -> OperationResult:
    """Remove a contact from mutt's address book."""

    if not alias:
        raise ValueError("Alias is required")

    clean_alias = alias.lower()
    alias_file = get_mutt_alias_file(config_file)

    if not alias_file.exists():
        raise FileNotFoundError("No mutt alias file found")

    with open(alias_file) as f:
        lines = f.readlines()

    target_line = f"alias {clean_alias} "
    filtered_lines = [
        line for line in lines if not line.strip().startswith(target_line)
    ]

    if len(filtered_lines) == len(lines):
        fuzzy_matches = _find_contact_fuzzy(
            alias, max_results=5, config_file=config_file
        )
        if not fuzzy_matches:
            raise ValueError(f"Contact '{clean_alias}' not found")
        elif len(fuzzy_matches) == 1:
            fuzzy_alias = fuzzy_matches[0].alias
            target_line = f"alias {fuzzy_alias} "
            filtered_lines = [
                line for line in lines if not line.strip().startswith(target_line)
            ]
            clean_alias = fuzzy_alias
        else:
            matches_str = ", ".join(match.alias for match in fuzzy_matches)
            raise ValueError(
                f"Multiple matches found for '{alias}': {matches_str}. Please be more specific."
            )

    with open(alias_file, "w") as f:
        f.writelines(filtered_lines)

    return OperationResult(status="success", message=f"Removed contact: {clean_alias}")


@mcp.tool(
    description="Checks Mutt Aliases Tool server status and mutt command availability."
)
def server_info() -> ServerInfo:
    """Get server status and mutt version."""
    stdout, stderr = run_command(["mutt", "-v"])
    result = stdout.decode().strip()
    version_lines = result.split("\n")
    version_line = version_lines[0] if version_lines else "Unknown version"

    return ServerInfo(
        name="Mutt Aliases Tool",
        version="1.0.0",
        status="active",
        capabilities=["add_contact", "find_contact", "remove_contact"],
        dependencies={"mutt": version_line},
    )

```

`src/mcp_handley_lab/email/notmuch/__init__.py`:

```py
"""Notmuch email search and indexing provider."""

```

`src/mcp_handley_lab/email/notmuch/tool.py`:

```py
"""Notmuch email search and indexing provider."""

import json
import os
import re
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from pydantic import BaseModel, Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp


def _find_smart_destination(
    source_files: list[str], maildir_root: Path, destination_folder: str
) -> Path:
    """Find existing destination folder based on source email locations. Never creates new folders."""
    if not source_files:
        raise ValueError("No source files provided to determine destination.")

    folder_map = {
        "archive": ["archive"],
        "trash": ["bin", "trash", "deleted"],
        "sent": ["sent"],
        "drafts": ["drafts", "draft"],
        "spam": ["spam", "junk"],
    }

    first_source = Path(source_files[0])
    rel_path = first_source.relative_to(maildir_root)

    # Determine account path - handles both root and account-specific folders
    # Root level emails are in structure: maildir/cur/file.eml or maildir/new/file.eml
    # Account emails are in structure: maildir/Account/INBOX/cur/file.eml
    if len(rel_path.parts) > 2:  # Account/folder/cur/file.eml
        account_path = maildir_root / rel_path.parts[0]
    else:  # cur/file.eml or new/file.eml (root level)
        account_path = maildir_root
    account_name = account_path.name

    # Try exact match first
    exact_match = account_path / destination_folder
    if exact_match.is_dir():
        return exact_match

    # Try common name variations (case-insensitive)
    destination_lower = destination_folder.lower()
    if potential_names := folder_map.get(destination_lower):
        for folder in account_path.iterdir():
            if folder.is_dir() and any(
                name in folder.name.lower() for name in potential_names
            ):
                return folder

    # No match found - fail with helpful error
    available_folders = [f.name for f in account_path.iterdir() if f.is_dir()]
    raise FileNotFoundError(
        f"No existing folder matching '{destination_folder}' found in account '{account_name}'. "
        f"Available folders: {available_folders}"
    )


class EmailContent(BaseModel):
    """Structured representation of a single email's content."""

    id: str = Field(..., description="The unique message ID of the email.")
    subject: str = Field(..., description="The subject line of the email.")
    from_address: str = Field(..., description="The sender's email address and name.")
    to_address: str = Field(
        ..., description="The primary recipient's email address and name."
    )
    date: str = Field(
        ..., description="The date the email was sent, in a human-readable format."
    )
    tags: list[str] = Field(
        ..., description="A list of notmuch tags associated with the email."
    )
    body_markdown: str = Field(
        ...,
        description="The body of the email, converted to Markdown for best LLM comprehension. Preserves lists, tables, links, and formatting.",
    )
    body_format: str = Field(
        ...,
        description="The original format of the body ('html' or 'text'). Indicates if the markdown was converted or is original plain text.",
    )
    attachments: list[str] = Field(
        default_factory=list,
        description="A list of filenames for any attachments in the email.",
    )


class TagResult(BaseModel):
    """Result of tag operation."""

    message_id: str = Field(..., description="The notmuch message ID that was tagged.")
    added_tags: list[str] = Field(
        ..., description="A list of tags that were added to the message."
    )
    removed_tags: list[str] = Field(
        ..., description="A list of tags that were removed from the message."
    )


class AttachmentExtractionResult(BaseModel):
    """Result of a successful attachment extraction operation."""

    message_id: str = Field(
        ..., description="The notmuch message ID from which attachments were extracted."
    )
    saved_files: list[str] = Field(
        ..., description="A list of absolute paths to the saved attachment files."
    )
    message: str = Field(
        ..., description="Status message describing the extraction result."
    )


class MoveResult(BaseModel):
    """Result of a successful email move operation."""

    message_ids: list[str] = Field(
        ..., description="The list of message IDs that were targeted for moving."
    )
    destination_folder: str = Field(
        ..., description="The maildir folder the emails were moved to."
    )
    moved_files_count: int = Field(
        ..., description="The number of email files successfully moved."
    )
    status: str = Field(..., description="A summary of the move operation.")


@mcp.tool(
    description="""Search emails using notmuch query language. Supports sender, subject, date ranges, tags, attachments, and body content filtering with boolean operators."""
)
def search(
    query: str = Field(
        ...,
        description="A valid notmuch search query. Examples: 'from:boss', 'tag:inbox and date:2024-01-01..', 'subject:\"Project X\"'.",
    ),
    limit: int = Field(
        default=100,
        description="The maximum number of message IDs to return.",
        gt=0,
    ),
) -> list[str]:
    """Search emails using notmuch query syntax."""
    cmd = ["notmuch", "search", "--limit", str(limit), query]
    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()
    return [line.strip() for line in output.split("\n") if line.strip()]


def _get_message_from_raw_source(message_id: str) -> EmailMessage:
    """Fetches the raw source of an email from notmuch and parses it into an EmailMessage object."""
    raw_email_bytes, _ = run_command(
        ["notmuch", "show", "--format=raw", f"id:{message_id}"]
    )
    parser = BytesParser(policy=policy.default)
    return parser.parsebytes(raw_email_bytes)


def parse_email_content(msg: EmailMessage):
    """Parses an EmailMessage to extract the best text body and attachments."""
    body = None
    attachments = []
    html_part = None

    body_part = msg.get_body(preferencelist=("html", "plain"))

    if body_part:
        content = body_part.get_content()

        if body_part.get_content_type() == "text/html":
            html_part = body_part
            soup = BeautifulSoup(content, "html.parser")
            for s in soup(["script", "style"]):
                s.decompose()
            body = md(str(soup), heading_style="ATX")
        else:
            body = content
    elif not msg.is_multipart() and not msg.is_attachment():
        body = msg.get_content()

    for part in msg.walk():
        if part.get_filename() and part is not body_part:
            attachment_info = f"{part.get_filename()} ({part.get_content_type()})"
            attachments.append(attachment_info)

    return {
        "body": body.strip() if body else "",
        "attachments": sorted(set(attachments)),
        "body_format": "html" if html_part else "text",
    }


@mcp.tool(
    description="""Display complete email content by message ID or notmuch query. Returns a structured object with headers and a clean, Markdown-formatted body for optimal LLM understanding."""
)
def show(
    query: str = Field(
        ...,
        description="A notmuch query to select the email(s) to display. Typically an 'id:<message-id>' query for a single email.",
    ),
) -> list[EmailContent]:
    """Show email content by fetching raw email sources and parsing with Python's email library."""
    cmd = ["notmuch", "search", "--format=json", "--output=messages", query]
    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()
    message_ids = json.loads(output)

    results = []
    for message_id in message_ids:
        reconstructed_msg = _get_message_from_raw_source(message_id)

        extracted_data = parse_email_content(reconstructed_msg)
        body_markdown = extracted_data["body"]
        body_format = extracted_data["body_format"]
        attachments = extracted_data["attachments"]

        subject = reconstructed_msg["Subject"]
        from_address = reconstructed_msg["From"]
        to_address = reconstructed_msg["To"]
        date = reconstructed_msg["Date"]

        tag_cmd = ["notmuch", "search", "--output=tags", f"id:{message_id}"]
        tag_stdout, _ = run_command(tag_cmd)
        tags = [
            tag.strip()
            for tag in tag_stdout.decode().strip().split("\n")
            if tag.strip()
        ]

        results.append(
            EmailContent(
                id=message_id,
                subject=subject,
                from_address=from_address,
                to_address=to_address,
                date=date,
                tags=tags,
                body_markdown=body_markdown.strip(),
                body_format=body_format,
                attachments=attachments,
            )
        )
    return results


@mcp.tool(
    description="""Index newly received emails into notmuch database. Required after email sync to make new messages searchable. Updates tags per initial rules."""
)
def new() -> str:
    """Index newly received emails with notmuch new."""
    stdout, stderr = run_command(["notmuch", "new"])
    output = stdout.decode().strip()
    return f"Notmuch database updated:\n{output}"


@mcp.tool(
    description="""List all tags in notmuch database. Shows system tags (inbox, unread, sent) and custom tags. Useful for understanding organization and planning searches."""
)
def list_tags() -> list[str]:
    """List all tags in the notmuch database."""
    stdout, stderr = run_command(["notmuch", "search", "--output=tags", "*"])
    output = stdout.decode().strip()
    return sorted([tag.strip() for tag in output.split("\n") if tag.strip()])


@mcp.tool(
    description="""Retrieve notmuch configuration settings. Shows all settings or specific key. Useful for troubleshooting database path, user info, and tagging rules."""
)
def config(
    key: str = Field(
        default="",
        description="An optional specific configuration key to retrieve (e.g., 'database.path'). If omitted, all configurations are listed.",
    ),
) -> str:
    """Get notmuch configuration values."""
    cmd = ["notmuch", "config", "list"]

    if key:
        cmd = ["notmuch", "config", "get", key]

    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()
    if key:
        return f"{key} = {output}"
    return f"Notmuch configuration:\n{output}"


@mcp.tool(
    description="""Count emails matching notmuch query without retrieving content. Fast way to validate queries and monitor email volumes."""
)
def count(
    query: str = Field(
        ...,
        description="A valid notmuch search query to count matching emails. Example: 'tag:unread'.",
    ),
) -> int:
    """Count emails matching a notmuch query."""
    cmd = ["notmuch", "count", query]

    stdout, stderr = run_command(cmd)
    count_result = stdout.decode().strip()
    return int(count_result)


@mcp.tool(
    description="""Add or remove tags from emails by message ID. Primary method for organizing emails in notmuch."""
)
def tag(
    message_id: str = Field(
        ..., description="The notmuch message ID of the email to modify."
    ),
    add_tags: list[str] = Field(
        default_factory=list, description="A list of tags to add to the email."
    ),
    remove_tags: list[str] = Field(
        default_factory=list, description="A list of tags to remove from the email."
    ),
) -> TagResult:
    """Add or remove tags from a specific email using notmuch."""
    cmd = (
        ["notmuch", "tag"]
        + [f"+{tag}" for tag in add_tags]
        + [f"-{tag}" for tag in remove_tags]
        + [f"id:{message_id}"]
    )

    run_command(cmd)

    return TagResult(
        message_id=message_id, added_tags=add_tags, removed_tags=remove_tags
    )


@mcp.tool(
    description="Extracts and saves one or all attachments from a specific email. If 'filename' is provided, only that attachment is saved. Files are saved to 'output_dir', which defaults to the current directory. Returns a result object with a list of absolute paths to the saved files."
)
def extract_attachments(
    message_id: str = Field(
        ...,
        description="The notmuch message ID of the email containing the attachments.",
    ),
    output_dir: str = Field(
        default="",
        description="The directory to save attachments to. Defaults to the current directory.",
    ),
    filename: str = Field(
        default="",
        description="The specific filename of the attachment to extract. If omitted, all attachments are extracted.",
    ),
) -> AttachmentExtractionResult:
    """
    Extracts attachments from an email, failing loudly if the email or attachment isn't found.
    """
    msg = _get_message_from_raw_source(message_id)

    if filename and (match := re.match(r"(.+?)\s+\(.+\)", filename)):
        filename = match.group(1)

    save_path = Path(output_dir or ".").expanduser()
    save_path.mkdir(parents=True, exist_ok=True)

    saved_files = []
    found_attachments = []

    for part in msg.walk():
        if (part_filename := part.get_filename()) and (
            not filename or part_filename == filename
        ):
            found_attachments.append(part)

    if filename and not found_attachments:
        raise FileNotFoundError(
            f"Attachment '{filename}' not found in email id:{message_id}."
        )

    if not found_attachments:
        return AttachmentExtractionResult(
            message_id=message_id,
            saved_files=[],
            message="No attachments found in the email.",
        )

    for part in found_attachments:
        part_filename = part.get_filename()
        clean_filename = re.sub(r'[\\/*?:"<>|]', "_", Path(part_filename).name)
        file_path = save_path / clean_filename

        counter = 1
        stem, suffix = file_path.stem, file_path.suffix
        while file_path.exists():
            file_path = save_path / f"{stem}_{counter}{suffix}"
            counter += 1

        if payload := part.get_payload(decode=True):
            file_path.write_bytes(payload)
            saved_files.append(str(file_path))

    return AttachmentExtractionResult(
        message_id=message_id,
        saved_files=saved_files,
        message=f"Successfully saved {len(saved_files)} attachment(s) to {save_path}.",
    )


@mcp.tool(
    description="Moves emails to an existing maildir folder (e.g., 'Trash', 'Archive'). Automatically finds the correct folder within the same email account (e.g., 'Hermes/Archive' for emails from 'Hermes/INBOX'). Will not create new folders - only moves to existing ones."
)
def move(
    message_ids: list[str] = Field(
        ...,
        description="A list of notmuch message IDs for the emails to be moved.",
        min_length=1,
    ),
    destination_folder: str = Field(
        ...,
        description="The destination maildir folder name (e.g., 'Trash', 'Archive'). Must be an existing folder. The tool will find the appropriate folder within the same email account.",
    ),
) -> MoveResult:
    """
    Moves emails to a specified maildir folder.

    This function performs three main steps:
    1. Finds the filesystem paths of the emails using their message IDs.
    2. Moves the email files to the destination maildir folder (into its 'new' subdirectory).
    3. Updates the notmuch database to reflect the changes.
    """
    if not message_ids:
        raise ValueError("At least one message_id must be provided.")

    query = " or ".join([f"id:{mid}" for mid in message_ids])
    search_cmd = ["notmuch", "search", "--output=files", query]
    stdout, _ = run_command(search_cmd)

    source_files = [
        line.strip() for line in stdout.decode().strip().split("\n") if line.strip()
    ]

    if not source_files:
        raise FileNotFoundError(
            f"No email files found for the given message IDs: {message_ids}"
        )

    # Get maildir root and determine smart destination folder
    db_path_str, _ = run_command(["notmuch", "config", "get", "database.path"])
    maildir_root = Path(db_path_str.decode().strip())

    # Find the appropriate destination based on source email locations
    smart_destination = _find_smart_destination(
        source_files, maildir_root, destination_folder
    )
    destination_dir = smart_destination / "new"

    for file_path in source_files:
        source_path = Path(file_path)
        destination_path = destination_dir / source_path.name

        # Use os.rename instead of os.renames to avoid creating directories
        # Create the destination 'new' directory if needed (this is safe)
        destination_dir.mkdir(parents=True, exist_ok=True)

        try:
            os.rename(source_path, destination_path)
        except OSError as e:
            raise OSError(
                f"Failed to move {source_path} to {destination_path}: {e}"
            ) from e

    # Update the notmuch index to discover the moved files
    new()

    # Construct and return a structured result
    moved_count = len(source_files)
    status_message = f"Successfully moved {moved_count} email(s) to '{destination_folder}' and updated the index."
    if moved_count < len(message_ids):
        status_message += f" Note: {len(message_ids) - moved_count} of the requested message IDs could not be found."

    return MoveResult(
        message_ids=message_ids,
        destination_folder=destination_folder,
        moved_files_count=moved_count,
        status=status_message,
    )

```

`src/mcp_handley_lab/email/oauth2/__init__.py`:

```py
"""OAuth2 authentication provider for email services."""

```

`src/mcp_handley_lab/email/oauth2/tool.py`:

```py
"""OAuth2 authentication provider for email services."""

from pydantic import Field

from mcp_handley_lab.email.common import mcp


@mcp.tool(
    name="oauth2_setup_m365",
    description="""Start Microsoft 365 OAuth2 authentication - Step 1 of 2. Generates authorization URL for browser login using secure authorization code flow.""",
)
def setup_m365_oauth2(
    client_id: str = Field(
        default="08162f7c-0fd2-4200-a84a-f25a4db0b584",
        description="The Microsoft 365 application client ID. Defaults to the one used by Thunderbird.",
    ),
    client_secret: str = Field(
        default="TxRBilcHdC6WGBee]fs?QR:SJ8nI[g82",
        description="The Microsoft 365 application client secret. Defaults to the one used by Thunderbird.",
    ),
) -> str:
    """Start Microsoft 365 OAuth2 setup using authorization code flow.

    Uses Thunderbird's client credentials by default.
    Returns authorization URL - complete with oauth2_complete_m365.
    """
    from msal import ConfidentialClientApplication

    scopes = ["https://outlook.office365.com/IMAP.AccessAsUser.All"]
    redirect_uri = "http://localhost"

    app = ConfidentialClientApplication(client_id, client_credential=client_secret)
    auth_url = app.get_authorization_request_url(scopes, redirect_uri=redirect_uri)

    return f"""OAuth2 Authorization Code Setup:

Claude should now open the following URL in your default browser:
{auth_url}

After you complete the login process, you will be redirected to a page showing "This site can't be reached" - this is expected! Copy the entire URL from the address bar (it contains your authorization code) and provide it to complete the OAuth2 setup with oauth2_complete_m365."""


@mcp.tool(
    name="oauth2_complete_m365",
    description="""Complete Microsoft 365 OAuth2 authentication - Step 2 of 2. Exchanges authorization code for tokens and provides ready-to-use offlineimap configuration.""",
)
def complete_m365_oauth2(
    redirect_url: str = Field(
        ...,
        description="The full URL from the browser's address bar after completing the login, which contains the authorization code.",
    ),
    client_id: str = Field(
        default="08162f7c-0fd2-4200-a84a-f25a4db0b584",
        description="The Microsoft 365 application client ID. Must match the one used in the setup step.",
    ),
    client_secret: str = Field(
        default="TxRBilcHdC6WGBee]fs?QR:SJ8nI[g82",
        description="The Microsoft 365 application client secret. Must match the one used in the setup step.",
    ),
) -> str:
    """Complete Microsoft 365 OAuth2 setup using the redirect URL from browser.

    Args:
        redirect_url: The complete URL from the browser after login (contains authorization code)
        client_id: Microsoft app client ID (defaults to Thunderbird's)
        client_secret: Microsoft app client secret (defaults to Thunderbird's)

    Returns the refresh token configuration for offlineimap.
    """
    from msal import ConfidentialClientApplication, SerializableTokenCache

    scopes = ["https://outlook.office365.com/IMAP.AccessAsUser.All"]
    redirect_uri = "http://localhost"

    code_start = redirect_url.find("code=") + 5
    code_end = (
        redirect_url.find("&", code_start)
        if "&" in redirect_url[code_start:]
        else len(redirect_url)
    )
    auth_code = redirect_url[code_start:code_end]

    cache = SerializableTokenCache()
    app = ConfidentialClientApplication(
        client_id, client_credential=client_secret, token_cache=cache
    )

    app.acquire_token_by_authorization_code(
        auth_code, scopes, redirect_uri=redirect_uri
    )

    refresh_token = cache.find("RefreshToken")[0]["secret"]

    return f"""✅ OAuth2 setup completed successfully!

Refresh token: {refresh_token}

Configuration needed for your .offlineimaprc file in the repository section:
auth_mechanisms = XOAUTH2
oauth2_request_url = https://login.microsoftonline.com/common/oauth2/v2.0/token
oauth2_client_id = {client_id}
oauth2_client_secret = {client_secret}
oauth2_refresh_token = {refresh_token}

Claude should offer to update the .offlineimaprc file automatically with this configuration.

To update your .offlineimaprc file, add these lines to the [Repository Your-Remote-Name] section:

```
[Repository Your-Remote-Name]
type = IMAP
remotehost = outlook.office365.com
remoteport = 993
remoteuser = your.email@domain.com
ssl = yes
auth_mechanisms = XOAUTH2
oauth2_request_url = https://login.microsoftonline.com/common/oauth2/v2.0/token
oauth2_client_id = {client_id}
oauth2_client_secret = {client_secret}
oauth2_refresh_token = {refresh_token}
```"""

```

`src/mcp_handley_lab/email/offlineimap/__init__.py`:

```py
"""OfflineIMAP email synchronization provider."""

```

`src/mcp_handley_lab/email/offlineimap/tool.py`:

```py
"""OfflineIMAP email synchronization provider."""

from pathlib import Path

from pydantic import Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp
from mcp_handley_lab.shared.models import OperationResult


@mcp.tool(
    description="Performs a full, one-time email synchronization for one or all accounts configured in `~/.offlineimaprc`. Downloads new mail, uploads sent items, and syncs flags and folders between local and remote servers. An optional `account` name can be specified to sync only that account."
)
def sync(
    account: str = Field(
        default="",
        description="Optional name of a specific account to sync from `~/.offlineimaprc`. If omitted, all accounts are synced.",
    ),
) -> OperationResult:
    """Run offlineimap to synchronize emails."""
    cmd = ["offlineimap", "-o1"]

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd, timeout=300)  # 5 minutes for email sync
    output = stdout.decode().strip()
    return OperationResult(
        status="success", message=f"Email sync completed successfully\n{output}"
    )


@mcp.tool(
    description="Validates the `~/.offlineimaprc` configuration by performing a dry run without actually syncing any mail. This is used to check for syntax errors, connection issues, or other setup problems before running a real sync."
)
def sync_status(
    config_file: str = Field(
        default=None,
        description="Optional path to the offlineimap configuration file. Defaults to `~/.offlineimaprc`.",
    ),
) -> OperationResult:
    """Check offlineimap sync status."""
    config_path = Path(config_file) if config_file else Path.home() / ".offlineimaprc"
    if not config_path.exists():
        raise FileNotFoundError(f"offlineimap configuration not found at {config_path}")

    stdout, stderr = run_command(["offlineimap", "--dry-run", "-o1"])
    output = stdout.decode().strip()
    return OperationResult(
        status="success", message=f"Offlineimap configuration valid:\n{output}"
    )


@mcp.tool(
    description="Displays comprehensive information about all configured email accounts, repositories, and their settings from `~/.offlineimaprc`. Shows connection details, authentication methods, and folder mappings. Useful for troubleshooting and understanding your email setup."
)
def repo_info(
    config_file: str = Field(
        default=None,
        description="Optional path to the offlineimap configuration file. Defaults to `~/.offlineimaprc`.",
    ),
) -> OperationResult:
    """Get information about configured offlineimap repositories."""
    stdout, stderr = run_command(["offlineimap", "--info"])
    output = stdout.decode().strip()
    return OperationResult(
        status="success", message=f"Repository information:\n{output}"
    )


@mcp.tool(
    description="Performs a dry-run simulation of email synchronization to show what would be synchronized without actually downloading, uploading, or modifying any emails. Useful for testing configuration changes and understanding sync operations before committing."
)
def sync_preview(
    account: str = Field(
        default="",
        description="Optional name of a specific account to preview syncing. If omitted, all accounts are previewed.",
    ),
) -> OperationResult:
    """Preview email sync operations without making changes."""
    cmd = ["offlineimap", "--dry-run", "-o1"]

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()
    return OperationResult(
        status="success",
        message=f"Sync preview{' for account ' + account if account else ''}:\n{output}",
    )


@mcp.tool(
    description="Performs fast email synchronization focusing on new messages while skipping time-consuming flag updates and folder operations. Downloads new emails quickly but less comprehensive than full sync. Ideal for frequent email checks."
)
def quick_sync(
    account: str = Field(
        default="",
        description="Optional name of a specific account for a quick sync. If omitted, all accounts are quick-synced.",
    ),
) -> OperationResult:
    """Perform quick email sync without updating flags."""
    cmd = ["offlineimap", "-q", "-o1"]

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd, timeout=180)  # 3 minutes for quick sync
    output = stdout.decode().strip()
    return OperationResult(
        status="success", message=f"Quick sync completed successfully\n{output}"
    )


@mcp.tool(
    description="Syncs only specified folders rather than all configured folders. Provide comma-separated folder names to sync selectively. Useful for large mailboxes or focusing on important folders like 'INBOX,Sent,Drafts'. Efficient for managing large email accounts with selective folder needs."
)
def sync_folders(
    folders: str = Field(
        ...,
        description="A comma-separated list of folder names to sync (e.g., 'INBOX,Sent').",
    ),
    account: str = Field(
        default="",
        description="Optional name of a specific account where the folders reside. If omitted, offlineimap's default is used.",
    ),
) -> OperationResult:
    """Sync only specified folders."""
    cmd = ["offlineimap", "-o1", "-f", folders]

    if account:
        cmd.extend(["-a", account])

    stdout, stderr = run_command(cmd, timeout=180)  # 3 minutes for folder sync
    output = stdout.decode().strip()
    return OperationResult(
        status="success", message=f"Folder sync completed for: {folders}\n{output}"
    )

```

`src/mcp_handley_lab/email/tool.py`:

```py
"""Unified email client MCP tool integrating all email providers."""

import importlib
from pathlib import Path

from pydantic import Field

from mcp_handley_lab.common.process import run_command

# Import the shared mcp instance
from mcp_handley_lab.email.common import mcp
from mcp_handley_lab.shared.models import ServerInfo


def discover_and_register_tools():
    """
    Automatically discovers and imports tool modules from subdirectories
    to trigger their @mcp.tool decorators for registration.
    """
    package_dir = Path(__file__).parent
    package_name = package_dir.name

    print(f"Discovering tools in '{package_name}' sub-packages...")

    for sub_dir in package_dir.iterdir():
        # Look for subdirectories that are valid packages (have __init__.py)
        # and contain a tool.py file.
        if sub_dir.is_dir() and (sub_dir / "__init__.py").exists():
            tool_module_path = sub_dir / "tool.py"
            if tool_module_path.exists():
                # Construct the full module path for importlib
                # e.g., 'mcp_handley_lab.email.msmtp.tool'
                module_name = f"mcp_handley_lab.{package_name}.{sub_dir.name}.tool"
                try:
                    # This import triggers the @mcp.tool decorators
                    importlib.import_module(module_name)
                    print(f"  ✓ Registered tools from: {sub_dir.name}")
                except ImportError as e:
                    print(f"  ✗ Failed to import {module_name}: {e}")


# Run the discovery process when this module is loaded
discover_and_register_tools()


@mcp.tool(
    description="Checks status of all email tools (msmtp, offlineimap, notmuch) and their configurations."
)
def server_info(
    config_file: str = Field(
        default=None,
        description="Optional path to the offlineimap configuration file (e.g., ~/.offlineimaprc). If not provided, the default location will be used.",
    )
) -> ServerInfo:
    """Check the status of email tools and their configurations."""
    run_command(["msmtp", "--version"])

    from mcp_handley_lab.email.msmtp.tool import _parse_msmtprc

    accounts = _parse_msmtprc()

    run_command(["offlineimap", "--version"])
    config_path = Path(config_file) if config_file else Path.home() / ".offlineimaprc"
    if not config_path.exists():
        raise RuntimeError(f"offlineimap configuration not found at {config_path}")

    run_command(["notmuch", "--version"])

    stdout, stderr = run_command(["notmuch", "count", "*"])
    db_info = stdout.decode().strip()
    db_status = f"{db_info} messages indexed"

    try:
        import importlib.util

        spec = importlib.util.find_spec("msal")
        oauth2_status = (
            "supported (msal available)"
            if spec
            else "not supported (msal not installed)"
        )
    except ImportError:
        oauth2_status = "not supported (msal not installed)"

    return ServerInfo(
        name="Email Tool Server",
        version="1.9.4",
        status="active",
        capabilities=["msmtp", "offlineimap", "notmuch", "mutt", "oauth2"],
        dependencies={
            "msmtp_accounts": str(len(accounts)),
            "notmuch_database": db_status,
            "offlineimap_config": "found",
            "oauth2_support": oauth2_status,
        },
    )

```

`src/mcp_handley_lab/google_calendar/__init__.py`:

```py
"""Google Calendar tool for MCP framework."""

```

`src/mcp_handley_lab/google_calendar/tool.py`:

```py
"""Google Calendar tool for calendar management via MCP."""

import pickle
import zoneinfo
from datetime import datetime, timedelta, timezone
from typing import Any

import dateparser
import pendulum
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.shared.models import ServerInfo

# Application-level default timezone as final fallback
DEFAULT_TIMEZONE = "Europe/London"


class Attendee(BaseModel):
    """Calendar event attendee."""

    email: str = Field(..., description="The email address of the attendee.")
    responseStatus: str = Field(
        default="needsAction",
        description="The attendee's response status (e.g., 'accepted', 'declined', 'needsAction').",
    )


class EventDateTime(BaseModel):
    """Event date/time information."""

    dateTime: str = Field(
        default="",
        description="The timestamp for timed events in RFC3339 format (e.g., '2023-12-25T10:00:00Z').",
    )
    date: str = Field(
        default="",
        description="The date for all-day events in YYYY-MM-DD format (e.g., '2023-12-25').",
    )
    timeZone: str = Field(
        default="",
        description="The timezone identifier (e.g., 'America/New_York', 'Europe/London').",
    )


class CalendarEvent(BaseModel):
    """Calendar event details."""

    id: str = Field(..., description="The unique identifier for the event.")
    summary: str = Field(..., description="The title or summary of the event.")
    description: str = Field(
        default="", description="A detailed description or notes for the event."
    )
    location: str = Field(
        default="", description="The physical location or meeting link for the event."
    )
    start: EventDateTime = Field(
        ..., description="The start time of the event, including timezone."
    )
    end: EventDateTime = Field(
        ..., description="The end time of the event, including timezone."
    )
    attendees: list[Attendee] = Field(
        default_factory=list, description="A list of people attending the event."
    )
    calendar_name: str = Field(
        default="", description="The name of the calendar this event belongs to."
    )
    created: str = Field(
        default="", description="The creation time of the event as an ISO 8601 string."
    )
    updated: str = Field(
        default="",
        description="The last modification time of the event as an ISO 8601 string.",
    )


class CreatedEventResult(BaseModel):
    """Result of creating a calendar event."""

    status: str = Field(
        ...,
        description="The status of the event creation (e.g., 'confirmed', 'tentative').",
    )
    event_id: str = Field(
        ..., description="The unique identifier assigned to the newly created event."
    )
    title: str = Field(..., description="The title of the created event.")
    time: str = Field(
        ..., description="A human-readable summary of when the event occurs."
    )
    calendar: str = Field(
        ..., description="The name or ID of the calendar where the event was created."
    )
    attendees: list[str] = Field(
        ..., description="A list of attendee email addresses for the event."
    )


class UpdateEventResult(BaseModel):
    """Result of a successful event update operation."""

    event_id: str = Field(
        ..., description="The unique identifier of the updated event."
    )
    html_link: str = Field(
        ..., description="A direct link to the event in the Google Calendar UI."
    )
    updated_fields: list[str] = Field(
        ...,
        description="A list of the fields that were modified in this update operation.",
    )
    message: str = Field(..., description="A human-readable confirmation message.")


class CalendarInfo(BaseModel):
    """Calendar information."""

    id: str = Field(..., description="The unique identifier of the calendar.")
    summary: str = Field(..., description="The title or name of the calendar.")
    accessRole: str = Field(
        ...,
        description="The user's access level to the calendar (e.g., 'owner', 'reader', 'writer').",
    )
    colorId: str = Field(
        ..., description="The color identifier used to display the calendar."
    )


class FreeTimeSlot(BaseModel):
    """Available time slot."""

    start: str = Field(
        ..., description="The start time of the free slot in ISO 8601 format."
    )
    end: str = Field(
        ..., description="The end time of the free slot in ISO 8601 format."
    )
    duration_minutes: int = Field(
        ..., description="The duration of the free time slot in minutes."
    )


mcp = FastMCP("Google Calendar Tool")


# Google Calendar API scopes
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_calendar_service():
    """Get authenticated Google Calendar service."""
    creds = None
    token_file = settings.google_token_path
    credentials_file = settings.google_credentials_path

    if token_file.exists():
        with open(token_file, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_file), SCOPES
            )
            creds = flow.run_local_server(port=0)

        token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)

    return build("calendar", "v3", credentials=creds)


def _resolve_calendar_id(calendar_id: str, service) -> str:
    """Resolve calendar name to calendar ID."""
    if calendar_id in ["primary", "all"] or "@" in calendar_id:
        return calendar_id

    calendar_list = service.calendarList().list().execute()

    for calendar in calendar_list.get("items", []):
        if calendar.get("summary", "").lower() == calendar_id.lower():
            return calendar["id"]

    return calendar_id


def _get_calendar_timezone(service: Any, calendar_id: str) -> str:
    """Gets the timezone of a specific calendar, falling back to the default."""
    try:
        calendar = service.calendars().get(calendarId=calendar_id).execute()
        return calendar.get("timeZone", DEFAULT_TIMEZONE)
    except Exception:
        # Fallback if the calendar isn't found or another error occurs
        return DEFAULT_TIMEZONE


def _parse_user_datetime(dt_str: str, default_tz: str = None) -> pendulum.DateTime:
    """
    Parses a datetime string using advanced natural language processing.

    Args:
        dt_str: The input datetime string (can be natural language)
        default_tz: Default timezone for naive datetimes (fallback context)

    Returns:
        A timezone-aware pendulum.DateTime object
    """
    if not dt_str.strip():
        raise ValueError("Datetime string cannot be empty")

    # Try dateparser first (best for natural language)
    settings = {
        "PREFER_DATES_FROM": "future",  # Good for event creation
        "RETURN_AS_TIMEZONE_AWARE": True,
    }

    if default_tz:
        settings["TIMEZONE"] = default_tz

    parsed_dt = dateparser.parse(dt_str, settings=settings)

    if parsed_dt:
        # Convert to pendulum for better timezone handling
        try:
            return pendulum.instance(parsed_dt)
        except Exception:
            # Handle StaticTzInfo conversion issues
            return pendulum.parse(parsed_dt.isoformat())

    # Fallback to pendulum for structured formats
    try:
        parsed_dt = pendulum.parse(dt_str)
        # If no timezone and we have a default, apply it
        if parsed_dt.timezone is None and default_tz:
            parsed_dt = parsed_dt.in_timezone(default_tz)
        return parsed_dt
    except Exception:
        pass

    raise ValueError(f"Could not parse datetime string: '{dt_str}'")


def _prepare_event_datetime(dt_str: str, target_tz: str = None) -> dict[str, str]:
    """
    Parses a datetime string and prepares the correct Google Calendar API format.
    Supports natural language, flexible formats, and mixed timezones.

    Args:
        dt_str: The input datetime string (supports natural language)
        target_tz: Target timezone (if None, preserves input timezone)

    Returns:
        A dictionary like {'dateTime': 'YYYY-MM-DDTHH:MM:SS', 'timeZone': '...'} for
        timed events, or {'date': 'YYYY-MM-DD'} for all-day events.
    """
    if not dt_str.strip():
        raise ValueError("Datetime string cannot be empty")

    # Check for date-only patterns (all-day events)
    # Only treat as date-only if it's clearly a date format without time
    looks_like_date_only = (
        len(dt_str.strip().split()) == 1  # Single token
        and "-" in dt_str  # Has date separators
        and dt_str.count("-") == 2  # YYYY-MM-DD format
        and not any(char.isalpha() for char in dt_str)  # No letters
        and "T" not in dt_str
        and ":" not in dt_str  # No time components
    )

    if looks_like_date_only:
        try:
            # Use dateparser for flexible date parsing
            parsed_dt = dateparser.parse(
                dt_str, settings={"PREFER_DATES_FROM": "future"}
            )
            if parsed_dt:
                return {"date": parsed_dt.strftime("%Y-%m-%d")}
        except Exception:
            pass

        # Fallback to pendulum for date parsing
        try:
            parsed_dt = pendulum.parse(dt_str)
            return {"date": parsed_dt.format("YYYY-MM-DD")}
        except Exception as e:
            raise ValueError(f"Could not parse date string: {dt_str}") from e

    # Handle timed events with advanced parsing
    try:
        parsed_dt = _parse_user_datetime(dt_str, target_tz)
    except Exception as e:
        raise ValueError(f"Could not parse datetime string: {dt_str}") from e

    # Convert to target timezone if specified, otherwise preserve input timezone
    if target_tz and target_tz != str(parsed_dt.timezone):
        final_dt = parsed_dt.in_timezone(target_tz)
    else:
        final_dt = parsed_dt

    # Return the format Google Calendar prefers
    # Handle timezone string conversion properly
    timezone_str = str(final_dt.timezone)
    if timezone_str.startswith("FixedTimezone("):
        # For fixed offsets, convert to standard format
        timezone_str = final_dt.timezone.name

    return {
        "dateTime": final_dt.isoformat(),
        "timeZone": timezone_str,
    }


def _normalize_datetime_for_output(dt_info: dict) -> dict:
    """Convert timezone-inconsistent datetime to unambiguous format for LLMs.

    Converts formats like:
    {"dateTime": "14:30:00Z", "timeZone": "Europe/London"}
    to:
    {"dateTime": "15:30:00+01:00", "timeZone": "Europe/London"}

    This eliminates LLM confusion between GMT/BST interpretation.
    """
    if not dt_info.get("dateTime") or not dt_info.get("timeZone"):
        return dt_info

    dt_str = dt_info["dateTime"]
    tz_str = dt_info["timeZone"]

    # Only process if we have a Z suffix with a specific timezone
    if not dt_str.endswith("Z") or tz_str.lower() == "utc":
        return dt_info

    try:
        # Parse UTC datetime
        utc_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

        # Convert to target timezone
        target_tz = zoneinfo.ZoneInfo(tz_str)
        local_dt = utc_dt.astimezone(target_tz)

        # Return with explicit offset format
        return {"dateTime": local_dt.isoformat(), "timeZone": tz_str}
    except Exception:
        # If conversion fails, return original
        return dt_info


def _build_event_model(event_data: dict) -> CalendarEvent:
    """Convert raw Google Calendar API event dict to CalendarEvent model."""
    start_raw = event_data.get("start", {})
    end_raw = event_data.get("end", {})

    # Normalize datetime formats for unambiguous LLM interpretation
    start_normalized = _normalize_datetime_for_output(start_raw)
    end_normalized = _normalize_datetime_for_output(end_raw)

    start_dt = EventDateTime(**start_normalized)
    end_dt = EventDateTime(**end_normalized)

    attendees = [
        Attendee(
            email=att.get("email", "Unknown"),
            responseStatus=att.get("responseStatus", "needsAction"),
        )
        for att in event_data.get("attendees", [])
    ]

    return CalendarEvent(
        id=event_data["id"],
        summary=event_data.get("summary", "No Title"),
        description=event_data.get("description", ""),
        location=event_data.get("location", ""),
        start=start_dt,
        end=end_dt,
        attendees=attendees,
        calendar_name=event_data.get("calendar_name", ""),
        created=event_data.get("created", ""),
        updated=event_data.get("updated", ""),
    )


def _get_normalization_patch(event_data: dict) -> dict:
    """If event has timezone inconsistency, return patch to fix it."""
    if not _has_timezone_inconsistency(event_data):
        return {}

    start = event_data["start"]
    end = event_data["end"]
    target_tz = zoneinfo.ZoneInfo(start["timeZone"])

    patch = {}

    # Normalize start time
    utc_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
    local_dt = utc_dt.astimezone(target_tz)
    patch["start"] = {
        "dateTime": local_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "timeZone": start["timeZone"],
    }

    # Normalize end time
    utc_dt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
    local_dt = utc_dt.astimezone(target_tz)
    patch["end"] = {
        "dateTime": local_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "timeZone": end["timeZone"],
    }

    return patch


def _has_timezone_inconsistency(event_data: dict) -> bool:
    """Check if an event has conflicting UTC time and timezone label."""
    start = event_data.get("start", {})

    # Check if this is a timed event (not all-day)
    if "dateTime" not in start:
        return False

    start_dt = start.get("dateTime", "")
    timezone = start.get("timeZone", "")

    # The inconsistency exists if dateTime ends in 'Z' (UTC) AND
    # a specific, non-UTC timezone is also defined
    has_utc_suffix = start_dt.endswith("Z")
    has_specific_timezone = bool(timezone and timezone.lower() != "utc")

    return has_utc_suffix and has_specific_timezone


def _parse_datetime_to_utc(dt_str: str) -> str:
    """
    Parse datetime string and convert to UTC with proper timezone handling.

    Handles:
    - ISO 8601 with timezone: "2024-06-30T14:00:00+01:00" -> "2024-06-30T13:00:00Z"
    - ISO 8601 with Z: "2024-06-30T14:00:00Z" -> "2024-06-30T14:00:00Z"
    - ISO 8601 naive: "2024-06-30T14:00:00" -> "2024-06-30T14:00:00Z" (assumes UTC)
    - Date only: "2024-06-30" -> "2024-06-30T00:00:00Z"
    """
    if not dt_str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if "T" not in dt_str:
        return dt_str + "T00:00:00Z"

    if dt_str.endswith("Z"):
        return dt_str
    elif "+" in dt_str or dt_str.count("-") > 2:
        dt = datetime.fromisoformat(dt_str)
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.isoformat().replace("+00:00", "Z")
    else:
        return dt_str + "Z"


def _client_side_filter(
    events: list[dict[str, Any]],
    search_text: str = "",
    search_fields: list[str] | None = None,
    case_sensitive: bool = False,
    match_all_terms: bool = True,
) -> list[dict[str, Any]]:
    """
    Client-side filtering of events with advanced search capabilities.

    Args:
        events: List of calendar events to filter
        search_text: Text to search for
        search_fields: Fields to search in. Default: ['summary', 'description', 'location']
        case_sensitive: Whether search should be case sensitive
        match_all_terms: If True, all search terms must match (AND logic).
                        If False, any search term can match (OR logic).
    """
    if not search_text:
        return events

    if search_fields is None:
        search_fields = ["summary", "description", "location"]

    search_terms = search_text.split()
    if not search_terms:
        return events

    if not case_sensitive:
        search_terms = [term.lower() for term in search_terms]

    filtered_events = []

    for event in events:
        searchable_text_parts = []

        for field in search_fields:
            if field == "summary":
                text = event.get("summary", "")
            elif field == "description":
                text = event.get("description", "")
            elif field == "location":
                text = event.get("location", "")
            elif field == "attendees":
                attendees = event.get("attendees", [])
                attendee_texts = []
                for attendee in attendees:
                    attendee_texts.append(attendee.get("email", ""))
                    attendee_texts.append(attendee.get("displayName", ""))
                text = " ".join(attendee_texts)
            else:
                text = event.get(field, "")

            if text:
                searchable_text_parts.append(text)

        full_searchable_text = " ".join(searchable_text_parts)
        if not case_sensitive:
            full_searchable_text = full_searchable_text.lower()

        if match_all_terms:
            matches = all(term in full_searchable_text for term in search_terms)
        else:
            matches = any(term in full_searchable_text for term in search_terms)

        if matches:
            filtered_events.append(event)

    return filtered_events


@mcp.tool(
    description="Retrieves detailed information about a specific calendar event by its ID. Returns comprehensive event details including attendees, location, and timestamps. Automatically detects timezone inconsistencies."
)
def get_event(
    event_id: str = Field(
        ..., description="The unique identifier of the event to retrieve."
    ),
    calendar_id: str = Field(
        "primary",
        description="The ID or name of the calendar containing the event. Use 'list_calendars' to see available options. Defaults to the user's primary calendar.",
    ),
) -> CalendarEvent:
    """Get detailed information about a specific event."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)
    event = service.events().get(calendarId=resolved_id, eventId=event_id).execute()

    if _has_timezone_inconsistency(event):
        print(
            f"⚠️  Timezone inconsistency detected in event '{event.get('summary', 'Unknown')}'. "
            f"To fix: update_event(event_id='{event_id}', calendar_id='{calendar_id}', normalize_timezone=True)"
        )

    return _build_event_model(event)


@mcp.tool(
    description="Creates a new event. Supports natural language datetimes (e.g., 'tomorrow at 2pm') and mixed timezones."
)
def create_event(
    summary: str = Field(..., description="The title or summary for the new event."),
    start_datetime: str = Field(
        ...,
        description="The start time of the event. Supports natural language (e.g., 'tomorrow at 2pm').",
    ),
    end_datetime: str = Field(
        ...,
        description="The end time of the event. Supports natural language (e.g., 'in 3 hours').",
    ),
    description: str = Field(
        "", description="A detailed description or notes for the event."
    ),
    location: str = Field(
        "", description="The physical location or meeting link for the event."
    ),
    calendar_id: str = Field(
        ...,
        description="The ID or name of the calendar to add the event to. Use 'list_calendars' to see available options. Required parameter - no default.",
    ),
    start_timezone: str = Field(
        "",
        description="Explicit IANA timezone for the start time (e.g., 'America/Los_Angeles'). Overrides calendar's default.",
    ),
    end_timezone: str = Field(
        "",
        description="Explicit IANA timezone for the end time. Essential for events spanning timezones, like flights.",
    ),
    attendees: list[str] = Field(
        default_factory=list,
        description="A list of attendee email addresses to invite to the event.",
    ),
) -> CreatedEventResult:
    """Create a new calendar event with intelligent datetime parsing and flexible timezone handling.

    Examples:
    - Natural language: start_datetime="tomorrow at 2pm", end_datetime="tomorrow at 3pm"
    - Mixed timezones: start_datetime="10:00am", start_timezone="America/Los_Angeles",
                      end_datetime="6:30pm", end_timezone="America/New_York"
    - ISO format: start_datetime="2024-07-15T14:00:00-08:00" (preserves timezone)
    - Relative time: start_datetime="in 2 hours", end_datetime="in 3 hours"
    """
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    # Get calendar's default timezone as fallback context
    calendar_tz = _get_calendar_timezone(service, resolved_id)

    # Prepare start datetime with smart timezone handling
    if start_timezone:
        # Use explicit timezone for start time
        start_body = _prepare_event_datetime(start_datetime, start_timezone)
    else:
        # Use calendar timezone as context for naive datetimes
        start_body = _prepare_event_datetime(start_datetime, calendar_tz)

    # Prepare end datetime with smart timezone handling
    if end_timezone:
        # Use explicit timezone for end time
        end_body = _prepare_event_datetime(end_datetime, end_timezone)
    else:
        # Use calendar timezone as context for naive datetimes
        end_body = _prepare_event_datetime(end_datetime, calendar_tz)

    event_body = {
        "summary": summary,
        "description": description or "",
        "location": location or "",
        "start": start_body,
        "end": end_body,
    }

    if attendees:
        event_body["attendees"] = [{"email": email} for email in attendees]

    created_event = (
        service.events().insert(calendarId=resolved_id, body=event_body).execute()
    )

    start = created_event.get("start", {})
    time_str = start.get("dateTime", start.get("date", "N/A"))
    tz_str = start.get("timeZone")
    display_time = f"{time_str} ({tz_str})" if tz_str else time_str

    return CreatedEventResult(
        status="Event created successfully!",
        event_id=created_event["id"],
        title=created_event["summary"],
        time=display_time,
        calendar=calendar_id,
        attendees=[att.get("email") for att in created_event.get("attendees", [])],
    )


@mcp.tool(
    description="Updates an event. Supports natural language rescheduling and can fix timezone inconsistencies."
)
def update_event(
    event_id: str = Field(
        ..., description="The unique identifier of the event to update."
    ),
    calendar_id: str = Field(
        "primary",
        description="The calendar where the event is located. Use 'list_calendars' to see available options. Defaults to the primary calendar.",
    ),
    summary: str = Field(
        "", description="New title for the event. If empty, the summary is not changed."
    ),
    start_datetime: str = Field(
        "",
        description="New start time for the event. Supports natural language. If empty, not changed.",
    ),
    end_datetime: str = Field(
        "",
        description="New end time for the event. Supports natural language. If empty, not changed.",
    ),
    description: str = Field(
        "", description="New description for the event. If empty, not changed."
    ),
    location: str = Field(
        "", description="New location for the event. If empty, not changed."
    ),
    start_timezone: str = Field(
        "",
        description="New IANA timezone for the start time. If empty, preserves existing timezone.",
    ),
    end_timezone: str = Field(
        "",
        description="New IANA timezone for the end time. If empty, preserves existing timezone.",
    ),
    normalize_timezone: bool = Field(
        False,
        description="Set to True to fix timezone inconsistencies (e.g., UTC time with a non-UTC timezone label) on the event.",
    ),
) -> UpdateEventResult:
    """Update an existing event, with automatic timezone handling for new times.

    Examples:
    - Natural language: start_datetime="tomorrow at 3pm", end_datetime="tomorrow at 4pm"
    - Reschedule with timezone: start_datetime="10am", start_timezone="Europe/London"
    - Relative time: start_datetime="in 1 hour" (keeps existing end time)
    - Mixed timezones: start_timezone="America/Los_Angeles", end_timezone="America/New_York"
    """
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)
    update_body = {}
    updated_fields = []

    current_event = None
    if normalize_timezone or start_datetime.strip() or end_datetime.strip():
        current_event = (
            service.events().get(calendarId=resolved_id, eventId=event_id).execute()
        )

    if normalize_timezone and current_event:
        normalization_patch = _get_normalization_patch(current_event)
        update_body.update(normalization_patch)
        if normalization_patch:
            updated_fields.append("timezone_normalization")

    # Build update from provided arguments
    if summary.strip():
        update_body["summary"] = summary
        updated_fields.append("summary")
    if description is not None:  # Allow clearing the description
        update_body["description"] = description
        updated_fields.append("description")
    if location is not None:  # Allow clearing the location
        update_body["location"] = location
        updated_fields.append("location")

    # If start or end times are being updated, use intelligent preparation logic
    if start_datetime.strip() or end_datetime.strip():
        # Get fallback timezone context
        calendar_tz = _get_calendar_timezone(service, resolved_id)
        existing_start_tz = (
            current_event.get("start", {}).get("timeZone") or calendar_tz
        )
        existing_end_tz = current_event.get("end", {}).get("timeZone") or calendar_tz

        if start_datetime.strip():
            # Use explicit timezone or preserve existing event's start timezone
            target_tz = start_timezone or existing_start_tz
            update_body["start"] = _prepare_event_datetime(start_datetime, target_tz)
            updated_fields.append("start_datetime")

        if end_datetime.strip():
            # Use explicit timezone or preserve existing event's end timezone
            target_tz = end_timezone or existing_end_tz
            update_body["end"] = _prepare_event_datetime(end_datetime, target_tz)
            updated_fields.append("end_datetime")

    if not update_body:
        # Return a minimal result for no updates case
        return UpdateEventResult(
            event_id=event_id,
            html_link="",
            updated_fields=[],
            message="No updates specified. Nothing to do.",
        )

    updated_event = (
        service.events()
        .patch(calendarId=resolved_id, eventId=event_id, body=update_body)
        .execute()
    )

    result_msg = f"Event (ID: {updated_event['id']}) updated successfully."
    if updated_fields:
        result_msg += f" Modified fields: {', '.join(updated_fields)}"
    if normalize_timezone and ("start" in update_body or "end" in update_body):
        result_msg += " (timezone inconsistency normalized)"

    return UpdateEventResult(
        event_id=updated_event["id"],
        html_link=updated_event.get("htmlLink", ""),
        updated_fields=updated_fields,
        message=result_msg,
    )


@mcp.tool(
    description="Deletes a calendar event permanently by event ID. WARNING: This action is irreversible. Returns confirmation of deletion."
)
def delete_event(
    event_id: str = Field(
        ..., description="The unique identifier of the event to be permanently deleted."
    ),
    calendar_id: str = Field(
        "primary",
        description="The calendar where the event is located. Use 'list_calendars' to see available options. Defaults to the primary calendar.",
    ),
) -> str:
    """Delete a calendar event. Trusts the provided event_id."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    service.events().delete(calendarId=resolved_id, eventId=event_id).execute()
    return f"Event (ID: {event_id}) has been permanently deleted."


@mcp.tool(
    description="Moves a calendar event from one calendar to another. This is the proper way to transfer events between calendars, preserving event metadata and attendee information."
)
def move_event(
    event_id: str = Field(
        ..., description="The unique identifier of the event to move."
    ),
    source_calendar_id: str = Field(
        "primary",
        description="The ID or name of the calendar the event is currently in. Use 'list_calendars' to see available options. Defaults to primary.",
    ),
    destination_calendar_id: str = Field(
        "primary",
        description="The ID or name of the calendar to move the event to. Use 'list_calendars' to see available options. Defaults to primary.",
    ),
) -> str:
    """Move an event from one calendar to another using the Google Calendar API move endpoint."""
    service = _get_calendar_service()
    source_resolved_id = _resolve_calendar_id(source_calendar_id, service)
    dest_resolved_id = _resolve_calendar_id(destination_calendar_id, service)

    # Use the Google Calendar API's move endpoint
    moved_event = (
        service.events()
        .move(
            calendarId=source_resolved_id,
            eventId=event_id,
            destination=dest_resolved_id,
        )
        .execute()
    )

    return f"Event (ID: {moved_event['id']}) moved successfully from '{source_calendar_id}' to '{destination_calendar_id}'."


@mcp.tool(
    description="Lists all calendars accessible to the authenticated user with their IDs, access levels, and colors. Use this to discover calendar IDs before using other calendar tools."
)
def list_calendars() -> list[CalendarInfo]:
    """List all accessible calendars."""
    service = _get_calendar_service()

    calendar_list = service.calendarList().list().execute()
    calendars = calendar_list.get("items", [])

    return [
        CalendarInfo(
            id=cal["id"],
            summary=cal.get("summary", "Unknown"),
            accessRole=cal.get("accessRole", "unknown"),
            colorId=cal.get("colorId", "default"),
        )
        for cal in calendars
    ]


@mcp.tool(
    description="Finds available free time slots within a calendar for scheduling meetings. Defaults to next 7 days if no date range specified. Returns up to 20 slots, checking every 30 minutes. Set `work_hours_only=False` to include evenings/weekends."
)
def find_time(
    calendar_id: str = Field(
        "primary",
        description="The ID or name of the calendar to search for free time. Use 'list_calendars' to see available options. Defaults to primary.",
    ),
    start_date: str = Field(
        "", description="The start date (YYYY-MM-DD) for the search. Defaults to now."
    ),
    end_date: str = Field(
        "",
        description="The end date (YYYY-MM-DD) for the search. Defaults to 7 days from the start date.",
    ),
    duration_minutes: int = Field(
        60, description="The desired duration of the free time slot in minutes."
    ),
    work_hours_only: bool = Field(
        True, description="If True, only searches for slots between 9 AM and 5 PM."
    ),
) -> list[FreeTimeSlot]:
    """Find free time slots in a calendar."""
    service = _get_calendar_service()
    resolved_id = _resolve_calendar_id(calendar_id, service)

    start_dt = datetime.now() if not start_date else datetime.fromisoformat(start_date)

    if not end_date:
        end_dt = start_dt + timedelta(days=7)
    else:
        end_dt = datetime.fromisoformat(end_date)

    freebusy_request = {
        "timeMin": _parse_datetime_to_utc(start_dt.isoformat()),
        "timeMax": _parse_datetime_to_utc(end_dt.isoformat()),
        "items": [{"id": resolved_id}],
    }

    freebusy_result = service.freebusy().query(body=freebusy_request).execute()
    busy_times = freebusy_result["calendars"][resolved_id].get("busy", [])

    slots = []
    if start_dt.tzinfo:
        current = start_dt.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        current = start_dt

    if end_dt.tzinfo:
        end_dt_utc = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        end_dt_utc = end_dt

    slot_duration = timedelta(minutes=duration_minutes)

    while current + slot_duration <= end_dt_utc:
        if work_hours_only and (current.hour < 9 or current.hour >= 17):
            current += timedelta(hours=1)
            continue

        slot_end = current + slot_duration

        is_free = True
        for busy in busy_times:
            busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
            busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))

            if busy_start.tzinfo:
                busy_start = busy_start.astimezone(timezone.utc).replace(tzinfo=None)
            if busy_end.tzinfo:
                busy_end = busy_end.astimezone(timezone.utc).replace(tzinfo=None)

            if current < busy_end and slot_end > busy_start:
                is_free = False
                break

        if is_free:
            slots.append((current, slot_end))

        current += timedelta(minutes=30)

    if not slots:
        return []

    # Convert to FreeTimeSlot objects
    free_slots = []
    for start_time, end_time in slots[:20]:  # Limit to first 20 slots
        free_slots.append(
            FreeTimeSlot(
                start=start_time.strftime("%Y-%m-%d %H:%M"),
                end=end_time.strftime("%Y-%m-%d %H:%M"),
                duration_minutes=duration_minutes,
            )
        )

    return free_slots


@mcp.tool(
    description="Searches for events in a date range. Filter by text, specific fields ('search_fields'), and case sensitivity."
)
def search_events(
    search_text: str = Field(
        "",
        description="Text to search for. If empty, lists all events in the date range. Can be a simple string or use Google Calendar's advanced search operators.",
    ),
    calendar_id: str = Field(
        "all",
        description="ID or name of the calendar to search. Use 'all' to search every accessible calendar, or use 'list_calendars' to see available options.",
    ),
    start_date: str = Field(
        "",
        description="The start date (YYYY-MM-DD) for the search range. Defaults to today.",
    ),
    end_date: str = Field(
        "",
        description="The end date (YYYY-MM-DD) for the search range. Defaults to 7 days from start (or 365 if search_text is provided).",
    ),
    max_results: int = Field(
        100, description="The maximum number of events to return per calendar."
    ),
    search_fields: list[str] = Field(
        default_factory=list,
        description="Client-side filter: specific fields to search within (e.g., 'summary', 'description', 'attendees'). If empty, defaults to API search.",
    ),
    case_sensitive: bool = Field(
        False,
        description="Client-side filter: If True, the search_text match will be case-sensitive.",
    ),
    match_all_terms: bool = Field(
        True,
        description="Client-side filter: If True (AND logic), all words in search_text must match. If False (OR logic), any can match.",
    ),
) -> list[CalendarEvent]:
    """Advanced hybrid search for calendar events."""
    service = _get_calendar_service()

    if not start_date:
        start_date = _parse_datetime_to_utc("")
    else:
        start_date = _parse_datetime_to_utc(start_date)

    if not end_date:
        days = 7 if not search_text else 365
        end_dt = datetime.now(timezone.utc) + timedelta(days=days)
        end_date = end_dt.isoformat().replace("+00:00", "Z")
    else:
        if "T" not in end_date:
            end_date = end_date + "T23:59:59Z"
        else:
            end_date = _parse_datetime_to_utc(end_date)

    events_list = []

    if calendar_id == "all":
        calendar_list = service.calendarList().list().execute()

        for calendar in calendar_list.get("items", []):
            cal_id = calendar["id"]

            params = {
                "calendarId": cal_id,
                "timeMin": start_date,
                "timeMax": end_date,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            }
            if search_text:
                params["q"] = search_text
            events_result = service.events().list(**params).execute()

            cal_events = events_result.get("items", [])
            for event in cal_events:
                event["calendar_name"] = calendar.get("summary", cal_id)
            events_list.extend(cal_events)
    else:
        resolved_id = _resolve_calendar_id(calendar_id, service)

        params = {
            "calendarId": resolved_id,
            "timeMin": start_date,
            "timeMax": end_date,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if search_text:
            params["q"] = search_text
        events_result = service.events().list(**params).execute()
        events_list = events_result.get("items", [])

    if search_fields or case_sensitive or not match_all_terms:
        filtered_events = _client_side_filter(
            events_list,
            search_text=search_text,
            search_fields=search_fields,
            case_sensitive=case_sensitive,
            match_all_terms=match_all_terms,
        )
    else:
        filtered_events = events_list

    if not filtered_events:
        return []

    filtered_events.sort(
        key=lambda x: x.get("start", {}).get(
            "dateTime", x.get("start", {}).get("date", "")
        )
    )

    # Convert filtered events to CalendarEvent objects
    return [_build_event_model(event) for event in filtered_events]


@mcp.tool(
    description="Checks the status of the Google Calendar server and API connectivity. Returns version info and available functions."
)
def server_info() -> ServerInfo:
    """Get server status and Google Calendar API connection info."""
    service = _get_calendar_service()

    calendar_list = service.calendarList().list(maxResults=1).execute()

    return ServerInfo(
        name="Google Calendar Tool",
        version="1.9.4",
        status="active",
        capabilities=[
            "search_events",
            "get_event",
            "create_event",
            "update_event",
            "delete_event",
            "move_event",
            "list_calendars",
            "find_time",
            "server_info",
        ],
        dependencies={
            "google_calendar_api": "active",
            "calendars_accessible": str(len(calendar_list.get("items", []))),
        },
    )

```

`src/mcp_handley_lab/google_maps/__init__.py`:

```py
"""Google Maps MCP tool for directions and routing."""

```

`src/mcp_handley_lab/google_maps/tool.py`:

```py
"""Google Maps tool for directions and routing via MCP."""

from datetime import datetime, timezone
from typing import Any, Literal

import googlemaps
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.shared.models import ServerInfo


class TransitDetails(BaseModel):
    """Transit-specific information for a step."""

    departure_time: datetime = Field(..., description="The scheduled departure time for this transit step.")
    arrival_time: datetime = Field(..., description="The scheduled arrival time for this transit step.")
    line_name: str = Field(..., description="The full name of the transit line (e.g., 'Red Line', 'Route 101').")
    line_short_name: str = Field(default="", description="The short name or number of the transit line.")
    vehicle_type: str = Field(..., description="The type of transit vehicle (e.g., 'BUS', 'SUBWAY', 'TRAIN').")
    headsign: str = Field(default="", description="The destination sign displayed on the transit vehicle.")
    num_stops: int = Field(..., description="The number of stops between boarding and alighting.")


class DirectionStep(BaseModel):
    """A single step in a route."""

    instruction: str = Field(..., description="Human-readable navigation instruction for this step.")
    distance: str = Field(..., description="The distance for this step (e.g., '0.5 km', '500 ft').")
    duration: str = Field(..., description="The estimated time for this step (e.g., '5 mins', '2 hours').")
    start_location: dict[str, float] = Field(..., description="The latitude and longitude coordinates where this step begins.")
    end_location: dict[str, float] = Field(..., description="The latitude and longitude coordinates where this step ends.")
    travel_mode: str = Field(default="", description="The mode of transport for this step (e.g., 'WALKING', 'DRIVING', 'TRANSIT').")
    transit_details: TransitDetails | None = Field(default=None, description="Additional details if this step involves public transit.")


class DirectionLeg(BaseModel):
    """A leg of a route (origin to destination or waypoint)."""

    distance: str = Field(..., description="The total distance for this leg of the journey.")
    duration: str = Field(..., description="The estimated total time for this leg of the journey.")
    start_address: str = Field(..., description="The human-readable address where this leg begins.")
    end_address: str = Field(..., description="The human-readable address where this leg ends.")
    steps: list[DirectionStep] = Field(..., description="The individual navigation steps that make up this leg.")


class DirectionRoute(BaseModel):
    """A complete route with all legs and steps."""

    summary: str = Field(..., description="A short textual description of the route (e.g., 'via I-95 N').")
    legs: list[DirectionLeg] = Field(..., description="The individual legs that make up this complete route.")
    distance: str = Field(..., description="The total distance for the entire route.")
    duration: str = Field(..., description="The estimated total time for the entire route.")
    polyline: str = Field(..., description="An encoded polyline representation of the route path.")
    warnings: list[str] = Field(default_factory=list, description="Any warnings about the route (e.g., tolls, traffic).")


class DirectionsResult(BaseModel):
    """Result of a directions request."""

    routes: list[DirectionRoute] = Field(..., description="A list of possible routes from origin to destination.")
    status: str = Field(..., description="The status of the API request (e.g., 'OK', 'ZERO_RESULTS').")
    origin: str = Field(..., description="The address or coordinates of the starting point.")
    destination: str = Field(..., description="The address or coordinates of the ending point.")
    mode: str = Field(..., description="The travel mode used for the directions (e.g., 'driving', 'transit').")
    departure_time: str = Field(default="", description="The requested departure time as an ISO 8601 string, if provided.")
    maps_url: str = Field(default="", description="A direct URL to Google Maps with the requested route.")


mcp = FastMCP("Google Maps Tool")


def _get_maps_client():
    """Get authenticated Google Maps client."""
    return googlemaps.Client(key=settings.google_maps_api_key)


def _generate_maps_url(
    origin: str,
    destination: str,
    mode: str,
    waypoints: list[str] = None,
    departure_time: str = "",
    arrival_time: str = "",
    avoid: list[str] = None,
    transit_mode: list[str] = None,
    transit_routing_preference: str = "",
    api_result: dict = None,
) -> str:
    """Generate a Google Maps URL for the directions using recommended parameters."""
    import urllib.parse
    from datetime import datetime

    # For transit mode with timing and API result, generate the complex format
    if mode == "transit" and api_result and (departure_time or arrival_time):
        # Extract coordinates from API result
        first_route = api_result[0]
        first_leg = first_route["legs"][0]
        origin_lat = first_leg["start_location"]["lat"]
        origin_lng = first_leg["start_location"]["lng"]
        dest_lat = first_leg["end_location"]["lat"]
        dest_lng = first_leg["end_location"]["lng"]

        # Calculate center point for map view
        center_lat = (origin_lat + dest_lat) / 2
        center_lng = (origin_lng + dest_lng) / 2

        # Generate fake place IDs (Google Maps format)
        origin_place_id = "0x47d8704fbb7e3d95:0xc59170db564833be"
        dest_place_id = "0x48761bccc506725f:0x3bb9e6e4b6391e8e"

        # Determine timestamp and time type
        if arrival_time:
            dt = datetime.fromisoformat(arrival_time.replace("Z", "+00:00"))
            timestamp = str(int(dt.timestamp()))
            time_type = "7e2"  # arrive by
        else:
            dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
            timestamp = str(int(dt.timestamp()))
            time_type = "7e1"  # depart at

        # Build the complex URL format
        origin_encoded = urllib.parse.quote(origin)
        dest_encoded = urllib.parse.quote(destination)

        return (
            f"https://www.google.com/maps/dir/{origin_encoded}/"
            f"{dest_encoded}/@{center_lat},{center_lng},9z/"
            f"data=!3m1!4b1!4m18!4m17!1m5!1m1!1s{origin_place_id}!2m2!"
            f"1d{origin_lng}!2d{origin_lat}!1m5!1m1!1s{dest_place_id}!2m2!"
            f"1d{dest_lng}!2d{dest_lat}!2m3!6e1!{time_type}!8j{timestamp}!3e3"
        )

    # Fallback to simple API format
    base_url = "https://www.google.com/maps/dir/"

    # Parameters
    params = {
        "api": "1",
        "origin": origin,
        "destination": destination,
        "travelmode": mode,
    }

    # Add waypoints if provided, separated by the pipe character
    if waypoints:
        params["waypoints"] = "|".join(waypoints)

    # Add departure or arrival time if provided (for transit mode)
    if mode == "transit":
        if departure_time:
            dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
            params["departure_time"] = str(int(dt.timestamp()))
        elif arrival_time:
            dt = datetime.fromisoformat(arrival_time.replace("Z", "+00:00"))
            params["arrival_time"] = str(int(dt.timestamp()))

        # Add transit mode preferences
        if transit_mode:
            params["transit_mode"] = "|".join(transit_mode)

        # Add transit routing preference
        if transit_routing_preference:
            params["transit_routing_preference"] = transit_routing_preference

    # Add avoid parameters for driving mode
    if mode == "driving" and avoid:
        params["avoid"] = ",".join(avoid)

    # URL encode the parameters and construct the final URL
    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    return url


def _parse_step(step: dict[str, Any]) -> DirectionStep:
    """Parse a direction step from API response."""
    transit_details = None
    travel_mode = step.get("travel_mode", "")

    # Extract transit details if this is a transit step
    if travel_mode == "TRANSIT" and "transit_details" in step:
        transit_data = step["transit_details"]

        # Convert Unix timestamps to datetime objects (using UTC then converting to local)
        departure_dt = datetime.fromtimestamp(
            transit_data["departure_time"]["value"], tz=timezone.utc
        )
        arrival_dt = datetime.fromtimestamp(
            transit_data["arrival_time"]["value"], tz=timezone.utc
        )

        line_data = transit_data.get("line", {})

        transit_details = TransitDetails(
            departure_time=departure_dt,
            arrival_time=arrival_dt,
            line_name=line_data.get("name", ""),
            line_short_name=line_data.get("short_name", ""),
            vehicle_type=line_data.get("vehicle", {}).get("type", ""),
            headsign=transit_data.get("headsign", ""),
            num_stops=transit_data.get("num_stops", 0),
        )

    return DirectionStep(
        instruction=step["html_instructions"],
        distance=step["distance"]["text"],
        duration=step["duration"]["text"],
        start_location=step["start_location"],
        end_location=step["end_location"],
        travel_mode=travel_mode,
        transit_details=transit_details,
    )


def _parse_leg(leg: dict[str, Any]) -> DirectionLeg:
    """Parse a direction leg from API response."""
    return DirectionLeg(
        distance=leg["distance"]["text"],
        duration=leg["duration"]["text"],
        start_address=leg["start_address"],
        end_address=leg["end_address"],
        steps=[_parse_step(step) for step in leg["steps"]],
    )


def _parse_route(route: dict[str, Any]) -> DirectionRoute:
    """Parse a route from API response."""
    legs = [_parse_leg(leg) for leg in route["legs"]]

    # Calculate total distance and duration
    total_distance = sum(leg["distance"]["value"] for leg in route["legs"])
    total_duration = sum(leg["duration"]["value"] for leg in route["legs"])

    # Convert to human-readable format
    distance_text = f"{total_distance / 1000:.1f} km"
    duration_text = f"{total_duration // 60} min"

    return DirectionRoute(
        summary=route["summary"],
        legs=legs,
        distance=distance_text,
        duration=duration_text,
        polyline=route["overview_polyline"]["points"],
        warnings=route.get("warnings", []),
    )


@mcp.tool(
    description="Gets directions between an origin and destination, supporting multiple travel modes, waypoints, and route preferences. For transit, supports specific transport modes and routing preferences."
)
def get_directions(
    origin: str = Field(..., description="The starting address, place name, or coordinates (e.g., '1600 Amphitheatre Parkway, Mountain View, CA')."),
    destination: str = Field(..., description="The ending address, place name, or coordinates (e.g., 'San Francisco, CA')."),
    mode: Literal["driving", "walking", "bicycling", "transit"] = Field("driving", description="The mode of transport to use for the directions."),
    departure_time: str = Field("", description="The desired departure time as an ISO 8601 UTC string (e.g., '2024-08-15T09:00:00Z'). Cannot be used with arrival_time."),
    arrival_time: str = Field("", description="The desired arrival time as an ISO 8601 UTC string (e.g., '2024-08-15T17:00:00Z'). Cannot be used with departure_time."),
    avoid: list[Literal["tolls", "highways", "ferries"]] = Field(default_factory=list, description="A list of route features to avoid (e.g., 'tolls', 'highways'). Only for 'driving' mode."),
    alternatives: bool = Field(False, description="If True, requests that alternative routes be provided in the response."),
    waypoints: list[str] = Field(default_factory=list, description="A list of addresses or coordinates to route through between the origin and destination."),
    transit_mode: list[Literal["bus", "subway", "train", "tram", "rail"]] = Field(default_factory=list, description="Preferred modes of public transit. Only for 'transit' mode."),
    transit_routing_preference: Literal["", "less_walking", "fewer_transfers"] = Field("", description="Specifies preferences for transit routes, such as fewer transfers or less walking. Only for 'transit' mode."),
) -> DirectionsResult:
    gmaps = _get_maps_client()

    # Parse departure/arrival time if provided
    departure_dt = None
    arrival_dt = None
    if departure_time:
        departure_dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
    if arrival_time:
        arrival_dt = datetime.fromisoformat(arrival_time.replace("Z", "+00:00"))

    # The avoid parameter is already a list, no need to process it

    # Make API request
    result = gmaps.directions(
        origin=origin,
        destination=destination,
        mode=mode,
        departure_time=departure_dt,
        arrival_time=arrival_dt,
        avoid=avoid if avoid else None,
        alternatives=alternatives,
        waypoints=waypoints if waypoints else None,
        transit_mode=transit_mode if transit_mode else None,
        transit_routing_preference=transit_routing_preference
        if transit_routing_preference
        else None,
    )

    if not result:
        return DirectionsResult(
            routes=[],
            status="NO_ROUTES_FOUND",
            origin=origin,
            destination=destination,
            mode=mode,
            departure_time=departure_time,
            maps_url="",
        )

    # Parse routes
    routes = [_parse_route(route) for route in result]

    # Generate Google Maps URL
    maps_url = _generate_maps_url(
        origin,
        destination,
        mode,
        waypoints,
        departure_time,
        arrival_time,
        avoid,
        transit_mode,
        transit_routing_preference,
        api_result=result,
    )

    return DirectionsResult(
        routes=routes,
        status="OK",
        origin=origin,
        destination=destination,
        mode=mode,
        departure_time=departure_time,
        maps_url=maps_url,
    )


@mcp.tool(description="Get Google Maps Tool server information and capabilities.")
def server_info() -> ServerInfo:
    return ServerInfo(
        name="Google Maps Tool",
        version="0.4.0",
        status="active",
        capabilities=[
            "get_directions",
            "server_info",
            "directions",
            "multiple_transport_modes",
            "waypoint_support",
            "traffic_aware_routing",
            "alternative_routes",
        ],
        dependencies={"googlemaps": "4.0.0+", "pydantic": "2.0.0+", "mcp": "1.0.0+"},
    )

```

`src/mcp_handley_lab/llm/agent_utils.py`:

```py
"""Shared utility functions for agent management - not exposed as MCP tools."""

from mcp_handley_lab.llm.memory import memory_manager


def create_agent(agent_name: str, system_prompt: str = "") -> str:
    """Create a new agent with optional system prompt."""
    memory_manager.create_agent(agent_name, system_prompt)
    system_prompt_info = (
        f" with system prompt: {system_prompt}" if system_prompt else ""
    )
    return f"✅ Agent '{agent_name}' created successfully{system_prompt_info}!"


def list_agents() -> str:
    """List all agents with their statistics."""
    agents = memory_manager.list_agents()

    if not agents:
        return "No agents found. Create an agent with create_agent()."

    result = "📋 **Agent List**\n\n"
    for agent in agents:
        stats = agent.get_stats()
        result += f"**{stats['name']}**\n"
        result += f"- Created: {stats['created_at'][:10]}\n"
        result += f"- Messages: {stats['message_count']}\n"
        result += f"- Tokens: {stats['total_tokens']:,}\n"
        result += f"- Cost: ${stats['total_cost']:.4f}\n"
        if stats["system_prompt"]:
            result += f"- System Prompt: {stats['system_prompt']}\n"
        result += "\n"

    return result


def agent_stats(agent_name: str) -> str:
    """Get detailed statistics for a specific agent."""
    agent = memory_manager.get_agent(agent_name)
    if not agent:
        raise ValueError(f"Agent '{agent_name}' not found")

    stats = agent.get_stats()

    result = f"📊 **Agent Statistics: {agent_name}**\n\n"
    result += "**Overview:**\n"
    result += f"- Created: {stats['created_at']}\n"
    result += f"- Total Messages: {stats['message_count']}\n"
    result += f"- Total Tokens: {stats['total_tokens']:,}\n"
    result += f"- Total Cost: ${stats['total_cost']:.4f}\n"

    if stats["system_prompt"]:
        result += f"- System Prompt: {stats['system_prompt']}\n"

    # Recent message history (last 5)
    if agent.messages:
        result += "\n**Recent Messages:**\n"
        recent_messages = agent.messages[-5:]
        for i, msg in enumerate(recent_messages, 1):
            role = msg.role
            content = msg.content

            # Truncate long messages
            if len(content) > 100:
                content = content[:97] + "..."

            result += f"{i}. **{role.title()}:** {content}\n"

    return result


def clear_agent(agent_name: str) -> str:
    """Clear an agent's conversation history."""
    memory_manager.clear_agent_history(agent_name)
    return f"✅ Agent '{agent_name}' history cleared successfully!"


def delete_agent(agent_name: str) -> str:
    """Delete an agent permanently."""
    memory_manager.delete_agent(agent_name)
    return f"✅ Agent '{agent_name}' deleted permanently!"


def get_response(agent_name: str, index: int = -1) -> str:
    """Get a message from an agent's conversation history by index."""
    return memory_manager.get_response(agent_name, index)

```

`src/mcp_handley_lab/llm/claude/__init__.py`:

```py
"""Claude LLM integration for MCP Framework."""

```

`src/mcp_handley_lab/llm/claude/tool.py`:

```py
"""Claude LLM tool for AI interactions via MCP."""

from typing import Any

from anthropic import Anthropic
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    build_server_info,
    load_provider_models,
    resolve_files_for_llm,
    resolve_images_for_multimodal_prompt,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.model_loader import (
    get_structured_model_listing,
)
from mcp_handley_lab.llm.shared import process_llm_request
from mcp_handley_lab.shared.models import LLMResult, ModelListing, ServerInfo

mcp = FastMCP("Claude Tool")

# Configure Claude client - fail fast if API key is invalid/missing
client = Anthropic(api_key=settings.anthropic_api_key)

# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL, _get_model_config = load_provider_models("claude")


def _resolve_model_alias(model: str) -> str:
    """Resolve model aliases to full model names."""
    aliases = {
        "sonnet": "claude-3-5-sonnet-20241022",
        "opus": "claude-3-opus-20240229",
        "haiku": "claude-3-5-haiku-20241022",
    }
    return aliases.get(model, model)


def _convert_history_to_claude_format(
    history: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Convert generic history to Claude's expected format.

    Claude requires alternating user/assistant messages. This function validates
    and fixes the sequence if needed.
    """
    if not history:
        return []

    claude_history = []
    last_role = None

    for message in history:
        role = message["role"]
        content = message["content"]

        # Skip system messages (handled separately in Claude)
        if role == "system":
            continue

        # If we have consecutive messages from the same role, merge them
        if role == last_role and claude_history:
            # Merge with previous message
            claude_history[-1]["content"] += "\n\n" + content
        else:
            # Add as new message
            claude_history.append({"role": role, "content": content})
            last_role = role

    # Ensure history starts with user message (Claude requirement)
    if claude_history and claude_history[0]["role"] != "user":
        # Prepend a placeholder user message if needed
        claude_history.insert(
            0, {"role": "user", "content": "[Previous conversation context]"}
        )

    return claude_history


def _resolve_files(files: list[str]) -> LLMResult:
    """Resolve file inputs to text content for Claude.

    Claude has a large context window (200K tokens), so we can include most files directly.
    Returns a string with all file contents concatenated.
    """
    if not files:
        return ""

    # Use shared file resolution with larger max size for Claude's big context
    file_contents = resolve_files_for_llm(files, max_file_size=20 * 1024 * 1024)  # 20MB
    return "\n\n".join(file_contents)


def _resolve_images_to_content_blocks(
    images: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Resolve image inputs to Claude content blocks."""
    if images is None:
        images = []
    # Use standardized image processing
    _, image_blocks = resolve_images_for_multimodal_prompt("", images)

    # Convert to Claude's specific format
    claude_image_blocks = []
    for image_block in image_blocks:
        claude_image_blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_block["mime_type"],
                    "data": image_block["data"],
                },
            }
        )

    return claude_image_blocks


def _claude_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Claude-specific text generation function for the shared processor."""
    # Extract Claude-specific parameters
    temperature = kwargs.get("temperature", 1.0)
    files = kwargs.get("files")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Get model configuration
    resolved_model = _resolve_model_alias(model)
    model_config = _get_model_config(resolved_model)
    max_output = model_config["output_tokens"]
    output_tokens = (
        min(max_output_tokens, max_output) if max_output_tokens > 0 else max_output
    )

    # Resolve file contents
    file_content = _resolve_files(files)

    # Build user content
    user_content = prompt
    if file_content:
        user_content += "\n\n" + file_content

    # Convert history to Claude format
    claude_history = _convert_history_to_claude_format(history)

    # Add current user message
    claude_history.append({"role": "user", "content": user_content})

    # Resolve model alias and prepare request parameters
    resolved_model = _resolve_model_alias(model)
    request_params = {
        "model": resolved_model,
        "messages": claude_history,
        "max_tokens": output_tokens,
        "temperature": temperature,
        "timeout": 599,
    }

    # Add system instruction if provided
    if system_instruction:
        request_params["system"] = system_instruction

    # Make API call
    response = client.messages.create(**request_params)

    if not response.content or not response.content[0].text:
        raise RuntimeError("No response text generated")

    # Extract additional Claude metadata
    return {
        "text": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "finish_reason": response.stop_reason,
        "avg_logprobs": 0.0,  # Claude doesn't provide logprobs
        "model_version": response.model,
        "response_id": response.id,
        "stop_sequence": response.stop_sequence or "",
        "cache_creation_input_tokens": response.usage.cache_creation_input_tokens or 0,
        "cache_read_input_tokens": response.usage.cache_read_input_tokens or 0,
        "service_tier": response.usage.service_tier or "",
    }


def _claude_image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Claude-specific image analysis function for the shared processor."""
    # Extract image analysis specific parameters
    images = kwargs.get("images", [])
    focus = kwargs.get("focus", "general")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Enhance prompt based on focus
    if focus != "general":
        prompt = f"Focus on {focus} aspects. {prompt}"

    # Get model configuration
    resolved_model = _resolve_model_alias(model)
    model_config = _get_model_config(resolved_model)
    max_output = model_config["output_tokens"]
    output_tokens = (
        min(max_output_tokens, max_output) if max_output_tokens > 0 else max_output
    )

    # Resolve images to content blocks
    image_blocks = _resolve_images_to_content_blocks(images)

    # Build content with text and images
    content_blocks = [{"type": "text", "text": prompt}] + image_blocks

    # Convert history to Claude format
    claude_history = _convert_history_to_claude_format(history)

    # Add current user message with images
    claude_history.append({"role": "user", "content": content_blocks})

    # Resolve model alias and prepare request parameters
    resolved_model = _resolve_model_alias(model)
    request_params = {
        "model": resolved_model,
        "messages": claude_history,
        "max_tokens": output_tokens,
        "temperature": 1.0,
        "timeout": 599,
    }

    # Add system instruction if provided
    if system_instruction:
        request_params["system"] = system_instruction

    # Make API call
    response = client.messages.create(**request_params)

    return {
        "text": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "finish_reason": response.stop_reason,
        "avg_logprobs": 0.0,  # Claude doesn't provide logprobs
        "model_version": response.model,
        "response_id": response.id,
        "stop_sequence": response.stop_sequence or "",
        "cache_creation_input_tokens": response.usage.cache_creation_input_tokens or 0,
        "cache_read_input_tokens": response.usage.cache_read_input_tokens or 0,
        "service_tier": response.usage.service_tier or "",
    }


@mcp.tool(
    description="Delegates a user query to external Anthropic Claude AI service on behalf of the human user. Returns Claude's verbatim response to assist the user. Use `agent_name` for separate conversation thread with Claude. For code reviews, use code2prompt first."
)
def ask(
    prompt: str = Field(
        ...,
        description="The user's question to delegate to external Claude AI service.",
    ),
    output_file: str = Field(
        "-",
        description="Path to save Claude's response. Use '-' to stream the output directly to stdout.",
    ),
    agent_name: str = Field(
        "session",
        description="Separate conversation thread with Claude AI service (distinct from your conversation with the user).",
    ),
    model: str = Field(
        DEFAULT_MODEL,
        description="The Claude model to use (e.g., 'claude-3-5-sonnet-20240620'). Can also use aliases like 'sonnet', 'opus', or 'haiku'.",
    ),
    temperature: float = Field(
        1.0,
        description="Controls randomness (0.0 to 2.0). Higher values like 1.0 are more creative, while lower values are more deterministic.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of file paths to be read and included as context in the prompt.",
    ),
    max_output_tokens: int = Field(
        0,
        description="Maximum number of tokens to generate in the response. If 0, uses the model's default maximum.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external Claude AI service. Remembered for this conversation thread.",
    ),
) -> LLMResult:
    """Ask Claude a question with optional persistent memory."""
    # Resolve model alias to full model name for consistent pricing
    resolved_model = _resolve_model_alias(model)
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=resolved_model,
        provider="claude",
        generation_func=_claude_generation_adapter,
        mcp_instance=mcp,
        temperature=temperature,
        files=files,
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
    )


@mcp.tool(
    description="Delegates image analysis to external Claude vision AI service on behalf of the user. Returns Claude's verbatim visual analysis to assist the user."
)
def analyze_image(
    prompt: str = Field(
        ...,
        description="The user's question about the images to delegate to external Claude vision AI service.",
    ),
    output_file: str = Field(
        "-",
        description="Path to save Claude's visual analysis. Use '-' to stream the output directly to stdout.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of image file paths to be analyzed along with the prompt.",
    ),
    focus: str = Field(
        "general",
        description="Specifies the focus of the analysis (e.g., 'text' to transcribe, 'objects' to identify).",
    ),
    model: str = Field(
        "claude-3-5-sonnet-20240620",
        description="The vision-capable Claude model to use for the analysis. Must be a model that supports image inputs.",
    ),
    agent_name: str = Field(
        "session",
        description="Separate conversation thread with Claude AI service (distinct from your conversation with the user).",
    ),
    max_output_tokens: int = Field(
        0,
        description="Maximum number of tokens to generate in the response. If 0, uses the model's default maximum.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external Claude AI service. Remembered for this conversation thread.",
    ),
) -> LLMResult:
    """Analyze images with Claude vision model."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="claude",
        generation_func=_claude_image_analysis_adapter,
        mcp_instance=mcp,
        images=files,
        focus=focus,
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
    )


@mcp.tool(
    description="Retrieves a comprehensive catalog of all available Claude models with pricing, capabilities, and performance information. Helps compare models and select the most suitable one for specific tasks or budget constraints."
)
def list_models() -> ModelListing:
    """List available Claude models with detailed information."""
    # Use structured model listing
    return get_structured_model_listing("claude")


@mcp.tool(
    description="Checks the status of the Claude Tool server and API connectivity. Returns connection status and list of available tools. Use this to verify the tool is operational before making other requests."
)
def server_info() -> ServerInfo:
    """Get server status and Claude configuration."""
    # Test API by making a simple request
    client.messages.create(
        model="claude-3-5-haiku-20241022",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10,
    )

    available_models = list(MODEL_CONFIGS.keys())

    return build_server_info(
        provider_name="Claude",
        available_models=available_models,
        memory_manager=memory_manager,
        vision_support=True,
        image_generation=False,
    )

```

`src/mcp_handley_lab/llm/common.py`:

```py
"""Shared utilities for LLM tools."""

import base64
import mimetypes
import os
from pathlib import Path

from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.shared.models import ServerInfo

# Enhance mimetypes with common text file types that might not be in the default database
# This runs once when the module is imported

# Programming languages and source code
mimetypes.add_type("text/x-c", ".c")
mimetypes.add_type("text/x-c++src", ".cpp")
mimetypes.add_type("text/x-java-source", ".java")
mimetypes.add_type("application/x-php", ".php")
mimetypes.add_type("application/sql", ".sql")
mimetypes.add_type("text/x-rustsrc", ".rs")
mimetypes.add_type("text/x-go", ".go")
mimetypes.add_type("text/x-ruby", ".rb")
mimetypes.add_type("text/x-perl", ".pl")
mimetypes.add_type("text/x-shellscript", ".sh")

# Documentation and markup
mimetypes.add_type("text/markdown", ".md")
mimetypes.add_type("text/markdown", ".markdown")
mimetypes.add_type("application/x-tex", ".tex")
mimetypes.add_type("text/x-diff", ".diff")
mimetypes.add_type("text/x-patch", ".patch")
mimetypes.add_type(
    "text/xml", ".xml"
)  # Ensure consistent XML MIME type across environments

# Configuration and structured data
mimetypes.add_type("text/x-yaml", ".yaml")
mimetypes.add_type("text/x-yaml", ".yml")
mimetypes.add_type("application/toml", ".toml")
mimetypes.add_type("text/plain", ".ini")
mimetypes.add_type("text/plain", ".conf")
mimetypes.add_type("text/plain", ".log")

# A set of application/* MIME types that are known to be text-based.
# This is used by is_text_file() to correctly identify text files that
# don't start with the 'text/' prefix (e.g., 'application/json').
# Note: text/* types are handled by the startswith('text/') check in is_text_file()
TEXT_BASED_APPLICATION_TYPES = {
    # Standard text-based application types
    "application/json",
    "application/javascript",
    "application/xhtml+xml",
    "application/rss+xml",
    "application/atom+xml",
    # Custom registered text-based application types (matching our add_type calls)
    "application/sql",
    "application/x-php",
    "application/x-tex",
    "application/toml",
}


def get_session_id(mcp_instance) -> str:
    """Get persistent session ID for this MCP server process."""
    context = mcp_instance.get_context()
    client_id = getattr(context, "client_id", None)
    return f"_session_{client_id}" if client_id else f"_session_{os.getpid()}"


def determine_mime_type(file_path: Path) -> str:
    """Determine MIME type based on file extension using enhanced mimetypes module."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type if mime_type else "application/octet-stream"


def is_gemini_supported_mime_type(mime_type: str) -> bool:
    """Check if MIME type is supported by Gemini API."""
    supported_mime_types = {
        # Documents
        "application/pdf",
        "text/plain",
        # Images
        "image/png",
        "image/jpeg",
        "image/webp",
        # Audio
        "audio/x-aac",
        "audio/flac",
        "audio/mp3",
        "audio/mpeg",
        "audio/m4a",
        "audio/opus",
        "audio/pcm",
        "audio/wav",
        "audio/webm",
        # Video
        "video/mp4",
        "video/mpeg",
        "video/quicktime",
        "video/mov",
        "video/avi",
        "video/x-flv",
        "video/mpg",
        "video/webm",
        "video/wmv",
        "video/3gpp",
    }
    return mime_type in supported_mime_types


def get_gemini_safe_mime_type(file_path: Path) -> str:
    """Get a Gemini-safe MIME type, falling back to text/plain for text files.

    This proactive approach prevents unnecessary API calls by converting known
    unsupported text MIME types to text/plain before upload. For unknown MIME
    types, the original is preserved to let Gemini handle the validation.
    """
    original_mime = determine_mime_type(file_path)

    # If it's already supported, use it
    if is_gemini_supported_mime_type(original_mime):
        return original_mime

    # If it's a text file, fall back to text/plain (which is supported)
    if is_text_file(file_path):
        return "text/plain"

    # For binary files, keep the original (let Gemini reject if unsupported)
    return original_mime


def is_gemini_mime_error(error_message: str) -> bool:
    """Check if an error message indicates an unsupported MIME type."""
    return "Unsupported MIME type" in str(error_message)


def is_text_file(file_path: Path) -> bool:
    """Check if file is likely a text file based on its MIME type."""
    mime_type = determine_mime_type(file_path)

    # Common text MIME types
    if mime_type.startswith("text/"):
        return True

    # Other common text-based formats categorized as 'application/*'
    return mime_type in TEXT_BASED_APPLICATION_TYPES


def resolve_file_content(
    file_item: str | dict[str, str],
) -> tuple[str | None, Path | None]:
    """Resolve file input to content string and optional path."""
    if isinstance(file_item, str):
        return file_item, None
    elif isinstance(file_item, dict):
        if "content" in file_item:
            return file_item["content"], None
        elif "path" in file_item:
            file_path = Path(file_item["path"])
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            return None, file_path
    return None, None


def read_file_smart(
    file_path: Path, max_size: int = 20 * 1024 * 1024
) -> tuple[str, bool]:
    """Read file with size-aware strategy. Returns (content, is_text)."""
    file_size = file_path.stat().st_size

    if file_size > max_size:
        raise ValueError(f"File too large: {file_size} bytes > {max_size}")

    if is_text_file(file_path):
        content = file_path.read_text(encoding="utf-8")
        return f"[File: {file_path.name}]\n{content}", True

    # Binary file - base64 encode
    file_content = file_path.read_bytes()
    encoded_content = base64.b64encode(file_content).decode()
    mime_type = determine_mime_type(file_path)
    return (
        f"[Binary file: {file_path.name}, {mime_type}, {file_size} bytes]\n{encoded_content}",
        False,
    )


def resolve_image_data(image_item: str | dict[str, str]) -> bytes:
    """Resolve image input to raw bytes."""
    if isinstance(image_item, str):
        if image_item.startswith("data:image"):
            header, encoded = image_item.split(",", 1)
            return base64.b64decode(encoded)
        else:
            return Path(image_item).read_bytes()
    elif isinstance(image_item, dict):
        if "data" in image_item:
            return base64.b64decode(image_item["data"])
        elif "path" in image_item:
            return Path(image_item["path"]).read_bytes()

    raise ValueError(f"Invalid image format: {image_item}")


def handle_output(
    response_text: str,
    output_file: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    provider: str,
) -> str:
    """Handle file output and return formatted response."""
    from mcp_handley_lab.common.pricing import format_usage

    usage_info = format_usage(input_tokens, output_tokens, cost)

    if output_file != "-":
        output_path = Path(output_file)
        output_path.write_text(response_text)
        char_count = len(response_text)
        line_count = response_text.count("\n") + 1
        return f"Response saved to: {output_file}\nContent: {char_count} characters, {line_count} lines\n{usage_info}"
    else:
        return f"{response_text}\n\n{usage_info}"


def handle_agent_memory(
    agent_name: str | bool | None,
    user_prompt: str,
    response_text: str,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    session_id_func,
) -> str | None:
    """Handle agent memory storage. Returns actual agent name used."""
    # Handle memory disable patterns
    if isinstance(agent_name, str) and (
        agent_name.lower() == "false" or agent_name == ""
    ):
        agent_name = False

    # Use session-specific agent for "session" or if no agent_name provided (and memory not disabled)
    if agent_name == "session" or agent_name is None:
        agent_name = session_id_func()

    # Store in agent memory (only if memory not disabled)
    if agent_name is not False:
        agent = memory_manager.get_agent(agent_name)
        if not agent:
            agent = memory_manager.create_agent(agent_name)

        memory_manager.add_message(
            agent_name, "user", user_prompt, input_tokens, cost / 2
        )
        memory_manager.add_message(
            agent_name, "assistant", response_text, output_tokens, cost / 2
        )
        return agent_name

    return None


def resolve_multimodal_content(
    files: list[str] | None = None, images: list[str] | None = None
) -> list[dict]:
    """
    Resolves file paths and image data into a standardized list of content blocks.
    Each block is a dict with 'type', 'mime_type', and 'data' (or 'text').
    """
    if files is None:
        files = []
    if images is None:
        images = []
    content_blocks = []

    # Process text/binary files
    for file_path_str in files:
        file_path = Path(file_path_str)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        mime_type = determine_mime_type(file_path)
        if is_text_file(file_path):
            text_content = file_path.read_text(encoding="utf-8")
            content_blocks.append(
                {
                    "type": "text_file",
                    "filename": file_path.name,
                    "text": text_content,
                }
            )
        else:
            # For binary files, pass as base64 data
            binary_data = file_path.read_bytes()
            content_blocks.append(
                {
                    "type": "binary_file",
                    "filename": file_path.name,
                    "mime_type": mime_type,
                    "data": base64.b64encode(binary_data),
                }
            )

    # Process images
    for image_item in images:
        image_bytes = resolve_image_data(image_item)

        # Determine mime type for the image
        if isinstance(image_item, str) and image_item.startswith("data:image"):
            mime_type = image_item.split(";")[0].split(":")[1]
        else:
            mime_type = determine_mime_type(Path(image_item))
            if not mime_type.startswith("image/"):
                mime_type = "image/jpeg"  # Default for safety

        content_blocks.append(
            {
                "type": "image",
                "mime_type": mime_type,
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            }
        )

    return content_blocks


def resolve_images_for_multimodal_prompt(
    prompt: str, images: list[str]
) -> tuple[str, list[dict]]:
    """
    Standardized image processing for multimodal prompts.

    Returns:
        tuple: (prompt_text, list of image content blocks)
        Each image block has: {"type": "image", "mime_type": str, "data": str}
    """
    if not images:
        return prompt, []

    image_blocks = []
    for image_path in images:
        image_bytes = resolve_image_data(image_path)

        # Determine mime type
        if isinstance(image_path, str) and image_path.startswith("data:image"):
            mime_type = image_path.split(";")[0].split(":")[1]
        else:
            mime_type = determine_mime_type(Path(image_path))
            if not mime_type.startswith("image/"):
                mime_type = "image/jpeg"

        image_blocks.append(
            {
                "type": "image",
                "mime_type": mime_type,
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            }
        )

    return prompt, image_blocks


def resolve_files_for_llm(
    files: list[str], max_file_size: int = 1024 * 1024
) -> list[str]:
    """Resolve list of file paths to inline content strings for LLM providers.

    Args:
        files: List of file paths
        max_file_size: Maximum file size to include (default 1MB)

    Returns:
        List of formatted content strings with file headers
    """
    if not files:
        return []

    inline_content = []
    for file_path_str in files:
        file_path = Path(file_path_str)
        try:
            content, is_text = read_file_smart(file_path, max_file_size)
            inline_content.append(content)
        except ValueError as e:
            if "too large" in str(e):
                # File too large - read truncated version
                if is_text_file(file_path):
                    content = file_path.read_text(encoding="utf-8")[
                        :100000
                    ]  # 100KB limit
                    inline_content.append(
                        f"[File: {file_path.name} (truncated)]\n{content}..."
                    )
                else:
                    inline_content.append(
                        f"[File: {file_path.name} - too large to include]"
                    )
            else:
                raise

    return inline_content


def build_server_info(
    provider_name: str,
    available_models: list[str],
    memory_manager,
    vision_support: bool = False,
    image_generation: bool = False,
) -> ServerInfo:
    """Build standardized ServerInfo object for LLM providers."""

    # Get agent count
    agent_count = len(memory_manager.list_agents())

    # Build capabilities list
    capabilities = [
        f"ask - Chat with {provider_name} models (persistent memory enabled by default)",
        "list_models - List available models with detailed information",
        "server_info - Get server status",
    ]

    if vision_support:
        capabilities.insert(
            1,
            "analyze_image - Image analysis with vision models (persistent memory enabled by default)",
        )

    if image_generation:
        if vision_support:
            capabilities.insert(
                2, f"generate_image - Generate images with {provider_name}"
            )
        else:
            capabilities.insert(
                1, f"generate_image - Generate images with {provider_name}"
            )

    # Build dependencies dict
    dependencies = {
        "api_key": "configured",
        "available_models": f"{len(available_models)} models",
        "active_agents": str(agent_count),
        "memory_storage": str(memory_manager.storage_dir),
    }

    if vision_support:
        dependencies["vision_support"] = "true"

    if image_generation:
        dependencies["image_generation"] = "true"

    return ServerInfo(
        name=f"{provider_name} Tool",
        version="1.0.0",
        status="active",
        capabilities=capabilities,
        dependencies=dependencies,
    )


def load_provider_models(provider: str) -> tuple[dict, str, callable]:
    """Load model configurations and return configs, default model, and config getter.

    Returns:
        tuple: (MODEL_CONFIGS dict, DEFAULT_MODEL str, _get_model_config function)
    """
    from mcp_handley_lab.llm.model_loader import (
        build_model_configs_dict,
        load_model_config,
    )

    # Load model configurations from YAML
    model_configs = build_model_configs_dict(provider)

    # Load default model from YAML
    config = load_model_config(provider)
    default_model = config["default_model"]

    # Return a closure for getting model config with fallback
    def get_model_config(model: str) -> dict:
        """Get model configuration with fallback to default."""
        return model_configs.get(model, model_configs[default_model])

    return model_configs, default_model, get_model_config

```

`src/mcp_handley_lab/llm/gemini/__init__.py`:

```py
"""Gemini LLM tool for AI interactions via MCP."""

```

`src/mcp_handley_lab/llm/gemini/tool.py`:

```py
"""Gemini LLM tool for AI interactions via MCP."""

import base64
import io
import json
import os
import time
from pathlib import Path
from typing import Any, Literal

import numpy as np
from google import genai as google_genai
from google.genai.types import (
    Blob,
    EmbedContentConfig,
    FileData,
    GenerateContentConfig,
    GenerateImagesConfig,
    GoogleSearch,
    GoogleSearchRetrieval,
    Part,
    Tool,
)
from mcp.server.fastmcp import FastMCP
from PIL import Image
from pydantic import Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    build_server_info,
    get_gemini_safe_mime_type,
    get_session_id,
    is_text_file,
    load_provider_models,
    resolve_image_data,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.model_loader import (
    get_structured_model_listing,
)
from mcp_handley_lab.llm.shared import process_image_generation, process_llm_request
from mcp_handley_lab.shared.models import (
    DocumentIndex,
    EmbeddingResult,
    ImageGenerationResult,
    IndexResult,
    LLMResult,
    ModelListing,
    SearchResult,
    ServerInfo,
    SimilarityResult,
)

mcp = FastMCP("Gemini Tool")

# Constants for configuration
GEMINI_INLINE_FILE_LIMIT_BYTES = 20 * 1024 * 1024  # 20MB
EMBEDDING_BATCH_SIZE = 100

# Type definitions
EmbeddingTaskType = Literal[
    "TASK_TYPE_UNSPECIFIED",
    "RETRIEVAL_QUERY",
    "RETRIEVAL_DOCUMENT",
    "SEMANTIC_SIMILARITY",
    "CLASSIFICATION",
    "CLUSTERING",
]

# Configure Gemini client - fail fast if API key is invalid/missing
client = google_genai.Client(api_key=settings.gemini_api_key)

# Generate session ID once at module load time
_SESSION_ID = f"_session_{os.getpid()}_{int(time.time())}"


# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL, _get_model_config = load_provider_models("gemini")


def _calculate_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two embedding vectors."""
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    dot_product = np.dot(vec1_np, vec2_np)
    norm_product = np.linalg.norm(vec1_np) * np.linalg.norm(vec2_np)
    return dot_product / norm_product


def _get_session_id() -> LLMResult:
    """Get the persistent session ID for this MCP server process."""
    return get_session_id(mcp)


def _get_model_config(model: str) -> dict[str, int]:
    """Get token limits for a specific model."""
    return MODEL_CONFIGS.get(model, MODEL_CONFIGS[DEFAULT_MODEL])


def _resolve_files(
    files: list[str],
) -> tuple[list[Part], bool]:
    """Resolve file inputs to structured content parts for google-genai API.

    Uses inlineData for files <20MB and Files API for larger files.
    Returns tuple of (Part objects list, Files API used flag).
    """
    parts = []
    used_files_api = False
    for file_item in files:
        # Handle unified format: strings or {"path": "..."} dicts
        if isinstance(file_item, str):
            file_path = Path(file_item)
        elif isinstance(file_item, dict) and "path" in file_item:
            file_path = Path(file_item["path"])
        else:
            raise ValueError(f"Invalid file item format: {file_item}")
        file_size = file_path.stat().st_size

        if file_size > GEMINI_INLINE_FILE_LIMIT_BYTES:
            # Large file - use Files API
            used_files_api = True
            uploaded_file = client.files.upload(
                file=str(file_path),
                mime_type=get_gemini_safe_mime_type(file_path),
            )
            parts.append(Part(fileData=FileData(fileUri=uploaded_file.uri)))
        else:
            # Small file - use inlineData with base64 encoding
            if is_text_file(file_path):
                # For text files, read directly as text
                content = file_path.read_text(encoding="utf-8")
                parts.append(Part(text=f"[File: {file_path.name}]\n{content}"))
            else:
                # For binary files, use inlineData
                file_content = file_path.read_bytes()
                encoded_content = base64.b64encode(file_content).decode()
                parts.append(
                    Part(
                        inlineData=Blob(
                            mimeType=get_gemini_safe_mime_type(file_path),
                            data=encoded_content,
                        )
                    )
                )

    return parts, used_files_api


def _resolve_images(
    images: list[str] | None = None,
) -> list[Image.Image]:
    """Resolve image inputs to PIL Image objects."""
    if images is None:
        images = []
    image_list = []

    # Handle images array
    for image_item in images:
        image_bytes = resolve_image_data(image_item)
        image_list.append(Image.open(io.BytesIO(image_bytes)))

    return image_list


def _gemini_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Gemini-specific text generation function for the shared processor."""
    # Extract Gemini-specific parameters
    temperature = kwargs.get("temperature", 1.0)
    grounding = kwargs.get("grounding", False)
    files = kwargs.get("files")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Configure tools for grounding if requested
    tools = []
    if grounding:
        if model.startswith("gemini-1.5"):
            tools.append(Tool(google_search_retrieval=GoogleSearchRetrieval()))
        else:
            tools.append(Tool(google_search=GoogleSearch()))

    # Resolve file contents
    file_parts, used_files_api = _resolve_files(files)

    # Get model configuration and token limits
    model_config = _get_model_config(model)
    max_output = model_config["output_tokens"]
    output_tokens = (
        min(max_output_tokens, max_output) if max_output_tokens > 0 else max_output
    )

    # Prepare config
    config_params = {
        "temperature": temperature,
        "max_output_tokens": output_tokens,
    }
    if system_instruction:
        config_params["system_instruction"] = system_instruction
    if tools:
        config_params["tools"] = tools

    config = GenerateContentConfig(**config_params)

    # Convert history to Gemini format
    gemini_history = [
        {
            "role": "model" if msg["role"] == "assistant" else msg["role"],
            "parts": [{"text": msg["content"]}],
        }
        for msg in history
    ]

    # Generate content
    if gemini_history:
        # Continue existing conversation
        user_parts = [Part(text=prompt)] + file_parts
        contents = gemini_history + [
            {"role": "user", "parts": [part.to_json_dict() for part in user_parts]}
        ]
        response = client.models.generate_content(
            model=model, contents=contents, config=config
        )
    else:
        # New conversation
        if file_parts:
            content_parts = [Part(text=prompt)] + file_parts
            response = client.models.generate_content(
                model=model, contents=content_parts, config=config
            )
        else:
            response = client.models.generate_content(
                model=model, contents=prompt, config=config
            )

    if not response.text:
        raise RuntimeError("No response text generated")

    # Extract grounding metadata - direct access, fail fast
    grounding_metadata = None
    response_dict = response.to_json_dict()
    if "candidates" in response_dict and response_dict["candidates"]:
        candidate = response_dict["candidates"][0]
        if "grounding_metadata" in candidate:
            metadata = candidate["grounding_metadata"]
            grounding_metadata = {
                "web_search_queries": metadata["web_search_queries"],
                "grounding_chunks": [
                    {"uri": chunk["web"]["uri"], "title": chunk["web"]["title"]}
                    for chunk in metadata["grounding_chunks"]
                    if "web" in chunk
                ],
                "grounding_supports": metadata["grounding_supports"],
                "search_entry_point": metadata["search_entry_point"],
            }

    # Extract additional response metadata - direct access
    finish_reason = ""
    avg_logprobs = 0.0
    if response.candidates and len(response.candidates) > 0:
        candidate = response.candidates[0]
        if candidate.finish_reason:
            finish_reason = str(candidate.finish_reason)
        if candidate.avg_logprobs is not None:
            avg_logprobs = float(candidate.avg_logprobs)

    # Extract generation time from server-timing header - fail fast on format changes
    # Files API responses don't include timing headers, only inline responses do
    generation_time_ms = 0
    if not used_files_api and response.sdk_http_response:
        http_dict = response.sdk_http_response.to_json_dict()
        headers = http_dict["headers"]
        server_timing = headers["server-timing"]
        if "dur=" in server_timing:
            # Extract duration from "gfet4t7; dur=11255" format. Fails loudly if format changes.
            dur_part = server_timing.split("dur=")[1].split(";")[0].split(",")[0]
            generation_time_ms = int(float(dur_part))

    return {
        "text": response.text,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count,
        "grounding_metadata": grounding_metadata,
        "finish_reason": finish_reason,
        "avg_logprobs": avg_logprobs,
        "model_version": response.model_version,
        "generation_time_ms": generation_time_ms,
        "response_id": "",  # Gemini doesn't provide a response ID
    }


def _gemini_image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Gemini-specific image analysis function for the shared processor."""
    # Extract image analysis specific parameters
    images = kwargs.get("images", [])
    max_output_tokens = kwargs.get("max_output_tokens")

    # Load images
    image_list = _resolve_images(images)

    # Get model configuration
    model_config = _get_model_config(model)
    max_output = model_config["output_tokens"]
    output_tokens = (
        min(max_output_tokens, max_output) if max_output_tokens > 0 else max_output
    )

    # Prepare content with images
    content = [prompt] + image_list

    # Prepare the config
    config_params = {"max_output_tokens": output_tokens, "temperature": 1.0}
    if system_instruction:
        config_params["system_instruction"] = system_instruction

    config = GenerateContentConfig(**config_params)

    # Generate response - image analysis starts fresh conversation
    response = client.models.generate_content(
        model=model, contents=content, config=config
    )

    if not response.text:
        raise RuntimeError("No response text generated")

    return {
        "text": response.text,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count,
    }


@mcp.tool(
    description="Delegates a user query to external Google Gemini AI service on behalf of the human user. Returns Gemini's verbatim response to assist the user. Use `agent_name` for separate conversation thread with Gemini. For code reviews, use code2prompt first."
)
def ask(
    prompt: str = Field(
        ...,
        description="The user's question to delegate to external Gemini AI service.",
    ),
    output_file: str = Field(
        default="-",
        description="File path to save Gemini's response. Use '-' for standard output.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with Gemini AI service (distinct from your conversation with the user).",
    ),
    model: str = Field(
        default=DEFAULT_MODEL,
        description="The Gemini model to use for the request (e.g., 'gemini-1.5-pro-latest').",
    ),
    temperature: float = Field(
        default=1.0,
        description="Controls randomness in the response. Higher values (e.g., 1.0) are more creative, lower values are more deterministic.",
    ),
    grounding: bool = Field(
        default=False,
        description="If True, enables Google Search grounding to provide more factual, up-to-date responses.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of file paths to provide as context to the model.",
    ),
    max_output_tokens: int = Field(
        default=0,
        description="The maximum number of tokens to generate in the response. 0 means use the model's default maximum.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external Gemini AI service. Remembered for this conversation thread.",
    ),
) -> LLMResult:
    """Ask Gemini a question with optional persistent memory."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="gemini",
        generation_func=_gemini_generation_adapter,
        mcp_instance=mcp,
        temperature=temperature,
        grounding=grounding,
        files=files,
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
    )


@mcp.tool(
    description="Delegates image analysis to external Gemini vision AI service on behalf of the user. Returns Gemini's verbatim visual analysis to assist the user."
)
def analyze_image(
    prompt: str = Field(
        ...,
        description="The user's question about the images to delegate to external Gemini vision AI service.",
    ),
    output_file: str = Field(
        default="-",
        description="File path to save Gemini's visual analysis. Use '-' for standard output.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of image file paths or base64 encoded strings to be analyzed.",
    ),
    focus: str = Field(
        default="general",
        description="The area of focus for the analysis (e.g., 'ocr', 'objects'). Note: This is a placeholder parameter in the current implementation.",
    ),
    model: str = Field(
        default=DEFAULT_MODEL,
        description="The Gemini vision model to use (e.g., 'gemini-1.5-pro-latest').",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with Gemini AI service (distinct from your conversation with the user).",
    ),
    max_output_tokens: int = Field(
        default=0,
        description="The maximum number of tokens to generate in the response. 0 means use the model's default maximum.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external Gemini AI service. Remembered for this conversation thread.",
    ),
) -> LLMResult:
    """Analyze images with Gemini vision model."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="gemini",
        generation_func=_gemini_image_analysis_adapter,
        mcp_instance=mcp,
        images=files,
        focus=focus,
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
    )


def _gemini_image_generation_adapter(prompt: str, model: str, **kwargs) -> dict:
    """Gemini-specific image generation function with comprehensive metadata extraction."""
    actual_model = model

    # Extract config parameters for metadata
    aspect_ratio = kwargs.get("aspect_ratio", "1:1")
    config = GenerateImagesConfig(number_of_images=1, aspect_ratio=aspect_ratio)

    response = client.models.generate_images(
        model=actual_model,
        prompt=prompt,
        config=config,
    )

    if not response.generated_images or not response.generated_images[0].image:
        raise RuntimeError("Generated image has no data")

    # Extract response data
    generated_image = response.generated_images[0]
    image = generated_image.image

    # Get the prompt token count. No fallback. If this fails, the request fails.
    count_response = client.models.count_tokens(
        model="gemini-1.5-flash-latest", contents=prompt
    )
    input_tokens = count_response.total_tokens

    # Extract safety attributes - direct access
    safety_attributes = {}
    if generated_image.safety_attributes:
        safety_attributes = {
            "categories": generated_image.safety_attributes.categories,
            "scores": generated_image.safety_attributes.scores,
            "content_type": generated_image.safety_attributes.content_type,
        }

    # Extract provider-specific metadata - direct access
    gemini_metadata = {
        "positive_prompt_safety_attributes": response.positive_prompt_safety_attributes,
        "actual_model_used": actual_model,
        "requested_model": model,
    }

    return {
        "image_bytes": image.image_bytes,
        "input_tokens": input_tokens,
        "enhanced_prompt": generated_image.enhanced_prompt or "",
        "original_prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "requested_format": "png",  # Gemini always returns PNG
        "mime_type": image.mime_type or "image/png",
        "cloud_uri": image.gcs_uri or "",
        "content_filter_reason": generated_image.rai_filtered_reason or "",
        "safety_attributes": safety_attributes,
        "gemini_metadata": gemini_metadata,
    }


@mcp.tool(
    description="Delegates image generation to external Google Imagen 3 AI service on behalf of the user. Returns the generated image file path to assist the user. Generated images are saved as PNG files."
)
def generate_image(
    prompt: str = Field(
        ...,
        description="The user's detailed description to send to external Imagen 3 AI service for image generation.",
    ),
    model: str = Field(
        default="imagen-3.0-generate-002",
        description="The Imagen model to use for image generation.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with image generation AI service (for prompt history tracking).",
    ),
) -> ImageGenerationResult:
    """Generate images with Google's Imagen 3 model."""
    return process_image_generation(
        prompt=prompt,
        agent_name=agent_name,
        model=model,
        provider="gemini",
        generation_func=_gemini_image_generation_adapter,
        mcp_instance=mcp,
    )


@mcp.tool(
    description="Generates embedding vectors for a given list of text strings using a specified model. Supports task-specific embeddings like 'SEMANTIC_SIMILARITY' or 'RETRIEVAL_DOCUMENT'."
)
def get_embeddings(
    contents: str | list[str] = Field(
        ...,
        description="The text string or list of text strings to be converted into embedding vectors.",
    ),
    model: str = Field(
        default="gemini-embedding-001", description="The embedding model to use."
    ),
    task_type: EmbeddingTaskType = Field(
        default="SEMANTIC_SIMILARITY",
        description="The intended use for the embedding. Affects how the embedding is generated. Options: 'RETRIEVAL_QUERY', 'RETRIEVAL_DOCUMENT', 'SEMANTIC_SIMILARITY', 'CLASSIFICATION', 'CLUSTERING'.",
    ),
    output_dimensionality: int = Field(
        default=0,
        description="The desired size of the output embedding vector. If 0, the model's default dimensionality is used.",
    ),
) -> list[EmbeddingResult]:
    """Generates embeddings for one or more text strings."""
    if isinstance(contents, str):
        contents = [contents]

    if not contents:
        raise ValueError("Contents list cannot be empty.")

    config_params = {"task_type": task_type.upper()}
    if output_dimensionality > 0:
        config_params["output_dimensionality"] = output_dimensionality

    config = EmbedContentConfig(**config_params)

    response = client.models.embed_content(
        model=model, contents=contents, config=config
    )

    # Direct, elegant, and trusts the response structure. Let it fail.
    return [EmbeddingResult(embedding=e.values) for e in response.embeddings]


@mcp.tool(
    description="Calculates the semantic similarity score (cosine similarity) between two text strings. Returns a score between -1.0 and 1.0, where 1.0 is identical."
)
def calculate_similarity(
    text1: str = Field(..., description="The first text string for comparison."),
    text2: str = Field(..., description="The second text string for comparison."),
    model: str = Field(
        default="gemini-embedding-001",
        description="The embedding model to use for generating vectors for similarity calculation.",
    ),
) -> SimilarityResult:
    """Calculates the cosine similarity between two texts."""
    if not text1 or not text2:
        raise ValueError("Both text1 and text2 must be provided.")

    embeddings = get_embeddings(
        contents=[text1, text2],
        model=model,
        task_type="SEMANTIC_SIMILARITY",
        output_dimensionality=0,
    )

    if len(embeddings) != 2:
        raise RuntimeError("Failed to generate embeddings for both texts.")

    similarity = _calculate_cosine_similarity(
        embeddings[0].embedding, embeddings[1].embedding
    )

    return SimilarityResult(similarity=similarity)


@mcp.tool(
    description="Creates a searchable semantic index from a list of document file paths. It reads the files, generates embeddings for them, and saves the index as a JSON file."
)
def index_documents(
    document_paths: list[str] = Field(
        ...,
        description="A list of file paths to the text documents that need to be indexed.",
    ),
    output_index_path: str = Field(
        ..., description="The file path where the resulting JSON index will be saved."
    ),
    model: str = Field(
        default="gemini-embedding-001",
        description="The embedding model to use for creating the document index.",
    ),
) -> IndexResult:
    """Creates a semantic index from document files."""
    indexed_data = []
    batch_size = EMBEDDING_BATCH_SIZE  # Process documents in batches

    for i in range(0, len(document_paths), batch_size):
        batch_paths = document_paths[i : i + batch_size]
        batch_contents = []
        valid_paths = []

        for doc_path_str in batch_paths:
            doc_path = Path(doc_path_str)
            # If path is not a file, .read_text() will raise an error. This is desired.
            batch_contents.append(doc_path.read_text(encoding="utf-8"))
            valid_paths.append(doc_path_str)

        if not batch_contents:
            continue

        embedding_results = get_embeddings(
            contents=batch_contents,
            model=model,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=0,
        )

        for path, emb_result in zip(valid_paths, embedding_results, strict=True):
            indexed_data.append(
                DocumentIndex(path=path, embedding=emb_result.embedding)
            )

    # Save the index to a file
    index_file = Path(output_index_path)
    index_file.parent.mkdir(parents=True, exist_ok=True)
    with open(index_file, "w") as f:
        # Pydantic's model_dump is used here to serialize our list of models
        json.dump([item.model_dump() for item in indexed_data], f, indent=2)

    return IndexResult(
        index_path=str(index_file),
        files_indexed=len(indexed_data),
        message=f"Successfully indexed {len(indexed_data)} files to {index_file}.",
    )


@mcp.tool(
    description="Performs a semantic search for a query against a pre-built document index file. Returns a ranked list of the most relevant documents based on similarity."
)
def search_documents(
    query: str = Field(..., description="The search query to find relevant documents."),
    index_path: str = Field(
        ...,
        description="The file path of the pre-computed JSON document index to search against.",
    ),
    top_k: int = Field(
        default=5, description="The number of top matching documents to return."
    ),
    model: str = Field(
        default="gemini-embedding-001",
        description="The embedding model to use for the query. Should match the model used to create the index.",
    ),
) -> list[SearchResult]:
    """Searches a document index for the most relevant documents to a query."""
    index_file = Path(index_path)
    # open() will raise FileNotFoundError. This is the correct behavior.
    with open(index_file) as f:
        indexed_data = json.load(f)

    if not indexed_data:
        return []

    # Get embedding for the query
    query_embedding_result = get_embeddings(
        contents=query,
        model=model,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=0,
    )
    query_embedding = query_embedding_result[0].embedding

    # Calculate similarities
    similarities = []
    for item in indexed_data:
        doc_embedding = item["embedding"]
        score = _calculate_cosine_similarity(query_embedding, doc_embedding)
        similarities.append({"path": item["path"], "score": score})

    # Sort by similarity and return top_k
    similarities.sort(key=lambda x: x["score"], reverse=True)

    results = [
        SearchResult(path=item["path"], similarity_score=item["score"])
        for item in similarities[:top_k]
    ]

    return results


@mcp.tool(
    description="Lists all available Gemini models with pricing, capabilities, and context windows. Helps compare models for cost, performance, and features to select the best model for specific tasks."
)
def list_models() -> ModelListing:
    """List available Gemini models with detailed information."""

    # Get models from API
    models_response = client.models.list()
    api_model_names = {model.name.split("/")[-1] for model in models_response}

    # Use structured model listing
    return get_structured_model_listing("gemini", api_model_names)


@mcp.tool(
    description="Checks Gemini Tool server status and API connectivity. Returns version info, model availability, and a list of available functions."
)
def server_info() -> ServerInfo:
    """Get server status and Gemini configuration."""

    # Test API by listing models
    models_response = client.models.list()
    available_models = []
    for model in models_response:
        # Filter for models that can be used with the generateContent and embedContent methods
        if "gemini" in model.name or "embedding" in model.name:
            available_models.append(model.name.split("/")[-1])

    # Add our new functions to the capabilities list
    info = build_server_info(
        provider_name="Gemini",
        available_models=available_models,
        memory_manager=memory_manager,
        vision_support=True,
        image_generation=True,
    )

    # Manually add embedding capabilities to the server info
    embedding_capabilities = [
        "get_embeddings - Generate embedding vectors for text.",
        "calculate_similarity - Compare two texts for semantic similarity.",
        "index_documents - Create a searchable index from files.",
        "search_documents - Search an index for a query.",
    ]
    info.capabilities.extend(embedding_capabilities)

    return info

```

`src/mcp_handley_lab/llm/grok/tool.py`:

```py
"""Grok LLM tool for AI interactions via MCP."""

from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from xai_sdk import Client

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    build_server_info,
    load_provider_models,
    resolve_files_for_llm,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.model_loader import (
    get_structured_model_listing,
)
from mcp_handley_lab.llm.shared import process_image_generation, process_llm_request
from mcp_handley_lab.shared.models import (
    ImageGenerationResult,
    LLMResult,
    ModelListing,
    ServerInfo,
)

mcp = FastMCP("Grok Tool")

# Configure Grok client
client = Client(api_key=settings.xai_api_key)

# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL, _get_model_config = load_provider_models("grok")


def _grok_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Grok-specific text generation function for the shared processor."""
    from xai_sdk import chat

    # Extract Grok-specific parameters
    temperature = kwargs.get("temperature", 1.0)
    files = kwargs.get("files")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Build messages using xai-sdk helpers
    messages = []

    # Add system instruction if provided
    if system_instruction:
        messages.append(chat.system(system_instruction))

    # Convert history to xai-sdk format
    for msg in history:
        if msg["role"] == "user":
            messages.append(chat.user(msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(chat.assistant(msg["content"]))

    # Resolve files
    inline_content = resolve_files_for_llm(files)

    # Add user message with any inline content
    user_content = prompt
    if inline_content:
        user_content += "\n\n" + "\n\n".join(inline_content)
    messages.append(chat.user(user_content))

    # Get model configuration
    model_config = _get_model_config(model)
    default_tokens = model_config["output_tokens"]

    # Build request parameters
    request_params = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    # Add max tokens
    if max_output_tokens > 0:
        request_params["max_tokens"] = max_output_tokens
    else:
        request_params["max_tokens"] = default_tokens

    # Make API call using XAI SDK's two-step process
    chat_session = client.chat.create(**request_params)
    response = chat_session.sample()

    if not response or not response.proto or not response.proto.choices:
        raise RuntimeError("No response generated")

    # Extract response data from proto
    choice = response.proto.choices[0]
    finish_reason = choice.finish_reason

    # Extract logprobs if available
    avg_logprobs = 0.0
    if hasattr(choice, "logprobs") and choice.logprobs:
        logprobs = [token.logprob for token in choice.logprobs.content]
        avg_logprobs = sum(logprobs) / len(logprobs) if logprobs else 0.0

    # Get message content - Grok uses reasoning_content for its responses
    message_content = ""
    if hasattr(choice.message, "content") and choice.message.content:
        message_content = choice.message.content
    elif (
        hasattr(choice.message, "reasoning_content")
        and choice.message.reasoning_content
    ):
        message_content = choice.message.reasoning_content

    return {
        "text": message_content,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "finish_reason": str(finish_reason),
        "avg_logprobs": avg_logprobs,
        "model_version": response.proto.model,
        "response_id": getattr(response, "id", ""),
        "system_fingerprint": getattr(response, "system_fingerprint", "") or "",
        "service_tier": "",  # Grok doesn't have service tiers
        "completion_tokens_details": {},  # Not available for Grok
        "prompt_tokens_details": {},  # Not available for Grok
    }


def _grok_image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Grok-specific image analysis function for the shared processor."""
    from xai_sdk import chat

    # Extract image analysis specific parameters
    images = kwargs.get("images", [])
    focus = kwargs.get("focus", "general")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Use standardized image processing
    from mcp_handley_lab.llm.common import resolve_images_for_multimodal_prompt

    # Enhance prompt based on focus
    if focus != "general":
        prompt = f"Focus on {focus} aspects. {prompt}"

    prompt_text, image_blocks = resolve_images_for_multimodal_prompt(prompt, images)

    # Build messages using xai-sdk helpers
    messages = []

    # Add system instruction if provided
    if system_instruction:
        messages.append(chat.system(system_instruction))

    # Convert history to xai-sdk format
    for msg in history:
        if msg["role"] == "user":
            messages.append(chat.user(msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(chat.assistant(msg["content"]))

    # Build message content with text and images
    content_parts = [chat.text(prompt_text)]
    for image_block in image_blocks:
        image_url = f"data:{image_block['mime_type']};base64,{image_block['data']}"
        content_parts.append(chat.image(image_url))

    # Add current message with images
    messages.append(chat.user(*content_parts))

    # Get model configuration
    model_config = _get_model_config(model)
    default_tokens = model_config["output_tokens"]

    # Build request parameters
    request_params = {
        "model": model,
        "messages": messages,
        "temperature": 1.0,
    }

    # Add max tokens
    if max_output_tokens > 0:
        request_params["max_tokens"] = max_output_tokens
    else:
        request_params["max_tokens"] = default_tokens

    # Make API call using XAI SDK's two-step process
    chat_session = client.chat.create(**request_params)
    response = chat_session.sample()

    if not response or not response.proto or not response.proto.choices:
        raise RuntimeError("No response generated")

    # Extract response data from proto
    choice = response.proto.choices[0]

    # Get message content - Grok uses reasoning_content for its responses
    message_content = ""
    if hasattr(choice.message, "content") and choice.message.content:
        message_content = choice.message.content
    elif (
        hasattr(choice.message, "reasoning_content")
        and choice.message.reasoning_content
    ):
        message_content = choice.message.reasoning_content

    return {
        "text": message_content,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "finish_reason": str(choice.finish_reason),
        "avg_logprobs": 0.0,  # Image analysis doesn't use logprobs
        "model_version": response.proto.model,
        "response_id": getattr(response, "id", ""),
        "system_fingerprint": getattr(response, "system_fingerprint", "") or "",
        "service_tier": "",  # Grok doesn't have service tiers
        "completion_tokens_details": {},  # Not available for vision models
        "prompt_tokens_details": {},  # Not available for vision models
    }


@mcp.tool(
    description="Delegates a user query to external xAI Grok service on behalf of the human user. Returns Grok's verbatim response to assist the user. Use `agent_name` for separate conversation thread with Grok. For code reviews, use code2prompt first."
)
def ask(
    prompt: str = Field(
        ..., description="The user's question to delegate to external Grok AI service."
    ),
    output_file: str = Field(
        default="-",
        description="File path to save Grok's response. Use '-' for standard output.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with Grok AI service (distinct from your conversation with the user).",
    ),
    model: str = Field(
        default=DEFAULT_MODEL,
        description="The Grok model to use for the request (e.g., 'grok-1').",
    ),
    temperature: float = Field(
        default=1.0,
        description="Controls randomness. Higher values (e.g., 1.0) are more creative, lower values are more deterministic.",
    ),
    max_output_tokens: int = Field(
        default=0,
        description="The maximum number of tokens to generate. 0 means use the model's default maximum.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of file paths to provide as text context to the model.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external Grok AI service. Remembered for this conversation thread.",
    ),
) -> LLMResult:
    """Ask Grok a question with optional persistent memory."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="grok",
        generation_func=_grok_generation_adapter,
        mcp_instance=mcp,
        temperature=temperature,
        files=files,
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
    )


@mcp.tool(
    description="Delegates image analysis to external Grok vision AI service on behalf of the user. Returns Grok's verbatim visual analysis to assist the user."
)
def analyze_image(
    prompt: str = Field(
        ...,
        description="The user's question about the images to delegate to external Grok vision AI service.",
    ),
    output_file: str = Field(
        default="-",
        description="File path to save Grok's visual analysis. Use '-' for standard output.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of image file paths or base64 encoded strings to be analyzed.",
    ),
    focus: str = Field(
        default="general",
        description="The area of focus for the analysis (e.g., 'ocr', 'objects'). This enhances the prompt to guide the model.",
    ),
    model: str = Field(
        default="grok-2-vision-1212",
        description="The Grok vision model to use. Must be a vision-capable model.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with Grok AI service (distinct from your conversation with the user).",
    ),
    max_output_tokens: int = Field(
        default=0,
        description="The maximum number of tokens to generate in the response. 0 means use the model's default maximum.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external Grok AI service. Remembered for this conversation thread.",
    ),
) -> LLMResult:
    """Analyze images with Grok vision model."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="grok",
        generation_func=_grok_image_analysis_adapter,
        mcp_instance=mcp,
        images=files,
        focus=focus,
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
    )


def _grok_image_generation_adapter(prompt: str, model: str, **kwargs) -> dict:
    """Grok-specific image generation function with comprehensive metadata extraction."""
    # Use xai-sdk's image.sample method
    response = client.image.sample(prompt=prompt, model=model, image_format="base64")

    if not response or not response.images:
        raise RuntimeError("No image generated")

    # Get the first (and typically only) image
    image = response.images[0]

    # Decode base64 image data
    import base64

    image_bytes = base64.b64decode(image.image_data)

    # Extract metadata
    grok_metadata = {
        "model_used": model,
        "safety_rating": getattr(image, "safety_rating", None),
        "finish_reason": getattr(image, "finish_reason", None),
    }

    return {
        "image_bytes": image_bytes,
        "generation_timestamp": 0,  # Not provided by xai-sdk
        "enhanced_prompt": "",  # Not provided by xai-sdk
        "original_prompt": prompt,
        "requested_format": "png",  # xai-sdk returns PNG
        "mime_type": "image/png",
        "grok_metadata": grok_metadata,
    }


@mcp.tool(
    description="Delegates image generation to external Grok AI service on behalf of the user. Returns the generated image file path to assist the user."
)
def generate_image(
    prompt: str = Field(
        ...,
        description="The user's detailed description to send to external Grok AI service for image generation.",
    ),
    model: str = Field(
        default="grok-2-image-1212",
        description="The Grok model to use for image generation.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with image generation AI service (for prompt history tracking).",
    ),
) -> ImageGenerationResult:
    """Generate images with Grok."""
    return process_image_generation(
        prompt=prompt,
        agent_name=agent_name,
        model=model,
        provider="grok",
        generation_func=_grok_image_generation_adapter,
        mcp_instance=mcp,
    )


@mcp.tool(
    description="Retrieves a catalog of available Grok models with their capabilities, pricing, and context windows. Use this to select the best model for a task."
)
def list_models() -> ModelListing:
    """List available Grok models with detailed information."""
    # Get models from API for availability checking
    language_models = client.models.list_language_models()
    api_model_ids = {m.name for m in language_models}

    # Also get image generation models
    image_models = client.models.list_image_generation_models()
    api_model_ids.update({m.name for m in image_models})

    # Use structured model listing
    return get_structured_model_listing("grok", api_model_ids)


@mcp.tool(
    description="Checks Grok Tool server status and API connectivity. Returns version info, model availability, and a list of available functions."
)
def server_info() -> ServerInfo:
    """Get server status and Grok configuration."""
    # Test API key by listing models
    language_models = client.models.list_language_models()
    available_models = [m.name for m in language_models if "grok" in m.name.lower()]

    # Also count image models
    image_models = client.models.list_image_generation_models()
    available_models.extend([m.name for m in image_models if "grok" in m.name.lower()])

    return build_server_info(
        provider_name="Grok",
        available_models=available_models,
        memory_manager=memory_manager,
        vision_support=True,
        image_generation=True,
    )

```

`src/mcp_handley_lab/llm/memory.py`:

```py
"""Agent memory management for persistent LLM conversations."""

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single message in a conversation."""

    role: str = Field(
        ..., description="The role of the message sender ('user' or 'assistant')."
    )
    content: str = Field(..., description="The text content of the message.")
    timestamp: datetime = Field(..., description="When the message was created.")
    tokens: int | None = Field(
        default=None, description="Number of tokens in this message, if available."
    )
    cost: float | None = Field(
        default=None, description="Cost associated with this message, if available."
    )


class AgentMemory(BaseModel):
    """Persistent memory for a named agent."""

    name: str = Field(..., description="The unique name of the agent.")
    system_prompt: str | None = Field(
        default=None,
        description="The system prompt for the agent. Remembered and re-sent with every message until changed.",
    )
    created_at: datetime = Field(
        ..., description="The timestamp when the agent was created."
    )
    messages: list[Message] = Field(
        default_factory=list, description="The list of conversation messages."
    )
    total_tokens: int = Field(
        default=0, description="The cumulative token count for this agent."
    )
    total_cost: float = Field(
        default=0.0, description="The cumulative cost for this agent's conversations."
    )

    def add_message(self, role: str, content: str, tokens: int = 0, cost: float = 0.0):
        """Add a message to the agent's memory."""
        message = Message(
            role=role,
            content=content,
            timestamp=datetime.now(),
            tokens=tokens,
            cost=cost,
        )
        self.messages.append(message)
        self.total_tokens += tokens
        self.total_cost += cost

    def clear_history(self):
        """Clear all conversation history."""
        self.messages = []
        self.total_tokens = 0
        self.total_cost = 0.0

    def get_history(self) -> list[dict[str, str]]:
        """Get conversation history in provider-agnostic format."""
        return [
            {"role": message.role, "content": message.content}
            for message in self.messages
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get summary statistics for the agent."""
        return {
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "message_count": len(self.messages),
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "system_prompt": self.system_prompt,
        }

    def get_response(self, index: int = -1) -> str:
        """Get a message content by index. Raises IndexError if not found."""
        if not self.messages:
            raise IndexError("Cannot get response: agent has no message history")
        return self.messages[index].content


class MemoryManager:
    """Manages agent memories with file-based persistence."""

    def __init__(self, storage_dir: str = ".mcp_handley_lab"):
        self.storage_dir = Path(storage_dir)
        self.agents_dir = self.storage_dir / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self._agents: dict[str, AgentMemory] = {}
        self._load_agents()

    def _get_agent_file(self, name: str) -> Path:
        """Get the file path for an agent."""
        return self.agents_dir / f"{name}.json"

    def _load_agents(self):
        """Load agents from disk."""
        if not self.agents_dir.exists():
            return

        for agent_file in self.agents_dir.glob("*.json"):
            agent = AgentMemory.model_validate_json(agent_file.read_text())
            self._agents[agent.name] = agent

    def _save_agent(self, agent: AgentMemory):
        """Save a single agent to disk."""
        agent_file = self._get_agent_file(agent.name)
        agent_file.write_text(agent.model_dump_json(indent=2))

    def create_agent(self, name: str, system_prompt: str | None = None) -> AgentMemory:
        """Create a new agent."""
        if name in self._agents:
            raise ValueError(f"Agent '{name}' already exists")

        agent = AgentMemory(
            name=name, system_prompt=system_prompt, created_at=datetime.now()
        )
        self._agents[name] = agent
        self._save_agent(agent)
        return agent

    def get_agent(self, name: str) -> AgentMemory | None:
        """Get an existing agent."""
        return self._agents.get(name)

    def list_agents(self) -> list[AgentMemory]:
        """List all agents."""
        return list(self._agents.values())

    def delete_agent(self, name: str) -> None:
        """Delete an agent."""
        if name not in self._agents:
            raise ValueError(f"Agent '{name}' not found")
        del self._agents[name]
        agent_file = self._get_agent_file(name)
        if agent_file.exists():
            agent_file.unlink()

    def add_message(
        self,
        agent_name: str,
        role: str,
        content: str,
        tokens: int = 0,
        cost: float = 0.0,
    ):
        """Add a message to an agent's memory."""
        agent = self.get_agent(agent_name)
        if agent:
            agent.add_message(role, content, tokens, cost)
            self._save_agent(agent)

    def clear_agent_history(self, agent_name: str) -> None:
        """Clear an agent's conversation history."""
        agent = self.get_agent(agent_name)
        if not agent:
            raise ValueError(f"Agent '{agent_name}' not found")
        agent.clear_history()
        self._save_agent(agent)

    def get_response(self, agent_name: str, index: int = -1) -> str:
        """Get a message content from an agent by index. Default -1 gets the last message."""
        agent = self.get_agent(agent_name)
        if not agent:
            raise ValueError(f"Agent '{agent_name}' not found")

        return agent.get_response(index)


# Global memory manager instance
memory_manager = MemoryManager()

```

`src/mcp_handley_lab/llm/model_loader.py`:

```py
"""Utility for loading model configurations from YAML files."""

from pathlib import Path
from typing import Any

import yaml


def load_model_config(provider: str) -> dict[str, Any]:
    """Load model configuration from YAML file for a specific provider.

    Args:
        provider: Provider name ('openai', 'claude', 'gemini')

    Returns:
        Dictionary containing models, display_categories, default_model, and usage_notes

    Raises:
        FileNotFoundError: If YAML file doesn't exist
        yaml.YAMLError: If YAML file is invalid
        ValueError: If required sections are missing
    """
    yaml_path = Path(__file__).parent / provider / "models.yaml"

    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Validate required sections (business logic, not defensive programming)
    required_sections = ["models", "display_categories", "default_model", "usage_notes"]
    missing_sections = [
        section for section in required_sections if section not in config
    ]
    if missing_sections:
        raise ValueError(f"Missing required sections: {missing_sections}")

    return config


def get_models_by_tags(
    config: dict[str, Any],
    required_tags: list[str],
    exclude_tags: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Filter models by tags.

    Args:
        config: Model configuration dictionary
        required_tags: Models must have ALL of these tags
        exclude_tags: Models must have NONE of these tags

    Returns:
        Dictionary of model_id -> model_config for matching models
    """
    exclude_tags = exclude_tags or []
    matching_models = {}

    for model_id, model_config in config["models"].items():
        model_tags = set(model_config.get("tags", []))

        # Check if model has all required tags
        if not all(tag in model_tags for tag in required_tags):
            continue

        # Check if model has any excluded tags
        if any(tag in model_tags for tag in exclude_tags):
            continue

        matching_models[model_id] = model_config

    return matching_models


def build_model_configs_dict(provider: str) -> dict[str, dict[str, Any]]:
    """Build MODEL_CONFIGS dictionary from YAML configuration.

    Args:
        provider: Provider name ('openai', 'claude', 'gemini')

    Returns:
        Dictionary compatible with existing MODEL_CONFIGS format
    """
    config = load_model_config(provider)
    model_configs = {}

    for model_id, model_info in config["models"].items():
        if provider == "openai":
            # OpenAI format - handle image generation models differently
            if model_info.get("pricing_type") == "per_image":
                # Image generation models don't need output_tokens/param
                model_configs[model_id] = {
                    "output_tokens": None,  # N/A for image generation
                    "param": None,
                }
            else:
                # Text generation models require explicit values in YAML
                if "output_tokens" not in model_info:
                    raise ValueError(
                        f"Missing 'output_tokens' for OpenAI model {model_id}"
                    )
                if "param" not in model_info:
                    raise ValueError(f"Missing 'param' for OpenAI model {model_id}")
                model_configs[model_id] = {
                    "output_tokens": model_info["output_tokens"],
                    "param": model_info["param"],
                    "supports_temperature": model_info.get("supports_temperature", True),
                }
        elif provider == "claude":
            # Claude format - require explicit values in YAML
            if "input_tokens" not in model_info:
                raise ValueError(f"Missing 'input_tokens' for Claude model {model_id}")
            # All Claude models in YAML have output_tokens defined - no need for defensive check
            model_configs[model_id] = {
                "input_tokens": model_info["input_tokens"],
                "output_tokens": model_info["output_tokens"],
            }
        elif provider == "gemini":
            # Gemini format - skip image/video generation models or require explicit values
            if model_info.get("pricing_type") in ["per_image", "per_second"]:
                # Image/video generation models don't need output_tokens
                model_configs[model_id] = {
                    "output_tokens": None  # N/A for image/video generation
                }
            else:
                # Text generation models require explicit values in YAML
                if "output_tokens" not in model_info:
                    raise ValueError(
                        f"Missing 'output_tokens' for Gemini model {model_id}"
                    )
                model_configs[model_id] = {"output_tokens": model_info["output_tokens"]}
        elif provider == "grok":
            # Grok format - similar to Gemini but different pricing types
            if model_info.get("pricing_type") == "per_image":
                # Image generation models don't need output_tokens
                model_configs[model_id] = {
                    "output_tokens": None  # N/A for image generation
                }
            else:
                # Text generation models require explicit values in YAML
                if "output_tokens" not in model_info:
                    raise ValueError(
                        f"Missing 'output_tokens' for Grok model {model_id}"
                    )
                model_configs[model_id] = {"output_tokens": model_info["output_tokens"]}
        # Other providers can be added here as needed

    return model_configs


def get_structured_model_listing(provider: str, api_model_ids: set | None = None):
    """Generate structured model listing from YAML configuration.

    Args:
        provider: Provider name ('openai', 'claude', 'gemini')
        api_model_ids: Set of model IDs available via API (for availability checking)

    Returns:
        ModelListing object with structured model information
    """
    from mcp_handley_lab.common.pricing import calculate_cost
    from mcp_handley_lab.shared.models import (
        ModelCategory,
        ModelInfo,
        ModelListing,
        ModelListingSummary,
        ModelPricing,
    )

    config = load_model_config(provider)

    # Build summary
    summary = ModelListingSummary(
        provider=provider,
        total_models=len(config["models"]),
        total_categories=len(config["display_categories"]),
        default_model=config["default_model"],
        api_available_models=len(api_model_ids) if api_model_ids else 0,
    )

    # Process categories and models
    categories = []
    all_models = []

    for category in config["display_categories"]:
        category_name = category["name"]
        required_tags = category["tags"]
        exclude_tags = category.get("exclude_tags", [])

        # Get models for this category
        category_models = get_models_by_tags(config, required_tags, exclude_tags)

        category_model_objects = []

        for model_id, model_config in category_models.items():
            # Check API availability
            available = model_id in api_model_ids if api_model_ids else True

            # Get pricing
            pricing_type = model_config.get("pricing_type", "token")

            if pricing_type == "per_image":
                cost_per_image = calculate_cost(
                    model_id, 1, 0, provider, images_generated=1
                )
                pricing = ModelPricing(type="per_image", cost_per_image=cost_per_image)
            elif pricing_type == "per_second":
                cost_per_second = calculate_cost(
                    model_id, 1, 0, provider, seconds_generated=1
                )
                pricing = ModelPricing(
                    type="per_second", cost_per_second=cost_per_second
                )
            else:
                input_cost = calculate_cost(model_id, 1000000, 0, provider)
                output_cost = calculate_cost(model_id, 0, 1000000, provider)
                pricing = ModelPricing(
                    type="per_token",
                    input_cost_per_1m=input_cost,
                    output_cost_per_1m=output_cost,
                )

            # Parse capabilities and best_for from strings to lists
            capabilities = []
            if model_config.get("capabilities"):
                capabilities = [
                    cap.strip() for cap in model_config["capabilities"].split(",")
                ]

            best_for = []
            if model_config.get("best_for"):
                best_for = [
                    item.strip() for item in model_config["best_for"].split(",")
                ]

            model_info = ModelInfo(
                id=model_id,
                name=model_id,
                description=model_config.get("description", ""),
                available=available,
                context_window=str(model_config.get("context_window", "")),
                pricing=pricing,
                tags=model_config.get("tags", []),
                capabilities=capabilities,
                best_for=best_for,
            )

            category_model_objects.append(model_info)
            all_models.append(model_info)

        if category_model_objects:  # Only add categories with models
            categories.append(
                ModelCategory(name=category_name, models=category_model_objects)
            )

    return ModelListing(
        summary=summary,
        categories=categories,
        models=all_models,
        usage_notes=config["usage_notes"],
    )


def format_model_listing(provider: str, api_model_ids: set | None = None) -> str:
    """Generate formatted model listing from YAML configuration.

    Args:
        provider: Provider name ('openai', 'claude', 'gemini')
        api_model_ids: Set of model IDs available via API (for availability checking)

    Returns:
        Formatted string with model information grouped by categories
    """
    from mcp_handley_lab.common.pricing import calculate_cost

    config = load_model_config(provider)
    model_info = []

    # Build summary
    total_models = len(config["models"])
    total_categories = len(config["display_categories"])

    summary = f"""
📊 {provider.title()} Model Summary
{"=" * (len(provider) + 20)}
• Total Models: {total_models}
• Model Categories: {total_categories}
• Default Model: {config["default_model"]}
"""

    # Add provider-specific info
    if provider == "openai":
        summary += f"• API Available Models: {len(api_model_ids) if api_model_ids else 'Unknown'}\n"

    # Process each display category
    for category in config["display_categories"]:
        category_name = category["name"]
        required_tags = category["tags"]
        exclude_tags = category.get("exclude_tags", [])

        model_info.append(f"\n{category_name}")
        model_info.append("=" * len(category_name))

        # Get models for this category
        category_models = get_models_by_tags(config, required_tags, exclude_tags)

        for model_id, model_config in category_models.items():
            # Check API availability
            if api_model_ids:
                availability = (
                    "✅ Available"
                    if model_id in api_model_ids
                    else "❓ Not listed in API"
                )
            else:
                availability = "✅ Configured"

            # Get pricing
            pricing_type = model_config.get("pricing_type", "token")
            if pricing_type == "per_image":
                cost_per_image = calculate_cost(
                    model_id, 1, 0, provider, images_generated=1
                )
                pricing = f"${cost_per_image:.3f} per image"
            elif pricing_type == "per_second":
                cost_per_second = calculate_cost(
                    model_id, 1, 0, provider, seconds_generated=1
                )
                pricing = f"${cost_per_second:.3f} per second"
            else:
                input_cost = calculate_cost(model_id, 1000000, 0, provider)
                output_cost = calculate_cost(model_id, 0, 1000000, provider)
                pricing = f"${input_cost:.2f}/${output_cost:.2f} per 1M tokens"

            # Format model entry
            context_window = model_config.get("context_window", "Unknown")
            description = model_config.get("description", "No description")
            capabilities = model_config.get("capabilities", "No capabilities listed")

            model_info.append(
                f"""
📋 {model_id}
   Description: {description}
   Status: {availability}
   Context Window: {context_window}
   Pricing: {pricing}
   {capabilities}"""
            )

    # Add usage notes
    usage_notes = "\n💡 Usage Notes:\n" + "\n".join(
        f"• {note}" for note in config["usage_notes"]
    )

    return summary + "\n".join(model_info) + usage_notes

```

`src/mcp_handley_lab/llm/openai/__init__.py`:

```py
"""OpenAI LLM integration for MCP Framework."""

```

`src/mcp_handley_lab/llm/openai/tool.py`:

```py
"""OpenAI LLM tool for AI interactions via MCP."""

import json
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from mcp.server.fastmcp import FastMCP
from openai import OpenAI
from pydantic import Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    build_server_info,
    load_provider_models,
    resolve_files_for_llm,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.model_loader import (
    get_structured_model_listing,
)
from mcp_handley_lab.llm.shared import process_image_generation, process_llm_request
from mcp_handley_lab.shared.models import (
    DocumentIndex,
    EmbeddingResult,
    ImageGenerationResult,
    IndexResult,
    LLMResult,
    ModelListing,
    SearchResult,
    ServerInfo,
    SimilarityResult,
)

mcp = FastMCP("OpenAI Tool")

# Constants for embedding configuration
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_BATCH_SIZE = 100

# Configure OpenAI client
client = OpenAI(api_key=settings.openai_api_key)

# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL, _get_model_config = load_provider_models("openai")


def _openai_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """OpenAI-specific text generation function for the shared processor."""
    # Get model configuration first for validation
    model_config = _get_model_config(model)
    
    # Extract OpenAI-specific parameters
    temperature = kwargs.get("temperature", 1.0)
    files = kwargs.get("files")
    max_output_tokens = kwargs.get("max_output_tokens")
    enable_logprobs = kwargs["enable_logprobs"]
    top_logprobs = kwargs["top_logprobs"]
    
    # Validate temperature parameter
    if not model_config.get("supports_temperature", True) and temperature != 1.0:
        raise ValueError(f"Model '{model}' does not support the 'temperature' parameter. Please remove it from your request.")

    # Build messages
    messages = []

    # Add system instruction if provided
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    # Add history (already in OpenAI format)
    messages.extend(history)

    # Resolve files
    inline_content = resolve_files_for_llm(files)

    # Add user message with any inline content
    user_content = prompt
    if inline_content:
        user_content += "\n\n" + "\n\n".join(inline_content)
    messages.append({"role": "user", "content": user_content})

    param_name = model_config["param"]
    default_tokens = model_config["output_tokens"]

    # Build request parameters
    request_params = {
        "model": model,
        "messages": messages,
    }

    # Add logprobs if requested
    if enable_logprobs:
        request_params["logprobs"] = True
        if top_logprobs > 0:
            request_params["top_logprobs"] = top_logprobs

    # Add temperature for models that support it
    if model_config.get("supports_temperature", True):
        request_params["temperature"] = temperature

    # Add max tokens with correct parameter name
    request_params[param_name] = max_output_tokens or default_tokens

    # Make API call
    response = client.chat.completions.create(**request_params)


    # Extract additional OpenAI metadata
    choice = response.choices[0]
    finish_reason = choice.finish_reason

    # Extract logprobs for confidence assessment
    avg_logprobs = 0.0
    if choice.logprobs and choice.logprobs.content:
        logprobs = [token.logprob for token in choice.logprobs.content]
        avg_logprobs = sum(logprobs) / len(logprobs)

    # Extract token details
    completion_tokens_details = {}
    if response.usage.completion_tokens_details:
        details = response.usage.completion_tokens_details
        completion_tokens_details = {
            "reasoning_tokens": details.reasoning_tokens,
            "accepted_prediction_tokens": details.accepted_prediction_tokens,
            "rejected_prediction_tokens": details.rejected_prediction_tokens,
            "audio_tokens": details.audio_tokens,
        }

    prompt_tokens_details = {}
    if response.usage.prompt_tokens_details:
        details = response.usage.prompt_tokens_details
        prompt_tokens_details = {
            "cached_tokens": details.cached_tokens,
            "audio_tokens": details.audio_tokens,
        }

    return {
        "text": response.choices[0].message.content,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "finish_reason": finish_reason,
        "avg_logprobs": avg_logprobs,
        "model_version": response.model,
        "response_id": response.id,
        "system_fingerprint": response.system_fingerprint or "",
        "service_tier": response.service_tier or "",
        "completion_tokens_details": completion_tokens_details,
        "prompt_tokens_details": prompt_tokens_details,
    }


def _openai_image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """OpenAI-specific image analysis function for the shared processor."""
    # Get model configuration first for validation
    model_config = _get_model_config(model)
    
    # Extract image analysis specific parameters
    images = kwargs.get("images", [])
    focus = kwargs.get("focus", "general")
    max_output_tokens = kwargs.get("max_output_tokens")
    temperature = kwargs.get("temperature", 1.0)
    
    # Validate temperature parameter
    if not model_config.get("supports_temperature", True) and temperature != 1.0:
        raise ValueError(f"Model '{model}' does not support the 'temperature' parameter. Please remove it from your request.")

    # Use standardized image processing
    from mcp_handley_lab.llm.common import resolve_images_for_multimodal_prompt

    # Enhance prompt based on focus
    if focus != "general":
        prompt = f"Focus on {focus} aspects. {prompt}"

    prompt_text, image_blocks = resolve_images_for_multimodal_prompt(prompt, images)

    # Build message content with images in OpenAI format
    content = [{"type": "text", "text": prompt_text}]
    for image_block in image_blocks:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_block['mime_type']};base64,{image_block['data']}"
                },
            }
        )

    # Build messages
    messages = []

    # Add system instruction if provided
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    # Add history (already in OpenAI format)
    messages.extend(history)

    # Add current message with images
    messages.append({"role": "user", "content": content})

    param_name = model_config["param"]
    default_tokens = model_config["output_tokens"]

    # Build request parameters
    request_params = {
        "model": model,
        "messages": messages,
    }

    # Add temperature for models that support it
    if model_config.get("supports_temperature", True):
        request_params["temperature"] = temperature

    # Add max tokens with correct parameter name
    request_params[param_name] = max_output_tokens or default_tokens

    # Make API call
    response = client.chat.completions.create(**request_params)


    return {
        "text": response.choices[0].message.content,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "finish_reason": response.choices[0].finish_reason,
        "avg_logprobs": 0.0,  # Image analysis doesn't use logprobs
        "model_version": response.model,
        "response_id": response.id,
        "system_fingerprint": response.system_fingerprint or "",
        "service_tier": response.service_tier or "",
        "completion_tokens_details": {},  # Not available for vision models
        "prompt_tokens_details": {},  # Not available for vision models
    }


@mcp.tool(
    description="Delegates a user query to external OpenAI GPT service on behalf of the human user. Returns OpenAI's verbatim response to assist the user. Use `agent_name` for separate conversation thread with OpenAI. For code reviews, use code2prompt first."
)
def ask(
    prompt: str = Field(
        ...,
        description="The user's question to delegate to external OpenAI AI service.",
    ),
    output_file: str = Field(
        default="-",
        description="File path to save OpenAI's response. Use '-' for standard output.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with OpenAI AI service (distinct from your conversation with the user).",
    ),
    model: str = Field(
        default=DEFAULT_MODEL,
        description="The OpenAI GPT model to use for the request (e.g., 'gpt-4o').",
    ),
    temperature: float = Field(
        default=1.0,
        description="Controls response randomness (0.0-2.0). Higher is more creative.",
    ),
    max_output_tokens: int = Field(
        default=0,
        description="Max response tokens. 0 for model's default max.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="List of file paths to include as context.",
    ),
    enable_logprobs: bool = Field(
        default=False,
        description="Return log probabilities for output tokens for confidence scoring.",
    ),
    top_logprobs: int = Field(
        default=0,
        description="Number of top-N logprobs to return per token (0-5). Requires enable_logprobs.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external OpenAI AI service. Remembered for this conversation thread.",
    ),
) -> LLMResult:
    """Ask OpenAI a question with optional persistent memory."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="openai",
        generation_func=_openai_generation_adapter,
        mcp_instance=mcp,
        temperature=temperature,
        files=files,
        max_output_tokens=max_output_tokens,
        enable_logprobs=enable_logprobs,
        top_logprobs=top_logprobs,
        system_prompt=system_prompt,
    )


@mcp.tool(
    description="Delegates image analysis to external OpenAI vision AI service on behalf of the user. Returns OpenAI's verbatim visual analysis to assist the user."
)
def analyze_image(
    prompt: str = Field(
        ...,
        description="The user's question about the images to delegate to external OpenAI vision AI service.",
    ),
    output_file: str = Field(
        default="-",
        description="File path to save OpenAI's visual analysis. Use '-' for standard output.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of image file paths or base64 encoded strings to be analyzed.",
    ),
    focus: str = Field(
        default="general",
        description="The area of focus for the analysis (e.g., 'ocr', 'objects'). This enhances the prompt to guide the model.",
    ),
    model: str = Field(
        default="gpt-4o", description="The OpenAI vision model to use (e.g., 'gpt-4o')."
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with OpenAI AI service (distinct from your conversation with the user).",
    ),
    max_output_tokens: int = Field(
        default=0,
        description="The maximum number of tokens to generate in the response. 0 means use the model's default maximum.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external OpenAI AI service. Remembered for this conversation thread.",
    ),
) -> LLMResult:
    """Analyze images with OpenAI vision model."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="openai",
        generation_func=_openai_image_analysis_adapter,
        mcp_instance=mcp,
        images=files,
        focus=focus,
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
    )


def _openai_image_generation_adapter(prompt: str, model: str, **kwargs) -> dict:
    """OpenAI-specific image generation function with comprehensive metadata extraction."""
    # Extract parameters for metadata
    size = kwargs.get("size", "1024x1024")
    quality = kwargs.get("quality", "standard")

    params = {"model": model, "prompt": prompt, "size": size, "n": 1}
    if model == "dall-e-3":
        params["quality"] = quality

    response = client.images.generate(**params)
    image = response.data[0]

    # Download the image
    with httpx.Client() as http_client:
        image_response = http_client.get(image.url)
        image_response.raise_for_status()
        image_bytes = image_response.content

    # Extract comprehensive metadata
    openai_metadata = {
        "background": getattr(response, "background", None),
        "output_format": getattr(response, "output_format", None),
        "usage": getattr(response, "usage", None),
    }

    return {
        "image_bytes": image_bytes,
        "generation_timestamp": response.created,
        "enhanced_prompt": image.revised_prompt or "",
        "original_prompt": prompt,
        "requested_size": size,
        "requested_quality": quality,
        "requested_format": "png",  # OpenAI always returns PNG
        "mime_type": "image/png",
        "original_url": image.url,
        "openai_metadata": openai_metadata,
    }


@mcp.tool(
    description="Delegates image generation to external OpenAI DALL-E service on behalf of the user. Returns the generated image file path to assist the user."
)
def generate_image(
    prompt: str = Field(
        ...,
        description="The user's detailed description to send to external DALL-E AI service for image generation.",
    ),
    model: str = Field(
        default="dall-e-3",
        description="The DALL-E model to use for image generation (e.g., 'dall-e-3', 'dall-e-2').",
    ),
    quality: str = Field(
        default="standard",
        description="The quality of the generated image. 'hd' for higher detail, 'standard' for faster generation. Only applies to dall-e-3.",
    ),
    size: str = Field(
        default="1024x1024",
        description="The dimensions of the image. Options vary by model: '1024x1024', '1792x1024', '1024x1792' for DALL-E 3.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with image generation AI service (for prompt history tracking).",
    ),
) -> ImageGenerationResult:
    """Generate images with DALL-E."""
    return process_image_generation(
        prompt=prompt,
        agent_name=agent_name,
        model=model,
        provider="openai",
        generation_func=_openai_image_generation_adapter,
        mcp_instance=mcp,
        quality=quality,
        size=size,
    )


def _calculate_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two embedding vectors."""
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    dot_product = np.dot(vec1_np, vec2_np)
    norm_product = np.linalg.norm(vec1_np) * np.linalg.norm(vec2_np)
    return dot_product / norm_product


@mcp.tool(
    description="Generates embedding vectors for text. Supports v3 model 'dimensions' param."
)
def get_embeddings(
    contents: str | list[str] = Field(
        ...,
        description="A single text string or a list of text strings to be converted into embedding vectors.",
    ),
    model: str = Field(
        default=DEFAULT_EMBEDDING_MODEL,
        description="The embedding model to use (e.g., 'text-embedding-3-small').",
    ),
    dimensions: int = Field(
        default=0,
        description="The desired size of the output embedding vector. If 0, the model's default is used. Only for v3 embedding models.",
    ),
) -> list[EmbeddingResult]:
    """Generates embeddings for one or more text strings."""
    if isinstance(contents, str):
        contents = [contents]

    if not contents:
        raise ValueError("Contents list cannot be empty.")

    params = {"model": model, "input": contents}

    # Only add dimensions parameter for v3 models
    if dimensions > 0 and "3" in model:
        params["dimensions"] = dimensions

    # Direct, fail-fast API call
    response = client.embeddings.create(**params)

    # Direct access - trust the response structure
    return [EmbeddingResult(embedding=item.embedding) for item in response.data]


@mcp.tool(
    description="Calculates cosine similarity between two texts. Returns score from -1.0 to 1.0."
)
def calculate_similarity(
    text1: str = Field(..., description="The first text string for comparison."),
    text2: str = Field(..., description="The second text string for comparison."),
    model: str = Field(
        default=DEFAULT_EMBEDDING_MODEL,
        description="The embedding model to use for generating vectors for similarity calculation.",
    ),
) -> SimilarityResult:
    """Calculates the cosine similarity between two texts."""
    if not text1 or not text2:
        raise ValueError("Both text1 and text2 must be provided.")

    embeddings = get_embeddings(contents=[text1, text2], model=model, dimensions=0)

    if len(embeddings) != 2:
        raise RuntimeError("Failed to generate embeddings for both texts.")

    similarity = _calculate_cosine_similarity(
        embeddings[0].embedding, embeddings[1].embedding
    )

    return SimilarityResult(similarity=similarity)


@mcp.tool(
    description="Creates a semantic index from document files by generating and saving embeddings."
)
def index_documents(
    document_paths: list[str] = Field(
        ...,
        description="A list of file paths to the text documents that need to be indexed.",
    ),
    output_index_path: str = Field(
        ..., description="The file path where the resulting JSON index will be saved."
    ),
    model: str = Field(
        default=DEFAULT_EMBEDDING_MODEL,
        description="The embedding model to use for creating the document index.",
    ),
) -> IndexResult:
    """Creates a semantic index from document files."""
    indexed_data = []
    batch_size = EMBEDDING_BATCH_SIZE

    for i in range(0, len(document_paths), batch_size):
        batch_paths = document_paths[i : i + batch_size]
        batch_contents = []
        valid_paths = []

        for doc_path_str in batch_paths:
            doc_path = Path(doc_path_str)
            # If path is not a file, .read_text() will raise an error. This is desired.
            batch_contents.append(doc_path.read_text(encoding="utf-8"))
            valid_paths.append(doc_path_str)

        if not batch_contents:
            continue

        embedding_results = get_embeddings(
            contents=batch_contents, model=model, dimensions=0
        )

        for path, emb_result in zip(valid_paths, embedding_results, strict=True):
            indexed_data.append(
                DocumentIndex(path=path, embedding=emb_result.embedding)
            )

    # Save the index to a file
    index_file = Path(output_index_path)
    index_file.parent.mkdir(parents=True, exist_ok=True)
    with open(index_file, "w") as f:
        json.dump([item.model_dump() for item in indexed_data], f, indent=2)

    return IndexResult(
        index_path=str(index_file),
        files_indexed=len(indexed_data),
        message=f"Successfully indexed {len(indexed_data)} files to {index_file}.",
    )


@mcp.tool(
    description="Searches a document index with a query. Returns a ranked list of docs by similarity."
)
def search_documents(
    query: str = Field(..., description="The search query to find relevant documents."),
    index_path: str = Field(
        ...,
        description="The file path of the pre-computed JSON document index to search against.",
    ),
    top_k: int = Field(
        default=5, description="The number of top matching documents to return."
    ),
    model: str = Field(
        default=DEFAULT_EMBEDDING_MODEL,
        description="The embedding model to use for the query. Should match the model used to create the index.",
    ),
) -> list[SearchResult]:
    """Searches a document index for the most relevant documents to a query."""
    index_file = Path(index_path)
    # open() will raise FileNotFoundError. This is the correct behavior.
    with open(index_file) as f:
        indexed_data = json.load(f)

    if not indexed_data:
        return []

    # Get embedding for the query
    query_embedding_result = get_embeddings(contents=query, model=model, dimensions=0)
    query_embedding = query_embedding_result[0].embedding

    # Calculate similarities
    similarities = []
    for item in indexed_data:
        doc_embedding = item["embedding"]
        score = _calculate_cosine_similarity(query_embedding, doc_embedding)
        similarities.append({"path": item["path"], "score": score})

    # Sort by similarity and return top_k
    similarities.sort(key=lambda x: x["score"], reverse=True)

    results = [
        SearchResult(path=item["path"], similarity_score=item["score"])
        for item in similarities[:top_k]
    ]

    return results


@mcp.tool(
    description="Retrieves a catalog of available OpenAI models with their capabilities, pricing, and context windows. Use this to select the best model for a task."
)
def list_models() -> ModelListing:
    """List available OpenAI models with detailed information."""
    # Get models from API for availability checking
    api_models = client.models.list()
    api_model_ids = {m.id for m in api_models.data}

    # Use structured model listing
    return get_structured_model_listing("openai", api_model_ids)


@mcp.tool(
    description="Checks OpenAI Tool server status and API connectivity. Returns version info, model availability, and a list of available functions."
)
def server_info() -> ServerInfo:
    """Get server status and OpenAI configuration."""
    # Test API key by listing models
    models = client.models.list()
    available_models = [
        m.id for m in models.data if m.id.startswith(("gpt", "dall-e", "text-", "o1"))
    ]

    # Add embedding capabilities to the server info
    info = build_server_info(
        provider_name="OpenAI",
        available_models=available_models,
        memory_manager=memory_manager,
        vision_support=True,
        image_generation=True,
    )

    # Manually add embedding capabilities to the server info
    embedding_capabilities = [
        "get_embeddings - Generate embedding vectors for text.",
        "calculate_similarity - Compare two texts for semantic similarity.",
        "index_documents - Create a searchable index from files.",
        "search_documents - Search an index for a query.",
    ]
    info.capabilities.extend(embedding_capabilities)

    return info

```

`src/mcp_handley_lab/llm/shared.py`:

```py
"""Shared utilities for LLM providers."""

import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path

from mcp_handley_lab.common.pricing import calculate_cost
from mcp_handley_lab.llm.common import (
    get_session_id,
    handle_agent_memory,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.shared.models import (
    GroundingMetadata,
    ImageGenerationResult,
    LLMResult,
)


def process_llm_request(
    prompt: str,
    output_file: str,
    agent_name: str,
    model: str,
    provider: str,
    generation_func: Callable,
    mcp_instance,
    **kwargs,
) -> LLMResult:
    """Generic handler for LLM requests that abstracts common patterns."""
    # Input validation
    if not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")
    if not output_file.strip():
        raise ValueError("Output file is required and cannot be empty")
    # Extract system_prompt parameter
    system_prompt = kwargs.pop("system_prompt", None)

    # Store original prompt for memory
    user_prompt = prompt
    history = []
    system_instruction = None
    actual_agent_name = agent_name

    # Handle agent memory with string-based pattern
    use_memory = should_use_memory(agent_name)
    if use_memory:
        if agent_name == "session":
            actual_agent_name = get_session_id(mcp_instance)
        else:
            actual_agent_name = agent_name

        # Get or create agent
        agent = memory_manager.get_agent(actual_agent_name)
        if not agent:
            # Create agent with provided system_prompt
            agent = memory_manager.create_agent(actual_agent_name, system_prompt)
        elif system_prompt is not None:
            # Update agent's system_prompt if provided
            agent.system_prompt = system_prompt
            memory_manager._save_agent(agent)

        # Get conversation history and current system_prompt
        history = agent.get_history()
        system_instruction = agent.system_prompt

    # Handle image analysis specific prompt modification
    if "image_data" in kwargs or "images" in kwargs:
        focus = kwargs.get("focus", "general")
        if focus != "general":
            prompt = f"Focus on {focus} aspects. {prompt}"
        # Add image description for memory
        image_count = 0
        if kwargs.get("image_data"):
            image_count += 1
        if kwargs.get("images"):
            image_count += len(kwargs.get("images", []))
        if image_count > 0:
            user_prompt = f"{user_prompt} [Image analysis: {image_count} image(s)]"

    # Call provider-specific generation function
    response_data = generation_func(
        prompt=prompt,
        model=model,
        history=history,
        system_instruction=system_instruction,
        **kwargs,
    )

    # Extract common response data
    response_text = response_data["text"]
    input_tokens = response_data["input_tokens"]
    output_tokens = response_data["output_tokens"]
    grounding_metadata_dict = response_data.get("grounding_metadata")
    finish_reason = response_data.get("finish_reason", "")
    avg_logprobs = response_data.get("avg_logprobs", 0.0)
    model_version = response_data.get("model_version", "")
    generation_time_ms = response_data.get("generation_time_ms", 0)
    response_id = response_data.get("response_id", "")
    # OpenAI-specific fields
    system_fingerprint = response_data.get("system_fingerprint", "")
    service_tier = response_data.get("service_tier", "")
    completion_tokens_details = response_data.get("completion_tokens_details", {})
    prompt_tokens_details = response_data.get("prompt_tokens_details", {})
    # Claude-specific fields
    stop_sequence = response_data.get("stop_sequence", "")
    cache_creation_input_tokens = response_data.get("cache_creation_input_tokens", 0)
    cache_read_input_tokens = response_data.get("cache_read_input_tokens", 0)
    cost = calculate_cost(model, input_tokens, output_tokens, provider)

    # Handle memory
    if use_memory:
        handle_agent_memory(
            actual_agent_name,
            user_prompt,
            response_text,
            input_tokens,
            output_tokens,
            cost,
            lambda: actual_agent_name,
        )

    # Handle output
    if output_file != "-":
        output_path = Path(output_file)
        output_path.write_text(response_text)

    from mcp_handley_lab.shared.models import UsageStats

    usage_stats = UsageStats(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        model_used=model,
    )

    # Convert grounding metadata dict to GroundingMetadata object
    grounding_metadata = None
    if grounding_metadata_dict:
        grounding_metadata = GroundingMetadata(**grounding_metadata_dict)

    return LLMResult(
        content=response_text,
        usage=usage_stats,
        agent_name=actual_agent_name if use_memory else "",
        grounding_metadata=grounding_metadata,
        finish_reason=finish_reason,
        avg_logprobs=avg_logprobs,
        model_version=model_version,
        generation_time_ms=generation_time_ms,
        response_id=response_id,
        system_fingerprint=system_fingerprint,
        service_tier=service_tier,
        completion_tokens_details=completion_tokens_details,
        prompt_tokens_details=prompt_tokens_details,
        stop_sequence=stop_sequence,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
    )


def should_use_memory(agent_name: str | bool | None) -> bool:
    """Determines if agent memory should be used based on the agent_name parameter."""
    if isinstance(agent_name, bool):
        return agent_name
    if agent_name is None:
        return True
    return agent_name != "" and agent_name.lower() != "false"


def process_image_generation(
    prompt: str,
    agent_name: str,
    model: str,
    provider: str,
    generation_func: Callable,
    mcp_instance,
    **kwargs,
) -> ImageGenerationResult:
    """Generic handler for LLM image generation requests."""
    if not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")

    # Call the provider-specific generation function to get the image
    response_data = generation_func(prompt=prompt, model=model, **kwargs)
    image_bytes = response_data["image_bytes"]
    input_tokens = response_data.get("input_tokens", 0)
    output_tokens = response_data.get("output_tokens", 1)

    file_id = str(uuid.uuid4())[:8]
    filename = f"{provider}_generated_{file_id}.png"
    filepath = Path(tempfile.gettempdir()) / filename
    filepath.write_bytes(image_bytes)

    cost = calculate_cost(
        model, input_tokens, output_tokens, provider, images_generated=1
    )

    handle_agent_memory(
        agent_name,
        f"Generate image: {prompt}",
        f"Generated image saved to {filepath}",
        input_tokens,
        output_tokens,
        cost,
        lambda: get_session_id(mcp_instance),
    )

    file_size = len(image_bytes)

    from mcp_handley_lab.shared.models import UsageStats

    usage_stats = UsageStats(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        model_used=model,
    )

    return ImageGenerationResult(
        message="Image Generated Successfully",
        file_path=str(filepath),
        file_size_bytes=file_size,
        usage=usage_stats,
        agent_name=agent_name if agent_name else "",
        # Metadata from provider response
        generation_timestamp=response_data.get("generation_timestamp", 0),
        enhanced_prompt=response_data.get("enhanced_prompt", ""),
        original_prompt=response_data.get("original_prompt", prompt),
        # Request parameters
        requested_size=response_data.get("requested_size", ""),
        requested_quality=response_data.get("requested_quality", ""),
        requested_format=response_data.get("requested_format", ""),
        aspect_ratio=response_data.get("aspect_ratio", ""),
        # Safety and filtering
        safety_attributes=response_data.get("safety_attributes", {}),
        content_filter_reason=response_data.get("content_filter_reason", ""),
        # Provider-specific metadata
        openai_metadata=response_data.get("openai_metadata", {}),
        gemini_metadata=response_data.get("gemini_metadata", {}),
        # Technical details
        mime_type=response_data.get("mime_type", ""),
        cloud_uri=response_data.get("cloud_uri", ""),
        original_url=response_data.get("original_url", ""),
    )

```

`src/mcp_handley_lab/mathematica/__init__.py`:

```py
# Mathematica MCP Tool
```

`src/mcp_handley_lab/mathematica/cli.py`:

```py
#!/usr/bin/env python3
"""
Mathematica MCP Tool CLI Entry Point

Command-line interface for the Mathematica MCP server.
"""

import sys
import logging
from .tool import mcp

def main():
    """Main entry point for the Mathematica MCP tool."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        mcp.run()
    except KeyboardInterrupt:
        print("\n👋 Mathematica MCP server stopped")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error running Mathematica MCP server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

`src/mcp_handley_lab/mathematica/tool.py`:

```py
"""
Mathematica MCP Tool - Production Version

Provides MCP tools for interacting with Wolfram Mathematica through a persistent kernel session.
Enables LLM-driven mathematical workflows with true REPL behavior and variable persistence.
"""

import logging
import threading
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import Field, BaseModel
from wolframclient.evaluation import WolframLanguageSession
from wolframclient.language import wlexpr, wl

from mcp_handley_lab.shared.models import OperationResult, ServerInfo

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Mathematica Tool")

# Global session management with thread safety
_session: Optional[WolframLanguageSession] = None
_evaluation_count = 0
_session_lock = threading.RLock()
_kernel_path = '/usr/bin/WolframKernel'
_result_history: List[Any] = []  # Store all results for %, %%, %n references
_input_history: List[str] = []   # Store input expressions for notebook reconstruction


class MathematicaResult(BaseModel):
    """Result of a Mathematica evaluation."""
    result: str = Field(description="The formatted result of the evaluation")
    raw_result: str = Field(description="The raw Wolfram Language result")
    success: bool = Field(description="Whether the evaluation succeeded")
    evaluation_count: int = Field(description="Number of evaluations in this session")
    expression: str = Field(description="The original expression that was evaluated")
    format_used: str = Field(description="The output format that was used")
    error: Optional[str] = Field(None, description="Error message if evaluation failed")
    note: Optional[str] = Field(None, description="Additional notes about the evaluation")


class SessionInfo(BaseModel):
    """Information about the current Mathematica session."""
    active: bool = Field(description="Whether the kernel session is active")
    evaluation_count: int = Field(description="Number of evaluations performed")
    version: Optional[str] = Field(None, description="Wolfram kernel version")
    memory_used: Optional[str] = Field(None, description="Memory currently in use")
    kernel_id: Optional[str] = Field(None, description="Kernel process ID")
    kernel_path: str = Field(description="Path to the Wolfram kernel")
    uptime_seconds: Optional[float] = Field(None, description="Session uptime in seconds")
    last_evaluation: Optional[str] = Field(None, description="Last expression evaluated")


def _get_session() -> WolframLanguageSession:
    """Get or create the global Wolfram session with thread safety."""
    global _session, _evaluation_count
    
    with _session_lock:
        if _session is None:
            try:
                logger.info("Starting Wolfram kernel session...")
                _session = WolframLanguageSession(_kernel_path)
                _evaluation_count = 0
                
                # Initialize session settings for better REPL behavior
                _session.evaluate(wlexpr('$HistoryLength = 100'))
                _session.evaluate(wlexpr('SetOptions[$Output, PageWidth -> Infinity]'))
                
                # Note: % references have proven unreliable in wolframclient
                # Instead, we provide Python-side state management for chaining operations
                logger.info("✅ Session configured for LLM workflows with Python-side state management")
                
                logger.info("✅ Wolfram session started successfully")
                
            except Exception as e:
                logger.error(f"❌ Failed to start Wolfram session: {e}")
                _session = None
                raise RuntimeError(f"Could not start Wolfram session: {e}")
    
    return _session


def _to_input_form(expr_obj) -> str:
    """
    Convert a Wolfram expression object back to parseable InputForm string.
    
    This is crucial because str(expr_obj) gives Python representation like 'wl.Plus(...)'
    which the kernel cannot parse. InputForm gives us parseable Wolfram code.
    """
    if expr_obj is None:
        return "Null"
    
    # Use the session to convert to InputForm string
    with _session_lock:
        if _session is not None:
            try:
                # Use ToString with InputForm to get a proper string representation
                input_form_str = _session.evaluate(wlexpr(f'ToString[{expr_obj}, InputForm]'))
                return str(input_form_str)
            except Exception as e:
                logger.warning(f"Failed to convert to InputForm: {e}")
                return str(expr_obj)
    return str(expr_obj)


def _format_result(session: WolframLanguageSession, raw_result: Any, output_format: str) -> str:
    """Format a raw Wolfram result into a string based on the desired format."""
    if output_format == "Raw":
        return str(raw_result)
    
    # For other formats, ask the kernel to convert to string
    format_func = {
        "InputForm": "InputForm",
        "OutputForm": "OutputForm", 
        "TeXForm": "TeXForm"
    }.get(output_format)
    
    if format_func:
        if format_func == "TeXForm":
            return str(session.evaluate(wlexpr(f'ToString[TeXForm[{raw_result}]]')))
        return str(session.evaluate(wlexpr(f'ToString[{raw_result}, {format_func}]')))
    
    return str(raw_result)


def _preprocess_percent_references(expression: str) -> str:
    """
    Robust preprocessing of % references using regex-based substitution.
    
    Handles:
    - % (last result)
    - %% (second to last)
    - %%% (third to last, etc.)
    - %n (result n, e.g., %5)
    
    This bypasses wolframclient's problematic % handling by doing substitution
    in Python before the expression is parsed.
    """
    global _result_history
    
    if not _result_history or '%' not in expression:
        return expression
    
    processed_expression = expression
    
    # Handle %n references (e.g., %5, %12)
    def replace_numbered(match):
        index = int(match.group(1))
        if 1 <= index <= len(_result_history):
            # Wolfram is 1-indexed, Python lists are 0-indexed
            result_obj = _result_history[index - 1]
            return f"({_to_input_form(result_obj)})"
        return match.group(0)  # Return original if index out of bounds
    
    processed_expression = re.sub(r'%(\d+)', replace_numbered, processed_expression)
    
    # Handle %%... references (%, %%, %%%)
    def replace_sequential(match):
        count = len(match.group(0))
        if 1 <= count <= len(_result_history):
            # % is history[-1], %% is history[-2], etc.
            result_obj = _result_history[-count]
            return f"({_to_input_form(result_obj)})"
        return match.group(0)  # Return original if not enough history
    
    # Match one or more % not preceded by a digit
    processed_expression = re.sub(r'(?<!\d)(%)+', replace_sequential, processed_expression)
    
    if processed_expression != expression:
        logger.debug(f"Preprocessed % references: '{expression}' -> '{processed_expression}'")
    
    return processed_expression


def _ensure_session_active() -> bool:
    """Ensure the session is active and responsive."""
    global _session
    
    with _session_lock:
        if _session is None:
            return False
        
        try:
            # Test session responsiveness with a simple evaluation
            _session.evaluate(wlexpr('1'))
            return True
        except Exception as e:
            logger.warning(f"Session unresponsive, will restart: {e}")
            _session = None
            return False


@mcp.tool()
def evaluate(
    expression: str = Field(description="Wolfram Language expression to evaluate"),
    output_format: str = Field(
        default="Raw", 
        description=(
            "Output format for the result. "
            "'Raw': Python's string representation of the result object. "
            "'InputForm': A string of valid Wolfram Language code. "
            "'OutputForm': Standard human-readable formatted output. "
            "'TeXForm': LaTeX representation for documents."
        )
    ),
    store_context: Optional[str] = Field(
        None,
        description="Optional key to store this result for later reference"
    )
) -> MathematicaResult:
    """
    Evaluate a Wolfram Language expression in the persistent session.
    
    This is the main tool for LLM-driven mathematical workflows. The session persists
    across multiple tool calls, allowing for true REPL behavior where variables,
    functions, and results are maintained between evaluations.
    
    Examples:
    - Basic math: "2 + 2"
    - Define variables: "x = 5; y = x^2"
    - Mathematical operations: "Factor[x^4 - 1]"
    - Solve equations: "Solve[x^2 + 3*x + 2 == 0, x]"
    - Integration: "Integrate[x^2 + 3*x + 1, x]"
    - Use persistent variables: "Expand[myExpression]"
    
    Note: % references are fully supported through Python-side preprocessing.
    Use % for last result, %% for second-to-last, %n for result n, etc.
    
    The session maintains all variables and definitions across calls, enabling
    complex mathematical workflows where LLMs can build on previous calculations.
    """
    global _evaluation_count
    
    with _session_lock:
        try:
            # Ensure session is active
            if not _ensure_session_active():
                session = _get_session()
            else:
                session = _session
            
            logger.debug(f"Evaluating: {expression}")
            
            # Preprocess % references before evaluation
            processed_expression = _preprocess_percent_references(expression)
            
            # Evaluate the processed expression
            raw_result = session.evaluate(wlexpr(processed_expression))
            _evaluation_count += 1
            
            # Store result in history for % references
            global _result_history, _input_history
            _result_history.append(raw_result)
            _input_history.append(expression)  # Store input for notebook reconstruction
            
            # Format the result based on requested format
            formatted_result = _format_result(session, raw_result, output_format)
            
            logger.debug(f"✅ Evaluation successful: {formatted_result}")
            
            return MathematicaResult(
                result=formatted_result,
                raw_result=str(raw_result),
                success=True,
                evaluation_count=_evaluation_count,
                expression=expression,
                format_used=output_format
            )
            
        except Exception as e:
            logger.error(f"❌ Evaluation failed: {e}")
            return MathematicaResult(
                result=f"Error: {str(e)}",
                raw_result="",
                success=False,
                evaluation_count=_evaluation_count,
                expression=expression,
                format_used=output_format if isinstance(output_format, str) else "Raw",
                error=str(e)
            )


@mcp.tool()
def session_info() -> SessionInfo:
    """
    Get comprehensive information about the current Mathematica session.
    
    Returns details about the active session including version, memory usage,
    evaluation count, and session health. Useful for monitoring session state
    and debugging mathematical workflows.
    """
    global _evaluation_count
    
    with _session_lock:
        try:
            if _session is None:
                return SessionInfo(
                    active=False,
                    evaluation_count=_evaluation_count,
                    kernel_path=_kernel_path
                )
            
            # Get session details from Wolfram
            version = str(_session.evaluate(wlexpr('$Version')))
            memory_used = str(_session.evaluate(wlexpr('MemoryInUse[]')))
            kernel_id = str(_session.evaluate(wlexpr('$ProcessID')))
            session_id = str(_session.evaluate(wlexpr('$SessionID')))
            
            return SessionInfo(
                active=True,
                evaluation_count=_evaluation_count,
                version=version,
                memory_used=memory_used,
                kernel_id=kernel_id,
                kernel_path=_kernel_path
            )
            
        except Exception as e:
            logger.error(f"Failed to get session info: {e}")
            return SessionInfo(
                active=False,
                evaluation_count=_evaluation_count,
                kernel_path=_kernel_path
            )


@mcp.tool()
def clear_session(
    keep_builtin: bool = Field(
        True,
        description="If True, preserve built-in Wolfram functions. If False, clear everything."
    )
) -> OperationResult:
    """
    Clear user-defined variables and symbols from the session.
    
    This resets the mathematical workspace while keeping the kernel running
    and preserving built-in Wolfram functions. Useful for starting fresh
    calculations or clearing memory when the session becomes cluttered.
    
    Args:
        keep_builtin: If True (default), only clears user-defined symbols.
                     If False, performs a more complete reset.
    
    Returns:
        Operation result with success status and session information.
    """
    global _evaluation_count
    
    with _session_lock:
        try:
            if not _ensure_session_active():
                session = _get_session()
            else:
                session = _session
            
            if keep_builtin:
                # Clear only user-defined symbols in Global context
                session.evaluate(wlexpr('ClearAll[Evaluate[Names["Global`*"]]]'))
                message = "Cleared user-defined variables"
            else:
                # More aggressive clearing
                session.evaluate(wlexpr('ClearAll["Global`*"]'))
                session.evaluate(wlexpr('$HistoryLength = 100'))
                message = "Cleared all symbols and reset session"
            
            # Clear Python-side history in both cases
            global _result_history, _input_history
            _result_history.clear()
            _input_history.clear()
            
            logger.info(f"✅ {message}")
            
            return OperationResult(
                status="success",
                message=message,
                data={"evaluation_count": _evaluation_count}
            )
            
        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
            return OperationResult(
                status="error",
                message=f"Failed to clear session: {str(e)}",
                data={"error": str(e)}
            )


@mcp.tool()
def restart_kernel() -> OperationResult:
    """
    Completely restart the Mathematica kernel.
    
    This terminates the current kernel process and starts a fresh one.
    All variables, functions, and session state will be lost. Use this
    when the kernel becomes unresponsive or when you need a completely
    clean mathematical environment.
    
    Returns:
        Operation result with success status and new session information.
    """
    global _session, _evaluation_count, _result_history
    
    with _session_lock:
        try:
            # Terminate existing session
            if _session:
                try:
                    _session.terminate()
                    logger.info("Previous session terminated")
                except Exception as e:
                    logger.warning(f"Error terminating previous session: {e}")
            
            # Reset state
            _session = None
            _evaluation_count = 0
            _result_history.clear()
            _input_history.clear()
            
            # Start new session
            new_session = _get_session()
            
            return OperationResult(
                status="success",
                message="Kernel restarted successfully",
                data={
                    "evaluation_count": _evaluation_count,
                    "kernel_path": _kernel_path
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to restart kernel: {e}")
            return OperationResult(
                status="error",
                message=f"Failed to restart kernel: {str(e)}",
                data={"error": str(e)}
            )


@mcp.tool()
def apply_to_last(
    operation: str = Field(description="Wolfram Language operation to apply to the last result (e.g., 'Factor', 'Expand', 'Solve[# == 0, x]')")
) -> MathematicaResult:
    """
    Apply a Wolfram Language operation to the last evaluation result.
    
    This tool provides a reliable way to chain operations. Use '#' as a placeholder
    for the last result within the operation string. For simple function names like
    'Factor', the '#' is not needed.
    
    Examples:
    - "Factor" - factors the last result
    - "Expand" - expands the last result  
    - "Solve[# == 0, x]" - solves equation where last result equals 0 (recommended pattern)
    - "Plot[#, {x, -2, 2}]" - plots the last result
    
    Alternative to % references for operation chaining.
    """
    global _evaluation_count, _result_history
    
    with _session_lock:
        try:
            if not _ensure_session_active():
                session = _get_session()
            else:
                session = _session
            
            if not _result_history:
                return MathematicaResult(
                    result="Error: No previous result available",
                    raw_result="",
                    success=False,
                    evaluation_count=_evaluation_count,
                    expression=operation,
                    format_used="Raw",
                    error="No previous result stored",
                    note="Use the 'evaluate' tool first to generate a result"
                )
            
            last_result = _result_history[-1]
            logger.debug(f"Applying '{operation}' to last result: {last_result}")
            
            # Apply the operation to the last result
            last_result_str = _to_input_form(last_result)
            
            if '#' in operation:
                operation_expr = operation.replace('#', last_result_str)
            else:
                operation_expr = f'{operation}[{last_result_str}]'
            
            raw_result = session.evaluate(wlexpr(operation_expr))
            _evaluation_count += 1
            _result_history.append(raw_result)  # Add to history
            global _input_history
            _input_history.append(f"{operation} applied to previous result")  # Store operation for notebook
            
            # Use Raw format by default for consistency
            formatted_result = str(raw_result)
            
            logger.debug(f"✅ Applied operation successfully: {formatted_result}")
            
            return MathematicaResult(
                result=formatted_result,
                raw_result=str(raw_result),
                success=True,
                evaluation_count=_evaluation_count,
                expression=f"{operation} applied to previous result",
                format_used="Raw",
                note="Result stored for further chaining operations"
            )
            
        except Exception as e:
            logger.error(f"❌ Operation application failed: {e}")
            return MathematicaResult(
                result=f"Error: {str(e)}",
                raw_result="",
                success=False,
                evaluation_count=_evaluation_count,
                expression=operation,
                format_used="Raw",
                error=str(e)
            )


@mcp.tool()
def convert_latex(
    latex_expression: str = Field(description="LaTeX mathematical expression to convert"),
    output_format: str = Field(
        default="OutputForm", 
        description=(
            "Output format for the converted result. "
            "'Raw': Python's string representation of the result object. "
            "'InputForm': A string of valid Wolfram Language code. "
            "'OutputForm': Standard human-readable formatted output. "
            "'TeXForm': LaTeX representation for documents."
        )
    )
) -> MathematicaResult:
    """
    Convert LaTeX mathematical expressions to Wolfram Language and evaluate them.
    
    This tool attempts to parse LaTeX mathematical notation (common in ArXiv papers)
    and convert it to executable Wolfram Language expressions. Useful for processing
    mathematical content from academic papers and integrating them into workflows.
    
    Examples:
    - Simple: "x^2 + 3x + 1"
    - Fractions: "\\frac{x^2}{2} + \\frac{3x}{4}"
    - Integrals: "\\int x^2 dx"
    - Sums: "\\sum_{i=1}^{n} i^2"
    - Limits: "\\lim_{x \\to 0} \\frac{\\sin x}{x}"
    
    Note: Works best for standard mathematical notation. LaTeX parsing has limitations
    and may struggle with complex layouts or custom macros. Complex expressions may need manual conversion.
    """
    global _evaluation_count
    
    with _session_lock:
        try:
            if not _ensure_session_active():
                session = _get_session()
            else:
                session = _session
            
            # Attempt to convert LaTeX to Wolfram Language
            try:
                # First try direct ToExpression with TeXForm
                conversion_expr = f'ToExpression["{latex_expression}", TeXForm]'
                raw_result = session.evaluate(wlexpr(conversion_expr))
                _evaluation_count += 1
                
                logger.debug(f"✅ LaTeX conversion successful: {raw_result}")
                
            except Exception as e:
                logger.info(f"Direct LaTeX parsing failed, trying manual conversion: {e}")
                
                # Try manual preprocessing for common LaTeX patterns
                manual_expr = (latex_expression
                              .replace(r'\frac{', 'Divide[')
                              .replace(r'}{', ',')
                              .replace(r'}', ']')
                              .replace(r'\int', 'Integrate')
                              .replace(r'\sum', 'Sum')
                              .replace(r'\lim', 'Limit')
                              .replace(r'\sin', 'Sin')
                              .replace(r'\cos', 'Cos')
                              .replace(r'\tan', 'Tan')
                              .replace(r'\log', 'Log')
                              .replace(r'\exp', 'Exp'))
                
                raw_result = session.evaluate(wlexpr(f'ToExpression["{manual_expr}"]'))
                _evaluation_count += 1
                
                logger.debug(f"✅ Manual LaTeX conversion successful: {raw_result}")
            
            # Format the result
            formatted_result = _format_result(session, raw_result, output_format)
            
            return MathematicaResult(
                result=formatted_result,
                raw_result=str(raw_result),
                success=True,
                evaluation_count=_evaluation_count,
                expression=f"LaTeX: {latex_expression}",
                format_used=output_format
            )
            
        except Exception as e:
            logger.error(f"LaTeX conversion failed: {e}")
            return MathematicaResult(
                result=f"Error converting LaTeX: {str(e)}",
                raw_result="",
                success=False,
                evaluation_count=_evaluation_count,
                expression=latex_expression,
                format_used=output_format,
                error=str(e)
            )


@mcp.tool()
def save_notebook(
    filepath: str = Field(description="Path where to save the notebook file"),
    format: str = Field("md", description="Output format: 'md' (markdown), 'wl' (wolfram script), 'wls' (wolfram script with outputs)"),
    title: str = Field("Mathematica Session", description="Title for the saved notebook")
) -> OperationResult:
    """
    Save the current session with complete input/output history in human-readable format.
    
    Preserves all evaluations, results, and session state for restoration after Claude restarts.
    The saved notebook contains both the input expressions and their corresponding outputs.
    
    Supported formats:
    - 'md': GitHub-friendly markdown with In/Out blocks (most readable)
    - 'wl': Executable Wolfram Language script (for restoration) 
    - 'wls': Wolfram script with output comments (readable + executable)
    """
    try:
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Choose format handler
        if format == "md":
            result = _save_as_markdown(filepath, title, timestamp)
        elif format == "wl":
            result = _save_as_wolfram_script(filepath, title, timestamp)
        elif format == "wls":
            result = _save_as_wolfram_script_with_outputs(filepath, title, timestamp)
        else:
            return OperationResult(
                status="error",
                message=f"Unsupported format: {format}. Use 'md', 'wl', or 'wls'.",
                data={"supported_formats": ["md", "wl", "wls"]}
            )
        
        return OperationResult(
            status="success",
            message=f"Notebook saved to {filepath} in {format} format",
            data={
                "filepath": filepath,
                "format": format,
                "evaluations": len(_input_history),
                "timestamp": timestamp
            }
        )
        
    except Exception as e:
        return OperationResult(
            status="error",
            message=f"Failed to save notebook: {str(e)}",
            data={"filepath": filepath, "format": format}
        )


def _save_as_markdown(filepath: str, title: str, timestamp: str) -> dict:
    """Save session as GitHub-friendly markdown with In/Out blocks."""
    global _input_history, _result_history, _evaluation_count
    
    content = f"""# {title}
*Generated: {timestamp}*  
*Kernel: Mathematica 14.2.1*  
*Evaluations: {_evaluation_count}*

"""
    
    # Generate In/Out pairs from our tracked history
    for i in range(len(_input_history)):
        input_expr = _input_history[i]
        if i < len(_result_history):
            output_result = _format_result(_get_session(), _result_history[i], "OutputForm")
        else:
            output_result = "No output"
        
        content += f"""## Evaluation {i+1}
```mathematica
In[{i+1}]:= {input_expr}
Out[{i+1}]= {output_result}
```

"""
    
    # Add session information
    content += """## Session State
Current variables and functions are preserved in this session.
Use `Names["Global`*"]` in Mathematica to see all defined symbols.

## Restoration
To restore this session, copy and paste the input lines into a new Mathematica notebook.
"""
    
    # Write to file
    Path(filepath).write_text(content)
    return {"format": "markdown"}


def _save_as_wolfram_script(filepath: str, title: str, timestamp: str) -> dict:
    """Save session as executable Wolfram Language script."""
    global _input_history, _evaluation_count
    
    content = f"""(* {title} *)
(* Generated: {timestamp} *)
(* Evaluations: {_evaluation_count} *)

"""
    
    # Add all input expressions as executable code
    for i, input_expr in enumerate(_input_history):
        content += f"""(* Evaluation {i+1} *)
{input_expr};

"""
    
    content += """(* End of session *)
Print["Session restored successfully! Variables: ", Length[Names["Global`*"]]];
"""
    
    Path(filepath).write_text(content)
    return {"format": "wolfram_language"}


def _save_as_wolfram_script_with_outputs(filepath: str, title: str, timestamp: str) -> dict:
    """Save session as Wolfram script with output comments."""
    global _input_history, _result_history, _evaluation_count
    
    content = f"""(* {title} *)
(* Generated: {timestamp} *)
(* Evaluations: {_evaluation_count} *)

"""
    
    # Add input/output pairs with comments
    for i in range(len(_input_history)):
        input_expr = _input_history[i]
        if i < len(_result_history):
            output_result = str(_result_history[i])
        else:
            output_result = "No output"
        
        content += f"""(* Evaluation {i+1} *)
{input_expr};
(* Result: {output_result} *)

"""
    
    content += """(* End of session *)
Print["Session restored with outputs preserved in comments"];
Print["Variables available: ", Names["Global`*"]];
"""
    
    Path(filepath).write_text(content)
    return {"format": "wolfram_language_with_outputs"}


@mcp.tool()
def server_info() -> ServerInfo:
    """
    Get comprehensive information about the Mathematica MCP server.
    
    Returns server status, capabilities, version information, and dependency status.
    Useful for debugging and verifying server health.
    """
    try:
        # Check if Wolfram kernel is available
        kernel_available = Path(_kernel_path).exists()
        
        # Get session status
        session_active = _session is not None and _ensure_session_active()
        
        dependencies = {
            "wolframclient": "available",
            "wolfram_kernel": "available" if kernel_available else "not found",
            "session_active": "yes" if session_active else "no"
        }
        
        status = "active" if kernel_available and session_active else "degraded"
        
        capabilities = [
            "evaluate - Evaluate Wolfram Language expressions with persistent session",
            "apply_to_last - Apply operations to the last evaluation result (alternative to % references)",
            "session_info - Get detailed session information and statistics", 
            "clear_session - Clear user-defined variables while keeping kernel alive",
            "restart_kernel - Completely restart the Wolfram kernel process",
            "convert_latex - Convert LaTeX mathematical expressions to Wolfram Language",
            "server_info - Get server status and capability information"
        ]
        
        return ServerInfo(
            name="Mathematica Tool",
            version="1.0.0",
            status=status,
            capabilities=capabilities,
            dependencies=dependencies
        )
        
    except Exception as e:
        logger.error(f"Failed to get server info: {e}")
        return ServerInfo(
            name="Mathematica Tool",
            version="1.0.0", 
            status="error",
            capabilities=[],
            dependencies={"error": str(e)}
        )


# Initialize session when module loads (like the working simple_server.py)
try:
    _get_session()
    logger.info("✅ Mathematica MCP tool initialized successfully")
except Exception as e:
    logger.warning(f"Could not initialize Mathematica session on startup: {e}")


if __name__ == "__main__":
    mcp.run()
```

`src/mcp_handley_lab/py2nb/__init__.py`:

```py
"""py2nb conversion tool for bidirectional Python script ↔ Jupyter notebook conversion."""

```

`src/mcp_handley_lab/py2nb/converter.py`:

```py
"""Core notebook conversion logic for bidirectional Python script ↔ Jupyter notebook conversion."""

import json
from pathlib import Path
from typing import Any

import nbformat.v4

# Comment syntax patterns from original py2nb
CELL_SPLIT_CHARS = ["#-", "# -"]
MARKDOWN_CHARS = ["#|", "# |"]
COMMAND_CHARS = ["#!", "# !", "#%", "# %"]


def _str_starts_with(string: str, options: list[str]) -> bool:
    """Check if string starts with any of the given options."""
    return any(string.startswith(opt) for opt in options)


def _get_comment_type(line: str) -> str | None:
    """Determine the type of comment based on prefix."""
    if _str_starts_with(line, COMMAND_CHARS):
        return "command"
    elif _str_starts_with(line, MARKDOWN_CHARS):
        return "markdown"
    elif _str_starts_with(line, CELL_SPLIT_CHARS):
        return "split"
    return None


def _extract_content(line: str, comment_type: str) -> str:
    """Extract content from comment line based on type."""
    if comment_type == "command":
        # Find first ! or % and return the command marker plus everything after it
        if "!" in line:
            return "!" + line[line.index("!") + 1 :].lstrip()
        elif "%" in line:
            return "%" + line[line.index("%") + 1 :].lstrip()
    elif comment_type == "markdown":
        # Find first | and return everything after it
        return line[line.index("|") + 1 :]
    return ""


def _new_cell(nb: Any, cell_content: str, cell_type: str = "code") -> str:
    """Create a new cell with proper metadata."""
    cell_content = cell_content.strip()
    if cell_content:
        if cell_type == "markdown":
            cell = nbformat.v4.new_markdown_cell(cell_content)
        elif cell_type == "command":
            cell = nbformat.v4.new_code_cell(cell_content)
            cell.metadata.update({"tags": ["command"], "collapsed": False})
        else:  # code cell
            cell = nbformat.v4.new_code_cell(cell_content)

        nb.cells.append(cell)
    return ""


def _validate_notebook(nb: Any) -> None:
    """Validate notebook structure and fix common issues."""
    for cell in nb.cells:
        # Remove auto-generated cell ids for consistent format
        if "id" in cell:
            del cell["id"]

        # Ensure proper cell structure
        if not hasattr(cell, "metadata"):
            cell.metadata = {}

        if cell.cell_type == "code":
            # Ensure code cells have required fields
            if not hasattr(cell, "execution_count"):
                cell.execution_count = None
            if not hasattr(cell, "outputs"):
                cell.outputs = []
        elif cell.cell_type == "markdown":
            # Ensure markdown cells don't have code cell fields
            if hasattr(cell, "execution_count"):
                delattr(cell, "execution_count")
            if hasattr(cell, "outputs"):
                delattr(cell, "outputs")

        # Ensure source is a list
        if isinstance(cell.source, str):
            cell.source = cell.source.splitlines(True)


def python_to_notebook(script_path: str, output_path: str | None = None) -> str:
    """Convert Python script to Jupyter notebook."""
    script_path = Path(script_path)

    if not script_path.exists():
        raise FileNotFoundError(f"Script file not found: {script_path}")

    # Determine output path
    if output_path:
        notebook_path = Path(output_path)
        if notebook_path.suffix != ".ipynb":
            notebook_path = notebook_path.with_suffix(".ipynb")
    else:
        notebook_path = script_path.with_suffix(".ipynb")

    with open(script_path, encoding="utf-8") as f:
        # Initialize cells and notebook
        markdown_cell = ""
        code_cell = ""
        command_cell = ""
        nb = nbformat.v4.new_notebook()

        # Set notebook metadata
        nb.metadata.update(
            {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3",
                },
                "language_info": {
                    "codemirror_mode": {"name": "ipython", "version": 3},
                    "file_extension": ".py",
                    "mimetype": "text/x-python",
                    "name": "python",
                    "nbconvert_exporter": "python",
                    "pygments_lexer": "ipython3",
                    "version": "3.8.0",
                },
            }
        )

        # Set consistent nbformat version
        nb.nbformat = 4
        nb.nbformat_minor = 2

        for line in f:
            comment_type = _get_comment_type(line)

            if comment_type:
                # Finish current code cell before processing comment
                code_cell = _new_cell(nb, code_cell, "code")

                if comment_type == "markdown":
                    # Add to markdown cell
                    markdown_cell += _extract_content(line, "markdown")
                elif comment_type == "command":
                    # Finish any pending markdown cell
                    markdown_cell = _new_cell(nb, markdown_cell, "markdown")
                    # Add to command cell
                    command_cell += _extract_content(line, "command") + "\n"
                elif comment_type == "split":
                    # Finish any pending cells and start fresh
                    markdown_cell = _new_cell(nb, markdown_cell, "markdown")
                    command_cell = _new_cell(nb, command_cell, "command")
            else:
                # Regular code line - finish pending markdown/command cells
                markdown_cell = _new_cell(nb, markdown_cell, "markdown")
                command_cell = _new_cell(nb, command_cell, "command")
                # Add to code cell
                code_cell += line

        # Finish any remaining cells
        markdown_cell = _new_cell(nb, markdown_cell, "markdown")
        command_cell = _new_cell(nb, command_cell, "command")
        code_cell = _new_cell(nb, code_cell, "code")

        # Always validate notebook structure for cleanup
        _validate_notebook(nb)

        # Write notebook
        with open(notebook_path, "w", encoding="utf-8") as f:
            nbformat.write(nb, f, version=nbformat.NO_CONVERT)

        return str(notebook_path)


def notebook_to_python(notebook_path: str, output_path: str | None = None) -> str:
    """Convert Jupyter notebook to Python script."""
    notebook_path = Path(notebook_path)

    if not notebook_path.exists():
        raise FileNotFoundError(f"Notebook file not found: {notebook_path}")

    # Determine output path
    if output_path:
        script_path = Path(output_path)
        if script_path.suffix != ".py":
            script_path = script_path.with_suffix(".py")
    else:
        script_path = notebook_path.with_suffix(".py")

    with (
        open(notebook_path, encoding="utf-8") as f_in,
        open(script_path, "w", encoding="utf-8") as f_out,
    ):
        last_source = ""
        notebook_data = json.load(f_in)

        for cell in notebook_data["cells"]:
            if last_source == "code" and cell["cell_type"] == "code":
                # Check if this is a command cell
                is_command_cell = "command" in cell.get("metadata", {}).get("tags", [])
                if not is_command_cell:
                    f_out.write("#-------------------------------\n\n")

            for line in cell["source"]:
                if cell["cell_type"] == "markdown":
                    line = "#| " + line.lstrip()
                elif cell["cell_type"] == "code":
                    # Check if this is a command cell
                    is_command_cell = "command" in cell.get("metadata", {}).get(
                        "tags", []
                    )
                    if is_command_cell:
                        # Remove leading ! if present (from py2nb conversion)
                        stripped_line = line.lstrip()
                        if stripped_line.startswith("!"):
                            stripped_line = stripped_line[1:].lstrip()
                        line = "#! " + stripped_line
                line = line.rstrip() + "\n"
                f_out.write(line)
            f_out.write("\n")
            last_source = cell["cell_type"]

    return str(script_path)


def validate_notebook_file(notebook_path: str) -> bool:
    """Validate a notebook file can be loaded and has valid structure."""
    try:
        with open(notebook_path, encoding="utf-8") as f:
            notebook_data = json.load(f)

        # Basic structure validation
        if "cells" not in notebook_data:
            return False

        for cell in notebook_data["cells"]:
            if "cell_type" not in cell or "source" not in cell:
                return False

        return True
    except (json.JSONDecodeError, FileNotFoundError):
        return False


def validate_python_file(script_path: str) -> bool:
    """Validate a Python file can be read and parsed."""
    try:
        with open(script_path, encoding="utf-8") as f:
            content = f.read()

        # Try to compile the Python code (basic syntax check)
        compile(content, script_path, "exec")
        return True
    except (SyntaxError, FileNotFoundError):
        return False

```

`src/mcp_handley_lab/py2nb/models.py`:

```py
"""Pydantic models for notebook conversion tool outputs."""

from pydantic import BaseModel, Field


class ConversionResult(BaseModel):
    """Result of notebook conversion operation."""

    success: bool = Field(..., description="Indicates if the conversion was successful.")
    input_path: str = Field(..., description="The absolute path of the source file.")
    output_path: str = Field(..., description="The absolute path of the newly created destination file.")
    backup_path: str | None = Field(default=None, description="The path to the backup of the original file, if one was created.")
    message: str = Field(..., description="A human-readable summary of the conversion result.")


class ValidationResult(BaseModel):
    """Result of file validation operation."""

    valid: bool = Field(..., description="Indicates if the file passed validation.")
    file_path: str = Field(..., description="The path to the file that was validated.")
    message: str = Field(..., description="A summary of the validation result.")
    error_details: str | None = Field(default=None, description="Detailed error information if validation failed.")


class RoundtripResult(BaseModel):
    """Result of round-trip conversion testing."""

    success: bool = Field(..., description="Indicates if the round-trip conversion completed successfully.")
    input_path: str = Field(..., description="The path to the original file used for round-trip testing.")
    differences_found: bool = Field(..., description="Whether any differences were detected between original and round-trip result.")
    message: str = Field(..., description="A summary of the round-trip test result.")
    diff_output: str | None = Field(default=None, description="Detailed diff output if differences were found.")
    temporary_files_cleaned: bool = Field(default=True, description="Whether temporary files created during testing were cleaned up.")


class ExecutionResult(BaseModel):
    """Result of notebook execution operation."""

    success: bool = Field(..., description="Indicates if the notebook execution completed successfully.")
    notebook_path: str = Field(..., description="The path to the notebook that was executed.")
    cells_executed: int = Field(..., description="The total number of cells that were executed.")
    cells_with_errors: int = Field(..., description="The number of cells that encountered errors during execution.")
    execution_time_seconds: float = Field(..., description="The total time taken to execute the notebook in seconds.")
    message: str = Field(..., description="A summary of the execution result.")
    error_details: str | None = Field(default=None, description="Detailed error information if execution failed.")
    kernel_name: str | None = Field(default=None, description="The name of the Jupyter kernel used for execution.")



```

`src/mcp_handley_lab/py2nb/tool.py`:

```py
"""py2nb conversion tool for MCP - bidirectional Python script ↔ Jupyter notebook conversion."""

import subprocess
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.shared.models import ServerInfo

from .converter import (
    notebook_to_python,
    python_to_notebook,
    validate_notebook_file,
    validate_python_file,
)
from .models import (
    ConversionResult,
    ExecutionResult,
    RoundtripResult,
    ValidationResult,
)

mcp = FastMCP("py2nb Conversion Tool")


@mcp.tool(
    description="Converts a Python script to a Jupyter notebook. Supports comment syntax for markdown cells (#|), command cells (#!), and cell splits (#-). Returns structured conversion result."
)
def py_to_notebook(
    script_path: str = Field(
        ...,
        description="Path to the Python script file to convert to a Jupyter notebook.",
    ),
    output_path: str = Field(
        default="",
        description="Path for the output notebook file. If empty, uses script name with .ipynb extension.",
    ),
    backup: bool = Field(
        default=True,
        description="If True, creates a backup of the original script file with .bak extension.",
    ),
) -> ConversionResult:
    """Convert Python script to Jupyter notebook."""
    script_path = Path(script_path)

    if not script_path.exists():
        raise FileNotFoundError(f"Script file not found: {script_path}")

    backup_path_str = None
    # Create backup if requested
    if backup:
        backup_path = script_path.with_suffix(script_path.suffix + ".bak")
        backup_path.write_text(script_path.read_text())
        backup_path_str = str(backup_path)

    # Convert to notebook
    notebook_path = python_to_notebook(str(script_path), output_path)

    # Validate the created notebook
    if not validate_notebook_file(notebook_path):
        raise RuntimeError(f"Generated notebook failed validation: {notebook_path}")

    message = f"Successfully converted {script_path} to {notebook_path}"
    if backup:
        message += f"\nBackup saved to: {backup_path_str}"

    return ConversionResult(
        success=True,
        input_path=str(script_path),
        output_path=notebook_path,
        backup_path=backup_path_str,
        message=message,
    )


@mcp.tool(
    description="Converts a Jupyter notebook to a Python script. Preserves markdown as #| comments, command cells as #! comments, and adds cell separators. Returns structured conversion result."
)
def notebook_to_py(
    notebook_path: str = Field(
        ...,
        description="Path to the Jupyter notebook file to convert to Python script.",
    ),
    output_path: str = Field(
        default="",
        description="Path for the output Python script. If empty, uses notebook name with .py extension.",
    ),
    validate_files: bool = Field(
        default=True,
        description="If True, validates the input notebook and output script for correct syntax.",
    ),
    backup: bool = Field(
        default=True,
        description="If True, creates a backup of the original notebook file with .bak extension.",
    ),
) -> ConversionResult:
    """Convert Jupyter notebook to Python script."""
    notebook_path = Path(notebook_path)

    if not notebook_path.exists():
        raise FileNotFoundError(f"Notebook file not found: {notebook_path}")

    # Validate input notebook
    if validate_files and not validate_notebook_file(str(notebook_path)):
        raise ValueError(f"Invalid notebook file: {notebook_path}")

    backup_path_str = None
    # Create backup if requested
    if backup:
        backup_path = notebook_path.with_suffix(notebook_path.suffix + ".bak")
        backup_path.write_text(notebook_path.read_text())
        backup_path_str = str(backup_path)

    # Convert to Python script
    script_path = notebook_to_python(str(notebook_path), output_path)

    # Validate the created script
    if validate_files and not validate_python_file(script_path):
        raise RuntimeError(f"Generated script failed validation: {script_path}")

    message = f"Successfully converted {notebook_path} to {script_path}"
    if backup:
        message += f"\nBackup saved to: {backup_path_str}"

    return ConversionResult(
        success=True,
        input_path=str(notebook_path),
        output_path=script_path,
        backup_path=backup_path_str,
        message=message,
    )


@mcp.tool(
    description="Validates a notebook file structure and syntax. Returns structured validation result with status and error details."
)
def validate_notebook(
    notebook_path: str = Field(
        ...,
        description="Path to the Jupyter notebook file to validate for correct structure and syntax.",
    ),
) -> ValidationResult:
    """Validate notebook file structure."""
    if not Path(notebook_path).exists():
        return ValidationResult(
            valid=False,
            file_path=notebook_path,
            message="File not found",
            error_details=f"File does not exist: {notebook_path}",
        )

    try:
        is_valid = validate_notebook_file(notebook_path)
        if is_valid:
            return ValidationResult(
                valid=True,
                file_path=notebook_path,
                message="Notebook validation passed",
            )
        else:
            return ValidationResult(
                valid=False,
                file_path=notebook_path,
                message="Notebook validation failed",
                error_details="Invalid notebook structure",
            )
    except Exception as e:
        return ValidationResult(
            valid=False,
            file_path=notebook_path,
            message="Notebook validation failed",
            error_details=str(e),
        )


@mcp.tool(
    description="Validates a Python script file syntax. Returns structured validation result with status and error details."
)
def validate_python(
    script_path: str = Field(
        ...,
        description="Path to the Python script file to validate for correct syntax.",
    ),
) -> ValidationResult:
    """Validate Python script file syntax."""
    if not Path(script_path).exists():
        return ValidationResult(
            valid=False,
            file_path=script_path,
            message="File not found",
            error_details=f"File does not exist: {script_path}",
        )

    try:
        is_valid = validate_python_file(script_path)
        if is_valid:
            return ValidationResult(
                valid=True,
                file_path=script_path,
                message="Python script validation passed",
            )
        else:
            return ValidationResult(
                valid=False,
                file_path=script_path,
                message="Python script validation failed",
                error_details="Python syntax error detected",
            )
    except Exception as e:
        return ValidationResult(
            valid=False,
            file_path=script_path,
            message="Python script validation failed",
            error_details=str(e),
        )


@mcp.tool(
    description="Performs round-trip conversion testing (py→nb→py) to verify conversion fidelity. Returns structured comparison results with difference details."
)
def test_roundtrip(
    script_path: str = Field(
        ...,
        description="Path to the Python script to test for round-trip conversion fidelity (py→nb→py).",
    ),
    cleanup: bool = Field(
        default=True,
        description="If True, removes temporary files created during the round-trip test.",
    ),
) -> RoundtripResult:
    """Test round-trip conversion fidelity."""
    script_path = Path(script_path)

    if not script_path.exists():
        return RoundtripResult(
            success=False,
            input_path=str(script_path),
            differences_found=False,
            message="Script file not found",
            temporary_files_cleaned=True,
        )

    try:
        # Original content
        original_content = script_path.read_text()

        # Convert to notebook
        notebook_path = script_path.with_suffix(".ipynb")
        python_to_notebook(str(script_path), str(notebook_path))

        # Convert back to Python
        roundtrip_path = script_path.with_suffix(".roundtrip.py")
        notebook_to_python(str(notebook_path), str(roundtrip_path))

        # Compare content
        roundtrip_content = roundtrip_path.read_text()

        # Normalize whitespace for comparison
        original_normalized = "\n".join(
            line.rstrip() for line in original_content.splitlines()
        )
        roundtrip_normalized = "\n".join(
            line.rstrip() for line in roundtrip_content.splitlines()
        )

        differences_found = original_normalized != roundtrip_normalized
        diff_output = None

        if differences_found:
            # Show differences
            import difflib

            diff = list(
                difflib.unified_diff(
                    original_content.splitlines(keepends=True),
                    roundtrip_content.splitlines(keepends=True),
                    fromfile=str(script_path),
                    tofile=str(roundtrip_path),
                    lineterm="",
                )
            )
            diff_output = "".join(diff)

        # Cleanup temporary files
        cleaned = True
        if cleanup:
            try:
                if notebook_path.exists():
                    notebook_path.unlink()
                if roundtrip_path.exists():
                    roundtrip_path.unlink()
            except Exception:
                cleaned = False

        message = (
            "Round-trip conversion successful"
            if not differences_found
            else "Round-trip differences detected"
        )

        return RoundtripResult(
            success=True,
            input_path=str(script_path),
            differences_found=differences_found,
            message=message,
            diff_output=diff_output,
            temporary_files_cleaned=cleaned,
        )

    except Exception as e:
        return RoundtripResult(
            success=False,
            input_path=str(script_path),
            differences_found=False,
            message=f"Round-trip test failed: {str(e)}",
            temporary_files_cleaned=cleanup,
        )


@mcp.tool(
    description="Checks the status of the Notebook Conversion Tool server and nbformat dependency. Returns structured server information with versions and capabilities."
)
def server_info() -> ServerInfo:
    """Get server status and dependency information."""
    try:
        import nbformat

        nbformat_version = nbformat.__version__
    except ImportError:
        nbformat_version = "Not installed"

    # Check if jupyter is available for optional execution
    try:
        result = subprocess.run(
            ["jupyter", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        jupyter_info = result.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.CalledProcessError):
        jupyter_info = "Not available"

    available_tools = [
        "py_to_notebook",
        "notebook_to_py",
        "validate_notebook",
        "validate_python",
        "test_roundtrip",
        "execute_notebook",
        "server_info",
    ]

    comment_syntax = {
        "#| or # |": "Markdown cells",
        "#! or # !": "Command cells (magic commands)",
        "#- or # -": "Cell separators",
        "#% or # %": "Command cells (alternative syntax)",
    }

    return ServerInfo(
        name="py2nb Conversion Tool",
        version="1.0.0",
        status="active",
        capabilities=available_tools,
        dependencies={
            "nbformat": nbformat_version,
            "jupyter": jupyter_info,
            "comment_syntax": str(comment_syntax),
        },
    )


@mcp.tool(
    description="Executes all cells in a Jupyter notebook and populates outputs as if a user ran every cell. Returns structured execution results with cell counts and timing."
)
def execute_notebook(
    notebook_path: str = Field(
        ..., description="Path to the Jupyter notebook file to execute all cells."
    ),
    allow_errors: bool = Field(
        default=False,
        description="If True, continues execution even when cells raise exceptions.",
    ),
    timeout: int = Field(
        default=600,
        description="Maximum time in seconds to wait for each cell to execute.",
        gt=0,
    ),
    kernel_name: str = Field(
        default="python3",
        description="Name of the Jupyter kernel to use for execution (e.g., 'python3', 'python').",
    ),
) -> ExecutionResult:
    """Execute all cells in a notebook and populate outputs."""
    notebook_path = Path(notebook_path)

    if not notebook_path.exists():
        return ExecutionResult(
            success=False,
            notebook_path=str(notebook_path),
            cells_executed=0,
            cells_with_errors=0,
            execution_time_seconds=0.0,
            message="Notebook file not found",
            error_details=f"File does not exist: {notebook_path}",
        )

    # Validate notebook first
    if not validate_notebook_file(str(notebook_path)):
        return ExecutionResult(
            success=False,
            notebook_path=str(notebook_path),
            cells_executed=0,
            cells_with_errors=0,
            execution_time_seconds=0.0,
            message="Invalid notebook file",
            error_details="Notebook file has invalid structure",
        )

    try:
        import nbformat
        from nbclient import NotebookClient
        from nbclient.exceptions import CellExecutionError
    except ImportError as e:
        return ExecutionResult(
            success=False,
            notebook_path=str(notebook_path),
            cells_executed=0,
            cells_with_errors=0,
            execution_time_seconds=0.0,
            message="Missing dependencies",
            error_details=f"Required libraries not installed: {e}",
        )

    try:
        # Load the notebook
        with open(notebook_path, encoding="utf-8") as f:
            nb = nbformat.read(f, as_version=4)

        # Create execution client
        client = NotebookClient(
            nb,
            timeout=timeout,
            kernel_name=kernel_name,
            allow_errors=allow_errors,
            resources={"metadata": {"path": str(notebook_path.parent)}},
        )

        # Execute the notebook
        start_time = time.time()

        try:
            client.execute()
            execution_success = True
            error_message = None
        except CellExecutionError as e:
            execution_success = False
            error_message = str(e)
        except Exception as e:
            execution_success = False
            error_message = f"Execution failed: {str(e)}"

        end_time = time.time()
        execution_time = end_time - start_time

        # Count executed cells and errors
        cells_executed = 0
        cells_with_errors = 0

        for cell in client.nb.cells:
            if cell.cell_type == "code":
                if (
                    hasattr(cell, "execution_count")
                    and cell.execution_count is not None
                ):
                    cells_executed += 1

                # Check for errors in outputs
                if hasattr(cell, "outputs"):
                    for output in cell.outputs:
                        if output.get("output_type") == "error":
                            cells_with_errors += 1
                            break

        # Save the executed notebook back to file
        with open(notebook_path, "w", encoding="utf-8") as f:
            nbformat.write(client.nb, f)

        if execution_success:
            message = f"Successfully executed {cells_executed} cells in {execution_time:.2f} seconds"
            if cells_with_errors > 0:
                message += f" ({cells_with_errors} cells had errors)"
        else:
            message = f"Execution stopped after {cells_executed} cells due to error"

        return ExecutionResult(
            success=execution_success,
            notebook_path=str(notebook_path),
            cells_executed=cells_executed,
            cells_with_errors=cells_with_errors,
            execution_time_seconds=execution_time,
            message=message,
            error_details=error_message,
            kernel_name=kernel_name,
        )

    except Exception as e:
        return ExecutionResult(
            success=False,
            notebook_path=str(notebook_path),
            cells_executed=0,
            cells_with_errors=0,
            execution_time_seconds=0.0,
            message="Execution failed",
            error_details=str(e),
            kernel_name=kernel_name,
        )

```

`src/mcp_handley_lab/shared/models.py`:

```py
from typing import Any, Literal

from pydantic import BaseModel, Field


class ServerInfo(BaseModel):
    """Standardized server information across all tools."""

    name: str = Field(..., description="The name of the MCP tool server.")
    version: str = Field(..., description="The version of the tool or its primary dependency.")
    status: str = Field(..., description="The operational status of the server (e.g., 'active', 'error').")
    capabilities: list[str] = Field(default_factory=list, description="A list of functions or features the tool provides.")
    dependencies: dict[str, str] = Field(default_factory=dict, description="A dictionary of dependencies and their versions or statuses.")


class UsageStats(BaseModel):
    """LLM usage statistics."""

    input_tokens: int = Field(..., description="Number of tokens in the input prompt.")
    output_tokens: int = Field(..., description="Number of tokens in the generated response.")
    cost: float = Field(..., description="Estimated cost of the API call in USD.")
    model_used: str = Field(..., description="The specific model identifier used for generation.")


class GroundingMetadata(BaseModel):
    """Grounding metadata for LLM responses."""

    web_search_queries: list[str] = Field(default_factory=list, description="List of search queries used for grounding.")
    grounding_chunks: list[dict[str, str]] = Field(default_factory=list, description="Chunks of grounded content with URI and title information.")
    grounding_supports: list[dict[str, Any]] = Field(default_factory=list, description="Mapping between generated text and source citations.")
    retrieval_metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the retrieval process.")
    search_entry_point: dict[str, Any] = Field(default_factory=dict, description="Search interface HTML and query information.")


class LLMResult(BaseModel):
    """Standard LLM response structure."""

    content: str = Field(..., description="The generated text content from the LLM.")
    usage: UsageStats = Field(..., description="Token usage and cost information for the request.")
    agent_name: str = Field(default="", description="Name of the conversational agent or session.")
    grounding_metadata: GroundingMetadata | None = Field(default=None, description="Metadata about grounding sources used in the response.")
    finish_reason: str = Field(default="", description="Reason why generation stopped (e.g., 'stop', 'length').")
    avg_logprobs: float = Field(default=0.0, description="Average log probability of the generated tokens.")
    model_version: str = Field(default="", description="Specific version identifier of the model used.")
    generation_time_ms: int = Field(default=0, description="Time taken to generate the response in milliseconds.")
    response_id: str = Field(default="", description="Unique identifier for this specific response.")
    # OpenAI-specific fields
    system_fingerprint: str = Field(default="", description="OpenAI system fingerprint for the request.")
    service_tier: str = Field(default="", description="OpenAI service tier used for the request.")
    completion_tokens_details: dict[str, Any] = Field(default_factory=dict, description="Detailed token usage breakdown from OpenAI.")
    prompt_tokens_details: dict[str, Any] = Field(default_factory=dict, description="Detailed prompt token information from OpenAI.")
    # Claude-specific fields
    stop_sequence: str = Field(default="", description="Stop sequence that terminated generation in Claude.")
    cache_creation_input_tokens: int = Field(default=0, description="Tokens used for cache creation in Claude.")
    cache_read_input_tokens: int = Field(default=0, description="Tokens read from cache in Claude.")


class ImageGenerationResult(BaseModel):
    """Comprehensive image generation result structure with full metadata."""

    # Core result fields
    message: str = Field(..., description="Status message describing the image generation result.")
    file_path: str = Field(..., description="Local file path where the generated image was saved.")
    file_size_bytes: int = Field(..., description="Size of the generated image file in bytes.")
    usage: UsageStats = Field(..., description="Cost and usage statistics for the image generation.")
    agent_name: str = Field(default="", description="Name of the agent or session that generated the image.")

    # Generation metadata
    generation_timestamp: int = Field(default=0, description="Unix timestamp when the image was generated.")
    enhanced_prompt: str = Field(default="", description="AI-enhanced version of the original prompt.")
    original_prompt: str = Field(default="", description="Original user prompt for the image generation.")

    # Request parameters (what was requested)
    requested_size: str = Field(default="", description="Requested image dimensions (e.g., '1024x1024').")
    requested_quality: str = Field(default="", description="Requested image quality (e.g., 'standard', 'hd').")
    requested_format: str = Field(default="", description="Requested image format (e.g., 'png', 'jpg').")
    aspect_ratio: str = Field(default="", description="Image aspect ratio (e.g., '1:1', '16:9').")

    # Safety and content filtering
    safety_attributes: dict[str, Any] = Field(default_factory=dict, description="Safety scores and flags from the provider.")
    content_filter_reason: str = Field(default="", description="Reason if content was filtered or rejected.")

    # Provider-specific metadata
    openai_metadata: dict[str, Any] = Field(default_factory=dict, description="OpenAI-specific metadata and response fields.")
    gemini_metadata: dict[str, Any] = Field(default_factory=dict, description="Gemini-specific metadata and response fields.")

    # Technical details
    mime_type: str = Field(default="", description="MIME type of the generated image (e.g., 'image/png').")
    cloud_uri: str = Field(default="", description="Cloud storage URI if the image is hosted remotely.")
    original_url: str = Field(default="", description="Original download URL from the provider.")


class FileResult(BaseModel):
    """Standard file operation result."""

    message: str = Field(..., description="Status message describing the file operation result.")
    file_path: str = Field(..., description="Path to the file that was created or modified.")
    file_size_bytes: int = Field(..., description="Size of the file in bytes.")


class OperationResult(BaseModel):
    """Generic operation result."""

    status: Literal["success", "error", "warning"] = Field(..., description="The outcome status of the operation.")
    message: str = Field(..., description="Human-readable description of the operation result.")
    data: dict[str, Any] = Field(default_factory=dict, description="Additional structured data related to the operation.")


class ModelPricing(BaseModel):
    """Model pricing information."""

    type: Literal["per_token", "per_image", "per_second"] = Field(..., description="The pricing model type used by this model.")
    input_cost_per_1m: float = Field(default=0.0, description="Cost per 1 million input tokens in the specified currency.")
    output_cost_per_1m: float = Field(default=0.0, description="Cost per 1 million output tokens in the specified currency.")
    cost_per_image: float = Field(default=0.0, description="Cost per generated image in the specified currency.")
    cost_per_second: float = Field(default=0.0, description="Cost per second of processing time in the specified currency.")
    unit: str = Field(default="USD", description="Currency unit for all pricing information.")


class ModelInfo(BaseModel):
    """Individual model information."""

    id: str = Field(..., description="Unique identifier for the model.")
    name: str = Field(..., description="Human-readable name of the model.")
    description: str = Field(..., description="Detailed description of the model's capabilities and use cases.")
    available: bool = Field(..., description="Whether the model is currently available for use.")
    context_window: str = Field(default="", description="Maximum context window size (e.g., '32K tokens', '2M tokens').")
    pricing: ModelPricing = Field(..., description="Pricing information for this model.")
    tags: list[str] = Field(default_factory=list, description="Tags categorizing the model (e.g., 'multimodal', 'fast').")
    capabilities: list[str] = Field(default_factory=list, description="List of specific capabilities this model supports.")
    best_for: list[str] = Field(default_factory=list, description="List of use cases this model is optimized for.")


class ModelCategory(BaseModel):
    """Model category with associated models."""

    name: str = Field(..., description="Name of the model category (e.g., 'Text Generation', 'Vision').")
    models: list[ModelInfo] = Field(..., description="List of models in this category.")


class ModelListingSummary(BaseModel):
    """Summary information for model listing."""

    provider: str = Field(..., description="Name of the AI provider (e.g., 'OpenAI', 'Google').")
    total_models: int = Field(..., description="Total number of models available from this provider.")
    total_categories: int = Field(..., description="Number of model categories.")
    default_model: str = Field(..., description="Default model identifier for this provider.")
    api_available_models: int = Field(default=0, description="Number of models available via API.")


class ModelListing(BaseModel):
    """Complete structured model listing."""

    summary: ModelListingSummary = Field(..., description="Summary statistics for this model listing.")
    categories: list[ModelCategory] = Field(..., description="Models organized by category.")
    models: list[ModelInfo] = Field(..., description="Flat list of all available models.")
    usage_notes: list[str] = Field(..., description="Important usage notes and limitations.")


class MuttContact(BaseModel):
    """Mutt address book contact."""

    alias: str = Field(..., description="Short alias or nickname for the contact. Defaults to firstname-surname format in lowercase when adding contacts.")
    email: str = Field(..., description="Email address of the contact.")
    name: str = Field(default="", description="Full name of the contact.")


class MuttContactSearchResult(BaseModel):
    """Search result for mutt contacts."""

    query: str = Field(..., description="The search query that was executed.")
    matches: list[MuttContact] = Field(..., description="List of contacts matching the search query.")
    total_found: int = Field(..., description="Total number of contacts found.")


class EmbeddingResult(BaseModel):
    """Result of an embedding request for a single piece of content."""

    embedding: list[float] = Field(..., description="Vector embedding as a list of floating-point numbers.")


class DocumentIndex(BaseModel):
    """A single indexed document containing its path and embedding vector."""

    path: str = Field(..., description="File path of the indexed document.")
    embedding: list[float] = Field(..., description="Vector embedding for the document content.")


class IndexResult(BaseModel):
    """Result of an indexing operation."""

    index_path: str = Field(..., description="Path to the created index file.")
    files_indexed: int = Field(..., description="Number of documents that were indexed.")
    message: str = Field(..., description="Status message describing the indexing result.")


class SearchResult(BaseModel):
    """A single result from a semantic search."""

    path: str = Field(..., description="Path to the document that matched the search.")
    similarity_score: float = Field(..., description="Similarity score between 0.0 and 1.0.")


class SimilarityResult(BaseModel):
    """Result of a similarity calculation between two texts."""

    similarity: float = Field(..., description="Cosine similarity score between -1.0 and 1.0.")

```

`src/mcp_handley_lab/vim/tool.py`:

```py
"""Vim tool for interactive text editing via MCP."""

import difflib
import os
import subprocess
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.shared.models import OperationResult, ServerInfo

mcp = FastMCP("Vim Tool")


def _run_vim(file_path: str, vim_args: list[str] = None) -> None:
    """Run vim directly using subprocess."""
    vim_cmd = ["vim"] + (vim_args or []) + [file_path]

    if os.isatty(0):
        subprocess.run(vim_cmd, check=True)
    else:
        subprocess.run(
            vim_cmd,
            capture_output=True,
            check=True,
        )


def _handle_instructions_and_content(
    temp_path: str, suffix: str, instructions: str, initial_content: str
) -> None:
    """Write content with optional instructions to temp file."""
    comment_char = "#" if suffix in [".py", ".sh", ".yaml", ".yml"] else "//"

    with open(temp_path, "w") as f:
        if instructions:
            for line in instructions.strip().split("\n"):
                f.write(f"{comment_char} {line}\n")
            f.write(f"{comment_char} {'=' * 60}\n\n")
        f.write(initial_content)


def _strip_instructions(content: str, instructions: str, suffix: str) -> str:
    """Remove instruction comments from content."""
    if not instructions:
        return content

    comment_char = "#" if suffix in [".py", ".sh", ".yaml", ".yml"] else "//"
    lines = content.split("\n")

    for i, line in enumerate(lines):
        if line.strip() == comment_char + " " + "=" * 60:
            return "\n".join(lines[i + 2 :])  # Skip separator and blank line
    return content


@mcp.tool(
    description="Opens Vim to edit content in a temporary file. Provide initial `content` and optional `instructions`. Set `file_extension` for syntax highlighting. Returns a diff of changes by default or full content if `show_diff=False`."
)
def prompt_user_edit(
    content: str = Field(
        ...,
        description="The initial text content to be edited. This is a required field.",
    ),
    file_extension: str = Field(
        ".txt",
        description="The file extension to use for the temporary file (e.g., '.py', '.md'). Determines syntax highlighting in Vim.",
    ),
    instructions: str = Field(
        "",
        description="Optional instructions to display as comments at the top of the file for the user.",
    ),
    show_diff: bool = Field(
        True,
        description="If True, return a diff of the changes. If False, return the full edited content.",
    ),
    keep_file: bool = Field(
        False,
        description="If True, the temporary file will not be deleted after editing. Useful for debugging.",
    ),
) -> OperationResult:
    """Open vim for editing provided content."""
    suffix = file_extension if file_extension.startswith(".") else f".{file_extension}"
    fd, temp_path = tempfile.mkstemp(suffix=suffix, text=True)

    try:
        os.close(fd)
        _handle_instructions_and_content(temp_path, suffix, instructions, content)

        _run_vim(temp_path)

        with open(temp_path) as f:
            edited_content = f.read()

        edited_content = _strip_instructions(edited_content, instructions, suffix)

        if show_diff:
            original_lines = content.splitlines(keepends=True)
            edited_lines = edited_content.splitlines(keepends=True)

            diff = list(
                difflib.unified_diff(
                    original_lines, edited_lines, fromfile="original", tofile="edited"
                )
            )

            if diff:
                added = sum(
                    1
                    for line in diff
                    if line.startswith("+") and not line.startswith("+++")
                )
                removed = sum(
                    1
                    for line in diff
                    if line.startswith("-") and not line.startswith("---")
                )

                result = (
                    f"Changes made: {added} lines added, {removed} lines removed\n\n"
                )
                result += "".join(diff)
            else:
                result = "No changes made"
        else:
            result = edited_content

        return OperationResult(status="success", message=result)

    finally:
        if not keep_file:
            os.unlink(temp_path)


@mcp.tool(
    description="Opens Vim to create new content from scratch with optional `initial_content` and `instructions`. Creates a temporary file, opens Vim for editing, then returns the final content. Instructions are shown as comments and automatically stripped."
)
def quick_edit(
    file_extension: str = Field(
        ".txt",
        description="The file extension for the new file (e.g., '.py', '.sh'). Determines syntax highlighting.",
    ),
    instructions: str = Field(
        "",
        description="Optional instructions to display as comments at the top of the file for the user to follow.",
    ),
    initial_content: str = Field(
        "",
        description="Optional initial content to populate the file with before editing begins.",
    ),
) -> OperationResult:
    """Open vim for creating new content."""
    suffix = file_extension if file_extension.startswith(".") else f".{file_extension}"
    fd, temp_path = tempfile.mkstemp(suffix=suffix, text=True)

    try:
        os.close(fd)
        _handle_instructions_and_content(
            temp_path, suffix, instructions, initial_content
        )

        _run_vim(temp_path)

        with open(temp_path) as f:
            content = f.read()

        content = _strip_instructions(content, instructions, suffix)

        return OperationResult(status="success", message=content)

    finally:
        os.unlink(temp_path)


@mcp.tool(
    description="Opens an existing file in Vim for interactive editing. If `instructions` are provided, the user must first view them in a read-only buffer before proceeding. Creates a backup (.bak) by default. Returns a diff of the changes."
)
def open_file(
    file_path: str = Field(
        ...,
        description="The absolute or relative path to the existing file to be opened for editing.",
    ),
    instructions: str = Field(
        "",
        description="Optional instructions shown to the user in a read-only buffer before they can edit the file.",
    ),
    show_diff: bool = Field(
        True,
        description="If True, return a diff of the changes. If False, just return a confirmation message.",
    ),
    backup: bool = Field(
        True,
        description="If True, create a backup of the original file with a '.bak' extension before editing.",
    ),
) -> OperationResult:
    """Open existing file in vim."""
    path = Path(file_path)

    original_content = path.read_text()
    if backup:
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(original_content)

    if instructions:
        fd, inst_path = tempfile.mkstemp(suffix=".txt", text=True)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(f"INSTRUCTIONS FOR EDITING: {file_path}\n")
                f.write("=" * 60 + "\n")
                f.write(instructions + "\n")
                f.write("=" * 60 + "\n")
                f.write("\nPress any key to continue to the file...")

            _run_vim(inst_path, ["-R"])
        finally:
            os.unlink(inst_path)

    _run_vim(str(path))

    edited_content = path.read_text()

    if show_diff:
        original_lines = original_content.splitlines(keepends=True)
        edited_lines = edited_content.splitlines(keepends=True)

        diff = list(
            difflib.unified_diff(
                original_lines,
                edited_lines,
                fromfile=f"{file_path}.original",
                tofile=file_path,
            )
        )

        if diff:
            added = sum(
                1
                for line in diff
                if line.startswith("+") and not line.startswith("+++")
            )
            removed = sum(
                1
                for line in diff
                if line.startswith("-") and not line.startswith("---")
            )

            result = f"File edited: {file_path}\n"
            result += f"Changes: {added} lines added, {removed} lines removed\n"
            if backup:
                result += f"Backup saved to: {backup_path}\n"
            result += "\n" + "".join(diff)
        else:
            result = f"No changes made to {file_path}"
    else:
        result = f"File edited: {file_path}"
        if backup:
            result += f"\nBackup saved to: {backup_path}"

    return OperationResult(status="success", message=result)


@mcp.tool(
    description="Checks the status of the Vim server and vim command availability. Returns version info and available functions."
)
def server_info() -> ServerInfo:
    """Get server status and vim version."""
    try:
        result = subprocess.run(
            ["vim", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        raise RuntimeError("vim command not found") from None

    version_line = result.stdout.split("\n")[0]

    return ServerInfo(
        name="Vim Tool",
        version="1.0.0",
        status="active",
        capabilities=["prompt_user_edit", "quick_edit", "open_file"],
        dependencies={"vim": version_line},
    )

```

`src/mcp_handley_lab/word/__init__.py`:

```py
"""Word documents MCP tool for document conversion and analysis."""
```

`src/mcp_handley_lab/word/converter.py`:

```py
"""Document conversion functions for Word documents."""

import subprocess
import time
from pathlib import Path
from typing import Literal

from .models import ConversionResult
from .utils import detect_word_format


def _run_pandoc(
    input_path: Path,
    output_path: Path,
    from_format: str,
    to_format: Literal["markdown", "docx", "html", "plain"],
) -> ConversionResult:
    """Run pandoc conversion and return result."""
    cmd = ["pandoc", str(input_path), "-f", from_format, "-t", to_format, "-o", str(output_path)]
    
    try:
        start_time = time.time()
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        end_time = time.time()
        
        return ConversionResult(
            success=True,
            input_path=str(input_path),
            output_path=str(output_path),
            input_format=from_format,
            output_format=to_format if to_format != "plain" else "text",
            file_size_bytes=output_path.stat().st_size,
            conversion_time_ms=int((end_time - start_time) * 1000),
            message=f"Successfully converted {from_format} to {to_format}"
        )
    except FileNotFoundError:
        raise RuntimeError("Pandoc not found. Please install pandoc to use conversion features.")
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Pandoc conversion failed: {e.stderr}") from e


def docx_to_markdown(input_path: str, output_path: str = "") -> ConversionResult:
    """Convert DOCX to Markdown using pandoc."""
    input_p = Path(input_path)
    if not detect_word_format(input_path).can_process:
        raise ValueError(f"Input file is not a processable Word document: {input_path}")
    output_p = Path(output_path) if output_path else input_p.with_suffix('.md')
    return _run_pandoc(input_p, output_p, "docx", "markdown")

def markdown_to_docx(input_path: str, output_path: str = "") -> ConversionResult:
    """Convert Markdown to DOCX using pandoc."""
    input_p = Path(input_path)
    if not input_p.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    output_p = Path(output_path) if output_path else input_p.with_suffix('.docx')
    return _run_pandoc(input_p, output_p, "markdown", "docx")
def docx_to_html(input_path: str, output_path: str = "") -> ConversionResult:
    """Convert DOCX to HTML using pandoc."""
    input_p = Path(input_path)
    if not detect_word_format(input_path).can_process:
        raise ValueError(f"Input file is not a processable Word document: {input_path}")
    output_p = Path(output_path) if output_path else input_p.with_suffix('.html')
    return _run_pandoc(input_p, output_p, "docx", "html")
def docx_to_text(input_path: str, output_path: str = "") -> ConversionResult:
    """Convert DOCX to plain text using pandoc."""
    input_p = Path(input_path)
    if not detect_word_format(input_path).can_process:
        raise ValueError(f"Input file is not a processable Word document: {input_path}")
    output_p = Path(output_path) if output_path else input_p.with_suffix('.txt')
    return _run_pandoc(input_p, output_p, "docx", "plain")
```

`src/mcp_handley_lab/word/models.py`:

```py
"""Pydantic models for Word documents tool."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class WordComment(BaseModel):
    """Word document comment with context."""
    
    comment_id: str = Field(..., description="Unique identifier for the comment.")
    author: str = Field(..., description="Author of the comment.")
    date: str = Field(..., description="Date when the comment was created.")
    text: str = Field(..., description="Text content of the comment.")
    referenced_text: str = Field(..., description="Text that the comment references.")
    paragraph_context: str = Field(..., description="Full paragraph containing the referenced text.")
    reply_to: str | None = Field(default=None, description="ID of parent comment if this is a reply.")


class TrackedChange(BaseModel):
    """Tracked change in Word document."""
    
    change_id: str = Field(..., description="Unique identifier for the tracked change.")
    type: Literal["insertion", "deletion", "formatting"] = Field(..., description="Type of change made.")
    author: str = Field(..., description="Author who made the change.")
    date: str = Field(..., description="Date when the change was made.")
    original_text: str = Field(..., description="Original text before the change.")
    changed_text: str = Field(..., description="New text after the change.")
    accepted: bool = Field(default=False, description="Whether the change has been accepted.")


class DocumentMetadata(BaseModel):
    """Word document metadata."""
    
    filename: str = Field(..., description="Name of the document file.")
    title: str = Field(default="", description="Document title from properties.")
    author: str = Field(default="", description="Document author from properties.")
    subject: str = Field(default="", description="Document subject from properties.")
    created: str = Field(default="", description="Document creation date.")
    modified: str = Field(default="", description="Last modification date.")
    word_count: int = Field(default=0, description="Number of words in the document.")
    page_count: int = Field(default=0, description="Number of pages in the document.")
    paragraph_count: int = Field(default=0, description="Number of paragraphs in the document.")
    format_version: str = Field(default="", description="Document format version (.doc, .docx, etc.).")


class Heading(BaseModel):
    """Document heading with level and text."""
    
    level: str = Field(..., description="The style level of the heading (e.g., 'Heading 1').")
    text: str = Field(..., description="The text content of the heading.")


class DocumentStructure(BaseModel):
    """Document structure analysis."""
    
    headings: list[Heading] = Field(default_factory=list, description="List of headings with level and text.")
    sections: list[str] = Field(default_factory=list, description="List of section titles.")
    tables: int = Field(default=0, description="Number of tables in the document.")
    images: int = Field(default=0, description="Number of images in the document.")
    hyperlinks: int = Field(default=0, description="Number of hyperlinks in the document.")
    footnotes: int = Field(default=0, description="Number of footnotes in the document.")


class CommentExtractionResult(BaseModel):
    """Result of comment extraction operation."""
    
    success: bool = Field(..., description="Whether the comment extraction succeeded.")
    document_path: str = Field(..., description="Path to the analyzed document.")
    comments: list[WordComment] = Field(..., description="List of extracted comments.")
    total_comments: int = Field(..., description="Total number of comments found.")
    unique_authors: list[str] = Field(..., description="List of unique comment authors.")
    message: str = Field(..., description="Status message about the extraction.")
    metadata: DocumentMetadata = Field(..., description="Document metadata.")


class TrackedChangesResult(BaseModel):
    """Result of tracked changes extraction."""
    
    success: bool = Field(..., description="Whether the tracked changes extraction succeeded.")
    document_path: str = Field(..., description="Path to the analyzed document.")
    changes: list[TrackedChange] = Field(..., description="List of tracked changes.")
    total_changes: int = Field(..., description="Total number of tracked changes.")
    unique_authors: list[str] = Field(..., description="List of unique change authors.")
    pending_changes: int = Field(..., description="Number of unaccepted changes.")
    message: str = Field(..., description="Status message about the extraction.")


class ConversionResult(BaseModel):
    """Result of document conversion operation."""
    
    success: bool = Field(..., description="Whether the conversion succeeded.")
    input_path: str = Field(..., description="Path to the input document.")
    output_path: str = Field(..., description="Path to the converted output document.")
    input_format: str = Field(..., description="Format of the input document.")
    output_format: str = Field(..., description="Format of the output document.")
    file_size_bytes: int = Field(..., description="Size of the output file in bytes.")
    conversion_time_ms: int = Field(default=0, description="Time taken for conversion in milliseconds.")
    message: str = Field(..., description="Status message about the conversion.")
    warnings: list[str] = Field(default_factory=list, description="Any warnings during conversion.")


class DocumentAnalysisResult(BaseModel):
    """Comprehensive document analysis result."""
    
    success: bool = Field(..., description="Whether the analysis succeeded.")
    document_path: str = Field(..., description="Path to the analyzed document.")
    metadata: DocumentMetadata = Field(..., description="Document metadata.")
    structure: DocumentStructure = Field(..., description="Document structure analysis.")
    has_comments: bool = Field(..., description="Whether the document contains comments.")
    has_tracked_changes: bool = Field(..., description="Whether the document has tracked changes.")
    message: str = Field(..., description="Status message about the analysis.")


class FormatDetectionResult(BaseModel):
    """Result of document format detection."""
    
    file_path: str = Field(..., description="Path to the analyzed file.")
    detected_format: Literal["docx", "doc", "xml", "unknown"] = Field(..., description="Detected file format.")
    is_valid: bool = Field(..., description="Whether the file is a valid Word document.")
    format_version: str = Field(default="", description="Specific format version if detectable.")
    can_process: bool = Field(..., description="Whether this tool can process the format.")
    message: str = Field(..., description="Status message about format detection.")
```

`src/mcp_handley_lab/word/parser.py`:

```py
"""Word document parser for comments, track changes, and content analysis."""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

from .models import (
    DocumentMetadata,
    DocumentStructure,
    Heading,
    TrackedChange,
    WordComment,
)



# Word namespace mappings
NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'cp': 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'dcterms': 'http://purl.org/dc/terms/',
}


class WordDocumentParser:
    """Parser for Word document content, comments, and tracked changes."""
    
    def __init__(self, document_path: str):
        """Initialize parser with document path."""
        self.document_path = Path(document_path)
        self.document_root = None
        self.comments_root = None
        self.core_props_root = None
        
    def _load_docx_xml(self) -> bool:
        """Load XML content from DOCX file."""
        try:
            with zipfile.ZipFile(self.document_path, 'r') as zip_file:
                # Load main document
                if 'word/document.xml' in zip_file.namelist():
                    document_content = zip_file.read('word/document.xml')
                    self.document_root = ET.fromstring(document_content)
                
                # Load comments if they exist
                if 'word/comments.xml' in zip_file.namelist():
                    comments_content = zip_file.read('word/comments.xml')
                    self.comments_root = ET.fromstring(comments_content)
                
                # Load core properties if they exist
                if 'docProps/core.xml' in zip_file.namelist():
                    core_props_content = zip_file.read('docProps/core.xml')
                    self.core_props_root = ET.fromstring(core_props_content)
                    
                return True
        except (zipfile.BadZipFile, ET.ParseError, FileNotFoundError):
            return False
    
    def _load_xml_directory(self) -> bool:
        """Load XML content from extracted DOCX directory."""
        try:
            # Load main document
            document_file = self.document_path / "word" / "document.xml"
            if document_file.exists():
                self.document_root = ET.parse(document_file).getroot()
            
            # Load comments if they exist
            comments_file = self.document_path / "word" / "comments.xml"
            if comments_file.exists():
                self.comments_root = ET.parse(comments_file).getroot()
            
            # Load core properties if they exist
            core_props_file = self.document_path / "docProps" / "core.xml"
            if core_props_file.exists():
                self.core_props_root = ET.parse(core_props_file).getroot()
                
            return self.document_root is not None
        except (ET.ParseError, FileNotFoundError):
            return False
    
    def _load_single_xml(self) -> bool:
        """Load single document.xml file."""
        try:
            if self.document_path.name == "document.xml":
                self.document_root = ET.parse(self.document_path).getroot()
                
                # Try to find comments.xml in the same directory
                comments_file = self.document_path.parent / "comments.xml"
                if comments_file.exists():
                    self.comments_root = ET.parse(comments_file).getroot()
                    
                return True
        except (ET.ParseError, FileNotFoundError):
            return False
        return False
    
    def load(self) -> None:
        """Load document content based on file type."""
        success = False
        if self.document_path.suffix.lower() == '.docx':
            success = self._load_docx_xml()
        elif self.document_path.is_dir():
            success = self._load_xml_directory()
        elif self.document_path.name == "document.xml":
            success = self._load_single_xml()
        
        if not success:
            raise ValueError(f"Failed to load or parse document: {self.document_path}")
    
    def extract_text_from_run(self, run_elem) -> str:
        """Extract text from a Word run element."""
        text = ""
        for t_elem in run_elem.findall('.//w:t', NAMESPACES):
            if t_elem.text:
                text += t_elem.text
        return text
    
    def extract_text_from_paragraph(self, para_elem) -> str:
        """Extract text from a Word paragraph element."""
        text = ""
        for run in para_elem.findall('.//w:r', NAMESPACES):
            text += self.extract_text_from_run(run)
        return text
    
    def extract_comments(self) -> List[WordComment]:
        """Extract all comments from the document."""
        if not self.document_root or not self.comments_root:
            return []
        
        # Parse comments.xml to get comment details
        comments_data = {}
        for comment in self.comments_root.findall('.//w:comment', NAMESPACES):
            comment_id = comment.get(f"{{{NAMESPACES['w']}}}id")
            author = comment.get(f"{{{NAMESPACES['w']}}}author", "Unknown")
            date = comment.get(f"{{{NAMESPACES['w']}}}date", "")
            
            # Extract comment text
            comment_text = ""
            for para in comment.findall('.//w:p', NAMESPACES):
                comment_text += self.extract_text_from_paragraph(para) + "\\n"
            
            comments_data[comment_id] = {
                'author': author,
                'date': date,
                'text': comment_text.strip()
            }
        
        # Find comment ranges in document
        comment_ranges = self._find_comment_ranges()
        
        # Combine comment data with referenced text
        comments = []
        for comment_id, comment_data in comments_data.items():
            referenced_text, paragraph_context = comment_ranges.get(comment_id, ("", ""))
            
            comment = WordComment(
                comment_id=comment_id,
                author=comment_data['author'],
                date=comment_data['date'],
                text=comment_data['text'],
                referenced_text=referenced_text,
                paragraph_context=paragraph_context
            )
            comments.append(comment)
        
        return comments
    
    def _find_comment_ranges(self) -> Dict[str, Tuple[str, str]]:
        """Find all comment ranges and extract the text between start and end markers."""
        comment_ranges = {}
        
        # Get all paragraphs
        paragraphs = self.document_root.findall('.//w:p', NAMESPACES)
        
        for para in paragraphs:
            # Find comment range starts and ends in this paragraph
            comment_starts = {}
            comment_ends = {}
            
            # Process all elements in the paragraph to find comment markers
            for elem in para.iter():
                if elem.tag == f"{{{NAMESPACES['w']}}}commentRangeStart":
                    comment_id = elem.get(f"{{{NAMESPACES['w']}}}id")
                    if comment_id:
                        comment_starts[comment_id] = elem
                elif elem.tag == f"{{{NAMESPACES['w']}}}commentRangeEnd":
                    comment_id = elem.get(f"{{{NAMESPACES['w']}}}id")
                    if comment_id:
                        comment_ends[comment_id] = elem
            
            # For each comment range, extract text between start and end
            for comment_id in comment_starts:
                if comment_id in comment_ends:
                    start_elem = comment_starts[comment_id]
                    end_elem = comment_ends[comment_id]
                    
                    # Extract text between start and end markers
                    para_text = self.extract_text_from_paragraph(para)
                    
                    # Try to find the specific text by looking at runs between markers
                    comment_text = self._extract_comment_text_between_markers(para, start_elem, end_elem)
                    if not comment_text:
                        comment_text = para_text  # Fallback to full paragraph
                    
                    comment_ranges[comment_id] = (comment_text, para_text)
        
        return comment_ranges
    
    def _extract_comment_text_between_markers(self, para, start_marker, end_marker):
        """Extract text specifically between comment start and end markers."""
        # Get all child elements of the paragraph
        children = list(para)
        
        try:
            start_idx = children.index(start_marker)
            end_idx = children.index(end_marker)
            
            # Extract text from elements between the markers
            text = ""
            for i in range(start_idx + 1, end_idx):
                elem = children[i]
                if elem.tag == f"{{{NAMESPACES['w']}}}r":  # Run element
                    text += self.extract_text_from_run(elem)
            
            return text.strip()
        except ValueError:
            # Markers not found as direct children, fall back to regex approach
            return ""
    
    def extract_tracked_changes(self) -> List[TrackedChange]:
        """Extract tracked changes from the document."""
        if not self.document_root:
            return []
        
        changes = []
        
        # Find inserted text
        for ins in self.document_root.findall('.//w:ins', NAMESPACES):
            change_id = ins.get(f"{{{NAMESPACES['w']}}}id", "")
            author = ins.get(f"{{{NAMESPACES['w']}}}author", "Unknown")
            date = ins.get(f"{{{NAMESPACES['w']}}}date", "")
            
            # Extract inserted text
            inserted_text = ""
            for run in ins.findall('.//w:r', NAMESPACES):
                inserted_text += self.extract_text_from_run(run)
            
            change = TrackedChange(
                change_id=change_id or f"ins_{len(changes)}",
                type="insertion",
                author=author,
                date=date,
                original_text="",
                changed_text=inserted_text.strip(),
                accepted=False
            )
            changes.append(change)
        
        # Find deleted text
        for del_elem in self.document_root.findall('.//w:del', NAMESPACES):
            change_id = del_elem.get(f"{{{NAMESPACES['w']}}}id", "")
            author = del_elem.get(f"{{{NAMESPACES['w']}}}author", "Unknown")
            date = del_elem.get(f"{{{NAMESPACES['w']}}}date", "")
            
            # Extract deleted text
            deleted_text = ""
            for run in del_elem.findall('.//w:r', NAMESPACES):
                deleted_text += self.extract_text_from_run(run)
            
            change = TrackedChange(
                change_id=change_id or f"del_{len(changes)}",
                type="deletion",
                author=author,
                date=date,
                original_text=deleted_text.strip(),
                changed_text="",
                accepted=False
            )
            changes.append(change)
        
        return changes
    
    def extract_metadata(self) -> DocumentMetadata:
        """Extract document metadata."""
        metadata = DocumentMetadata(
            filename=self.document_path.name
        )
        
        # Extract from core properties if available
        if self.core_props_root:
            title_elem = self.core_props_root.find('.//dc:title', NAMESPACES)
            if title_elem is not None and title_elem.text:
                metadata.title = title_elem.text
            
            creator_elem = self.core_props_root.find('.//dc:creator', NAMESPACES)
            if creator_elem is not None and creator_elem.text:
                metadata.author = creator_elem.text
            
            subject_elem = self.core_props_root.find('.//dc:subject', NAMESPACES)
            if subject_elem is not None and subject_elem.text:
                metadata.subject = subject_elem.text
            
            created_elem = self.core_props_root.find('.//dcterms:created', NAMESPACES)
            if created_elem is not None and created_elem.text:
                metadata.created = created_elem.text
            
            modified_elem = self.core_props_root.find('.//dcterms:modified', NAMESPACES)
            if modified_elem is not None and modified_elem.text:
                metadata.modified = modified_elem.text
        
        # Count document elements
        if self.document_root:
            # Count paragraphs
            paragraphs = self.document_root.findall('.//w:p', NAMESPACES)
            metadata.paragraph_count = len(paragraphs)
            
            # Count words (rough estimate)
            total_text = ""
            for para in paragraphs:
                total_text += self.extract_text_from_paragraph(para) + " "
            
            words = total_text.strip().split()
            metadata.word_count = len([w for w in words if w.strip()])
        
        # Set format version
        if self.document_path.suffix.lower() == '.docx':
            metadata.format_version = "DOCX"
        elif self.document_path.suffix.lower() == '.doc':
            metadata.format_version = "DOC"
        else:
            metadata.format_version = "XML"
        
        return metadata
    
    def analyze_structure(self) -> DocumentStructure:
        """Analyze document structure."""
        structure = DocumentStructure()
        
        if not self.document_root:
            return structure
        
        # Find headings
        headings = []
        for para in self.document_root.findall('.//w:p', NAMESPACES):
            # Check for heading styles
            style_elem = para.find('.//w:pStyle', NAMESPACES)
            if style_elem is not None:
                style_val = style_elem.get(f"{{{NAMESPACES['w']}}}val", "")
                if "heading" in style_val.lower() or style_val.startswith("Heading"):
                    heading_text = self.extract_text_from_paragraph(para)
                    if heading_text.strip():
                        headings.append(Heading(
                            level=style_val,
                            text=heading_text.strip()
                        ))
        
        structure.headings = headings
        structure.sections = [h.text for h in headings]
        
        # Count other elements
        structure.tables = len(self.document_root.findall('.//w:tbl', NAMESPACES))
        structure.images = len(self.document_root.findall('.//w:drawing', NAMESPACES))
        structure.hyperlinks = len(self.document_root.findall('.//w:hyperlink', NAMESPACES))
        
        return structure
```

`src/mcp_handley_lab/word/tool.py`:

```py
"""Word documents MCP tool for document conversion and analysis."""

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.shared.models import ServerInfo

from . import converter
from .models import (
    CommentExtractionResult,
    ConversionResult,
    DocumentAnalysisResult,
    FormatDetectionResult,
    TrackedChangesResult,
)
from .parser import WordDocumentParser
from .utils import detect_word_format

mcp = FastMCP("Word Documents Tool")


@mcp.tool(
    description="Detect Word document format and validate if processable. Supports .docx, .doc, and extracted XML structures."
)
def detect_format(
    file_path: str = Field(
        ...,
        description="Path to the Word document file to analyze.",
    )
) -> FormatDetectionResult:
    """Detect Word document format and validate compatibility."""
    return detect_word_format(file_path)


@mcp.tool(
    description="Extract comments from Word document with referenced text context. Supports DOCX files and extracted XML structures."
)
def extract_comments(
    document_path: str = Field(
        ...,
        description="Path to the Word document (.docx) or extracted XML directory.",
    )
) -> CommentExtractionResult:
    """Extract comments from Word document."""
    parser = WordDocumentParser(document_path)
    parser.load()
    
    comments = parser.extract_comments()
    unique_authors = list(set(comment.author for comment in comments))
    metadata = parser.extract_metadata()
    
    return CommentExtractionResult(
        success=True,
        document_path=document_path,
        comments=comments,
        total_comments=len(comments),
        unique_authors=unique_authors,
        message=f"Successfully extracted {len(comments)} comments from {len(unique_authors)} authors",
        metadata=metadata
    )


@mcp.tool(
    description="Extract tracked changes from Word document. Shows insertions, deletions, and formatting changes with author information."
)
def extract_tracked_changes(
    document_path: str = Field(
        ...,
        description="Path to the Word document (.docx) or extracted XML directory.",
    )
) -> TrackedChangesResult:
    """Extract tracked changes from Word document."""
    parser = WordDocumentParser(document_path)
    parser.load()
    
    changes = parser.extract_tracked_changes()
    unique_authors = list(set(change.author for change in changes))
    pending_changes = len([change for change in changes if not change.accepted])
    
    return TrackedChangesResult(
        success=True,
        document_path=document_path,
        changes=changes,
        total_changes=len(changes),
        unique_authors=unique_authors,
        pending_changes=pending_changes,
        message=f"Successfully extracted {len(changes)} tracked changes from {len(unique_authors)} authors ({pending_changes} pending)"
    )


@mcp.tool(
    description="Convert DOCX document to Markdown format using pandoc. Preserves formatting and structure where possible."
)
def docx_to_markdown(
    input_path: str = Field(
        ...,
        description="Path to the input DOCX file.",
    ),
    output_path: str = Field(
        default="",
        description="Path for the output Markdown file. If empty, uses input filename with .md extension.",
    )
) -> ConversionResult:
    """Convert DOCX to Markdown using pandoc."""
    return converter.docx_to_markdown(input_path, output_path)


@mcp.tool(
    description="Convert Markdown document to DOCX format using pandoc. Creates a properly formatted Word document."
)
def markdown_to_docx(
    input_path: str = Field(
        ...,
        description="Path to the input Markdown file.",
    ),
    output_path: str = Field(
        default="",
        description="Path for the output DOCX file. If empty, uses input filename with .docx extension.",
    )
) -> ConversionResult:
    """Convert Markdown to DOCX using pandoc."""
    return converter.markdown_to_docx(input_path, output_path)


@mcp.tool(
    description="Convert DOCX document to HTML format using pandoc. Maintains formatting and structure."
)
def docx_to_html(
    input_path: str = Field(
        ...,
        description="Path to the input DOCX file.",
    ),
    output_path: str = Field(
        default="",
        description="Path for the output HTML file. If empty, uses input filename with .html extension.",
    )
) -> ConversionResult:
    """Convert DOCX to HTML using pandoc."""
    return converter.docx_to_html(input_path, output_path)


@mcp.tool(
    description="Convert DOCX document to plain text format using pandoc. Strips all formatting."
)
def docx_to_text(
    input_path: str = Field(
        ...,
        description="Path to the input DOCX file.",
    ),
    output_path: str = Field(
        default="",
        description="Path for the output text file. If empty, uses input filename with .txt extension.",
    )
) -> ConversionResult:
    """Convert DOCX to plain text using pandoc."""
    return converter.docx_to_text(input_path, output_path)


@mcp.tool(
    description="Perform comprehensive analysis of Word document including metadata, structure, comments, and tracked changes."
)
def analyze_document(
    document_path: str = Field(
        ...,
        description="Path to the Word document (.docx) or extracted XML directory.",
    )
) -> DocumentAnalysisResult:
    """Perform comprehensive Word document analysis."""
    parser = WordDocumentParser(document_path)
    parser.load()
    
    metadata = parser.extract_metadata()
    structure = parser.analyze_structure()
    comments = parser.extract_comments()
    tracked_changes = parser.extract_tracked_changes()
    
    return DocumentAnalysisResult(
        success=True,
        document_path=document_path,
        metadata=metadata,
        structure=structure,
        has_comments=len(comments) > 0,
        has_tracked_changes=len(tracked_changes) > 0,
        message=f"Successfully analyzed document: {len(comments)} comments, {len(tracked_changes)} tracked changes, {metadata.word_count} words"
    )


@mcp.tool(
    description="Get server information for the Word Documents Tool, including available functions and dependency status."
)
def server_info() -> ServerInfo:
    """Get Word Documents Tool server information."""
    try:
        import subprocess
        
        # Check pandoc availability
        result = subprocess.run(
            ["pandoc", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        pandoc_version = result.stdout.split('\n')[0].strip() if result.stdout else "Available"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pandoc_version = "Not available"
    
    available_functions = [
        "detect_format",
        "extract_comments", 
        "extract_tracked_changes",
        "docx_to_markdown",
        "markdown_to_docx",
        "docx_to_html",
        "docx_to_text",
        "analyze_document",
        "server_info"
    ]
    
    return ServerInfo(
        name="Word Documents Tool",
        version="1.0.0",
        status="active",
        capabilities=available_functions,
        dependencies={
            "pandoc": pandoc_version,
            "supported_inputs": ".docx, .doc, extracted XML",
            "supported_outputs": ".md, .html, .txt, .docx",
            "xml_parser": "Built-in xml.etree.ElementTree"
        }
    )
```

`src/mcp_handley_lab/word/utils.py`:

```py
"""Utility functions for Word documents processing."""

import mimetypes
import zipfile
from pathlib import Path

from .models import FormatDetectionResult


def detect_word_format(file_path: str) -> FormatDetectionResult:
    """Detect Word document format and validate if processable."""
    file_path_obj = Path(file_path)
    
    if not file_path_obj.exists():
        return FormatDetectionResult(
            file_path=file_path,
            detected_format="unknown",
            is_valid=False,
            can_process=False,
            message=f"File not found: {file_path}"
        )
    
    # Check file extension first
    suffix = file_path_obj.suffix.lower()
    
    # Check MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    
    # Detect DOCX format (ZIP-based OpenXML)
    if suffix == '.docx' or mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Check for required DOCX structure
                required_files = ['[Content_Types].xml', 'word/document.xml']
                if all(f in zip_file.namelist() for f in required_files):
                    return FormatDetectionResult(
                        file_path=file_path,
                        detected_format="docx",
                        is_valid=True,
                        format_version="OpenXML",
                        can_process=True,
                        message="Valid DOCX document detected"
                    )
        except (zipfile.BadZipFile, FileNotFoundError):
            pass
    
    # Detect DOC format (older binary format)
    if suffix == '.doc' or mime_type == 'application/msword':
        try:
            # Check for OLE header signature
            with open(file_path, 'rb') as f:
                header = f.read(8)
                if header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
                    return FormatDetectionResult(
                        file_path=file_path,
                        detected_format="doc",
                        is_valid=True,
                        format_version="Binary DOC",
                        can_process=True,
                        message="Valid DOC document detected"
                    )
        except (IOError, OSError):
            pass
    
    # Check if it's a directory with extracted DOCX XML files
    if file_path_obj.is_dir():
        word_dir = file_path_obj / "word"
        if (word_dir / "document.xml").exists() and (file_path_obj / "[Content_Types].xml").exists():
            return FormatDetectionResult(
                file_path=file_path,
                detected_format="xml",
                is_valid=True,
                format_version="Extracted DOCX XML",
                can_process=True,
                message="Valid extracted DOCX XML structure detected"
            )
    
    # Check if it's a standalone document.xml file
    if file_path_obj.name == "document.xml" and file_path_obj.exists():
        return FormatDetectionResult(
            file_path=file_path,
            detected_format="xml",
            is_valid=True,
            format_version="DOCX document.xml",
            can_process=True,
            message="Valid DOCX document.xml file detected"
        )
    
    return FormatDetectionResult(
        file_path=file_path,
        detected_format="unknown",
        is_valid=False,
        can_process=False,
        message="Unrecognized or invalid Word document format"
    )


def is_word_document(file_path: str) -> bool:
    """Quick check if file is a processable Word document."""
    result = detect_word_format(file_path)
    return result.can_process


def get_document_extension(file_path: str) -> str:
    """Get the appropriate file extension for a document path."""
    return Path(file_path).suffix.lower()
```